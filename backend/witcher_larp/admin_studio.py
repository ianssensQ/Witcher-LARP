"""Read-only Admin Studio overview for the static master shell."""

from __future__ import annotations

import sqlite3
from typing import Any

from .repository import latest_snapshot_version, quote_identifier


def build_admin_overview(connection: sqlite3.Connection) -> dict[str, Any]:
    snapshot_version = latest_snapshot_version(connection)
    return {
        "stage": "STAGE-2: Admin Studio",
        "snapshot_version": snapshot_version,
        "navigation": [
            {"id": item["id"], "label": item["label"], "status": item["status"]}
            for item in _sections(connection, snapshot_version)
        ],
        "sections": _sections(connection, snapshot_version),
        "visibility": {
            "scope": "master",
            "role_token_required": True,
            "master_only": True,
            "redacted_tables": ["role_tokens", "player_codes"],
        },
    }


def _sections(
    connection: sqlite3.Connection, snapshot_version: str | None
) -> list[dict[str, Any]]:
    return [
        _content_section(connection, snapshot_version),
        _game_ops_section(connection),
        _events_section(connection),
        _npc_section(connection),
        _backups_section(connection),
        _final_section(connection),
    ]


def _content_section(
    connection: sqlite3.Connection, snapshot_version: str | None
) -> dict[str, Any]:
    return {
        "id": "content",
        "label": "Content",
        "status": "ready" if snapshot_version else "not_imported",
        "metrics": [
            _metric("Snapshot", snapshot_version or "not imported"),
            _metric("Players", _count_table(connection, "players")),
            _metric("QR objects", _count_table(connection, "qr_objects")),
            _metric("Rewards", _count_table(connection, "rewards")),
        ],
        "actions": [
            _action(
                "import_validation",
                "Import and validation",
                "POST",
                "/api/master/content/import",
                "ready",
            ),
            _action(
                "snapshot_export",
                "Snapshot export",
                "POST",
                "/api/master/content/snapshot/export",
                "ready" if snapshot_version else "not_imported",
            ),
            _action(
                "qr_checklist",
                "QR/manual checklist",
                "GET",
                "/api/master/content/qr-checklist",
                "ready" if snapshot_version else "not_imported",
            ),
            _action(
                "handout_checklist",
                "Player handout checklist",
                "GET",
                "/api/master/content/handout-checklist",
                "ready" if snapshot_version else "not_imported",
            ),
            _action(
                "player_snapshot",
                "Player-scoped snapshot",
                "GET",
                "/api/content/snapshot",
                "player_code_required",
            ),
        ],
    }


def _game_ops_section(connection: sqlite3.Connection) -> dict[str, Any]:
    act_state = _act_state(connection)
    return {
        "id": "game-ops",
        "label": "Game Ops",
        "status": "ready",
        "metrics": [
            _metric("Current act", act_state.get("current_act_id") or "not started"),
            _metric("Act status", act_state.get("status") or "not started"),
            _metric("Recent events", _count_table(connection, "event_log")),
            _metric("Sync clients", _count_table(connection, "client_sync_state")),
            _metric("Timers", _count_table(connection, "auto_timers")),
            _metric("Lord battles", _count_table(connection, "lord_battles")),
        ],
        "actions": [
            _action("master_state", "Game ops state", "GET", "/api/master/state", "ready"),
            _action("event_log", "Recent event log", "GET", "/api/master/state", "ready"),
            _action("sync_status", "Sync status", "GET", "/api/master/state", "ready"),
            _action(
                "anti_snowball",
                "Anti-snowball state",
                "GET",
                "/api/master/state",
                "ready",
            ),
            _action(
                "visibility_audit",
                "Visibility audit",
                "GET",
                "/api/master/visibility-audit",
                "ready",
            ),
            _action("acts_state", "Acts state", "GET", "/api/master/acts/state", "ready"),
            _action("timers", "Timers", "GET", "/api/master/timers", "ready"),
            _action("pvp_throttle", "PvP throttle", "POST", "/api/master/pvp-throttle", "ready"),
            _action(
                "game_ops_correction",
                "Game ops correction",
                "POST",
                "/api/master/game-ops/corrections",
                "ready",
            ),
            _action(
                "potion_trade_corrections",
                "Potion/trade corrections",
                "POST",
                "/api/master/game-ops/corrections",
                "ready",
            ),
            _action("lord_battles", "Lord battles", "GET", "/api/lord-battles", "ready"),
        ],
    }


def _events_section(connection: sqlite3.Connection) -> dict[str, Any]:
    open_review_count = _count_where(
        connection,
        "event_reviews",
        "status NOT IN ('approved', 'rejected', 'corrected')",
    )
    reward_pending_count = _count_where(
        connection,
        "reward_approvals",
        "status = ?",
        ("pending_master_approval",),
    )
    status = "needs_attention" if open_review_count or reward_pending_count else "ready"
    return {
        "id": "events",
        "label": "Events",
        "status": status,
        "metrics": [
            _metric("Open reviews", open_review_count),
            _metric("Pending rewards", reward_pending_count),
            _metric("Synced events", _count_table(connection, "events")),
            _metric("Corrections", _count_table(connection, "master_corrections")),
        ],
        "actions": [
            _action("review_queue", "Review queue", "GET", "/api/master/review-queue", "ready"),
            _action("event_review", "Review decision", "POST", "/api/events/{event_id}/review", "ready"),
            _action("corrections", "Corrections", "POST", "/api/master/corrections", "ready"),
            _action("paper_recovery", "Paper recovery intake", "POST", "/api/events/sync", "ready"),
            _action(
                "reward_approval",
                "Reward approval",
                "POST",
                "/api/master/reward-approvals/{approval_id}",
                "ready",
            ),
        ],
    }


def _npc_section(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        "id": "npc",
        "label": "NPC",
        "status": "ready",
        "metrics": [
            _metric("Seed NPC events", _count_table(connection, "npc_events")),
            _metric("Runtime NPC events", _count_table(connection, "npc_runtime_events")),
            _metric("Captured deals", _count_table(connection, "npc_deals")),
        ],
        "actions": [
            _action("npc_events", "NPC events", "GET", "/api/master/npc/events", "ready"),
            _action("npc_record", "Record NPC event", "POST", "/api/master/npc/events", "ready"),
            _action("npc_deals", "NPC deals", "GET", "/api/master/npc/deals", "ready"),
        ],
    }


def _backups_section(connection: sqlite3.Connection) -> dict[str, Any]:
    failed_count = _count_where(connection, "backup_runs", "status = ?", ("failed",))
    return {
        "id": "backups",
        "label": "Backups",
        "status": "needs_attention" if failed_count else "ready",
        "metrics": [
            _metric("Configured jobs", _count_table(connection, "backup_jobs")),
            _metric("Backup runs", _count_table(connection, "backup_runs")),
            _metric("Failed runs", failed_count),
        ],
        "actions": [
            _action("backup_status", "Backup status", "GET", "/api/master/backups/status", "ready"),
            _action("run_backup", "Run backup", "POST", "/api/backups/run", "ready"),
            _action("restore_backup", "Restore backup", None, None, "pending_backend"),
        ],
    }


def _final_section(connection: sqlite3.Connection) -> dict[str, Any]:
    lock = _final_lock_state(connection)
    return {
        "id": "final",
        "label": "Final",
        "status": "ready",
        "metrics": [
            _metric("Final locked", "yes" if lock.get("locked_at") else "no"),
            _metric("Evidence fields", _count_table(connection, "final_summary_fields")),
            _metric("Final notes", _count_table(connection, "final_master_notes")),
            _metric("Final procedures", _count_table(connection, "final_procedures")),
        ],
        "actions": [
            _action("final_summary", "Final summary", "GET", "/api/master/final-summary", "ready"),
            _action(
                "final_note",
                "Final note",
                "POST",
                "/api/master/final-summary/notes",
                "ready",
            ),
        ],
    }


def _metric(label: str, value: object) -> dict[str, object]:
    return {"label": label, "value": value}


def _action(
    action_id: str,
    label: str,
    method: str | None,
    endpoint: str | None,
    status: str,
) -> dict[str, str | None]:
    return {
        "id": action_id,
        "label": label,
        "method": method,
        "endpoint": endpoint,
        "status": status,
    }


def _act_state(connection: sqlite3.Connection) -> dict[str, object]:
    row = _fetch_one(
        connection,
        "act_state",
        """
        SELECT current_act_id, status, active_started_at, final_locked_at, updated_at
        FROM act_state
        WHERE id = 1
        """,
    )
    return _clean_row(row)


def _final_lock_state(connection: sqlite3.Connection) -> dict[str, object]:
    row = _fetch_one(
        connection,
        "final_lock_state",
        "SELECT locked_at, operator, source FROM final_lock_state WHERE id = 1",
    )
    return _clean_row(row)


def _count_table(connection: sqlite3.Connection, table_name: str) -> int:
    return _count_where(connection, table_name, "1 = 1")


def _count_where(
    connection: sqlite3.Connection,
    table_name: str,
    where_sql: str,
    params: tuple[object, ...] = (),
) -> int:
    if not _table_exists(connection, table_name):
        return 0
    row = connection.execute(
        f"SELECT COUNT(*) FROM {quote_identifier(table_name)} WHERE {where_sql}",
        params,
    ).fetchone()
    return int(row[0]) if row is not None else 0


def _fetch_one(
    connection: sqlite3.Connection,
    table_name: str,
    sql: str,
    params: tuple[object, ...] = (),
) -> sqlite3.Row | None:
    if not _table_exists(connection, table_name):
        return None
    return connection.execute(sql, params).fetchone()


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


def _clean_row(row: sqlite3.Row | None) -> dict[str, object]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}
