"""FastAPI application factory for the local game master server."""

from __future__ import annotations

from .config import Settings
from .database import healthcheck_database, init_database

try:
    from fastapi import FastAPI
except ModuleNotFoundError:  # pragma: no cover - exercised in dependency smoke tests.
    FastAPI = None  # type: ignore[assignment]


def create_app(settings: Settings | None = None):
    if FastAPI is None:
        raise RuntimeError(
            "FastAPI is not installed. Install backend dependencies with "
            "`uv sync` and run backend commands through `uv run python`."
        )

    runtime_settings = settings or Settings.from_env()
    init_database(runtime_settings)
    api = FastAPI(title=runtime_settings.app_name)

    @api.get("/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": runtime_settings.app_name,
            "database": healthcheck_database(runtime_settings).as_dict(),
        }

    return api


app = create_app() if FastAPI is not None else None
