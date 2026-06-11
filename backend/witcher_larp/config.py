"""Runtime configuration for the local master-server backend."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "game.db"
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "data" / "backups"
DEFAULT_CORS_ALLOW_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
    "http://127.0.0.1:5177",
    "http://127.0.0.1:5178",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://localhost:5177",
    "http://localhost:5178",
)


@dataclass(frozen=True)
class Settings:
    app_name: str = "Witcher LARP Core Engine"
    database_path: Path = DEFAULT_DATABASE_PATH
    backup_dir: Path = DEFAULT_BACKUP_DIR
    sqlite_timeout_seconds: float = 5.0
    cors_allow_origins: tuple[str, ...] = DEFAULT_CORS_ALLOW_ORIGINS

    @classmethod
    def from_env(cls) -> "Settings":
        database_path = os.environ.get("WITCHER_LARP_DB")
        cors_origins = tuple(
            origin.strip()
            for origin in os.environ.get("WITCHER_LARP_CORS_ORIGINS", "").split(",")
            if origin.strip()
        )
        settings_kwargs = {}
        if cors_origins:
            settings_kwargs["cors_allow_origins"] = cors_origins

        if database_path:
            settings_kwargs["database_path"] = Path(database_path).expanduser().resolve()

        return cls(**settings_kwargs)
