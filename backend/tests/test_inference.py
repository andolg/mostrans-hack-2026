import json

import joblib
import pandas as pd

from backend.ml.inference import SavedPredictor


class FakeBooster:
    def predict(self, features, num_threads):
        return (features["hour"].to_numpy(dtype=float)
                + 10 * features["is_holiday"].to_numpy()
                + 5 * features["is_short_day"].to_numpy())


class FakeModel:
    booster_ = FakeBooster()


def test_saved_predictor_uses_local_features_and_artifacts(tmp_path):
    metadata = {
        "routes": [1, 5],
        "ensemble": {"lgb_l1_deep": 0.7, "lgb_poisson": 0.1, "median_12w": 0.2},
    }
    (tmp_path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    joblib.dump(FakeModel(), tmp_path / "lgb_l1_deep.joblib")
    joblib.dump(FakeModel(), tmp_path / "lgb_poisson.joblib")
    pd.DataFrame([{"route": 1, "weekday": 4, "hour": 8, "value": 5}]).to_csv(
        tmp_path / "median_12w.csv", index=False,
    )

    from backend.app.holidays import HolidayCalendar

    holidays = HolidayCalendar(tmp_path)
    holidays.codes.update({"2026-01-09": 8, "2026-01-10": 2})
    predictor = SavedPredictor(tmp_path, calendar_data=holidays)
    frame = pd.DataFrame({
        "route": [1, 1, 5],
        "date": ["2026-01-09", "2026-01-10", "2026-01-09"],
        "hour": [8, 8, 8],
    })
    assert predictor.predict_frame(frame).prediction.tolist() == [15, 10, 0]
