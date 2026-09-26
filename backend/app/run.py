import os
from pathlib import Path

from .config import Settings
from .main import create_app


settings_path = Path(os.environ.get("BACKEND_SETTINGS", Path(__file__).resolve().parents[1] / "settings.json"))
app = create_app(Settings.from_file(settings_path))
