from pathlib import Path

import pandas as pd

from backend.app.holidays import HolidayCalendar
from backend.ml.features import calendar


def test_calendar_uses_api_days_and_falls_back_for_future_years():
    holidays = HolidayCalendar.from_dir(Path(__file__).resolve().parents[1] / "calendar")
    assert holidays.code("2024-04-27") == 0  # working Saturday
    assert holidays.code("2025-11-01") == 2  # shortened Saturday
    assert holidays.code("2025-11-03") == 1  # moved day off on Monday
    assert holidays.code("2025-11-04") == 8
    assert holidays.code("2027-01-09") == 1  # ordinary fallback weekend
    assert holidays.code("2027-01-01") == 8  # fixed national holiday
    assert holidays.code("2027-05-03") == 0  # no guessed transfer
    frame = pd.DataFrame({
        "route": [1, 1, 1, 1],
        "date": ["2024-04-27", "2025-11-01", "2025-11-03", "2025-11-04"],
        "hour": [8, 8, 8, 8],
    })
    features = calendar(frame, holidays)
    assert features["is_weekend"].tolist() == [0, 0, 1, 1]
    assert features["is_holiday"].tolist() == [0, 0, 0, 1]
    assert features["is_short_day"].tolist() == [0, 1, 0, 0]
