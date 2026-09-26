import pandas as pd


def calendar(frame: pd.DataFrame, calendar_data) -> pd.DataFrame:
    day = pd.to_datetime(frame["date"])
    codes = day.dt.strftime("%Y-%m-%d").map(calendar_data.code)
    result = pd.DataFrame(index=frame.index)
    result["route"] = frame["route"].to_numpy()
    result["hour"] = frame["hour"].to_numpy()
    result["weekday"] = day.dt.dayofweek.to_numpy()
    result["month"] = day.dt.month.to_numpy()
    result["day"] = day.dt.day.to_numpy()
    result["week"] = day.dt.isocalendar().week.to_numpy(dtype="int64")
    result["day_of_year"] = day.dt.dayofyear.to_numpy()
    result["is_weekend"] = codes.isin([1, 8]).astype(int).to_numpy()
    result["is_holiday"] = codes.eq(8).astype(int).to_numpy()
    result["is_short_day"] = codes.eq(2).astype(int).to_numpy()
    result["summer"] = day.dt.month.isin([6, 7, 8]).astype(int).to_numpy()
    result["school_start"] = day.dt.month.eq(9).astype(int).to_numpy()
    return result
