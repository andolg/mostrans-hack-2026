"""Calendar-only forecasts for horizons where no future validations are known."""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.holidays import HolidayCalendar

CALENDAR = HolidayCalendar(Path(os.environ.get(
    "CALENDAR_DIR", Path(__file__).resolve().parents[1] / "untracked/calendar",
)))


def calendar(frame: pd.DataFrame, calendar_data=None) -> pd.DataFrame:
    date = pd.to_datetime(frame["date"])
    day = date.dt.dayofyear
    days = date.dt.strftime("%Y-%m-%d")
    codes = days.map((calendar_data or CALENDAR).code)
    result = pd.DataFrame(index=frame.index)
    result["route"] = frame["route"].to_numpy()
    result["hour"] = frame["hour"].to_numpy()
    result["weekday"] = date.dt.dayofweek.to_numpy()
    result["month"] = date.dt.month.to_numpy()
    result["day"] = date.dt.day.to_numpy()
    result["week"] = date.dt.isocalendar().week.to_numpy(dtype="int64")
    result["day_of_year"] = day.to_numpy()
    result["is_weekend"] = codes.isin([1, 8]).astype(int).to_numpy()
    result["is_holiday"] = codes.eq(8).astype(int).to_numpy()
    result["is_short_day"] = codes.eq(2).astype(int).to_numpy()
    result["summer"] = date.dt.month.isin([6, 7, 8]).astype(int).to_numpy()
    result["school_start"] = date.dt.month.eq(9).astype(int).to_numpy()
    return result


def profile_table(train: pd.DataFrame, weeks: int = 8,
                  statistic: str = "median") -> pd.DataFrame:
    end = pd.Timestamp(train.date.max())
    recent = train.loc[pd.to_datetime(train.date) > end - pd.Timedelta(weeks=weeks)]
    recent = recent.copy()
    recent["weekday"] = pd.to_datetime(recent.date).dt.dayofweek
    return recent.groupby(["route", "weekday", "hour"], as_index=False).boardings.agg(
        statistic,
    ).rename(columns={"boardings": "value"})


def profile(train: pd.DataFrame, future: pd.DataFrame, weeks: int = 8,
            statistic: str = "median") -> np.ndarray:
    learned = profile_table(train, weeks, statistic).set_index(
        ["route", "weekday", "hour"],
    ).value
    target = future.copy()
    target["weekday"] = pd.to_datetime(target.date).dt.dayofweek
    keys = ["route", "weekday", "hour"]
    return target.set_index(keys).index.map(learned).fillna(0).to_numpy(dtype=float)


def lightgbm(train: pd.DataFrame, future: pd.DataFrame, objective: str = "regression_l1",
             leaves: int = 31, min_child_samples: int = 60,
             n_estimators: int = 450, recent_days: int | None = None) -> tuple[np.ndarray, LGBMRegressor]:
    if recent_days is not None:
        cutoff = pd.Timestamp(train.date.max()) - pd.Timedelta(days=recent_days)
        train = train.loc[pd.to_datetime(train.date) > cutoff]
    model = LGBMRegressor(
        objective=objective, n_estimators=n_estimators, learning_rate=0.035,
        num_leaves=leaves, min_child_samples=min_child_samples,
        max_depth=-1, verbosity=-1, n_jobs=4, random_state=42,
    )
    model.fit(calendar(train), train.boardings)
    prediction = np.maximum(0, model.predict(calendar(future)))
    prediction[future.route.to_numpy() == 5] = 0
    return prediction, model


def catboost(train: pd.DataFrame, future: pd.DataFrame,
             loss: str = "MAE"):
    from catboost import CatBoostRegressor

    features = calendar(train)
    future_features = calendar(future)
    cats = ["route", "hour", "weekday", "month", "is_weekend", "is_holiday", "summer"]
    for column in cats:
        features[column] = features[column].astype(str)
        future_features[column] = future_features[column].astype(str)
    model = CatBoostRegressor(
        loss_function=loss, iterations=550, depth=7, learning_rate=0.055,
        thread_count=4, verbose=False, random_seed=42,
        allow_writing_files=False,
    )
    model.fit(features, train.boardings, cat_features=cats)
    prediction = np.maximum(0, model.predict(future_features))
    prediction[future.route.to_numpy() == 5] = 0
    return prediction, model


def selected_ensemble(train: pd.DataFrame, future: pd.DataFrame):
    deep, deep_model = lightgbm(
        train, future, leaves=63, min_child_samples=35, n_estimators=650,
    )
    poisson, poisson_model = lightgbm(train, future, objective="poisson")
    seasonal = profile(train, future, weeks=12)
    return 0.7 * deep + 0.1 * poisson + 0.2 * seasonal, {
        "lgb_l1_deep": deep_model, "lgb_poisson": poisson_model,
    }


def wape_score(y: np.ndarray, prediction: np.ndarray) -> float:
    return max(0.0, 1 - np.abs(y - prediction).sum() / y.sum())
