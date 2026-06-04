"""Deterministic offline PvE rule engine and server replay helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import re
import sqlite3
from typing import Any
from uuid import uuid4

from .asset_service import grant_asset_ownership, reward_asset_entries
from .runtime_schema import ensure_runtime_schema, log_event
from .stats import CANONICAL_STAT_SET, CANONICAL_STATS, DEFAULT_STAT_ID


PVE_RESULTS = {"success", "partial_success", "failure", "timeout"}
COOLDOWN_RESULTS = {"failure", "timeout"}
PARTIAL_SUCCESS_MARGIN = 2
VALID_UNLOCK_SOURCES = {"server_sync", "master_unlock_code", "act1_default"}
APP_GENERATED_ROLL_SOURCE = "app_generated"
MASTER_RECOVERED_ROLL_SOURCES = {"master_override", "paper_recovered"}
VALID_PVE_ROLL_SOURCES = {APP_GENERATED_ROLL_SOURCE, *MASTER_RECOVERED_ROLL_SOURCES}
VALID_MODIFIER_SOURCES = {
    "item",
    "items",
    "potion",
    "potions",
    "artifact",
    "artifacts",
    "magic",
    "system",
}
SERVER_MODIFIER_SOURCE_ALIASES = {"items": "item", "potions": "potion", "artifacts": "artifact"}
EFFECT_STAT_ALIASES = {
    "combat": "Сила",
    "strength": "Сила",
    "force": "Сила",
    "agility": "Ловкость",
    "dexterity": "Ловкость",
    "lore": "Разум",
    "reason": "Разум",
    "mind": "Разум",
    "alchemy": "Разум",
    "influence": "Харизма",
    "charisma": "Харизма",
    "magic": "Воля",
    "will": "Воля",
}
SCENE_HP_BY_TIER = {1: 6, 2: 10, 3: 14, 4: 18}
DEFAULT_ROUND_LIMIT = 5


@dataclass(frozen=True)
class PveValidationResult:
    status: str
    reason: str | None
    metadata: dict[str, Any]


class PveSideEffectConflictError(RuntimeError):
    """Raised when a side-effect conflict appears after validation."""


def build_pve_scene_card(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    qr_id: str,
    unlocked_act_ids: set[str] | None = None,
    unlock_source: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_runtime_schema(connection)
    current_time = now or datetime.now(UTC)
    qr = _fetch_required(connection, "qr_objects", "qr_id", qr_id)
    scenario = _fetch_required(connection, "pve_scenarios", "scenario_id", str(qr["scenario_id"]))
    mob = _fetch_required(connection, "mobs", "mob_id", str(scenario["combat_profile_id"]))
    reward = _fetch_optional(connection, "rewards", "reward_id", str(scenario["reward_id"]))
    act = _fetch_optional(connection, "acts", "act_id", str(qr["act_id"]))
    player = _runtime_player(connection, player_id)
    cooldown = active_pve_cooldown(connection, player_id=player_id, qr_id=qr_id, now=current_time)
    server_modifiers = _server_derived_modifiers(
        connection,
        player_id=player_id,
        qr=qr,
        scenario=scenario,
    )

    act_id = str(qr["act_id"])
    unlocked_ids = unlocked_act_ids or {"act1"}
    act_locked = _act_locked(act, act_id, unlocked_ids, unlock_source)
    tier = _to_int(scenario["tier"])
    level = _to_int(player.get("level"))
    armor_or_ward_bonus = 0
    player_scene_hp = max(7, 6 + level + armor_or_ward_bonus)

    return {
        "player_id": player_id,
        "qr_id": qr_id,
        "manual_code": qr["manual_code"],
        "qr_mode": qr["qr_mode"],
        "consumption_rule": qr["consumption_rule"],
        "physical_presence_required": _truthy(qr["physical_presence_required"]),
        "act_id": act_id,
        "act_locked": act_locked,
        "unlock_source": unlock_source,
        "cooldown": cooldown,
        "scenario": _clean_row(scenario),
        "mob": _clean_row(mob),
        "reward": _clean_row(reward) if reward is not None else None,
        "primary_stat": scenario["primary_stat"],
        "check_policy": scenario["check_policy"],
        "dc": _to_int(scenario["dc"]),
        "combat_dc": _to_int(mob["combat_dc"]),
        "scene_hp": _scene_hp(mob, tier),
        "scene_damage": _to_int(mob["scene_damage"]),
        "round_limit": _to_int(mob["round_limit"]) or DEFAULT_ROUND_LIMIT,
        "base_damage": _base_damage(connection),
        "timeout_outcome": scenario["timeout_outcome"] or _timeout_outcome(connection),
        "failure_cooldown_min": _failure_cooldown_minutes(connection),
        "player_scene_hp": player_scene_hp,
        "player_level": level,
        "player_stats": _player_stats(player),
        "server_modifiers": server_modifiers,
        "server_modifier_total": sum(int(item["value"]) for item in server_modifiers),
        "ordinary_scene_available": qr["qr_mode"] in {"repeatable_scene", "always_available_scene"},
        "role_load_profile": "5_witchers_4_field_sorceresses",
    }


def resolve_pve_scene(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    qr_id: str,
    roll: int,
    modifiers: list[dict[str, Any]] | None = None,
    result_override: str | None = None,
    unlock_source: str | None = None,
    check_id: str | None = None,
    roll_source: str = APP_GENERATED_ROLL_SOURCE,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(UTC)
    card = build_pve_scene_card(
        connection,
        player_id=player_id,
        qr_id=qr_id,
        unlock_source=unlock_source or "act1_default",
        now=current_time,
    )
    server_modifiers = _normalize_modifiers(card.get("server_modifiers", []))
    client_modifier_claims = _normalize_modifiers(modifiers or [])
    stat_name = str(card["primary_stat"])
    stat_value = int(card["player_stats"].get(stat_name, 0))
    modifier_total = sum(int(item["value"]) for item in server_modifiers)
    total = roll + stat_value + modifier_total
    dc = int(card["dc"])
    calculated_result = calculate_pve_outcome(total, dc)
    result = "timeout" if result_override == "timeout" else calculated_result

    cooldown_until = (
        (current_time + timedelta(minutes=int(card["failure_cooldown_min"]))).isoformat(timespec="seconds")
        if result in COOLDOWN_RESULTS
        else None
    )
    scene_hp = int(card["scene_hp"])
    player_scene_hp = int(card["player_scene_hp"])
    margin = max(0, total - dc)
    damage = scene_hp if result == "success" else max(0, int(card["base_damage"]) + (margin // 5))
    scene_hp_remaining = 0 if result == "success" else max(scene_hp - damage, 0)
    player_scene_hp_remaining = (
        max(0, player_scene_hp - int(card["scene_damage"]))
        if result in COOLDOWN_RESULTS
        else player_scene_hp
    )

    roll_check_id = check_id or f"check-{uuid4().hex}"
    roll_id = f"roll-{uuid4().hex}"
    roll_created_at = current_time.isoformat(timespec="seconds")
    roll_entry = {
        "roll_id": roll_id,
        "check_id": roll_check_id,
        "source": roll_source,
        "created_at": roll_created_at,
        "player_id": player_id,
        "qr_id": card["qr_id"],
        "scenario_id": card["scenario"]["scenario_id"],
        "die": "d20",
        "roll": roll,
        "roll_value": roll,
        "stat": stat_name,
        "stat_value": stat_value,
        "modifiers": server_modifiers,
        "server_modifier_total": modifier_total,
        "total": total,
        "dc": dc,
        "outcome": calculated_result,
        "rolled_at": roll_created_at,
    }
    reward = card["reward"] if isinstance(card["reward"], dict) else {}
    reward_id = str(reward.get("reward_id", card["scenario"].get("reward_id", "")))
    reward_approval_policy = str(reward.get("approval_policy", "auto"))
    reward_status = (
        "pending_master_approval"
        if result == "success" and reward_approval_policy == "pending_master_approval"
        else "auto"
        if result == "success" and reward_id
        else "none"
    )

    payload = {
        "scenario_id": card["scenario"]["scenario_id"],
        "qr_id": card["qr_id"],
        "check_id": roll_check_id,
        "act_id": card["act_id"],
        "unlock_source": unlock_source or "act1_default",
        "roll_source": roll_source,
        "roll": roll,
        "stat": stat_name,
        "stat_value": stat_value,
        "modifiers": server_modifiers,
        "server_modifiers": server_modifiers,
        "server_modifier_total": modifier_total,
        "total": total,
        "dc": dc,
        "combat_dc": card["combat_dc"],
        "rounds": [
            {
                "round": 1,
                "action": "attack/check",
                "roll": roll_entry,
                "damage": damage,
                "scene_hp_remaining": scene_hp_remaining,
                "player_scene_hp_remaining": player_scene_hp_remaining,
            }
        ],
        "roll_log": [roll_entry],
        "scene_hp": scene_hp,
        "scene_hp_remaining": scene_hp_remaining,
        "player_scene_hp": player_scene_hp,
        "player_scene_hp_remaining": player_scene_hp_remaining,
        "outcome": result,
        "result": result,
        "reward_id": reward_id,
        "reward_approval_policy": reward_approval_policy,
        "reward_status": reward_status,
        "cooldown_until": cooldown_until,
        "timeout_outcome": card["timeout_outcome"],
        "qr_mode": card["qr_mode"],
        "consumption_rule": card["consumption_rule"],
        "physical_presence_confirmed": True,
        "role_load_profile": card["role_load_profile"],
    }
    if client_modifier_claims and client_modifier_claims != server_modifiers:
        payload["client_modifier_claims"] = client_modifier_claims
    return payload


def validate_pve_completion(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    payload: dict[str, Any],
) -> PveValidationResult:
    metadata: dict[str, Any] = {"pve_runtime": "v1", "single_d20": True}
    qr_id = str(payload.get("qr_id", ""))
    scenario_id = str(payload.get("scenario_id", ""))
    if not qr_id or not scenario_id:
        return PveValidationResult("rejected", "missing pve qr_id or scenario_id", metadata)

    try:
        unlock_source = str(payload.get("unlock_source", "")) or None
        card = build_pve_scene_card(
            connection,
            player_id=player_id,
            qr_id=qr_id,
            unlock_source=unlock_source,
        )
    except LookupError as exc:
        return PveValidationResult("needs_master_review", str(exc), metadata)

    metadata.update(
        {
            "qr_id": qr_id,
            "scenario_id": scenario_id,
            "act_id": card["act_id"],
            "qr_mode": card["qr_mode"],
            "consumption_rule": card["consumption_rule"],
            "role_load_profile": card["role_load_profile"],
        }
    )
    metadata.update(_pve_replay_metadata(card, payload))
    if str(card["scenario"]["scenario_id"]) != scenario_id:
        return PveValidationResult("needs_master_review", f"qr scenario mismatch: {qr_id}", metadata)
    if bool(card["act_locked"]):
        return PveValidationResult(
            "needs_master_review",
            "future act requires server sync or master unlock code",
            metadata,
        )
    act_reason = _act_availability_reason(connection, card, unlock_source)
    if act_reason is not None:
        return PveValidationResult("needs_master_review", act_reason, metadata)

    result = str(payload.get("result", payload.get("outcome", "")))
    if result not in PVE_RESULTS:
        return PveValidationResult("rejected", f"unsupported pve result: {result}", metadata)
    metadata["result"] = result
    scenario_reward_id = str(card["scenario"].get("reward_id") or "").strip()
    payload_has_reward_id = "reward_id" in payload
    client_reward_id = str(payload.get("reward_id") or "").strip()
    metadata["scenario_reward_id"] = scenario_reward_id or None
    if payload_has_reward_id:
        metadata["client_reward_id"] = client_reward_id or None
    if result == "success":
        if not scenario_reward_id:
            metadata["reward_id"] = None
            metadata["reward_status"] = "none"
            return PveValidationResult(
                "needs_master_review",
                "pve scenario has no reward_id",
                metadata,
            )
        if payload_has_reward_id and client_reward_id != scenario_reward_id:
            metadata["reward_id"] = scenario_reward_id
            metadata["reward_status"] = "none"
            return PveValidationResult(
                "needs_master_review",
                f"pve reward_id mismatch for scenario {scenario_id}",
                metadata,
            )
        if not isinstance(card.get("reward"), dict):
            metadata["reward_id"] = scenario_reward_id
            metadata["reward_status"] = "none"
            return PveValidationResult(
                "needs_master_review",
                f"unknown scenario reward_id: {scenario_reward_id}",
                metadata,
            )
    metadata["reward_id"] = scenario_reward_id or None
    metadata["reward_status"] = _reward_status_for_payload(card, result, scenario_reward_id)

    if bool(card["physical_presence_required"]) and not _truthy(
        payload.get("physical_presence_confirmed")
    ):
        return PveValidationResult(
            "needs_master_review",
            "physical presence confirmation required for physical QR scene",
            metadata,
        )
    if card.get("cooldown") is not None:
        metadata["cooldown"] = card["cooldown"]
        return PveValidationResult("rejected", "pve cooldown active", metadata)
    if result == "success" and _is_unique_scene(card):
        consumed = _pve_consumed_object(connection, qr_id)
        if consumed is not None:
            metadata["consumed_by_event_id"] = consumed.get("source_event_id")
            return PveValidationResult(
                "needs_master_review",
                "unique QR object already consumed",
                metadata,
            )

    replay_reason = _replay_roll_contract(card, payload, result)
    if replay_reason is not None:
        return PveValidationResult("needs_master_review", replay_reason, metadata)
    return PveValidationResult("ok", None, metadata)


def apply_pve_completion_side_effects(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    payload: dict[str, Any],
    metadata: dict[str, Any],
    status: str,
    server_event_id: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_runtime_schema(connection)
    current_time = now or datetime.now(UTC)
    result = str(payload.get("result", payload.get("outcome", "")))
    qr_id = str(metadata.get("qr_id") or payload.get("qr_id"))
    scenario_id = str(metadata.get("scenario_id") or payload.get("scenario_id"))
    act_id = str(metadata.get("act_id") or payload.get("act_id"))
    reward_id = str(metadata.get("reward_id") or payload.get("reward_id") or "")
    reward_status = str(metadata.get("reward_status") or "none")
    cooldown_until = None

    if result in COOLDOWN_RESULTS:
        cooldown_until = (
            current_time + timedelta(minutes=_failure_cooldown_minutes(connection))
        ).isoformat(timespec="seconds")
        connection.execute(
            """
            INSERT INTO pve_cooldowns (
                player_id, qr_id, cooldown_until, reason, source_event_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(player_id, qr_id) DO UPDATE SET
                cooldown_until = excluded.cooldown_until,
                reason = excluded.reason,
                source_event_id = excluded.source_event_id,
                created_at = excluded.created_at
            """,
            (
                player_id,
                qr_id,
                cooldown_until,
                "pve_failure",
                server_event_id,
                current_time.isoformat(timespec="seconds"),
            ),
        )

    if result == "success" and _metadata_is_unique_scene(metadata):
        cursor = connection.execute(
            """
            INSERT INTO pve_consumed_objects (
                qr_id, scenario_id, act_id, player_id, source_event_id,
                consumed_at, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(qr_id) DO NOTHING
            """,
            (
                qr_id,
                scenario_id,
                act_id,
                player_id,
                server_event_id,
                current_time.isoformat(timespec="seconds"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
            ),
        )
        if cursor.rowcount == 0:
            raise PveSideEffectConflictError("unique QR object already consumed")

    connection.execute(
        """
        INSERT INTO pve_attempts (
            server_event_id, player_id, qr_id, scenario_id, act_id, result,
            outcome, roll_log_json, reward_id, reward_status, cooldown_until,
            payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            server_event_id,
            player_id,
            qr_id,
            scenario_id,
            act_id,
            result,
            str(payload.get("outcome", result)),
            json.dumps(payload.get("roll_log", []), ensure_ascii=False, sort_keys=True),
            reward_id,
            reward_status,
            cooldown_until or None,
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
            current_time.isoformat(timespec="seconds"),
        ),
    )

    reward_update: dict[str, Any] = {"status": "not_applied"}
    if status == "accepted" and result == "success" and reward_status == "auto" and reward_id:
        reward_update = _apply_auto_reward(
            connection,
            player_id=player_id,
            reward_id=reward_id,
            preferred_stat=str(payload.get("level_up_stat") or payload.get("stat") or ""),
            source_event_id=server_event_id,
            now=current_time,
        )

    applied = {
        "cooldown_until": cooldown_until or None,
        "reward_update": reward_update,
        "reward_status": reward_status,
    }
    log_event(
        connection,
        "pve_completion_applied",
        {
            "server_event_id": server_event_id,
            "player_id": player_id,
            "qr_id": qr_id,
            "scenario_id": scenario_id,
            "result": result,
            **applied,
        },
        source="event_sync",
        created_at=current_time,
    )
    return applied


def active_pve_cooldown(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    qr_id: str,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    ensure_runtime_schema(connection)
    current_time = now or datetime.now(UTC)
    row = connection.execute(
        """
        SELECT player_id, qr_id, cooldown_until, reason, source_event_id
        FROM pve_cooldowns
        WHERE player_id = ? AND qr_id = ? AND cooldown_until > ?
        """,
        (player_id, qr_id, current_time.isoformat(timespec="seconds")),
    ).fetchone()
    return _clean_row(row) if row is not None else None


def _act_availability_reason(
    connection: sqlite3.Connection,
    card: dict[str, Any],
    unlock_source: str | None,
) -> str | None:
    act_id = str(card["act_id"])
    if act_id == "act1":
        return None
    act = _fetch_optional(connection, "acts", "act_id", act_id)
    if act is None or not _truthy(act["unlock_required"]):
        return None
    if unlock_source == "server_sync":
        if _act_has_physical_announcement(connection, act_id):
            return None
        return "future act requires authoritative server sync after physical announcement"
    if unlock_source == "master_unlock_code":
        if _act_unlock_code_revealed(connection, act_id):
            return None
        return "master unlock code is not revealed for this act"
    return "future act requires server sync or master unlock code"


def _act_has_physical_announcement(connection: sqlite3.Connection, act_id: str) -> bool:
    if not _table_exists(connection, "act_history"):
        return False
    row = connection.execute(
        """
        SELECT physical_announcement_state
        FROM act_history
        WHERE act_id = ?
        """,
        (act_id,),
    ).fetchone()
    return row is not None and _is_announced(row["physical_announcement_state"])


def _act_unlock_code_revealed(connection: sqlite3.Connection, act_id: str) -> bool:
    if not _table_exists(connection, "act_history"):
        return False
    row = connection.execute(
        """
        SELECT physical_announcement_state, unlock_revealed_at
        FROM act_history
        WHERE act_id = ?
        """,
        (act_id,),
    ).fetchone()
    return (
        row is not None
        and _is_announced(row["physical_announcement_state"])
        and bool(row["unlock_revealed_at"])
    )


def _is_unique_scene(card: dict[str, Any]) -> bool:
    return str(card.get("qr_mode", "")) == "unique_object" or str(
        card.get("consumption_rule", "")
    ) == "consume_once"


def _metadata_is_unique_scene(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("qr_mode", "")) == "unique_object" or str(
        metadata.get("consumption_rule", "")
    ) == "consume_once"


def _pve_consumed_object(
    connection: sqlite3.Connection,
    qr_id: str,
) -> dict[str, Any] | None:
    ensure_runtime_schema(connection)
    row = connection.execute(
        """
        SELECT qr_id, player_id, source_event_id, consumed_at
        FROM pve_consumed_objects
        WHERE qr_id = ?
        """,
        (qr_id,),
    ).fetchone()
    return _clean_row(row) if row is not None else None


def _pve_replay_metadata(card: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    roll_log = payload.get("roll_log", [])
    roll_entry = roll_log[0] if isinstance(roll_log, list) and roll_log and isinstance(roll_log[0], dict) else {}
    roll = _to_int(payload.get("roll") if _field_present(payload, "roll") else roll_entry.get("roll"))
    if roll == 0 and _field_present(roll_entry, "value"):
        roll = _to_int(roll_entry["value"])
    stat_name = str(payload.get("stat") or roll_entry.get("stat") or card["primary_stat"])
    server_stat = str(card["primary_stat"])
    stat_value = int(card["player_stats"].get(server_stat, 0))
    server_modifiers = _normalize_modifiers(card.get("server_modifiers", []))
    modifier_total = sum(int(item["value"]) for item in server_modifiers)
    total = roll + stat_value + modifier_total if roll else None
    return {
        "roll": roll or None,
        "dc": int(card["dc"]),
        "claimed_stat": stat_name,
        "server_stat": server_stat,
        "server_stat_value": stat_value,
        "server_modifiers": server_modifiers,
        "server_modifier_total": modifier_total,
        "server_replay_total": total,
    }


def _replay_roll_contract(
    card: dict[str, Any],
    payload: dict[str, Any],
    result: str,
) -> str | None:
    roll_log = payload.get("roll_log", [])
    if not isinstance(roll_log, list) or len(roll_log) != 1 or not isinstance(roll_log[0], dict):
        return "pve completion must include exactly one replayable d20 roll_log entry"

    roll_entry = roll_log[0]
    if str(roll_entry.get("die", "d20")) != "d20":
        return "pve check must log exactly one d20 and no reroll"
    roll_source = str(
        roll_entry.get("source") or payload.get("roll_source") or payload.get("source") or ""
    )
    if roll_source not in VALID_PVE_ROLL_SOURCES:
        return "pve roll source must be app_generated or explicit master/paper recovery"
    if roll_source == APP_GENERATED_ROLL_SOURCE:
        if not str(roll_entry.get("roll_id") or payload.get("roll_id") or ""):
            return "app-generated pve roll must include roll_id and check_id"
        if not str(roll_entry.get("check_id") or payload.get("check_id") or ""):
            return "app-generated pve roll must include roll_id and check_id"
        if str(roll_entry.get("player_id") or payload.get("player_id") or "") not in {
            "",
            str(card["player_id"]),
        }:
            return "pve roll player_id does not match authenticated player"
        if str(roll_entry.get("qr_id") or payload.get("qr_id") or "") != str(card["qr_id"]):
            return "pve roll qr_id does not match scene"
        if str(roll_entry.get("scenario_id") or payload.get("scenario_id") or "") != str(
            card["scenario"]["scenario_id"]
        ):
            return "pve roll scenario_id does not match scene"
        if not str(roll_entry.get("created_at") or roll_entry.get("rolled_at") or ""):
            return "app-generated pve roll must include created_at"
    if not any(_field_present(source, "roll") for source in (payload, roll_entry)) and not _field_present(
        roll_entry,
        "value",
    ):
        return "pve roll log must include d20 roll value"

    roll = _to_int(payload.get("roll") if _field_present(payload, "roll") else roll_entry.get("roll"))
    if roll == 0 and _field_present(roll_entry, "value"):
        roll = _to_int(roll_entry["value"])
    if roll < 1 or roll > 20:
        return "pve roll must be exactly one d20 in the 1-20 range"
    if _field_present(payload, "roll_value") and _to_int(payload["roll_value"]) != roll:
        return "pve roll_value does not match d20 roll"
    if _field_present(roll_entry, "roll_value") and _to_int(roll_entry["roll_value"]) != roll:
        return "pve roll_value does not match d20 roll"

    stat_name = str(payload.get("stat") or roll_entry.get("stat") or card["primary_stat"])
    if stat_name != str(card["primary_stat"]):
        return "pve stat does not match scenario primary_stat"
    stat_value = int(card["player_stats"].get(stat_name, 0))
    if _field_present(payload, "modifiers"):
        logged_modifiers = _normalize_modifiers(payload.get("modifiers", []))
    elif "modifiers" in roll_entry:
        logged_modifiers = _normalize_modifiers(roll_entry.get("modifiers", []))
    else:
        return "pve modifiers must be logged even when empty"
    server_modifiers = _normalize_modifiers(card.get("server_modifiers", []))
    if logged_modifiers != server_modifiers:
        return "pve modifiers do not match server-derived modifiers"
    modifier_total = sum(int(item["value"]) for item in server_modifiers)
    total = roll + stat_value + modifier_total
    expected_dc = int(card["dc"])
    expected_result = calculate_pve_outcome(total, expected_dc)

    if _field_present(payload, "stat_value") and _to_int(payload["stat_value"]) != stat_value:
        return "pve stat_value does not match server player state"
    if _field_present(roll_entry, "stat_value") and _to_int(roll_entry["stat_value"]) != stat_value:
        return "pve stat_value does not match server player state"
    if _field_present(payload, "total") and _to_int(payload["total"]) != total:
        return "pve total does not match single_d20 replay"
    if _field_present(roll_entry, "total") and _to_int(roll_entry["total"]) != total:
        return "pve total does not match single_d20 replay"
    if _field_present(payload, "server_modifier_total") and _to_int(payload["server_modifier_total"]) != modifier_total:
        return "pve modifier total does not match server-derived modifiers"
    if _field_present(roll_entry, "server_modifier_total") and _to_int(roll_entry["server_modifier_total"]) != modifier_total:
        return "pve modifier total does not match server-derived modifiers"
    if _field_present(payload, "dc") and _to_int(payload["dc"]) != expected_dc:
        return "pve dc does not match scenario"
    if _field_present(roll_entry, "dc") and _to_int(roll_entry["dc"]) != expected_dc:
        return "pve dc does not match scenario"
    if result in {"success", "partial_success", "failure"} and result != expected_result:
        return "pve result does not match single_d20 replay"
    return None


def calculate_pve_outcome(total: int, dc: int) -> str:
    if total >= dc:
        return "success"
    if total >= dc - PARTIAL_SUCCESS_MARGIN:
        return "partial_success"
    return "failure"


def _roll_log_has_contract(roll_log: object) -> bool:
    return (
        isinstance(roll_log, list)
        and bool(roll_log)
        and isinstance(roll_log[0], dict)
        and any(key in roll_log[0] for key in ("roll", "value", "total", "modifiers", "dc"))
    )


def _reward_status_for_payload(
    card: dict[str, Any],
    result: str,
    reward_id: object,
) -> str:
    if result != "success" or not reward_id:
        return "none"
    reward = card.get("reward")
    approval_policy = str(reward.get("approval_policy", "auto")) if isinstance(reward, dict) else "auto"
    return "pending_master_approval" if approval_policy == "pending_master_approval" else "auto"


def _apply_auto_reward(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    reward_id: str,
    preferred_stat: str,
    source_event_id: int,
    now: datetime,
) -> dict[str, Any]:
    player = _runtime_player(connection, player_id)
    reward = _fetch_optional(connection, "rewards", "reward_id", reward_id)
    if reward is None:
        return {"status": "skipped", "reason": "unknown_reward", "reward_id": reward_id}

    xp_before = _to_int(player.get("xp"))
    level_before = _to_int(player.get("level"))
    gold_before = _to_int(player.get("gold"))
    xp_gain = _to_int(reward["xp"])
    gold_gain = _to_int(reward["gold"])
    xp_after = xp_before + xp_gain
    level_after = _level_for_xp(connection, xp_after)
    level_after = max(level_before, level_after)
    stats = _player_stats(player)
    stat_gains: list[dict[str, Any]] = []
    max_stat = _max_stat(connection)
    for _ in range(max(0, level_after - level_before)):
        stat_name = _stat_to_raise(stats, preferred_stat)
        before = int(stats.get(stat_name, 0))
        after = min(max_stat, before + 1)
        stats[stat_name] = after
        stat_gains.append({"stat": stat_name, "before": before, "after": after})

    connection.execute(
        """
        UPDATE player_runtime_state
        SET xp = ?, level = ?, gold = ?, stats_json = ?, updated_at = ?
        WHERE player_id = ?
        """,
        (
            xp_after,
            level_after,
            gold_before + gold_gain,
            json.dumps(stats, ensure_ascii=False, sort_keys=True),
            now.isoformat(timespec="seconds"),
            player_id,
        ),
    )
    granted_assets = [
        grant_asset_ownership(
            connection,
            owner_player_id=player_id,
            asset_type=str(asset["asset_type"]),
            asset_id=str(asset["asset_id"]),
            quantity=_to_int(asset["quantity"]) or 1,
            source="reward_auto",
            source_ref_id=str(source_event_id),
            now=now,
        )
        for asset in reward_asset_entries(connection, reward_id)
    ]
    return {
        "status": "applied",
        "reward_id": reward_id,
        "xp_gain": xp_gain,
        "gold_gain": gold_gain,
        "xp_before": xp_before,
        "xp_after": xp_after,
        "level_before": level_before,
        "level_after": level_after,
        "stat_gains": stat_gains,
        "granted_assets": granted_assets,
        "source_event_id": source_event_id,
    }


def _runtime_player(connection: sqlite3.Connection, player_id: str) -> dict[str, Any]:
    ensure_runtime_schema(connection)
    row = connection.execute(
        """
        SELECT player_id, role_type, level, xp, gold, stats_json
        FROM player_runtime_state
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if row is not None:
        return _clean_row(row)

    player = _fetch_required(connection, "players", "player_id", player_id)
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
    }


def _level_for_xp(connection: sqlite3.Connection, xp: int) -> int:
    thresholds = [0, 10, 25, 45, 70, 100, 135, 175, 220, 270]
    if _table_exists(connection, "xp_rules"):
        row = connection.execute(
            """
            SELECT level_thresholds
            FROM xp_rules
            ORDER BY _row_number
            LIMIT 1
            """
        ).fetchone()
        if row is not None and row["level_thresholds"]:
            thresholds = [_to_int(part) for part in str(row["level_thresholds"]).split(";") if part]
    level = 1
    for index, threshold in enumerate(thresholds, start=1):
        if xp >= threshold:
            level = index
    return level


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
    return preferred_stat or (sorted(stats)[0] if stats else DEFAULT_STAT_ID)


def _normalize_modifiers(modifiers: object) -> list[dict[str, Any]]:
    if not isinstance(modifiers, list):
        return []
    result: list[dict[str, Any]] = []
    for index, modifier in enumerate(modifiers):
        if not isinstance(modifier, dict):
            continue
        source = str(modifier.get("source") or modifier.get("type") or "system")
        source = SERVER_MODIFIER_SOURCE_ALIASES.get(source, source)
        value = _to_int(modifier.get("value"))
        result.append(
            {
                "source": source if source in VALID_MODIFIER_SOURCES else "system",
                "label": str(modifier.get("label") or source or f"modifier_{index + 1}"),
                "value": value,
            }
        )
    return result


def _server_derived_modifiers(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    qr: sqlite3.Row,
    scenario: sqlite3.Row,
) -> list[dict[str, Any]]:
    context = {
        "player_id": player_id,
        "qr_id": str(qr["qr_id"]),
        "scenario_id": str(scenario["scenario_id"]),
        "scene_type": str(scenario["scene_type"]),
        "primary_stat": str(scenario["primary_stat"]),
    }
    player_stats = _player_stats(_runtime_player(connection, player_id))
    modifiers: list[dict[str, Any]] = []
    modifiers.extend(_owned_item_modifiers(connection, context, player_stats))
    modifiers.extend(_owned_artifact_modifiers(connection, context))
    modifiers.extend(_used_potion_modifiers(connection, context))
    modifiers.extend(_active_magic_modifiers(connection, context))
    return [modifier for modifier in modifiers if int(modifier["value"]) != 0]


def _owned_item_modifiers(
    connection: sqlite3.Connection,
    context: dict[str, str],
    player_stats: dict[str, int],
) -> list[dict[str, Any]]:
    if not (_table_exists(connection, "asset_ownership") and _table_exists(connection, "items")):
        return []
    rows = connection.execute(
        """
        SELECT own.asset_id, own.quantity, item.stat_requirement_json, item.effect_json
        FROM asset_ownership own
        JOIN items item ON item.item_id = own.asset_id
        WHERE own.owner_player_id = ?
          AND own.asset_type = 'item'
          AND own.status = 'active'
          AND own.quantity > 0
        ORDER BY own.asset_id
        """,
        (context["player_id"],),
    ).fetchall()
    modifiers: list[dict[str, Any]] = []
    for row in rows:
        requirements = _json_loads(str(row["stat_requirement_json"]), {})
        if not _stat_requirements_met(player_stats, requirements):
            continue
        value = _modifier_value_from_effect(_json_loads(str(row["effect_json"]), {}), context)
        if value:
            modifiers.append({"source": "item", "label": str(row["asset_id"]), "value": value})
    return modifiers


def _owned_artifact_modifiers(
    connection: sqlite3.Connection,
    context: dict[str, str],
) -> list[dict[str, Any]]:
    if not (_table_exists(connection, "asset_ownership") and _table_exists(connection, "artifacts")):
        return []
    rows = connection.execute(
        """
        SELECT own.asset_id, artifact.power_budget
        FROM asset_ownership own
        JOIN artifacts artifact ON artifact.artifact_id = own.asset_id
        WHERE own.owner_player_id = ?
          AND own.asset_type = 'artifact'
          AND own.status = 'active'
          AND own.quantity > 0
        ORDER BY own.asset_id
        """,
        (context["player_id"],),
    ).fetchall()
    return [
        {
            "source": "artifact",
            "label": f"{row['asset_id']} power budget",
            "value": min(4, _to_int(row["power_budget"])),
        }
        for row in rows
        if _to_int(row["power_budget"]) > 0
    ]


def _used_potion_modifiers(
    connection: sqlite3.Connection,
    context: dict[str, str],
) -> list[dict[str, Any]]:
    if not (_table_exists(connection, "potion_scene_usage") and _table_exists(connection, "potions")):
        return []
    rows = connection.execute(
        """
        SELECT usage.potion_id, potion.effect_json
        FROM potion_scene_usage usage
        JOIN potions potion ON potion.potion_id = usage.potion_id
        WHERE usage.player_id = ?
          AND usage.scene_id IN (?, ?)
        ORDER BY usage.created_at, usage.potion_id
        """,
        (context["player_id"], context["qr_id"], context["scenario_id"]),
    ).fetchall()
    modifiers: list[dict[str, Any]] = []
    for row in rows:
        value = _modifier_value_from_effect(_json_loads(str(row["effect_json"]), {}), context)
        if value:
            modifiers.append({"source": "potion", "label": str(row["potion_id"]), "value": value})
    return modifiers


def _active_magic_modifiers(
    connection: sqlite3.Connection,
    context: dict[str, str],
) -> list[dict[str, Any]]:
    if not _table_exists(connection, "magic_effects"):
        return []
    rows = connection.execute(
        """
        SELECT spell_id, target_type, target_id, effect_json
        FROM magic_effects
        WHERE status IN ('active', 'accepted', 'approved')
          AND (
            (target_type = 'player' AND target_id = ?)
            OR (target_type IN ('qr', 'scene') AND target_id = ?)
            OR (target_type IN ('scenario', 'scene') AND target_id = ?)
          )
        ORDER BY created_at, effect_id
        """,
        (context["player_id"], context["qr_id"], context["scenario_id"]),
    ).fetchall()
    modifiers: list[dict[str, Any]] = []
    for row in rows:
        value = _modifier_value_from_effect(_json_loads(str(row["effect_json"]), {}), context)
        if value:
            modifiers.append({"source": "magic", "label": str(row["spell_id"]), "value": value})
    return modifiers


def _modifier_value_from_effect(effect: dict[str, Any], context: dict[str, str]) -> int:
    if not isinstance(effect, dict):
        return 0
    scene_types = effect.get("scene_types") or effect.get("scene_type")
    if isinstance(scene_types, str):
        scene_type_set = {part.strip() for part in scene_types.replace(",", ";").split(";") if part.strip()}
    elif isinstance(scene_types, list):
        scene_type_set = {str(part).strip() for part in scene_types if str(part).strip()}
    else:
        scene_type_set = set()
    if scene_type_set and context["scene_type"] not in scene_type_set:
        return 0

    effect_stat = str(effect.get("stat") or effect.get("modifier_stat") or "").strip()
    if effect_stat:
        effect_stat = EFFECT_STAT_ALIASES.get(effect_stat, effect_stat)
        if effect_stat != context["primary_stat"]:
            return 0

    for key in ("modifier", "modifier_value", "value"):
        if key in effect:
            return _to_int(effect[key])

    effect_name = str(effect.get("effect") or "")
    generic = re.fullmatch(r"(?:modifier|bonus)_(plus|minus)_(\d+)", effect_name)
    if generic is not None:
        sign = 1 if generic.group(1) == "plus" else -1
        return sign * int(generic.group(2))

    next_check = re.fullmatch(r"next_check_(plus|minus)_(\d+)", effect_name)
    if next_check is not None:
        sign = 1 if next_check.group(1) == "plus" else -1
        return sign * int(next_check.group(2))

    stat_specific = re.fullmatch(r"([A-Za-z_]+)_modifier_(plus|minus)_(\d+)", effect_name)
    if stat_specific is None:
        return 0
    stat_id = EFFECT_STAT_ALIASES.get(stat_specific.group(1), stat_specific.group(1))
    if stat_id not in CANONICAL_STAT_SET or stat_id != context["primary_stat"]:
        return 0
    sign = 1 if stat_specific.group(2) == "plus" else -1
    return sign * int(stat_specific.group(3))


def _stat_requirements_met(stats: dict[str, int], requirements: dict[str, Any]) -> bool:
    if not isinstance(requirements, dict):
        return False
    for stat_id, required in requirements.items():
        if str(stat_id) not in CANONICAL_STAT_SET:
            return False
        if int(stats.get(str(stat_id), 0)) < _to_int(required):
            return False
    return True


def _base_damage(connection: sqlite3.Connection) -> int:
    row = _first_row(connection, "pve_combat_rules")
    return _to_int(row["base_damage"]) if row is not None else 1


def _timeout_outcome(connection: sqlite3.Connection) -> str:
    row = _first_row(connection, "pve_combat_rules")
    return str(row["timeout_outcome"]) if row is not None else "fail_and_cooldown"


def _failure_cooldown_minutes(connection: sqlite3.Connection) -> int:
    row = _first_row(connection, "pve_combat_rules")
    return _to_int(row["failure_cooldown_min"]) if row is not None else 30


def _scene_hp(mob: sqlite3.Row, tier: int) -> int:
    return _to_int(mob["scene_hp"]) or SCENE_HP_BY_TIER.get(tier, 6)


def _act_locked(
    act: sqlite3.Row | None,
    act_id: str,
    unlocked_act_ids: set[str],
    unlock_source: str | None,
) -> bool:
    if act_id in unlocked_act_ids or act_id == "act1":
        return False
    if unlock_source in VALID_UNLOCK_SOURCES:
        return False
    if act is None:
        return act_id != "act1"
    return _truthy(act["unlock_required"])


def _fetch_required(
    connection: sqlite3.Connection,
    table_name: str,
    id_column: str,
    row_id: str,
) -> sqlite3.Row:
    row = _fetch_optional(connection, table_name, id_column, row_id)
    if row is None:
        raise LookupError(f"unknown {table_name}.{id_column}: {row_id}")
    return row


def _fetch_optional(
    connection: sqlite3.Connection,
    table_name: str,
    id_column: str,
    row_id: str,
) -> sqlite3.Row | None:
    if not _table_exists(connection, table_name):
        return None
    return connection.execute(
        f'SELECT * FROM "{table_name}" WHERE "{id_column}" = ? LIMIT 1',
        (row_id,),
    ).fetchone()


def _first_row(connection: sqlite3.Connection, table_name: str) -> sqlite3.Row | None:
    if not _table_exists(connection, table_name):
        return None
    return connection.execute(f'SELECT * FROM "{table_name}" ORDER BY _row_number LIMIT 1').fetchone()


def _player_stats(player: dict[str, Any]) -> dict[str, int]:
    raw = player.get("stats_json", "{}")
    if isinstance(raw, dict):
        parsed = raw
    else:
        try:
            parsed = json.loads(str(raw or "{}"))
        except json.JSONDecodeError:
            parsed = {}
    stats = {str(key): _to_int(value) for key, value in parsed.items()}
    for stat_id in CANONICAL_STAT_SET:
        stats.setdefault(stat_id, 0)
    return stats


def _json_loads(value: str, default: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return default
    return parsed if isinstance(parsed, dict) else default


def _clean_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        key: row[key]
        for key in row.keys()
        if key not in {"_import_run_id", "_row_number"}
    }


def _field_present(payload: dict[str, Any], field: str) -> bool:
    return field in payload and payload[field] not in (None, "")


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


def _is_announced(value: object) -> bool:
    return str(value or "").strip().lower() in {
        "announced",
        "completed",
        "done",
        "physical_announced",
    }


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def _to_int(value: object) -> int:
    if value is None or str(value) == "":
        return 0
    return int(value)
