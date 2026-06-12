"""SQLite connection and schema bootstrap for the local game runtime."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Iterator

from .config import Settings
from .event_schema import ensure_event_schema
from .repository import ensure_import_schema
from .runtime_schema import ensure_runtime_schema


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DatabaseHealth:
    status: str
    path: str
    schema_version: int

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "path": self.path,
            "schema_version": self.schema_version,
        }


def _ensure_parent(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def connect(settings: Settings | None = None) -> Iterator[sqlite3.Connection]:
    runtime_settings = settings or Settings.from_env()
    _ensure_parent(runtime_settings.database_path)
    connection = sqlite3.connect(
        runtime_settings.database_path,
        timeout=runtime_settings.sqlite_timeout_seconds,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database(settings: Settings | None = None) -> DatabaseHealth:
    runtime_settings = settings or Settings.from_env()
    with connect(runtime_settings) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            INSERT INTO schema_version (id, version)
            VALUES (1, 1)
            ON CONFLICT(id) DO UPDATE SET version = excluded.version;

            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                source TEXT NOT NULL DEFAULT 'system',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        ensure_import_schema(connection)
        ensure_event_schema(connection)
        ensure_runtime_schema(connection)

    return healthcheck_database(runtime_settings)


def healthcheck_database(settings: Settings | None = None) -> DatabaseHealth:
    runtime_settings = settings or Settings.from_env()
    try:
        with connect(runtime_settings) as connection:
            row = connection.execute(
                "SELECT version FROM schema_version WHERE id = 1"
            ).fetchone()
    except sqlite3.OperationalError:
        row = None

    return DatabaseHealth(
        status="ok" if row else "missing_schema",
        path=str(runtime_settings.database_path),
        schema_version=int(row["version"]) if row else 0,
    )
