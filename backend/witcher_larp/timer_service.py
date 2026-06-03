"""Auto timer engine for act-relative runtime effects."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from .backup_service import run_backup
from .config import Settings
from .runtime_schema import ensure_runtime_schema, log_event


def apply_due_timers(
    connection: sqlite3.Connection,
    settings: Settings,
    *,
    now: datetime | None = None,
    source: str = "auto_timer",
) -> list[dict[str, object]]:
    ensure_runtime_schema(connection)
    ensure_runtime_content_state(connection)
    current_time = now or datetime.now(UTC)
    applied: list[dict[str, object]] = []
    if not _table_exists(connection, "acts") or not _table_exists(connection, "auto_timers"):
        return applied

    act_rows = connection.execute(
        """
        SELECT
            h.act_id,
            h.started_at,
            h.operator,
            a.start_offset_min,
            a.end_offset_min
        FROM act_history h
        JOIN acts a ON a.act_id = h.act_id
        ORDER BY a.sequence
        """
    ).fetchall()
    for act_row in act_rows:
        started_at = _parse_iso(str(act_row["started_at"]))
        elapsed_minutes = int((current_time - started_at).total_seconds() // 60)
        if elapsed_minutes < 0:
            continue
        act_duration = max(
            0,
            _to_int(act_row["end_offset_min"]) - _to_int(act_row["start_offset_min"]),
        )
        elapsed_minutes = min(elapsed_minutes, act_duration)
        timer_rows = connection.execute(
            """
            SELECT timer_id, act_id, timer_type, offset_min, interval_min, effect_type
            FROM auto_timers
            WHERE act_id = ?
            ORDER BY _row_number
            """,
            (act_row["act_id"],),
        ).fetchall()
        for timer_row in timer_rows:
            due_offsets = _due_offsets_for_timer(
                timer_row,
                act_start_offset=_to_int(act_row["start_offset_min"]),
                elapsed_minutes=elapsed_minutes,
            )
            for due_offset in due_offsets:
                due_at = started_at + timedelta(minutes=due_offset)
                if _timer_tick_exists(connection, str(timer_row["timer_id"]), due_at):
                    continue
                payload = _apply_timer_effect(
                    connection,
                    settings,
                    timer_row,
                    act_id=str(act_row["act_id"]),
                    due_at=due_at,
                    applied_at=current_time,
                    source=source,
                )
                _record_timer_tick(
                    connection,
                    timer_row,
                    act_id=str(act_row["act_id"]),
                    due_at=due_at,
                    applied_at=current_time,
                    source=source,
                    payload=payload,
                )
                applied.append(payload)
    return applied


def timer_status(
    connection: sqlite3.Connection,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    ensure_runtime_schema(connection)
    current_time = now or datetime.now(UTC)
    applied_count = connection.execute(
        "SELECT COUNT(*) FROM applied_timer_ticks"
    ).fetchone()[0]
    return {
        "server_time": current_time.isoformat(timespec="seconds"),
        "applied_tick_count": int(applied_count),
        "ticks": [
            {
                "timer_id": row["timer_id"],
                "act_id": row["act_id"],
                "effect_type": row["effect_type"],
                "due_at": row["due_at"],
                "applied_at": row["applied_at"],
            }
            for row in connection.execute(
                """
                SELECT timer_id, act_id, effect_type, due_at, applied_at
                FROM applied_timer_ticks
                ORDER BY applied_at, timer_id
                """
            ).fetchall()
        ],
    }


def ensure_runtime_content_state(connection: sqlite3.Connection) -> None:
    ensure_runtime_schema(connection)
    if _table_exists(connection, "players"):
        for row in connection.execute(
            """
            SELECT player_id, role_type, level, xp, gold, stats_json
            FROM players
            ORDER BY _row_number
            """
        ).fetchall():
            level = _to_int(row["level"])
            role_type = str(row["role_type"])
            max_mana = _mana_max(level) if role_type == "sorceress" else 0
            connection.execute(
                """
                INSERT INTO player_runtime_state (
                    player_id, role_type, level, xp, gold, stats_json,
                    mana, max_mana, challenge_tokens, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, 0, ?)
                ON CONFLICT(player_id) DO NOTHING
                """,
                (
                    row["player_id"],
                    role_type,
                    level,
                    _to_int(row["xp"]),
                    _to_int(row["gold"]),
                    row["stats_json"],
                    max_mana,
                    _iso(),
                ),
            )

    if _table_exists(connection, "domains"):
        movement_by_domain = _movement_defaults_by_domain(connection)
        if _table_exists(connection, "players"):
            domain_rows = connection.execute(
                """
                SELECT d.domain_id, d.lord_player_id, d.starting_gold, d.base_income,
                       p.stats_json AS lord_stats_json
                FROM domains d
                LEFT JOIN players p ON p.player_id = d.lord_player_id
                ORDER BY d._row_number
                """
            ).fetchall()
        else:
            domain_rows = connection.execute(
                """
                SELECT domain_id, lord_player_id, starting_gold, base_income,
                       NULL AS lord_stats_json
                FROM domains
                ORDER BY _row_number
                """
            ).fetchall()
        for row in domain_rows:
            movement = movement_by_domain.get(str(row["domain_id"]), {"current_mp": 0, "mp_cap": 0})
            starting_influence = _stats_influence(row["lord_stats_json"])
            connection.execute(
                """
                INSERT INTO domain_runtime_state (
                    domain_id, lord_player_id, gold, base_income, current_mp,
                    mp_cap, influence, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(domain_id) DO NOTHING
                """,
                (
                    row["domain_id"],
                    row["lord_player_id"],
                    _to_int(row["starting_gold"]),
                    _to_int(row["base_income"]),
                    movement["current_mp"],
                    movement["mp_cap"],
                    starting_influence,
                    _iso(),
                ),
            )


def _apply_timer_effect(
    connection: sqlite3.Connection,
    settings: Settings,
    timer_row: sqlite3.Row,
    *,
    act_id: str,
    due_at: datetime,
    applied_at: datetime,
    source: str,
) -> dict[str, object]:
    effect_type = str(timer_row["effect_type"])
    payload: dict[str, object] = {
        "timer_id": timer_row["timer_id"],
        "act_id": act_id,
        "effect_type": effect_type,
        "due_at": due_at.isoformat(timespec="seconds"),
        "applied_at": applied_at.isoformat(timespec="seconds"),
        "source": source,
    }
    if effect_type == "lord_income_and_mana":
        payload.update(_apply_lord_income_mana_and_mp(connection, applied_at))
    elif effect_type == "lock_new_pvp_challenges":
        payload.update(_apply_final_lock(connection, applied_at, source))
    elif effect_type == "backup_before_final":
        backup = run_backup(
            connection,
            settings,
            trigger_type="pre_final_lock",
            operator="auto_timer",
            source=source,
            affects_transition=True,
            now=applied_at,
        )
        payload["backup"] = backup.as_dict()
    else:
        payload["status"] = "no_effect_handler"

    log_event(
        connection,
        "timer_tick_applied",
        payload,
        source=source,
        created_at=applied_at,
    )
    return payload


def _apply_lord_income_mana_and_mp(
    connection: sqlite3.Connection, applied_at: datetime
) -> dict[str, object]:
    from .lord_runtime import anti_snowball_cut_for_domain, ensure_lord_runtime_state

    ensure_lord_runtime_state(connection)
    pending_rewards = _create_contested_pending_tick_rewards(connection, applied_at)
    domain_updates = []
    for row in connection.execute(
        """
        SELECT domain_id, gold, base_income, current_mp, mp_cap, influence
        FROM domain_runtime_state
        ORDER BY domain_id
        """
    ).fetchall():
        territory_income = _territory_income(connection, str(row["domain_id"]))
        raw_income = _to_int(row["base_income"]) + territory_income
        influence_gain = _influence_gain(connection, str(row["domain_id"]))
        anti_snowball = anti_snowball_cut_for_domain(connection, str(row["domain_id"]))
        cut_percent = _to_int(anti_snowball["income_cut_percent"])
        income = (raw_income * (100 - cut_percent)) // 100
        current_mp = min(_to_int(row["mp_cap"]), _to_int(row["current_mp"]) + _mp_refill_amount(connection))
        influence = _to_int(row["influence"]) + influence_gain
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET gold = gold + ?, current_mp = ?, influence = ?, updated_at = ?
            WHERE domain_id = ?
            """,
            (income, current_mp, influence, _iso(applied_at), row["domain_id"]),
        )
        domain_updates.append(
            {
                "domain_id": row["domain_id"],
                "income": income,
                "raw_income": raw_income,
                "territory_income": territory_income,
                "influence_gain": influence_gain,
                "influence": influence,
                "current_mp": current_mp,
                "anti_snowball": anti_snowball,
            }
        )

    sorceress_updates = []
    for row in connection.execute(
        """
        SELECT player_id, level, mana, max_mana
        FROM player_runtime_state
        WHERE role_type = 'sorceress'
        ORDER BY player_id
        """
    ).fetchall():
        level = _to_int(row["level"])
        max_mana = _mana_max(level)
        bonuses = _mana_bonus_sources(connection, str(row["player_id"]))
        regen = _mana_regen(level, bonuses["bonus"])
        mana = min(max_mana, _to_int(row["mana"]) + regen)
        connection.execute(
            """
            UPDATE player_runtime_state
            SET mana = ?, max_mana = ?, updated_at = ?
            WHERE player_id = ?
            """,
            (mana, max_mana, _iso(applied_at), row["player_id"]),
        )
        sorceress_updates.append(
            {
                "player_id": row["player_id"],
                "level": level,
                "regen": regen,
                "mana": mana,
                "max_mana": max_mana,
                "patron_domain_id": bonuses["patron_domain_id"],
                "bonus_sources": bonuses["sources"],
            }
        )

    return {
        "status": "applied",
        "domain_updates": domain_updates,
        "sorceress_updates": sorceress_updates,
        "pending_tick_rewards": pending_rewards,
    }


def _apply_final_lock(
    connection: sqlite3.Connection, applied_at: datetime, source: str
) -> dict[str, object]:
    row = connection.execute("SELECT locked_at FROM final_lock_state WHERE id = 1").fetchone()
    if row is not None and row["locked_at"]:
        return {"status": "already_locked", "locked_at": row["locked_at"]}
    locked_at = _iso(applied_at)
    connection.execute(
        """
        UPDATE final_lock_state
        SET locked_at = ?, operator = 'auto_timer', source = ?
        WHERE id = 1
        """,
        (locked_at, source),
    )
    return {
        "status": "locked",
        "locked_at": locked_at,
        "pvp_challenge_state": "new_challenges_closed",
    }


def _record_timer_tick(
    connection: sqlite3.Connection,
    timer_row: sqlite3.Row,
    *,
    act_id: str,
    due_at: datetime,
    applied_at: datetime,
    source: str,
    payload: dict[str, object],
) -> None:
    connection.execute(
        """
        INSERT INTO applied_timer_ticks (
            timer_id, due_at, act_id, effect_type, applied_at, source, payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timer_row["timer_id"],
            due_at.isoformat(timespec="seconds"),
            act_id,
            timer_row["effect_type"],
            applied_at.isoformat(timespec="seconds"),
            source,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ),
    )


def _due_offsets_for_timer(
    timer_row: sqlite3.Row,
    *,
    act_start_offset: int,
    elapsed_minutes: int,
) -> list[int]:
    first_due = max(0, _to_int(timer_row["offset_min"]) - act_start_offset)
    if first_due > elapsed_minutes:
        return []
    interval = _to_int(timer_row["interval_min"])
    if str(timer_row["timer_type"]) == "one_shot" or interval <= 0:
        return [first_due]
    due_offsets: list[int] = []
    current = first_due
    while current <= elapsed_minutes:
        due_offsets.append(current)
        current += interval
    return due_offsets


def _timer_tick_exists(
    connection: sqlite3.Connection, timer_id: str, due_at: datetime
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM applied_timer_ticks
        WHERE timer_id = ? AND due_at = ?
        """,
        (timer_id, due_at.isoformat(timespec="seconds")),
    ).fetchone()
    return row is not None


def _movement_defaults_by_domain(
    connection: sqlite3.Connection,
) -> dict[str, dict[str, int]]:
    if not _table_exists(connection, "movement_pools"):
        return {}
    return {
        str(row["domain_id"]): {
            "current_mp": _to_int(row["current_mp"]),
            "mp_cap": _to_int(row["mp_cap"]),
        }
        for row in connection.execute(
            """
            SELECT domain_id, current_mp, mp_cap
            FROM movement_pools
            ORDER BY _row_number
            """
        ).fetchall()
    }


def _territory_income(connection: sqlite3.Connection, domain_id: str) -> int:
    if not _table_exists(connection, "territories"):
        return 0
    income_by_tier = {1: 8, 2: 14, 3: 22}
    total = 0
    if _table_exists(connection, "territory_runtime_state"):
        rows = connection.execute(
            """
            SELECT t.bonus_type, t.tier
            FROM territories t
            JOIN territory_runtime_state rt ON rt.territory_id = t.territory_id
            WHERE rt.owner_domain_id = ? AND rt.status = 'controlled'
            """,
            (domain_id,),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT bonus_type, tier
            FROM territories
            WHERE owner_domain_id = ?
            """,
            (domain_id,),
        ).fetchall()
    for row in rows:
        if row["bonus_type"] == "residence":
            continue
        total += income_by_tier.get(_to_int(row["tier"]), 0)
    return total


def _influence_gain(connection: sqlite3.Connection, domain_id: str) -> int:
    if not _table_exists(connection, "territories"):
        return 1
    if _table_exists(connection, "territory_runtime_state"):
        rows = connection.execute(
            """
            SELECT t.bonus_type
            FROM territories t
            JOIN territory_runtime_state rt ON rt.territory_id = t.territory_id
            WHERE rt.owner_domain_id = ? AND rt.status = 'controlled'
            """,
            (domain_id,),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT bonus_type
            FROM territories
            WHERE owner_domain_id = ?
            """,
            (domain_id,),
        ).fetchall()
    territory_bonus = sum(1 for row in rows if row["bonus_type"] != "residence")
    return 1 + territory_bonus


def _create_contested_pending_tick_rewards(
    connection: sqlite3.Connection, applied_at: datetime
) -> list[dict[str, object]]:
    if not (
        _table_exists(connection, "territory_runtime_state")
        and _table_exists(connection, "pending_tick_reward_runtime")
    ):
        return []
    created = []
    for row in connection.execute(
        """
        SELECT rt.territory_id, rt.owner_domain_id, t.tier
        FROM territory_runtime_state rt
        JOIN territories t ON t.territory_id = rt.territory_id
        WHERE rt.status IN ('in_battle', 'contested', 'contested_pending_tick')
        ORDER BY rt.territory_id
        """
    ).fetchall():
        reward_gold = {1: 8, 2: 14, 3: 22}.get(_to_int(row["tier"]), 0)
        pending_reward_id = (
            "pending_tick_"
            f"{row['territory_id']}_"
            f"{applied_at.isoformat(timespec='seconds').replace(':', '').replace('+', '_')}"
        )
        connection.execute(
            """
            INSERT INTO pending_tick_reward_runtime (
                pending_reward_id, domain_id, territory_id, reward_gold, status, due_at
            )
            VALUES (?, ?, ?, ?, 'pending', ?)
            ON CONFLICT(pending_reward_id) DO NOTHING
            """,
            (
                pending_reward_id,
                row["owner_domain_id"],
                row["territory_id"],
                reward_gold,
                applied_at.isoformat(timespec="seconds"),
            ),
        )
        created.append(
            {
                "pending_reward_id": pending_reward_id,
                "territory_id": row["territory_id"],
                "reward_gold": reward_gold,
                "status": "pending",
            }
        )
    return created


def _mana_bonus_sources(connection: sqlite3.Connection, player_id: str) -> dict[str, Any]:
    if not (_table_exists(connection, "players") and _table_exists(connection, "domains")):
        return {"bonus": 0, "sources": [], "patron_domain_id": None}
    patron_domain_id = _current_patron_domain_id(connection, player_id)
    if patron_domain_id is None or not _table_exists(connection, "territories"):
        return {"bonus": 0, "sources": [], "patron_domain_id": patron_domain_id}
    if _table_exists(connection, "territory_runtime_state"):
        rows = connection.execute(
            """
            SELECT t.territory_id
            FROM territories t
            JOIN territory_runtime_state rt ON rt.territory_id = t.territory_id
            WHERE rt.owner_domain_id = ?
              AND rt.status = 'controlled'
              AND t.bonus_type = 'magic'
            ORDER BY t.territory_id
            """,
            (patron_domain_id,),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT territory_id
            FROM territories
            WHERE owner_domain_id = ? AND bonus_type = 'magic'
            ORDER BY territory_id
            """,
            (patron_domain_id,),
        ).fetchall()
    sources = [str(row["territory_id"]) for row in rows]
    return {"bonus": len(sources), "sources": sources, "patron_domain_id": patron_domain_id}


def _current_patron_domain_id(connection: sqlite3.Connection, player_id: str) -> str | None:
    player = connection.execute(
        """
        SELECT sorceress_start_lord_id
        FROM players
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if player is None or not player["sorceress_start_lord_id"]:
        return None
    start_domain_id = _domain_id_for_lord(connection, str(player["sorceress_start_lord_id"]))
    current_domain_id = start_domain_id
    if _table_exists(connection, "sorceress_alignment_evidence"):
        for row in connection.execute(
            """
            SELECT alignment_state, payload_json
            FROM sorceress_alignment_evidence
            WHERE sorceress_id = ?
            ORDER BY created_at, evidence_id
            """,
            (player_id,),
        ).fetchall():
            alignment_state = str(row["alignment_state"])
            payload = _json_loads(str(row["payload_json"]), {})
            payload_domain_id = _patron_domain_id_from_payload(connection, payload)
            if payload_domain_id is not None:
                current_domain_id = payload_domain_id
            elif alignment_state == "start_lord_support":
                current_domain_id = start_domain_id
            elif alignment_state in {"independent_intrigue", "open_betrayal"} and _truthy(
                payload.get("no_patron")
            ):
                current_domain_id = None
    return current_domain_id


def _patron_domain_id_from_payload(
    connection: sqlite3.Connection, payload: dict[str, Any]
) -> str | None:
    for key in ("patron_domain_id", "new_patron_domain_id", "domain_id"):
        value = payload.get(key)
        if value and _domain_exists(connection, str(value)):
            return str(value)
    for key in ("patron_lord_id", "new_patron_lord_id", "lord_player_id", "lord_id"):
        value = payload.get(key)
        if value:
            domain_id = _domain_id_for_lord(connection, str(value))
            if domain_id is not None:
                return domain_id
    return None


def _domain_id_for_lord(connection: sqlite3.Connection, lord_player_id: str) -> str | None:
    row = connection.execute(
        """
        SELECT domain_id
        FROM domains
        WHERE lord_player_id = ?
        """,
        (lord_player_id,),
    ).fetchone()
    return str(row["domain_id"]) if row is not None else None


def _domain_exists(connection: sqlite3.Connection, domain_id: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM domains
        WHERE domain_id = ?
        """,
        (domain_id,),
    ).fetchone()
    return row is not None


def _mp_refill_amount(connection: sqlite3.Connection) -> int:
    if not _table_exists(connection, "movement_rules"):
        return 0
    row = connection.execute(
        """
        SELECT refill_amount
        FROM movement_rules
        ORDER BY _row_number
        LIMIT 1
        """
    ).fetchone()
    return _to_int(row["refill_amount"]) if row is not None else 0


def _mana_max(level: int) -> int:
    return 6 + level


def _mana_regen(level: int, bonuses: int) -> int:
    return 2 + (level // 3) + bonuses


def _stats_influence(value: object) -> int:
    if value in (None, ""):
        return 0
    try:
        stats = json.loads(str(value))
    except json.JSONDecodeError:
        return 0
    if not isinstance(stats, dict):
        return 0
    return _to_int(stats.get("Харизма", stats.get("influence")))


def _json_loads(value: str, default: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return default
    return parsed if isinstance(parsed, dict) else default


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


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


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")


def _to_int(value: object) -> int:
    if value is None or str(value) == "":
        return 0
    return int(value)
