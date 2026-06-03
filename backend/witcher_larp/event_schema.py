"""SQLite schema for event intake and master review queues."""

from __future__ import annotations

import sqlite3


def ensure_event_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS events (
            server_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            device_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            client_sequence INTEGER NOT NULL,
            client_created_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT,
            payload_json TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            source TEXT NOT NULL DEFAULT 'client',
            received_at TEXT NOT NULL,
            applied_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_events_status
        ON events(status);

        CREATE INDEX IF NOT EXISTS idx_events_actor
        ON events(actor_id, actor_type);

        CREATE TABLE IF NOT EXISTS event_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            server_event_id INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'P2',
            decision TEXT,
            decision_reason TEXT,
            decided_by TEXT,
            decided_at TEXT,
            correction_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (server_event_id) REFERENCES events(server_event_id)
        );

        CREATE TABLE IF NOT EXISTS master_corrections (
            correction_id TEXT PRIMARY KEY,
            review_id INTEGER NOT NULL,
            server_event_id INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            action TEXT NOT NULL,
            operator TEXT NOT NULL,
            reason TEXT NOT NULL,
            severity TEXT NOT NULL,
            status_before TEXT NOT NULL,
            status_after TEXT NOT NULL,
            correction_json TEXT NOT NULL DEFAULT '{}',
            source TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (review_id) REFERENCES event_reviews(review_id),
            FOREIGN KEY (server_event_id) REFERENCES events(server_event_id)
        );
        """
    )
    _ensure_columns(
        connection,
        "event_reviews",
        {
            "decision": "TEXT",
            "decision_reason": "TEXT",
            "decided_by": "TEXT",
            "decided_at": "TEXT",
            "correction_id": "TEXT",
        },
    )


def _ensure_columns(
    connection: sqlite3.Connection,
    table_name: str,
    columns: dict[str, str],
) -> None:
    existing = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, definition in columns.items():
        if column_name not in existing:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
            )
