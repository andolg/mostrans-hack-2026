import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .features import calendar


class SavedPredictor:
    """Run the saved ensemble without retraining."""

    def __init__(self, models_dir: Path, is_holiday):
        metadata = json.loads((models_dir / "metadata.json").read_text(encoding="utf-8"))
        self.routes = metadata["routes"]
        self.weights = metadata["ensemble"]
        self.is_holiday = is_holiday
        self.deep = joblib.load(models_dir / "lgb_l1_deep.joblib")
        self.poisson = joblib.load(models_dir / "lgb_poisson.joblib")
        seasonal = pd.read_csv(models_dir / "median_12w.csv")
        self.seasonal = {
            (int(row.route), int(row.weekday), int(row.hour)): float(row.value)
            for row in seasonal.itertuples(index=False)
        }

    def predict_frame(self, future: pd.DataFrame) -> pd.DataFrame:
        features = calendar(future, self.is_holiday)
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
