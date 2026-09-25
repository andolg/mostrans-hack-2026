"""Additional model comparison, using the same fixed chronological folds."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate import FOLDS
from models import catboost, lightgbm, wape_score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = pd.read_csv(args.data, sep=";", dtype={"date": str})
    methods = {
        "lgb_l1_180d": lambda tr, te: lightgbm(tr, te, recent_days=180)[0],
        "lgb_l1_120d": lambda tr, te: lightgbm(tr, te, recent_days=120)[0],
        "lgb_l1_deep": lambda tr, te: lightgbm(tr, te, leaves=63, min_child_samples=35,
                                                n_estimators=650)[0],
        "catboost_mae": lambda tr, te: catboost(tr, te)[0],
        "catboost_rmse": lambda tr, te: catboost(tr, te, "RMSE")[0],
    }
    scores = []
    predictions = []
    for cutoff, first, last in FOLDS:
        train = data.loc[data.date <= cutoff].reset_index(drop=True)
        test = data.loc[data.date.between(first, last)].reset_index(drop=True)
        for name, predict in methods.items():
            values = np.maximum(0, np.rint(predict(train, test)))
            score = wape_score(test.boardings.to_numpy(), values)
            scores.append({"train_end": cutoff, "test_start": first,
                           "test_end": last, "model": name,
                           "wape_score": round(score, 6)})
            predictions.append(test.assign(model=name, prediction=values, fold=first))
            print(f"{first} {name:16s} {score:.5f}", flush=True)
    args.output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(scores).to_csv(args.output / "scores.csv", index=False)
    pd.concat(predictions).to_csv(args.output / "backtest_predictions.csv", index=False)


if __name__ == "__main__":
    main()
