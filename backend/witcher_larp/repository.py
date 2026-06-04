"""SQLite persistence for imported runtime CSV content."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime

from .content_schema import TABLE_ID_COLUMNS
from .csv_loader import CsvTable, SeedPack
from .import_models import ImportErrorDetail, ImportReport


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def ensure_import_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS import_runs (
            run_id TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            files_json TEXT NOT NULL DEFAULT '[]',
            error_count INTEGER NOT NULL DEFAULT 0,
            snapshot_version TEXT
        );

        CREATE TABLE IF NOT EXISTS import_errors (
            error_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            code TEXT NOT NULL,
            file TEXT NOT NULL,
            row_number INTEGER,
            record_id TEXT,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES import_runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS snapshot_versions (
            snapshot_version TEXT PRIMARY KEY,
            import_run_id TEXT NOT NULL,
            profile_id TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (import_run_id) REFERENCES import_runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS client_sync_state (
            client_id TEXT PRIMARY KEY,
            player_id TEXT,
            snapshot_version TEXT,
            last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_event_sequence INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS reward_approvals (
            approval_id TEXT PRIMARY KEY,
            reward_id TEXT NOT NULL,
            player_id TEXT,
            status TEXT NOT NULL,
            source_event_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            decided_at TEXT
        );

        CREATE TABLE IF NOT EXISTS raid_effects (
            raid_effect_id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL,
            source_domain_id TEXT,
            target_domain_id TEXT,
            target_territory_id TEXT,
            status TEXT NOT NULL,
            starts_at_offset_min INTEGER,
            ends_at_offset_min INTEGER,
            started_at TEXT,
            expires_at TEXT,
            expired_at TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}'
        );
        """
    )


def ensure_content_schema(connection: sqlite3.Connection, tables: dict[str, CsvTable]) -> None:
    for table in tables.values():
        columns = [
            '"_import_run_id" TEXT NOT NULL',
            '"_row_number" INTEGER NOT NULL',
        ]
        for header in table.headers:
            columns.append(f"{quote_identifier(header)} TEXT NOT NULL DEFAULT ''")
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {quote_identifier(table.name)} "
            f"({', '.join(columns)})"
        )


def replace_content(
    connection: sqlite3.Connection,
    pack: SeedPack,
    run_id: str,
    snapshot_version: str,
    content_hash: str,
    snapshot_payload: dict[str, object],
) -> ImportReport:
    now = _utc_now()
    ensure_import_schema(connection)
    ensure_content_schema(connection, pack.tables)

    for table in pack.tables.values():
        connection.execute(f"DELETE FROM {quote_identifier(table.name)}")

    connection.execute(
        """
        INSERT INTO import_runs (
            run_id, source_path, status, started_at, finished_at,
            files_json, error_count, snapshot_version
        )
        VALUES (?, ?, 'success', ?, ?, ?, 0, ?)
        """,
        (
            run_id,
            str(pack.source_path),
            now,
            now,
            json.dumps(pack.files, ensure_ascii=False),
            snapshot_version,
        ),
    )

    for table in pack.tables.values():
        _insert_table_rows(connection, table, run_id)

    profile_id = _profile_id(pack)
    connection.execute(
        """
        INSERT INTO snapshot_versions (
            snapshot_version, import_run_id, profile_id, content_hash,
            snapshot_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_version) DO UPDATE SET
            import_run_id = excluded.import_run_id,
            profile_id = excluded.profile_id,
            content_hash = excluded.content_hash,
            snapshot_json = excluded.snapshot_json,
            created_at = excluded.created_at
        """,
        (
            snapshot_version,
            run_id,
            profile_id,
            content_hash,
            json.dumps(snapshot_payload, ensure_ascii=False, sort_keys=True),
            now,
        ),
    )

    return ImportReport(
        run_id=run_id,
        status="success",
        files=pack.files,
        errors=[],
        snapshot_version=snapshot_version,
    )


def record_failed_import(
    connection: sqlite3.Connection,
    pack: SeedPack,
    run_id: str,
    errors: list[ImportErrorDetail],
) -> ImportReport:
    now = _utc_now()
    ensure_import_schema(connection)
    connection.execute(
        """
        INSERT INTO import_runs (
            run_id, source_path, status, started_at, finished_at,
            files_json, error_count, snapshot_version
        )
        VALUES (?, ?, 'failed', ?, ?, ?, ?, NULL)
        """,
        (
            run_id,
            str(pack.source_path),
            now,
            now,
            json.dumps(pack.files, ensure_ascii=False),
            len(errors),
        ),
    )
    for error in errors:
        connection.execute(
            """
            INSERT INTO import_errors (
                run_id, code, file, row_number, record_id, message
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                error.code,
                error.file,
                error.row,
                error.record_id,
                error.message,
            ),
        )
    return ImportReport(run_id=run_id, status="failed", files=pack.files, errors=errors)


def fetch_table(connection: sqlite3.Connection, table_name: str) -> list[dict[str, str]]:
    rows = connection.execute(
        f"SELECT * FROM {quote_identifier(table_name)} ORDER BY _row_number"
    ).fetchall()
    result: list[dict[str, str]] = []
    for row in rows:
        result.append(
            {
                key: row[key]
                for key in row.keys()
                if key not in {"_import_run_id", "_row_number"}
            }
        )
    return result


def fetch_latest_snapshot(connection: sqlite3.Connection) -> dict[str, object] | None:
    ensure_import_schema(connection)
    row = connection.execute(
        """
        SELECT snapshot_json
        FROM snapshot_versions
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["snapshot_json"])


def latest_snapshot_version(connection: sqlite3.Connection) -> str | None:
    ensure_import_schema(connection)
    row = connection.execute(
        """
        SELECT snapshot_version
        FROM snapshot_versions
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    return str(row["snapshot_version"])


def quote_identifier(identifier: str) -> str:
    if not IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"Unsafe SQLite identifier: {identifier}")
    return f'"{identifier}"'


def _insert_table_rows(
    connection: sqlite3.Connection, table: CsvTable, run_id: str
) -> None:
    columns = ["_import_run_id", "_row_number", *table.headers]
    placeholders = ", ".join("?" for _ in columns)
    sql = (
        f"INSERT INTO {quote_identifier(table.name)} "
        f"({', '.join(quote_identifier(column) for column in columns)}) "
        f"VALUES ({placeholders})"
    )
    for record in table.rows:
        values = [run_id, record.row_number, *[record.values[header] for header in table.headers]]
        connection.execute(sql, values)


def _profile_id(pack: SeedPack) -> str:
    profiles = pack.tables["profiles.csv"]
    return profiles.rows[0].values[TABLE_ID_COLUMNS["profiles.csv"]]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
