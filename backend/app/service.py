import csv
from datetime import date, datetime, timedelta

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import and_, create_engine, func, or_, select, text, update

from .config import Settings
from .db import actual_hourly, forecast_hourly, forecast_metadata, insert_missing, metadata


class BoardingsService:
    def __init__(self, settings: Settings, predictor):
        self.settings = settings
        self.predictor = predictor
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        self.engine = create_engine(settings.database_url, connect_args=connect_args)
        self.forecast_start = settings.historical_end + timedelta(days=1)
        self.precomputed_end = settings.historical_end + timedelta(days=settings.precompute_days)

    def initialize(self):
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                # Only one API worker populates the shared tables at a time.
                connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('mostrans-startup'))"))
            self._seed_history(connection)
            self._check_history(connection)
            self._ensure_metadata(connection)
            self._fill_forecasts(
                connection, datetime.combine(self.forecast_start, datetime.min.time()),
                datetime.combine(self.precomputed_end + timedelta(days=1), datetime.min.time()),
                self.predictor.routes,
            )

    def close(self):
        self.engine.dispose()

    def _seed_history(self, connection):
        with self.settings.history_csv.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file, delimiter=";")
            batch = []
            for row in reader:
                batch.append({
                    "route": int(row["route"]), "date": date.fromisoformat(row["date"]),
                    "hour": int(row["hour"]), "boardings": int(row["boardings"]),
                })
                if len(batch) == 2000:
                    insert_missing(connection, actual_hourly, batch)
                    batch.clear()
            insert_missing(connection, actual_hourly, batch)

    def _check_history(self, connection):
        first, last, count = connection.execute(select(
            func.min(actual_hourly.c.date), func.max(actual_hourly.c.date), func.count(),
        ).where(actual_hourly.c.route.in_(self.predictor.routes))).one()
        if last != self.settings.historical_end:
            raise ValueError("Prepared history does not match historical_end")
        expected = ((last - first).days + 1) * len(self.predictor.routes) * 24
        if count != expected:
            raise ValueError("Prepared history is incomplete")
        self.historical_start = first

    def _ensure_metadata(self, connection):
        version = self.predictor.version
        insert_missing(connection, forecast_metadata, [{
            "forecast_version": version, "historical_end": self.settings.historical_end,
            "precomputed_end": self.precomputed_end,
        }])
        connection.execute(update(forecast_metadata).where(
            forecast_metadata.c.forecast_version == version,
        ).values(precomputed_end=self.precomputed_end))

    def _fill_forecasts(self, connection, start: datetime, end: datetime, routes: list[int]):
        if start >= end:
            return
        existing = set(connection.execute(select(
            forecast_hourly.c.route, forecast_hourly.c.date, forecast_hourly.c.hour,
        ).where(
            forecast_hourly.c.forecast_version == self.predictor.version,
            forecast_hourly.c.date >= start.date(), forecast_hourly.c.date <= (end - timedelta(hours=1)).date(),
            forecast_hourly.c.route.in_(routes),
        )).all())
        missing = []
        instant = start
        while instant < end:
            for route in routes:
                if (route, instant.date(), instant.hour) not in existing:
                    missing.append({"route": route, "date": instant.date().isoformat(), "hour": instant.hour})
                if len(missing) == 7200:
                    self._predict_and_save(connection, missing)
                    missing.clear()
            instant += timedelta(hours=1)
        self._predict_and_save(connection, missing)

    def _predict_and_save(self, connection, missing):
        if not missing:
            return
        result = self.predictor.predict_frame(pd.DataFrame(missing))
        rows = [{
            "forecast_version": self.predictor.version,
            "route": int(row.route), "date": date.fromisoformat(row.date),
            "hour": int(row.hour), "boardings": int(row.prediction),
        } for row in result.itertuples(index=False)]
        insert_missing(connection, forecast_hourly, rows)

    def get_metadata(self):
        return {
            "routes": self.predictor.routes,
            "historical_start": self.historical_start.isoformat(),
            "historical_end": self.settings.historical_end.isoformat(),
            "precomputed_end": self.precomputed_end.isoformat(),
            "forecast_version": self.predictor.version,
        }

    def get_boardings(self, start: datetime, end: datetime, route: int | None, group_by: str):
        if start.tzinfo is not None or end.tzinfo is not None:
            raise HTTPException(422, "Use local dataset time without a timezone offset")
        if start >= end or start.minute or start.second or start.microsecond or end.minute or end.second or end.microsecond:
            raise HTTPException(422, "The interval must be positive and aligned to whole hours")
        if start.date() < self.historical_start:
            raise HTTPException(422, f"History starts on {self.historical_start}")
        if route is not None and route not in self.predictor.routes:
            raise HTTPException(422, f"Unsupported route: {route}")
        routes = [route] if route is not None else self.predictor.routes
        actual_end = datetime.combine(self.forecast_start, datetime.min.time())
        points = []
        with self.engine.begin() as connection:
            if start < actual_end:
                points.extend(self._aggregate(connection, actual_hourly, start,
                                              min(end, actual_end), routes, group_by))
            if end > actual_end:
                forecast_from = max(start, actual_end)
                # Startup fills this range, so only later dates need cache-miss inference.
                uncached_from = max(forecast_from, datetime.combine(
                    self.precomputed_end + timedelta(days=1), datetime.min.time(),
                ))
                self._fill_forecasts(connection, uncached_from, end, routes)
                try:
                    forecast_points = self._aggregate(connection, forecast_hourly,
                                                      forecast_from, end, routes, group_by)
                except HTTPException as error:
                    if error.status_code != 503:
                        raise
                    # Repair a missing cached row without scanning the whole configured grid.
                    self._fill_forecasts(connection, forecast_from, end, routes)
                    forecast_points = self._aggregate(connection, forecast_hourly,
                                                      forecast_from, end, routes, group_by)
                points.extend(forecast_points)
        return {"points": sorted(points, key=lambda point: (point["route"], point["start"]))}

    def _aggregate(self, connection, table, start: datetime, end: datetime,
                   routes: list[int], group_by: str):
        last = end - timedelta(hours=1)
        filters = [
            table.c.route.in_(routes),
            or_(table.c.date > start.date(), and_(table.c.date == start.date(), table.c.hour >= start.hour)),
            or_(table.c.date < last.date(), and_(table.c.date == last.date(), table.c.hour <= last.hour)),
        ]
        source = "actual" if table is actual_hourly else "forecast"
        if source == "forecast":
            filters.append(table.c.forecast_version == self.predictor.version)

        expected = int((end - start).total_seconds() // 3600) * len(routes)

        if group_by == "hour":
            buckets = [table.c.date, table.c.hour]
        elif group_by == "day":
            buckets = [table.c.date]
        elif connection.dialect.name == "postgresql":
            buckets = [func.date_trunc("month", table.c.date)]
        else:
            buckets = [func.strftime("%Y-%m-01", table.c.date)]
        statement = select(table.c.route, *buckets, func.count(), func.sum(table.c.boardings)).where(
            *filters,
        ).group_by(table.c.route, *buckets).order_by(table.c.route, *buckets)

        points = []
        found = 0
        for row in connection.execute(statement):
            found += row[-2]
            bucket = row[1]
            if group_by == "hour":
                bucket_start = datetime.combine(bucket, datetime.min.time()).replace(hour=row[2])
                bucket_end = bucket_start + timedelta(hours=1)
            else:
                bucket_date = bucket.date() if isinstance(bucket, datetime) else (
                    bucket if isinstance(bucket, date) else date.fromisoformat(bucket[:10])
                )
                bucket_start = datetime.combine(bucket_date, datetime.min.time())
                if group_by == "day":
                    bucket_end = bucket_start + timedelta(days=1)
                else:
                    year = bucket_date.year + (bucket_date.month == 12)
                    month = bucket_date.month % 12 + 1
                    bucket_end = datetime(year, month, 1)
            points.append({
                "route": row[0], "start": max(bucket_start, start).isoformat(),
                "end": min(bucket_end, end).isoformat(), "boardings": int(row[-1]),
                "source": source,
                "forecast_version": self.predictor.version if source == "forecast" else None,
                "historical_end": self.settings.historical_end.isoformat() if source == "forecast" else None,
            })
        # Missing hours must not silently reduce an aggregate total.
        if found != expected:
            raise HTTPException(503, f"Hourly {source} data is incomplete")
        return points
