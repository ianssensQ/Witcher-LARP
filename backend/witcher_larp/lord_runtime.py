"""Mutable lord strategy runtime services."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from .asset_service import AssetContractError
from .asset_service import grant_asset_ownership
from .asset_service import reward_asset_entries, reward_numeric_payload
from .building_effects import ADDRESSED_ORDER_BUILDING_ID
from .building_effects import ALCHEMY_LAB_BUILDING_ID
from .building_effects import ALCHEMY_RAID_DURATION_REDUCTION_MINUTES
from .building_effects import BANK_BUILDING_ID, BANK_LOOT_REDUCTION_PERCENT
from .building_effects import MAGE_STUDY_BUILDING_ID
from .building_effects import MAGE_STUDY_RESIDENCE_DEFENSE_BONUS
from .building_effects import PUBLIC_ORDER_BUILDING_ID
from .building_effects import RITUAL_CHAMBER_BUILDING_ID, RITUAL_CLEANSE_CHARGE_CAP
from .building_effects import flat_income_bonus, stock_cap_percent
from .building_effects import territory_income_bonus_percent
from .building_effects import treasury_income_floor_percent
from .content_schema import split_ids
from .runtime_schema import ensure_runtime_schema, log_event
from .stats import CANONICAL_STATS, DEFAULT_STAT_ID
from .territory_bonuses import controlled_domain_numeric_bonus
from .territory_bonuses import controlled_domain_recruit_card_ids
from .territory_bonuses import territory_numeric_bonus
from .timer_service import ensure_runtime_content_state
from .xp_service import spend_xp_for_levels


ACTIVE_ORDER_STATUSES = {
    "published",
    "addressed_pending",
    "accepted",
    "in_progress",
    "claimed_at_prop",
    "submitted_pending_sync",
    "pending_master_approval",
    "failed_retryable",
    "contested_review",
}
CANCELLABLE_ORDER_STATUSES = {
    "draft",
    "published",
    "addressed_pending",
    "accepted",
    "failed_retryable",
}
CLOSED_ORDER_STATUSES = {
    "completed",
    "failed_closed",
    "cancelled_by_lord",
    "expired",
    "cancelled",
    "failed",
    "rejected",
    "resolved",
}
FINAL_LOCK_ORDER_OVERRIDE_SOURCES = {
    "master_api",
    "master_override",
    "paper_recovered",
    "paper_final_evidence",
}
LORD_ORDER_MANAGEMENT_ACTIONS = {
    "create",
    "start",
    "cancel",
    "expire",
    "fail_closed",
    "fail_retryable",
    "contested_review",
}
PLAYER_ORDER_ACTIONS = {"accept", "submit_success"}
MASTER_ORDER_ACTIONS = {"complete"}
ARMY_UNIT_CLASS_POWER_BONUS = {
    "infantry": 0,
    "guard": 4,
    "ranged": 4,
    "cavalry": 10,
    "heavy_siege": 16,
    "specialist": 8,
}
ORDER_MASTER_RECOVERY_SOURCES = {
    "master_api",
    "master_override",
    "paper_recovered",
    "paper_order_resolution",
    "paper_final_evidence",
}
LOCKED_GARRISON_TRANSFER_STATUSES = {
    "in_battle",
    "contested",
    "contested_pending_tick",
    "capture_pending_garrison",
    "awaiting_garrison",
}
BATTLE_REQUIRED_CLAIM_STATUSES = {"in_battle", "contested", "contested_pending_tick"}
GARRISON_PENDING_CLAIM_STATUSES = {"awaiting_garrison", "capture_pending_garrison"}
BLOCKING_ROUTE_STATUSES = {
    "in_battle",
    "contested",
    "contested_pending_tick",
    "capture_pending_garrison",
    "awaiting_garrison",
}
LORD_MOVE_SECONDS_PER_EDGE = 1
FRONT_LOCKED_ROUTE_MESSAGE = (
    "Army is already on a neutral, foreign, or contested front; resolve that front "
    "or return to controlled territory before moving to another front."
)
DEFAULT_ACTIVE_ARMY_STACK_CAPACITY = 5
BASE_RAID_TOKEN_CAP = 1
RAID_TOKEN_REFILL_PER_TICK = 1
RAID_GARRISON_POWER_WEAK_THRESHOLD = 20
RAID_GARRISON_POWER_STRONG_THRESHOLD = 55
RAID_GARRISON_POWER_HARD_THRESHOLD = 95
RAID_RESIDENCE_BASE_DEFENSE = 1
RAID_TERRITORY_WARD_DEFENSE = 1
RAID_RESIDENCE_WARD_DEFENSE = 2
MAP_INTEL_LEVELS = {
    "presence": 0,
    "owner": 1,
    "domain": 1,
    "rough_strength": 2,
    "composition": 3,
}
CLEAN_REGISTRATION_FLAG = "clean_registration_start"

TERRITORY_BUILDING_TREE_IDS = {
    "defense": ["b_training_yard", "b_barracks", "b_wards"],
    "gold_income": ["b_market", "b_tax_office", "b_storehouse"],
    "recruit": ["b_training_yard", "b_barracks", "b_archery_range", "b_stables"],
    "order": ["b_notice_board", "b_envoy_hall", "b_map_room"],
    "magic": ["b_mage_study", "b_alchemy_lab", "b_wards"],
    "resource": ["b_market", "b_storehouse", "b_bank"],
    "research": ["b_map_room", "b_scrying_room"],
    "artifact": ["b_scrying_room", "b_alchemy_lab"],
    "special": ["b_map_room", "b_scrying_room", "b_wards"],
    "raid_cover": ["b_wards", "b_raid_office"],
    "visibility": ["b_map_room", "b_scrying_room"],
}

BUILDING_RECRUIT_INITIAL_STOCK_BY_CLASS = {
    "infantry": 24,
    "guard": 12,
    "ranged": 12,
    "cavalry": 4,
    "heavy_siege": 2,
    "specialist": 3,
}
BUILDING_RECRUIT_GROWTH_PER_HOUR_BY_CLASS = {
    "infantry": 24,
    "guard": 12,
    "ranged": 12,
    "cavalry": 4,
    "heavy_siege": 2,
    "specialist": 3,
}
BASE_RECRUIT_STOCK_CAP_TICKS = 2


class LordRuntimeError(ValueError):
    """Raised when a lord action fails a runtime rule."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def ensure_lord_runtime_state(connection: sqlite3.Connection) -> None:
    """Copy imported seed state into mutable tables without overwriting play state."""

    ensure_runtime_schema(connection)
    ensure_runtime_content_state(connection)
    now = _iso()
    clean_registration_start = _clean_registration_start_enabled(connection)

    if _table_exists(connection, "territories"):
        for row in connection.execute(
            """
            SELECT territory_id, owner_domain_id
            FROM territories
            ORDER BY _row_number
            """
        ).fetchall():
            owner = _optional(row["owner_domain_id"])
            connection.execute(
                """
                INSERT INTO territory_runtime_state (
                    territory_id, owner_domain_id, status, controlled_since, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(territory_id) DO NOTHING
                """,
                (
                    row["territory_id"],
                    owner,
                    "controlled" if owner else "neutral",
                    now if owner else None,
                    now,
                ),
            )

    _backfill_domain_building_territories(connection)

    if not clean_registration_start and _table_exists(connection, "garrisons"):
        for row in connection.execute(
            """
            SELECT garrison_id, territory_id, domain_id, card_id, count, status
            FROM garrisons
            ORDER BY _row_number
            """
        ).fetchall():
            connection.execute(
                """
                INSERT INTO garrison_runtime_state (
                    garrison_id, territory_id, domain_id, card_id, count, status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(garrison_id) DO NOTHING
                """,
                (
                    row["garrison_id"],
                    row["territory_id"],
                    row["domain_id"],
                    row["card_id"],
                    _to_int(row["count"]),
                    row["status"] or "active",
                    now,
                ),
            )

    if not clean_registration_start and _table_exists(connection, "territory_claims"):
        for row in connection.execute(
            """
            SELECT claim_id, territory_id, claimant_domain_id, status, source
            FROM territory_claims
            ORDER BY _row_number
            """
        ).fetchall():
            connection.execute(
                """
                INSERT INTO territory_claim_runtime (
                    claim_id, territory_id, claimant_domain_id, defender_domain_id,
                    status, source, created_at, battle_required
                )
                VALUES (?, ?, ?, NULL, ?, ?, ?, ?)
                ON CONFLICT(claim_id) DO NOTHING
                """,
                (
                    row["claim_id"],
                    row["territory_id"],
                    row["claimant_domain_id"],
                    row["status"] or "controlled",
                    row["source"] or "seed",
                    now,
                    0 if row["status"] == "controlled" else 1,
                ),
            )

    if _table_exists(connection, "recruit_markets"):
        for row in connection.execute(
            """
            SELECT offer_id, domain_id, card_id, cost, status
            FROM recruit_markets
            ORDER BY _row_number
            """
        ).fetchall():
            connection.execute(
                """
                INSERT INTO recruit_offer_runtime (
                    offer_id, domain_id, card_id, cost, status, source, held_by_domain_id, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'seed', ?, ?)
                ON CONFLICT(offer_id) DO NOTHING
                """,
                (
                    row["offer_id"],
                    row["domain_id"],
                    row["card_id"],
                    _to_int(row["cost"]),
                    row["status"] or "available",
                    row["domain_id"] if row["status"] == "held" else None,
                    now,
                ),
            )

    if not clean_registration_start and _table_exists(connection, "army_reserves"):
        for row in connection.execute(
            """
            SELECT reserve_id, domain_id, card_id, count, status
            FROM army_reserves
            ORDER BY _row_number
            """
        ).fetchall():
            connection.execute(
                """
                INSERT INTO army_reserve_runtime (
                    reserve_id, domain_id, card_id, count, status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(reserve_id) DO NOTHING
                """,
                (
                    row["reserve_id"],
                    row["domain_id"],
                    row["card_id"],
                    _to_int(row["count"]),
                    row["status"] or "available",
                    now,
                ),
            )

    if not clean_registration_start and _table_exists(connection, "orders"):
        for row in connection.execute(
            """
            SELECT order_id, lord_id, target_player_id, object_id, visibility, status, escrow_reward_id
            FROM orders
            ORDER BY _row_number
            """
        ).fetchall():
            connection.execute(
                """
                INSERT INTO order_runtime_state (
                    order_id, lord_id, target_player_id, object_id, visibility,
                    status, escrow_reward_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(order_id) DO NOTHING
                """,
                (
                    row["order_id"],
                    row["lord_id"],
                    _optional(row["target_player_id"]),
                    row["object_id"],
                    row["visibility"] or "public",
                    row["status"] or "published",
                    _optional(row["escrow_reward_id"]),
                    now,
                    now,
                ),
            )
            if row["escrow_reward_id"] and (
                row["status"] or "published"
            ) in _order_statuses_counting_against_cap(connection):
                _reserve_order_escrow(
                    connection,
                    str(row["order_id"]),
                    lord_id=str(row["lord_id"]),
                    reward_id=str(row["escrow_reward_id"]),
                    debit_domain=False,
                    now=now,
                )

    _initialize_domain_locations(connection, now)
    _ensure_minimum_active_army_stack_capacity(connection, now)
    reconcile_raid_token_caps(connection, now=now)
    reconcile_raid_effects(connection)


def move_lord(
    connection: sqlite3.Connection,
    lord_id: str,
    *,
    to_node_id: str | None = None,
    route_node_ids: list[str] | None = None,
    expected_cost: int | None = None,
    source: str = "lord_panel",
) -> dict[str, Any]:
    ensure_lord_runtime_state(connection)
    domain = _domain_for_lord(connection, lord_id)
    reconcile_pending_lord_moves(connection, domain_id=str(domain["domain_id"]))
    domain = _domain_for_lord(connection, lord_id)
    if active_pending_lord_move(connection, str(domain["domain_id"])) is not None:
        raise LordRuntimeError(
            "pending_move_active",
            "Active army is already moving; wait for arrival before moving again.",
        )
    current_node_id = domain["current_node_id"] or _residence_node(connection, domain["domain_id"])
    if current_node_id is None:
        raise LordRuntimeError("missing_residence", "Lord domain has no residence node.")

    requested_to_node_id = to_node_id or next(
        (node for node in reversed(route_node_ids or []) if node),
        None,
    )
    if requested_to_node_id is None:
        raise LordRuntimeError("missing_route", "Movement requires a target node or route.")
    if requested_to_node_id == current_node_id:
        raise LordRuntimeError("already_at_target", "Lord army is already at the target node.")

    route = _planned_movement_route(
        connection,
        domain_id=str(domain["domain_id"]),
        current_node_id=current_node_id,
        requested_to_node_id=requested_to_node_id,
        route_node_ids=route_node_ids,
    )
    cost = _route_cost(connection, route)
    if expected_cost is not None and expected_cost != cost:
        raise LordRuntimeError(
            "route_cost_mismatch",
            f"Server route costs {cost} MP, not {expected_cost}.",
        )
    current_mp = _to_int(domain["current_mp"])
    if cost > current_mp:
        raise LordRuntimeError(
            "insufficient_mp",
            f"Route costs {cost} MP, but domain has {current_mp}.",
        )

    target_node_id = route[-1]
    front_lock_reason = _front_locked_movement_reason(
        connection,
        str(domain["domain_id"]),
        current_node_id=current_node_id,
        target_node_id=target_node_id,
    )
    if front_lock_reason is not None:
        raise LordRuntimeError("front_locked", front_lock_reason)
    if _movement_requires_active_army(connection, str(domain["domain_id"]), target_node_id):
        if not _active_army_at_node(connection, str(domain["domain_id"]), current_node_id):
            raise LordRuntimeError(
                "missing_active_army",
                "Contesting or capturing territory requires an active army at the moving node.",
            )

    now_dt = datetime.now(UTC)
    now = _iso(now_dt)
    arrival_at = _iso(now_dt + timedelta(seconds=_movement_duration_seconds(route)))
    move_id = f"move_{uuid4().hex}"
    connection.execute(
        """
        UPDATE domain_runtime_state
        SET current_mp = current_mp - ?, updated_at = ?
        WHERE domain_id = ?
        """,
        (cost, now, domain["domain_id"]),
    )
    connection.execute(
        """
        INSERT INTO pending_lord_moves (
            move_id, domain_id, lord_id, from_node_id, to_node_id,
            requested_to_node_id, route_node_ids_json, mp_cost, status,
            source, started_at, arrival_at, result_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, '{}')
        """,
        (
            move_id,
            domain["domain_id"],
            lord_id,
            current_node_id,
            target_node_id,
            requested_to_node_id,
            json.dumps(route, ensure_ascii=True),
            cost,
            source,
            now,
            arrival_at,
        ),
    )

    pending_move = {
        "move_id": move_id,
        "domain_id": domain["domain_id"],
        "lord_id": lord_id,
        "from_node_id": current_node_id,
        "to_node_id": target_node_id,
        "requested_to_node_id": requested_to_node_id,
        "route": route,
        "mp_spent": cost,
        "current_mp": current_mp - cost,
        "started_at": now,
        "arrival_at": arrival_at,
        "status": "pending",
    }
    result = {
        "status": "pending_move",
        "pending_move": pending_move,
        "domain_id": domain["domain_id"],
        "from_node_id": current_node_id,
        "to_node_id": target_node_id,
        "requested_to_node_id": requested_to_node_id,
        "route": route,
        "mp_spent": cost,
        "current_mp": current_mp - cost,
        "battle_spent_mp": 0,
        "claim": None,
    }
    log_event(connection, "lord_move_started", result, source=source)
    return result


def preview_lord_route(
    connection: sqlite3.Connection,
    lord_id: str,
    *,
    to_node_id: str | None = None,
    route_node_ids: list[str] | None = None,
    source: str = "lord_panel",
) -> dict[str, Any]:
    """Return the server-authoritative map route before mutating movement state."""

    ensure_lord_runtime_state(connection)
    domain = _domain_for_lord(connection, lord_id)
    domain_id = str(domain["domain_id"])
    current_node_id = domain["current_node_id"] or _residence_node(connection, domain_id)
    current_mp = _to_int(domain["current_mp"])
    requested_to_node_id = to_node_id or next(
        (node for node in reversed(route_node_ids or []) if node),
        None,
    )
    base_payload: dict[str, Any] = {
        "status": "blocked",
        "can_move": False,
        "domain_id": domain_id,
        "lord_id": lord_id,
        "from_node_id": current_node_id,
        "to_node_id": None,
        "requested_to_node_id": requested_to_node_id,
        "route": [],
        "mp_cost": 0,
        "mp_available": current_mp,
        "source": source,
    }
    if current_node_id is None:
        return {
            **base_payload,
            "reason_code": "missing_residence",
            "reason": "Lord domain has no residence node.",
        }
    pending = active_pending_lord_move(connection, domain_id)
    if pending is not None:
        return {
            **base_payload,
            "reason_code": "pending_move_active",
            "reason": "Active army is already moving; wait for arrival before moving again.",
            "pending_move": pending,
        }
    if requested_to_node_id is None:
        return {
            **base_payload,
            "reason_code": "missing_route",
            "reason": "Movement requires a target node or route.",
        }
    if requested_to_node_id == current_node_id:
        return {
            **base_payload,
            "to_node_id": current_node_id,
            "route": [current_node_id],
            "reason_code": "already_at_target",
            "reason": "Lord army is already at the target node.",
        }

    route = _planned_movement_route(
        connection,
        domain_id=domain_id,
        current_node_id=current_node_id,
        requested_to_node_id=requested_to_node_id,
        route_node_ids=route_node_ids,
    )
    cost = _route_cost(connection, route)
    target_node_id = route[-1]
    arrival_at = _iso(datetime.now(UTC) + timedelta(seconds=_movement_duration_seconds(route)))
    front_lock_reason = _front_locked_movement_reason(
        connection,
        domain_id,
        current_node_id=current_node_id,
        target_node_id=target_node_id,
    )
    requires_active_army = _movement_requires_active_army(connection, domain_id, target_node_id)
    active_army_ready = (
        not requires_active_army
        or _active_army_at_node(connection, domain_id, current_node_id)
    )
    affordable = cost <= current_mp
    stopped = target_node_id != requested_to_node_id
    reason_code = None
    reason = None
    if stopped:
        reason_code = "route_stopped_at_front"
        reason = "Route stops at the first neutral, foreign, or contested territory."
    if not affordable:
        reason_code = "insufficient_mp"
        reason = f"Route costs {cost} MP, but domain has {current_mp}."
    if not active_army_ready:
        reason_code = "missing_active_army"
        reason = "Contesting or capturing territory requires an active army at the moving node."
    if front_lock_reason is not None:
        reason_code = "front_locked"
        reason = front_lock_reason

    return {
        "status": "blocked" if reason_code in {"insufficient_mp", "missing_active_army", "front_locked"} else (
            "stopped" if stopped else "ready"
        ),
        "can_move": affordable and active_army_ready and front_lock_reason is None,
        "domain_id": domain_id,
        "lord_id": lord_id,
        "from_node_id": current_node_id,
        "to_node_id": target_node_id,
        "requested_to_node_id": requested_to_node_id,
        "route": route,
        "mp_cost": cost,
        "mp_available": current_mp,
        "arrival_at": arrival_at,
        "arrival_seconds": _movement_duration_seconds(route),
        "affordable": affordable,
        "requires_active_army": requires_active_army,
        "active_army_ready": active_army_ready,
        "reason_code": reason_code,
        "reason": reason,
        "outcome": _movement_outcome_preview(connection, domain_id, target_node_id),
        "source": source,
    }


def transfer_garrison(
    connection: sqlite3.Connection,
    lord_id: str,
    *,
    territory_id: str,
    card_id: str | None = None,
    stack_id: str | None = None,
    target_stack_id: str | None = None,
    army_id: str | None = None,
    target_army_id: str | None = None,
    garrison_id: str | None = None,
    target_garrison_id: str | None = None,
    count: int = 1,
    operation: str = "garrison",
    source: str = "lord_panel",
) -> dict[str, Any]:
    ensure_lord_runtime_state(connection)
    if count <= 0:
        raise LordRuntimeError("invalid_count", "Transfer count must be positive.")
    domain = _domain_for_lord(connection, lord_id)
    reconcile_pending_lord_moves(connection, domain_id=str(domain["domain_id"]))
    domain = _domain_for_lord(connection, lord_id)
    if active_pending_lord_move(connection, str(domain["domain_id"])) is not None:
        raise LordRuntimeError(
            "pending_move_active",
            "Active army is moving and cannot transfer units until arrival.",
        )

    source_stack_id = stack_id or army_id or garrison_id
    target_stack_id = target_stack_id or target_army_id or target_garrison_id
    if operation == "split_active":
        return _split_active_army_stack(
            connection,
            domain_id=str(domain["domain_id"]),
            territory_id=territory_id,
            army_id=_required_stack_id(source_stack_id),
            count=count,
            source=source,
        )
    if operation == "split_garrison":
        return _split_garrison_stack(
            connection,
            domain_id=str(domain["domain_id"]),
            territory_id=territory_id,
            garrison_id=_required_stack_id(source_stack_id),
            count=count,
            source=source,
        )
    if operation == "merge_active":
        return _merge_active_army_stacks(
            connection,
            domain_id=str(domain["domain_id"]),
            territory_id=territory_id,
            source_army_id=_required_stack_id(source_stack_id),
            target_army_id=_required_stack_id(target_stack_id),
            source=source,
        )
    if operation == "merge_garrison":
        return _merge_garrison_stacks(
            connection,
            domain_id=str(domain["domain_id"]),
            territory_id=territory_id,
            source_garrison_id=_required_stack_id(source_stack_id),
            target_garrison_id=_required_stack_id(target_stack_id),
            source=source,
        )

    if operation == "reserve_to_active":
        card_id = _required_card_id(card_id)
        return _transfer_reserve_to_active(
            connection,
            domain_id=str(domain["domain_id"]),
            territory_id=territory_id,
            card_id=card_id,
            count=count,
            source=source,
        )
    if operation not in {"garrison", "active_to_fort", "fort_to_active"}:
        raise LordRuntimeError(
            "unknown_garrison_operation",
            "Garrison operation must be reserve_to_active, active_to_fort, fort_to_active, split_active, split_garrison, merge_active or merge_garrison.",
        )
    if not source_stack_id:
        card_id = _required_card_id(card_id)

    domain_id = str(domain["domain_id"])
    territory = _territory_state(connection, territory_id)
    territory_owner = _optional(territory["owner_domain_id"])
    territory_status = str(territory["status"])
    capture_claim = None
    now = _iso()

    if operation == "fort_to_active":
        _assert_local_owned_transfer_territory(connection, domain_id, territory)
        capacity = _to_int(domain["active_army_capacity"])
        if source_stack_id:
            if target_stack_id:
                card_id, target = _transfer_garrison_stack_to_active_army_stack(
                    connection,
                    domain_id=domain_id,
                    territory_id=territory_id,
                    source_garrison_id=_required_stack_id(source_stack_id),
                    target_army_id=_required_stack_id(target_stack_id),
                    count=count,
                    now=now,
                )
            else:
                _assert_active_army_new_stack_capacity_available(
                    connection, domain_id, capacity
                )
                _garrison_stack(
                    connection,
                    domain_id,
                    territory_id,
                    _required_stack_id(source_stack_id),
                )
                consumed = _consume_garrison_stack(
                    connection,
                    domain_id,
                    territory_id,
                    _required_stack_id(source_stack_id),
                    count,
                    now,
                )
                card_id = str(consumed["card_id"])
                target = _insert_active_army_stack(
                    connection,
                    domain_id=domain_id,
                    territory_id=territory_id,
                    card_id=card_id,
                    count=count,
                    now=now,
                )
        else:
            _assert_active_army_stack_capacity_available(
                connection, domain_id, card_id, capacity
            )
            _consume_garrison(connection, domain_id, territory_id, card_id, count, now)
            target = _upsert_active_army(
                connection,
                domain_id=domain_id,
                territory_id=territory_id,
                card_id=card_id,
                count=count,
                now=now,
            )
        result = {
            "status": "active_army_updated",
            "domain_id": domain_id,
            "territory_id": territory_id,
            "card_id": card_id,
            "count": count,
            "operation": "fort_to_active",
            "capacity": capacity,
            "source_stack_id": source_stack_id,
            "target_stack_id": target_stack_id,
            "target_stack": target,
        }
        log_event(connection, "lord_fort_to_active", result, source=source)
        return result

    if territory_owner != domain_id:
        capture_claim = _capture_ready_claim(connection, territory_id, domain_id)
        if capture_claim is None:
            raise LordRuntimeError(
                "capture_not_resolved",
                "Territory capture requires a resolved battle claim awaiting garrison.",
            )
    else:
        _assert_local_owned_transfer_territory(connection, domain_id, territory)
    if territory_status in LOCKED_GARRISON_TRANSFER_STATUSES and capture_claim is None:
        raise LordRuntimeError(
            "territory_contested",
            "Contested territory cannot be changed by garrison transfer until its claim is resolved.",
        )

    if source_stack_id:
        if target_stack_id:
            card_id, target_garrison = _transfer_active_army_stack_to_garrison_stack(
                connection,
                domain_id=domain_id,
                territory_id=territory_id,
                source_army_id=_required_stack_id(source_stack_id),
                target_garrison_id=_required_stack_id(target_stack_id),
                count=count,
                now=now,
            )
        else:
            _assert_fort_new_stack_capacity_available(connection, territory_id)
            consumed = _consume_active_army_stack_at_territory(
                connection,
                domain_id,
                territory_id,
                _required_stack_id(source_stack_id),
                count,
                now,
            )
            card_id = str(consumed["card_id"])
            target_garrison = _insert_garrison_stack(
                connection, territory_id, domain_id, card_id, count, now
            )
    else:
        _assert_fort_capacity_available(connection, territory_id, card_id)
        _consume_active_army_at_territory(connection, domain_id, territory_id, card_id, count, now)
        target_garrison = _upsert_garrison(connection, territory_id, domain_id, card_id, count, now)

    captured = False
    if territory_owner != domain_id:
        captured = True
        connection.execute(
            """
            UPDATE territory_runtime_state
            SET owner_domain_id = ?, status = 'controlled', contested_by_domain_id = NULL,
                controlled_since = ?, updated_at = ?
            WHERE territory_id = ?
            """,
            (domain_id, now, now, territory_id),
        )
        connection.execute(
            """
            UPDATE territory_claim_runtime
            SET status = 'controlled', resolved_at = ?
            WHERE claim_id = ?
            """,
            (now, capture_claim["claim_id"]),
        )

    pending_awards = _award_pending_tick_rewards(
        connection, domain_id, territory_id, now
    )
    result = {
        "status": "captured" if captured else "reinforced",
        "domain_id": domain_id,
        "territory_id": territory_id,
        "card_id": card_id,
        "count": count,
        "garrison_required": True,
        "pending_tick_awards": pending_awards,
        "operation": "active_to_fort",
        "source_stack_id": source_stack_id,
        "target_stack_id": target_stack_id,
        "target_stack": target_garrison,
    }
    log_event(connection, "lord_garrison_transferred", result, source=source)
    return result


def buy_building(
    connection: sqlite3.Connection,
    lord_id: str,
    *,
    building_id: str,
    territory_id: str | None = None,
    source: str = "lord_panel",
) -> dict[str, Any]:
    ensure_lord_runtime_state(connection)
    domain = _domain_for_lord(connection, lord_id)
    domain_id = str(domain["domain_id"])
    building = _building(connection, building_id)
    scoped_territory_id = _building_purchase_territory_id(
        connection,
        domain_id,
        territory_id,
    )
    _assert_building_allowed_for_territory(
        connection,
        scoped_territory_id,
        building_id,
    )
    if _has_building_at(connection, domain_id, scoped_territory_id, building_id):
        raise LordRuntimeError("building_already_owned", "Building is already owned.")

    missing = [
        prereq
        for prereq in split_ids(str(building["prerequisite_ids"]))
        if not _has_building_at(connection, domain_id, scoped_territory_id, prereq)
    ]
    if missing:
        raise LordRuntimeError(
            "missing_prerequisites",
            f"Missing building prerequisites: {', '.join(missing)}.",
        )

    cost = _to_int(building["gold_cost"])
    if _to_int(domain["gold"]) < cost:
        raise LordRuntimeError(
            "insufficient_gold",
            f"Building costs {cost} gold, but domain has {domain['gold']}.",
        )

    now = _iso()
    raid_delta = _building_raid_token_delta(building)
    capacity_delta = _to_int(building["capacity_delta"])
    connection.execute(
        """
        UPDATE domain_runtime_state
        SET gold = gold - ?,
            active_army_capacity = active_army_capacity + ?,
            raid_token_cap = raid_token_cap + ?,
            raid_tokens = MIN(raid_tokens + ?, raid_token_cap + ?),
            updated_at = ?
        WHERE domain_id = ?
        """,
        (
            cost,
            capacity_delta,
            raid_delta,
            raid_delta,
            raid_delta,
            now,
            domain_id,
        ),
    )
    connection.execute(
        """
        INSERT INTO domain_buildings (
            domain_id, territory_id, building_id, purchased_at, source
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (domain_id, scoped_territory_id, building_id, now, source),
    )

    unlocked = []
    spawned_reserves = []
    for card_id in split_ids(str(building["recruit_unlock_ids"])):
        offer = _ensure_recruit_offer(
            connection,
            domain_id,
            card_id,
            source=f"building:{building_id}",
            now=now,
        )
        unlocked.append(offer)
        reserve = _ensure_building_recruit_reserve(
            connection,
            domain_id,
            building_id,
            card_id,
            now,
            seed_existing_to_initial=True,
        )
        if reserve is not None:
            spawned_reserves.append(reserve)

    result = {
        "status": "purchased",
        "domain_id": domain_id,
        "territory_id": scoped_territory_id,
        "building_id": building_id,
        "gold_spent": cost,
        "capacity_delta": capacity_delta,
        "raid_token_delta": raid_delta,
        "unlocked_recruit_offers": unlocked,
        "spawned_reserves": spawned_reserves,
    }
    log_event(connection, "lord_building_purchased", result, source=source)
    return result


def recruit_action(
    connection: sqlite3.Connection,
    lord_id: str,
    *,
    action: str,
    offer_id: str | None = None,
    card_id: str | None = None,
    quantity: int = 1,
    territory_id: str | None = None,
    source: str = "lord_panel",
) -> dict[str, Any]:
    ensure_lord_runtime_state(connection)
    if quantity <= 0:
        raise LordRuntimeError("invalid_count", "Recruit quantity must be positive.")
    domain = _domain_for_lord(connection, lord_id)
    domain_id = str(domain["domain_id"])
    now = _iso()

    if action == "refresh":
        spawned_reserves = _ensure_recruit_reserves_for_owned_buildings(
            connection, domain_id, now
        )
        unlocked_cards = _unlocked_recruit_cards(connection, domain_id)
        _retire_locked_recruit_offers(connection, domain_id, unlocked_cards, now)
        offers = [_ensure_recruit_offer(connection, domain_id, card_id, source=source, now=now) for card_id in unlocked_cards]
        return {
            "status": "refreshed",
            "domain_id": domain_id,
            "offers": offers,
            "unit_classes": sorted({offer["unit_class"] for offer in offers}),
            "spawned_reserves": spawned_reserves,
        }

    if action == "purchase_stock":
        if not territory_id:
            raise LordRuntimeError(
                "missing_territory_id",
                "Recruit stock purchase requires territory_id.",
            )
        if not card_id:
            raise LordRuntimeError(
                "missing_card_id",
                "Recruit stock purchase requires card_id.",
            )
        unlocked_cards = _unlocked_recruit_cards(connection, domain_id)
        if card_id not in unlocked_cards:
            raise LordRuntimeError(
                "offer_not_available",
                "Recruit card is not unlocked for this domain.",
            )
        _retire_locked_recruit_offers(connection, domain_id, unlocked_cards, now)
        ensured_offer = _ensure_recruit_offer(
            connection,
            domain_id,
            card_id,
            source=source,
            now=now,
        )
        offer_id = str(ensured_offer["offer_id"])
        action = "purchase"

    if not offer_id:
        raise LordRuntimeError("missing_offer", "Recruit action requires offer_id.")
    offer = _recruit_offer(connection, offer_id, domain_id)

    if action == "hold":
        if offer["status"] not in {"available", "held"}:
            raise LordRuntimeError("offer_not_available", "Only available offers can be held.")
        if offer["status"] == "held" and offer["held_by_domain_id"] != domain_id:
            raise LordRuntimeError("offer_held", "Offer is already held by another domain.")
        connection.execute(
            """
            UPDATE recruit_offer_runtime
            SET status = 'held', held_by_domain_id = ?, updated_at = ?
            WHERE offer_id = ?
            """,
            (domain_id, now, offer_id),
        )
        return {"status": "held", "domain_id": domain_id, "offer_id": offer_id}

    if action == "purchase":
        if offer["status"] not in {"available", "held"}:
            raise LordRuntimeError("offer_not_available", "Offer cannot be purchased.")
        if offer["status"] == "held" and offer["held_by_domain_id"] not in {None, domain_id}:
            raise LordRuntimeError("offer_held", "Offer is held by another domain.")
        cost_per_unit = _to_int(offer["cost"])
        cost = cost_per_unit * quantity
        domain = _domain_by_id(connection, domain_id)
        if _to_int(domain["gold"]) < cost:
            raise LordRuntimeError(
                "insufficient_gold",
                f"Recruit offer costs {cost} gold, but domain has {domain['gold']}.",
            )
        territory = _territory_state(connection, territory_id) if territory_id else None
        if territory is not None:
            territory_owner = _optional(territory["owner_domain_id"])
            if territory_owner != domain_id:
                raise LordRuntimeError(
                    "territory_not_owned",
                    "Recruiting to a garrison requires a controlled territory.",
                )
            if (
                str(territory["status"]) in LOCKED_GARRISON_TRANSFER_STATUSES
                or _optional(territory["contested_by_domain_id"]) is not None
            ):
                raise LordRuntimeError(
                    "territory_contested",
                    "Contested territory cannot receive recruited units.",
                )
            if raid_recruit_blocked_for_territory(connection, territory_id):
                raise LordRuntimeError(
                    "recruit_blocked_by_raid",
                    "Active raid blocks recruiting into this territory.",
                    409,
                )
            _assert_fort_capacity_available(
                connection, territory_id, str(offer["card_id"])
            )
            if (
                _available_reserve_count(connection, domain_id, str(offer["card_id"]))
                < quantity
            ):
                raise LordRuntimeError(
                    "insufficient_stock",
                    "No accumulated recruit stock is available.",
                )
            _consume_reserve(connection, domain_id, str(offer["card_id"]), quantity)
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET gold = gold - ?, updated_at = ?
            WHERE domain_id = ?
            """,
            (cost, now, domain_id),
        )
        if territory is not None:
            connection.execute(
                """
                UPDATE recruit_offer_runtime
                SET held_by_domain_id = ?, updated_at = ?
                WHERE offer_id = ?
                """,
                (domain_id, now, offer_id),
            )
            _upsert_garrison(
                connection,
                territory_id,
                domain_id,
                str(offer["card_id"]),
                quantity,
                now,
            )
            result = {
                "status": "hired",
                "domain_id": domain_id,
                "offer_id": offer_id,
                "territory_id": territory_id,
                "card_id": offer["card_id"],
                "count": quantity,
                "cost_per_unit": cost_per_unit,
                "gold_spent": cost,
                "garrison": {
                    "territory_id": territory_id,
                    "domain_id": domain_id,
                    "card_id": offer["card_id"],
                    "count": quantity,
                    "status": "active",
                },
            }
            log_event(connection, "lord_recruit_hired", result, source=source)
            return result
        connection.execute(
            """
            UPDATE recruit_offer_runtime
            SET status = 'purchased', held_by_domain_id = ?, updated_at = ?
            WHERE offer_id = ?
            """,
            (domain_id, now, offer_id),
        )
        reserve = _upsert_reserve(
            connection, domain_id, str(offer["card_id"]), quantity, now
        )
        result = {
            "status": "purchased",
            "domain_id": domain_id,
            "offer_id": offer_id,
            "card_id": offer["card_id"],
            "count": quantity,
            "cost_per_unit": cost_per_unit,
            "gold_spent": cost,
            "reserve": reserve,
        }
        log_event(connection, "lord_recruit_purchased", result, source=source)
        return result

    raise LordRuntimeError("unknown_recruit_action", f"Unknown recruit action: {action}.")


def start_raid(
    connection: sqlite3.Connection,
    lord_id: str,
    *,
    target_territory_id: str,
    rule_id: str | None = None,
    expected_token_cost: int | None = None,
    expected_gold_cost: int | None = None,
    source: str = "lord_panel",
) -> dict[str, Any]:
    ensure_lord_runtime_state(connection)
    domain = _domain_for_lord(connection, lord_id)
    domain_id = str(domain["domain_id"])
    rule = _raid_rule(connection, rule_id)
    target = _territory_state(connection, target_territory_id)
    target_content = _territory_content(connection, target_territory_id)
    target_owner = _optional(target["owner_domain_id"])
    if _final_lock_active(connection):
        raise LordRuntimeError("final_lock", "Raids are locked after final lock.", 409)
    if not target_owner:
        raise LordRuntimeError("invalid_target", "Raid target must be owned.")
    if target_owner == domain_id:
        raise LordRuntimeError("invalid_target", "Cannot raid your own territory.")

    target_type = _raid_target_type(target_content)
    allowed_target_types = split_ids(_raid_rule_value(rule, "allowed_target_types", "territory"))
    territory_target_allowed = any(
        item in allowed_target_types for item in ("territory", "contested", "b_raid_only")
    )
    if (
        (target_type == "residence" and "residence" not in allowed_target_types)
        or (target_type == "territory" and not territory_target_allowed)
    ):
        raise LordRuntimeError(
            "invalid_target",
            f"Raid rule cannot target {target_type}.",
        )

    base_token_cost = _to_int(rule["token_cost"])
    token_surcharge = raid_token_surcharge_for_domain(connection, domain_id)
    token_cost = base_token_cost + token_surcharge
    gold_cost = 0
    if (
        (expected_token_cost is not None and expected_token_cost != token_cost)
        or (expected_gold_cost is not None and expected_gold_cost != gold_cost)
    ):
        raise LordRuntimeError(
            "stale_expected_cost",
            "Raid cost changed; refresh lord state before starting the raid.",
            409,
        )

    required_buildings = split_ids(_raid_rule_value(rule, "required_building_ids", ""))
    missing_buildings = [
        building_id
        for building_id in required_buildings
        if not _has_building(connection, domain_id, building_id)
    ]
    if missing_buildings:
        raise LordRuntimeError(
            "rule_locked",
            f"Raid rule is locked. Missing buildings: {', '.join(missing_buildings)}.",
        )

    if _to_int(domain["raid_tokens"]) < token_cost:
        raise LordRuntimeError("insufficient_raid_tokens", "Not enough raid tokens.")
    if _active_raid_effect_exists(
        connection,
        domain_id=domain_id,
        target_territory_id=target_territory_id,
        rule_id=str(rule["rule_id"]),
    ):
        raise LordRuntimeError(
            "duplicate_active_effect",
            "This raid effect is already active on the target.",
            409,
        )

    effect_type = _raid_rule_value(rule, "effect_type", "temporary_debuff")
    resistance = _raid_resistance_result(
        connection,
        target_territory_id=target_territory_id,
        owner_domain_id=target_owner,
        target_type=target_type,
        rule=rule,
    )
    resistance_score = _to_int(resistance["score"])
    resistance_outcome = str(resistance["outcome"])
    effect_applied = resistance_outcome != "blocked"
    loot_gold = _raid_loot_gold(
        connection,
        target_owner,
        target_territory_id,
        resistance_outcome,
    ) if effect_type == "loot_once" else 0
    target_raid_tokens_lost = (
        _raid_residence_token_loss(connection, target_owner, resistance_outcome)
        if effect_type == "residence_pressure" and effect_applied
        else 0
    )
    current_time = datetime.now(UTC)
    now = _iso(current_time)
    base_duration_min = max(0, _to_int(rule["duration_min"]))
    duration_min = _raid_effect_duration(base_duration_min, resistance_outcome)
    alchemy_duration_reduction = 0
    if (
        effect_applied
        and duration_min > 0
        and effect_type != "loot_once"
        and _has_building(connection, target_owner, ALCHEMY_LAB_BUILDING_ID)
    ):
        alchemy_duration_reduction = min(
            ALCHEMY_RAID_DURATION_REDUCTION_MINUTES,
            max(0, duration_min - 1),
        )
        duration_min = max(1, duration_min - ALCHEMY_RAID_DURATION_REDUCTION_MINUTES)
    expires_at = _iso(current_time + timedelta(minutes=duration_min))
    effect_id = f"raid_{uuid4().hex}"
    effect_status = "active" if effect_applied and duration_min > 0 and effect_type != "loot_once" else (
        "resolved" if effect_applied else "blocked"
    )
    payload = {
        "resistance": resistance_score,
        "raid_strength": resistance["raid_strength"],
        "resistance_outcome": resistance_outcome,
        "effect_multiplier": resistance["effect_multiplier"],
        "effect_applied": effect_applied,
        "loot_gold": loot_gold,
        "target_raid_tokens_lost": target_raid_tokens_lost,
        "token_surcharge": token_surcharge,
        "base_token_cost": base_token_cost,
        "loot_policy": _raid_rule_value(rule, "loot_policy", "no_loot"),
        "effect_type": effect_type,
        "base_duration_min": base_duration_min,
        "duration_min": duration_min,
        "alchemy_duration_reduction": alchemy_duration_reduction,
        "counterplay": _raid_rule_value(rule, "counterplay", ""),
        "visibility": _raid_rule_value(rule, "visibility", "source_target_and_masters"),
    }
    connection.execute(
        """
        UPDATE domain_runtime_state
        SET raid_tokens = raid_tokens - ?, gold = gold + ?, updated_at = ?
        WHERE domain_id = ?
        """,
        (token_cost, loot_gold, now, domain_id),
    )
    if loot_gold:
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET gold = MAX(0, gold - ?), updated_at = ?
            WHERE domain_id = ?
            """,
            (loot_gold, now, target_owner),
        )
    if target_raid_tokens_lost:
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET raid_tokens = MAX(0, raid_tokens - ?), updated_at = ?
            WHERE domain_id = ?
            """,
            (target_raid_tokens_lost, now, target_owner),
        )
    connection.execute(
        """
        INSERT INTO raid_effects (
            raid_effect_id, rule_id, source_domain_id, target_domain_id,
            target_territory_id, status, starts_at_offset_min, ends_at_offset_min,
            started_at, expires_at, payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        (
            effect_id,
            rule["rule_id"],
            domain_id,
            target_owner,
            target_territory_id,
            effect_status,
            duration_min,
            now,
            expires_at,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ),
    )
    result = {
        "status": effect_status,
        "raid_effect_id": effect_id,
        "source_domain_id": domain_id,
        "target_domain_id": target_owner,
        "target_territory_id": target_territory_id,
        "rule_id": rule["rule_id"],
        "effect_type": payload["effect_type"],
        "token_spent": token_cost,
        "gold_spent": gold_cost,
        "started": True,
        "resisted": resistance_outcome != "full",
        "blocked": resistance_outcome == "blocked",
        "loot_applied": loot_gold > 0,
        "validation_error": None,
        "needs_master_review": False,
        "started_at": now,
        "expires_at": expires_at,
        **payload,
    }
    event_id = log_event(connection, "lord_raid_started", result, source=source)
    updated_domain = _domain_by_id(connection, domain_id)
    result["raid_tokens"] = _to_int(updated_domain["raid_tokens"])
    result["gold"] = _to_int(updated_domain["gold"])
    result["active_raid_effects"] = [
        {
            "raid_effect_id": effect_id,
            "rule_id": rule["rule_id"],
            "effect_type": result["effect_type"],
            "target_territory_id": target_territory_id,
            "target_domain_id": target_owner,
            "status": effect_status,
            "started_at": now,
            "expires_at": expires_at,
            "resisted": resistance_outcome != "full",
            "loot_applied": loot_gold > 0,
        }
    ]
    result["audit_event_id"] = event_id
    return result


def reconcile_raid_effects(
    connection: sqlite3.Connection, *, now: datetime | None = None
) -> list[dict[str, Any]]:
    ensure_runtime_schema(connection)
    if not _table_exists(connection, "raid_effects"):
        return []

    current_time = now or datetime.now(UTC)
    expired_at = _iso(current_time)
    expired: list[dict[str, Any]] = []
    for row in connection.execute(
        """
        SELECT raid_effect_id, source_domain_id, target_domain_id,
               target_territory_id, expires_at
        FROM raid_effects
        WHERE status = 'active' AND expires_at IS NOT NULL
        ORDER BY expires_at, raid_effect_id
        """
    ).fetchall():
        try:
            expires_at_dt = _parse_iso(str(row["expires_at"]))
        except ValueError:
            continue
        if expires_at_dt > current_time:
            continue
        connection.execute(
            """
            UPDATE raid_effects
            SET status = 'expired', expired_at = ?
            WHERE raid_effect_id = ? AND status = 'active'
            """,
            (expired_at, row["raid_effect_id"]),
        )
        payload = {
            "raid_effect_id": row["raid_effect_id"],
            "source_domain_id": row["source_domain_id"],
            "target_domain_id": row["target_domain_id"],
            "target_territory_id": row["target_territory_id"],
            "status": "expired",
            "expires_at": row["expires_at"],
            "expired_at": expired_at,
        }
        expired.append(payload)
        log_event(connection, "lord_raid_expired", payload, source="raid_lifecycle")
    return expired


def reconcile_raid_token_caps(
    connection: sqlite3.Connection, *, now: str | None = None
) -> list[dict[str, Any]]:
    ensure_runtime_schema(connection)
    if not _table_exists(connection, "domain_runtime_state"):
        return []
    now_text = now or _iso()
    updates: list[dict[str, Any]] = []
    for row in connection.execute(
        "SELECT domain_id, raid_tokens, raid_token_cap FROM domain_runtime_state ORDER BY domain_id"
    ).fetchall():
        domain_id = str(row["domain_id"])
        cap = _raid_token_cap_for_domain(connection, domain_id)
        before_cap = _to_int(row["raid_token_cap"])
        before_tokens = _to_int(row["raid_tokens"])
        next_tokens = min(before_tokens, cap)
        if before_cap == cap and before_tokens == next_tokens:
            continue
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET raid_token_cap = ?,
                raid_tokens = ?,
                updated_at = ?
            WHERE domain_id = ?
            """,
            (cap, next_tokens, now_text, domain_id),
        )
        updates.append(
            {
                "domain_id": domain_id,
                "before_cap": before_cap,
                "after_cap": cap,
                "before_tokens": before_tokens,
                "after_tokens": next_tokens,
            }
        )
    return updates


def refill_raid_tokens_for_tick(
    connection: sqlite3.Connection, *, now: str
) -> list[dict[str, Any]]:
    reconcile_raid_token_caps(connection, now=now)
    updates: list[dict[str, Any]] = []
    for row in connection.execute(
        """
        SELECT domain_id, raid_tokens, raid_token_cap
        FROM domain_runtime_state
        ORDER BY domain_id
        """
    ).fetchall():
        before = _to_int(row["raid_tokens"])
        cap = max(BASE_RAID_TOKEN_CAP, _to_int(row["raid_token_cap"]))
        after = min(cap, before + RAID_TOKEN_REFILL_PER_TICK)
        if after == before:
            continue
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET raid_tokens = ?, updated_at = ?
            WHERE domain_id = ?
            """,
            (after, now, row["domain_id"]),
        )
        updates.append(
            {
                "domain_id": row["domain_id"],
                "before": before,
                "after": after,
                "cap": cap,
                "refill": after - before,
            }
        )
    return updates


def refill_ritual_cleanse_charges_for_tick(
    connection: sqlite3.Connection, *, now: str
) -> list[dict[str, Any]]:
    if not _table_exists(connection, "domain_runtime_state"):
        return []
    updates: list[dict[str, Any]] = []
    for row in connection.execute(
        """
        SELECT domain_id, ritual_cleanse_charges
        FROM domain_runtime_state
        ORDER BY domain_id
        """
    ).fetchall():
        domain_id = str(row["domain_id"])
        if not _has_building(connection, domain_id, RITUAL_CHAMBER_BUILDING_ID):
            continue
        before = _to_int(row["ritual_cleanse_charges"])
        after = min(RITUAL_CLEANSE_CHARGE_CAP, before + 1)
        if after == before:
            continue
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET ritual_cleanse_charges = ?, updated_at = ?
            WHERE domain_id = ?
            """,
            (after, now, domain_id),
        )
        updates.append(
            {
                "domain_id": domain_id,
                "before": before,
                "after": after,
                "refill": after - before,
                "cap": RITUAL_CLEANSE_CHARGE_CAP,
            }
        )
    return updates


def cleanse_raid_effect(
    connection: sqlite3.Connection,
    lord_id: str,
    *,
    raid_effect_id: str,
    source: str = "lord_panel",
) -> dict[str, Any]:
    ensure_lord_runtime_state(connection)
    domain = _domain_for_lord(connection, lord_id)
    domain_id = str(domain["domain_id"])
    if not _has_building(connection, domain_id, RITUAL_CHAMBER_BUILDING_ID):
        raise LordRuntimeError(
            "ritual_chamber_required",
            "Ritual cleanse requires Ritual Chamber in the residence.",
        )
    charges = _to_int(_row_value(domain, "ritual_cleanse_charges", 0))
    if charges <= 0:
        raise LordRuntimeError(
            "ritual_cleanse_unavailable",
            "No ritual cleanse charge is available.",
        )
    effect = connection.execute(
        """
        SELECT *
        FROM raid_effects
        WHERE raid_effect_id = ?
        """,
        (raid_effect_id,),
    ).fetchone()
    if effect is None:
        raise LordRuntimeError("raid_effect_not_found", "Raid effect is not available.", 404)
    if str(effect["status"]) != "active":
        raise LordRuntimeError(
            "raid_effect_not_active",
            "Only active raid effects can be cleansed.",
            409,
        )
    if str(effect["target_domain_id"]) != domain_id:
        raise LordRuntimeError(
            "raid_effect_not_owned",
            "Ritual cleanse can target only this house holdings.",
            403,
        )
    now = _iso()
    payload = _json_loads(effect["payload_json"], {})
    payload.update(
        {
            "cleansed": True,
            "cleansed_at": now,
            "cleansed_by_domain_id": domain_id,
            "cleanse_source": source,
        }
    )
    connection.execute(
        """
        UPDATE raid_effects
        SET status = 'cleansed',
            expired_at = ?,
            payload_json = ?
        WHERE raid_effect_id = ? AND status = 'active'
        """,
        (
            now,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            raid_effect_id,
        ),
    )
    connection.execute(
        """
        UPDATE domain_runtime_state
        SET ritual_cleanse_charges = MAX(0, ritual_cleanse_charges - 1),
            updated_at = ?
        WHERE domain_id = ?
        """,
        (now, domain_id),
    )
    refreshed = _domain_by_id(connection, domain_id)
    result = {
        "status": "cleansed",
        "raid_effect_id": raid_effect_id,
        "domain_id": domain_id,
        "ritual_cleanse_charges": _to_int(refreshed["ritual_cleanse_charges"]),
        "cleansed_at": now,
    }
    log_event(connection, "lord_ritual_cleanse_used", result, source=source)
    return result


def active_raid_effects_for_territory(
    connection: sqlite3.Connection,
    territory_id: str,
    *,
    effect_type: str | None = None,
) -> list[dict[str, Any]]:
    return [
        effect
        for effect in _active_raid_effect_payloads(
            connection,
            "target_territory_id = ?",
            (territory_id,),
        )
        if effect_type is None or effect.get("effect_type") == effect_type
    ]


def active_raid_effects_for_domain(
    connection: sqlite3.Connection,
    domain_id: str,
    *,
    effect_type: str | None = None,
) -> list[dict[str, Any]]:
    return [
        effect
        for effect in _active_raid_effect_payloads(
            connection,
            "target_domain_id = ?",
            (domain_id,),
        )
        if effect_type is None or effect.get("effect_type") == effect_type
    ]


def raid_income_multiplier_for_territory(
    connection: sqlite3.Connection, territory_id: str
) -> int:
    effects = active_raid_effects_for_territory(
        connection,
        territory_id,
        effect_type="income_down",
    )
    if not effects:
        return 100

    multipliers: list[int] = []
    for effect in effects:
        outcome = str(effect.get("resistance_outcome") or "")
        if outcome == "full":
            multipliers.append(0)
        elif outcome == "weakened":
            multipliers.append(50)
        else:
            multipliers.append(_to_int(effect.get("effect_multiplier")) or 100)
    return min(multipliers)


def raid_defense_penalty_for_territory(
    connection: sqlite3.Connection, territory_id: str
) -> int:
    effects = active_raid_effects_for_territory(
        connection,
        territory_id,
        effect_type="defense_down",
    )
    if not effects:
        return 0
    if any(str(effect.get("resistance_outcome")) == "full" for effect in effects):
        return 2
    return 1


def raid_recruit_blocked_for_territory(
    connection: sqlite3.Connection, territory_id: str
) -> bool:
    return bool(
        active_raid_effects_for_territory(
            connection,
            territory_id,
            effect_type="recruit_block",
        )
    )


def raid_order_public_cap_penalty_for_domain(
    connection: sqlite3.Connection, domain_id: str
) -> int:
    return 1 if active_raid_effects_for_domain(
        connection,
        domain_id,
        effect_type="order_visibility_disrupt",
    ) else 0


def raid_token_surcharge_for_domain(
    connection: sqlite3.Connection, domain_id: str
) -> int:
    return 1 if active_raid_effects_for_domain(
        connection,
        domain_id,
        effect_type="residence_pressure",
    ) else 0


def raid_defense_summary(
    connection: sqlite3.Connection,
    *,
    target_territory_id: str,
    owner_domain_id: str,
    target_type: str,
) -> dict[str, Any]:
    garrison_power = (
        0
        if target_type == "residence"
        else _territory_garrison_power(connection, target_territory_id, owner_domain_id)
    )
    score = _raid_defense_score(
        connection,
        target_territory_id=target_territory_id,
        owner_domain_id=owner_domain_id,
        target_type=target_type,
    )
    if score <= 0:
        risk = "низкий"
    elif score == 1:
        risk = "средний"
    elif score == 2:
        risk = "высокий"
    else:
        risk = "очень высокий"
    return {
        "raid_defense_score": score,
        "garrison_power": garrison_power,
        "risk_label": risk,
        "has_wards": _has_building(connection, owner_domain_id, "b_wards"),
        "active_army_present": (
            target_type != "residence"
            and _domain_current_territory(connection, owner_domain_id) == target_territory_id
        ),
    }


def order_action(
    connection: sqlite3.Connection,
    lord_id: str,
    *,
    action: str,
    object_id: str | None = None,
    target_player_id: str | None = None,
    visibility: str = "public",
    escrow_reward_id: str | None = None,
    visible_hook: str | None = None,
    expires_at: str | None = None,
    order_id: str | None = None,
    player_id: str | None = None,
    result_event_id: str | None = None,
    reason: str | None = None,
    source: str = "lord_panel",
    actor_role: str = "lord",
) -> dict[str, Any]:
    ensure_lord_runtime_state(connection)
    domain = _domain_for_lord(connection, lord_id)
    domain_id = str(domain["domain_id"])
    now = _iso()
    actor_role = actor_role.strip().lower()

    if action == "create":
        _assert_order_action_authority(action, actor_role)
        if _final_lock_active(connection) and source not in FINAL_LOCK_ORDER_OVERRIDE_SOURCES:
            raise LordRuntimeError(
                "final_lock_orders_closed",
                "Final lock blocks new lord orders except master override or paper final evidence.",
                status_code=409,
            )
        if not object_id:
            raise LordRuntimeError("missing_object", "Order requires object_id.")
        visibility = _normalize_visibility(visibility)
        if visibility == "addressed" and not target_player_id:
            raise LordRuntimeError("missing_target", "Addressed order requires target_player_id.")
        if target_player_id:
            _assert_order_recipient_exists(connection, target_player_id)
        _assert_order_building_unlocked(
            connection,
            domain_id,
            visibility,
            source=source,
            actor_role=actor_role,
        )
        if not escrow_reward_id:
            raise LordRuntimeError("missing_escrow_reward", "Order requires an escrow_reward_id.")
        _assert_order_object_exists(connection, object_id)
        _assert_order_cap(connection, lord_id, visibility)
        if target_player_id:
            _assert_player_object_available(connection, target_player_id, object_id)
        new_order_id = order_id or f"order_{uuid4().hex}"
        status = "addressed_pending" if visibility == "addressed" else "published"
        connection.execute(
            """
            INSERT INTO order_runtime_state (
                order_id, lord_id, target_player_id, object_id, visibility, status,
                escrow_reward_id, visible_hook, expires_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_order_id,
                lord_id,
                target_player_id,
                object_id,
                visibility,
                status,
                escrow_reward_id,
                _optional(visible_hook),
                _optional(expires_at),
                now,
                now,
            ),
        )
        if escrow_reward_id:
            _reserve_order_escrow(
                connection,
                new_order_id,
                lord_id=lord_id,
                reward_id=escrow_reward_id,
                debit_domain=True,
                now=now,
                domain=domain,
            )
        result = _order_payload(connection, new_order_id)
        log_event(connection, "lord_order_created", result, source=source)
        return {"status": "created", "order": result}

    if not order_id:
        raise LordRuntimeError("missing_order", "Order action requires order_id.")
    order = _order_for_lord(connection, lord_id, order_id)
    _assert_order_action_authority(action, actor_role)

    if action == "accept":
        _assert_master_recovery_reason(action, actor_role, source, reason)
        actor = player_id
        if actor_role == "master" and not actor:
            actor = order["target_player_id"]
        if not actor:
            raise LordRuntimeError("missing_player", "Accept requires player_id.")
        if order["visibility"] == "addressed" and order["target_player_id"] != actor:
            raise LordRuntimeError("addressed_order_mismatch", "Order is addressed to another player.")
        if order["status"] not in {"published", "addressed_pending", "failed_retryable"}:
            raise LordRuntimeError("order_not_accepting", "Order cannot be accepted in current status.")
        _assert_player_object_available(connection, actor, str(order["object_id"]), exclude_order_id=order_id)
        connection.execute(
            """
            UPDATE order_runtime_state
            SET status = 'accepted',
                accepted_by_player_id = ?,
                reason = COALESCE(?, reason),
                updated_at = ?
            WHERE order_id = ?
            """,
            (actor, reason, now, order_id),
        )
        return {"status": "accepted", "order": _order_payload(connection, order_id)}

    if action == "start":
        _transition_order(connection, order, "in_progress", now=now)
        return {"status": "in_progress", "order": _order_payload(connection, order_id)}

    if action == "submit_success":
        _assert_master_recovery_reason(action, actor_role, source, reason)
        if order["status"] not in {"accepted", "in_progress", "claimed_at_prop", "submitted_pending_sync"}:
            raise LordRuntimeError("order_not_submittable", "Order cannot be submitted in current status.")
        actor = player_id
        if actor_role == "master" and not actor:
            actor = order["accepted_by_player_id"] or order["target_player_id"]
        if not actor:
            raise LordRuntimeError("missing_player", "Success sync requires player_id.")
        if actor_role != "master" and not result_event_id:
            raise LordRuntimeError("missing_order_proof", "Success sync requires result_event_id proof.")
        if not order["accepted_by_player_id"] and actor_role != "master":
            raise LordRuntimeError("order_not_accepted", "Order must be accepted before player submission.")
        if order["accepted_by_player_id"] and order["accepted_by_player_id"] != actor:
            raise LordRuntimeError("order_actor_mismatch", "Order is accepted by another player.")
        connection.execute(
            """
            UPDATE order_runtime_state
            SET status = 'pending_master_approval',
                submitted_by_player_id = ?,
                result_event_id = ?,
                reason = COALESCE(?, reason),
                updated_at = ?
            WHERE order_id = ?
            """,
            (actor, result_event_id, reason, now, order_id),
        )
        closed_competitors = _close_competing_orders(
            connection,
            object_id=str(order["object_id"]),
            winner_order_id=order_id,
            now=now,
        )
        result = {
            "status": "pending_master_approval",
            "order": _order_payload(connection, order_id),
            "closed_competing_orders": closed_competitors,
        }
        log_event(connection, "lord_order_success_synced", result, source=source)
        return result

    if action == "complete":
        _assert_master_recovery_reason(action, actor_role, source, reason)
        if order["status"] not in {"pending_master_approval", "submitted_pending_sync", "completed"}:
            raise LordRuntimeError("order_not_ready_for_completion", "Order needs submitted player proof before completion.")
        actor = player_id or order["submitted_by_player_id"] or order["accepted_by_player_id"] or order["target_player_id"]
        if not actor:
            raise LordRuntimeError("missing_order_proof", "Completion requires accepted or submitted player proof.")
        _transition_order(connection, order, "completed", now=now)
        closed_competitors = _close_competing_orders(
            connection,
            object_id=str(order["object_id"]),
            winner_order_id=order_id,
            now=now,
        )
        reward_update = _award_order_escrow(
            connection,
            order_id,
            target_player_id=str(actor),
            now=now,
            reason=reason or "completed",
        )
        result = {
            "status": "completed",
            "order": _order_payload(connection, order_id),
            "reward_update": reward_update,
            "closed_competing_orders": closed_competitors,
        }
        log_event(connection, "lord_order_completed", result, source=source)
        return result

    if action in {"cancel", "expire", "fail_closed", "fail_retryable", "contested_review"}:
        status_by_action = {
            "cancel": "cancelled_by_lord",
            "expire": "expired",
            "fail_closed": "failed_closed",
            "fail_retryable": "failed_retryable",
            "contested_review": "contested_review",
        }
        new_status = status_by_action[action]
        if action == "cancel" and str(order["status"]) not in CANCELLABLE_ORDER_STATUSES:
            raise LordRuntimeError(
                "order_already_in_progress",
                "Order has already started, is under review, or is closed.",
                status_code=409,
            )
        _transition_order(connection, order, new_status, now=now, reason=reason)
        if new_status in {"cancelled_by_lord", "expired", "failed_closed"}:
            _refund_order_escrow(connection, order_id, now=now, reason=reason or new_status)
        result = {"status": new_status, "order": _order_payload(connection, order_id)}
        log_event(connection, "lord_order_status_changed", result, source=source)
        return result

    raise LordRuntimeError("unknown_order_action", f"Unknown order action: {action}.")


def build_diplomacy_signals(connection: sqlite3.Connection, viewer_domain_id: str) -> list[dict[str, Any]]:
    ensure_lord_runtime_state(connection)
    powers = _army_power_by_domain(connection)
    average_power = sum(powers.values()) / len(powers) if powers else 0
    order_counts = _active_order_counts(connection)
    contested = _contested_counts(connection)
    raid_counts = _active_raid_counts(connection)
    signals: list[dict[str, Any]] = []
    for domain_id, power in sorted(powers.items()):
        ratio = int((power / average_power) * 100) if average_power else 0
        order_count = order_counts.get(domain_id, 0)
        order_pressure: dict[str, Any]
        if domain_id == viewer_domain_id:
            order_pressure = {
                "active_orders": order_count,
                "active_order_pressure": "own_exact",
                "active_order_visibility": "own_exact",
            }
        else:
            order_pressure = {
                "active_order_pressure": _order_pressure_bucket(order_count),
                "active_order_visibility": "foreign_coarse",
            }
        signals.append(
            {
                "domain_id": domain_id,
                "army_power": power,
                "army_power_ratio": ratio,
                **order_pressure,
                "active_raids": raid_counts.get(domain_id, 0),
                "contested_pressure": contested.get(domain_id, 0),
                "coalition_prompt": ratio >= 130 and domain_id != viewer_domain_id,
            }
        )
    return signals


def anti_snowball_cut_for_domain(connection: sqlite3.Connection, domain_id: str) -> dict[str, Any]:
    ensure_runtime_schema(connection)
    powers = _army_power_by_domain(connection)
    own_power = powers.get(domain_id, 0)
    average_power = sum(powers.values()) / len(powers) if powers else 0
    ratio = int((own_power / average_power) * 100) if average_power else 0
    cut = 0
    if _table_exists(connection, "anti_snowball_rules"):
        for row in connection.execute(
            """
            SELECT army_power_ratio_threshold, income_cut_percent
            FROM anti_snowball_rules
            ORDER BY CAST(army_power_ratio_threshold AS INTEGER)
            """
        ).fetchall():
            if ratio >= _to_int(row["army_power_ratio_threshold"]):
                cut = _to_int(row["income_cut_percent"])
    return {
        "domain_id": domain_id,
        "army_power": own_power,
        "average_army_power": average_power,
        "army_power_ratio": ratio,
        "income_cut_percent": cut,
    }


def visible_garrisons_for(
    connection: sqlite3.Connection, territory_id: str, viewer_domain_id: str
) -> list[dict[str, Any]]:
    ensure_lord_runtime_state(connection)
    rows = _rows(
        connection,
        """
        SELECT garrison_id, territory_id, domain_id, card_id, count, status
        FROM garrison_runtime_state
        WHERE territory_id = ? AND status = 'active' AND count > 0
        ORDER BY garrison_id
        """,
        (territory_id,),
    )
    visible = []
    for row in rows:
        if row["domain_id"] == viewer_domain_id:
            visible.append(dict(row))
        else:
            visible.append(
                {
                    "territory_id": row["territory_id"],
                    "domain_id": row["domain_id"],
                    "status": "hidden_foreign_garrison",
                    "hidden": True,
                }
            )
    return visible


def active_pending_lord_move(
    connection: sqlite3.Connection, domain_id: str
) -> dict[str, Any] | None:
    ensure_runtime_schema(connection)
    row = connection.execute(
        """
        SELECT *
        FROM pending_lord_moves
        WHERE domain_id = ? AND status = 'pending'
        ORDER BY started_at, move_id
        LIMIT 1
        """,
        (domain_id,),
    ).fetchone()
    return _pending_move_payload(row) if row is not None else None


def reconcile_pending_lord_moves(
    connection: sqlite3.Connection,
    *,
    domain_id: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    ensure_runtime_schema(connection)
    current_time = now or datetime.now(UTC)
    current_iso = _iso(current_time)
    params: list[Any] = [current_iso]
    domain_filter = ""
    if domain_id is not None:
        domain_filter = " AND domain_id = ?"
        params.append(domain_id)
    rows = connection.execute(
        f"""
        SELECT *
        FROM pending_lord_moves
        WHERE status = 'pending'
          AND arrival_at <= ?
          {domain_filter}
        ORDER BY arrival_at, started_at, move_id
        """,
        params,
    ).fetchall()
    completed = []
    for row in rows:
        completed.append(_complete_pending_lord_move(connection, row, current_iso))
    return completed


def build_lord_map_intel(
    connection: sqlite3.Connection, viewer_domain_id: str
) -> dict[str, Any]:
    ensure_runtime_schema(connection)
    viewer_node_id = _active_army_location_node(connection, viewer_domain_id)
    revealed_by_target = {
        (str(row["target_type"]), str(row["target_id"])): _normalized_map_intel_level(
            row["intel_level"]
        )
        for row in connection.execute(
            """
            SELECT target_type, target_id, intel_level
            FROM lord_map_intel
            WHERE domain_id = ?
            """,
            (viewer_domain_id,),
        ).fetchall()
    }
    revealed = [
        dict(row)
        for row in connection.execute(
            """
            SELECT target_type, target_id, intel_level, revealed_at, source
            FROM lord_map_intel
            WHERE domain_id = ?
            ORDER BY target_type, target_id
            """,
            (viewer_domain_id,),
        ).fetchall()
    ]
    return {
        "graph_visible": True,
        "hidden_detail_policy": "enemy_army_and_garrison_details_redacted",
        "enemy_armies": _visible_enemy_army_intel(
            connection,
            viewer_domain_id,
            viewer_node_id,
            revealed_by_target,
        ),
        "revealed": revealed,
    }


def _visible_enemy_army_intel(
    connection: sqlite3.Connection,
    viewer_domain_id: str,
    viewer_node_id: str | None,
    revealed_by_target: dict[tuple[str, str], str],
) -> list[dict[str, Any]]:
    if viewer_node_id is None:
        return []
    visible_node_ids = sorted({viewer_node_id, *_adjacent_map_node_ids(connection, viewer_node_id)})

    placeholders = ", ".join("?" for _ in visible_node_ids)
    rows = connection.execute(
        f"""
        SELECT
            army.army_id,
            domain_state.domain_id,
            army.card_id,
            army.count,
            COALESCE(NULLIF(domain_state.current_node_id, ''), army.location_node_id) AS effective_location_node_id,
            domains.name AS domain_name,
            nodes.territory_id,
            territories.name AS territory_name
        FROM domain_runtime_state domain_state
        LEFT JOIN active_army_runtime army
          ON army.domain_id = domain_state.domain_id
         AND army.status = 'active'
         AND army.count > 0
        LEFT JOIN domains ON domains.domain_id = domain_state.domain_id
        LEFT JOIN map_nodes nodes ON nodes.node_id = COALESCE(NULLIF(domain_state.current_node_id, ''), army.location_node_id)
        LEFT JOIN territories ON territories.territory_id = nodes.territory_id
        WHERE domain_state.domain_id != ?
          AND COALESCE(NULLIF(domain_state.current_node_id, ''), army.location_node_id) IN ({placeholders})
        ORDER BY effective_location_node_id, domain_state.domain_id, army.army_id
        """,
        (viewer_domain_id, *visible_node_ids),
    ).fetchall()

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        location_node_id = str(row["effective_location_node_id"])
        key = (str(row["domain_id"]), location_node_id)
        group = grouped.setdefault(
            key,
            {
                "target_id": f"{row['domain_id']}:{location_node_id}",
                "domain_id": str(row["domain_id"]),
                "domain_name": row["domain_name"],
                "node_id": location_node_id,
                "territory_id": _optional(row["territory_id"]),
                "territory_name": row["territory_name"],
                "adjacent_to_node_id": viewer_node_id,
                "total_count": 0,
                "stacks": [],
            },
        )
        count = _to_int(row["count"])
        group["total_count"] += count
        if row["army_id"] and count > 0:
            group["stacks"].append(
                {
                    "army_id": row["army_id"],
                    "card_id": row["card_id"],
                    "count": count,
                }
            )

    payloads = []
    for group in grouped.values():
        target_id = str(group["target_id"])
        domain_id = str(group["domain_id"])
        intel_level = revealed_by_target.get(
            ("enemy_army", target_id),
            revealed_by_target.get(("enemy_army", domain_id), "presence"),
        )
        rank = _map_intel_rank(intel_level)
        payload: dict[str, Any] = {
            "target_id": target_id,
            "target_type": "enemy_army",
            "node_id": group["node_id"],
            "territory_id": group["territory_id"],
            "territory_name": group["territory_name"],
            "adjacent_to_node_id": group["adjacent_to_node_id"],
            "intel_level": intel_level,
            "presence": True,
            "detail_redacted": rank < MAP_INTEL_LEVELS["composition"],
        }
        if rank >= MAP_INTEL_LEVELS["owner"]:
            payload["owner_domain_id"] = domain_id
            payload["owner_domain_name"] = group["domain_name"] or domain_id
        if rank >= MAP_INTEL_LEVELS["rough_strength"]:
            payload["rough_strength"] = _rough_army_strength(_to_int(group["total_count"]))
        if rank >= MAP_INTEL_LEVELS["composition"]:
            payload["total_count"] = _to_int(group["total_count"])
            payload["stack_count"] = len(group["stacks"])
            payload["composition"] = group["stacks"]
        payloads.append(payload)

    return payloads


def _active_army_location_node(
    connection: sqlite3.Connection, domain_id: str
) -> str | None:
    domain_row = connection.execute(
        """
        SELECT current_node_id
        FROM domain_runtime_state
        WHERE domain_id = ?
        LIMIT 1
        """,
        (domain_id,),
    ).fetchone()
    if domain_row is not None:
        node_id = _optional(domain_row["current_node_id"])
        if node_id is not None:
            return node_id

    row = connection.execute(
        """
        SELECT location_node_id
        FROM active_army_runtime
        WHERE domain_id = ?
          AND status = 'active'
          AND count > 0
          AND location_node_id IS NOT NULL
        GROUP BY location_node_id
        ORDER BY SUM(count) DESC, location_node_id
        LIMIT 1
        """,
        (domain_id,),
    ).fetchone()
    return _optional(row["location_node_id"]) if row is not None else None


def _adjacent_map_node_ids(connection: sqlite3.Connection, node_id: str) -> set[str]:
    adjacent: set[str] = set()
    for row in connection.execute(
        """
        SELECT from_node_id, to_node_id, bidirectional
        FROM map_edges
        ORDER BY _row_number
        """
    ).fetchall():
        from_node_id = str(row["from_node_id"])
        to_node_id = str(row["to_node_id"])
        bidirectional = str(row["bidirectional"]).lower() == "true" or row["bidirectional"] is True
        if from_node_id == node_id:
            adjacent.add(to_node_id)
        if bidirectional and to_node_id == node_id:
            adjacent.add(from_node_id)
    return adjacent


def _normalized_map_intel_level(value: object) -> str:
    text = str(value or "presence").strip().lower()
    if text in {"rough", "strength"}:
        return "rough_strength"
    if text in MAP_INTEL_LEVELS:
        return text
    return "presence"


def _map_intel_rank(level: str) -> int:
    return MAP_INTEL_LEVELS.get(_normalized_map_intel_level(level), 0)


def _rough_army_strength(total_count: int) -> str:
    if total_count <= 2:
        return "small"
    if total_count <= 6:
        return "medium"
    return "large"


def runtime_table(connection: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    ensure_lord_runtime_state(connection)
    if not _table_exists(connection, table_name):
        return []
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table_name}").fetchall()]


def _create_claim_if_needed(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    target_node_id: str,
    now: str,
    source: str,
) -> dict[str, Any] | None:
    target = connection.execute(
        """
        SELECT n.territory_id, t.owner_domain_id, t.status, t.contested_by_domain_id
        FROM map_nodes n
        LEFT JOIN territory_runtime_state t ON t.territory_id = n.territory_id
        WHERE n.node_id = ?
        """,
        (target_node_id,),
    ).fetchone()
    if target is None or not target["territory_id"]:
        return None
    if target["owner_domain_id"] == domain_id:
        return None

    existing = connection.execute(
        """
        SELECT claim_id, territory_id, claimant_domain_id, status
        FROM territory_claim_runtime
        WHERE territory_id = ?
          AND status IN ('in_battle', 'contested', 'contested_pending_tick', 'awaiting_garrison')
        ORDER BY created_at
        LIMIT 1
        """,
        (target["territory_id"],),
    ).fetchone()
    if existing is not None:
        return dict(existing)

    claim_id = f"claim_{uuid4().hex}"
    connection.execute(
        """
        INSERT INTO territory_claim_runtime (
            claim_id, territory_id, claimant_domain_id, defender_domain_id,
            status, source, created_at, battle_required
        )
        VALUES (?, ?, ?, ?, 'in_battle', ?, ?, 1)
        """,
        (
            claim_id,
            target["territory_id"],
            domain_id,
            _optional(target["owner_domain_id"]),
            source,
            now,
        ),
    )
    connection.execute(
        """
        UPDATE territory_runtime_state
        SET status = 'in_battle', contested_by_domain_id = ?, updated_at = ?
        WHERE territory_id = ?
        """,
        (domain_id, now, target["territory_id"]),
    )
    return {
        "claim_id": claim_id,
        "territory_id": target["territory_id"],
        "claimant_domain_id": domain_id,
        "defender_domain_id": _optional(target["owner_domain_id"]),
        "status": "in_battle",
        "visible_to_lords": True,
    }


def _movement_requires_active_army(
    connection: sqlite3.Connection, domain_id: str, target_node_id: str
) -> bool:
    target = connection.execute(
        """
        SELECT n.territory_id, t.owner_domain_id
        FROM map_nodes n
        LEFT JOIN territory_runtime_state t ON t.territory_id = n.territory_id
        WHERE n.node_id = ?
        LIMIT 1
        """,
        (target_node_id,),
    ).fetchone()
    if target is None or not target["territory_id"]:
        return False
    return _optional(target["owner_domain_id"]) != domain_id


def _initialize_domain_locations(connection: sqlite3.Connection, now: str) -> None:
    if not _table_exists(connection, "domains"):
        return
    for row in connection.execute(
        "SELECT domain_id FROM domains ORDER BY _row_number"
    ).fetchall():
        domain_id = str(row["domain_id"])
        residence = _residence_node(connection, domain_id)
        if residence is None:
            continue
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET current_node_id = COALESCE(current_node_id, ?), updated_at = ?
            WHERE domain_id = ?
            """,
            (residence, now, domain_id),
        )


def _transfer_reserve_to_active(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    territory_id: str,
    card_id: str,
    count: int,
    source: str,
) -> dict[str, Any]:
    domain = _domain_by_id(connection, domain_id)
    residence = _residence_node(connection, domain_id)
    residence_territory = _territory_for_node(connection, residence) if residence else None
    if domain["current_node_id"] != residence:
        raise LordRuntimeError(
            "not_at_residence",
            "Reserve can transfer to active army only at the domain residence.",
        )
    if residence_territory != territory_id:
        raise LordRuntimeError(
            "not_at_residence",
            "Reserve can transfer to active army only through the residence territory.",
        )
    capacity = _to_int(domain["active_army_capacity"])
    _assert_active_army_stack_capacity_available(
        connection, domain_id, card_id, capacity
    )
    card = _unit_card(connection, card_id)
    gold_cost = _to_int(card["cost"]) * count
    if _to_int(domain["gold"]) < gold_cost:
        raise LordRuntimeError(
            "insufficient_gold",
            f"Deploying reserve costs {gold_cost} gold, but domain has {domain['gold']}.",
        )
    _consume_reserve(connection, domain_id, card_id, count)
    now = _iso()
    connection.execute(
        """
        UPDATE domain_runtime_state
        SET gold = gold - ?, updated_at = ?
        WHERE domain_id = ?
        """,
        (gold_cost, now, domain_id),
    )
    army_id = _stable_id("army", domain_id, card_id)
    connection.execute(
        """
        INSERT INTO active_army_runtime (
            army_id, domain_id, card_id, count, location_node_id, status, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?)
        ON CONFLICT(army_id) DO UPDATE SET
            count = active_army_runtime.count + excluded.count,
            location_node_id = excluded.location_node_id,
            updated_at = excluded.updated_at
        """,
        (army_id, domain_id, card_id, count, residence, now),
    )
    result = {
        "status": "active_army_updated",
        "domain_id": domain_id,
        "card_id": card_id,
        "count": count,
        "gold_spent": gold_cost,
        "location_node_id": residence,
        "capacity": capacity,
    }
    log_event(connection, "lord_reserve_to_active", result, source=source)
    return result


def _award_pending_tick_rewards(
    connection: sqlite3.Connection, domain_id: str, territory_id: str, now: str
) -> list[dict[str, Any]]:
    rows = _rows(
        connection,
        """
        SELECT pending_reward_id, reward_gold
        FROM pending_tick_reward_runtime
        WHERE territory_id = ? AND status = 'pending'
        ORDER BY due_at
        """,
        (territory_id,),
    )
    awards = []
    for row in rows:
        connection.execute(
            """
            UPDATE pending_tick_reward_runtime
            SET status = 'awarded', awarded_to_domain_id = ?, awarded_at = ?
            WHERE pending_reward_id = ?
            """,
            (domain_id, now, row["pending_reward_id"]),
        )
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET gold = gold + ?, updated_at = ?
            WHERE domain_id = ?
            """,
            (_to_int(row["reward_gold"]), now, domain_id),
        )
        awards.append(
            {
                "pending_reward_id": row["pending_reward_id"],
                "reward_gold": _to_int(row["reward_gold"]),
                "awarded_to_domain_id": domain_id,
            }
        )
    return awards


def _capture_ready_claim(
    connection: sqlite3.Connection, territory_id: str, domain_id: str
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT claim_id, territory_id, claimant_domain_id, status
        FROM territory_claim_runtime
        WHERE territory_id = ?
          AND claimant_domain_id = ?
          AND status = 'awaiting_garrison'
        ORDER BY resolved_at DESC, created_at DESC
        LIMIT 1
        """,
        (territory_id, domain_id),
    ).fetchone()


def _assert_local_owned_transfer_territory(
    connection: sqlite3.Connection, domain_id: str, territory: sqlite3.Row
) -> None:
    territory_id = str(territory["territory_id"])
    if _optional(territory["owner_domain_id"]) != domain_id:
        raise LordRuntimeError(
            "territory_not_owned",
            "Fort transfers require a territory controlled by the lord domain.",
        )
    if (
        str(territory["status"]) in LOCKED_GARRISON_TRANSFER_STATUSES
        or _optional(territory["contested_by_domain_id"]) is not None
    ):
        raise LordRuntimeError(
            "territory_contested",
            "Contested territory cannot be changed by garrison transfer until its claim is resolved.",
        )
    if _current_territory_id(connection, domain_id) != territory_id:
        raise LordRuntimeError(
            "army_not_at_territory",
            "Fort transfers are local to the lord army's current territory.",
        )


def _active_army_at_territory(
    connection: sqlite3.Connection, domain_id: str, territory_id: str
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM active_army_runtime army
        JOIN map_nodes node ON node.node_id = army.location_node_id
        WHERE army.domain_id = ?
          AND army.status = 'active'
          AND army.count > 0
          AND node.territory_id = ?
        LIMIT 1
        """,
        (domain_id, territory_id),
    ).fetchone()
    return row is not None


def _active_army_at_node(
    connection: sqlite3.Connection, domain_id: str, node_id: str
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM active_army_runtime
        WHERE domain_id = ?
          AND status = 'active'
          AND count > 0
          AND location_node_id = ?
        LIMIT 1
        """,
        (domain_id, node_id),
    ).fetchone()
    return row is not None


def _current_territory_id(connection: sqlite3.Connection, domain_id: str) -> str | None:
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


def _node_for_territory(connection: sqlite3.Connection, territory_id: str) -> str:
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
    if row is None:
        raise LordRuntimeError("territory_node_not_found", "Territory has no map node.")
    return str(row["node_id"])


def _complete_pending_lord_move(
    connection: sqlite3.Connection, move: sqlite3.Row, completed_at: str
) -> dict[str, Any]:
    route = json.loads(move["route_node_ids_json"] or "[]")
    target_node_id = str(move["to_node_id"])
    connection.execute(
        """
        UPDATE domain_runtime_state
        SET current_node_id = ?, updated_at = ?
        WHERE domain_id = ?
        """,
        (target_node_id, completed_at, move["domain_id"]),
    )
    connection.execute(
        """
        UPDATE active_army_runtime
        SET location_node_id = ?, updated_at = ?
        WHERE domain_id = ? AND status = 'active' AND count > 0
        """,
        (target_node_id, completed_at, move["domain_id"]),
    )
    claim = _create_claim_if_needed(
        connection,
        domain_id=str(move["domain_id"]),
        target_node_id=target_node_id,
        now=completed_at,
        source=str(move["source"]),
    )
    result = {
        "status": "moved",
        "move_id": move["move_id"],
        "domain_id": move["domain_id"],
        "lord_id": move["lord_id"],
        "from_node_id": move["from_node_id"],
        "to_node_id": target_node_id,
        "requested_to_node_id": move["requested_to_node_id"],
        "route": route,
        "mp_spent": _to_int(move["mp_cost"]),
        "battle_spent_mp": 0,
        "claim": claim,
        "completed_at": completed_at,
    }
    connection.execute(
        """
        UPDATE pending_lord_moves
        SET status = 'completed', completed_at = ?, result_json = ?
        WHERE move_id = ?
        """,
        (completed_at, json.dumps(result, ensure_ascii=True), move["move_id"]),
    )
    log_event(connection, "lord_move_arrived", result, source=str(move["source"]))
    return result


def _pending_move_payload(row: sqlite3.Row) -> dict[str, Any]:
    result = json.loads(row["result_json"] or "{}")
    route = json.loads(row["route_node_ids_json"] or "[]")
    return {
        "move_id": row["move_id"],
        "domain_id": row["domain_id"],
        "lord_id": row["lord_id"],
        "from_node_id": row["from_node_id"],
        "to_node_id": row["to_node_id"],
        "requested_to_node_id": row["requested_to_node_id"],
        "route": route,
        "mp_cost": _to_int(row["mp_cost"]),
        "mp_spent": _to_int(row["mp_cost"]),
        "status": row["status"],
        "source": row["source"],
        "started_at": row["started_at"],
        "arrival_at": row["arrival_at"],
        "completed_at": row["completed_at"],
        "result": result,
    }


def _movement_duration_seconds(route: list[str]) -> int:
    return max(1, len(route) - 1) * LORD_MOVE_SECONDS_PER_EDGE


def _route_stopped_for_blocking_territory(
    connection: sqlite3.Connection, domain_id: str, route: list[str]
) -> list[str]:
    stopped = [route[0]]
    for index, node_id in enumerate(route[1:], start=1):
        _assert_movement_node_allowed(
            connection,
            domain_id,
            node_id,
            route_position="target" if index == len(route) - 1 else "route",
        )
        stopped.append(node_id)
        if index < len(route) - 1 and _node_blocks_route(connection, domain_id, node_id):
            break
    return stopped


def _planned_movement_route(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    current_node_id: str,
    requested_to_node_id: str,
    route_node_ids: list[str] | None,
) -> list[str]:
    _assert_movement_node_allowed(
        connection,
        domain_id,
        requested_to_node_id,
        route_position="target",
    )
    route = [node for node in (route_node_ids or []) if node]
    if route:
        if route[0] != current_node_id:
            route = [current_node_id, *route]
        if route[-1] != requested_to_node_id:
            if not _node_blocks_route(connection, domain_id, route[-1]):
                raise LordRuntimeError(
                    "route_target_mismatch",
                    "Route final node must match to_node_id or stop at a blocking territory.",
                )
    else:
        route = _shortest_movement_route(
            connection,
            domain_id=domain_id,
            current_node_id=current_node_id,
            requested_to_node_id=requested_to_node_id,
        )
    if len(route) < 2:
        raise LordRuntimeError("missing_route", "Movement requires a target node or route.")
    return _route_stopped_for_blocking_territory(connection, domain_id, route)


def _shortest_movement_route(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    current_node_id: str,
    requested_to_node_id: str,
) -> list[str]:
    edges = connection.execute(
        """
        SELECT from_node_id, to_node_id, mp_cost, bidirectional
        FROM map_edges
        ORDER BY _row_number
        """
    ).fetchall()
    graph: dict[str, list[tuple[str, int]]] = {}
    for edge in edges:
        cost = _to_int(edge["mp_cost"])
        if cost <= 0:
            raise LordRuntimeError(
                "invalid_route_cost",
                f"Map edge between {edge['from_node_id']} and {edge['to_node_id']} must have positive MP cost.",
            )
        graph.setdefault(str(edge["from_node_id"]), []).append((str(edge["to_node_id"]), cost))
        if str(edge["bidirectional"]).lower() == "true" or edge["bidirectional"] is True:
            graph.setdefault(str(edge["to_node_id"]), []).append((str(edge["from_node_id"]), cost))

    route = _dijkstra_route(
        graph,
        current_node_id,
        requested_to_node_id,
        can_expand=lambda node_id: not _node_blocks_route(connection, domain_id, node_id),
        can_enter=lambda node_id: _movement_node_can_enter(
            connection,
            domain_id,
            node_id,
            route_position="target" if node_id == requested_to_node_id else "route",
        ),
    )
    if route is not None:
        return route

    raw_route = _dijkstra_route(
        graph,
        current_node_id,
        requested_to_node_id,
        can_expand=lambda _node_id: True,
        can_enter=lambda node_id: _movement_node_can_enter(
            connection,
            domain_id,
            node_id,
            route_position="target" if node_id == requested_to_node_id else "route",
        ),
    )
    if raw_route is not None:
        return raw_route
    raise LordRuntimeError(
        "invalid_route",
        f"No map route between {current_node_id} and {requested_to_node_id}.",
    )


def _dijkstra_route(
    graph: dict[str, list[tuple[str, int]]],
    start_node_id: str,
    target_node_id: str,
    *,
    can_expand,
    can_enter,
) -> list[str] | None:
    distances: dict[str, int] = {start_node_id: 0}
    previous: dict[str, str] = {}
    pending = {start_node_id}
    visited: set[str] = set()
    while pending:
        current = min(pending, key=lambda node_id: distances.get(node_id, 10**9))
        pending.remove(current)
        if current in visited:
            continue
        visited.add(current)
        if current == target_node_id:
            break
        if current != start_node_id and not can_expand(current):
            continue
        for neighbor, cost in graph.get(current, []):
            if neighbor in visited or not can_enter(neighbor):
                continue
            candidate = distances[current] + cost
            if candidate < distances.get(neighbor, 10**9):
                distances[neighbor] = candidate
                previous[neighbor] = current
                pending.add(neighbor)

    if target_node_id not in distances:
        return None
    route = [target_node_id]
    while route[0] != start_node_id:
        prior = previous.get(route[0])
        if prior is None:
            return None
        route.insert(0, prior)
    return route


def _movement_node_can_enter(
    connection: sqlite3.Connection,
    domain_id: str,
    node_id: str,
    *,
    route_position: str,
) -> bool:
    try:
        _assert_movement_node_allowed(
            connection,
            domain_id,
            node_id,
            route_position=route_position,
        )
    except LordRuntimeError:
        return False
    return True


def _assert_movement_node_allowed(
    connection: sqlite3.Connection,
    domain_id: str,
    node_id: str,
    *,
    route_position: str,
) -> None:
    node = _movement_node(connection, node_id)
    if str(node["zone_status"]) == "no_play_excluded" or str(node["node_type"]) == "no_play_zone":
        raise LordRuntimeError(
            "forbidden_map_target",
            "Excluded map zones cannot be used for lord movement.",
        )
    owner_domain_id = _optional(node["owner_domain_id"])
    if str(node["node_type"]) == "residence" or str(node["bonus_type"]) == "residence":
        if owner_domain_id != domain_id:
            code = "forbidden_residence_route" if route_position == "route" else "forbidden_residence_target"
            raise LordRuntimeError(
                code,
                "Lord residences are raid-only and cannot be attacked by ordinary movement.",
            )


def _movement_node(connection: sqlite3.Connection, node_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT
            n.node_id,
            n.node_type,
            n.zone_status,
            n.territory_id,
            tr.owner_domain_id,
            tr.status,
            tr.contested_by_domain_id,
            t.bonus_type
        FROM map_nodes n
        LEFT JOIN territory_runtime_state tr ON tr.territory_id = n.territory_id
        LEFT JOIN territories t ON t.territory_id = n.territory_id
        WHERE n.node_id = ?
        LIMIT 1
        """,
        (node_id,),
    ).fetchone()
    if row is None:
        raise LordRuntimeError("map_node_not_found", "Map node is not available.", 404)
    return row


def _node_blocks_route(
    connection: sqlite3.Connection, domain_id: str, node_id: str
) -> bool:
    node = _movement_node(connection, node_id)
    territory_id = _optional(node["territory_id"])
    if territory_id is None:
        return False
    if _optional(node["owner_domain_id"]) != domain_id:
        return True
    if _optional(node["contested_by_domain_id"]) is not None:
        return True
    return str(node["status"]) in BLOCKING_ROUTE_STATUSES


def _front_locked_movement_reason(
    connection: sqlite3.Connection,
    domain_id: str,
    *,
    current_node_id: str,
    target_node_id: str,
) -> str | None:
    if not _node_blocks_route(connection, domain_id, current_node_id):
        return None
    if not _node_blocks_route(connection, domain_id, target_node_id):
        return None
    return FRONT_LOCKED_ROUTE_MESSAGE


def _route_cost(connection: sqlite3.Connection, route: list[str]) -> int:
    total = 0
    for from_node, to_node in zip(route, route[1:]):
        edge = connection.execute(
            """
            SELECT mp_cost
            FROM map_edges
            WHERE (from_node_id = ? AND to_node_id = ?)
               OR (bidirectional = 'true' AND from_node_id = ? AND to_node_id = ?)
            ORDER BY _row_number
            LIMIT 1
            """,
            (from_node, to_node, to_node, from_node),
        ).fetchone()
        if edge is None:
            raise LordRuntimeError("invalid_route", f"No map edge between {from_node} and {to_node}.")
        mp_cost = _to_int(edge["mp_cost"])
        if mp_cost <= 0:
            raise LordRuntimeError(
                "invalid_route_cost",
                f"Map edge between {from_node} and {to_node} must have positive MP cost.",
            )
        total += mp_cost
    return total


def _movement_outcome_preview(
    connection: sqlite3.Connection, domain_id: str, target_node_id: str
) -> dict[str, Any]:
    node = _movement_node(connection, target_node_id)
    territory_id = _optional(node["territory_id"])
    if territory_id is None:
        return {"kind": "waypoint", "battle_required": False}
    owner_domain_id = _optional(node["owner_domain_id"])
    if owner_domain_id == domain_id:
        return {
            "kind": "controlled",
            "territory_id": territory_id,
            "owner_domain_id": owner_domain_id,
            "battle_required": False,
        }
    existing = connection.execute(
        """
        SELECT claim_id, territory_id, claimant_domain_id, defender_domain_id, status
        FROM territory_claim_runtime
        WHERE territory_id = ?
          AND status IN ('in_battle', 'contested', 'contested_pending_tick', 'awaiting_garrison')
        ORDER BY created_at
        LIMIT 1
        """,
        (territory_id,),
    ).fetchone()
    if existing is not None:
        existing_status = str(existing["status"] or "")
        return {
            "kind": "existing_claim",
            "territory_id": territory_id,
            "owner_domain_id": owner_domain_id,
            "battle_required": existing_status in BATTLE_REQUIRED_CLAIM_STATUSES,
            "garrison_required": existing_status in GARRISON_PENDING_CLAIM_STATUSES,
            "claim": dict(existing),
        }
    return {
        "kind": "will_create_claim",
        "territory_id": territory_id,
        "owner_domain_id": owner_domain_id,
        "defender_domain_id": owner_domain_id,
        "battle_required": True,
    }


def _domain_for_lord(connection: sqlite3.Connection, lord_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT d.*
        FROM domain_runtime_state d
        WHERE d.lord_player_id = ?
        """,
        (lord_id,),
    ).fetchone()
    if row is None:
        raise LordRuntimeError("lord_domain_not_found", "Lord domain is not available.", 404)
    return row


def _domain_by_id(connection: sqlite3.Connection, domain_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM domain_runtime_state WHERE domain_id = ?",
        (domain_id,),
    ).fetchone()
    if row is None:
        raise LordRuntimeError("domain_not_found", "Domain is not available.", 404)
    return row


def _territory_state(connection: sqlite3.Connection, territory_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM territory_runtime_state WHERE territory_id = ?",
        (territory_id,),
    ).fetchone()
    if row is None:
        raise LordRuntimeError("territory_not_found", "Territory is not available.", 404)
    return row


def _backfill_domain_building_territories(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "domain_buildings") or not _table_exists(
        connection,
        "territories",
    ):
        return
    rows = connection.execute(
        """
        SELECT rowid AS building_rowid, domain_id, territory_id, building_id, purchased_at
        FROM domain_buildings
        ORDER BY domain_id, building_id, purchased_at
        """
    ).fetchall()
    for row in rows:
        residence_id = _residence_territory(connection, str(row["domain_id"]))
        if not residence_id:
            continue
        current_territory_id = _optional(row["territory_id"])
        current_content = (
            _territory_content_row(connection, current_territory_id)
            if current_territory_id
            else None
        )
        if (
            current_territory_id == residence_id
            and current_content is not None
            and _is_residence_territory_row(current_content)
        ):
            continue
        try:
            connection.execute(
                """
                UPDATE domain_buildings
                SET territory_id = ?
                WHERE rowid = ?
                """,
                (
                    residence_id,
                    row["building_rowid"],
                ),
            )
        except sqlite3.IntegrityError:
            connection.execute(
                """
                DELETE FROM domain_buildings
                WHERE rowid = ?
                """,
                (row["building_rowid"],),
            )


def _territory_content_row(
    connection: sqlite3.Connection, territory_id: str
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM territories WHERE territory_id = ?",
        (territory_id,),
    ).fetchone()


def _residence_territory(connection: sqlite3.Connection, domain_id: str) -> str | None:
    row = connection.execute(
        """
        SELECT t.territory_id
        FROM territories t
        LEFT JOIN territory_runtime_state rt ON rt.territory_id = t.territory_id
        WHERE COALESCE(rt.owner_domain_id, t.owner_domain_id) = ?
          AND t.bonus_type = 'residence'
        ORDER BY t._row_number
        LIMIT 1
        """,
        (domain_id,),
    ).fetchone()
    return _optional(row["territory_id"]) if row else None


def _building_purchase_territory_id(
    connection: sqlite3.Connection,
    domain_id: str,
    territory_id: str | None,
) -> str:
    residence_id = _residence_territory(connection, domain_id)
    scoped_territory_id = _optional(territory_id) or residence_id
    if not scoped_territory_id or not residence_id:
        raise LordRuntimeError(
            "missing_building_territory",
            "Building purchase requires the lord residence.",
        )
    territory = _territory_state(connection, scoped_territory_id)
    content = _territory_content_row(connection, scoped_territory_id)
    owner_domain_id = _optional(territory["owner_domain_id"]) or _optional(
        content["owner_domain_id"] if content is not None else None
    )
    if owner_domain_id != domain_id:
        raise LordRuntimeError(
            "territory_not_owned",
            "Building purchase is available only in controlled territories.",
            403,
        )
    if scoped_territory_id != residence_id or content is None or not _is_residence_territory_row(content):
        raise LordRuntimeError(
            "building_tree_residence_only",
            "Buildings can be constructed only in the lord residence.",
        )
    return scoped_territory_id


def _assert_building_allowed_for_territory(
    connection: sqlite3.Connection,
    territory_id: str,
    building_id: str,
) -> None:
    territory = _territory_content_row(connection, territory_id)
    if territory is None:
        raise LordRuntimeError("territory_not_found", "Territory is not available.", 404)
    if _is_residence_territory_row(territory):
        return
    raise LordRuntimeError(
        "building_tree_residence_only",
        "Buildings can be constructed only in the lord residence.",
    )


def _territory_building_ids(
    connection: sqlite3.Connection,
    territory: sqlite3.Row,
) -> list[str]:
    bonus_type = str(territory["bonus_type"] or "")
    base_ids = TERRITORY_BUILDING_TREE_IDS.get(
        bonus_type,
        ["b_training_yard", "b_market", "b_wards"],
    )
    buildings = {
        str(row["building_id"]): row
        for row in connection.execute("SELECT * FROM buildings").fetchall()
    }
    visible: set[str] = set()
    stack = list(base_ids)
    while stack:
        current_id = stack.pop()
        if current_id in visible:
            continue
        visible.add(current_id)
        building = buildings.get(current_id)
        if building is None:
            continue
        stack.extend(split_ids(str(building["prerequisite_ids"])))
    return [
        str(row["building_id"])
        for row in connection.execute("SELECT building_id FROM buildings ORDER BY _row_number").fetchall()
        if str(row["building_id"]) in visible
    ]


def _is_residence_territory_row(territory: sqlite3.Row) -> bool:
    territory_id = str(territory["territory_id"] or "")
    return str(territory["bonus_type"] or "") == "residence" or territory_id.startswith(
        "territory_res_"
    )


def _building(connection: sqlite3.Connection, building_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM buildings WHERE building_id = ?",
        (building_id,),
    ).fetchone()
    if row is None:
        raise LordRuntimeError("building_not_found", "Building is not available.", 404)
    return row


def _has_building(connection: sqlite3.Connection, domain_id: str, building_id: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM domain_buildings
        WHERE domain_id = ? AND building_id = ?
        """,
        (domain_id, building_id),
    ).fetchone()
    return row is not None


def _has_building_at(
    connection: sqlite3.Connection,
    domain_id: str,
    territory_id: str,
    building_id: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM domain_buildings
        WHERE domain_id = ? AND territory_id = ? AND building_id = ?
        """,
        (domain_id, territory_id, building_id),
    ).fetchone()
    return row is not None


def _recruit_offer(
    connection: sqlite3.Connection, offer_id: str, domain_id: str
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT *
        FROM recruit_offer_runtime
        WHERE offer_id = ? AND domain_id = ?
        """,
        (offer_id, domain_id),
    ).fetchone()
    if row is None:
        raise LordRuntimeError("offer_not_found", "Recruit offer is not available.", 404)
    return row


def _raid_rule(connection: sqlite3.Connection, rule_id: str | None) -> sqlite3.Row:
    if rule_id:
        row = connection.execute(
            "SELECT * FROM raid_rules WHERE rule_id = ?",
            (rule_id,),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT * FROM raid_rules ORDER BY _row_number LIMIT 1"
        ).fetchone()
    if row is None:
        raise LordRuntimeError("raid_rule_not_found", "Raid rule is not available.", 404)
    return row


def _raid_rule_value(rule: sqlite3.Row, column_name: str, fallback: str = "") -> str:
    if column_name not in rule.keys():
        return fallback
    return str(rule[column_name] or fallback)


def _row_value(row: sqlite3.Row, column_name: str, fallback: object = None) -> object:
    if column_name not in row.keys():
        return fallback
    return row[column_name]


def _building_raid_token_delta(building: sqlite3.Row) -> int:
    explicit_delta = _row_value(building, "raid_token_delta")
    if explicit_delta is not None and str(explicit_delta) != "":
        return max(0, _to_int(explicit_delta))
    return 1 if _truthy(_row_value(building, "raid_unlock", False)) else 0


def _owned_building_ids(connection: sqlite3.Connection, domain_id: str) -> set[str]:
    if not _table_exists(connection, "domain_buildings"):
        return set()
    return {
        str(row["building_id"])
        for row in connection.execute(
            """
            SELECT DISTINCT building_id
            FROM domain_buildings
            WHERE domain_id = ?
            """,
            (domain_id,),
        ).fetchall()
    }


def building_flat_income_bonus_for_domain(
    connection: sqlite3.Connection, domain_id: str
) -> int:
    return flat_income_bonus(_owned_building_ids(connection, domain_id))


def building_territory_income_bonus_percent_for_domain(
    connection: sqlite3.Connection, domain_id: str
) -> int:
    return territory_income_bonus_percent(_owned_building_ids(connection, domain_id))


def building_treasury_income_floor_percent_for_domain(
    connection: sqlite3.Connection, domain_id: str
) -> int:
    return treasury_income_floor_percent(_owned_building_ids(connection, domain_id))


def _recruit_stock_cap_for_domain(
    connection: sqlite3.Connection,
    domain_id: str,
    unit_class: str,
    fallback: int,
) -> int:
    growth = recruit_growth_per_hour_for_unit_class(unit_class)
    cap = max(1, (growth or fallback) * BASE_RECRUIT_STOCK_CAP_TICKS)
    percent = stock_cap_percent(_owned_building_ids(connection, domain_id))
    return max(1, (cap * percent) // 100)


def _raid_token_cap_for_domain(connection: sqlite3.Connection, domain_id: str) -> int:
    cap = BASE_RAID_TOKEN_CAP
    if _table_exists(connection, "domain_buildings") and _table_exists(connection, "buildings"):
        for building in connection.execute(
            """
            SELECT b.*
            FROM domain_buildings db
            JOIN buildings b ON b.building_id = db.building_id
            WHERE db.domain_id = ?
            ORDER BY db.purchased_at, db.building_id
            """,
            (domain_id,),
        ).fetchall():
            cap += _building_raid_token_delta(building)
    cap += controlled_domain_numeric_bonus(connection, domain_id, "raid_token_cap")
    return max(BASE_RAID_TOKEN_CAP, cap)


def _active_raid_effect_payloads(
    connection: sqlite3.Connection,
    where_sql: str,
    params: tuple[object, ...],
) -> list[dict[str, Any]]:
    if not _table_exists(connection, "raid_effects"):
        return []
    effects: list[dict[str, Any]] = []
    for row in connection.execute(
        f"""
        SELECT *
        FROM raid_effects
        WHERE status = 'active' AND {where_sql}
        ORDER BY started_at, raid_effect_id
        """,
        params,
    ).fetchall():
        payload = _json_loads(row["payload_json"], {})
        if payload.get("effect_applied") is False:
            continue
        effects.append(
            {
                "raid_effect_id": row["raid_effect_id"],
                "rule_id": row["rule_id"],
                "source_domain_id": row["source_domain_id"],
                "target_domain_id": row["target_domain_id"],
                "target_territory_id": row["target_territory_id"],
                "status": row["status"],
                "started_at": row["started_at"],
                "expires_at": row["expires_at"],
                **payload,
            }
        )
    return effects


def _territory_content(
    connection: sqlite3.Connection, territory_id: str
) -> sqlite3.Row | None:
    try:
        return connection.execute(
            "SELECT * FROM territories WHERE territory_id = ?",
            (territory_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None


def _raid_target_type(territory: sqlite3.Row | None) -> str:
    bonus_type = str(territory["bonus_type"] or "") if territory is not None else ""
    return "residence" if bonus_type == "residence" else "territory"


def _active_raid_effect_exists(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    target_territory_id: str,
    rule_id: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM raid_effects
        WHERE source_domain_id = ?
          AND target_territory_id = ?
          AND rule_id = ?
          AND status = 'active'
        LIMIT 1
        """,
        (domain_id, target_territory_id, rule_id),
    ).fetchone()
    return row is not None


def _order_for_lord(
    connection: sqlite3.Connection, lord_id: str, order_id: str
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM order_runtime_state WHERE order_id = ? AND lord_id = ?",
        (order_id, lord_id),
    ).fetchone()
    if row is None:
        raise LordRuntimeError("order_not_found", "Order is not available.", 404)
    return row


def _order_payload(connection: sqlite3.Connection, order_id: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM order_runtime_state WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    payload = dict(row)
    payload["escrow"] = [
        dict(item)
        for item in connection.execute(
            "SELECT * FROM escrow_ledger WHERE order_id = ? ORDER BY created_at",
            (order_id,),
        ).fetchall()
    ]
    return payload


def _transition_order(
    connection: sqlite3.Connection,
    order: sqlite3.Row,
    status: str,
    *,
    now: str,
    reason: str | None = None,
) -> None:
    connection.execute(
        """
        UPDATE order_runtime_state
        SET status = ?, reason = COALESCE(?, reason), updated_at = ?
        WHERE order_id = ?
        """,
        (status, reason, now, order["order_id"]),
    )


def _assert_order_action_authority(action: str, actor_role: str) -> None:
    if action in PLAYER_ORDER_ACTIONS and actor_role not in {"player", "master"}:
        raise LordRuntimeError(
            "order_player_auth_required",
            "Order accept/submit requires player auth or master recovery.",
            status_code=403,
        )
    if action in MASTER_ORDER_ACTIONS and actor_role != "master":
        raise LordRuntimeError(
            "order_master_approval_required",
            "Order completion and escrow award require master approval.",
            status_code=403,
        )
    if action in LORD_ORDER_MANAGEMENT_ACTIONS and actor_role not in {"lord", "master"}:
        raise LordRuntimeError(
            "order_lord_auth_required",
            "Order offer management requires lord or master authority.",
            status_code=403,
        )


def _assert_master_recovery_reason(
    action: str,
    actor_role: str,
    source: str,
    reason: str | None,
) -> None:
    if actor_role != "master" or source not in ORDER_MASTER_RECOVERY_SOURCES:
        return
    if reason and reason.strip():
        return
    raise LordRuntimeError(
        "missing_order_recovery_reason",
        f"Master {action} requires an audit reason.",
    )


def _order_building_gate_bypassed(source: str, actor_role: str) -> bool:
    return actor_role == "master" or source in (
        FINAL_LOCK_ORDER_OVERRIDE_SOURCES | ORDER_MASTER_RECOVERY_SOURCES
    )


def _assert_order_building_unlocked(
    connection: sqlite3.Connection,
    domain_id: str,
    visibility: str,
    *,
    source: str,
    actor_role: str,
) -> None:
    if _order_building_gate_bypassed(source, actor_role):
        return
    if visibility == "public" and not _has_building(
        connection,
        domain_id,
        PUBLIC_ORDER_BUILDING_ID,
    ):
        raise LordRuntimeError(
            "public_orders_locked",
            "Public orders require Notice Board in the residence.",
        )
    if visibility == "addressed" and not _has_building(
        connection,
        domain_id,
        ADDRESSED_ORDER_BUILDING_ID,
    ):
        raise LordRuntimeError(
            "addressed_orders_locked",
            "Addressed orders require Envoy Hall in the residence.",
        )


def _close_competing_orders(
    connection: sqlite3.Connection,
    *,
    object_id: str,
    winner_order_id: str,
    now: str,
) -> list[str]:
    closed: list[str] = []
    count_statuses = _order_statuses_counting_against_cap(connection)
    if not count_statuses:
        return closed
    for row in connection.execute(
        """
        SELECT order_id
        FROM order_runtime_state
        WHERE object_id = ?
          AND order_id <> ?
          AND status IN ({})
        ORDER BY created_at
        """.format(_status_placeholders(count_statuses)),
        (object_id, winner_order_id, *sorted(count_statuses)),
    ).fetchall():
        updated = connection.execute(
            """
            UPDATE order_runtime_state
            SET status = 'failed_closed',
                reason = 'object_already_completed',
                updated_at = ?
            WHERE order_id = ?
              AND status IN ({})
            """.format(_status_placeholders(count_statuses)),
            (now, row["order_id"], *sorted(count_statuses)),
        )
        if updated.rowcount:
            _refund_order_escrow(
                connection,
                str(row["order_id"]),
                now=now,
                reason="object_already_completed",
            )
            closed.append(str(row["order_id"]))
    return closed


def _assert_order_cap(connection: sqlite3.Connection, lord_id: str, visibility: str) -> None:
    domain = _domain_for_lord(connection, lord_id)
    domain_id = str(domain["domain_id"])
    if visibility == "public":
        cap = 2 if _has_building(connection, domain_id, PUBLIC_ORDER_BUILDING_ID) else 0
    else:
        cap = 1 if _has_building(connection, domain_id, ADDRESSED_ORDER_BUILDING_ID) else 0
    if visibility == "public":
        cap = max(0, cap - raid_order_public_cap_penalty_for_domain(connection, domain_id))
    count_statuses = _order_statuses_counting_against_cap(connection)
    if not count_statuses:
        return
    count = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM order_runtime_state
        WHERE lord_id = ? AND visibility = ? AND status IN ({_status_placeholders(count_statuses)})
        """,
        (lord_id, visibility, *sorted(count_statuses)),
    ).fetchone()[0]
    if int(count) >= cap:
        raise LordRuntimeError(
            "order_cap_exceeded",
            f"Lord has {count} active {visibility} orders; cap is {cap}.",
        )


def _assert_player_object_available(
    connection: sqlite3.Connection,
    player_id: str,
    object_id: str,
    *,
    exclude_order_id: str | None = None,
) -> None:
    lock_statuses = _order_statuses_locking_objects(connection)
    if not lock_statuses:
        return
    params: list[object] = [player_id, player_id, object_id, *sorted(lock_statuses)]
    extra = ""
    if exclude_order_id:
        extra = "AND order_id <> ?"
        params.append(exclude_order_id)
    row = connection.execute(
        f"""
        SELECT order_id
        FROM order_runtime_state
        WHERE (accepted_by_player_id = ? OR target_player_id = ?)
          AND object_id = ?
          AND status IN ({_status_placeholders(lock_statuses)})
          {extra}
        LIMIT 1
        """,
        params,
    ).fetchone()
    if row is not None:
        raise LordRuntimeError(
            "order_object_conflict",
            "Player already has an active order for this object.",
        )


def _assert_order_recipient_exists(connection: sqlite3.Connection, player_id: str) -> None:
    row = connection.execute(
        """
        SELECT player_id
        FROM players
        WHERE player_id = ?
          AND role_type IN ('witcher', 'sorceress')
        LIMIT 1
        """,
        (player_id,),
    ).fetchone()
    if row is None:
        raise LordRuntimeError(
            "invalid_addressed_target",
            "Addressed order target must be an eligible witcher or sorceress.",
        )


def _assert_order_object_exists(connection: sqlite3.Connection, object_id: str) -> None:
    checks = (
        ("order_interest_objects", "interest_id"),
        ("qr_objects", "qr_id"),
        ("territories", "territory_id"),
        ("items", "item_id"),
        ("cards", "card_id"),
        ("artifacts", "artifact_id"),
    )
    for table_name, column_name in checks:
        if not _table_exists(connection, table_name):
            continue
        row = connection.execute(
            f"SELECT 1 FROM {table_name} WHERE {column_name} = ? LIMIT 1",
            (object_id,),
        ).fetchone()
        if row is not None:
            return
    raise LordRuntimeError("unknown_order_object", "Order object is not in runtime content.")


def _reserve_order_escrow(
    connection: sqlite3.Connection,
    order_id: str,
    *,
    lord_id: str,
    reward_id: str,
    debit_domain: bool,
    now: str,
    domain: sqlite3.Row | None = None,
) -> dict[str, Any]:
    ledger_id = _stable_id("escrow", order_id, reward_id)
    existing = connection.execute(
        "SELECT * FROM escrow_ledger WHERE ledger_id = ?",
        (ledger_id,),
    ).fetchone()
    if existing is not None:
        return dict(existing)

    domain = domain or _domain_for_lord(connection, lord_id)
    try:
        numeric = reward_numeric_payload(connection, reward_id)
        assets = reward_asset_entries(connection, reward_id)
    except AssetContractError as exc:
        raise LordRuntimeError(exc.code, str(exc), exc.status_code) from exc

    reserved_gold = _to_int(numeric["gold"])
    if debit_domain and reserved_gold > 0:
        fresh_domain = _domain_by_id(connection, str(domain["domain_id"]))
        if _to_int(fresh_domain["gold"]) < reserved_gold:
            raise LordRuntimeError(
                "insufficient_escrow_gold",
                f"Order escrow needs {reserved_gold} gold, but domain has {fresh_domain['gold']}.",
            )
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET gold = gold - ?, updated_at = ?
            WHERE domain_id = ?
            """,
            (reserved_gold, now, domain["domain_id"]),
        )

    connection.execute(
        """
        INSERT INTO escrow_ledger (
            ledger_id, order_id, reward_id, status, created_at,
            reserved_gold, reserved_xp, reserved_assets_json, reserved_from_domain_id
        )
        VALUES (?, ?, ?, 'reserved', ?, ?, ?, ?, ?)
        ON CONFLICT(ledger_id) DO NOTHING
        """,
        (
            ledger_id,
            order_id,
            reward_id,
            now,
            reserved_gold,
            _to_int(numeric["xp"]),
            _json_dumps(assets),
            domain["domain_id"],
        ),
    )
    return dict(
        connection.execute(
            "SELECT * FROM escrow_ledger WHERE ledger_id = ?",
            (ledger_id,),
        ).fetchone()
    )


def _refund_order_escrow(
    connection: sqlite3.Connection,
    order_id: str,
    *,
    now: str,
    reason: str,
) -> dict[str, Any]:
    rows = _reserved_escrow_rows(connection, order_id)
    refunded_gold = 0
    for row in rows:
        reserved_gold = _to_int(row["reserved_gold"])
        domain_id = _optional(row["reserved_from_domain_id"])
        if reserved_gold > 0 and domain_id:
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET gold = gold + ?, updated_at = ?
                WHERE domain_id = ?
                """,
                (reserved_gold, now, domain_id),
            )
            refunded_gold += reserved_gold
    connection.execute(
        """
        UPDATE escrow_ledger
        SET status = 'released', released_at = ?, reason = ?
        WHERE order_id = ? AND status = 'reserved'
        """,
        (now, reason, order_id),
    )
    return {
        "status": "released" if rows else "already_settled",
        "order_id": order_id,
        "refunded_gold": refunded_gold,
        "released_rewards": [str(row["reward_id"]) for row in rows],
    }


def _award_order_escrow(
    connection: sqlite3.Connection,
    order_id: str,
    *,
    target_player_id: str,
    now: str,
    reason: str,
) -> dict[str, Any]:
    rows = _reserved_escrow_rows(connection, order_id)
    if not rows:
        return {
            "status": "already_settled",
            "order_id": order_id,
            "awarded_to_player_id": target_player_id,
            "rewards": [],
        }

    rewards = [
        _apply_order_reward(
            connection,
            order_id=order_id,
            ledger=row,
            target_player_id=target_player_id,
            now=now,
        )
        for row in rows
    ]
    connection.execute(
        """
        UPDATE escrow_ledger
        SET status = 'awarded', released_at = ?, reason = ?, awarded_to_player_id = ?
        WHERE order_id = ? AND status = 'reserved'
        """,
        (now, reason, target_player_id, order_id),
    )
    return {
        "status": "applied",
        "order_id": order_id,
        "awarded_to_player_id": target_player_id,
        "rewards": rewards,
    }


def _reserved_escrow_rows(connection: sqlite3.Connection, order_id: str) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT *
        FROM escrow_ledger
        WHERE order_id = ? AND status = 'reserved'
        ORDER BY created_at, ledger_id
        """,
        (order_id,),
    ).fetchall()


def _apply_order_reward(
    connection: sqlite3.Connection,
    *,
    order_id: str,
    ledger: sqlite3.Row,
    target_player_id: str,
    now: str,
) -> dict[str, Any]:
    player = _runtime_player(connection, target_player_id, now=now)
    xp_before = _to_int(player.get("xp"))
    level_before = _to_int(player.get("level"))
    gold_before = _to_int(player.get("gold"))
    xp_gain = _to_int(ledger["reserved_xp"])
    gold_gain = _to_int(ledger["reserved_gold"])
    xp_after, level_after = spend_xp_for_levels(
        connection,
        level_before=level_before,
        xp_available=xp_before + xp_gain,
    )
    stats = _player_stats(player)
    stat_gains: list[dict[str, Any]] = []
    max_stat = _max_stat(connection)
    for _ in range(max(0, level_after - level_before)):
        stat_name = _stat_to_raise(stats)
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
            _json_dumps(stats),
            now,
            target_player_id,
        ),
    )

    granted_assets = []
    for asset in _json_loads(ledger["reserved_assets_json"], []):
        try:
            granted_assets.append(
                grant_asset_ownership(
                    connection,
                    owner_player_id=target_player_id,
                    asset_type=str(asset["asset_type"]),
                    asset_id=str(asset["asset_id"]),
                    quantity=_to_int(asset.get("quantity")) or 1,
                    source="order_escrow_awarded",
                    source_ref_id=order_id,
                    now=_parse_iso(now),
                )
            )
        except AssetContractError as exc:
            raise LordRuntimeError(exc.code, str(exc), exc.status_code) from exc

    return {
        "reward_id": ledger["reward_id"],
        "xp_gain": xp_gain,
        "gold_gain": gold_gain,
        "xp_before": xp_before,
        "xp_after": xp_after,
        "level_before": level_before,
        "level_after": level_after,
        "stat_gains": stat_gains,
        "granted_assets": granted_assets,
    }


def _status_placeholders(statuses: set[str]) -> str:
    return ", ".join("?" for _ in statuses)


def _order_statuses_locking_objects(connection: sqlite3.Connection) -> set[str]:
    return _order_statuses_with_flag(connection, "locks_object")


def _order_statuses_counting_against_cap(connection: sqlite3.Connection) -> set[str]:
    return _order_statuses_with_flag(connection, "counts_against_cap") | set(ACTIVE_ORDER_STATUSES)


def _order_statuses_with_flag(connection: sqlite3.Connection, flag_column: str) -> set[str]:
    if not _table_exists(connection, "order_status_rules"):
        return set(ACTIVE_ORDER_STATUSES)
    try:
        rows = connection.execute(
            f"""
            SELECT status_id
            FROM order_status_rules
            WHERE lower(COALESCE({flag_column}, 'false')) = 'true'
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return set(ACTIVE_ORDER_STATUSES)
    return {str(row["status_id"]) for row in rows}


def _normalize_visibility(value: str) -> str:
    visibility = value.strip().lower()
    if visibility not in {"public", "addressed"}:
        raise LordRuntimeError("invalid_visibility", "Order visibility must be public or addressed.")
    return visibility


def _ensure_recruit_reserves_for_owned_buildings(
    connection: sqlite3.Connection, domain_id: str, now: str
) -> list[dict[str, Any]]:
    spawned: list[dict[str, Any]] = []
    for row in connection.execute(
        """
        SELECT db.building_id, b.recruit_unlock_ids
        FROM domain_buildings db
        JOIN buildings b ON b.building_id = db.building_id
        WHERE db.domain_id = ?
        ORDER BY db.purchased_at, db.building_id
        """,
        (domain_id,),
    ).fetchall():
        building_id = str(row["building_id"])
        for card_id in split_ids(str(row["recruit_unlock_ids"])):
            reserve = _ensure_building_recruit_reserve(
                connection, domain_id, building_id, card_id, now
            )
            if reserve is not None:
                spawned.append(reserve)
    return spawned


def apply_recruit_growth_tick(
    connection: sqlite3.Connection,
    *,
    now: str,
) -> list[dict[str, Any]]:
    """Apply one game-tick worth of recruit growth for visible recruit offers."""

    candidates: dict[tuple[str, str], set[str]] = {}
    if _table_exists(connection, "recruit_offer_runtime"):
        for row in connection.execute(
            """
            SELECT domain_id, card_id, status
            FROM recruit_offer_runtime
            WHERE status IN ('available', 'held')
            ORDER BY domain_id, card_id
            """
        ).fetchall():
            candidates.setdefault(
                (str(row["domain_id"]), str(row["card_id"])),
                set(),
            ).add(f"offer:{row['status']}")

    if _table_exists(connection, "domain_buildings"):
        for row in connection.execute(
            """
            SELECT db.domain_id, db.building_id, b.recruit_unlock_ids
            FROM domain_buildings db
            JOIN buildings b ON b.building_id = db.building_id
            ORDER BY db.domain_id, db.purchased_at, db.building_id
            """
        ).fetchall():
            domain_id = str(row["domain_id"])
            building_id = str(row["building_id"])
            for card_id in split_ids(str(row["recruit_unlock_ids"])):
                candidates.setdefault((domain_id, card_id), set()).add(
                    f"building:{building_id}"
                )

    if _table_exists(connection, "domain_runtime_state"):
        for row in connection.execute(
            "SELECT domain_id FROM domain_runtime_state ORDER BY domain_id"
        ).fetchall():
            domain_id = str(row["domain_id"])
            for card_id in controlled_domain_recruit_card_ids(connection, domain_id):
                candidates.setdefault((domain_id, card_id), set()).add(
                    "territory_bonus:recruit_card_unlock"
                )

    updates: list[dict[str, Any]] = []
    for (domain_id, card_id), sources in sorted(candidates.items()):
        card = _unit_card(connection, card_id)
        unit_class = str(card["unit_class"])
        growth = recruit_growth_per_hour_for_unit_class(unit_class)
        if growth <= 0:
            continue
        reserve = connection.execute(
            """
            SELECT *
            FROM army_reserve_runtime
            WHERE domain_id = ? AND card_id = ?
            ORDER BY reserve_id
            LIMIT 1
            """,
            (domain_id, card_id),
        ).fetchone()
        if reserve is None:
            reserve_id = _stable_id("reserve", domain_id, card_id, "tick")
            cap = _recruit_stock_cap_for_domain(connection, domain_id, unit_class, growth)
            next_count = min(cap, growth)
            connection.execute(
                """
                INSERT INTO army_reserve_runtime (
                    reserve_id, domain_id, card_id, count, status, updated_at
                )
                VALUES (?, ?, ?, ?, 'available', ?)
                """,
                (reserve_id, domain_id, card_id, next_count, now),
            )
            updates.append(
                {
                    "domain_id": domain_id,
                    "card_id": card_id,
                    "reserve_id": reserve_id,
                    "before": 0,
                    "after": next_count,
                    "growth": next_count,
                    "cap": cap,
                    "sources": sorted(sources),
                }
            )
            continue

        current_count = _to_int(reserve["count"])
        cap = _recruit_stock_cap_for_domain(
            connection,
            domain_id,
            unit_class,
            current_count + growth,
        )
        next_count = min(cap, current_count + growth)
        connection.execute(
            """
            UPDATE army_reserve_runtime
            SET count = ?,
                status = 'available',
                updated_at = ?
            WHERE reserve_id = ?
            """,
            (next_count, now, reserve["reserve_id"]),
        )
        updates.append(
            {
                "domain_id": domain_id,
                "card_id": card_id,
                "reserve_id": reserve["reserve_id"],
                "before": current_count,
                "after": next_count,
                "growth": max(0, next_count - current_count),
                "cap": cap,
                "sources": sorted(sources),
            }
        )
    return updates


def _ensure_building_recruit_reserve(
    connection: sqlite3.Connection,
    domain_id: str,
    building_id: str,
    card_id: str,
    now: str,
    *,
    seed_existing_to_initial: bool = False,
) -> dict[str, Any] | None:
    card = _unit_card(connection, card_id)
    if _optional(card["source_id"]) != building_id:
        return None
    existing_reserve = connection.execute(
        """
        SELECT *
        FROM army_reserve_runtime
        WHERE domain_id = ? AND card_id = ?
        LIMIT 1
        """,
        (domain_id, card_id),
    ).fetchone()
    if existing_reserve is not None:
        initial_count = _building_recruit_reserve_count(card)
        if seed_existing_to_initial and _to_int(existing_reserve["count"]) < initial_count:
            connection.execute(
                """
                UPDATE army_reserve_runtime
                SET count = ?,
                    status = 'available',
                    updated_at = ?
                WHERE reserve_id = ?
                """,
                (initial_count, now, existing_reserve["reserve_id"]),
            )
            return dict(
                connection.execute(
                    "SELECT * FROM army_reserve_runtime WHERE reserve_id = ?",
                    (existing_reserve["reserve_id"],),
                ).fetchone()
            )
        return _grow_building_recruit_reserve(connection, existing_reserve, card, now)

    reserve_id = _stable_id("reserve", domain_id, card_id, "building", building_id)
    count = _building_recruit_reserve_count(card)
    cursor = connection.execute(
        """
        INSERT INTO army_reserve_runtime (
            reserve_id, domain_id, card_id, count, status, updated_at
        )
        VALUES (?, ?, ?, ?, 'available', ?)
        ON CONFLICT(reserve_id) DO NOTHING
        """,
        (reserve_id, domain_id, card_id, count, now),
    )
    if cursor.rowcount < 1:
        return None
    return dict(
        connection.execute(
            "SELECT * FROM army_reserve_runtime WHERE reserve_id = ?",
            (reserve_id,),
        ).fetchone()
    )


def _building_recruit_reserve_count(card: sqlite3.Row) -> int:
    unit_class = str(card["unit_class"])
    return BUILDING_RECRUIT_INITIAL_STOCK_BY_CLASS.get(unit_class, 1)


def recruit_growth_per_hour_for_unit_class(unit_class: str) -> int:
    return BUILDING_RECRUIT_GROWTH_PER_HOUR_BY_CLASS.get(unit_class, 0)


def _grow_building_recruit_reserve(
    connection: sqlite3.Connection,
    reserve: sqlite3.Row,
    card: sqlite3.Row,
    now: str,
) -> dict[str, Any] | None:
    unit_class = str(card["unit_class"])
    rate = BUILDING_RECRUIT_GROWTH_PER_HOUR_BY_CLASS.get(unit_class, 0)
    if rate <= 0:
        return None
    current_count = _to_int(reserve["count"])
    cap = _recruit_stock_cap_for_domain(
        connection,
        str(reserve["domain_id"]),
        unit_class,
        current_count + rate,
    )
    if current_count > cap:
        connection.execute(
            """
            UPDATE army_reserve_runtime
            SET count = ?, updated_at = ?
            WHERE reserve_id = ?
            """,
            (cap, now, reserve["reserve_id"]),
        )
        return dict(
            connection.execute(
                "SELECT * FROM army_reserve_runtime WHERE reserve_id = ?",
                (reserve["reserve_id"],),
            ).fetchone()
        )
    try:
        last_updated = _parse_iso(str(reserve["updated_at"]))
        current_time = _parse_iso(now)
    except ValueError:
        last_updated = current_time = datetime.now(UTC)
    elapsed_hours = int((current_time - last_updated).total_seconds() // 3600)
    if elapsed_hours <= 0:
        return None
    next_count = min(cap, current_count + rate * elapsed_hours)
    if next_count <= current_count:
        connection.execute(
            """
            UPDATE army_reserve_runtime
            SET updated_at = ?
            WHERE reserve_id = ?
            """,
            (now, reserve["reserve_id"]),
        )
        return None
    connection.execute(
        """
        UPDATE army_reserve_runtime
        SET count = ?, updated_at = ?
        WHERE reserve_id = ?
        """,
        (next_count, now, reserve["reserve_id"]),
    )
    return dict(
        connection.execute(
            "SELECT * FROM army_reserve_runtime WHERE reserve_id = ?",
            (reserve["reserve_id"],),
        ).fetchone()
    )


def _ensure_recruit_offer(
    connection: sqlite3.Connection,
    domain_id: str,
    card_id: str,
    *,
    source: str,
    now: str,
) -> dict[str, Any]:
    card = _unit_card(connection, card_id)
    active_offer = connection.execute(
        """
        SELECT *
        FROM recruit_offer_runtime
        WHERE domain_id = ?
          AND card_id = ?
          AND status IN ('available', 'held')
        ORDER BY
          CASE WHEN status = 'held' THEN 0 ELSE 1 END,
          updated_at DESC,
          offer_id
        LIMIT 1
        """,
        (domain_id, card_id),
    ).fetchone()
    if active_offer is not None:
        payload = dict(active_offer)
        payload["unit_class"] = card["unit_class"]
        return payload

    generation = 1 + _to_int(
        connection.execute(
            """
            SELECT COUNT(*)
            FROM recruit_offer_runtime
            WHERE domain_id = ? AND card_id = ?
            """,
            (domain_id, card_id),
        ).fetchone()[0]
    )
    offer_id = _stable_id("offer", domain_id, card_id, source, str(generation))
    connection.execute(
        """
        INSERT INTO recruit_offer_runtime (
            offer_id, domain_id, card_id, cost, status, source, updated_at
        )
        VALUES (?, ?, ?, ?, 'available', ?, ?)
        ON CONFLICT(offer_id) DO NOTHING
        """,
        (offer_id, domain_id, card_id, _to_int(card["cost"]), source, now),
    )
    row = connection.execute(
        "SELECT * FROM recruit_offer_runtime WHERE offer_id = ?",
        (offer_id,),
    ).fetchone()
    payload = dict(row)
    payload["unit_class"] = card["unit_class"]
    return payload


def _retire_locked_recruit_offers(
    connection: sqlite3.Connection, domain_id: str, unlocked_cards: list[str], now: str
) -> None:
    placeholders = ", ".join("?" for _ in unlocked_cards)
    exclusion = f"AND card_id NOT IN ({placeholders})" if unlocked_cards else ""
    connection.execute(
        f"""
        UPDATE recruit_offer_runtime
        SET status = 'locked_requires_building',
            held_by_domain_id = NULL,
            updated_at = ?
        WHERE domain_id = ?
          AND source != 'seed'
          AND status IN ('available', 'held')
          {exclusion}
        """,
        (now, domain_id, *unlocked_cards),
    )


def _unlocked_recruit_cards(connection: sqlite3.Connection, domain_id: str) -> list[str]:
    cards: set[str] = set()
    for row in connection.execute(
        """
        SELECT b.recruit_unlock_ids
        FROM domain_buildings db
        JOIN buildings b ON b.building_id = db.building_id
        WHERE db.domain_id = ?
        """,
        (domain_id,),
    ).fetchall():
        cards.update(split_ids(str(row["recruit_unlock_ids"])))
    for row in connection.execute(
        """
        SELECT card_id
        FROM recruit_offer_runtime
        WHERE domain_id = ?
          AND source = 'seed'
          AND status != 'locked_requires_building'
        """,
        (domain_id,),
    ).fetchall():
        cards.add(str(row["card_id"]))
    for row in connection.execute(
        """
        SELECT t.territory_id
        FROM territory_runtime_state rt
        JOIN territories t ON t.territory_id = rt.territory_id
        WHERE rt.owner_domain_id = ? AND t.bonus_type = 'recruit'
        """,
        (domain_id,),
    ).fetchall():
        cards.add("unit_specialist_t3")
    cards.update(controlled_domain_recruit_card_ids(connection, domain_id))
    return sorted(cards)


def _unit_card(connection: sqlite3.Connection, card_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM army_unit_cards WHERE card_id = ?",
        (card_id,),
    ).fetchone()
    if row is None:
        raise LordRuntimeError("unit_card_not_found", f"Army unit card {card_id} is not available.")
    return row


def _upsert_reserve(
    connection: sqlite3.Connection, domain_id: str, card_id: str, count: int, now: str
) -> dict[str, Any]:
    reserve_id = _stable_id("reserve", domain_id, card_id)
    connection.execute(
        """
        INSERT INTO army_reserve_runtime (
            reserve_id, domain_id, card_id, count, status, updated_at
        )
        VALUES (?, ?, ?, ?, 'available', ?)
        ON CONFLICT(reserve_id) DO UPDATE SET
            count = army_reserve_runtime.count + excluded.count,
            status = 'available',
            updated_at = excluded.updated_at
        """,
        (reserve_id, domain_id, card_id, count, now),
    )
    return dict(
        connection.execute(
            "SELECT * FROM army_reserve_runtime WHERE reserve_id = ?",
            (reserve_id,),
        ).fetchone()
    )


def _consume_reserve(
    connection: sqlite3.Connection, domain_id: str, card_id: str, count: int
) -> None:
    rows = connection.execute(
        """
        SELECT reserve_id, count
        FROM army_reserve_runtime
        WHERE domain_id = ? AND card_id = ? AND status = 'available'
          AND count > 0
        ORDER BY reserve_id
        """,
        (domain_id, card_id),
    ).fetchall()
    if sum(_to_int(row["count"]) for row in rows) < count:
        raise LordRuntimeError("insufficient_reserve", "Not enough reserve units.")

    remaining_to_consume = count
    now = _iso()
    for row in rows:
        if remaining_to_consume <= 0:
            break
        row_count = _to_int(row["count"])
        consumed = min(row_count, remaining_to_consume)
        remaining = row_count - consumed
        connection.execute(
            """
            UPDATE army_reserve_runtime
            SET count = ?,
                status = ?,
                updated_at = ?
            WHERE reserve_id = ?
            """,
            (
                remaining,
                "available" if remaining > 0 else "empty",
                now,
                row["reserve_id"],
            ),
        )
        remaining_to_consume -= consumed


def _available_reserve_count(
    connection: sqlite3.Connection, domain_id: str, card_id: str
) -> int:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(count), 0) AS count
        FROM army_reserve_runtime
        WHERE domain_id = ?
          AND card_id = ?
          AND status = 'available'
          AND count > 0
        """,
        (domain_id, card_id),
    ).fetchone()
    return _to_int(row["count"] if row is not None else 0)


def _split_active_army_stack(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    territory_id: str,
    army_id: str,
    count: int,
    source: str,
) -> dict[str, Any]:
    now = _iso()
    domain = _domain_by_id(connection, domain_id)
    source_stack = _active_army_stack_at_territory(
        connection, domain_id, territory_id, army_id
    )
    source_count = _to_int(source_stack["count"])
    if source_count <= 1:
        raise LordRuntimeError(
            "stack_cannot_split",
            "Stack must contain more than one unit to split.",
        )
    if count <= 0 or count >= source_count:
        raise LordRuntimeError(
            "invalid_split_count",
            "Split count must leave units in both stacks.",
        )
    _assert_active_army_new_stack_capacity_available(
        connection, domain_id, _to_int(domain["active_army_capacity"])
    )
    remaining = source_count - count
    connection.execute(
        """
        UPDATE active_army_runtime
        SET count = ?, updated_at = ?
        WHERE army_id = ?
        """,
        (remaining, now, army_id),
    )
    new_stack = _insert_active_army_stack(
        connection,
        domain_id=domain_id,
        territory_id=territory_id,
        card_id=str(source_stack["card_id"]),
        count=count,
        now=now,
    )
    result = {
        "status": "active_stack_split",
        "domain_id": domain_id,
        "territory_id": territory_id,
        "source_stack_id": army_id,
        "source_remaining": remaining,
        "target_stack": new_stack,
        "card_id": source_stack["card_id"],
        "count": count,
    }
    log_event(connection, "lord_active_stack_split", result, source=source)
    return result


def _split_garrison_stack(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    territory_id: str,
    garrison_id: str,
    count: int,
    source: str,
) -> dict[str, Any]:
    now = _iso()
    territory = _territory_state(connection, territory_id)
    if _optional(territory["owner_domain_id"]) != domain_id:
        raise LordRuntimeError(
            "territory_not_owned",
            "Garrison split requires a territory controlled by the lord domain.",
        )
    if (
        str(territory["status"]) in LOCKED_GARRISON_TRANSFER_STATUSES
        or _optional(territory["contested_by_domain_id"]) is not None
    ):
        raise LordRuntimeError(
            "territory_contested",
            "Contested territory cannot split garrison stacks.",
        )
    source_stack = _garrison_stack(connection, domain_id, territory_id, garrison_id)
    source_count = _to_int(source_stack["count"])
    if source_count <= 1:
        raise LordRuntimeError(
            "stack_cannot_split",
            "Stack must contain more than one unit to split.",
        )
    if count <= 0 or count >= source_count:
        raise LordRuntimeError(
            "invalid_split_count",
            "Split count must leave units in both stacks.",
        )
    _assert_fort_new_stack_capacity_available(connection, territory_id)
    remaining = source_count - count
    connection.execute(
        """
        UPDATE garrison_runtime_state
        SET count = ?, updated_at = ?
        WHERE garrison_id = ?
        """,
        (remaining, now, garrison_id),
    )
    new_stack = _insert_garrison_stack(
        connection,
        territory_id,
        domain_id,
        str(source_stack["card_id"]),
        count,
        now,
    )
    result = {
        "status": "garrison_stack_split",
        "domain_id": domain_id,
        "territory_id": territory_id,
        "source_stack_id": garrison_id,
        "source_remaining": remaining,
        "target_stack": new_stack,
        "card_id": source_stack["card_id"],
        "count": count,
    }
    log_event(connection, "lord_garrison_stack_split", result, source=source)
    return result


def _merge_active_army_stacks(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    territory_id: str,
    source_army_id: str,
    target_army_id: str,
    source: str,
) -> dict[str, Any]:
    if source_army_id == target_army_id:
        raise LordRuntimeError(
            "merge_same_stack",
            "Source and target stacks must be different.",
        )
    now = _iso()
    source_stack = _active_army_stack_at_territory(
        connection, domain_id, territory_id, source_army_id
    )
    target_stack = _active_army_stack_at_territory(
        connection, domain_id, territory_id, target_army_id
    )
    if source_stack["card_id"] != target_stack["card_id"]:
        raise LordRuntimeError(
            "merge_unit_mismatch",
            "Only stacks with the same unit card can be merged.",
        )
    merged_count = _to_int(source_stack["count"]) + _to_int(target_stack["count"])
    connection.execute(
        """
        UPDATE active_army_runtime
        SET count = ?, status = 'active', updated_at = ?
        WHERE army_id = ?
        """,
        (merged_count, now, target_army_id),
    )
    connection.execute(
        """
        UPDATE active_army_runtime
        SET count = 0, status = 'empty', updated_at = ?
        WHERE army_id = ?
        """,
        (now, source_army_id),
    )
    target = dict(
        connection.execute(
            "SELECT * FROM active_army_runtime WHERE army_id = ?",
            (target_army_id,),
        ).fetchone()
    )
    result = {
        "status": "active_stack_merged",
        "domain_id": domain_id,
        "territory_id": territory_id,
        "source_stack_id": source_army_id,
        "target_stack_id": target_army_id,
        "target_stack": target,
        "card_id": target_stack["card_id"],
        "count": merged_count,
    }
    log_event(connection, "lord_active_stack_merged", result, source=source)
    return result


def _merge_garrison_stacks(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    territory_id: str,
    source_garrison_id: str,
    target_garrison_id: str,
    source: str,
) -> dict[str, Any]:
    if source_garrison_id == target_garrison_id:
        raise LordRuntimeError(
            "merge_same_stack",
            "Source and target stacks must be different.",
        )
    now = _iso()
    territory = _territory_state(connection, territory_id)
    if _optional(territory["owner_domain_id"]) != domain_id:
        raise LordRuntimeError(
            "territory_not_owned",
            "Garrison merge requires a territory controlled by the lord domain.",
        )
    if (
        str(territory["status"]) in LOCKED_GARRISON_TRANSFER_STATUSES
        or _optional(territory["contested_by_domain_id"]) is not None
    ):
        raise LordRuntimeError(
            "territory_contested",
            "Contested territory cannot merge garrison stacks.",
        )
    source_stack = _garrison_stack(
        connection, domain_id, territory_id, source_garrison_id
    )
    target_stack = _garrison_stack(
        connection, domain_id, territory_id, target_garrison_id
    )
    if source_stack["card_id"] != target_stack["card_id"]:
        raise LordRuntimeError(
            "merge_unit_mismatch",
            "Only stacks with the same unit card can be merged.",
        )
    merged_count = _to_int(source_stack["count"]) + _to_int(target_stack["count"])
    connection.execute(
        """
        UPDATE garrison_runtime_state
        SET count = ?, status = 'active', updated_at = ?
        WHERE garrison_id = ?
        """,
        (merged_count, now, target_garrison_id),
    )
    connection.execute(
        """
        UPDATE garrison_runtime_state
        SET count = 0, status = 'empty', updated_at = ?
        WHERE garrison_id = ?
        """,
        (now, source_garrison_id),
    )
    target = dict(
        connection.execute(
            "SELECT * FROM garrison_runtime_state WHERE garrison_id = ?",
            (target_garrison_id,),
        ).fetchone()
    )
    result = {
        "status": "garrison_stack_merged",
        "domain_id": domain_id,
        "territory_id": territory_id,
        "source_stack_id": source_garrison_id,
        "target_stack_id": target_garrison_id,
        "target_stack": target,
        "card_id": target_stack["card_id"],
        "count": merged_count,
    }
    log_event(connection, "lord_garrison_stack_merged", result, source=source)
    return result


def _transfer_garrison_stack_to_active_army_stack(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    territory_id: str,
    source_garrison_id: str,
    target_army_id: str,
    count: int,
    now: str,
) -> tuple[str, dict[str, Any]]:
    source_stack = _garrison_stack(
        connection, domain_id, territory_id, source_garrison_id
    )
    target_stack = _active_army_stack_at_territory(
        connection, domain_id, territory_id, target_army_id
    )
    if source_stack["card_id"] != target_stack["card_id"]:
        raise LordRuntimeError(
            "merge_unit_mismatch",
            "Only stacks with the same unit card can be merged.",
        )
    _consume_garrison_stack(
        connection,
        domain_id,
        territory_id,
        source_garrison_id,
        count,
        now,
    )
    target_count = _to_int(target_stack["count"]) + count
    connection.execute(
        """
        UPDATE active_army_runtime
        SET count = ?, status = 'active', updated_at = ?
        WHERE army_id = ?
        """,
        (target_count, now, target_army_id),
    )
    target = dict(
        connection.execute(
            "SELECT * FROM active_army_runtime WHERE army_id = ?",
            (target_army_id,),
        ).fetchone()
    )
    return str(source_stack["card_id"]), target


def _transfer_active_army_stack_to_garrison_stack(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    territory_id: str,
    source_army_id: str,
    target_garrison_id: str,
    count: int,
    now: str,
) -> tuple[str, dict[str, Any]]:
    source_stack = _active_army_stack_at_territory(
        connection, domain_id, territory_id, source_army_id
    )
    target_stack = _garrison_stack(
        connection, domain_id, territory_id, target_garrison_id
    )
    if source_stack["card_id"] != target_stack["card_id"]:
        raise LordRuntimeError(
            "merge_unit_mismatch",
            "Only stacks with the same unit card can be merged.",
        )
    _consume_active_army_stack_at_territory(
        connection,
        domain_id,
        territory_id,
        source_army_id,
        count,
        now,
    )
    target_count = _to_int(target_stack["count"]) + count
    connection.execute(
        """
        UPDATE garrison_runtime_state
        SET count = ?, status = 'active', updated_at = ?
        WHERE garrison_id = ?
        """,
        (target_count, now, target_garrison_id),
    )
    target = dict(
        connection.execute(
            "SELECT * FROM garrison_runtime_state WHERE garrison_id = ?",
            (target_garrison_id,),
        ).fetchone()
    )
    return str(source_stack["card_id"]), target


def _active_army_stack_at_territory(
    connection: sqlite3.Connection,
    domain_id: str,
    territory_id: str,
    army_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT army.army_id, army.domain_id, army.card_id, army.count, army.location_node_id
        FROM active_army_runtime army
        JOIN map_nodes node ON node.node_id = army.location_node_id
        WHERE army.army_id = ?
          AND army.domain_id = ?
          AND army.status = 'active'
          AND army.count > 0
          AND node.territory_id = ?
        LIMIT 1
        """,
        (army_id, domain_id, territory_id),
    ).fetchone()
    if row is None:
        raise LordRuntimeError(
            "active_stack_not_found",
            "Active army stack is not available at this territory.",
        )
    return row


def _garrison_stack(
    connection: sqlite3.Connection,
    domain_id: str,
    territory_id: str,
    garrison_id: str,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT garrison_id, territory_id, domain_id, card_id, count
        FROM garrison_runtime_state
        WHERE garrison_id = ?
          AND domain_id = ?
          AND territory_id = ?
          AND status = 'active'
          AND count > 0
        LIMIT 1
        """,
        (garrison_id, domain_id, territory_id),
    ).fetchone()
    if row is None:
        raise LordRuntimeError(
            "garrison_stack_not_found",
            "Garrison stack is not available at this territory.",
        )
    return row


def _consume_active_army_stack_at_territory(
    connection: sqlite3.Connection,
    domain_id: str,
    territory_id: str,
    army_id: str,
    count: int,
    now: str,
) -> sqlite3.Row:
    row = _active_army_stack_at_territory(connection, domain_id, territory_id, army_id)
    if _to_int(row["count"]) < count:
        raise LordRuntimeError(
            "missing_active_army",
            "A matching active army unit at the territory is required.",
        )
    remaining = _to_int(row["count"]) - count
    connection.execute(
        """
        UPDATE active_army_runtime
        SET count = ?,
            status = ?,
            updated_at = ?
        WHERE army_id = ?
        """,
        (remaining, "active" if remaining > 0 else "empty", now, army_id),
    )
    return row


def _consume_garrison_stack(
    connection: sqlite3.Connection,
    domain_id: str,
    territory_id: str,
    garrison_id: str,
    count: int,
    now: str,
) -> sqlite3.Row:
    row = _garrison_stack(connection, domain_id, territory_id, garrison_id)
    if _to_int(row["count"]) < count:
        raise LordRuntimeError("insufficient_garrison", "Not enough fort garrison units.")
    remaining = _to_int(row["count"]) - count
    connection.execute(
        """
        UPDATE garrison_runtime_state
        SET count = ?,
            status = ?,
            updated_at = ?
        WHERE garrison_id = ?
        """,
        (remaining, "active" if remaining > 0 else "empty", now, garrison_id),
    )
    return row


def _consume_active_army_at_territory(
    connection: sqlite3.Connection,
    domain_id: str,
    territory_id: str,
    card_id: str,
    count: int,
    now: str,
) -> None:
    row = connection.execute(
        """
        SELECT army.army_id, army.count
        FROM active_army_runtime army
        JOIN map_nodes node ON node.node_id = army.location_node_id
        WHERE army.domain_id = ?
          AND army.card_id = ?
          AND army.status = 'active'
          AND army.count > 0
          AND node.territory_id = ?
        ORDER BY army.army_id
        LIMIT 1
        """,
        (domain_id, card_id, territory_id),
    ).fetchone()
    if row is None or _to_int(row["count"]) < count:
        raise LordRuntimeError(
            "missing_active_army",
            "A matching active army unit at the territory is required.",
        )
    remaining = _to_int(row["count"]) - count
    connection.execute(
        """
        UPDATE active_army_runtime
        SET count = ?,
            status = ?,
            updated_at = ?
        WHERE army_id = ?
        """,
        (remaining, "active" if remaining > 0 else "empty", now, row["army_id"]),
    )


def _assert_fort_capacity_available(
    connection: sqlite3.Connection, territory_id: str, card_id: str
) -> None:
    if not _table_exists(connection, "territory_forts"):
        return
    fort = connection.execute(
        """
        SELECT garrison_capacity
        FROM territory_forts
        WHERE territory_id = ?
        LIMIT 1
        """,
        (territory_id,),
    ).fetchone()
    if fort is None:
        return
    existing_stack = connection.execute(
        """
        SELECT 1
        FROM garrison_runtime_state
        WHERE territory_id = ?
          AND card_id = ?
          AND status = 'active'
          AND count > 0
        LIMIT 1
        """,
        (territory_id, card_id),
    ).fetchone()
    if existing_stack is not None:
        return
    current = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM garrison_runtime_state
        WHERE territory_id = ? AND status = 'active' AND count > 0
        """,
        (territory_id,),
    ).fetchone()["count"]
    capacity = _to_int(fort["garrison_capacity"])
    if _to_int(current) + 1 > capacity:
        raise LordRuntimeError(
            "fort_capacity_exceeded",
            f"Fort garrison stack capacity is {capacity}.",
        )


def _assert_fort_new_stack_capacity_available(
    connection: sqlite3.Connection, territory_id: str
) -> None:
    if not _table_exists(connection, "territory_forts"):
        return
    fort = connection.execute(
        """
        SELECT garrison_capacity
        FROM territory_forts
        WHERE territory_id = ?
        LIMIT 1
        """,
        (territory_id,),
    ).fetchone()
    if fort is None:
        return
    current = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM garrison_runtime_state
        WHERE territory_id = ? AND status = 'active' AND count > 0
        """,
        (territory_id,),
    ).fetchone()["count"]
    capacity = _to_int(fort["garrison_capacity"])
    if _to_int(current) + 1 > capacity:
        raise LordRuntimeError(
            "fort_capacity_exceeded",
            f"Fort garrison stack capacity is {capacity}.",
        )


def _consume_garrison(
    connection: sqlite3.Connection,
    domain_id: str,
    territory_id: str,
    card_id: str,
    count: int,
    now: str,
) -> None:
    row = connection.execute(
        """
        SELECT garrison_id, count
        FROM garrison_runtime_state
        WHERE domain_id = ?
          AND territory_id = ?
          AND card_id = ?
          AND status = 'active'
          AND count > 0
        ORDER BY garrison_id
        LIMIT 1
        """,
        (domain_id, territory_id, card_id),
    ).fetchone()
    if row is None or _to_int(row["count"]) < count:
        raise LordRuntimeError("insufficient_garrison", "Not enough fort garrison units.")
    remaining = _to_int(row["count"]) - count
    connection.execute(
        """
        UPDATE garrison_runtime_state
        SET count = ?,
            status = ?,
            updated_at = ?
        WHERE garrison_id = ?
        """,
        (remaining, "active" if remaining > 0 else "empty", now, row["garrison_id"]),
    )


def _upsert_active_army(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    territory_id: str,
    card_id: str,
    count: int,
    now: str,
) -> dict[str, Any]:
    army_id = _stable_id("army", domain_id, card_id)
    location_node_id = _node_for_territory(connection, territory_id)
    connection.execute(
        """
        INSERT INTO active_army_runtime (
            army_id, domain_id, card_id, count, location_node_id, status, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?)
        ON CONFLICT(army_id) DO UPDATE SET
            count = active_army_runtime.count + excluded.count,
            location_node_id = excluded.location_node_id,
            status = 'active',
            updated_at = excluded.updated_at
        """,
        (army_id, domain_id, card_id, count, location_node_id, now),
    )
    return dict(
        connection.execute(
            "SELECT * FROM active_army_runtime WHERE army_id = ?",
            (army_id,),
        ).fetchone()
    )


def _insert_active_army_stack(
    connection: sqlite3.Connection,
    *,
    domain_id: str,
    territory_id: str,
    card_id: str,
    count: int,
    now: str,
) -> dict[str, Any]:
    army_id = f"army_{uuid4().hex}"
    location_node_id = _node_for_territory(connection, territory_id)
    connection.execute(
        """
        INSERT INTO active_army_runtime (
            army_id, domain_id, card_id, count, location_node_id, status, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?)
        """,
        (army_id, domain_id, card_id, count, location_node_id, now),
    )
    return dict(
        connection.execute(
            "SELECT * FROM active_army_runtime WHERE army_id = ?",
            (army_id,),
        ).fetchone()
    )


def _upsert_garrison(
    connection: sqlite3.Connection,
    territory_id: str,
    domain_id: str,
    card_id: str,
    count: int,
    now: str,
) -> dict[str, Any]:
    garrison_id = _stable_id("garrison", territory_id, domain_id, card_id)
    connection.execute(
        """
        INSERT INTO garrison_runtime_state (
            garrison_id, territory_id, domain_id, card_id, count, status, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?)
        ON CONFLICT(garrison_id) DO UPDATE SET
            count = garrison_runtime_state.count + excluded.count,
            status = 'active',
            updated_at = excluded.updated_at
        """,
        (garrison_id, territory_id, domain_id, card_id, count, now),
    )
    return dict(
        connection.execute(
            "SELECT * FROM garrison_runtime_state WHERE garrison_id = ?",
            (garrison_id,),
        ).fetchone()
    )


def _insert_garrison_stack(
    connection: sqlite3.Connection,
    territory_id: str,
    domain_id: str,
    card_id: str,
    count: int,
    now: str,
) -> dict[str, Any]:
    garrison_id = f"garrison_{uuid4().hex}"
    connection.execute(
        """
        INSERT INTO garrison_runtime_state (
            garrison_id, territory_id, domain_id, card_id, count, status, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?)
        """,
        (garrison_id, territory_id, domain_id, card_id, count, now),
    )
    return dict(
        connection.execute(
            "SELECT * FROM garrison_runtime_state WHERE garrison_id = ?",
            (garrison_id,),
        ).fetchone()
    )


def _active_army_count(connection: sqlite3.Connection, domain_id: str) -> int:
    return int(
        connection.execute(
            """
            SELECT COUNT(*)
            FROM active_army_runtime
            WHERE domain_id = ? AND status = 'active' AND count > 0
            """,
            (domain_id,),
        ).fetchone()[0]
    )


def _assert_active_army_stack_capacity_available(
    connection: sqlite3.Connection,
    domain_id: str,
    card_id: str,
    capacity: int,
) -> None:
    existing_stack = connection.execute(
        """
        SELECT 1
        FROM active_army_runtime
        WHERE domain_id = ?
          AND card_id = ?
          AND status = 'active'
          AND count > 0
        LIMIT 1
        """,
        (domain_id, card_id),
    ).fetchone()
    if existing_stack is not None:
        return
    if _active_army_count(connection, domain_id) + 1 > capacity:
        raise LordRuntimeError(
            "army_capacity_exceeded",
            f"Active army stack capacity is {capacity}.",
        )


def _assert_active_army_new_stack_capacity_available(
    connection: sqlite3.Connection,
    domain_id: str,
    capacity: int,
) -> None:
    if _active_army_count(connection, domain_id) + 1 > capacity:
        raise LordRuntimeError(
            "army_capacity_exceeded",
            f"Active army stack capacity is {capacity}.",
        )


def _ensure_minimum_active_army_stack_capacity(
    connection: sqlite3.Connection, now: str
) -> None:
    if not _table_exists(connection, "domain_runtime_state"):
        return
    connection.execute(
        """
        UPDATE domain_runtime_state
        SET active_army_capacity = ?,
            updated_at = ?
        WHERE active_army_capacity < ?
        """,
        (
            DEFAULT_ACTIVE_ARMY_STACK_CAPACITY,
            now,
            DEFAULT_ACTIVE_ARMY_STACK_CAPACITY,
        ),
    )


def _army_power_by_domain(connection: sqlite3.Connection) -> dict[str, int]:
    if not _table_exists(connection, "army_unit_cards"):
        return {}
    powers: dict[str, int] = {}
    sources = [
        ("army_reserve_runtime", "domain_id"),
        ("active_army_runtime", "domain_id"),
        ("garrison_runtime_state", "domain_id"),
    ]
    for table_name, domain_column in sources:
        if not _table_exists(connection, table_name):
            continue
        for row in connection.execute(
            f"""
            SELECT r.{domain_column} AS domain_id, r.count, c.attack, c.defense, c.hp, c.tier, c.unit_class
            FROM {table_name} r
            JOIN army_unit_cards c ON c.card_id = r.card_id
            WHERE r.status IN ('available', 'active') AND r.count > 0
            """
        ).fetchall():
            unit_power = (
                _to_int(row["attack"])
                + _to_int(row["defense"])
                + _to_int(row["hp"])
                + _to_int(row["tier"])
                + ARMY_UNIT_CLASS_POWER_BONUS.get(str(row["unit_class"]), 0)
            )
            powers[str(row["domain_id"])] = powers.get(str(row["domain_id"]), 0) + unit_power * _to_int(row["count"])
    for row in connection.execute("SELECT domain_id FROM domain_runtime_state").fetchall():
        powers.setdefault(str(row["domain_id"]), 0)
    return powers


def _active_order_counts(connection: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    count_statuses = _order_statuses_counting_against_cap(connection)
    if not count_statuses:
        for row in connection.execute("SELECT domain_id FROM domain_runtime_state").fetchall():
            counts[str(row["domain_id"])] = 0
        return counts
    for row in connection.execute(
        f"""
        SELECT d.domain_id, COUNT(o.order_id) AS count
        FROM domain_runtime_state d
        LEFT JOIN order_runtime_state o
          ON o.lord_id = d.lord_player_id
         AND o.status IN ({_status_placeholders(count_statuses)})
        GROUP BY d.domain_id
        """,
        tuple(sorted(count_statuses)),
    ).fetchall():
        counts[str(row["domain_id"])] = _to_int(row["count"])
    return counts


def _order_pressure_bucket(count: int) -> str:
    if count <= 0:
        return "none"
    if count == 1:
        return "low"
    if count == 2:
        return "medium"
    return "high"


def _contested_counts(connection: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in connection.execute(
        """
        SELECT claimant_domain_id, COUNT(*) AS count
        FROM territory_claim_runtime
        WHERE status IN ('in_battle', 'contested', 'contested_pending_tick')
        GROUP BY claimant_domain_id
        """
    ).fetchall():
        counts[str(row["claimant_domain_id"])] = _to_int(row["count"])
    return counts


def _active_raid_counts(connection: sqlite3.Connection) -> dict[str, int]:
    if not _table_exists(connection, "raid_effects"):
        return {}
    counts: dict[str, int] = {}
    for row in connection.execute(
        """
        SELECT source_domain_id, COUNT(*) AS count
        FROM raid_effects
        WHERE status = 'active'
        GROUP BY source_domain_id
        """
    ).fetchall():
        counts[str(row["source_domain_id"])] = _to_int(row["count"])
    return counts


def _raid_resistance_result(
    connection: sqlite3.Connection,
    *,
    target_territory_id: str,
    owner_domain_id: str,
    target_type: str,
    rule: sqlite3.Row,
) -> dict[str, Any]:
    raid_strength = max(1, _to_int(_raid_rule_value(rule, "tier", "1")))
    score = _raid_defense_score(
        connection,
        target_territory_id=target_territory_id,
        owner_domain_id=owner_domain_id,
        target_type=target_type,
    )
    if score <= 0:
        outcome = "full"
        multiplier = 100
    elif score > raid_strength:
        outcome = "blocked"
        multiplier = 0
    else:
        outcome = "weakened"
        multiplier = 50
    return {
        "score": score,
        "raid_strength": raid_strength,
        "outcome": outcome,
        "effect_multiplier": multiplier,
    }


def _raid_defense_score(
    connection: sqlite3.Connection,
    *,
    target_territory_id: str,
    owner_domain_id: str,
    target_type: str,
) -> int:
    if target_type == "residence":
        score = RAID_RESIDENCE_BASE_DEFENSE
        if _has_building(connection, owner_domain_id, MAGE_STUDY_BUILDING_ID):
            score += MAGE_STUDY_RESIDENCE_DEFENSE_BONUS
        if _has_building(connection, owner_domain_id, "b_wards"):
            score += RAID_RESIDENCE_WARD_DEFENSE
        return score

    score = _raid_garrison_defense_points(
        _territory_garrison_power(connection, target_territory_id, owner_domain_id)
    )
    score += territory_numeric_bonus(
        connection,
        target_territory_id,
        "raid_defense_flat",
    )
    if _domain_current_territory(connection, owner_domain_id) == target_territory_id:
        score += 1
    if _has_building(connection, owner_domain_id, "b_wards"):
        score += RAID_TERRITORY_WARD_DEFENSE
    return score


def _raid_garrison_defense_points(garrison_power: int) -> int:
    if garrison_power >= RAID_GARRISON_POWER_HARD_THRESHOLD:
        return 3
    if garrison_power >= RAID_GARRISON_POWER_STRONG_THRESHOLD:
        return 2
    if garrison_power >= RAID_GARRISON_POWER_WEAK_THRESHOLD:
        return 1
    return 0


def _territory_garrison_power(
    connection: sqlite3.Connection, territory_id: str, owner_domain_id: str
) -> int:
    if not _table_exists(connection, "army_unit_cards"):
        return 0
    total = 0
    for row in connection.execute(
        """
        SELECT g.count, c.attack, c.defense, c.hp, c.tier
        FROM garrison_runtime_state g
        JOIN army_unit_cards c ON c.card_id = g.card_id
        WHERE g.territory_id = ?
          AND g.domain_id = ?
          AND g.status = 'active'
          AND g.count > 0
        """,
        (territory_id, owner_domain_id),
    ).fetchall():
        total += (
            _to_int(row["attack"])
            + _to_int(row["defense"])
            + _to_int(row["hp"])
            + _to_int(row["tier"])
        ) * _to_int(row["count"])
    return total


def _territory_resistance(
    connection: sqlite3.Connection, territory_id: str, owner_domain_id: str
) -> int:
    return _raid_defense_score(
        connection,
        target_territory_id=territory_id,
        owner_domain_id=owner_domain_id,
        target_type="territory",
    )


def _raid_effect_duration(base_duration_min: int, resistance_outcome: str) -> int:
    if resistance_outcome == "blocked":
        return 0
    if resistance_outcome == "weakened" and base_duration_min > 1:
        return max(1, base_duration_min // 2)
    return base_duration_min


def _raid_loot_gold(
    connection: sqlite3.Connection,
    target_domain_id: str,
    target_territory_id: str,
    resistance_outcome: str,
) -> int:
    if resistance_outcome == "blocked":
        return 0
    loot_by_tier = {1: 6, 2: 12, 3: 18}
    base_loot = loot_by_tier.get(max(1, _territory_tier(connection, target_territory_id)), 6)
    if resistance_outcome == "weakened":
        base_loot = max(1, base_loot // 2)
    if _has_building(connection, target_domain_id, BANK_BUILDING_ID):
        base_loot = max(1, base_loot * (100 - BANK_LOOT_REDUCTION_PERCENT) // 100)
    target = _domain_by_id(connection, target_domain_id)
    return min(_to_int(target["gold"]), base_loot)


def _raid_residence_token_loss(
    connection: sqlite3.Connection, target_domain_id: str, resistance_outcome: str
) -> int:
    if resistance_outcome == "blocked":
        return 0
    target = _domain_by_id(connection, target_domain_id)
    return min(1, _to_int(target["raid_tokens"]))


def _territory_tier(connection: sqlite3.Connection, territory_id: str) -> int:
    row = connection.execute(
        "SELECT tier FROM territories WHERE territory_id = ?",
        (territory_id,),
    ).fetchone()
    return _to_int(row["tier"]) if row is not None else 1


def _residence_node(connection: sqlite3.Connection, domain_id: str) -> str | None:
    row = connection.execute(
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
    return _optional(row["node_id"]) if row else None


def _domain_current_territory(
    connection: sqlite3.Connection, domain_id: str
) -> str | None:
    if not _table_exists(connection, "map_nodes"):
        return None
    row = connection.execute(
        """
        SELECT n.territory_id
        FROM domain_runtime_state d
        JOIN map_nodes n ON n.node_id = d.current_node_id
        WHERE d.domain_id = ?
        LIMIT 1
        """,
        (domain_id,),
    ).fetchone()
    return _optional(row["territory_id"]) if row else None


def _rows(
    connection: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()
) -> list[sqlite3.Row]:
    return connection.execute(sql, params).fetchall()


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


def _clean_registration_start_enabled(connection: sqlite3.Connection) -> bool:
    if not _table_exists(connection, "runtime_flags"):
        return False
    row = connection.execute(
        """
        SELECT value_json
        FROM runtime_flags
        WHERE flag_id = ?
        """,
        (CLEAN_REGISTRATION_FLAG,),
    ).fetchone()
    if row is None:
        return False
    try:
        payload = json.loads(str(row["value_json"] or "{}"))
    except json.JSONDecodeError:
        return False
    return bool(payload.get("enabled"))


def _optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _to_int(value: object) -> int:
    if value is None or str(value) == "":
        return 0
    return int(value)


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _runtime_player(
    connection: sqlite3.Connection,
    player_id: str,
    *,
    now: str,
) -> dict[str, Any]:
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

    player = connection.execute(
        """
        SELECT player_id, role_type, level, xp, gold, stats_json
        FROM players
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if player is None:
        raise LordRuntimeError("unknown_player", f"Unknown player_id: {player_id}.", 404)
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
            now,
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


def _stat_to_raise(stats: dict[str, int]) -> str:
    for stat_name in CANONICAL_STATS:
        if stats.get(stat_name, 0) < 7:
            return stat_name
    for stat_name in sorted(stats):
        if stats[stat_name] < 7:
            return stat_name
    return sorted(stats)[0] if stats else DEFAULT_STAT_ID


def _final_lock_active(connection: sqlite3.Connection) -> bool:
    row = connection.execute("SELECT locked_at FROM final_lock_state WHERE id = 1").fetchone()
    return bool(row and row["locked_at"])


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


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")


def _required_card_id(card_id: str | None) -> str:
    if not card_id:
        raise LordRuntimeError("missing_card_id", "Card id is required for this operation.")
    return card_id


def _required_stack_id(stack_id: str | None) -> str:
    if not stack_id:
        raise LordRuntimeError("missing_stack_id", "Stack id is required for this operation.")
    return stack_id


def _stable_id(prefix: str, *parts: str) -> str:
    slug = "_".join(re.sub(r"[^A-Za-z0-9]+", "_", part).strip("_") for part in parts)
    return f"{prefix}_{slug}".lower()
