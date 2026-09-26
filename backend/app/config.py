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
    calendar_dir: Path | None = None
    forecast_batch_size: int = 7200

    @classmethod
    def from_file(cls, path: Path) -> "Settings":
        data = json.loads(path.read_text(encoding="utf-8"))
        forecast_batch_size = int(data.get("forecast_batch_size", 7200))
        if forecast_batch_size < 1:
            raise ValueError("forecast_batch_size must be positive")

        def resolve(value: str) -> Path:
            file_path = Path(value)
            return file_path if file_path.is_absolute() else path.parent / file_path

        return cls(
            history_csv=resolve(data["history_csv"]),
            models_dir=resolve(data["models_dir"]),
            historical_end=date.fromisoformat(data["historical_end"]),
            precompute_days=int(data.get("precompute_days", 365)),
            database_url=os.environ["DATABASE_URL"],
            calendar_dir=resolve(data["calendar_dir"]) if "calendar_dir" in data else None,
            forecast_batch_size=forecast_batch_size,
        )
