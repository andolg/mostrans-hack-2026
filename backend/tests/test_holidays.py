from pathlib import Path

import pandas as pd

from backend.app.holidays import HolidayCalendar
from backend.ml.features import calendar


def test_calendar_covers_future_year_and_preserves_model_feature(tmp_path):
    holidays = HolidayCalendar.from_file(Path(__file__).resolve().parents[1] / "holidays.json")
    assert holidays.is_holiday("2025-12-31")
    assert holidays.is_holiday("2026-01-01")
    assert holidays.is_holiday("2026-01-09")
    assert not holidays.is_holiday("2026-01-10")
    frame = pd.DataFrame({
        "route": [1, 1], "date": ["2026-01-09", "2026-01-10"], "hour": [8, 8],
    })
    assert calendar(frame, is_holiday=holidays.is_holiday)["is_holiday"].tolist() == [1, 0]
