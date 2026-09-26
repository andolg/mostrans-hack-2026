from sqlalchemy import Column, Date, ForeignKey, Integer, MetaData, String, Table


metadata = MetaData()

actual_hourly = Table(
    "actual_hourly", metadata,
    Column("route", Integer, primary_key=True),
    Column("date", Date, primary_key=True),
    Column("hour", Integer, primary_key=True),
    Column("boardings", Integer, nullable=False),
)

forecast_metadata = Table(
    "forecast_metadata", metadata,
    Column("forecast_version", String(64), primary_key=True),
    Column("historical_end", Date, nullable=False),
    Column("precomputed_end", Date, nullable=False),
)

forecast_hourly = Table(
    "forecast_hourly", metadata,
    Column("forecast_version", String(64), ForeignKey("forecast_metadata.forecast_version"), primary_key=True),
    Column("route", Integer, primary_key=True),
    Column("date", Date, primary_key=True),
    Column("hour", Integer, primary_key=True),
    Column("boardings", Integer, nullable=False),
)


def insert_missing(connection, table, rows):
    if not rows:
        return
    if connection.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    connection.execute(insert(table).on_conflict_do_nothing(), rows)
