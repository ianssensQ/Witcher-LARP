"""Act lifecycle service and offline unlock-code gating."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from .backup_service import run_backup
from .config import Settings
from .runtime_schema import ensure_runtime_schema, log_event
from .timer_service import apply_due_timers, ensure_final_lock, ensure_runtime_content_state
from .timer_service import timer_status


ANNOUNCED_STATES = {"announced", "completed", "done", "physical_announced"}
REGISTRATION_ACT_ID = "registration"
CLEAN_REGISTRATION_FLAG = "clean_registration_start"
DEFAULT_ACTIVE_ARMY_STACK_CAPACITY = 5


class ActServiceError(RuntimeError):
    """Base exception for act service failures."""


class ActNotFoundError(ActServiceError):
    """Raised when imported content does not define the requested act."""


class UnlockCodeHiddenError(ActServiceError):
    """Raised when unlock-code reveal is still gated."""


def start_act(
    connection: sqlite3.Connection,
    settings: Settings,
    act_id: str,
    *,
    operator: str,
    source: str = "master_api",
    physical_announcement_state: str = "announced",
    now: datetime | None = None,
) -> dict[str, object]:
    ensure_runtime_schema(connection)
    ensure_runtime_content_state(connection)
    act_row = _fetch_act(connection, act_id)
    if act_row is None:
        raise ActNotFoundError(f"Unknown act_id: {act_id}")

    current_time = now or datetime.now(UTC)
    registration_reset = act_id == REGISTRATION_ACT_ID
    applied_before = [] if registration_reset else apply_due_timers(
        connection, settings, now=current_time
    )
    current_state = _current_state(connection)
    backup = None
    final_lock_effect = None
    registration_reset_effect = None
    if registration_reset:
        backup = run_backup(
            connection,
            settings,
            trigger_type="registration_reset",
            operator=operator,
            source=source,
            affects_transition=True,
            now=current_time,
        )
        registration_reset_effect = _reset_game_for_registration(
            connection,
            operator=operator,
            source=source,
            now=current_time,
        )
        current_state = _current_state(connection)
    if str(act_row["act_type"]) == "final":
        final_lock_effect = ensure_final_lock(
            connection,
            applied_at=current_time,
            operator=operator,
            source="direct_final_act_start" if source == "master_api" else source,
        )
    if current_state["current_act_id"] and current_state["current_act_id"] != act_id:
        backup = run_backup(
            connection,
            settings,
            trigger_type="pre_act_transition",
            operator=operator,
            source=source,
            affects_transition=True,
            now=current_time,
        )
        _complete_previous_act(connection, str(current_state["current_act_id"]), current_time)

    existing = connection.execute(
        """
        SELECT act_id
        FROM act_history
        WHERE act_id = ?
        """,
        (act_id,),
    ).fetchone()
    is_new_start = existing is None
    if is_new_start:
        connection.execute(
            """
            INSERT INTO act_history (
                act_id, status, started_at, operator, source,
                physical_announcement_state, physical_announcement_at,
                server_timestamp
            )
            VALUES (?, 'active', ?, ?, ?, ?, ?, ?)
            """,
            (
                act_id,
                _iso(current_time),
                operator,
                source,
                physical_announcement_state,
                _iso(current_time) if _is_announced(physical_announcement_state) else None,
                _iso(current_time),
            ),
        )
    else:
        connection.execute(
            """
            UPDATE act_history
            SET status = 'active',
                operator = ?,
                source = ?,
                physical_announcement_state = ?,
                physical_announcement_at = CASE
                    WHEN ? THEN COALESCE(physical_announcement_at, ?)
                    ELSE physical_announcement_at
                END,
                server_timestamp = ?
            WHERE act_id = ?
            """,
            (
                operator,
                source,
                physical_announcement_state,
                1 if _is_announced(physical_announcement_state) else 0,
                _iso(current_time),
                _iso(current_time),
                act_id,
            ),
        )

    connection.execute(
        """
        UPDATE act_state
        SET current_act_id = ?,
            status = 'active',
            active_started_at = (
                SELECT started_at FROM act_history WHERE act_id = ?
            ),
            updated_at = ?
        WHERE id = 1
        """,
        (act_id, act_id, _iso(current_time)),
    )

    start_effects: dict[str, object] = {}
    if registration_reset_effect is not None:
        start_effects["registration_reset"] = registration_reset_effect
    if is_new_start and not registration_reset:
        start_effects["challenge_tokens"] = _grant_challenge_tokens(
            connection,
            act_id,
            operator=operator,
            source=source,
            now=current_time,
        )
        start_effects["army_windows"] = _open_army_windows(
            connection,
            act_row,
            operator=operator,
            source=source,
            now=current_time,
        )
    if final_lock_effect is not None:
        start_effects["final_lock"] = final_lock_effect

    log_event(
        connection,
        "act_started",
        {
            "act_id": act_id,
            "operator": operator,
            "source": source,
            "physical_announcement_state": physical_announcement_state,
            "physical_announcement_at": _iso(current_time)
            if _is_announced(physical_announcement_state)
            else None,
            "is_new_start": is_new_start,
        },
        source=source,
        created_at=current_time,
    )
    applied_after = [] if registration_reset else apply_due_timers(
        connection, settings, now=current_time
    )
    return {
        "act": _act_payload(act_row),
        "state": _current_state(connection),
        "backup": backup.as_dict() if backup is not None else None,
        "start_effects": start_effects,
        "applied_timers": [*applied_before, *applied_after],
        "unlock_code": _unlock_code_state(connection, act_id),
    }


def record_physical_announcement(
    connection: sqlite3.Connection,
    act_id: str,
    *,
    operator: str,
    source: str = "master_api",
    state: str = "announced",
    now: datetime | None = None,
) -> dict[str, object]:
    ensure_runtime_schema(connection)
    current_time = now or datetime.now(UTC)
    history = connection.execute(
        """
        SELECT act_id
        FROM act_history
        WHERE act_id = ?
        """,
        (act_id,),
    ).fetchone()
    if history is None:
        raise UnlockCodeHiddenError("Act must be started before physical announcement.")
    connection.execute(
        """
        UPDATE act_history
        SET physical_announcement_state = ?,
            physical_announcement_at = ?,
            operator = ?,
            source = ?,
            server_timestamp = ?
        WHERE act_id = ?
        """,
        (state, _iso(current_time), operator, source, _iso(current_time), act_id),
    )
    log_event(
        connection,
        "act_physical_announcement_recorded",
        {"act_id": act_id, "operator": operator, "state": state},
        source=source,
        created_at=current_time,
    )
    return _unlock_code_state(connection, act_id)


def set_active_act_elapsed_minutes(
    connection: sqlite3.Connection,
    settings: Settings,
    elapsed_minutes: int,
    *,
    operator: str = "master",
    source: str = "master_time_control",
    now: datetime | None = None,
) -> dict[str, object]:
    ensure_runtime_schema(connection)
    ensure_runtime_content_state(connection)
    current_time = now or datetime.now(UTC)
    elapsed_minutes = max(0, int(elapsed_minutes))
    state = _current_state(connection)
    act_id = state.get("current_act_id")
    if not act_id:
        raise UnlockCodeHiddenError("Act must be started before elapsed time can be changed.")

    started_at = current_time - timedelta(minutes=elapsed_minutes)
    started_at_text = _iso(started_at)
    now_text = _iso(current_time)
    connection.execute(
        """
        UPDATE act_history
        SET started_at = ?,
            operator = ?,
            source = ?,
            server_timestamp = ?
        WHERE act_id = ?
        """,
        (started_at_text, operator, source, now_text, act_id),
    )
    connection.execute(
        """
        UPDATE act_state
        SET active_started_at = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (started_at_text, now_text),
    )
    log_event(
        connection,
        "act_elapsed_time_set",
        {
            "act_id": act_id,
            "elapsed_minutes": elapsed_minutes,
            "operator": operator,
            "source": source,
            "started_at": started_at_text,
        },
        source=source,
        created_at=current_time,
    )
    applied = apply_due_timers(connection, settings, now=current_time, source=source)
    return {
        "act_id": act_id,
        "elapsed_minutes": elapsed_minutes,
        "active_started_at": started_at_text,
        "state": _current_state(connection),
        "applied_timers": applied,
    }


def reveal_unlock_code(
    connection: sqlite3.Connection,
    act_id: str,
    *,
    operator: str,
    source: str = "master_api",
    now: datetime | None = None,
) -> dict[str, object]:
    ensure_runtime_schema(connection)
    current_time = now or datetime.now(UTC)
    act_row = _fetch_act(connection, act_id)
    if act_row is None:
        raise ActNotFoundError(f"Unknown act_id: {act_id}")
    history = connection.execute(
        """
        SELECT physical_announcement_state
        FROM act_history
        WHERE act_id = ?
        """,
        (act_id,),
    ).fetchone()
    if history is None:
        raise UnlockCodeHiddenError("Act has not started yet.")
    if _to_bool(act_row["physical_announcement_required"]) and not _is_announced(
        str(history["physical_announcement_state"])
    ):
        raise UnlockCodeHiddenError("Physical announcement must be recorded before reveal.")

    unlock = _fetch_unlock_code(connection, act_id)
    if unlock is None:
        raise ActNotFoundError(f"No unlock code configured for act_id: {act_id}")
    connection.execute(
        """
        UPDATE act_history
        SET unlock_revealed_at = COALESCE(unlock_revealed_at, ?),
            unlock_revealed_by = COALESCE(unlock_revealed_by, ?),
            server_timestamp = ?
        WHERE act_id = ?
        """,
        (_iso(current_time), operator, _iso(current_time), act_id),
    )
    payload = {
        "act_id": act_id,
        "unlock_id": unlock["unlock_id"],
        "code": unlock["code"],
        "revealed": True,
        "operator": operator,
        "physical_announcement_state": history["physical_announcement_state"],
        "server_timestamp": _iso(current_time),
    }
    log_event(
        connection,
        "act_unlock_code_revealed",
        payload,
        source=source,
        created_at=current_time,
    )
    return payload


def get_act_state(
    connection: sqlite3.Connection,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    applied = apply_due_timers(connection, settings, now=now)
    return {
        "state": _current_state(connection),
        "acts": [_act_payload(row) for row in _fetch_acts(connection)],
        "history": [
            {
                "act_id": row["act_id"],
                "status": row["status"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "operator": row["operator"],
                "source": row["source"],
                "physical_announcement_state": row["physical_announcement_state"],
                "physical_announcement_at": row["physical_announcement_at"],
                "unlock_revealed_at": row["unlock_revealed_at"],
                "unlock_revealed_by": row["unlock_revealed_by"],
            }
            for row in connection.execute(
                """
                SELECT *
                FROM act_history
                ORDER BY started_at
                """
            ).fetchall()
        ],
        "timers": timer_status(connection, now=now),
        "applied_timers": applied,
        "resources": _resource_state(connection),
    }


def _reset_game_for_registration(
    connection: sqlite3.Connection,
    *,
    operator: str,
    source: str,
    now: datetime,
) -> dict[str, object]:
    now_text = _iso(now)
    tables_to_clear = [
        "reward_approval_audit",
        "asset_locks",
        "asset_ownership",
        "reward_approvals",
        "npc_deals",
        "npc_runtime_events",
        "pve_consumed_objects",
        "pve_cooldowns",
        "pve_attempts",
        "master_corrections",
        "event_reviews",
        "events",
        "reputation_changes",
        "reputation_state",
        "lord_battle_actions",
        "lord_battle_log",
        "lord_battles",
        "pending_lord_moves",
        "territory_claim_runtime",
        "lord_map_intel",
        "pending_tick_reward_runtime",
        "garrison_runtime_state",
        "domain_buildings",
        "recruit_offer_runtime",
        "army_reserve_runtime",
        "active_army_runtime",
        "escrow_ledger",
        "order_runtime_state",
        "army_windows",
        "applied_timer_ticks",
        "pvp_reviews",
        "pvp_stake_ledger",
        "gwent_rounds",
        "gwent_runtime_matches",
        "pvp_challenges",
        "pvp_table_runtime",
        "personal_card_conversions",
        "potion_scene_usage",
        "potion_inventory",
        "potion_market_runtime",
        "trade_transfer_runtime",
        "magic_effects",
        "sorceress_spell_casts",
        "locked_magical_intent",
        "favorite_history",
        "favorite_runtime",
        "sorceress_alignment_evidence",
        "final_master_notes",
        "raid_effects",
        "client_sync_state",
        "player_runtime_state",
        "domain_runtime_state",
        "territory_runtime_state",
        "act_history",
    ]
    cleared = {
        table_name: deleted
        for table_name in tables_to_clear
        if (deleted := _delete_table_if_exists(connection, table_name)) > 0
    }

    if _table_exists(connection, "final_lock_state"):
        connection.execute(
            """
            UPDATE final_lock_state
            SET locked_at = NULL,
                operator = NULL,
                source = NULL
            WHERE id = 1
            """
        )
    if _table_exists(connection, "pvp_throttle_state"):
        connection.execute(
            """
            UPDATE pvp_throttle_state
            SET mode = 'normal',
                max_tables = 2,
                max_started_per_player_per_act = 2,
                final_lock_behavior = 'no_new_challenges_after_final_lock',
                updated_at = ?
            WHERE id = 1
            """,
            (now_text,),
        )
    connection.execute(
        """
        UPDATE act_state
        SET current_act_id = NULL,
            status = 'not_started',
            active_started_at = NULL,
            final_locked_at = NULL,
            updated_at = ?
        WHERE id = 1
        """,
        (now_text,),
    )

    ensure_runtime_content_state(connection)
    _reset_initial_territory_state(connection, now_text)
    _reset_initial_domain_locations(connection, now_text)
    _set_runtime_flag(
        connection,
        CLEAN_REGISTRATION_FLAG,
        {
            "enabled": True,
            "act_id": REGISTRATION_ACT_ID,
            "operator": operator,
            "source": source,
            "updated_at": now_text,
        },
        now_text,
    )

    domain_gold_values = [
        _to_int(row["gold"])
        for row in connection.execute(
            "SELECT gold FROM domain_runtime_state ORDER BY domain_id"
        ).fetchall()
    ]
    payload = {
        "status": "applied",
        "operator": operator,
        "cleared_tables": cleared,
        "domain_count": len(domain_gold_values),
        "initial_domain_gold": sorted(set(domain_gold_values)),
        "clean_lord_seed_runtime": True,
    }
    log_event(
        connection,
        "registration_game_reset",
        payload,
        source=source,
        created_at=now,
    )
    return payload


def _grant_challenge_tokens(
    connection: sqlite3.Connection,
    act_id: str,
    *,
    operator: str,
    source: str,
    now: datetime,
) -> dict[str, object]:
    if not _table_exists(connection, "challenge_tokens"):
        return {"status": "skipped", "reason": "challenge_tokens table missing"}
    row = connection.execute(
        """
        SELECT tokens_per_player, start_window_min
        FROM challenge_tokens
        WHERE act_id = ?
        LIMIT 1
        """,
        (act_id,),
    ).fetchone()
    if row is None:
        return {"status": "skipped", "reason": "no token rule for act"}
    tokens = _to_int(row["tokens_per_player"])
    connection.execute(
        """
        UPDATE player_runtime_state
        SET challenge_tokens = challenge_tokens + ?,
            updated_at = ?
        WHERE role_type IN ('lord', 'sorceress', 'witcher')
        """,
        (tokens, _iso(now)),
    )
    payload = {
        "act_id": act_id,
        "tokens_per_player": tokens,
        "start_window_min": _to_int(row["start_window_min"]),
        "operator": operator,
        "player_count": _player_count(connection),
        "eligible_player_count": _challenge_token_player_count(connection),
        "status": "applied",
    }
    log_event(connection, "challenge_tokens_granted", payload, source=source, created_at=now)
    return payload


def _open_army_windows(
    connection: sqlite3.Connection,
    act_row: sqlite3.Row,
    *,
    operator: str,
    source: str,
    now: datetime,
) -> dict[str, object]:
    act_id = str(act_row["act_id"])
    duration = max(0, _to_int(act_row["end_offset_min"]) - _to_int(act_row["start_offset_min"]))
    closes_at = now + timedelta(minutes=duration)
    windows = []
    for row in connection.execute(
        """
        SELECT domain_id, mp_cap
        FROM domain_runtime_state
        ORDER BY domain_id
        """
    ).fetchall():
        payload = {"operator": operator, "act_duration_min": duration}
        connection.execute(
            """
            INSERT INTO army_windows (
                act_id, domain_id, status, opened_at, closes_at, payload_json
            )
            VALUES (?, ?, 'open', ?, ?, ?)
            ON CONFLICT(act_id, domain_id) DO UPDATE SET
                status = excluded.status,
                opened_at = excluded.opened_at,
                closes_at = excluded.closes_at,
                payload_json = excluded.payload_json
            """,
            (
                act_id,
                row["domain_id"],
                _iso(now),
                _iso(closes_at),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET current_mp = mp_cap,
                updated_at = ?
            WHERE domain_id = ?
            """,
            (_iso(now), row["domain_id"]),
        )
        windows.append(
            {
                "domain_id": row["domain_id"],
                "status": "open",
                "opened_at": _iso(now),
                "closes_at": _iso(closes_at),
                "current_mp": row["mp_cap"],
            }
        )
    payload = {"act_id": act_id, "operator": operator, "windows": windows, "status": "applied"}
    log_event(connection, "army_windows_opened", payload, source=source, created_at=now)
    return payload


def _complete_previous_act(
    connection: sqlite3.Connection, act_id: str, completed_at: datetime
) -> None:
    connection.execute(
        """
        UPDATE act_history
        SET status = 'completed',
            completed_at = COALESCE(completed_at, ?)
        WHERE act_id = ?
        """,
        (_iso(completed_at), act_id),
    )


def _current_state(connection: sqlite3.Connection) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT current_act_id, status, active_started_at, final_locked_at, updated_at
        FROM act_state
        WHERE id = 1
        """
    ).fetchone()
    if row is None:
        return {"current_act_id": None, "status": "not_started"}
    final_lock = connection.execute(
        "SELECT locked_at FROM final_lock_state WHERE id = 1"
    ).fetchone()
    return {
        "current_act_id": row["current_act_id"],
        "status": row["status"],
        "active_started_at": row["active_started_at"],
        "final_locked_at": final_lock["locked_at"] if final_lock else row["final_locked_at"],
        "updated_at": row["updated_at"],
    }


def _resource_state(connection: sqlite3.Connection) -> dict[str, object]:
    return {
        "players": [
            {
                "player_id": row["player_id"],
                "role_type": row["role_type"],
                "level": row["level"],
                "gold": row["gold"],
                "mana": row["mana"],
                "max_mana": row["max_mana"],
                "challenge_tokens": row["challenge_tokens"],
            }
            for row in connection.execute(
                """
                SELECT *
                FROM player_runtime_state
                ORDER BY player_id
                """
            ).fetchall()
        ],
        "domains": [
            {
                "domain_id": row["domain_id"],
                "lord_player_id": row["lord_player_id"],
                "gold": row["gold"],
                "base_income": row["base_income"],
                "current_mp": row["current_mp"],
                "mp_cap": row["mp_cap"],
                "influence": row["influence"] if "influence" in row.keys() else 0,
            }
            for row in connection.execute(
                """
                SELECT *
                FROM domain_runtime_state
                ORDER BY domain_id
                """
            ).fetchall()
        ],
        "army_windows": [
            {
                "act_id": row["act_id"],
                "domain_id": row["domain_id"],
                "status": row["status"],
                "opened_at": row["opened_at"],
                "closes_at": row["closes_at"],
            }
            for row in connection.execute(
                """
                SELECT *
                FROM army_windows
                ORDER BY act_id, domain_id
                """
            ).fetchall()
        ],
    }


def _unlock_code_state(connection: sqlite3.Connection, act_id: str) -> dict[str, object]:
    unlock = _fetch_unlock_code(connection, act_id)
    history = connection.execute(
        """
        SELECT physical_announcement_state, unlock_revealed_at, unlock_revealed_by
        FROM act_history
        WHERE act_id = ?
        """,
        (act_id,),
    ).fetchone()
    if unlock is None:
        return {"configured": False, "revealed": False}
    can_reveal = history is not None and _is_announced(str(history["physical_announcement_state"]))
    return {
        "configured": True,
        "unlock_id": unlock["unlock_id"],
        "act_id": act_id,
        "revealed": bool(history and history["unlock_revealed_at"]),
        "available": can_reveal,
        "code": unlock["code"] if history and history["unlock_revealed_at"] else None,
        "physical_announcement_state": history["physical_announcement_state"] if history else None,
        "unlock_revealed_at": history["unlock_revealed_at"] if history else None,
        "unlock_revealed_by": history["unlock_revealed_by"] if history else None,
    }


def _fetch_unlock_code(
    connection: sqlite3.Connection, act_id: str
) -> sqlite3.Row | None:
    if not _table_exists(connection, "act_unlock_codes"):
        return None
    return connection.execute(
        """
        SELECT unlock_id, act_id, code
        FROM act_unlock_codes
        WHERE act_id = ?
        LIMIT 1
        """,
        (act_id,),
    ).fetchone()


def _fetch_act(connection: sqlite3.Connection, act_id: str) -> sqlite3.Row | None:
    if not _table_exists(connection, "acts"):
        return None
    return connection.execute(
        """
        SELECT *
        FROM acts
        WHERE act_id = ?
        """,
        (act_id,),
    ).fetchone()


def _fetch_acts(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    if not _table_exists(connection, "acts"):
        return []
    return connection.execute(
        """
        SELECT *
        FROM acts
        ORDER BY sequence
        """
    ).fetchall()


def _act_payload(row: sqlite3.Row) -> dict[str, object]:
    return {
        "act_id": row["act_id"],
        "sequence": _to_int(row["sequence"]),
        "act_type": row["act_type"],
        "name": row["name"],
        "start_offset_min": _to_int(row["start_offset_min"]),
        "end_offset_min": _to_int(row["end_offset_min"]),
        "unlock_required": _to_bool(row["unlock_required"]),
        "physical_announcement_required": _to_bool(row["physical_announcement_required"]),
    }


def _player_count(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) FROM player_runtime_state").fetchone()
    return int(row[0])


def _challenge_token_player_count(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*)
        FROM player_runtime_state
        WHERE role_type IN ('lord', 'sorceress', 'witcher')
        """
    ).fetchone()
    return int(row[0])


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


def _delete_table_if_exists(connection: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(connection, table_name):
        return 0
    cursor = connection.execute(f"DELETE FROM {table_name}")
    return max(0, int(cursor.rowcount or 0))


def _reset_initial_territory_state(connection: sqlite3.Connection, now_text: str) -> None:
    if not _table_exists(connection, "territories"):
        return
    connection.execute(
        """
        INSERT INTO territory_runtime_state (
            territory_id, owner_domain_id, status, controlled_since, updated_at
        )
        SELECT
            territory_id,
            NULLIF(owner_domain_id, ''),
            CASE WHEN NULLIF(owner_domain_id, '') IS NULL THEN 'neutral' ELSE 'controlled' END,
            CASE WHEN NULLIF(owner_domain_id, '') IS NULL THEN NULL ELSE ? END,
            ?
        FROM territories
        ORDER BY _row_number
        """,
        (now_text, now_text),
    )


def _reset_initial_domain_locations(connection: sqlite3.Connection, now_text: str) -> None:
    if not _table_exists(connection, "map_nodes") or not _table_exists(connection, "territories"):
        return
    connection.execute(
        """
        UPDATE domain_runtime_state
        SET current_node_id = (
                SELECT n.node_id
                FROM territories t
                JOIN map_nodes n ON n.territory_id = t.territory_id
                WHERE t.owner_domain_id = domain_runtime_state.domain_id
                  AND t.bonus_type = 'residence'
                ORDER BY t._row_number
                LIMIT 1
            ),
            active_army_capacity = ?,
            raid_tokens = 1,
            raid_token_cap = 1,
            updated_at = ?
        """,
        (DEFAULT_ACTIVE_ARMY_STACK_CAPACITY, now_text),
    )


def _set_runtime_flag(
    connection: sqlite3.Connection,
    flag_id: str,
    payload: dict[str, object],
    now_text: str,
) -> None:
    connection.execute(
        """
        INSERT INTO runtime_flags (flag_id, value_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(flag_id) DO UPDATE SET
            value_json = excluded.value_json,
            updated_at = excluded.updated_at
        """,
        (flag_id, json.dumps(payload, ensure_ascii=False, sort_keys=True), now_text),
    )


def _is_announced(value: str) -> bool:
    return value.strip().lower() in ANNOUNCED_STATES


def _to_bool(value: object) -> bool:
    return str(value).strip().lower() == "true"


def _to_int(value: object) -> int:
    if value is None or str(value) == "":
        return 0
    return int(value)


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")
