from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, Query

from .config import Settings
from .service import BoardingsService


def create_app(settings: Settings, predictor_factory=None) -> FastAPI:
    if predictor_factory is None:
        from .predictor import load_predictor
        predictor_factory = lambda: load_predictor(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service = BoardingsService(settings, predictor_factory())
        service.initialize()
        app.state.service = service
        yield
        service.close()

    app = FastAPI(title="MosTram Boardings API", lifespan=lifespan)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/metadata")
    def get_metadata():
        return app.state.service.get_metadata()

    @app.get("/api/boardings")
    def get_boardings(
        from_: datetime = Query(alias="from"),
        to: datetime = Query(),
        route: int | None = Query(default=None),
        group_by: Literal["hour", "day", "month"] = Query(default="hour"),
    ):
        return app.state.service.get_boardings(from_, to, route, group_by)

    return app
