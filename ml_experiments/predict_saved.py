"""Run a saved ensemble on a requested calendar grid without retraining."""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from models import calendar


def predict(models_dir: Path, output: Path, start: str, end: str) -> pd.DataFrame:
    metadata = json.loads((models_dir / "metadata.json").read_text())
    index = pd.MultiIndex.from_product(
        [metadata["routes"], pd.date_range(start, end).strftime("%Y-%m-%d"), range(24)],
        names=["route", "date", "hour"],
    )
    future = index.to_frame(index=False)
    weights = metadata["ensemble"]
    deep = np.maximum(0, joblib.load(models_dir / "lgb_l1_deep.joblib").predict(calendar(future)))
    poisson = np.maximum(0, joblib.load(models_dir / "lgb_poisson.joblib").predict(calendar(future)))
    seasonal = pd.read_csv(models_dir / "median_12w.csv").set_index(
        ["route", "weekday", "hour"],
    ).value
    weekday = pd.to_datetime(future.date).dt.dayofweek
    keys = pd.MultiIndex.from_arrays([future.route, weekday, future.hour])
    median = keys.map(seasonal).fillna(0).to_numpy(dtype=float)
    prediction = (weights["lgb_l1_deep"] * deep +
                  weights["lgb_poisson"] * poisson +
                  weights["median_12w"] * median)
    prediction[future.route.to_numpy() == 5] = 0
    result = future.assign(prediction=np.maximum(0, np.rint(prediction)).astype(int))
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
