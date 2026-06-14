"""Обзор мастерской панели для статического мастерского интерфейса."""

from __future__ import annotations

import sqlite3
from typing import Any

from .repository import latest_snapshot_version, quote_identifier


def build_admin_overview(connection: sqlite3.Connection) -> dict[str, Any]:
    snapshot_version = latest_snapshot_version(connection)
    return {
        "stage": "ЭТАП 2: Мастерская панель",
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
        "label": "Настройка",
        "status": "ready" if snapshot_version else "not_imported",
        "metrics": [
            _metric("Снапшот", snapshot_version or "не импортирован"),
            _metric("Игроки", _count_table(connection, "players")),
            _metric("QR-объекты", _count_table(connection, "qr_objects")),
            _metric("Награды", _count_table(connection, "rewards")),
        ],
        "actions": [
            _action(
                "import_validation",
                "Импорт и валидация",
                "POST",
                "/api/master/content/import",
                "ready",
            ),
            _action(
                "snapshot_export",
                "Экспорт снапшота",
                "POST",
                "/api/master/content/snapshot/export",
                "ready" if snapshot_version else "not_imported",
            ),
            _action(
                "qr_checklist",
                "Чеклист QR/ручных кодов",
                "GET",
                "/api/master/content/qr-checklist",
                "ready" if snapshot_version else "not_imported",
            ),
            _action(
                "handout_checklist",
                "Чеклист памяток игрокам",
                "GET",
                "/api/master/content/handout-checklist",
                "ready" if snapshot_version else "not_imported",
            ),
            _action(
                "player_snapshot",
                "Игроковый снапшот",
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
        "label": "Пульт мастера",
        "status": "ready",
        "metrics": [
            _metric("Текущий акт", act_state.get("current_act_id") or "не начат"),
            _metric("Статус акта", act_state.get("status") or "не начат"),
            _metric("События", _count_table(connection, "event_log")),
            _metric("Клиенты синхронизации", _count_table(connection, "client_sync_state")),
            _metric("Таймеры", _count_table(connection, "auto_timers")),
            _metric("Битвы лордов", _count_table(connection, "lord_battles")),
        ],
        "actions": [
            _action("master_state", "Состояние игры", "GET", "/api/master/state", "ready"),
            _action("event_log", "Последние события", "GET", "/api/master/state", "ready"),
            _action("sync_status", "Статус синхронизации", "GET", "/api/master/state", "ready"),
            _action(
                "anti_snowball",
                "Антисноуболл",
                "GET",
                "/api/master/state",
                "ready",
            ),
            _action(
                "visibility_audit",
                "Аудит видимости",
                "GET",
                "/api/master/visibility-audit",
                "ready",
            ),
            _action("acts_state", "Состояние актов", "GET", "/api/master/acts/state", "ready"),
            _action("timers", "Таймеры", "GET", "/api/master/timers", "ready"),
            _action(
                "manual_lord_tick",
                "Ручной тик лордов",
                "POST",
                "/api/master/timers/lord-income-tick",
                "ready",
            ),
            _action("pvp_throttle", "Ограничение PvP", "POST", "/api/master/pvp-throttle", "ready"),
            _action(
                "game_ops_correction",
                "Коррекция состояния",
                "POST",
                "/api/master/game-ops/corrections",
                "ready",
            ),
            _action(
                "admin_setup_grant",
                "Предыгровая выдача ресурсов",
                "POST",
                "/api/master/admin-setup/grants",
                "ready",
            ),
            _action(
                "registration_hard_reset",
                "Хард-резет в регистрацию",
                "POST",
                "/api/master/game/start-setup",
                "ready",
            ),
            _action(
                "potion_trade_corrections",
                "Коррекции зелий/обмена",
                "POST",
                "/api/master/game-ops/corrections",
                "ready",
            ),
            _action("lord_battles", "Битвы лордов", "GET", "/api/lord-battles", "ready"),
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
        "label": "Ревью",
        "status": status,
        "metrics": [
            _metric("Открытые проверки", open_review_count),
            _metric("Награды на подтверждении", reward_pending_count),
            _metric("Синхронизированные события", _count_table(connection, "events")),
            _metric("Коррекции", _count_table(connection, "master_corrections")),
        ],
        "actions": [
            _action("review_queue", "Очередь проверки", "GET", "/api/master/review-queue", "ready"),
            _action("event_review", "Решение проверки", "POST", "/api/events/{event_id}/review", "ready"),
            _action("corrections", "Коррекции", "POST", "/api/master/corrections", "ready"),
            _action(
                "paper_recovery",
                "Ввод бумажного восстановления",
                "POST",
                "/api/events/sync",
                "ready",
            ),
            _action(
                "reward_approval",
                "Подтверждение награды",
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
            _metric("Сценарные NPC-события", _count_table(connection, "npc_events")),
            _metric("Игровые NPC-события", _count_table(connection, "npc_runtime_events")),
            _metric("Сделки", _count_table(connection, "npc_deals")),
        ],
        "actions": [
            _action("npc_events", "NPC-события", "GET", "/api/master/npc/events", "ready"),
            _action("npc_record", "Записать NPC-событие", "POST", "/api/master/npc/events", "ready"),
            _action("npc_deals", "NPC-сделки", "GET", "/api/master/npc/deals", "ready"),
        ],
    }


def _backups_section(connection: sqlite3.Connection) -> dict[str, Any]:
    failed_count = _count_where(connection, "backup_runs", "status = ?", ("failed",))
    return {
        "id": "backups",
        "label": "Бэкапы",
        "status": "needs_attention" if failed_count else "ready",
        "metrics": [
            _metric("Настроенные задачи", _count_table(connection, "backup_jobs")),
            _metric("Запуски бэкапа", _count_table(connection, "backup_runs")),
            _metric("Ошибки", failed_count),
        ],
        "actions": [
            _action("backup_status", "Статус бэкапов", "GET", "/api/master/backups/status", "ready"),
            _action("run_backup", "Запустить бэкап", "POST", "/api/backups/run", "ready"),
            _action("restore_backup", "Восстановить бэкап", None, None, "pending_backend"),
        ],
    }


def _final_section(connection: sqlite3.Connection) -> dict[str, Any]:
    lock = _final_lock_state(connection)
    return {
        "id": "final",
        "label": "Финал",
        "status": "ready",
        "metrics": [
            _metric("Финал закрыт", "да" if lock.get("locked_at") else "нет"),
            _metric("Поля доказательств", _count_table(connection, "final_summary_fields")),
            _metric("Финальные заметки", _count_table(connection, "final_master_notes")),
            _metric("Финальные процедуры", _count_table(connection, "final_procedures")),
        ],
        "actions": [
            _action("final_summary", "Финальная сводка", "GET", "/api/master/final-summary", "ready"),
            _action(
                "final_note",
                "Финальная заметка",
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
