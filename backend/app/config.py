import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    history_csv: Path
    models_dir: Path
    historical_end: date
    precompute_days: int
    database_url: str
    holidays_json: Path | None = None

    @classmethod
    def from_file(cls, path: Path) -> "Settings":
        data = json.loads(path.read_text(encoding="utf-8"))

        def resolve(value: str) -> Path:
            file_path = Path(value)
            return file_path if file_path.is_absolute() else path.parent / file_path

        return cls(
            history_csv=resolve(data["history_csv"]),
            models_dir=resolve(data["models_dir"]),
            historical_end=date.fromisoformat(data["historical_end"]),
            precompute_days=int(data.get("precompute_days", 365)),
            database_url=os.environ["DATABASE_URL"],
            holidays_json=resolve(data["holidays_json"]) if "holidays_json" in data else None,
        )
