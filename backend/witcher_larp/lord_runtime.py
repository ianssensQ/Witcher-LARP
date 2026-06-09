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
from .content_schema import split_ids
from .runtime_schema import ensure_runtime_schema, log_event
from .stats import CANONICAL_STATS, DEFAULT_STAT_ID
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
BLOCKING_ROUTE_STATUSES = {
    "in_battle",
    "contested",
    "contested_pending_tick",
    "capture_pending_garrison",
    "awaiting_garrison",
}
LORD_MOVE_SECONDS_PER_EDGE = 1
DEFAULT_ACTIVE_ARMY_STACK_CAPACITY = 5

BUILDING_RECRUIT_INITIAL_STOCK_BY_CLASS = {
    "infantry": 24,
    "guard": 14,
    "ranged": 14,
    "cavalry": 5,
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
BUILDING_RECRUIT_STOCK_CAP_BY_CLASS = {
    "infantry": 240,
    "guard": 140,
    "ranged": 140,
    "cavalry": 50,
    "heavy_siege": 24,
    "specialist": 36,
}


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

    if _table_exists(connection, "garrisons"):
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

    if _table_exists(connection, "territory_claims"):
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

    if _table_exists(connection, "army_reserves"):
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

    if _table_exists(connection, "orders"):
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
    reconcile_pending_lord_moves(connection, domain_id=str(domain["domain_id"]))
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

    return {
        "status": "blocked" if reason_code in {"insufficient_mp", "missing_active_army"} else (
            "stopped" if stopped else "ready"
        ),
        "can_move": affordable and active_army_ready,
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
    card_id: str,
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

    if operation == "reserve_to_active":
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
            "Garrison operation must be reserve_to_active, active_to_fort or fort_to_active.",
        )

    domain_id = str(domain["domain_id"])
    territory = _territory_state(connection, territory_id)
    territory_owner = _optional(territory["owner_domain_id"])
    territory_status = str(territory["status"])
    capture_claim = None
    now = _iso()

    if operation == "fort_to_active":
        _assert_local_owned_transfer_territory(connection, domain_id, territory)
        capacity = _to_int(domain["active_army_capacity"])
        _assert_active_army_stack_capacity_available(
            connection, domain_id, card_id, capacity
        )
        _consume_garrison(connection, domain_id, territory_id, card_id, count, now)
        _upsert_active_army(
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

    _assert_fort_capacity_available(connection, territory_id, card_id)
    _consume_active_army_at_territory(connection, domain_id, territory_id, card_id, count, now)
    _upsert_garrison(connection, territory_id, domain_id, card_id, count, now)

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
    }
    log_event(connection, "lord_garrison_transferred", result, source=source)
    return result


def buy_building(
    connection: sqlite3.Connection,
    lord_id: str,
    *,
    building_id: str,
    source: str = "lord_panel",
) -> dict[str, Any]:
    ensure_lord_runtime_state(connection)
    domain = _domain_for_lord(connection, lord_id)
    building = _building(connection, building_id)
    if _has_building(connection, str(domain["domain_id"]), building_id):
        raise LordRuntimeError("building_already_owned", "Building is already owned.")

    missing = [
        prereq
        for prereq in split_ids(str(building["prerequisite_ids"]))
        if not _has_building(connection, str(domain["domain_id"]), prereq)
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
    raid_delta = 1 if _truthy(building["raid_unlock"]) else 0
    capacity_delta = _to_int(building["capacity_delta"])
    connection.execute(
        """
        UPDATE domain_runtime_state
        SET gold = gold - ?,
            active_army_capacity = active_army_capacity + ?,
            raid_tokens = raid_tokens + ?,
            updated_at = ?
        WHERE domain_id = ?
        """,
        (cost, capacity_delta, raid_delta, now, domain["domain_id"]),
    )
    connection.execute(
        """
        INSERT INTO domain_buildings (domain_id, building_id, purchased_at, source)
        VALUES (?, ?, ?, ?)
        """,
        (domain["domain_id"], building_id, now, source),
    )

    unlocked = []
    spawned_reserves = []
    for card_id in split_ids(str(building["recruit_unlock_ids"])):
        offer = _ensure_recruit_offer(
            connection,
            str(domain["domain_id"]),
            card_id,
            source=f"building:{building_id}",
            now=now,
        )
        unlocked.append(offer)
        reserve = _ensure_building_recruit_reserve(
            connection,
            str(domain["domain_id"]),
            building_id,
            card_id,
            now,
        )
        if reserve is not None:
            spawned_reserves.append(reserve)

    result = {
        "status": "purchased",
        "domain_id": domain["domain_id"],
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
            _assert_fort_capacity_available(
                connection, territory_id, str(offer["card_id"])
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
    source: str = "lord_panel",
) -> dict[str, Any]:
    ensure_lord_runtime_state(connection)
    domain = _domain_for_lord(connection, lord_id)
    domain_id = str(domain["domain_id"])
    rule = _raid_rule(connection, rule_id)
    target = _territory_state(connection, target_territory_id)
    target_owner = _optional(target["owner_domain_id"])
    if not target_owner:
        raise LordRuntimeError("raid_target_neutral", "Raid target must be owned.")
    if target_owner == domain_id:
        raise LordRuntimeError("raid_target_own", "Cannot raid your own territory.")

    token_cost = _to_int(rule["token_cost"])
    gold_cost = _to_int(rule["gold_cost"])
    if _to_int(domain["raid_tokens"]) < token_cost:
        raise LordRuntimeError("insufficient_raid_tokens", "Not enough raid tokens.")
    if _to_int(domain["gold"]) < gold_cost:
        raise LordRuntimeError("insufficient_gold", "Not enough gold for raid.")

    resistance = _territory_resistance(connection, target_territory_id, target_owner)
    loot_gold = 0 if resistance else min(gold_cost, 5 * max(1, _territory_tier(connection, target_territory_id)))
    current_time = datetime.now(UTC)
    now = _iso(current_time)
    duration_min = max(0, _to_int(rule["duration_min"]))
    expires_at = _iso(current_time + timedelta(minutes=duration_min))
    effect_id = f"raid_{uuid4().hex}"
    payload = {
        "resistance": resistance,
        "loot_gold": loot_gold,
        "loot_policy": rule["loot_policy"],
        "counterplay": rule["counterplay"],
        "visibility": "source_target_and_masters",
    }
    connection.execute(
        """
        UPDATE domain_runtime_state
        SET raid_tokens = raid_tokens - ?, gold = gold - ? + ?, updated_at = ?
        WHERE domain_id = ?
        """,
        (token_cost, gold_cost, loot_gold, now, domain_id),
    )
    connection.execute(
        """
        INSERT INTO raid_effects (
            raid_effect_id, rule_id, source_domain_id, target_domain_id,
            target_territory_id, status, starts_at_offset_min, ends_at_offset_min,
            started_at, expires_at, payload_json
        )
        VALUES (?, ?, ?, ?, ?, 'active', NULL, ?, ?, ?, ?)
        """,
        (
            effect_id,
            rule["rule_id"],
            domain_id,
            target_owner,
            target_territory_id,
            duration_min,
            now,
            expires_at,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ),
    )
    result = {
        "status": "active",
        "raid_effect_id": effect_id,
        "source_domain_id": domain_id,
        "target_domain_id": target_owner,
        "target_territory_id": target_territory_id,
        "token_spent": token_cost,
        "gold_spent": gold_cost,
        "started_at": now,
        "expires_at": expires_at,
        **payload,
    }
    log_event(connection, "lord_raid_started", result, source=source)
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


def order_action(
    connection: sqlite3.Connection,
    lord_id: str,
    *,
    action: str,
    object_id: str | None = None,
    target_player_id: str | None = None,
    visibility: str = "public",
    escrow_reward_id: str | None = None,
    order_id: str | None = None,
    player_id: str | None = None,
    result_event_id: str | None = None,
    reason: str | None = None,
    source: str = "lord_panel",
    actor_role: str = "lord",
) -> dict[str, Any]:
    ensure_lord_runtime_state(connection)
    domain = _domain_for_lord(connection, lord_id)
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
                escrow_reward_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_order_id,
                lord_id,
                target_player_id,
                object_id,
                visibility,
                status,
                escrow_reward_id,
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
        "enemy_armies": [],
        "revealed": revealed,
    }


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
    _consume_reserve(connection, domain_id, card_id, count)
    now = _iso()
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
        return {
            "kind": "existing_claim",
            "territory_id": territory_id,
            "owner_domain_id": owner_domain_id,
            "battle_required": True,
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
    cap = 2 if visibility == "public" else 1
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


def _assert_order_object_exists(connection: sqlite3.Connection, object_id: str) -> None:
    checks = (
        ("qr_objects", "qr_id"),
        ("territories", "territory_id"),
        ("items", "item_id"),
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


def _ensure_building_recruit_reserve(
    connection: sqlite3.Connection,
    domain_id: str,
    building_id: str,
    card_id: str,
    now: str,
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
    try:
        last_updated = _parse_iso(str(reserve["updated_at"]))
        current_time = _parse_iso(now)
    except ValueError:
        last_updated = current_time = datetime.now(UTC)
    elapsed_hours = int((current_time - last_updated).total_seconds() // 3600)
    if elapsed_hours <= 0:
        return None
    current_count = _to_int(reserve["count"])
    cap = BUILDING_RECRUIT_STOCK_CAP_BY_CLASS.get(unit_class, current_count + rate)
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
) -> None:
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


def _upsert_garrison(
    connection: sqlite3.Connection,
    territory_id: str,
    domain_id: str,
    card_id: str,
    count: int,
    now: str,
) -> None:
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
            SELECT r.{domain_column} AS domain_id, r.count, c.attack, c.defense, c.hp, c.tier
            FROM {table_name} r
            JOIN army_unit_cards c ON c.card_id = r.card_id
            WHERE r.status IN ('available', 'active') AND r.count > 0
            """
        ).fetchall():
            unit_power = _to_int(row["attack"]) + _to_int(row["defense"]) + _to_int(row["hp"]) + _to_int(row["tier"])
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


def _territory_resistance(
    connection: sqlite3.Connection, territory_id: str, owner_domain_id: str
) -> int:
    garrison_count = connection.execute(
        """
        SELECT COALESCE(SUM(count), 0)
        FROM garrison_runtime_state
        WHERE territory_id = ? AND domain_id = ? AND status = 'active'
        """,
        (territory_id, owner_domain_id),
    ).fetchone()[0]
    ward_bonus = 2 if _has_building(connection, owner_domain_id, "b_wards") else 0
    return int(garrison_count) + ward_bonus


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


def _stable_id(prefix: str, *parts: str) -> str:
    slug = "_".join(re.sub(r"[^A-Za-z0-9]+", "_", part).strip("_") for part in parts)
    return f"{prefix}_{slug}".lower()
