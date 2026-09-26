"""Compare independently weighted holiday and weather specialists on the fixed folds."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from evaluate import CLIMATE_BEFORE, FOLDS
from models import WEATHER_FEATURES, add_weather, calendar, climatology, load_weather, profile, wape_score


def ensemble(train: pd.DataFrame, test: pd.DataFrame, *, holiday: bool, weather: bool):
    train_features = calendar(train)
    test_features = calendar(test)
    if not holiday:
        train_features = train_features.drop(columns="is_holiday")
        test_features = test_features.drop(columns="is_holiday")
    if not weather:
        weather_columns = [column for column in WEATHER_FEATURES if column in train_features]
        train_features = train_features.drop(columns=weather_columns)
        test_features = test_features.drop(columns=weather_columns)

    common = dict(learning_rate=0.035, max_depth=-1, verbosity=-1, n_jobs=4, random_state=42)
    deep = LGBMRegressor(objective="regression_l1", n_estimators=650, num_leaves=63,
                        min_child_samples=35, **common)
    poisson = LGBMRegressor(objective="poisson", n_estimators=450, num_leaves=31,
                           min_child_samples=60, **common)
    deep.fit(train_features, train.boardings)
    poisson.fit(train_features, train.boardings)
    deep_values = np.maximum(0, deep.predict(test_features))
    poisson_values = np.maximum(0, poisson.predict(test_features))
    deep_values[test.route.to_numpy() == 5] = 0
    poisson_values[test.route.to_numpy() == 5] = 0
    return 0.7 * deep_values + 0.1 * poisson_values + 0.2 * profile(train, test, weeks=12)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--weather", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = pd.read_csv(args.data, sep=";", dtype={"date": str})
    observed_weather = load_weather(args.weather)
    climate = climatology(observed_weather, CLIMATE_BEFORE)
    parts = []
    for cutoff, first, last in FOLDS:
        train = data.loc[data.date <= cutoff].reset_index(drop=True)
        test = data.loc[data.date.between(first, last)].reset_index(drop=True)
        train_weather = add_weather(train, observed_weather)
        test_weather = add_weather(test, None, climate)
        base = ensemble(train, test, holiday=False, weather=False)
        holiday = ensemble(train, test, holiday=True, weather=False)
        weather = ensemble(train_weather, test_weather, holiday=False, weather=True)
        parts.append(test[["route", "date", "hour", "boardings"]].assign(
            fold=first, is_holiday=calendar(test).is_holiday.to_numpy(),
            base=base, holiday=holiday, weather=weather,
        ))
        print(f"{first}: base={wape_score(test.boardings, np.rint(base)):.5f} "
              f"holiday={wape_score(test.boardings, np.rint(holiday)):.5f} "
              f"weather={wape_score(test.boardings, np.rint(weather)):.5f}", flush=True)

    predictions = pd.concat(parts, ignore_index=True)
    weights = [0.0, 0.25, 0.5, 1.0]
    scores = []
    for holiday_scope in ["all_dates", "holiday_dates"]:
        holiday_mask = 1 if holiday_scope == "all_dates" else predictions.is_holiday
        for holiday_weight in weights:
            for weather_weight in weights:
                estimate = (predictions.base + holiday_weight * holiday_mask *
                            (predictions.holiday - predictions.base) +
                            weather_weight * (predictions.weather - predictions.base))
                estimate = np.maximum(0, np.rint(estimate))
                for fold, group in [("pooled", predictions), *predictions.groupby("fold")]:
                    chosen = estimate.loc[group.index]
                    scores.append({
                        "fold": fold, "holiday_scope": holiday_scope,
                        "holiday_weight": holiday_weight, "weather_weight": weather_weight,
                        "wape_score": round(wape_score(group.boardings.to_numpy(), chosen.to_numpy()), 6),
                    })
    args.output.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(args.output / "component_predictions.csv", index=False)
    pd.DataFrame(scores).to_csv(args.output / "weight_scores.csv", index=False)


if __name__ == "__main__":
    main()
