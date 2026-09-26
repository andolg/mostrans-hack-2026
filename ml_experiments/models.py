"""Calendar (and optional weather) forecasts for horizons where no future validations are known."""

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor


HOLIDAYS = {
    "2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04",
    "2025-01-05", "2025-01-06", "2025-01-07", "2025-01-08",
    "2025-02-23", "2025-03-08", "2025-05-01", "2025-05-09",
    "2025-06-12", "2025-11-04", "2025-12-31",
}


def calendar(frame: pd.DataFrame, is_holiday=None) -> pd.DataFrame:
    date = pd.to_datetime(frame["date"])
    day = date.dt.dayofyear
    result = pd.DataFrame(index=frame.index)
    result["route"] = frame["route"].to_numpy()
    result["hour"] = frame["hour"].to_numpy()
    result["weekday"] = date.dt.dayofweek.to_numpy()
    result["month"] = date.dt.month.to_numpy()
    result["day"] = date.dt.day.to_numpy()
    result["week"] = date.dt.isocalendar().week.to_numpy(dtype="int64")
    result["day_of_year"] = day.to_numpy()
    result["is_weekend"] = (date.dt.dayofweek >= 5).astype(int).to_numpy()
    days = date.dt.strftime("%Y-%m-%d")
    result["is_holiday"] = (
        days.isin(HOLIDAYS) if is_holiday is None else days.map(is_holiday)
    ).astype(int).to_numpy()
    result["summer"] = date.dt.month.isin([6, 7, 8]).astype(int).to_numpy()
    result["school_start"] = date.dt.month.eq(9).astype(int).to_numpy()
    for column in WEATHER_FEATURES:
        if column in frame:
            result[column] = frame[column].to_numpy(dtype=float)
    return result


WEATHER_RAW = [
    "temperature_2m", "apparent_temperature", "precipitation", "rain", "snowfall",
    "snow_depth", "wind_speed_10m",
]
WEATHER_FEATURES = WEATHER_RAW + [
    "precipitation_prev_hour", "precipitation_morning", "precipitation_day",
    "temperature_day_min", "temperature_day_max",
]


def load_weather(path) -> pd.DataFrame:
    """Read fetch_weather.py output and add derived features on the continuous series."""
    weather = pd.read_csv(path, sep=";", dtype={"date": str}).sort_values(["date", "hour"])
    weather = weather[["date", "hour"] + WEATHER_RAW].reset_index(drop=True)
    daily = weather.groupby("date")
    weather["precipitation_prev_hour"] = weather.precipitation.shift(1, fill_value=0)
    morning = weather.precipitation.where(weather.hour.between(6, 10), 0)
    weather["precipitation_morning"] = morning.groupby(weather.date).transform("sum")
    weather["precipitation_day"] = daily.precipitation.transform("sum")
    weather["temperature_day_min"] = daily.temperature_2m.transform("min")
    weather["temperature_day_max"] = daily.temperature_2m.transform("max")
    return weather


def climatology(weather: pd.DataFrame, before: str, window: int = 7) -> pd.DataFrame:
    """Mean weather per (day_of_year, hour) over dates before `before`, smoothed ±window days."""
    history = weather.loc[weather.date < before].copy()
    history["day_of_year"] = pd.to_datetime(history.date).dt.dayofyear
    means = history.groupby(["day_of_year", "hour"])[WEATHER_FEATURES].mean()
    parts = []
    for hour in range(24):
        table = means.xs(hour, level="hour").reindex(range(1, 367)).interpolate(limit_direction="both")
        wrapped = pd.concat([table.iloc[-window:], table, table.iloc[:window]])
        smooth = wrapped.rolling(2 * window + 1, center=True).mean().iloc[window:-window]
        parts.append(smooth.assign(hour=hour).rename_axis("day_of_year").reset_index())
    return pd.concat(parts, ignore_index=True)


def add_weather(frame: pd.DataFrame, weather: pd.DataFrame | None,
                climate: pd.DataFrame | None = None) -> pd.DataFrame:
    """Join weather by (date, hour); fill dates outside `weather` from `climate`."""
    if weather is None:
        result = frame.assign(**{column: np.nan for column in WEATHER_FEATURES})
    else:
        result = frame.merge(weather[["date", "hour"] + WEATHER_FEATURES],
                             on=["date", "hour"], how="left")
    missing = result[WEATHER_FEATURES[0]].isna()
    if climate is not None and missing.any():
        keys = pd.DataFrame({"day_of_year": pd.to_datetime(result.date[missing]).dt.dayofyear,
                             "hour": result.hour[missing]})
        filled = keys.merge(climate, on=["day_of_year", "hour"], how="left")
        result.loc[missing, WEATHER_FEATURES] = filled[WEATHER_FEATURES].to_numpy()
    assert not result[WEATHER_FEATURES].isna().any().any(), "weather is missing for some hours"
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
