"""Backtest two-month hourly forecasts on consecutive held-out windows."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from models import lightgbm, profile, selected_ensemble, wape_score


FOLDS = [
    ("2025-04-30", "2025-05-01", "2025-06-30"),
    ("2025-06-30", "2025-07-01", "2025-08-31"),
    ("2025-08-31", "2025-09-01", "2025-10-31"),
]


def evaluate(data: pd.DataFrame, output: Path) -> list[dict]:
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
        train = data.loc[data.date <= cutoff].reset_index(drop=True)
        test = data.loc[data.date.between(first, last)].reset_index(drop=True)
        for name, predict in methods.items():
            values = np.maximum(0, np.rint(predict(train, test)))
            score = wape_score(test.boardings.to_numpy(), values)
            scores.append({"train_end": cutoff, "test_start": first,
                           "test_end": last, "model": name,
                           "wape_score": round(score, 6)})
            predictions.append(test.assign(model=name, prediction=values,
                                           fold=first))
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
    args = parser.parse_args()
    data = pd.read_csv(args.data, sep=";", dtype={"date": str})
    evaluate(data, args.output)


if __name__ == "__main__":
    main()
