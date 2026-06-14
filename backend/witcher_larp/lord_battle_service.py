"""Deterministic 5x6 lord battle runtime."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
import json
import sqlite3
from typing import Any
from uuid import uuid4

from .lord_runtime import active_pending_lord_move, ensure_lord_runtime_state
from .lord_runtime import raid_defense_penalty_for_territory
from .runtime_schema import ensure_runtime_schema, log_event


BOARD_WIDTH = 5
BOARD_HEIGHT = 6
DEPLOYMENT_CAP = 5
DEPLOYMENT_SECONDS = 60
NEUTRAL_DEFENSE_COUNT_BY_TIER = {
    1: 3,
    2: 4,
    3: 6,
    4: 8,
}
HERO_HP_BASE = 30
HERO_HP_POWER_DIVISOR = 10
HERO_HP_MIN = 35
HERO_HP_MAX = 70
UNIT_CLASSES = {
    "infantry",
    "guard",
    "ranged",
    "cavalry",
    "heavy_siege",
    "specialist",
}
UNIT_CLASS_ATTACK_BONUS = {
    "infantry": 0,
    "guard": 0,
    "ranged": 1,
    "cavalry": 2,
    "heavy_siege": 3,
    "specialist": 1,
}
UNIT_CLASS_DEFENSE_BONUS = {
    "infantry": 0,
    "guard": 0,
    "ranged": 0,
    "cavalry": 1,
    "heavy_siege": 1,
    "specialist": 1,
}
UNIT_CLASS_POWER_BONUS = {
    "infantry": 0,
    "guard": 4,
    "ranged": 4,
    "cavalry": 10,
    "heavy_siege": 16,
    "specialist": 8,
}
HERO_ATTACK_MULTIPLIER = {
    "infantry": 1,
    "guard": 1,
    "ranged": 1,
    "cavalry": 1,
    "heavy_siege": 2,
    "specialist": 1,
}
ARCING_ATTACK_CLASSES = {"ranged", "heavy_siege"}
UNIT_BATTLE_RANGES = {
    "tier": (1, 4),
    "attack": (1, 20),
    "defense": (1, 20),
    "hp": (1, 50),
    "initiative": (1, 20),
    "move_range": (1, BOARD_HEIGHT - 1),
    "attack_range": (1, BOARD_HEIGHT - 1),
}
FINAL_BATTLE_STATES = {"finished", "needs_master_review"}
BATTLE_READY_CLAIM_STATUSES = {"in_battle", "contested", "contested_pending_tick"}
GARRISON_PENDING_CLAIM_STATUSES = {"awaiting_garrison", "capture_pending_garrison"}


class LordBattleError(ValueError):
    """Raised when a lord battle action violates the runtime contract."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def ensure_lord_battle_runtime_state(connection: sqlite3.Connection) -> None:
    ensure_runtime_schema(connection)
    ensure_lord_runtime_state(connection)


def create_lord_battle(
    connection: sqlite3.Connection,
    *,
    attacker_domain_id: str | None = None,
    attacker_lord_id: str | None = None,
    defender_domain_id: str | None = None,
    defender_lord_id: str | None = None,
    territory_id: str | None = None,
    claim_id: str | None = None,
    battle_id: str | None = None,
    seed: str | None = None,
    actor_domain_id: str | None = None,
    actor_role_type: str | None = None,
    source: str = "lord_battle_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_lord_battle_runtime_state(connection)
    if (
        actor_role_type == "lord"
        and actor_domain_id
        and active_pending_lord_move(connection, actor_domain_id) is not None
    ):
        raise LordBattleError(
            "pending_move_active",
            "Active army is moving and cannot start a battle until arrival.",
        )
    current_time = now or datetime.now(UTC)
    battle_id = battle_id or f"lord_battle_{uuid4().hex}"
    existing = _fetch_battle(connection, battle_id)
    if existing is not None:
        _assert_create_actor_allowed(
            str(existing["attacker_domain_id"]),
            actor_domain_id,
            actor_role_type,
            defender_domain_id=_optional(existing["defender_domain_id"]),
            allow_defender_actor=True,
        )
        payload = _battle_payload(
            connection,
            existing,
            viewer_domain_id=actor_domain_id,
            viewer_role_type=actor_role_type,
        )
        payload["duplicate"] = True
        return payload

    claim = _claim_for_create(connection, claim_id, territory_id)
    if claim is not None:
        claim_status = str(claim["status"] or "")
        if claim_status not in BATTLE_READY_CLAIM_STATUSES:
            raise LordBattleError(
                "claim_awaiting_garrison"
                if claim_status in GARRISON_PENDING_CLAIM_STATUSES
                else "claim_not_battle_ready",
                "Territory claim is already resolved; place a garrison instead of starting another battle.",
                409,
            )
        claim_id = str(claim["claim_id"])
        territory_id = str(claim["territory_id"])
        attacker_domain_id = attacker_domain_id or str(claim["claimant_domain_id"])
        defender_domain_id = defender_domain_id or _optional(claim["defender_domain_id"])

    attacker_domain_id = _resolve_domain_id(
        connection,
        domain_id=attacker_domain_id,
        lord_id=attacker_lord_id,
        label="attacker",
    )
    if defender_domain_id or defender_lord_id:
        defender_domain_id = _resolve_domain_id(
            connection,
            domain_id=defender_domain_id,
            lord_id=defender_lord_id,
            label="defender",
        )

    territory = _territory_context(connection, territory_id)
    if territory is not None:
        territory_id = str(territory["territory_id"])
        owner_domain_id = _optional(territory["runtime_owner_domain_id"])
        if defender_domain_id is None and owner_domain_id != attacker_domain_id:
            defender_domain_id = owner_domain_id
        _assert_attacker_at_territory(connection, attacker_domain_id, territory_id)

    if defender_domain_id == attacker_domain_id:
        raise LordBattleError("same_domain", "Lord battle requires two different sides.")
    _assert_create_actor_allowed(
        attacker_domain_id,
        actor_domain_id,
        actor_role_type,
        defender_domain_id=defender_domain_id,
        allow_defender_actor=claim is not None,
    )

    battle_type = "neutral" if defender_domain_id is None else "lord_vs_lord"
    rule = _battle_rule(connection)
    seed = seed or _stable_seed(
        battle_id,
        attacker_domain_id,
        defender_domain_id or "neutral",
        territory_id or "no_territory",
    )
    attacker_sources = _active_army_sources(connection, attacker_domain_id)
    if not attacker_sources:
        raise LordBattleError(
            "missing_attacker_army",
            "Attacker needs at least one active army unit card.",
        )

    if battle_type == "neutral":
        defender_sources = _neutral_sources(connection, territory)
        defender_control = "neutral_ai"
        target_seconds = 10 * 60
        master_takeover_enabled = True
    else:
        defender_sources = _defender_sources(connection, str(defender_domain_id), territory_id)
        defender_control = "lord"
        target_seconds = 20 * 60
        master_takeover_enabled = False
    if not defender_sources:
        raise LordBattleError(
            "missing_defender_army",
            "Defender needs a garrison, active army, or neutral defense profile.",
        )

    board, deployment, hero_hp = _build_initial_board(
        attacker_sources,
        defender_sources,
        seed=seed,
        rule=rule,
    )
    deployment["started_at"] = _iso(current_time)
    deployment["timer_started_at"] = None
    deployment["deadline_at"] = _iso(current_time + timedelta(seconds=DEPLOYMENT_SECONDS))
    deployment["ready"] = {
        "attacker": False,
        "defender": battle_type == "neutral",
    }
    deployment["phase"] = "deployment"
    if battle_type == "neutral":
        _auto_deploy_side(board, deployment, "defender")
        hero_hp = _hero_hp_for_stacks(board["stacks"])
    initiative: list[str] = []
    active_stack_id = None
    active_side = None
    timeout_at = current_time + timedelta(seconds=DEPLOYMENT_SECONDS)

    connection.execute(
        """
        INSERT INTO lord_battles (
            battle_id, battle_type, territory_id, claim_id, attacker_domain_id,
            defender_domain_id, defender_control, status, seed, round_number,
            active_side, active_stack_id, turn_started_at, timeout_at,
            timeout_counts_json, board_json, hero_hp_json, deployment_json,
            initiative_json, burned_cards_json, result_json, created_at, updated_at,
            target_duration_seconds, auto_resolve_after_seconds, master_takeover_enabled
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, 'deployment', ?, 1, ?, ?, ?, ?, '{}', ?, ?, ?, ?,
            '[]', '{}', ?, ?, ?, ?, ?
        )
        """,
        (
            battle_id,
            battle_type,
            territory_id,
            claim_id,
            attacker_domain_id,
            defender_domain_id,
            defender_control,
            seed,
            active_side,
            active_stack_id,
            _iso(current_time),
            _iso(timeout_at),
            _json_dumps(board),
            _json_dumps(hero_hp),
            _json_dumps(deployment),
            _json_dumps(initiative),
            _iso(current_time),
            _iso(current_time),
            target_seconds,
            target_seconds + 5 * 60,
            1 if master_takeover_enabled else 0,
        ),
    )
    _append_log(
        connection,
        battle_id,
        round_number=1,
        actor_side=None,
        entry_type="lord_battle_started",
        payload={
            "battle_type": battle_type,
            "territory_id": territory_id,
            "claim_id": claim_id,
            "attacker_domain_id": attacker_domain_id,
            "defender_domain_id": defender_domain_id,
            "defender_control": defender_control,
            "seed": seed,
            "target_duration_seconds": target_seconds,
        },
        now=current_time,
    )
    _append_log(
        connection,
        battle_id,
        round_number=1,
        actor_side=None,
        entry_type="deployment_started",
        payload={
            "deployment_hand": deployment["hand"],
            "deployed": deployment["deployed"],
            "deadline_at": deployment["deadline_at"],
            "hp_formula_inputs": hero_hp["formula_inputs"],
        },
        now=current_time,
    )
    log_event(
        connection,
        "lord_battle_started",
        {
            "battle_id": battle_id,
            "battle_type": battle_type,
            "territory_id": territory_id,
            "claim_id": claim_id,
            "attacker_domain_id": attacker_domain_id,
            "defender_domain_id": defender_domain_id,
            "defender_control": defender_control,
            "seed": seed,
        },
        source=source,
        created_at=current_time,
    )
    return _battle_payload(
        connection,
        _fetch_battle_required(connection, battle_id),
        viewer_domain_id=actor_domain_id,
        viewer_role_type=actor_role_type,
    )


def get_lord_battle(
    connection: sqlite3.Connection,
    battle_id: str,
    *,
    viewer_domain_id: str | None = None,
    viewer_role_type: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_lord_battle_runtime_state(connection)
    row = _fetch_battle_required(connection, battle_id)
    state = _state_from_row(row)
    current_time = now or datetime.now(UTC)
    state_changed = _start_deployment_timer_for_viewer(
        state,
        current_time,
        viewer_domain_id=viewer_domain_id,
        viewer_role_type=viewer_role_type,
    )
    state_changed = (
        _advance_due_state(
            connection,
            state,
            current_time,
            source="lord_battle_get",
        )
        or state_changed
    )
    if state_changed:
        _save_state(connection, state, current_time)
    payload = _state_payload(
        connection,
        state,
        viewer_domain_id=viewer_domain_id,
        viewer_role_type=viewer_role_type,
    )
    payload.update(_lord_battle_queue_annotations(connection).get(str(state["battle_id"]), {}))
    return payload


def list_lord_battles(
    connection: sqlite3.Connection,
    *,
    domain_id: str | None = None,
    viewer_domain_id: str | None = None,
    viewer_role_type: str | None = None,
) -> dict[str, Any]:
    ensure_lord_battle_runtime_state(connection)
    params: tuple[object, ...] = ()
    where = ""
    if domain_id:
        where = "WHERE attacker_domain_id = ? OR defender_domain_id = ?"
        params = (domain_id, domain_id)
    rows = connection.execute(
        f"""
        SELECT *
        FROM lord_battles
        {where}
        ORDER BY created_at DESC, battle_id
        """,
        params,
    ).fetchall()
    queue_annotations = _lord_battle_queue_annotations(connection)
    return {
        "items": [
            {
                **_battle_payload(
                    connection,
                    row,
                    include_log=False,
                    include_queue=False,
                    viewer_domain_id=viewer_domain_id,
                    viewer_role_type=viewer_role_type,
                ),
                **queue_annotations.get(str(row["battle_id"]), {}),
            }
            for row in rows
        ]
    }


def _lord_battle_queue_annotations(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT battle_id, attacker_domain_id, defender_domain_id, status, created_at
        FROM lord_battles
        WHERE status NOT IN ('finished', 'needs_master_review', 'cancelled', 'closed', 'resolved')
        ORDER BY created_at ASC, battle_id ASC
        """
    ).fetchall()
    first_battle_by_domain: dict[str, str] = {}
    queue_counts_by_domain: dict[str, int] = {}
    annotations: dict[str, dict[str, Any]] = {}
    for row in rows:
        battle_id = str(row["battle_id"])
        participants = [
            domain_id
            for domain_id in (
                _optional(row["attacker_domain_id"]),
                _optional(row["defender_domain_id"]),
            )
            if domain_id
        ]
        blocking_battle_ids = sorted(
            {
                first_battle_by_domain[domain_id]
                for domain_id in participants
                if domain_id in first_battle_by_domain
            }
        )
        previous_counts = [queue_counts_by_domain.get(domain_id, 0) for domain_id in participants]
        annotations[battle_id] = {
            "queue_state": "waiting" if blocking_battle_ids else "ready",
            "queue_position": (max(previous_counts) if previous_counts else 0) + 1,
            "blocking_battle_ids": blocking_battle_ids,
        }
        for domain_id in participants:
            first_battle_by_domain.setdefault(domain_id, battle_id)
            queue_counts_by_domain[domain_id] = queue_counts_by_domain.get(domain_id, 0) + 1
    return annotations


def _assert_lord_battle_queue_ready(
    connection: sqlite3.Connection, state: dict[str, Any], actor_role_type: str | None
) -> None:
    if actor_role_type == "npc_master" or state["status"] in FINAL_BATTLE_STATES:
        return
    annotation = _lord_battle_queue_annotations(connection).get(str(state["battle_id"]))
    if annotation and annotation.get("queue_state") == "waiting":
        raise LordBattleError(
            "battle_waiting_for_previous",
            "This battle waits for an earlier lord battle to finish.",
            409,
        )


def record_lord_battle_action(
    connection: sqlite3.Connection,
    battle_id: str,
    *,
    action_type: str,
    actor_side: str,
    action_id: str | None = None,
    actor_domain_id: str | None = None,
    actor_role_type: str | None = None,
    payload: dict[str, Any] | None = None,
    source: str = "lord_battle_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_lord_battle_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    action_id = action_id or f"battle_action_{uuid4().hex}"
    row = _fetch_battle_required(connection, battle_id)
    state = _state_from_row(row)
    payload = dict(payload or {})
    action_type = action_type.strip().lower()
    actor_side = _side_name(actor_side)
    _assert_actor_allowed(state, actor_side, actor_domain_id, actor_role_type)
    _assert_lord_battle_queue_ready(connection, state, actor_role_type)
    _start_deployment_timer_for_actor(
        state,
        current_time,
        actor_side=actor_side,
        actor_role_type=actor_role_type,
    )
    existing_action = connection.execute(
        """
        SELECT result_json
        FROM lord_battle_actions
        WHERE battle_id = ? AND action_id = ?
        """,
        (battle_id, action_id),
    ).fetchone()
    if existing_action is not None:
        result = _json_loads(str(existing_action["result_json"]), {})
        result["duplicate"] = True
        return result

    if state["status"] == "deployment" and _deployment_timer_due(state, current_time):
        _finalize_deployment(
            connection,
            state,
            current_time,
            source=source,
            reason="deployment_timer",
        )

    if state["status"] == "active" and action_type in {"move", "attack", "defend", "skip"}:
        _advance_due_state(
            connection,
            state,
            current_time,
            source=source,
            include_timeouts=False,
            include_neutral_ai=True,
        )

    if state["status"] in FINAL_BATTLE_STATES:
        result = {
            "status": state["status"],
            "battle": _state_payload(
                connection,
                state,
                viewer_domain_id=actor_domain_id,
                viewer_role_type=actor_role_type,
            ),
        }
    elif state["status"] == "deployment":
        if action_type == "deploy":
            result = _apply_deploy_action(connection, state, actor_side, payload, current_time)
        elif action_type == "ready":
            result = _apply_deployment_ready(
                connection,
                state,
                actor_side,
                current_time,
                source=source,
            )
        else:
            raise LordBattleError(
                "battle_in_deployment",
                "Battle is still in deployment. Deploy units or confirm readiness first.",
            )
    elif action_type in {"deploy", "ready"}:
        raise LordBattleError("deployment_closed", "Deployment is already closed for this battle.")
    elif action_type != "timeout" and _turn_timer_due(state, current_time):
        timed_out_side = str(state["active_side"])
        result = _apply_timeout(
            connection,
            state,
            timed_out_side,
            current_time,
            source=source,
        )
        result["timed_out_before_action"] = True
        result["requested_action_type"] = action_type
        result["requested_actor_side"] = actor_side
    elif action_type == "master_takeover":
        result = _apply_master_takeover(connection, state, actor_side, current_time)
    elif action_type == "ai_turn":
        result = _apply_ai_turn(connection, state, actor_side, current_time, source=source)
    elif action_type == "timeout":
        result = _apply_timeout(connection, state, actor_side, current_time, source=source)
    elif action_type == "auto_resolve":
        result = _apply_auto_resolve(
            connection,
            state,
            actor_side,
            actor_role_type,
            current_time,
            source=source,
        )
    elif action_type == "surrender":
        result = _apply_surrender(connection, state, actor_side, current_time, source=source)
    elif action_type == "move":
        result = _apply_move_action(connection, state, actor_side, payload, current_time)
    elif action_type == "attack":
        result = _apply_attack_action(connection, state, actor_side, payload, current_time, source=source)
    elif action_type in {"defend", "skip"}:
        result = _apply_defend_action(connection, state, actor_side, current_time)
    else:
        raise LordBattleError("unknown_action", f"Unsupported battle action: {action_type}.")

    if action_type != "ai_turn" and _advance_due_state(
        connection,
        state,
        current_time,
        source=source,
        include_timeouts=False,
        include_neutral_ai=True,
    ):
        result["auto_advanced"] = True
    _save_state(connection, state, current_time)
    result.setdefault(
        "battle",
        _state_payload(
            connection,
            state,
            viewer_domain_id=actor_domain_id,
            viewer_role_type=actor_role_type,
        ),
    )
    result.setdefault("duplicate", False)
    connection.execute(
        """
        INSERT INTO lord_battle_actions (
            action_id, battle_id, actor_side, action_type, payload_json,
            result_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action_id,
            battle_id,
            actor_side,
            action_type,
            _json_dumps(payload),
            _json_dumps(result),
            _iso(current_time),
        ),
    )
    return result


def _apply_deploy_action(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    payload: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    if bool(state["deployment"].get("ready", {}).get(actor_side)):
        raise LordBattleError("deployment_side_ready", "Side already confirmed deployment.")
    item, hand_index = _deployment_item_from_payload(state, actor_side, payload)
    to_cell = payload.get("to") if isinstance(payload.get("to"), dict) else payload
    to_x = _to_int(to_cell.get("x"))
    to_y = _to_int(to_cell.get("y"))
    _assert_can_deploy_to_cell(state["board"], actor_side, to_x, to_y)
    existing = _deployment_entry_for_item(state["deployment"], actor_side, item)
    if existing is None and len(state["deployment"]["deployed"][actor_side]) >= int(state["deployment"]["deployment_cap"]):
        raise LordBattleError("deployment_cap_reached", "Deployment cap is already reached.")
    stack_id = str(existing["stack_id"]) if existing else f"{actor_side[0].upper()}{hand_index + 1}"
    state["board"]["stacks"] = [
        stack for stack in state["board"]["stacks"] if stack["stack_id"] != stack_id
    ]
    stack = _stack_from_source(item, side=actor_side, index=hand_index)
    stack["stack_id"] = stack_id
    stack["x"] = to_x
    stack["y"] = to_y
    state["board"]["stacks"].append(stack)
    deployed_entry = _deployment_entry(stack)
    if existing is None:
        state["deployment"]["deployed"][actor_side].append(deployed_entry)
    else:
        state["deployment"]["deployed"][actor_side] = [
            deployed_entry if _same_deployment_item(entry, item) else entry
            for entry in state["deployment"]["deployed"][actor_side]
        ]
    _append_log(
        connection,
        state["battle_id"],
        round_number=state["round_number"],
        actor_side=actor_side,
        entry_type="unit_deployed",
        payload=deployed_entry,
        now=now,
    )
    return {
        "status": "deployed",
        "side": actor_side,
        "stack_id": stack_id,
        "card_id": item["card_id"],
        "source_id": item["source_id"],
        "to": {"x": to_x, "y": to_y},
        "deployment_cap": state["deployment"]["deployment_cap"],
    }


def _apply_deployment_ready(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    now: datetime,
    *,
    source: str,
) -> dict[str, Any]:
    state["deployment"].setdefault("ready", {"attacker": False, "defender": False})
    state["deployment"]["ready"][actor_side] = True
    _append_log(
        connection,
        state["battle_id"],
        round_number=state["round_number"],
        actor_side=actor_side,
        entry_type="deployment_ready",
        payload={"ready": deepcopy(state["deployment"]["ready"])},
        now=now,
    )
    if all(bool(state["deployment"]["ready"].get(side)) for side in ("attacker", "defender")):
        _finalize_deployment(
            connection,
            state,
            now,
            source=source,
            reason="all_sides_ready",
        )
        return {"status": state["status"], "deployment": "finalized"}
    return {
        "status": "deployment_ready",
        "ready": deepcopy(state["deployment"]["ready"]),
    }


def _apply_master_takeover(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    now: datetime,
) -> dict[str, Any]:
    if actor_side != "defender" or state["battle_type"] != "neutral":
        raise LordBattleError(
            "takeover_not_available",
            "Master takeover is available only for the neutral defender.",
        )
    state["defender_control"] = "master"
    _append_log(
        connection,
        state["battle_id"],
        round_number=state["round_number"],
        actor_side=actor_side,
        entry_type="master_takeover",
        payload={"defender_control": "master"},
        now=now,
    )
    return {"status": "master_takeover", "defender_control": "master"}


def _apply_ai_turn(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    now: datetime,
    *,
    source: str,
) -> dict[str, Any]:
    if state["defender_control"] != "neutral_ai" or actor_side != "defender":
        raise LordBattleError("ai_not_available", "Server AI controls only neutral defender turns.")
    if state["active_side"] != "defender":
        raise LordBattleError("not_ai_turn", "Neutral AI can act only on defender turn.")
    stack = _active_stack(state)
    target = _nearest_enemy_stack(state["board"], stack)
    if target is not None and _can_attack(state["board"], stack, target):
        return _attack_stack(
            connection,
            state,
            actor_side,
            stack,
            target,
            now,
            source=source,
            ai=True,
        )
    if target is not None:
        moved = _move_toward_target(state["board"], stack, target)
        if moved:
            _append_log(
                connection,
                state["battle_id"],
                round_number=state["round_number"],
                actor_side=actor_side,
                entry_type="ai_move",
                payload={"stack_id": stack["stack_id"], "to": {"x": stack["x"], "y": stack["y"]}},
                now=now,
            )
            _advance_turn(state, now)
            return {"status": "ai_moved", "stack_id": stack["stack_id"]}
    return _defend_current_stack(connection, state, actor_side, now, entry_type="ai_defend")


def _apply_timeout(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    now: datetime,
    *,
    source: str,
) -> dict[str, Any]:
    if actor_side != state["active_side"]:
        raise LordBattleError("not_active_side", "Timeout can be recorded only for the active side.")
    counts = state["timeout_counts"]
    counts[actor_side] = int(counts.get(actor_side, 0)) + 1
    _append_log(
        connection,
        state["battle_id"],
        round_number=state["round_number"],
        actor_side=actor_side,
        entry_type="lord_battle_turn_timeout",
        payload={
            "stack_id": state["active_stack_id"],
            "timeout_count": counts[actor_side],
            "policy": "auto_defend_then_skip",
        },
        now=now,
    )
    if counts[actor_side] >= 2:
        return _finish_by_auto_resolve(
            connection,
            state,
            now,
            source=source,
            reason="repeated_timeout",
        )
    return _defend_current_stack(connection, state, actor_side, now, entry_type="timeout_auto_defend")


def _apply_auto_resolve(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    actor_role_type: str | None,
    now: datetime,
    *,
    source: str,
) -> dict[str, Any]:
    if state["battle_type"] == "lord_vs_lord" and actor_role_type != "npc_master":
        votes = _auto_resolve_votes(state)
        if actor_side not in votes["sides"]:
            votes["sides"].append(actor_side)
            votes["sides"].sort()
        _append_log(
            connection,
            state["battle_id"],
            round_number=state["round_number"],
            actor_side=actor_side,
            entry_type="auto_resolve_vote",
            payload=_auto_resolve_vote_payload(state),
            now=now,
        )
        if len(votes["sides"]) < 2:
            return {
                "status": "auto_resolve_vote_pending",
                "auto_resolve": _auto_resolve_vote_payload(state),
            }
        return _finish_by_auto_resolve(
            connection,
            state,
            now,
            source=source,
            reason="manual_auto_resolve_confirmed",
        )
    return _finish_by_auto_resolve(connection, state, now, source=source, reason="manual_auto_resolve")


def _apply_surrender(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    now: datetime,
    *,
    source: str,
) -> dict[str, Any]:
    if actor_side != state["active_side"]:
        raise LordBattleError("not_active_side", "Surrender is allowed only on your own turn.")
    winner_side = _enemy_side(actor_side)
    _finish_battle(
        connection,
        state,
        winner_side=winner_side,
        outcome="surrender",
        now=now,
        source=source,
    )
    return {"status": "finished", "outcome": "surrender", "winner_side": winner_side}


def _apply_move_action(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    payload: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    stack = _require_active_actor_stack(state, actor_side, payload.get("stack_id"))
    to_cell = payload.get("to") or {}
    to_x = _to_int(to_cell.get("x"))
    to_y = _to_int(to_cell.get("y"))
    _assert_can_move(state["board"], stack, to_x, to_y)
    from_cell = {"x": stack["x"], "y": stack["y"]}
    stack["x"] = to_x
    stack["y"] = to_y
    stack["defended"] = False
    _append_log(
        connection,
        state["battle_id"],
        round_number=state["round_number"],
        actor_side=actor_side,
        entry_type="unit_moved",
        payload={"stack_id": stack["stack_id"], "from": from_cell, "to": {"x": to_x, "y": to_y}},
        now=now,
    )
    _advance_turn(state, now)
    return {"status": "moved", "stack_id": stack["stack_id"], "from": from_cell, "to": {"x": to_x, "y": to_y}}


def _apply_attack_action(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    payload: dict[str, Any],
    now: datetime,
    *,
    source: str,
) -> dict[str, Any]:
    stack = _require_active_actor_stack(state, actor_side, payload.get("stack_id"))
    target_stack_id = _optional(payload.get("target_stack_id"))
    if target_stack_id:
        target = _stack_by_id(state["board"], target_stack_id)
        return _attack_stack(connection, state, actor_side, stack, target, now, source=source)
    target_type = str(payload.get("target_type") or "").strip().lower()
    if target_type == "hero":
        target_side = _side_name(str(payload.get("target_side") or _enemy_side(actor_side)))
        return _attack_hero(connection, state, actor_side, stack, target_side, now, source=source)
    raise LordBattleError("missing_target", "Attack requires target_stack_id or target_type=hero.")


def _apply_defend_action(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    now: datetime,
) -> dict[str, Any]:
    return _defend_current_stack(connection, state, actor_side, now, entry_type="unit_defended")


def _attack_stack(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    stack: dict[str, Any],
    target: dict[str, Any],
    now: datetime,
    *,
    source: str,
    ai: bool = False,
) -> dict[str, Any]:
    if target["side"] == actor_side:
        raise LordBattleError("friendly_fire", "Cannot attack your own stack.")
    if not _is_alive(target):
        raise LordBattleError("target_destroyed", "Target stack is already destroyed.")
    if not _can_attack(state["board"], stack, target):
        raise LordBattleError("illegal_attack", "Target is outside range or line of sight.")

    damage = _damage(stack, target)
    casualty = _apply_damage_to_stack(target, damage)
    retaliation: dict[str, Any] | None = None
    distance = _distance(stack, target)
    if _is_alive(target) and not bool(target.get("retaliated_this_round")) and int(target["attack_range"]) >= distance:
        retaliation_damage = _damage(target, stack)
        retaliation_casualty = _apply_damage_to_stack(stack, retaliation_damage)
        target["retaliated_this_round"] = True
        retaliation = {
            "stack_id": target["stack_id"],
            "target_stack_id": stack["stack_id"],
            "damage": retaliation_damage,
            "casualties": retaliation_casualty,
        }
    stack["defended"] = False
    entry_type = "ai_attack" if ai else "unit_attacked"
    _append_log(
        connection,
        state["battle_id"],
        round_number=state["round_number"],
        actor_side=actor_side,
        entry_type=entry_type,
        payload={
            "stack_id": stack["stack_id"],
            "target_stack_id": target["stack_id"],
            "damage_formula": "count_alive * max(1, effective_attack - effective_defense + modifiers)",
            "damage": damage,
            "casualties": casualty,
            "retaliation": retaliation,
        },
        now=now,
    )
    winner_side = _winner_from_state(state)
    if winner_side:
        _finish_battle(connection, state, winner_side=winner_side, outcome="unit_wipe", now=now, source=source)
    else:
        _advance_turn(state, now)
    return {
        "status": "attacked",
        "stack_id": stack["stack_id"],
        "target_stack_id": target["stack_id"],
        "damage": damage,
        "casualties": casualty,
        "retaliation": retaliation,
    }


def _attack_hero(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    stack: dict[str, Any],
    target_side: str,
    now: datetime,
    *,
    source: str,
) -> dict[str, Any]:
    if target_side == actor_side:
        raise LordBattleError("friendly_fire", "Cannot attack your own hero.")
    hero_cell = state["board"]["hero_cells"][target_side]
    target = {"x": hero_cell["x"], "y": hero_cell["y"], "defense": 0, "side": target_side}
    if _distance(stack, target) > int(stack["attack_range"]) or not _can_arc_or_see(
        state["board"],
        stack,
        target,
    ):
        raise LordBattleError("illegal_hero_attack", "Hero is outside range or line of sight.")
    damage = _hero_damage(stack)
    state["hero_hp"][target_side]["current"] = max(
        0,
        int(state["hero_hp"][target_side]["current"]) - damage,
    )
    _append_log(
        connection,
        state["battle_id"],
        round_number=state["round_number"],
        actor_side=actor_side,
        entry_type="hero_attacked",
        payload={
            "stack_id": stack["stack_id"],
            "target_side": target_side,
            "damage": damage,
            "hero_hp": state["hero_hp"][target_side]["current"],
        },
        now=now,
    )
    if int(state["hero_hp"][target_side]["current"]) <= 0:
        _finish_battle(connection, state, winner_side=actor_side, outcome="hero_hp", now=now, source=source)
    else:
        _advance_turn(state, now)
    return {
        "status": "hero_attacked",
        "stack_id": stack["stack_id"],
        "target_side": target_side,
        "damage": damage,
        "hero_hp": state["hero_hp"][target_side]["current"],
    }


def _defend_current_stack(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    actor_side: str,
    now: datetime,
    *,
    entry_type: str,
) -> dict[str, Any]:
    if actor_side != state["active_side"]:
        raise LordBattleError("not_active_side", "Only the active side can defend or skip.")
    stack = _active_stack(state)
    stack["defended"] = True
    _append_log(
        connection,
        state["battle_id"],
        round_number=state["round_number"],
        actor_side=actor_side,
        entry_type=entry_type,
        payload={"stack_id": stack["stack_id"], "defense_modifier": -1},
        now=now,
    )
    _advance_turn(state, now)
    return {"status": "defended", "stack_id": stack["stack_id"]}


def _finish_by_auto_resolve(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    now: datetime,
    *,
    source: str,
    reason: str,
) -> dict[str, Any]:
    winner_side = _auto_resolve_winner(state)
    for stack in _alive_stacks(state["board"], _enemy_side(winner_side)):
        stack["count_alive"] = 0
        stack["wounds_on_front_unit"] = 0
    _finish_battle(
        connection,
        state,
        winner_side=winner_side,
        outcome="auto_resolve",
        now=now,
        source=source,
        reason=reason,
    )
    return {
        "status": "finished",
        "outcome": "auto_resolve",
        "reason": reason,
        "winner_side": winner_side,
    }


def _finish_battle(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    *,
    winner_side: str,
    outcome: str,
    now: datetime,
    source: str,
    reason: str | None = None,
) -> None:
    if state["status"] in FINAL_BATTLE_STATES:
        return
    loser_side = _enemy_side(winner_side)
    burned_cards = _apply_losses(connection, state, now)
    state["burned_cards"].extend(burned_cards)
    retreat = _apply_retreat(connection, state, loser_side, now)
    capture = _apply_capture_result(connection, state, winner_side, now)
    duration_seconds = max(0, int((now - _parse_iso(state["created_at"])).total_seconds()))
    winner_domain_id = _domain_for_side(state, winner_side)
    loser_domain_id = _domain_for_side(state, loser_side)
    state["status"] = "finished"
    state["active_side"] = None
    state["active_stack_id"] = None
    state["finished_at"] = _iso(now)
    state["result"] = {
        "winner_side": winner_side,
        "winner_domain_id": winner_domain_id,
        "loser_side": loser_side,
        "loser_domain_id": loser_domain_id,
        "outcome": outcome,
        "reason": reason,
        "duration_seconds": duration_seconds,
        "target_duration_seconds": state["target_duration_seconds"],
        "over_target": duration_seconds > state["target_duration_seconds"],
        "burned_cards": burned_cards,
        "retreat": retreat,
        "capture": capture,
        "applied_at": _iso(now),
    }
    _append_log(
        connection,
        state["battle_id"],
        round_number=state["round_number"],
        actor_side=winner_side,
        entry_type="lord_battle_finished",
        payload=state["result"],
        now=now,
    )
    log_event(
        connection,
        "lord_battle_finished" if outcome != "auto_resolve" else "lord_battle_auto_resolved",
        {"battle_id": state["battle_id"], **state["result"]},
        source=source,
        created_at=now,
    )


def _apply_losses(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    now: datetime,
) -> list[dict[str, Any]]:
    burned = []
    for stack in state["board"]["stacks"]:
        casualties = max(0, int(stack["initial_count"]) - int(stack["count_alive"]))
        if casualties <= 0:
            continue
        source_type = stack["source_type"]
        source_id = stack["source_id"]
        if source_type == "active_army":
            _decrement_runtime_stack(
                connection,
                table_name="active_army_runtime",
                id_column="army_id",
                row_id=source_id,
                casualties=casualties,
                now=now,
            )
        elif source_type == "garrison":
            _decrement_runtime_stack(
                connection,
                table_name="garrison_runtime_state",
                id_column="garrison_id",
                row_id=source_id,
                casualties=casualties,
                now=now,
            )
        elif source_type != "neutral_profile":
            continue
        burned.append(
            {
                "source_type": source_type,
                "source_id": source_id,
                "domain_id": stack["domain_id"],
                "card_id": stack["card_id"],
                "count": casualties,
            }
        )
    return burned


def _decrement_runtime_stack(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    id_column: str,
    row_id: str,
    casualties: int,
    now: datetime,
) -> None:
    row = connection.execute(
        f"SELECT count FROM {table_name} WHERE {id_column} = ?",
        (row_id,),
    ).fetchone()
    if row is None:
        return
    remaining = max(0, int(row["count"]) - casualties)
    status = "burned" if remaining == 0 else "active"
    connection.execute(
        f"""
        UPDATE {table_name}
        SET count = ?, status = ?, updated_at = ?
        WHERE {id_column} = ?
        """,
        (remaining, status, _iso(now), row_id),
    )


def _apply_retreat(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    loser_side: str,
    now: datetime,
) -> dict[str, Any] | None:
    loser_domain_id = _domain_for_side(state, loser_side)
    if not loser_domain_id:
        return None
    active_stacks = [
        stack
        for stack in state["board"]["stacks"]
        if stack["side"] == loser_side
        and stack["source_type"] == "active_army"
    ]
    if not active_stacks:
        return None
    retreat_node = _retreat_node(
        connection,
        loser_domain_id,
        battle_territory_id=_optional(state.get("territory_id")),
    )
    if retreat_node is None:
        return {"domain_id": loser_domain_id, "status": "no_retreat_node"}
    active_source_ids = {
        str(stack["source_id"])
        for stack in active_stacks
        if stack.get("source_id")
    }
    if active_source_ids:
        placeholders = ",".join("?" for _ in active_source_ids)
        connection.execute(
            f"""
            UPDATE active_army_runtime
            SET location_node_id = ?, updated_at = ?
            WHERE domain_id = ? AND army_id IN ({placeholders})
            """,
            (retreat_node, _iso(now), loser_domain_id, *sorted(active_source_ids)),
        )
    connection.execute(
        """
        UPDATE domain_runtime_state
        SET current_node_id = ?, updated_at = ?
        WHERE domain_id = ?
        """,
        (retreat_node, _iso(now), loser_domain_id),
    )
    return {
        "domain_id": loser_domain_id,
        "to_node_id": retreat_node,
        "territory_id": _territory_for_node(connection, retreat_node),
        "status": "retreated",
    }


def _apply_capture_result(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    winner_side: str,
    now: datetime,
) -> dict[str, Any] | None:
    territory_id = state.get("territory_id")
    if not territory_id:
        return None
    attacker_won = winner_side == "attacker"
    attacker_domain_id = state["attacker_domain_id"]
    if attacker_won:
        connection.execute(
            """
            UPDATE territory_runtime_state
            SET status = 'capture_pending_garrison',
                contested_by_domain_id = ?,
                updated_at = ?
            WHERE territory_id = ?
            """,
            (attacker_domain_id, _iso(now), territory_id),
        )
        if state.get("claim_id"):
            connection.execute(
                """
                UPDATE territory_claim_runtime
                SET status = 'awaiting_garrison', battle_required = 0, resolved_at = ?
                WHERE claim_id = ?
                """,
                (_iso(now), state["claim_id"]),
            )
        return {
            "status": "capture_pending_garrison",
            "territory_id": territory_id,
            "winning_domain_id": attacker_domain_id,
            "garrison_required": True,
        }

    territory = _territory_context(connection, territory_id)
    controlled_status = "controlled" if _optional(territory["runtime_owner_domain_id"]) else "neutral"
    connection.execute(
        """
        UPDATE territory_runtime_state
        SET status = ?,
            contested_by_domain_id = NULL,
            updated_at = ?
        WHERE territory_id = ?
        """,
        (controlled_status, _iso(now), territory_id),
    )
    if state.get("claim_id"):
        connection.execute(
            """
            UPDATE territory_claim_runtime
            SET status = 'failed_defender_won', battle_required = 0, resolved_at = ?
            WHERE claim_id = ?
            """,
            (_iso(now), state["claim_id"]),
        )
    defender_domain_id = _optional(territory["runtime_owner_domain_id"])
    pending_tick_awards = _settle_pending_tick_rewards(
        connection,
        territory_id,
        defender_domain_id,
        now,
    )
    return {
        "status": "defense_held",
        "territory_id": territory_id,
        "pending_tick_awards": pending_tick_awards,
    }


def _settle_pending_tick_rewards(
    connection: sqlite3.Connection,
    territory_id: str,
    winner_domain_id: str | None,
    now: datetime,
) -> list[dict[str, Any]]:
    if not _table_exists(connection, "pending_tick_reward_runtime"):
        return []
    rows = connection.execute(
        """
        SELECT pending_reward_id, reward_gold
        FROM pending_tick_reward_runtime
        WHERE territory_id = ? AND status = 'pending'
        ORDER BY due_at, pending_reward_id
        """,
        (territory_id,),
    ).fetchall()
    settled = []
    for row in rows:
        if winner_domain_id:
            connection.execute(
                """
                UPDATE pending_tick_reward_runtime
                SET status = 'awarded', awarded_to_domain_id = ?, awarded_at = ?
                WHERE pending_reward_id = ?
                """,
                (winner_domain_id, _iso(now), row["pending_reward_id"]),
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET gold = gold + ?, updated_at = ?
                WHERE domain_id = ?
                """,
                (int(row["reward_gold"]), _iso(now), winner_domain_id),
            )
            settled.append(
                {
                    "pending_reward_id": row["pending_reward_id"],
                    "reward_gold": int(row["reward_gold"]),
                    "awarded_to_domain_id": winner_domain_id,
                    "status": "awarded",
                }
            )
        else:
            connection.execute(
                """
                UPDATE pending_tick_reward_runtime
                SET status = 'voided', awarded_at = ?
                WHERE pending_reward_id = ?
                """,
                (_iso(now), row["pending_reward_id"]),
            )
            settled.append(
                {
                    "pending_reward_id": row["pending_reward_id"],
                    "reward_gold": int(row["reward_gold"]),
                    "awarded_to_domain_id": None,
                    "status": "voided",
                }
            )
    return settled


def _advance_turn(state: dict[str, Any], now: datetime) -> None:
    winner_side = _winner_from_state(state)
    if winner_side:
        return
    current_id = state["active_stack_id"]
    if current_id:
        _stack_by_id(state["board"], current_id)["acted_round"] = state["round_number"]
    order = [
        stack_id
        for stack_id in state["initiative_order"]
        if _is_alive(_stack_by_id(state["board"], stack_id))
        and int(_stack_by_id(state["board"], stack_id).get("acted_round", 0)) != state["round_number"]
    ]
    next_stack_id: str | None = None
    if current_id in order:
        current_index = order.index(current_id)
        for candidate_id in order[current_index + 1 :]:
            candidate = _stack_by_id(state["board"], candidate_id)
            if _is_alive(candidate):
                next_stack_id = candidate_id
                break
    else:
        next_stack_id = order[0] if order else None

    if next_stack_id is None:
        state["round_number"] += 1
        for stack in state["board"]["stacks"]:
            stack["retaliated_this_round"] = False
            stack["defended"] = False
        state["initiative_order"] = _initiative_order(
            state["board"],
            state["seed"],
            state["round_number"],
        )
        next_stack_id = state["initiative_order"][0] if state["initiative_order"] else None

    state["active_stack_id"] = next_stack_id
    state["active_side"] = _stack_by_id(state["board"], next_stack_id)["side"] if next_stack_id else None
    state["turn_started_at"] = _iso(now)
    state["timeout_at"] = _iso(now + timedelta(seconds=int(state["turn_timer_seconds"])))


def _winner_from_state(state: dict[str, Any]) -> str | None:
    for side in ("attacker", "defender"):
        if int(state["hero_hp"][side]["current"]) <= 0:
            return _enemy_side(side)
        if not _alive_stacks(state["board"], side):
            return _enemy_side(side)
    return None


def _auto_resolve_winner(state: dict[str, Any]) -> str:
    scores = {}
    for side in ("attacker", "defender"):
        stack_score = sum(
            _unit_power(stack) * int(stack["count_alive"])
            for stack in _alive_stacks(state["board"], side)
        )
        scores[side] = stack_score + int(state["hero_hp"][side]["current"])
    if scores["attacker"] == scores["defender"]:
        pick = _deterministic_int(state["seed"], "auto_resolve", modulus=2)
        return "attacker" if pick == 0 else "defender"
    return "attacker" if scores["attacker"] > scores["defender"] else "defender"


def _build_initial_board(
    attacker_sources: list[dict[str, Any]],
    defender_sources: list[dict[str, Any]],
    *,
    seed: str,
    rule: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    sorted_sources = {
        side: _sort_sources_for_deploy(sources, seed, side)
        for side, sources in (("attacker", attacker_sources), ("defender", defender_sources))
    }
    deployment = {
        "deployment_cap": DEPLOYMENT_CAP,
        "hand": {
            "attacker": [_hand_item(source) for source in sorted_sources["attacker"]],
            "defender": [_hand_item(source) for source in sorted_sources["defender"]],
        },
        "deployed": {"attacker": [], "defender": []},
        "undeployed": {"attacker": [], "defender": []},
    }
    board = {
        "width": int(rule["grid_width"]),
        "height": int(rule["grid_height"]),
        "hero_cells": {
            "attacker": {"x": 2, "y": 0},
            "defender": {"x": 2, "y": int(rule["grid_height"]) - 1},
        },
        "start_lines": {
            "attacker": 0,
            "defender": int(rule["grid_height"]) - 1,
        },
        "stacks": [],
        "rules": {
            "damage_formula": rule["damage_formula"],
            "initiative_tiebreaker": rule["initiative_tiebreaker"],
            "timeout_policy": rule["timeout_policy"],
            "auto_resolve_policy": rule["auto_resolve_policy"],
            "turn_timer_seconds": int(rule["turn_timer_seconds"]),
            "line_of_sight": "orthogonal_clear_path",
            "movement": "orthogonal_manhattan",
            "retaliation": "once_per_unit_per_round",
        },
    }
    return board, deployment, _hero_hp_for_stacks(board["stacks"])


def _stack_from_source(source: dict[str, Any], *, side: str, index: int) -> dict[str, Any]:
    stack_id = f"{side[0].upper()}{index + 1}"
    return {
        "stack_id": stack_id,
        "side": side,
        "domain_id": source.get("domain_id"),
        "source_type": source["source_type"],
        "source_id": source["source_id"],
        "card_id": source["card_id"],
        "unit_class": source["unit_class"],
        "tier": int(source["tier"]),
        "attack": int(source["attack"]),
        "defense": int(source["defense"]),
        "hp": int(source["hp"]),
        "initiative": int(source["initiative"]),
        "move_range": int(source["move_range"]),
        "attack_range": int(source["attack_range"]),
        "initial_count": int(source["count"]),
        "count_alive": int(source["count"]),
        "wounds_on_front_unit": 0,
        "x": 0,
        "y": 0,
        "acted_round": 0,
        "retaliated_this_round": False,
        "defended": False,
    }


def _deployment_position(side: str, index: int) -> tuple[int, int]:
    x_order = [0, 1, 3, 4, 2]
    if side == "attacker":
        y_order = [0, 0, 0, 0, 1]
    else:
        y_order = [5, 5, 5, 5, 4]
    return x_order[index], y_order[index]


def _deployment_rows(board: dict[str, Any], side: str) -> set[int]:
    start_line = int(board["start_lines"][side])
    if side == "attacker":
        return {start_line, min(int(board["height"]) - 1, start_line + 1)}
    return {start_line, max(0, start_line - 1)}


def _normalize_board_start_lines(board: dict[str, Any]) -> dict[str, Any]:
    height = max(1, int(board.get("height") or 1))
    hero_cells = board.get("hero_cells")
    start_lines = board.get("start_lines")
    if not isinstance(hero_cells, dict):
        return board
    normalized = dict(start_lines) if isinstance(start_lines, dict) else {}
    attacker_cell = hero_cells.get("attacker")
    defender_cell = hero_cells.get("defender")
    normalized["attacker"] = (
        int(attacker_cell.get("y", 0)) if isinstance(attacker_cell, dict) else 0
    )
    normalized["defender"] = (
        int(defender_cell.get("y", height - 1)) if isinstance(defender_cell, dict) else height - 1
    )
    board["start_lines"] = normalized
    return board


def _assert_can_deploy_to_cell(board: dict[str, Any], side: str, x: int, y: int) -> None:
    if not (0 <= x < int(board["width"]) and 0 <= y < int(board["height"])):
        raise LordBattleError("deploy_off_board", "Deployment cell is outside the 5x6 board.")
    if y not in _deployment_rows(board, side):
        raise LordBattleError("deploy_outside_start_zone", "Unit must deploy inside its start zone.")
    if _is_hero_cell(board, x, y):
        raise LordBattleError("deploy_to_hero_cell", "Units cannot deploy on hero cells.")
    if _occupied_stack_at(board, x, y) is not None:
        raise LordBattleError("deploy_to_occupied_cell", "Deployment cell is occupied.")


def _deployment_item_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("source_type") or ""),
        str(item.get("source_id") or ""),
        str(item.get("card_id") or ""),
    )


def _same_deployment_item(entry: dict[str, Any], item: dict[str, Any]) -> bool:
    return _deployment_item_key(entry) == _deployment_item_key(item)


def _deployment_entry_for_item(
    deployment: dict[str, Any],
    side: str,
    item: dict[str, Any],
) -> dict[str, Any] | None:
    for entry in deployment["deployed"].get(side, []):
        if _same_deployment_item(entry, item):
            return entry
    return None


def _deployment_entry(stack: dict[str, Any]) -> dict[str, Any]:
    return {
        "stack_id": stack["stack_id"],
        "card_id": stack["card_id"],
        "unit_class": stack["unit_class"],
        "count": stack["initial_count"],
        "x": stack["x"],
        "y": stack["y"],
        "source_type": stack["source_type"],
        "source_id": stack["source_id"],
        "domain_id": stack.get("domain_id"),
    }


def _deployment_item_from_payload(
    state: dict[str, Any],
    side: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    source_id = str(payload.get("source_id") or "").strip()
    card_id = str(payload.get("card_id") or "").strip()
    if not source_id and not card_id:
        raise LordBattleError("missing_card_id", "Deploy action requires card_id or source_id.")
    hand = state["deployment"]["hand"].get(side, [])
    first_card_match: tuple[dict[str, Any], int] | None = None
    for index, item in enumerate(hand):
        if source_id and source_id == str(item.get("source_id")):
            return item, index
        if card_id and card_id == str(item.get("card_id")) and first_card_match is None:
            first_card_match = item, index
            if _deployment_entry_for_item(state["deployment"], side, item) is None:
                return item, index
    if first_card_match is not None:
        return first_card_match
    raise LordBattleError(
        "deployment_card_not_in_hand",
        "Cannot deploy a card outside the available deployment hand.",
    )


def _auto_deploy_side(board: dict[str, Any], deployment: dict[str, Any], side: str) -> None:
    for hand_index, item in enumerate(deployment["hand"].get(side, [])):
        if len(deployment["deployed"][side]) >= int(deployment["deployment_cap"]):
            break
        deploy_index = len(deployment["deployed"][side])
        stack = _stack_from_source(item, side=side, index=hand_index)
        stack["x"], stack["y"] = _deployment_position(side, deploy_index)
        board["stacks"].append(stack)
        deployment["deployed"][side].append(_deployment_entry(stack))


def _finalize_deployment(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    now: datetime,
    *,
    source: str,
    reason: str,
) -> None:
    if state["status"] != "deployment":
        return
    deployment = state["deployment"]
    for side in ("attacker", "defender"):
        deployed_keys = {
            _deployment_item_key(entry)
            for entry in deployment["deployed"].get(side, [])
        }
        deployment["undeployed"][side] = [
            item
            for item in deployment["hand"].get(side, [])
            if _deployment_item_key(item) not in deployed_keys
        ]
    deployment["ready"] = {"attacker": True, "defender": True}
    deployment["phase"] = "complete"
    deployment["completed_at"] = _iso(now)
    deployment["completed_reason"] = reason
    state["hero_hp"] = _hero_hp_for_stacks(state["board"]["stacks"])
    state["status"] = "active"
    state["round_number"] = 1
    state["initiative_order"] = _initiative_order(state["board"], state["seed"], 1)
    state["active_stack_id"] = state["initiative_order"][0] if state["initiative_order"] else None
    state["active_side"] = (
        _stack_by_id(state["board"], state["active_stack_id"])["side"]
        if state["active_stack_id"]
        else None
    )
    state["turn_started_at"] = _iso(now)
    state["timeout_at"] = _iso(now + timedelta(seconds=int(state["turn_timer_seconds"])))
    _append_log(
        connection,
        state["battle_id"],
        round_number=state["round_number"],
        actor_side=None,
        entry_type="deployment_recorded",
        payload={
            "deployed": deployment["deployed"],
            "undeployed": deployment["undeployed"],
            "reason": reason,
            "hp_formula_inputs": state["hero_hp"]["formula_inputs"],
        },
        now=now,
    )
    winner_side = _winner_from_state(state)
    if winner_side:
        _finish_battle(
            connection,
            state,
            winner_side=winner_side,
            outcome="deployment_no_units",
            now=now,
            source=source,
            reason=reason,
        )


def _hero_hp_payload(stacks: list[dict[str, Any]], side: str) -> dict[str, int]:
    deployed_power = _deployed_army_power(stacks, side)
    hp = min(
        HERO_HP_MAX,
        max(HERO_HP_MIN, HERO_HP_BASE + deployed_power // HERO_HP_POWER_DIVISOR),
    )
    return {"current": hp, "max": hp, "deployed_army_power": deployed_power}


def _deployed_army_power(stacks: list[dict[str, Any]], side: str) -> int:
    return sum(
        _unit_power(stack) * int(stack["initial_count"])
        for stack in stacks
        if stack["side"] == side
    )


def _hero_hp_for_stacks(stacks: list[dict[str, Any]]) -> dict[str, Any]:
    hero_hp = {
        "attacker": _hero_hp_payload(stacks, "attacker"),
        "defender": _hero_hp_payload(stacks, "defender"),
    }
    hero_hp["formula_inputs"] = {
        "base": HERO_HP_BASE,
        "power_divisor": HERO_HP_POWER_DIVISOR,
        "min": HERO_HP_MIN,
        "max": HERO_HP_MAX,
        "attacker_deployed_army_power": _deployed_army_power(stacks, "attacker"),
        "defender_deployed_army_power": _deployed_army_power(stacks, "defender"),
    }
    return hero_hp


def _active_army_sources(connection: sqlite3.Connection, domain_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT a.army_id, a.domain_id, a.card_id, a.count, c.*
        FROM active_army_runtime a
        JOIN army_unit_cards c ON c.card_id = a.card_id
        WHERE a.domain_id = ?
          AND a.status = 'active'
          AND a.count > 0
        ORDER BY a.army_id
        """,
        (domain_id,),
    ).fetchall()
    return [_source_from_row(row, "active_army", str(row["army_id"])) for row in rows]


def _defender_sources(
    connection: sqlite3.Connection,
    defender_domain_id: str,
    territory_id: str | None,
) -> list[dict[str, Any]]:
    sources = []
    if territory_id:
        rows = connection.execute(
            """
            SELECT g.garrison_id, g.domain_id, g.card_id, g.count, c.*
            FROM garrison_runtime_state g
            JOIN army_unit_cards c ON c.card_id = g.card_id
            WHERE g.domain_id = ?
              AND g.territory_id = ?
              AND g.status = 'active'
              AND g.count > 0
            ORDER BY g.garrison_id
            """,
            (defender_domain_id, territory_id),
        ).fetchall()
        sources.extend(_source_from_row(row, "garrison", str(row["garrison_id"])) for row in rows)
        _apply_raid_defense_penalty(
            sources,
            raid_defense_penalty_for_territory(connection, territory_id),
        )
        if _domain_current_territory(connection, defender_domain_id) == territory_id:
            sources.extend(_active_army_sources(connection, defender_domain_id))
    else:
        sources.extend(_active_army_sources(connection, defender_domain_id))
    return sources


def _apply_raid_defense_penalty(
    sources: list[dict[str, Any]], penalty: int
) -> None:
    if penalty <= 0:
        return
    for source in sources:
        if source.get("source_type") != "garrison":
            continue
        source["defense"] = max(0, int(source["defense"]) - penalty)
        source["raid_defense_penalty"] = penalty


def _neutral_sources(
    connection: sqlite3.Connection,
    territory: sqlite3.Row | None,
) -> list[dict[str, Any]]:
    profile_id = _optional(territory["neutral_defense_profile_id"]) if territory is not None else None
    tier = _to_int(territory["tier"]) if territory is not None else 1
    if profile_id:
        mob = connection.execute(
            "SELECT tier FROM mobs WHERE mob_id = ? LIMIT 1",
            (profile_id,),
        ).fetchone()
        if mob is not None:
            tier = max(1, _to_int(mob["tier"]))
    max_sources = min(DEPLOYMENT_CAP, max(2, tier + 1))
    rows = connection.execute(
        """
        SELECT *
        FROM army_unit_cards
        WHERE CAST(tier AS INTEGER) <= ?
          AND unit_class IN ('infantry', 'guard', 'ranged', 'cavalry', 'heavy_siege', 'specialist')
        ORDER BY CAST(tier AS INTEGER) DESC, unit_class
        LIMIT ?
        """,
        (tier, max_sources),
    ).fetchall()
    if not rows:
        rows = connection.execute(
            """
            SELECT *
            FROM army_unit_cards
            WHERE unit_class IN ('infantry', 'guard', 'ranged', 'cavalry', 'heavy_siege', 'specialist')
            ORDER BY CAST(tier AS INTEGER), unit_class
            LIMIT 2
            """
        ).fetchall()
    neutral_count = NEUTRAL_DEFENSE_COUNT_BY_TIER.get(
        tier,
        NEUTRAL_DEFENSE_COUNT_BY_TIER[max(NEUTRAL_DEFENSE_COUNT_BY_TIER)],
    )
    return [
        {
            **_source_from_row(row, "neutral_profile", f"neutral_{profile_id or 'default'}_{row['card_id']}"),
            "domain_id": None,
            "count": neutral_count,
            "neutral_profile_id": profile_id,
        }
        for row in rows
    ]


def _source_from_row(row: sqlite3.Row, source_type: str, source_id: str) -> dict[str, Any]:
    unit_class = str(row["unit_class"])
    if unit_class not in UNIT_CLASSES:
        raise LordBattleError("unsupported_unit_class", f"Unsupported lord unit class: {unit_class}.")
    stats = {column: _to_int(row[column]) for column in UNIT_BATTLE_RANGES}
    for column, (minimum, maximum) in UNIT_BATTLE_RANGES.items():
        value = stats[column]
        if not minimum <= value <= maximum:
            raise LordBattleError(
                "invalid_unit_stat",
                (
                    f"Army unit card {row['card_id']} has invalid {column}={value}; "
                    f"expected {minimum}..{maximum}."
                ),
            )
    return {
        "source_type": source_type,
        "source_id": source_id,
        "domain_id": _optional(row["domain_id"]) if "domain_id" in row.keys() else None,
        "card_id": row["card_id"],
        "unit_class": unit_class,
        "tier": stats["tier"],
        "attack": stats["attack"],
        "defense": stats["defense"],
        "hp": stats["hp"],
        "initiative": stats["initiative"],
        "move_range": stats["move_range"],
        "attack_range": stats["attack_range"],
        "count": max(1, _to_int(row["count"]) if "count" in row.keys() else 1),
    }


def _hand_item(source: dict[str, Any]) -> dict[str, Any]:
    item = {
        "source_type": source["source_type"],
        "source_id": source["source_id"],
        "domain_id": source.get("domain_id"),
        "card_id": source["card_id"],
        "unit_class": source["unit_class"],
        "tier": source["tier"],
        "attack": source["attack"],
        "defense": source["defense"],
        "hp": source["hp"],
        "initiative": source["initiative"],
        "move_range": source["move_range"],
        "attack_range": source["attack_range"],
        "count": source["count"],
    }
    if source.get("neutral_profile_id"):
        item["neutral_profile_id"] = source["neutral_profile_id"]
    return item


def _sort_sources_for_deploy(
    sources: list[dict[str, Any]],
    seed: str,
    side: str,
) -> list[dict[str, Any]]:
    return sorted(
        sources,
        key=lambda source: (
            -int(source["tier"]),
            -_unit_power(source),
            _deterministic_int(seed, side, source["source_id"]),
        ),
    )


def _initiative_order(board: dict[str, Any], seed: str, round_number: int) -> list[str]:
    alive = [stack for stack in board["stacks"] if _is_alive(stack)]
    ordered_ids: list[str] = []
    initiative_values = sorted({int(stack["initiative"]) for stack in alive}, reverse=True)
    for initiative in initiative_values:
        tied = sorted(
            [stack for stack in alive if int(stack["initiative"]) == initiative],
            key=lambda stack: (
                -int(stack["tier"]),
                _deterministic_int(seed, "initiative", stack["stack_id"]),
            ),
        )
        if len(tied) > 1:
            offset = (round_number - 1) % len(tied)
            tied = tied[offset:] + tied[:offset]
        ordered_ids.extend(stack["stack_id"] for stack in tied)
    return ordered_ids


def _damage(attacker: dict[str, Any], defender: dict[str, Any]) -> int:
    modifiers = -1 if bool(defender.get("defended")) else 0
    per_unit_damage = max(
        1,
        _effective_attack(attacker) - _effective_defense(defender) + modifiers,
    )
    return max(1, int(attacker["count_alive"]) * per_unit_damage)


def _hero_damage(stack: dict[str, Any]) -> int:
    multiplier = HERO_ATTACK_MULTIPLIER.get(str(stack.get("unit_class") or ""), 1)
    return max(1, int(stack["count_alive"]) * _effective_attack(stack) * multiplier)


def _effective_attack(stack: dict[str, Any]) -> int:
    unit_class = str(stack.get("unit_class") or "")
    return int(stack["attack"]) + UNIT_CLASS_ATTACK_BONUS.get(unit_class, 0)


def _effective_defense(stack: dict[str, Any]) -> int:
    unit_class = str(stack.get("unit_class") or "")
    return int(stack["defense"]) + UNIT_CLASS_DEFENSE_BONUS.get(unit_class, 0)


def _apply_damage_to_stack(stack: dict[str, Any], damage: int) -> dict[str, int]:
    if not _is_alive(stack):
        return {"killed": 0, "count_alive": 0, "wounds_on_front_unit": 0}
    total = int(stack["wounds_on_front_unit"]) + damage
    killed = min(int(stack["count_alive"]), total // int(stack["hp"]))
    remaining_alive = int(stack["count_alive"]) - killed
    wounds = 0 if remaining_alive <= 0 else total % int(stack["hp"])
    stack["count_alive"] = remaining_alive
    stack["wounds_on_front_unit"] = wounds
    return {
        "killed": killed,
        "count_alive": remaining_alive,
        "wounds_on_front_unit": wounds,
    }


def _assert_can_move(board: dict[str, Any], stack: dict[str, Any], to_x: int, to_y: int) -> None:
    if not (0 <= to_x < int(board["width"]) and 0 <= to_y < int(board["height"])):
        raise LordBattleError("move_off_board", "Move target is outside the 5x6 board.")
    if _is_hero_cell(board, to_x, to_y):
        raise LordBattleError("move_to_hero_cell", "Units cannot enter hero cells.")
    if _occupied_stack_at(board, to_x, to_y) is not None:
        raise LordBattleError("move_to_occupied_cell", "Move target is occupied.")
    distance = abs(int(stack["x"]) - to_x) + abs(int(stack["y"]) - to_y)
    if distance <= 0 or distance > int(stack["move_range"]):
        raise LordBattleError("move_out_of_range", "Move target is outside move_range.")


def _can_attack(board: dict[str, Any], stack: dict[str, Any], target: dict[str, Any]) -> bool:
    distance = _distance(stack, target)
    return distance <= int(stack["attack_range"]) and _can_arc_or_see(board, stack, target)


def _can_arc_or_see(board: dict[str, Any], stack: dict[str, Any], target: dict[str, Any]) -> bool:
    if _uses_arcing_attack(stack):
        return True
    return _line_of_sight_clear(board, stack, target)


def _uses_arcing_attack(stack: dict[str, Any]) -> bool:
    return int(stack.get("attack_range", 1)) > 1 and str(stack.get("unit_class") or "") in ARCING_ATTACK_CLASSES


def _line_of_sight_clear(board: dict[str, Any], stack: dict[str, Any], target: dict[str, Any]) -> bool:
    if _distance(stack, target) <= 1:
        return True
    if int(stack["x"]) == int(target["x"]):
        step = 1 if int(target["y"]) > int(stack["y"]) else -1
        for y in range(int(stack["y"]) + step, int(target["y"]), step):
            if _occupied_stack_at(board, int(stack["x"]), y) is not None:
                return False
        return True
    if int(stack["y"]) == int(target["y"]):
        step = 1 if int(target["x"]) > int(stack["x"]) else -1
        for x in range(int(stack["x"]) + step, int(target["x"]), step):
            if _occupied_stack_at(board, x, int(stack["y"])) is not None:
                return False
        return True
    return False


def _move_toward_target(
    board: dict[str, Any],
    stack: dict[str, Any],
    target: dict[str, Any],
) -> bool:
    best_cell = None
    best_distance = _distance(stack, target)
    max_range = int(stack["move_range"])
    for x in range(int(board["width"])):
        for y in range(int(board["height"])):
            candidate_distance = abs(int(stack["x"]) - x) + abs(int(stack["y"]) - y)
            if candidate_distance <= 0 or candidate_distance > max_range:
                continue
            if _is_hero_cell(board, x, y) or _occupied_stack_at(board, x, y) is not None:
                continue
            distance_to_target = abs(x - int(target["x"])) + abs(y - int(target["y"]))
            if distance_to_target < best_distance:
                best_cell = (x, y)
                best_distance = distance_to_target
    if best_cell is None:
        return False
    stack["x"], stack["y"] = best_cell
    return True


def _battle_rule(connection: sqlite3.Connection) -> dict[str, Any]:
    defaults = {
        "grid_width": BOARD_WIDTH,
        "grid_height": BOARD_HEIGHT,
        "turn_timer_seconds": 60,
        "damage_formula": "count_alive*max(1 effective_attack-effective_defense+modifiers)",
        "initiative_tiebreaker": "initiative_desc_tier_desc_seed",
        "timeout_policy": "auto_defend_then_skip",
        "auto_resolve_policy": "repeated_timeout_master_takeover_or_auto_resolve",
    }
    if not _table_exists(connection, "lord_battle_rules"):
        return defaults
    row = connection.execute(
        "SELECT * FROM lord_battle_rules ORDER BY _row_number LIMIT 1"
    ).fetchone()
    if row is None:
        return defaults
    return {
        "grid_width": _to_int(row["grid_width"]) or BOARD_WIDTH,
        "grid_height": _to_int(row["grid_height"]) or BOARD_HEIGHT,
        "turn_timer_seconds": _to_int(row["turn_timer_seconds"]) or 60,
        "damage_formula": str(row["damage_formula"] or defaults["damage_formula"]),
        "initiative_tiebreaker": str(row["initiative_tiebreaker"] or defaults["initiative_tiebreaker"]),
        "timeout_policy": str(row["timeout_policy"] or defaults["timeout_policy"]),
        "auto_resolve_policy": str(row["auto_resolve_policy"] or defaults["auto_resolve_policy"]),
    }


def _claim_for_create(
    connection: sqlite3.Connection,
    claim_id: str | None,
    territory_id: str | None,
) -> sqlite3.Row | None:
    if claim_id:
        row = connection.execute(
            "SELECT * FROM territory_claim_runtime WHERE claim_id = ?",
            (claim_id,),
        ).fetchone()
        if row is None:
            raise LordBattleError("claim_not_found", "Territory claim is not available.", 404)
        return row
    if territory_id:
        return connection.execute(
            """
            SELECT *
            FROM territory_claim_runtime
            WHERE territory_id = ?
              AND status IN ('in_battle', 'contested', 'contested_pending_tick', 'awaiting_garrison', 'capture_pending_garrison')
            ORDER BY created_at
            LIMIT 1
            """,
            (territory_id,),
        ).fetchone()
    return None


def _resolve_domain_id(
    connection: sqlite3.Connection,
    *,
    domain_id: str | None,
    lord_id: str | None,
    label: str,
) -> str:
    if domain_id:
        row = connection.execute(
            "SELECT domain_id FROM domain_runtime_state WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()
    elif lord_id:
        row = connection.execute(
            "SELECT domain_id FROM domain_runtime_state WHERE lord_player_id = ?",
            (lord_id,),
        ).fetchone()
    else:
        raise LordBattleError(f"missing_{label}", f"Missing {label} domain or lord id.")
    if row is None:
        raise LordBattleError(f"{label}_domain_not_found", f"{label.title()} domain is not available.", 404)
    return str(row["domain_id"])


def _territory_context(connection: sqlite3.Connection, territory_id: str | None) -> sqlite3.Row | None:
    if territory_id is None:
        return None
    row = connection.execute(
        """
        SELECT
            t.*,
            COALESCE(r.owner_domain_id, t.owner_domain_id) AS runtime_owner_domain_id,
            COALESCE(
                r.status,
                CASE
                    WHEN t.owner_domain_id IS NULL OR t.owner_domain_id = ''
                    THEN 'neutral'
                    ELSE 'controlled'
                END
            ) AS runtime_status,
            r.contested_by_domain_id
        FROM territories t
        LEFT JOIN territory_runtime_state r ON r.territory_id = t.territory_id
        WHERE t.territory_id = ?
        LIMIT 1
        """,
        (territory_id,),
    ).fetchone()
    if row is None:
        raise LordBattleError("territory_not_found", "Territory is not available.", 404)
    return row


def _assert_attacker_at_territory(
    connection: sqlite3.Connection,
    attacker_domain_id: str,
    territory_id: str,
) -> None:
    current = _domain_current_territory(connection, attacker_domain_id)
    if current and current != territory_id:
        raise LordBattleError(
            "attacker_not_at_territory",
            "Attacking active army must be at the battle territory.",
        )


def _domain_current_territory(connection: sqlite3.Connection, domain_id: str) -> str | None:
    row = connection.execute(
        """
        SELECT n.territory_id
        FROM domain_runtime_state d
        LEFT JOIN map_nodes n ON n.node_id = d.current_node_id
        WHERE d.domain_id = ?
        LIMIT 1
        """,
        (domain_id,),
    ).fetchone()
    return _optional(row["territory_id"]) if row is not None else None


def _territory_for_node(connection: sqlite3.Connection, node_id: str | None) -> str | None:
    if node_id is None:
        return None
    row = connection.execute(
        "SELECT territory_id FROM map_nodes WHERE node_id = ? LIMIT 1",
        (node_id,),
    ).fetchone()
    return _optional(row["territory_id"]) if row is not None else None


def _retreat_node(
    connection: sqlite3.Connection,
    domain_id: str,
    *,
    battle_territory_id: str | None = None,
) -> str | None:
    battle_node = _node_for_territory(connection, battle_territory_id)
    candidates = _retreat_candidates(connection, domain_id, exclude_territory_id=battle_territory_id)
    if battle_node is not None and candidates:
        nearest = _nearest_node_by_route_cost(connection, battle_node, candidates)
        if nearest is not None:
            return nearest
    residence = connection.execute(
        """
        SELECT n.node_id
        FROM territories t
        JOIN map_nodes n ON n.territory_id = t.territory_id
        WHERE t.owner_domain_id = ? AND t.bonus_type = 'residence'
        ORDER BY n._row_number
        LIMIT 1
        """,
        (domain_id,),
    ).fetchone()
    if residence is not None:
        return _optional(residence["node_id"])
    if candidates:
        return candidates[0]
    row = connection.execute(
        """
        SELECT n.node_id
        FROM territory_runtime_state r
        JOIN map_nodes n ON n.territory_id = r.territory_id
        WHERE r.owner_domain_id = ?
        ORDER BY n._row_number
        LIMIT 1
        """,
        (domain_id,),
    ).fetchone()
    return _optional(row["node_id"]) if row is not None else None


def _node_for_territory(connection: sqlite3.Connection, territory_id: str | None) -> str | None:
    if not territory_id:
        return None
    row = connection.execute(
        """
        SELECT node_id
        FROM map_nodes
        WHERE territory_id = ?
        ORDER BY _row_number
        LIMIT 1
        """,
        (territory_id,),
    ).fetchone()
    return _optional(row["node_id"]) if row is not None else None


def _retreat_candidates(
    connection: sqlite3.Connection,
    domain_id: str,
    *,
    exclude_territory_id: str | None,
) -> list[str]:
    rows = connection.execute(
        """
        SELECT n.node_id, t.territory_id
        FROM territories t
        JOIN map_nodes n ON n.territory_id = t.territory_id
        LEFT JOIN territory_runtime_state r ON r.territory_id = t.territory_id
        WHERE COALESCE(NULLIF(r.owner_domain_id, ''), NULLIF(t.owner_domain_id, '')) = ?
          AND (? IS NULL OR t.territory_id != ?)
          AND COALESCE(
                NULLIF(r.status, ''),
                CASE
                    WHEN t.owner_domain_id IS NULL OR t.owner_domain_id = ''
                    THEN 'neutral'
                    ELSE 'controlled'
                END
              ) NOT IN (
                'contested',
                'contested_pending_tick',
                'in_battle',
                'awaiting_garrison',
                'capture_pending_garrison'
              )
        ORDER BY n._row_number
        """,
        (domain_id, exclude_territory_id, exclude_territory_id),
    ).fetchall()
    return [str(row["node_id"]) for row in rows if _optional(row["node_id"])]


def _nearest_node_by_route_cost(
    connection: sqlite3.Connection,
    start_node_id: str,
    candidate_node_ids: list[str],
) -> str | None:
    candidates = set(candidate_node_ids)
    if start_node_id in candidates:
        return start_node_id
    graph: dict[str, list[tuple[str, int]]] = {}
    for edge in connection.execute(
        "SELECT from_node_id, to_node_id, mp_cost, bidirectional FROM map_edges"
    ).fetchall():
        cost = max(1, _to_int(edge["mp_cost"]))
        from_node = str(edge["from_node_id"])
        to_node = str(edge["to_node_id"])
        graph.setdefault(from_node, []).append((to_node, cost))
        if str(edge["bidirectional"]).strip().lower() == "true":
            graph.setdefault(to_node, []).append((from_node, cost))

    distances: dict[str, int] = {start_node_id: 0}
    visited: set[str] = set()
    while True:
        current = min(
            (node for node in distances if node not in visited),
            key=lambda node: distances[node],
            default=None,
        )
        if current is None:
            return None
        if current in candidates:
            return current
        visited.add(current)
        for neighbor, cost in graph.get(current, []):
            next_cost = distances[current] + cost
            if next_cost < distances.get(neighbor, 10**9):
                distances[neighbor] = next_cost


def _state_from_row(row: sqlite3.Row) -> dict[str, Any]:
    board = _normalize_board_start_lines(_json_loads(str(row["board_json"]), {}))
    rule = board.get("rules", {})
    return {
        "battle_id": row["battle_id"],
        "battle_type": row["battle_type"],
        "territory_id": row["territory_id"],
        "claim_id": row["claim_id"],
        "attacker_domain_id": row["attacker_domain_id"],
        "defender_domain_id": row["defender_domain_id"],
        "defender_control": row["defender_control"],
        "status": row["status"],
        "seed": row["seed"],
        "round_number": int(row["round_number"]),
        "active_side": row["active_side"],
        "active_stack_id": row["active_stack_id"],
        "turn_started_at": row["turn_started_at"],
        "timeout_at": row["timeout_at"],
        "timeout_counts": _json_loads(str(row["timeout_counts_json"]), {}),
        "board": board,
        "hero_hp": _json_loads(str(row["hero_hp_json"]), {}),
        "deployment": _json_loads(str(row["deployment_json"]), {}),
        "initiative_order": _json_loads(str(row["initiative_json"]), []),
        "burned_cards": _json_loads(str(row["burned_cards_json"]), []),
        "result": _json_loads(str(row["result_json"]), {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "finished_at": row["finished_at"],
        "target_duration_seconds": int(row["target_duration_seconds"]),
        "auto_resolve_after_seconds": int(row["auto_resolve_after_seconds"]),
        "master_takeover_enabled": bool(row["master_takeover_enabled"]),
        "turn_timer_seconds": int(rule.get("turn_timer_seconds") or 60),
    }


def _turn_timer_due(state: dict[str, Any], now: datetime) -> bool:
    if state["status"] != "active" or not state.get("active_side"):
        return False
    timeout_at = _parse_iso(state.get("timeout_at"))
    return now >= timeout_at


def _start_deployment_timer_for_viewer(
    state: dict[str, Any],
    now: datetime,
    *,
    viewer_domain_id: str | None,
    viewer_role_type: str | None,
) -> bool:
    if state["status"] != "deployment" or viewer_role_type != "lord":
        return False
    if _viewer_side(
        state,
        viewer_domain_id=viewer_domain_id,
        viewer_role_type=viewer_role_type,
    ) is None:
        return False
    return _start_deployment_timer(state, now)


def _start_deployment_timer_for_actor(
    state: dict[str, Any],
    now: datetime,
    *,
    actor_side: str,
    actor_role_type: str | None,
) -> bool:
    if state["status"] != "deployment" or actor_role_type == "npc_master":
        return False
    if actor_side not in {"attacker", "defender"}:
        return False
    return _start_deployment_timer(state, now)


def _start_deployment_timer(state: dict[str, Any], now: datetime) -> bool:
    deployment = state.setdefault("deployment", {})
    if deployment.get("timer_started_at"):
        return False
    deadline = now + timedelta(seconds=DEPLOYMENT_SECONDS)
    deployment["timer_started_at"] = _iso(now)
    deployment["started_at"] = _iso(now)
    deployment["deadline_at"] = _iso(deadline)
    state["timeout_at"] = _iso(deadline)
    return True


def _advance_due_state(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    now: datetime,
    *,
    source: str,
    include_timeouts: bool = True,
    include_neutral_ai: bool = True,
) -> bool:
    changed = False
    if _deployment_timer_due(state, now):
        _finalize_deployment(
            connection,
            state,
            now,
            source=source,
            reason="deployment_timer",
        )
        changed = True

    for _ in range(BOARD_WIDTH * BOARD_HEIGHT):
        if state["status"] in FINAL_BATTLE_STATES:
            break
        winner_side = _winner_from_state(state) if state["status"] == "active" else None
        if winner_side:
            _finish_battle(
                connection,
                state,
                winner_side=winner_side,
                outcome="state_check",
                now=now,
                source=source,
            )
            changed = True
            break
        if (
            include_neutral_ai
            and state["status"] == "active"
            and state.get("defender_control") == "neutral_ai"
            and state.get("active_side") == "defender"
        ):
            _apply_ai_turn(connection, state, "defender", now, source=source)
            changed = True
            continue
        if include_timeouts and _turn_timer_due(state, now):
            _apply_timeout(
                connection,
                state,
                str(state["active_side"]),
                now,
                source=source,
            )
            changed = True
            continue
        break
    return changed


def _deployment_timer_due(state: dict[str, Any], now: datetime) -> bool:
    if state["status"] != "deployment":
        return False
    if not state.get("deployment", {}).get("timer_started_at"):
        return False
    deadline_at = _optional(state.get("deployment", {}).get("deadline_at")) or state.get("timeout_at")
    return now >= _parse_iso(deadline_at)


def _save_state(connection: sqlite3.Connection, state: dict[str, Any], now: datetime) -> None:
    connection.execute(
        """
        UPDATE lord_battles
        SET defender_control = ?,
            status = ?,
            round_number = ?,
            active_side = ?,
            active_stack_id = ?,
            turn_started_at = ?,
            timeout_at = ?,
            timeout_counts_json = ?,
            board_json = ?,
            hero_hp_json = ?,
            deployment_json = ?,
            initiative_json = ?,
            burned_cards_json = ?,
            result_json = ?,
            updated_at = ?,
            finished_at = ?
        WHERE battle_id = ?
        """,
        (
            state["defender_control"],
            state["status"],
            state["round_number"],
            state["active_side"],
            state["active_stack_id"],
            state["turn_started_at"],
            state["timeout_at"],
            _json_dumps(state["timeout_counts"]),
            _json_dumps(state["board"]),
            _json_dumps(state["hero_hp"]),
            _json_dumps(state["deployment"]),
            _json_dumps(state["initiative_order"]),
            _json_dumps(state["burned_cards"]),
            _json_dumps(state["result"]),
            _iso(now),
            state.get("finished_at"),
            state["battle_id"],
        ),
    )


def _battle_payload(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    include_log: bool = True,
    include_queue: bool = True,
    viewer_domain_id: str | None = None,
    viewer_role_type: str | None = None,
) -> dict[str, Any]:
    payload = _state_payload(
        connection,
        _state_from_row(row),
        include_log=include_log,
        viewer_domain_id=viewer_domain_id,
        viewer_role_type=viewer_role_type,
    )
    if include_queue:
        payload.update(_lord_battle_queue_annotations(connection).get(str(row["battle_id"]), {}))
    return payload


def _state_payload(
    connection: sqlite3.Connection,
    state: dict[str, Any],
    *,
    include_log: bool = True,
    viewer_domain_id: str | None = None,
    viewer_role_type: str | None = None,
) -> dict[str, Any]:
    created_at = _parse_iso(state["created_at"])
    finished_at = _parse_iso(state["finished_at"]) if state.get("finished_at") else datetime.now(UTC)
    elapsed = max(0, int((finished_at - created_at).total_seconds()))
    board = deepcopy(state["board"])
    deployment = deepcopy(state["deployment"])
    initiative_order = list(state["initiative_order"])
    visibility = _apply_payload_visibility(
        state,
        board,
        deployment,
        initiative_order,
        viewer_domain_id=viewer_domain_id,
        viewer_role_type=viewer_role_type,
    )
    payload = {
        "battle_id": state["battle_id"],
        "battle_type": state["battle_type"],
        "territory_id": state["territory_id"],
        "claim_id": state["claim_id"],
        "attacker_domain_id": state["attacker_domain_id"],
        "defender_domain_id": state["defender_domain_id"],
        "defender_control": state["defender_control"],
        "status": state["status"],
        "seed": state["seed"],
        "round_number": state["round_number"],
        "active_side": state["active_side"],
        "active_stack_id": state["active_stack_id"],
        "turn_started_at": state["turn_started_at"],
        "timeout_at": state["timeout_at"],
        "timeout_counts": state["timeout_counts"],
        "board": board,
        "hero_hp": state["hero_hp"],
        "deployment": deployment,
        "initiative_order": initiative_order,
        "burned_cards": state["burned_cards"],
        "result": state["result"],
        "auto_resolve": _auto_resolve_vote_payload(state),
        "visibility": visibility,
        "created_at": state["created_at"],
        "updated_at": state["updated_at"],
        "finished_at": state["finished_at"],
        "duration_report": {
            "elapsed_seconds": elapsed,
            "target_duration_seconds": state["target_duration_seconds"],
            "auto_resolve_after_seconds": state["auto_resolve_after_seconds"],
            "over_target": elapsed > state["target_duration_seconds"],
            "auto_resolve_path_available": True,
        },
    }
    if include_log:
        payload["battle_log"] = _battle_log(connection, state["battle_id"])
    return payload


def _viewer_side(
    state: dict[str, Any],
    *,
    viewer_domain_id: str | None,
    viewer_role_type: str | None,
) -> str | None:
    if viewer_role_type == "npc_master":
        return None
    if viewer_domain_id == state["attacker_domain_id"]:
        return "attacker"
    if viewer_domain_id and viewer_domain_id == state.get("defender_domain_id"):
        return "defender"
    return None


def _apply_payload_visibility(
    state: dict[str, Any],
    board: dict[str, Any],
    deployment: dict[str, Any],
    initiative_order: list[str],
    *,
    viewer_domain_id: str | None,
    viewer_role_type: str | None,
) -> dict[str, Any]:
    viewer_side = _viewer_side(
        state,
        viewer_domain_id=viewer_domain_id,
        viewer_role_type=viewer_role_type,
    )
    visibility = {
        "viewer_side": viewer_side,
        "enemy_deployment_hidden": False,
    }
    if state["status"] != "deployment" or viewer_role_type == "npc_master":
        return visibility
    visibility["enemy_deployment_hidden"] = True
    visible_side = viewer_side
    board["stacks"] = [
        stack for stack in board.get("stacks", []) if stack.get("side") == visible_side
    ]
    initiative_order.clear()
    for side in ("attacker", "defender"):
        if side == visible_side:
            continue
        deployment.setdefault("hand", {})[side] = []
        deployment.setdefault("deployed", {})[side] = []
        deployment.setdefault("undeployed", {})[side] = []
    return visibility


def _auto_resolve_votes(state: dict[str, Any]) -> dict[str, Any]:
    result = state.setdefault("result", {})
    votes = result.setdefault("auto_resolve_votes", {"sides": []})
    if not isinstance(votes, dict):
        votes = {"sides": []}
        result["auto_resolve_votes"] = votes
    sides = votes.setdefault("sides", [])
    if not isinstance(sides, list):
        votes["sides"] = []
    return votes


def _auto_resolve_vote_payload(state: dict[str, Any]) -> dict[str, Any]:
    required = 2 if state.get("battle_type") == "lord_vs_lord" else 1
    votes = _auto_resolve_votes(state) if state["status"] not in FINAL_BATTLE_STATES else {}
    sides = sorted(str(side) for side in votes.get("sides", []) if str(side) in {"attacker", "defender"})
    return {
        "required": required,
        "count": len(sides),
        "sides": sides,
        "label": f"Авторасчет {len(sides)}/{required}",
        "confirmed": len(sides) >= required,
    }


def _battle_log(connection: sqlite3.Connection, battle_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT log_id, battle_id, round_number, actor_side, entry_type, payload_json, created_at
        FROM lord_battle_log
        WHERE battle_id = ?
        ORDER BY log_id
        """,
        (battle_id,),
    ).fetchall()
    return [
        {
            "log_id": row["log_id"],
            "battle_id": row["battle_id"],
            "round_number": row["round_number"],
            "actor_side": row["actor_side"],
            "entry_type": row["entry_type"],
            "payload": _json_loads(str(row["payload_json"]), {}),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _append_log(
    connection: sqlite3.Connection,
    battle_id: str,
    *,
    round_number: int,
    actor_side: str | None,
    entry_type: str,
    payload: dict[str, Any],
    now: datetime,
) -> None:
    connection.execute(
        """
        INSERT INTO lord_battle_log (
            battle_id, round_number, actor_side, entry_type, payload_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (battle_id, round_number, actor_side, entry_type, _json_dumps(payload), _iso(now)),
    )


def _fetch_battle(connection: sqlite3.Connection, battle_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM lord_battles WHERE battle_id = ?",
        (battle_id,),
    ).fetchone()


def _fetch_battle_required(connection: sqlite3.Connection, battle_id: str) -> sqlite3.Row:
    row = _fetch_battle(connection, battle_id)
    if row is None:
        raise LordBattleError("battle_not_found", "Lord battle is not available.", 404)
    return row


def _assert_actor_allowed(
    state: dict[str, Any],
    actor_side: str,
    actor_domain_id: str | None,
    actor_role_type: str | None,
) -> None:
    if actor_role_type == "npc_master":
        return
    if not actor_domain_id:
        raise LordBattleError("missing_actor_token", "Lord battle action requires a role token.", 401)
    expected = _domain_for_side(state, actor_side)
    if expected is None:
        raise LordBattleError("master_required", "Only a master can control this battle side.", 403)
    if actor_domain_id != expected:
        raise LordBattleError("wrong_actor_domain", "Actor domain cannot control this battle side.", 403)


def _assert_create_actor_allowed(
    attacker_domain_id: str,
    actor_domain_id: str | None,
    actor_role_type: str | None,
    *,
    defender_domain_id: str | None = None,
    allow_defender_actor: bool = False,
) -> None:
    if actor_role_type == "npc_master":
        return
    if not actor_domain_id:
        raise LordBattleError("missing_actor_token", "Lord battle creation requires a role token.", 401)
    allowed_domain_ids = {attacker_domain_id}
    if allow_defender_actor and defender_domain_id:
        allowed_domain_ids.add(defender_domain_id)
    if actor_domain_id not in allowed_domain_ids:
        raise LordBattleError("wrong_actor_domain", "Actor domain cannot create this battle.", 403)


def _require_active_actor_stack(
    state: dict[str, Any],
    actor_side: str,
    requested_stack_id: object,
) -> dict[str, Any]:
    if actor_side != state["active_side"]:
        raise LordBattleError("not_active_side", "Only the active side can act.")
    stack = _active_stack(state)
    if requested_stack_id and str(requested_stack_id) != stack["stack_id"]:
        raise LordBattleError("not_active_stack", "Only the active stack can act.")
    if stack["side"] != actor_side:
        raise LordBattleError("wrong_stack_side", "Active stack belongs to another side.")
    return stack


def _active_stack(state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("active_stack_id"):
        raise LordBattleError("no_active_stack", "Battle has no active stack.")
    return _stack_by_id(state["board"], state["active_stack_id"])


def _stack_by_id(board: dict[str, Any], stack_id: str | None) -> dict[str, Any]:
    for stack in board["stacks"]:
        if stack["stack_id"] == stack_id:
            return stack
    raise LordBattleError("stack_not_found", "Battle stack is not available.", 404)


def _alive_stacks(board: dict[str, Any], side: str | None = None) -> list[dict[str, Any]]:
    return [
        stack
        for stack in board["stacks"]
        if _is_alive(stack) and (side is None or stack["side"] == side)
    ]


def _nearest_enemy_stack(board: dict[str, Any], stack: dict[str, Any]) -> dict[str, Any] | None:
    enemies = _alive_stacks(board, _enemy_side(stack["side"]))
    if not enemies:
        return None
    return sorted(enemies, key=lambda enemy: (_distance(stack, enemy), enemy["stack_id"]))[0]


def _occupied_stack_at(board: dict[str, Any], x: int, y: int) -> dict[str, Any] | None:
    for stack in board["stacks"]:
        if _is_alive(stack) and int(stack["x"]) == x and int(stack["y"]) == y:
            return stack
    return None


def _is_hero_cell(board: dict[str, Any], x: int, y: int) -> bool:
    return any(int(cell["x"]) == x and int(cell["y"]) == y for cell in board["hero_cells"].values())


def _distance(a: dict[str, Any], b: dict[str, Any]) -> int:
    return abs(int(a["x"]) - int(b["x"])) + abs(int(a["y"]) - int(b["y"]))


def _is_alive(stack: dict[str, Any]) -> bool:
    return int(stack.get("count_alive", 0)) > 0


def _unit_power(stack: dict[str, Any]) -> int:
    unit_class = str(stack.get("unit_class") or "")
    return (
        int(stack["attack"])
        + int(stack["defense"])
        + int(stack["hp"])
        + int(stack["tier"])
        + UNIT_CLASS_POWER_BONUS.get(unit_class, 0)
    )


def _domain_for_side(state: dict[str, Any], side: str) -> str | None:
    if side == "attacker":
        return state["attacker_domain_id"]
    return state["defender_domain_id"]


def _enemy_side(side: str) -> str:
    return "defender" if side == "attacker" else "attacker"


def _side_name(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"attacker", "defender"}:
        raise LordBattleError("invalid_side", "Battle side must be attacker or defender.")
    return normalized


def _stable_seed(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _deterministic_int(*parts: str, modulus: int | None = None) -> int:
    value = int(hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12], 16)
    return value % modulus if modulus else value


def _parse_iso(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _to_int(value: object) -> int:
    if value is None or str(value) == "":
        return 0
    return int(value)


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
