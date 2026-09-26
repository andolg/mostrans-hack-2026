import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HolidayCalendar:
    annual: frozenset[str]
    specific: frozenset[str]

    @classmethod
    def from_file(cls, path: Path) -> "HolidayCalendar":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(frozenset(data["annual"]), frozenset(data["specific"]))

    def is_holiday(self, day: str) -> bool:
        return day[5:] in self.annual or day in self.specific
