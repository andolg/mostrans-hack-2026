import csv
import json
from dataclasses import replace
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select, func

from backend.app.config import Settings
from backend.app.db import actual_hourly, forecast_hourly
from backend.app.main import create_app


class FakePredictor:
    routes = [1, 5]
    version = "test-model"

    def __init__(self):
        self.calls = []

    def predict_frame(self, frame):
        self.calls.append(frame.copy())
        return frame.assign(prediction=frame.route.where(frame.route != 5, 0))


def make_settings(tmp_path, days=1):
    history = tmp_path / "history.csv"
    with history.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(["route", "date", "hour", "boardings"])
        for route in (1, 5):
            for hour in range(24):
                writer.writerow([route, "2025-10-31", hour, 2 if route == 1 and hour == 23 else 0])
    return Settings(
        history_csv=history,
        models_dir=tmp_path,
        historical_end=date(2025, 10, 31),
        precompute_days=days,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
    )


def test_startup_seeds_history_and_precomputes_once(tmp_path):
    settings = make_settings(tmp_path, days=2)
    predictor = FakePredictor()
    app = create_app(settings, predictor_factory=lambda: predictor)

    with TestClient(app) as client:
        metadata = client.get("/api/metadata").json()
        assert metadata == {
            "routes": [1, 5],
            "historical_start": "2025-10-31",
            "historical_end": "2025-10-31",
            "precomputed_end": "2025-11-02",
            "forecast_version": "test-model",
        }
        assert client.get("/health").status_code == 200

    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(actual_hourly)) == 48
        assert connection.scalar(select(func.count()).select_from(forecast_hourly)) == 96
    assert len(predictor.calls) == 1
    assert len(predictor.calls[0]) == 96

    with TestClient(app):
        pass
    assert len(predictor.calls) == 1


def test_forecast_batch_size_from_settings_controls_precomputation(tmp_path, monkeypatch):
    settings = make_settings(tmp_path)
    config = tmp_path / "settings.json"
    config.write_text(json.dumps({
        "history_csv": str(settings.history_csv),
        "models_dir": str(settings.models_dir),
        "historical_end": settings.historical_end.isoformat(),
        "precompute_days": settings.precompute_days,
        "forecast_batch_size": 10,
    }), encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", settings.database_url)
    predictor = FakePredictor()

    with TestClient(create_app(Settings.from_file(config), predictor_factory=lambda: predictor)):
        pass

    assert [len(call) for call in predictor.calls] == [10, 10, 10, 10, 8]


def test_interval_response_keeps_actuals_and_forecasts_distinct(tmp_path):
    app = create_app(make_settings(tmp_path), predictor_factory=FakePredictor)
    with TestClient(app) as client:
        response = client.get("/api/boardings", params={
            "from": "2025-10-31T23:00", "to": "2025-11-02T00:00",
            "route": 1, "group_by": "day",
        })
        assert response.status_code == 200
        assert response.json()["points"] == [
            {"route": 1, "start": "2025-10-31T23:00:00", "end": "2025-11-01T00:00:00",
             "boardings": 2, "source": "actual", "forecast_version": None,
             "historical_end": None},
            {"route": 1, "start": "2025-11-01T00:00:00", "end": "2025-11-02T00:00:00",
             "boardings": 24, "source": "forecast", "forecast_version": "test-model",
             "historical_end": "2025-10-31"},
        ]


def test_cache_miss_predicts_in_one_batch_and_is_saved(tmp_path):
    predictor = FakePredictor()
    app = create_app(make_settings(tmp_path), predictor_factory=lambda: predictor)
    params = {"from": "2025-11-02T00:00", "to": "2025-11-02T02:00", "route": 1}
    with TestClient(app) as client:
        assert len(predictor.calls) == 1
        first = client.get("/api/boardings", params=params)
        second = client.get("/api/boardings", params=params)
        assert first.status_code == second.status_code == 200
        assert [point["boardings"] for point in first.json()["points"]] == [1, 1]
        assert first.json() == second.json()
    assert len(predictor.calls) == 2
    assert len(predictor.calls[1]) == 2


def test_zero_forecast_is_a_cache_hit(tmp_path):
    predictor = FakePredictor()
    app = create_app(make_settings(tmp_path), predictor_factory=lambda: predictor)
    with TestClient(app) as client:
        params = {"from": "2025-11-02T00:00", "to": "2025-11-02T02:00", "route": 5}
        first = client.get("/api/boardings", params=params)
        second = client.get("/api/boardings", params=params)
        assert [point["boardings"] for point in first.json()["points"]] == [0, 0]
        assert first.json() == second.json()
    assert len(predictor.calls) == 2


def test_invalid_interval_and_route_are_rejected(tmp_path):
    app = create_app(make_settings(tmp_path), predictor_factory=FakePredictor)
    with TestClient(app) as client:
        assert client.get("/api/boardings", params={
            "from": "2025-11-01T02:00", "to": "2025-11-01T01:00",
        }).status_code == 422
        assert client.get("/api/boardings", params={
            "from": "2025-11-01T00:00", "to": "2025-11-01T01:00", "route": 99,
        }).status_code == 422
        assert client.get("/api/boardings", params={
            "from": "2025-10-30T00:00", "to": "2025-10-30T01:00",
        }).status_code == 422
        assert client.get("/api/boardings", params={
            "from": "2025-11-01T00:00+03:00", "to": "2025-11-01T01:00+03:00",
        }).status_code == 422


def test_monthly_aggregation_returns_separate_route_series(tmp_path):
    app = create_app(make_settings(tmp_path), predictor_factory=FakePredictor)
    with TestClient(app) as client:
        response = client.get("/api/boardings", params={
            "from": "2025-11-01T00:00", "to": "2025-11-02T00:00", "group_by": "month",
        })
        assert response.status_code == 200
        assert [(point["route"], point["boardings"]) for point in response.json()["points"]] == [
            (1, 24), (5, 0),
        ]


def test_missing_historical_hour_is_not_treated_as_zero(tmp_path):
    settings = make_settings(tmp_path)
    app = create_app(settings, predictor_factory=FakePredictor)
    with TestClient(app) as client:
        with create_engine(settings.database_url).begin() as connection:
            connection.execute(delete(actual_hourly).where(
                actual_hourly.c.route == 1, actual_hourly.c.hour == 0,
            ))
        response = client.get("/api/boardings", params={
            "from": "2025-10-31T00:00", "to": "2025-10-31T01:00", "route": 1,
        })
        assert response.status_code == 503


def test_missing_precomputed_hour_is_rebuilt(tmp_path):
    settings = make_settings(tmp_path)
    predictor = FakePredictor()
    app = create_app(settings, predictor_factory=lambda: predictor)
    with TestClient(app) as client:
        with create_engine(settings.database_url).begin() as connection:
            connection.execute(delete(forecast_hourly).where(
                forecast_hourly.c.route == 1, forecast_hourly.c.hour == 0,
            ))
        response = client.get("/api/boardings", params={
            "from": "2025-11-01T00:00", "to": "2025-11-01T01:00", "route": 1,
        })
        assert response.status_code == 200
        assert response.json()["points"][0]["boardings"] == 1
        assert len(predictor.calls) == 2


def test_startup_rejects_history_with_wrong_cutoff(tmp_path):
    settings = replace(make_settings(tmp_path), historical_end=date(2025, 10, 30))
    with pytest.raises(ValueError, match="historical_end"):
        with TestClient(create_app(settings, predictor_factory=FakePredictor)):
            pass


def test_startup_rejects_incomplete_prepared_history(tmp_path):
    settings = make_settings(tmp_path)
    rows = settings.history_csv.read_text(encoding="utf-8").splitlines()
    settings.history_csv.write_text("\n".join(rows[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete"):
        with TestClient(create_app(settings, predictor_factory=FakePredictor)):
            pass
