"""Runtime configuration for the local master-server backend."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "game.db"


@dataclass(frozen=True)
class Settings:
    app_name: str = "Witcher LARP Core Engine"
    database_path: Path = DEFAULT_DATABASE_PATH
    sqlite_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "Settings":
        database_path = os.environ.get("WITCHER_LARP_DB")
        if not database_path:
            return cls()

        return cls(database_path=Path(database_path).expanduser().resolve())
