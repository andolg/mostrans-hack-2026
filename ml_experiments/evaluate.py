"""Backtest two-month hourly forecasts on consecutive held-out windows."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from models import (WEATHER_FEATURES, add_weather, climatology, lightgbm, load_weather,
                    profile, selected_ensemble, wape_score)


FOLDS = [
    ("2025-04-30", "2025-05-01", "2025-06-30"),
    ("2025-06-30", "2025-07-01", "2025-08-31"),
    ("2025-08-31", "2025-09-01", "2025-10-31"),
]
# Climatology uses only years before the backtested data to avoid leakage.
CLIMATE_BEFORE = "2025-01-01"


def add_weather_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--weather", type=Path, help="fetch_weather.py output; omit for calendar only")
    parser.add_argument("--weather-mode", choices=["actual", "climate"], default="actual",
                        help="weather for test windows: observed or climatology")
    parser.add_argument("--weather-columns", default=",".join(WEATHER_FEATURES),
                        help="comma-separated subset of weather features to use")


def fold_splitter(data: pd.DataFrame, args):
    """Return a function (cutoff, first, last) -> (train, test) with weather attached."""
    weather = load_weather(args.weather) if args.weather else None
    climate = climatology(weather, CLIMATE_BEFORE) if weather is not None else None
    drop = sorted(set(WEATHER_FEATURES) - set(args.weather_columns.split(",")))

    def split(cutoff: str, first: str, last: str):
        train, test = split(cutoff, first, last)
        if weather is None:
            return train, test
        train = add_weather(train, weather)
        test = add_weather(test, weather if args.weather_mode == "actual" else None, climate)
        return train.drop(columns=drop), test.drop(columns=drop)

    return split


def evaluate(data: pd.DataFrame, output: Path, split) -> list[dict]:
    scores = []
    predictions = []
    methods = {
        "median_4w": lambda tr, te: profile(tr, te, 4, "median"),
        "median_8w": lambda tr, te: profile(tr, te, 8, "median"),
        "median_12w": lambda tr, te: profile(tr, te, 12, "median"),
        "mean_8w": lambda tr, te: profile(tr, te, 8, "mean"),
        "lgb_l1": lambda tr, te: lightgbm(tr, te)[0],
        "lgb_poisson": lambda tr, te: lightgbm(tr, te, "poisson")[0],
        "selected_ensemble": lambda tr, te: selected_ensemble(tr, te)[0],
    }
    for cutoff, first, last in FOLDS:
        train, test = split(cutoff, first, last)
        for name, predict in methods.items():
            values = np.maximum(0, np.rint(predict(train, test)))
            score = wape_score(test.boardings.to_numpy(), values)
            scores.append({"train_end": cutoff, "test_start": first,
                           "test_end": last, "model": name,
                           "wape_score": round(score, 6)})
            predictions.append(test[["route", "date", "hour", "boardings"]].assign(
                model=name, prediction=values, fold=first))
            print(f"{first} {name:14s} {score:.5f}", flush=True)
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(scores).to_csv(output / "scores.csv", index=False)
    pd.concat(predictions).to_csv(output / "backtest_predictions.csv", index=False)
    (output / "folds.json").write_text(json.dumps(FOLDS, indent=2))
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    add_weather_args(parser)
    args = parser.parse_args()
    data = pd.read_csv(args.data, sep=";", dtype={"date": str})
    evaluate(data, args.output, fold_splitter(data, args))


if __name__ == "__main__":
    main()
