import hashlib
import json
from pathlib import Path

from backend.ml.inference import SavedPredictor

from .config import Settings
from .holidays import HolidayCalendar


class ModelPredictor:
    def __init__(self, settings: Settings):
        holidays_path = settings.holidays_json or Path(__file__).resolve().parents[1] / "holidays.json"
        metadata = json.loads((settings.models_dir / "metadata.json").read_text(encoding="utf-8"))
        if metadata["train_end"] != settings.historical_end.isoformat():
            raise ValueError("Model training cutoff differs from historical_end")
        holidays = HolidayCalendar.from_file(holidays_path)
        self.model = SavedPredictor(settings.models_dir, is_holiday=holidays.is_holiday)
        self.routes = self.model.routes

        # Changing model files or the calendar must create a new cache version.
        digest = hashlib.sha256()
        for path in sorted(settings.models_dir.iterdir()):
            if path.is_file():
                digest.update(path.name.encode())
                digest.update(path.read_bytes())
        digest.update(holidays_path.read_bytes())
        self.version = digest.hexdigest()[:16]

    def predict_frame(self, frame):
        return self.model.predict_frame(frame)


def load_predictor(settings: Settings) -> ModelPredictor:
    return ModelPredictor(settings)
