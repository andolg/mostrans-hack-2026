"""Run a saved ensemble on a requested calendar grid without retraining."""

import argparse
import json
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

if __package__:
    from .models import CALENDAR, calendar
else:
    from models import CALENDAR, calendar


class SavedPredictor:
    """Keep models in memory for repeated route/hour requests."""

    def __init__(self, models_dir: Path, calendar_data=None):
        metadata = json.loads((models_dir / "metadata.json").read_text())
        self.routes = metadata["routes"]
        self.weights = metadata["ensemble"]
        self.forecast_start = metadata["forecast_start"]
        self.forecast_end = metadata["forecast_end"]
        self.precomputed = {}
        self.calendar_data = calendar_data or CALENDAR
        self.deep = joblib.load(models_dir / "lgb_l1_deep.joblib")
        self.poisson = joblib.load(models_dir / "lgb_poisson.joblib")
        seasonal = pd.read_csv(models_dir / "median_12w.csv")
        self.seasonal = {
            (int(row.route), int(row.weekday), int(row.hour)): float(row.value)
            for row in seasonal.itertuples(index=False)
        }

    def predict_one(self, route: int, day: str, hour: int) -> int:
        key = (route, day, hour)
        if key in self.precomputed:
            return self.precomputed[key]
        if route == 5:
            return 0
        current = date.fromisoformat(day)
        weekday = current.weekday()
        code = self.calendar_data.code(day)
        features = np.array([[
            route, hour, weekday, current.month, current.day,
            current.isocalendar().week, current.timetuple().tm_yday,
            int(code in (1, 8)), int(code == 8), int(code == 2),
            int(current.month in (6, 7, 8)), int(current.month == 9),
        ]], dtype=np.int64)
        deep = max(0.0, self.deep.booster_.predict(features, num_threads=1)[0])
        poisson = max(0.0, self.poisson.booster_.predict(features, num_threads=1)[0])
        median = self.seasonal.get((route, weekday, hour), 0.0)
        return max(0, int(np.rint(
            self.weights["lgb_l1_deep"] * deep +
            self.weights["lgb_poisson"] * poisson +
            self.weights["median_12w"] * median,
        )))

    def precompute(self) -> pd.DataFrame:
        """Build the finite scored horizon once at service startup."""
        index = pd.MultiIndex.from_product(
            [self.routes,
             pd.date_range(self.forecast_start, self.forecast_end).strftime("%Y-%m-%d"),
             range(24)],
            names=["route", "date", "hour"],
        )
        result = self.predict_frame(index.to_frame(index=False))
        self.precomputed = {
            (int(row.route), row.date, int(row.hour)): int(row.prediction)
            for row in result.itertuples(index=False)
        }
        return result

    def predict_frame(self, future: pd.DataFrame) -> pd.DataFrame:
        features = calendar(future, calendar_data=self.calendar_data)
        deep = np.maximum(0, self.deep.booster_.predict(features, num_threads=1))
        poisson = np.maximum(0, self.poisson.booster_.predict(features, num_threads=1))
        weekday = pd.to_datetime(future.date).dt.dayofweek
        median = np.fromiter(
            (self.seasonal.get((int(route), int(day), int(hour)), 0.0)
             for route, day, hour in zip(future.route, weekday, future.hour)),
            dtype=float, count=len(future),
        )
        prediction = (self.weights["lgb_l1_deep"] * deep +
                      self.weights["lgb_poisson"] * poisson +
                      self.weights["median_12w"] * median)
        prediction[future.route.to_numpy() == 5] = 0
        return future.assign(prediction=np.maximum(0, np.rint(prediction)).astype(int))


def predict(models_dir: Path, output: Path, start: str, end: str) -> pd.DataFrame:
    predictor = SavedPredictor(models_dir)
    index = pd.MultiIndex.from_product(
        [predictor.routes, pd.date_range(start, end).strftime("%Y-%m-%d"), range(24)],
        names=["route", "date", "hour"],
    )
    future = index.to_frame(index=False)
    result = predictor.predict_frame(future)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, sep=";", index=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    args = parser.parse_args()
    result = predict(args.models_dir, args.output, args.start, args.end)
    print(f"{len(result):,} predictions -> {args.output}")


if __name__ == "__main__":
    main()
