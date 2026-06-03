"""Backup hooks for act transitions and manual master actions."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .config import Settings
from .runtime_schema import ensure_runtime_schema, log_event


@dataclass(frozen=True)
class BackupResult:
    backup_id: str
    job_id: str
    trigger_type: str
    status: str
    needs_master_review: bool
    artifact_path: str | None
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "backup_id": self.backup_id,
            "job_id": self.job_id,
            "trigger_type": self.trigger_type,
            "status": self.status,
            "needs_master_review": self.needs_master_review,
            "artifact_path": self.artifact_path,
            "error": self.error,
        }


def run_backup(
    connection: sqlite3.Connection,
    settings: Settings,
    *,
    trigger_type: str = "manual",
    operator: str = "system",
    source: str = "backup_service",
    affects_transition: bool = False,
    now: datetime | None = None,
) -> BackupResult:
    ensure_runtime_schema(connection)
    started_at = _iso(now)
    backup_id = f"backup_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"
    job = _find_backup_job(connection, trigger_type)
    if job is None:
        result = BackupResult(
            backup_id=backup_id,
            job_id=f"missing_{trigger_type}",
            trigger_type=trigger_type,
            status="failed",
            needs_master_review=affects_transition,
            artifact_path=None,
            error=f"No backup job configured for trigger_type={trigger_type}",
        )
        _record_backup_result(connection, result, started_at, operator, source, True, True)
        return result

    include_sqlite = _to_bool(job["include_sqlite"])
    include_event_log = _to_bool(job["include_event_log"])
    try:
        manifest_path = _write_backup_artifact(
            connection,
            settings,
            backup_id=backup_id,
            job_id=str(job["job_id"]),
            trigger_type=trigger_type,
            include_sqlite=include_sqlite,
            include_event_log=include_event_log,
            started_at=started_at,
            operator=operator,
            source=source,
        )
    except Exception as exc:  # pragma: no cover - exercised through failure handling paths.
        result = BackupResult(
            backup_id=backup_id,
            job_id=str(job["job_id"]),
            trigger_type=trigger_type,
            status="failed",
            needs_master_review=affects_transition,
            artifact_path=None,
            error=str(exc),
        )
        _record_backup_result(
            connection,
            result,
            started_at,
            operator,
            source,
            include_sqlite,
            include_event_log,
        )
        return result

    result = BackupResult(
        backup_id=backup_id,
        job_id=str(job["job_id"]),
        trigger_type=trigger_type,
        status="success",
        needs_master_review=False,
        artifact_path=str(manifest_path),
    )
    _record_backup_result(
        connection,
        result,
        started_at,
        operator,
        source,
        include_sqlite,
        include_event_log,
    )
    return result


def _find_backup_job(
    connection: sqlite3.Connection, trigger_type: str
) -> sqlite3.Row | None:
    if not _table_exists(connection, "backup_jobs"):
        return None
    row = connection.execute(
        """
        SELECT job_id, trigger_type, include_sqlite, include_event_log
        FROM backup_jobs
        WHERE trigger_type = ?
        ORDER BY _row_number
        LIMIT 1
        """,
        (trigger_type,),
    ).fetchone()
    if row is not None:
        return row
    if trigger_type == "manual":
        return None
    return connection.execute(
        """
        SELECT job_id, trigger_type, include_sqlite, include_event_log
        FROM backup_jobs
        WHERE trigger_type = 'manual'
        ORDER BY _row_number
        LIMIT 1
        """
    ).fetchone()


def _write_backup_artifact(
    connection: sqlite3.Connection,
    settings: Settings,
    *,
    backup_id: str,
    job_id: str,
    trigger_type: str,
    include_sqlite: bool,
    include_event_log: bool,
    started_at: str,
    operator: str,
    source: str,
) -> Path:
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path: Path | None = None
    if include_sqlite:
        sqlite_path = settings.backup_dir / f"{backup_id}.sqlite"
        _copy_sqlite_database(settings.database_path, sqlite_path)

    event_log: list[dict[str, object]] = []
    if include_event_log:
        event_log = [
            {
                "id": int(row["id"]),
                "event_type": row["event_type"],
                "payload_json": row["payload_json"],
                "source": row["source"],
                "created_at": row["created_at"],
            }
            for row in connection.execute(
                """
                SELECT id, event_type, payload_json, source, created_at
                FROM event_log
                ORDER BY id
                """
            ).fetchall()
        ]

    manifest = {
        "backup_id": backup_id,
        "job_id": job_id,
        "trigger_type": trigger_type,
        "started_at": started_at,
        "operator": operator,
        "source": source,
        "sqlite_path": str(sqlite_path) if sqlite_path is not None else None,
        "event_log": event_log,
    }
    manifest_path = settings.backup_dir / f"{backup_id}.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest_path


def _copy_sqlite_database(source_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path) as source, sqlite3.connect(target_path) as target:
        source.backup(target)


def _record_backup_result(
    connection: sqlite3.Connection,
    result: BackupResult,
    started_at: str,
    operator: str,
    source: str,
    include_sqlite: bool,
    include_event_log: bool,
) -> None:
    finished_at = _iso()
    connection.execute(
        """
        INSERT INTO backup_runs (
            backup_id, job_id, trigger_type, status, needs_master_review,
            artifact_path, include_sqlite, include_event_log, started_at,
            finished_at, operator, source, error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result.backup_id,
            result.job_id,
            result.trigger_type,
            result.status,
            1 if result.needs_master_review else 0,
            result.artifact_path,
            1 if include_sqlite else 0,
            1 if include_event_log else 0,
            started_at,
            finished_at,
            operator,
            source,
            result.error,
        ),
    )
    log_event(
        connection,
        "backup_run",
        {
            **result.as_dict(),
            "operator": operator,
            "started_at": started_at,
            "finished_at": finished_at,
        },
        source=source,
    )


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _to_bool(value: object) -> bool:
    return str(value).strip().lower() == "true"


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")
