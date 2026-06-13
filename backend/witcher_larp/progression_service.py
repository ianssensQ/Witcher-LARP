"""Player stat allocation runtime for initial build and level-up points."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import sqlite3
from typing import Any

from .runtime_schema import ensure_runtime_schema, log_event
from .stats import CANONICAL_STAT_SET, CANONICAL_STATS, RUNTIME_STAT_MAX, START_STAT_BUDGET, START_STAT_MAX


@dataclass(frozen=True)
class StatAllocationValidationResult:
    status: str
    reason: str | None
    metadata: dict[str, Any]


class StatAllocationConflictError(RuntimeError):
    """Raised when an accepted stat allocation no longer matches runtime state."""


def validate_stat_allocation(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    payload: dict[str, Any],
) -> StatAllocationValidationResult:
    ensure_runtime_schema(connection)
    try:
        plan = _allocation_plan(connection, player_id=player_id, payload=payload)
    except ValueError as exc:
        return StatAllocationValidationResult(
            "rejected",
            str(exc),
            {"progression_runtime": "v1", "player_id": player_id},
        )
    except LookupError as exc:
        return StatAllocationValidationResult(
            "needs_master_review",
            str(exc),
            {"progression_runtime": "v1", "player_id": player_id},
        )
    return StatAllocationValidationResult("ok", None, plan)


def apply_stat_allocation(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    payload: dict[str, Any],
    server_event_id: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(UTC)
    plan = _allocation_plan(connection, player_id=player_id, payload=payload)
    connection.execute(
        """
        UPDATE player_runtime_state
        SET stats_json = ?,
            unspent_stat_points = ?,
            updated_at = ?
        WHERE player_id = ?
        """,
        (
            _json_dumps(plan["stats_after"]),
            int(plan["unspent_stat_points_after"]),
            current_time.isoformat(timespec="seconds"),
            player_id,
        ),
    )
    applied = {
        "player_id": player_id,
        "allocation_type": plan["allocation_type"],
        "stat_deltas": plan["stat_deltas"],
        "stats_before": plan["stats_before"],
        "stats_after": plan["stats_after"],
        "unspent_stat_points_before": plan["unspent_stat_points_before"],
        "unspent_stat_points_after": plan["unspent_stat_points_after"],
        "server_event_id": server_event_id,
    }
    log_event(
        connection,
        "player_stats_allocated",
        applied,
        source="event_sync",
        created_at=current_time,
    )
    return applied


def _allocation_plan(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    player = _runtime_player(connection, player_id)
    payload_player_id = str(payload.get("player_id") or "").strip()
    if payload_player_id and payload_player_id != player_id:
        raise ValueError("stat allocation player_id does not match authenticated actor")

    stat_deltas = _stat_deltas(payload)
    if not stat_deltas:
        raise ValueError("stat allocation requires positive stat_deltas")
    total_delta = sum(stat_deltas.values())
    stats_before = _player_stats(player)
    stats_after = dict(stats_before)
    unspent_before = _to_int(player.get("unspent_stat_points"))
    initial_available = max(0, START_STAT_BUDGET - sum(stats_before.values()))

    allocation_type = str(payload.get("allocation_type") or "auto").strip().lower()
    if allocation_type == "auto":
        allocation_type = "initial" if initial_available > 0 else "level_up"
    if allocation_type not in {"initial", "level_up"}:
        raise ValueError(f"unsupported stat allocation_type: {allocation_type}")

    max_stat = _max_stat(connection)
    if allocation_type == "initial":
        if initial_available <= 0:
            raise ValueError("initial stat allocation is already complete")
        if total_delta > initial_available:
            raise ValueError("initial stat allocation exceeds remaining start budget")
        unspent_after = unspent_before
        for stat_id, delta in stat_deltas.items():
            after = stats_after[stat_id] + delta
            if after > START_STAT_MAX:
                raise ValueError("initial stat allocation exceeds start stat cap")
            stats_after[stat_id] = after
    else:
        if unspent_before <= 0:
            raise ValueError("no unspent stat points available")
        if total_delta > unspent_before:
            raise ValueError("stat allocation exceeds unspent stat points")
        unspent_after = unspent_before - total_delta
        for stat_id, delta in stat_deltas.items():
            after = stats_after[stat_id] + delta
            if after > max_stat:
                raise ValueError("stat allocation exceeds runtime stat cap")
            stats_after[stat_id] = after

    claimed_stats_after = _optional_stats_payload(payload.get("stats_after"))
    if claimed_stats_after is not None and claimed_stats_after != stats_after:
        raise ValueError("stat allocation stats_after does not match replay")
    if "unspent_stat_points_after" in payload and _to_int(payload["unspent_stat_points_after"]) != unspent_after:
        raise ValueError("stat allocation unspent_stat_points_after does not match replay")

    return {
        "progression_runtime": "v1",
        "player_id": player_id,
        "allocation_type": allocation_type,
        "stat_deltas": stat_deltas,
        "stats_before": stats_before,
        "stats_after": stats_after,
        "unspent_stat_points_before": unspent_before,
        "unspent_stat_points_after": unspent_after,
        "initial_stat_points_remaining_before": initial_available,
        "start_stat_budget": START_STAT_BUDGET,
        "start_stat_cap": START_STAT_MAX,
        "runtime_stat_cap": max_stat,
    }


def _stat_deltas(payload: dict[str, Any]) -> dict[str, int]:
    raw = payload.get("stat_deltas") or payload.get("deltas")
    if raw is None and payload.get("stat"):
        raw = {str(payload["stat"]): payload.get("points", 1)}
    if not isinstance(raw, dict):
        return {}
    deltas: dict[str, int] = {}
    for key, value in raw.items():
        stat_id = str(key).strip()
        if stat_id not in CANONICAL_STAT_SET:
            raise ValueError("stat allocation uses non-canonical stat")
        delta = _to_int(value)
        if delta <= 0:
            raise ValueError("stat allocation deltas must be positive")
        deltas[stat_id] = deltas.get(stat_id, 0) + delta
    return deltas


def _optional_stats_payload(raw: object) -> dict[str, int] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("stat allocation stats_after must be an object")
    stats = {stat_id: 0 for stat_id in CANONICAL_STATS}
    for key, value in raw.items():
        stat_id = str(key).strip()
        if stat_id not in CANONICAL_STAT_SET:
            raise ValueError("stat allocation stats_after uses non-canonical stat")
        stats[stat_id] = _to_int(value)
    return stats


def _runtime_player(connection: sqlite3.Connection, player_id: str) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT player_id, role_type, level, xp, gold, stats_json, unspent_stat_points
        FROM player_runtime_state
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if row is not None:
        return _clean_row(row)
    player = connection.execute(
        """
        SELECT player_id, role_type, level, xp, gold, stats_json
        FROM players
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if player is None:
        raise LookupError(f"unknown player_id: {player_id}")
    level = _to_int(player["level"])
    role_type = str(player["role_type"])
    max_mana = 6 + level if role_type == "sorceress" else 0
    connection.execute(
        """
        INSERT INTO player_runtime_state (
            player_id, role_type, level, xp, gold, stats_json,
            unspent_stat_points, mana, max_mana, challenge_tokens, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, 0, ?)
        ON CONFLICT(player_id) DO NOTHING
        """,
        (
            player_id,
            role_type,
            level,
            _to_int(player["xp"]),
            _to_int(player["gold"]),
            player["stats_json"],
            max_mana,
            datetime.now(UTC).isoformat(timespec="seconds"),
        ),
    )
    return {
        "player_id": player_id,
        "role_type": role_type,
        "level": level,
        "xp": _to_int(player["xp"]),
        "gold": _to_int(player["gold"]),
        "stats_json": player["stats_json"],
        "unspent_stat_points": 0,
    }


def _max_stat(connection: sqlite3.Connection) -> int:
    if _table_exists(connection, "xp_rules"):
        row = connection.execute(
            """
            SELECT max_stat
            FROM xp_rules
            ORDER BY _row_number
            LIMIT 1
            """
        ).fetchone()
        if row is not None:
            return _to_int(row["max_stat"]) or RUNTIME_STAT_MAX
    return RUNTIME_STAT_MAX


def _player_stats(player: dict[str, Any]) -> dict[str, int]:
    raw = player.get("stats_json") or "{}"
    if isinstance(raw, dict):
        parsed = raw
    else:
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            parsed = {}
    stats = {stat_id: 0 for stat_id in CANONICAL_STATS}
    for key, value in parsed.items():
        stat_id = str(key)
        if stat_id in CANONICAL_STAT_SET:
            stats[stat_id] = _to_int(value)
    return stats


def _clean_row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


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


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _to_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
