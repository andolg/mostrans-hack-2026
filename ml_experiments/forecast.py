"""Fit the selected ensemble and write a full-grid submission and models."""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from models import calendar, profile_table, selected_ensemble


def forecast(data: pd.DataFrame, start: str, end: str,
             output: Path, models_dir: Path) -> pd.DataFrame:
    routes = sorted(int(route) for route in data.route.unique())
    index = pd.MultiIndex.from_product(
        [routes, pd.date_range(start, end).strftime("%Y-%m-%d"), range(24)],
        names=["route", "date", "hour"],
    )
    future = index.to_frame(index=False)
    values, models = selected_ensemble(data, future)
    prediction = np.maximum(0, np.rint(values)).astype(int)
    result = future.assign(prediction=prediction)

    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, sep=";", index=False)
    models_dir.mkdir(parents=True, exist_ok=True)
    for name, model in models.items():
        joblib.dump(model, models_dir / f"{name}.joblib")
    profile_table(data, weeks=12).to_csv(models_dir / "median_12w.csv", index=False)
    (models_dir / "metadata.json").write_text(json.dumps({
        "train_end": str(data.date.max()), "forecast_start": start,
        "forecast_end": end, "routes": routes,
        "ensemble": {"lgb_l1_deep": 0.7, "lgb_poisson": 0.1,
                     "median_12w": 0.2},
        "features": list(calendar(future).columns),
    }, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--start", default="2025-11-01")
    parser.add_argument("--end", default="2025-12-31")
    args = parser.parse_args()
    data = pd.read_csv(args.data, sep=";", dtype={"date": str})
    result = forecast(data, args.start, args.end, args.output, args.models_dir)
    print(f"{len(result):,} predictions, total {result.prediction.sum():,} -> {args.output}")


if __name__ == "__main__":
    main()
