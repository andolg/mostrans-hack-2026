"""Russian workday calendar, backed by saved isDayOff yearly snapshots."""

import csv
import json
from datetime import date, timedelta
from pathlib import Path


class HolidayCalendar:
    def __init__(self, directory: Path):
        self.directory = directory
        fallback = Path(__file__).resolve().parents[1] / "holidays.json"
        self.annual = set(json.loads(fallback.read_text(encoding="utf-8"))["annual"])
        self.codes = {}
        for path in sorted(directory.glob("[0-9][0-9][0-9][0-9].csv")):
            with path.open(newline="", encoding="utf-8") as source:
                rows = list(csv.DictReader(source))
            year = int(path.stem)
            expected = [date(year, 1, 1) + timedelta(days=i)
                        for i in range((date(year + 1, 1, 1) - date(year, 1, 1)).days)]
            if [row["date"] for row in rows] != [day.isoformat() for day in expected]:
                raise ValueError(f"Incomplete calendar: {path}")
            self.codes.update((row["date"], int(row["day_type"])) for row in rows)

    def code(self, day: str) -> int:
        if day in self.codes:
            return self.codes[day]
        current = date.fromisoformat(day)
        if day[5:] in self.annual:
            return 8
        return 1 if current.weekday() >= 5 else 0

    def is_day_off(self, day: str) -> bool:
        return self.code(day) in (1, 8)

    def is_holiday(self, day: str) -> bool:
        return self.code(day) == 8

    def is_short_day(self, day: str) -> bool:
        return self.code(day) == 2
