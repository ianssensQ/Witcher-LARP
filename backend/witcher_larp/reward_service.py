"""Master reward approval lifecycle and reward application."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from typing import Any

from .asset_service import AssetContractError
from .asset_service import active_locks_for_source, ensure_asset_contract_schema
from .asset_service import assert_reward_assets_unlocked
from .asset_service import grant_asset_ownership, lock_reward_assets, release_locks_for_source
from .asset_service import reward_asset_entries, reward_numeric_payload
from .runtime_schema import log_event
from .stats import CANONICAL_STATS, DEFAULT_STAT_ID
from .xp_service import spend_xp_for_levels


APPROVAL_ACTIONS = {"approve", "correct", "reject"}
FINAL_APPROVAL_STATUSES = {"approved", "corrected", "rejected"}


def create_pending_reward_approval(
    connection: sqlite3.Connection,
    *,
    approval_id: str,
    reward_id: str,
    player_id: str,
    source_event_id: int | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_asset_contract_schema(connection)
    timestamp = _iso(now)
    existing = connection.execute(
        """
        SELECT approval_id, status
        FROM reward_approvals
        WHERE approval_id = ?
        """,
        (approval_id,),
    ).fetchone()
    if existing is None:
        assert_reward_assets_unlocked(
            connection,
            reward_id=reward_id,
            purpose="reward approval",
        )
    connection.execute(
        """
        INSERT INTO reward_approvals (
            approval_id, reward_id, player_id, status, source_event_id,
            created_at, correction_json, locked_assets_json
        )
        VALUES (?, ?, ?, 'pending_master_approval', ?, ?, '{}', '[]')
        ON CONFLICT(approval_id) DO NOTHING
        """,
        (approval_id, reward_id, player_id, source_event_id, timestamp),
    )
    approval = _fetch_approval(connection, approval_id)
    if str(approval["status"]) == "pending_master_approval":
        lock_reward_assets(
            connection,
            approval_id=approval_id,
            player_id=player_id,
            reward_id=reward_id,
            now=now,
        )
    return reward_approval_payload(connection, approval_id)


def decide_reward_approval(
    connection: sqlite3.Connection,
    *,
    approval_id: str,
    action: str,
    operator: str,
    reason: str,
    correction: dict[str, Any] | None = None,
    source: str = "master_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_asset_contract_schema(connection)
    normalized_action = action.strip().lower()
    if normalized_action not in APPROVAL_ACTIONS:
        raise AssetContractError(
            "invalid_approval_action",
            f"Unsupported reward approval action: {action}.",
        )
    if not reason.strip():
        raise AssetContractError("missing_audit_reason", "Reward approval requires an audit reason.")
    current_time = now or datetime.now(UTC)
    approval = _fetch_approval(connection, approval_id)
    status_before = str(approval["status"])
    status_after = _status_for_action(normalized_action)
    if status_before in FINAL_APPROVAL_STATUSES:
        if status_before == status_after:
            return {
                **reward_approval_payload(connection, approval_id),
                "decision": {"status": "duplicate", "action": normalized_action},
                "duplicate": True,
            }
        raise AssetContractError(
            "approval_already_decided",
            f"Reward approval {approval_id} is already {status_before}.",
            409,
        )
    if status_before != "pending_master_approval":
        raise AssetContractError(
            "approval_not_pending",
            f"Reward approval {approval_id} is not pending.",
            409,
        )

    correction_payload = correction or {}
    reward_id = str(approval["reward_id"])
    player_id = str(approval["player_id"])
    reward_update = {"status": "not_applied"}
    if normalized_action == "reject":
        release_locks_for_source(
            connection,
            lock_type="reward_approval",
            source_ref_id=approval_id,
            status="released",
            reason=reason,
            now=current_time,
        )
    else:
        reward_update = _apply_reward_payload(
            connection,
            approval_id=approval_id,
            player_id=player_id,
            reward_id=reward_id,
            correction=correction_payload if normalized_action == "correct" else {},
            status_after=status_after,
            now=current_time,
        )

    connection.execute(
        """
        UPDATE reward_approvals
        SET status = ?,
            decided_at = ?,
            decided_by = ?,
            audit_reason = ?,
            correction_json = ?,
            applied_at = ?
        WHERE approval_id = ?
        """,
        (
            status_after,
            _iso(current_time),
            operator,
            reason,
            _json_dumps(correction_payload if normalized_action == "correct" else {}),
            _iso(current_time) if normalized_action in {"approve", "correct"} else None,
            approval_id,
        ),
    )
    _record_audit(
        connection,
        approval_id=approval_id,
        action=normalized_action,
        operator=operator,
        reason=reason,
        status_before=status_before,
        status_after=status_after,
        correction=correction_payload if normalized_action == "correct" else {},
        now=current_time,
    )
    source_event_id = approval["source_event_id"]
    if source_event_id is not None:
        connection.execute(
            """
            UPDATE pve_attempts
            SET reward_status = ?
            WHERE server_event_id = ?
            """,
            (status_after, source_event_id),
        )
    payload = reward_approval_payload(connection, approval_id)
    payload["decision"] = {
        "status": status_after,
        "action": normalized_action,
        "reward_update": reward_update,
    }
    payload["duplicate"] = False
    log_event(
        connection,
        "reward_approval_decided",
        payload,
        source=source,
        created_at=current_time,
    )
    return payload


def reward_approval_payload(connection: sqlite3.Connection, approval_id: str) -> dict[str, Any]:
    ensure_asset_contract_schema(connection)
    row = _fetch_approval(connection, approval_id)
    payload = _clean_row(row)
    payload["correction"] = _json_loads(payload.get("correction_json"), {})
    payload["locked_assets"] = _json_loads(payload.get("locked_assets_json"), [])
    payload["active_locks"] = active_locks_for_source(
        connection,
        lock_type="reward_approval",
        source_ref_id=approval_id,
    )
    payload["audit"] = [
        {
            **_clean_row(audit),
            "correction": _json_loads(audit["correction_json"], {}),
        }
        for audit in connection.execute(
            """
            SELECT *
            FROM reward_approval_audit
            WHERE approval_id = ?
            ORDER BY created_at, audit_id
            """,
            (approval_id,),
        ).fetchall()
    ]
    return payload


def _apply_reward_payload(
    connection: sqlite3.Connection,
    *,
    approval_id: str,
    player_id: str,
    reward_id: str,
    correction: dict[str, Any],
    status_after: str,
    now: datetime,
) -> dict[str, Any]:
    numeric = reward_numeric_payload(connection, reward_id, correction)
    player = _runtime_player(connection, player_id)
    xp_before = _to_int(player.get("xp"))
    level_before = _to_int(player.get("level"))
    gold_before = _to_int(player.get("gold"))
    unspent_before = _to_int(player.get("unspent_stat_points"))
    xp_after, level_after = spend_xp_for_levels(
        connection,
        level_before=level_before,
        xp_available=xp_before + numeric["xp"],
    )
    unspent_after = unspent_before + max(0, level_after - level_before)

    connection.execute(
        """
        UPDATE player_runtime_state
        SET xp = ?, level = ?, gold = ?, unspent_stat_points = ?, updated_at = ?
        WHERE player_id = ?
        """,
        (
            xp_after,
            level_after,
            gold_before + numeric["gold"],
            unspent_after,
            _iso(now),
            player_id,
        ),
    )

    active_locks = active_locks_for_source(
        connection,
        lock_type="reward_approval",
        source_ref_id=approval_id,
    )
    if status_after == "corrected":
        release_locks_for_source(
            connection,
            lock_type="reward_approval",
            source_ref_id=approval_id,
            status="released",
            reason="corrected reward replaced original locked assets",
            now=now,
        )
        active_locks = []

    granted_assets: list[dict[str, Any]] = []
    if active_locks:
        release_locks_for_source(
            connection,
            lock_type="reward_approval",
            source_ref_id=approval_id,
            status="consumed",
            reason=f"reward approval {status_after}",
            now=now,
        )
        for lock in active_locks:
            granted_assets.append(
                grant_asset_ownership(
                    connection,
                    owner_player_id=player_id,
                    asset_type=str(lock["asset_type"]),
                    asset_id=str(lock["asset_id"]),
                    quantity=_to_int(lock["quantity"]) or 1,
                    source=f"reward_{status_after}",
                    source_ref_id=approval_id,
                    now=now,
                )
            )
    else:
        for asset in reward_asset_entries(connection, reward_id, correction):
            granted_assets.append(
                grant_asset_ownership(
                    connection,
                    owner_player_id=player_id,
                    asset_type=str(asset["asset_type"]),
                    asset_id=str(asset["asset_id"]),
                    quantity=_to_int(asset["quantity"]) or 1,
                    source=f"reward_{status_after}",
                    source_ref_id=approval_id,
                    now=now,
                )
            )

    return {
        "status": "applied",
        "reward_id": reward_id,
        "xp_gain": numeric["xp"],
        "gold_gain": numeric["gold"],
        "xp_before": xp_before,
        "xp_after": xp_after,
        "level_before": level_before,
        "level_after": level_after,
        "stat_points_gained": max(0, level_after - level_before),
        "unspent_stat_points_before": unspent_before,
        "unspent_stat_points_after": unspent_after,
        "stat_gains": [],
        "granted_assets": granted_assets,
    }


def _record_audit(
    connection: sqlite3.Connection,
    *,
    approval_id: str,
    action: str,
    operator: str,
    reason: str,
    status_before: str,
    status_after: str,
    correction: dict[str, Any],
    now: datetime,
) -> None:
    connection.execute(
        """
        INSERT INTO reward_approval_audit (
            approval_id, action, operator, reason, status_before,
            status_after, correction_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            approval_id,
            action,
            operator,
            reason,
            status_before,
            status_after,
            _json_dumps(correction),
            _iso(now),
        ),
    )


def _fetch_approval(connection: sqlite3.Connection, approval_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT *
        FROM reward_approvals
        WHERE approval_id = ?
        """,
        (approval_id,),
    ).fetchone()
    if row is None:
        raise AssetContractError("unknown_reward_approval", f"Unknown reward approval: {approval_id}.", 404)
    return row


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
        raise AssetContractError("unknown_player", f"Unknown player_id: {player_id}.", 404)
    level = _to_int(player["level"])
    role_type = str(player["role_type"])
    max_mana = 6 + level if role_type == "sorceress" else 0
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
            player_id,
            role_type,
            level,
            _to_int(player["xp"]),
            _to_int(player["gold"]),
            player["stats_json"],
            max_mana,
            _iso(),
        ),
    )
    return _clean_row(player)


def _status_for_action(action: str) -> str:
    return {"approve": "approved", "correct": "corrected", "reject": "rejected"}[action]


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
            return _to_int(row["max_stat"]) or 7
    return 7


def _stat_to_raise(stats: dict[str, int], preferred_stat: str) -> str:
    if preferred_stat in stats and stats[preferred_stat] < 7:
        return preferred_stat
    for stat_name in CANONICAL_STATS:
        if stats.get(stat_name, 0) < 7:
            return stat_name
    for stat_name in sorted(stats):
        if stats[stat_name] < 7:
            return stat_name
    return sorted(stats)[0] if stats else DEFAULT_STAT_ID


def _player_stats(player: dict[str, Any]) -> dict[str, int]:
    raw = player.get("stats_json") or "{}"
    try:
        loaded = json.loads(str(raw))
    except json.JSONDecodeError:
        loaded = {}
    stats = {str(key): _to_int(value) for key, value in loaded.items()}
    for stat_id in CANONICAL_STATS:
        stats.setdefault(stat_id, 0)
    return stats


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _clean_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: object, fallback: Any) -> Any:
    try:
        if value in (None, ""):
            return fallback
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback


def _to_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")
