"""Read-only auth and state helpers for the lord browser frontend."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache
import json
from pathlib import Path
from typing import Any
import sqlite3

from pydantic import BaseModel, Field

from .lord_runtime import ACTIVE_ORDER_STATUSES
from .lord_runtime import active_pending_lord_move, build_lord_map_intel
from .lord_runtime import anti_snowball_cut_for_domain, build_diplomacy_signals
from .lord_runtime import ensure_lord_runtime_state, reconcile_pending_lord_moves
from .lord_runtime import recruit_growth_per_hour_for_unit_class
from .lord_runtime import visible_garrisons_for
from .lord_battle_service import list_lord_battles
from .repository import fetch_table, latest_snapshot_version

LORD_MAP_LAYOUT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "seed"
    / "lord_map_layout.json"
)

PUBLIC_ORDER_LIMIT = 2
ADDRESSED_ORDER_LIMIT = 1

ORDER_STATUS_LABELS = {
    "draft": "Черновик",
    "published": "Открыт",
    "addressed_pending": "Ждет адресата",
    "accepted": "Взят",
    "in_progress": "В работе",
    "claimed_at_prop": "У объекта",
    "submitted_pending_sync": "Ждет синхронизации",
    "pending_master_approval": "Ждет мастера",
    "completed": "Завершен",
    "failed_retryable": "Провален, можно повторить",
    "failed_closed": "Закрыт провалом",
    "cancelled_by_lord": "Отменен",
    "expired": "Истек",
    "contested_review": "На решении мастера",
}

ORDER_VISIBILITY_LABELS = {
    "public": "Публичный",
    "addressed": "Адресный",
}

ITEM_TYPE_LABELS = {
    "material": "материал",
    "trophy": "трофей",
    "plot_key": "сюжетный предмет",
    "order_token": "жетон заказа",
    "pvp_stake": "метка ставки",
    "final_evidence": "финальное свидетельство",
}


class RoleTokenRequest(BaseModel):
    token: str = Field(min_length=1)


class RoleTokenAuth(BaseModel):
    token_id: str
    role_type: str
    owner_id: str
    display_name: str | None = None
    lord_id: str | None = None
    domain_id: str | None = None
    permissions: list[str] = Field(default_factory=list)


def authenticate_role_token(
    connection: sqlite3.Connection, token: str
) -> RoleTokenAuth | None:
    normalized = token.strip()
    if not normalized:
        return None
    try:
        row = connection.execute(
            """
            SELECT
                rt.token_id,
                rt.role_type,
                rt.owner_id,
                rt.enabled,
                p.display_name,
                p.lord_id AS player_domain_id,
                d.domain_id AS owned_domain_id
            FROM role_tokens rt
            LEFT JOIN players p ON p.player_id = rt.owner_id
            LEFT JOIN domains d ON d.lord_player_id = rt.owner_id
            WHERE rt.token = ?
            """,
            (normalized,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None or str(row["enabled"]).lower() != "true":
        return None

    role_type = str(row["role_type"])
    owner_id = str(row["owner_id"])
    domain_id = _coalesce(row["owned_domain_id"], row["player_domain_id"])
    permissions = {
        "lord": ["lord_panel:read"],
        "npc_master": ["master:read", "master:write"],
    }.get(role_type, [])
    return RoleTokenAuth(
        token_id=str(row["token_id"]),
        role_type=role_type,
        owner_id=owner_id,
        display_name=_optional(row["display_name"]),
        lord_id=owner_id if role_type == "lord" else None,
        domain_id=domain_id,
        permissions=permissions,
    )


def build_lord_state(
    connection: sqlite3.Connection, lord_id: str
) -> dict[str, Any] | None:
    ensure_lord_runtime_state(connection)
    players = _table(connection, "players")
    lord = next(
        (
            player
            for player in players
            if player.get("player_id") == lord_id and player.get("role_type") == "lord"
        ),
        None,
    )
    if lord is None:
        return None

    domains = _table(connection, "domains")
    domain = next(
        (
            row
            for row in domains
            if row.get("lord_player_id") == lord_id
            or (lord.get("lord_id") and row.get("domain_id") == lord.get("lord_id"))
        ),
        None,
    )
    domain_id = domain.get("domain_id") if domain else lord.get("lord_id", "")
    reconcile_pending_lord_moves(connection, domain_id=domain_id)
    runtime_domain = _runtime_domain(connection, domain_id) or {}
    domain_payload = {**domain, **runtime_domain} if domain else runtime_domain

    territories = _table(connection, "territories")
    territory_runtime = {
        row["territory_id"]: row
        for row in _runtime_rows(connection, "territory_runtime_state", "territory_id")
    }
    map_nodes = _table(connection, "map_nodes")
    map_edges = _table(connection, "map_edges")
    pending_rewards = _runtime_rows(
        connection, "pending_tick_reward_runtime", "pending_reward_id"
    )

    owned_territories = [
        _territory_payload(
            connection,
            territory,
            territory_runtime,
            map_nodes,
            pending_rewards,
            viewer_domain_id=domain_id,
        )
        for territory in territories
        if _runtime_owner(territory, territory_runtime) == domain_id
    ]
    neutral_territories = [
        _territory_payload(
            connection,
            territory,
            territory_runtime,
            map_nodes,
            pending_rewards,
            viewer_domain_id=domain_id,
        )
        for territory in territories
        if not _runtime_owner(territory, territory_runtime)
    ]
    other_territories = [
        _territory_payload(
            connection,
            territory,
            territory_runtime,
            map_nodes,
            pending_rewards,
            viewer_domain_id=domain_id,
        )
        for territory in territories
        if _runtime_owner(territory, territory_runtime)
        and _runtime_owner(territory, territory_runtime) != domain_id
    ]

    movement = runtime_domain or _latest_for_domain(_table(connection, "movement_pools"), domain_id)
    raw_orders = [
        order
        for order in _runtime_rows(connection, "order_runtime_state", "order_id")
        if order.get("lord_id") == lord_id
    ]
    order_targets = _visible_order_targets(connection)
    eligible_recipients = _eligible_order_recipients(players)
    reward_options = _order_reward_options(connection)
    orders = _lord_order_payloads(
        connection,
        raw_orders,
        order_targets=order_targets,
        eligible_recipients=eligible_recipients,
        reward_options=reward_options,
    )
    recruit_market_rows = [
        offer
        for offer in _runtime_rows(connection, "recruit_offer_runtime", "offer_id")
        if offer.get("domain_id") == domain_id
    ]
    army_reserve = [
        reserve
        for reserve in _runtime_rows(connection, "army_reserve_runtime", "reserve_id")
        if reserve.get("domain_id") == domain_id
    ]
    recruit_market = _recruit_market_payload(
        connection, recruit_market_rows, army_reserve
    )
    active_army = [
        army
        for army in _runtime_rows(connection, "active_army_runtime", "army_id")
        if army.get("domain_id") == domain_id
    ]
    owned_buildings = [
        building
        for building in _runtime_rows(connection, "domain_buildings", "building_id")
        if building.get("domain_id") == domain_id
    ]
    raid_effects = [
        raid
        for raid in _runtime_rows(connection, "raid_effects", "raid_effect_id")
        if raid.get("source_domain_id") == domain_id
        or raid.get("target_domain_id") == domain_id
    ]
    building_catalog = _table(connection, "buildings")
    raid_rules = _raid_rule_payloads(
        _table(connection, "raid_rules"),
        owned_buildings=owned_buildings,
        building_catalog=building_catalog,
    )
    raid_targets = _raid_target_payloads(
        [
            *owned_territories,
            *neutral_territories,
            *other_territories,
        ],
        raid_effects=raid_effects,
        viewer_domain_id=domain_id,
        domains=domains,
    )
    active_raid_effects = [
        _raid_effect_payload(raid)
        for raid in raid_effects
        if raid.get("status") == "active"
    ]
    raid_history = sorted(
        (_raid_effect_payload(raid) for raid in raid_effects),
        key=lambda raid: str(raid.get("started_at") or ""),
        reverse=True,
    )[:8]

    snapshot_version = latest_snapshot_version(connection)
    active_orders = [
        order for order in raw_orders if order.get("status") in ACTIVE_ORDER_STATUSES
    ]
    owned_ids = {item["territory_id"] for item in owned_territories}
    garrison_targets = _garrison_targets(
        owned_territories,
        neutral_territories,
        other_territories,
        domain_id,
    )
    battles = list_lord_battles(connection, domain_id=domain_id)["items"]
    claims = _visible_claims(connection, domain_id)
    pending_domain_rewards = [
        reward
        for reward in pending_rewards
        if reward.get("domain_id") == domain_id or reward.get("territory_id") in owned_ids
    ]
    anti_snowball = anti_snowball_cut_for_domain(connection, domain_id)
    territory_income = sum(
        _territory_income_per_hour(territory) for territory in owned_territories
    )
    raw_income = _int_value(domain_payload.get("base_income")) + territory_income
    income_cut_percent = _int_value(anti_snowball.get("income_cut_percent"))
    income = (raw_income * (100 - income_cut_percent)) // 100
    active_army_slots_used = _active_stack_count(active_army)
    active_army_capacity = _int_value(domain_payload.get("active_army_capacity"))
    domain_payload = {
        **domain_payload,
        "territory_income_per_hour": territory_income,
        "raw_income_per_hour": raw_income,
        "income_per_hour": income,
        "active_army_slots_used": active_army_slots_used,
        "active_army_slots_free": max(0, active_army_capacity - active_army_slots_used),
    }
    pending_move = active_pending_lord_move(connection, domain_id)
    route_options = {
        "current_node_id": domain_payload.get("current_node_id"),
        "mp_available": _int_value(domain_payload.get("current_mp")),
        "mp_cap": _int_value(domain_payload.get("mp_cap")),
        "pending_move_active": pending_move is not None,
    }

    return {
        "snapshot_version": snapshot_version,
        "lord": _lord_payload(lord, domain_id),
        "domain": domain_payload,
        "movement": movement,
        "summary": {
            "owned_territories": len(owned_territories),
            "neutral_territories": len(neutral_territories),
            "other_territories": len(other_territories),
            "active_orders": len(active_orders),
            "pending_rewards": len(pending_domain_rewards),
            "garrison_targets": len(garrison_targets),
            "active_battles": sum(1 for battle in battles if battle.get("status") == "active"),
            "active_claims": len(claims),
            "available_recruits": sum(
                1 for offer in recruit_market if offer.get("status") == "available"
            ),
            "owned_buildings": len(owned_buildings),
            "active_raids": sum(1 for raid in raid_effects if raid.get("status") == "active"),
        },
        "territories": owned_territories,
        "neutral_territories": neutral_territories,
        "other_territories": other_territories,
        "garrison_targets": garrison_targets,
        "claims": claims,
        "battles": battles,
        "orders": orders,
        "order_cap": _order_cap_payload(connection, lord_id),
        "escrow": _order_escrow_payload(
            connection,
            lord_id,
            domain_payload=domain_payload,
            reward_options=reward_options,
        ),
        "order_conflicts": _order_conflicts_payload(
            connection,
            lord_id,
            raw_orders,
            order_targets=order_targets,
        ),
        "visible_targets": order_targets,
        "eligible_recipients": eligible_recipients,
        "order_reward_options": reward_options,
        "recruit_market": recruit_market,
        "army_reserve": army_reserve,
        "active_army": active_army,
        "owned_buildings": owned_buildings,
        "building_catalog": _building_catalog_payload(building_catalog, owned_buildings),
        "raid_tokens": _int_value(domain_payload.get("raid_tokens")),
        "raid_rules": raid_rules,
        "raid_targets": raid_targets,
        "active_raid_effects": active_raid_effects,
        "raid_history": raid_history,
        "raid_effects": raid_effects,
        "map_nodes": map_nodes,
        "map_edges": map_edges,
        "lord_map_layout": _lord_map_layout(),
        "lord_map_intel": build_lord_map_intel(connection, domain_id),
        "pending_move": pending_move,
        "route_options": route_options,
        "diplomacy_signals": build_diplomacy_signals(connection, domain_id),
        "anti_snowball": anti_snowball,
        "timer_summary": _timer_summary(connection),
        "action_surfaces": _action_surfaces(lord_id),
    }


def _lord_order_payloads(
    connection: sqlite3.Connection,
    orders: list[dict[str, Any]],
    *,
    order_targets: list[dict[str, Any]],
    eligible_recipients: list[dict[str, Any]],
    reward_options: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    targets_by_id = {str(item["target_id"]): item for item in order_targets}
    recipients_by_id = {str(item["player_id"]): item for item in eligible_recipients}
    rewards_by_id = {str(item["reward_id"]): item for item in reward_options}
    escrow_by_order = _escrow_rows_by_order(connection, [str(order["order_id"]) for order in orders])
    conflicts_by_order = _conflict_badges_by_order(connection, orders, targets_by_id)

    decorated = []
    for order in orders:
        object_id = str(order.get("object_id") or "")
        target = targets_by_id.get(object_id, _fallback_order_target(object_id))
        reward = rewards_by_id.get(str(order.get("escrow_reward_id") or ""), {})
        executor_id = _coalesce(
            order.get("accepted_by_player_id"),
            order.get("submitted_by_player_id"),
            order.get("target_player_id"),
        )
        executor = recipients_by_id.get(str(executor_id or ""), {})
        escrow_rows = escrow_by_order.get(str(order["order_id"]), [])
        escrow_status = _order_escrow_status(escrow_rows, order.get("status"))
        visibility = str(order.get("visibility") or "public")
        status = str(order.get("status") or "")
        decorated.append(
            {
                **order,
                "visibility_label": ORDER_VISIBILITY_LABELS.get(visibility, visibility),
                "status_label": ORDER_STATUS_LABELS.get(status, status),
                "object_label": target.get("label"),
                "target_type": target.get("target_type"),
                "target_type_label": target.get("target_type_label"),
                "location_label": target.get("location_label"),
                "target_act_id": target.get("act_id"),
                "visible_hook": _order_visible_hook(order, target),
                "reward_label": reward.get("label") or _humanize_identifier(order.get("escrow_reward_id")),
                "reward_gold": reward.get("gold", 0),
                "reward_xp": reward.get("xp", 0),
                "escrow_status": escrow_status,
                "escrow_label": _escrow_status_label(escrow_status),
                "target_player_label": _player_label(
                    recipients_by_id.get(str(order.get("target_player_id") or ""), {})
                ),
                "executor_label": _player_label(executor),
                "conflict_badge": conflicts_by_order.get(str(order["order_id"])),
            }
        )
    return decorated


def _visible_order_targets(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    territories = _table(connection, "territories")
    map_nodes = _table(connection, "map_nodes")
    pve_scenarios = {row.get("scenario_id"): row for row in _table(connection, "pve_scenarios")}
    targets: list[dict[str, Any]] = []

    nodes_by_territory = {
        row.get("territory_id"): row for row in map_nodes if row.get("territory_id")
    }
    nodes_by_id = {row.get("node_id"): row for row in map_nodes if row.get("node_id")}

    for territory in territories:
        node = nodes_by_territory.get(territory.get("territory_id"), {})
        targets.append(
            {
                "target_id": territory.get("territory_id"),
                "target_type": "territory",
                "target_type_label": "Территория",
                "label": territory.get("name") or _humanize_identifier(territory.get("territory_id")),
                "location_label": node.get("name") or territory.get("name"),
                "act_id": None,
                "source": "territories",
            }
        )

    for qr in _table(connection, "qr_objects"):
        scenario = pve_scenarios.get(qr.get("scenario_id"), {})
        node = nodes_by_id.get(qr.get("location_node_id"), {})
        scene_label = _scene_type_label(scenario.get("scene_type") or qr.get("qr_mode"))
        location_label = node.get("name") or _humanize_identifier(qr.get("location_node_id"))
        targets.append(
            {
                "target_id": qr.get("qr_id"),
                "target_type": "qr_scene",
                "target_type_label": "QR-сцена",
                "label": f"{scene_label}: {location_label}",
                "location_label": location_label,
                "act_id": qr.get("act_id"),
                "source": "qr_objects",
            }
        )

    for item in _table(connection, "items"):
        targets.append(
            {
                "target_id": item.get("item_id"),
                "target_type": "item",
                "target_type_label": "Предмет",
                "label": _item_label(item),
                "location_label": "предмет",
                "act_id": None,
                "source": "items",
            }
        )

    for artifact in _table(connection, "artifacts"):
        targets.append(
            {
                "target_id": artifact.get("artifact_id"),
                "target_type": "artifact",
                "target_type_label": "Артефакт",
                "label": _artifact_label(artifact),
                "location_label": "артефакт",
                "act_id": None,
                "source": "artifacts",
            }
        )

    return [
        target
        for target in sorted(
            targets,
            key=lambda item: (
                str(item.get("target_type_label") or ""),
                str(item.get("label") or ""),
            ),
        )
        if target.get("target_id")
    ]


def _eligible_order_recipients(players: list[dict[str, str]]) -> list[dict[str, Any]]:
    recipients = []
    for player in players:
        role_type = str(player.get("role_type") or "")
        if role_type not in {"witcher", "sorceress"}:
            continue
        recipients.append(
            {
                "player_id": player.get("player_id"),
                "display_name": player.get("display_name") or _humanize_identifier(player.get("player_id")),
                "role_type": role_type,
                "role_label": "Ведьмак" if role_type == "witcher" else "Чародейка",
            }
        )
    return sorted(recipients, key=lambda item: str(item.get("display_name") or ""))


def _order_reward_options(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rewards = []
    for reward in _table(connection, "rewards"):
        item_labels = _reward_asset_labels(connection, reward)
        gold = _int_value(reward.get("gold"))
        xp = _int_value(reward.get("xp"))
        rewards.append(
            {
                "reward_id": reward.get("reward_id"),
                "label": _reward_label(gold=gold, xp=xp, asset_labels=item_labels),
                "gold": gold,
                "xp": xp,
                "asset_labels": item_labels,
                "approval_policy": reward.get("approval_policy"),
            }
        )
    return sorted(rewards, key=lambda item: str(item.get("label") or ""))


def _order_cap_payload(connection: sqlite3.Connection, lord_id: str) -> dict[str, int]:
    count_statuses = _order_statuses_counting_against_cap(connection)
    return {
        "public_active": _order_count_for_visibility(
            connection, lord_id, "public", count_statuses
        ),
        "public_limit": PUBLIC_ORDER_LIMIT,
        "addressed_active": _order_count_for_visibility(
            connection, lord_id, "addressed", count_statuses
        ),
        "addressed_limit": ADDRESSED_ORDER_LIMIT,
    }


def _order_escrow_payload(
    connection: sqlite3.Connection,
    lord_id: str,
    *,
    domain_payload: dict[str, Any],
    reward_options: list[dict[str, Any]],
) -> dict[str, Any]:
    reward_by_id = {str(item.get("reward_id")): item for item in reward_options}
    locked_gold = 0
    locked_assets: dict[tuple[str, str], dict[str, Any]] = {}
    try:
        rows = connection.execute(
            """
            SELECT e.*
            FROM escrow_ledger e
            JOIN order_runtime_state o ON o.order_id = e.order_id
            WHERE o.lord_id = ? AND e.status = 'reserved'
            ORDER BY e.created_at, e.ledger_id
            """,
            (lord_id,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    for row in rows:
        locked_gold += _int_value(row["reserved_gold"])
        reward = reward_by_id.get(str(row["reward_id"]), {})
        for asset in _loads_json(row["reserved_assets_json"], []):
            if not isinstance(asset, dict):
                continue
            asset_type = str(asset.get("asset_type") or "")
            asset_id = str(asset.get("asset_id") or "")
            key = (asset_type, asset_id)
            quantity = _int_value(asset.get("quantity")) or 1
            entry = locked_assets.setdefault(
                key,
                {
                    "asset_type": asset_type,
                    "asset_id": asset_id,
                    "label": _asset_label(asset_type, asset_id),
                    "quantity": 0,
                    "reward_label": reward.get("label"),
                },
            )
            entry["quantity"] += quantity
    return {
        "locked_gold": locked_gold,
        "locked_assets": sorted(
            locked_assets.values(),
            key=lambda item: str(item.get("label") or ""),
        ),
        "locked_asset_count": sum(item["quantity"] for item in locked_assets.values()),
        "available_gold": _int_value(
            _coalesce(
                domain_payload.get("gold"),
                domain_payload.get("starting_gold"),
            )
        ),
    }


def _order_conflicts_payload(
    connection: sqlite3.Connection,
    lord_id: str,
    orders: list[dict[str, Any]],
    *,
    order_targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    own_object_ids = {str(order.get("object_id") or "") for order in orders if order.get("object_id")}
    if not own_object_ids:
        return []
    count_statuses = _order_statuses_counting_against_cap(connection) | {"contested_review"}
    targets_by_id = {str(item["target_id"]): item for item in order_targets}
    placeholders = ", ".join("?" for _ in own_object_ids)
    status_placeholders = ", ".join("?" for _ in count_statuses)
    try:
        rows = [
            dict(row)
            for row in connection.execute(
                f"""
                SELECT order_id, lord_id, object_id, visibility, status
                FROM order_runtime_state
                WHERE object_id IN ({placeholders})
                  AND status IN ({status_placeholders})
                ORDER BY object_id, updated_at, order_id
                """,
                (*sorted(own_object_ids), *sorted(count_statuses)),
            ).fetchall()
        ]
    except sqlite3.OperationalError:
        return []

    conflicts = []
    for object_id in sorted({str(row["object_id"]) for row in rows}):
        group = [row for row in rows if str(row["object_id"]) == object_id]
        own_group = [row for row in group if row.get("lord_id") == lord_id]
        if not own_group:
            continue
        is_review = any(str(row.get("status")) == "contested_review" for row in own_group)
        other_lord_count = len({row["lord_id"] for row in group if row.get("lord_id") != lord_id})
        same_object_race = len(group) > len(own_group) or len(own_group) > 1
        if not is_review and not same_object_race:
            continue
        target = targets_by_id.get(object_id, _fallback_order_target(object_id))
        conflicts.append(
            {
                "conflict_id": f"order_conflict_{object_id}",
                "object_id": object_id,
                "object_label": target.get("label"),
                "status": "contested_review" if is_review else "object_conflict",
                "badge_label": "На решении мастера" if is_review else "Конкурирующий заказ",
                "own_order_ids": [row["order_id"] for row in own_group],
                "competing_order_count": max(0, len(group) - len(own_group)),
                "competing_lord_count": other_lord_count,
            }
        )
    return conflicts


def _order_statuses_counting_against_cap(connection: sqlite3.Connection) -> set[str]:
    try:
        rows = connection.execute(
            """
            SELECT status_id
            FROM order_status_rules
            WHERE lower(COALESCE(counts_against_cap, 'false')) = 'true'
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return set(ACTIVE_ORDER_STATUSES)
    return {str(row["status_id"]) for row in rows} | set(ACTIVE_ORDER_STATUSES)


def _order_count_for_visibility(
    connection: sqlite3.Connection,
    lord_id: str,
    visibility: str,
    statuses: set[str],
) -> int:
    if not statuses:
        return 0
    placeholders = ", ".join("?" for _ in statuses)
    try:
        row = connection.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM order_runtime_state
            WHERE lord_id = ? AND visibility = ? AND status IN ({placeholders})
            """,
            (lord_id, visibility, *sorted(statuses)),
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    return _int_value(row["count"] if row else 0)


def _escrow_rows_by_order(
    connection: sqlite3.Connection, order_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    if not order_ids:
        return {}
    placeholders = ", ".join("?" for _ in order_ids)
    try:
        rows = [
            dict(row)
            for row in connection.execute(
                f"""
                SELECT *
                FROM escrow_ledger
                WHERE order_id IN ({placeholders})
                ORDER BY created_at, ledger_id
                """,
                tuple(order_ids),
            ).fetchall()
        ]
    except sqlite3.OperationalError:
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["order_id"]), []).append(row)
    return grouped


def _conflict_badges_by_order(
    connection: sqlite3.Connection,
    orders: list[dict[str, Any]],
    targets_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    conflicts = _order_conflicts_payload(
        connection,
        str(orders[0].get("lord_id") or "") if orders else "",
        orders,
        order_targets=list(targets_by_id.values()),
    )
    badges: dict[str, dict[str, Any]] = {}
    for conflict in conflicts:
        for order_id in conflict.get("own_order_ids", []):
            badges[str(order_id)] = {
                "status": conflict.get("status"),
                "label": conflict.get("badge_label"),
                "object_label": conflict.get("object_label"),
            }
    return badges


def _order_escrow_status(rows: list[dict[str, Any]], status: object) -> str:
    if any(str(row.get("status")) == "reserved" for row in rows):
        return "reserved"
    if any(str(row.get("status")) == "awarded" for row in rows):
        return "awarded"
    if any(str(row.get("status")) == "released" for row in rows):
        return "released"
    if str(status) == "draft":
        return "not_locked"
    return "none"


def _escrow_status_label(status: str) -> str:
    return {
        "reserved": "В залоге",
        "awarded": "Выплачено",
        "released": "Возвращено",
        "not_locked": "Не удержано",
    }.get(status, "Нет залога")


def _order_visible_hook(order: dict[str, Any], target: dict[str, Any]) -> str:
    stored_hook = _optional(order.get("visible_hook"))
    if stored_hook:
        return stored_hook
    status = str(order.get("status") or "")
    prefix = "Адресный заказ" if order.get("visibility") == "addressed" else "Публичный заказ"
    if status == "contested_review":
        prefix = "Спорный заказ"
    label = target.get("label") or _humanize_identifier(order.get("object_id"))
    location = target.get("location_label")
    return f"{prefix}: {label}" + (f" ({location})" if location and location != label else "")


def _fallback_order_target(target_id: object) -> dict[str, Any]:
    return {
        "target_id": target_id,
        "target_type": "unknown",
        "target_type_label": "Объект",
        "label": _humanize_identifier(target_id),
        "location_label": "",
        "source": "unknown",
    }


def _scene_type_label(value: object) -> str:
    return {
        "monster_hunt": "Охота",
        "investigation": "Расследование",
        "moral_choice": "Договор",
        "puzzle_check": "Загадка",
        "sorceress_hook": "Чародейский след",
        "order_object": "Заказной объект",
        "lord_hook": "Интрига владения",
        "npc_deal": "Сделка",
        "artifact": "Артефакт",
        "repeatable_scene": "Сцена",
        "always_available_scene": "Открытая сцена",
        "unique_object": "Уникальный объект",
    }.get(str(value or ""), _humanize_identifier(value))


def _item_label(item: dict[str, Any]) -> str:
    raw_type = str(item.get("item_type") or "")
    item_type = ITEM_TYPE_LABELS.get(raw_type, _humanize_identifier(raw_type))
    tier = _optional(item.get("tier"))
    return f"{item_type}" + (f", тир {tier}" if tier else "")


def _artifact_label(artifact: dict[str, Any]) -> str:
    rarity = _optional(artifact.get("rarity")) or "Rare"
    return f"Артефакт {rarity}"


def _reward_asset_labels(connection: sqlite3.Connection, reward: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for item_id in _split_ids(reward.get("item_ids")):
        labels.append(_asset_label("item", item_id, connection=connection))
    for card_id in _split_ids(reward.get("card_ids")):
        labels.append(_asset_label("card", card_id, connection=connection))
    for artifact_id in _split_ids(reward.get("artifact_ids")):
        labels.append(_asset_label("artifact", artifact_id, connection=connection))
    return labels


def _reward_label(*, gold: int, xp: int, asset_labels: list[str]) -> str:
    parts = []
    if gold:
        parts.append(f"{gold} золота")
    if xp:
        parts.append(f"{xp} опыта")
    parts.extend(asset_labels)
    return ", ".join(parts) if parts else "Награда без выплаты"


def _asset_label(
    asset_type: str,
    asset_id: str,
    *,
    connection: sqlite3.Connection | None = None,
) -> str:
    if connection is not None and asset_type == "item":
        row = _row_by_id(connection, "items", "item_id", asset_id)
        if row:
            return _item_label(row)
    if connection is not None and asset_type == "artifact":
        row = _row_by_id(connection, "artifacts", "artifact_id", asset_id)
        if row:
            return _artifact_label(row)
    if asset_type == "card":
        return "Карта награды"
    if asset_type == "item":
        return "Предмет награды"
    if asset_type == "artifact":
        return "Артефакт"
    return _humanize_identifier(asset_type or asset_id)


def _row_by_id(
    connection: sqlite3.Connection, table_name: str, column_name: str, value: str
) -> dict[str, Any] | None:
    try:
        row = connection.execute(
            f"SELECT * FROM {table_name} WHERE {column_name} = ? LIMIT 1",
            (value,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def _player_label(player: dict[str, Any]) -> str | None:
    if not player:
        return None
    role = player.get("role_label")
    name = player.get("display_name")
    return f"{name}, {role}" if role and name else name


def _split_ids(value: object) -> list[str]:
    if value in {None, ""}:
        return []
    return [
        item.strip()
        for chunk in str(value).split(";")
        for item in chunk.split(",")
        if item.strip()
    ]


def _loads_json(value: object, fallback: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except (TypeError, json.JSONDecodeError):
        return fallback


def _humanize_identifier(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.replace("_", " ").replace("-", " ")


def _raid_rule_payloads(
    rows: list[dict[str, Any]],
    *,
    owned_buildings: list[dict[str, Any]],
    building_catalog: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    owned_ids = {str(building.get("building_id")) for building in owned_buildings}
    building_names = {
        str(building.get("building_id")): str(building.get("name") or building.get("building_id"))
        for building in building_catalog
    }
    payloads: list[dict[str, Any]] = []
    for row in rows:
        rule_id = str(row.get("rule_id") or "")
        required_ids = _split_ids(row.get("required_building_ids"))
        missing_ids = [building_id for building_id in required_ids if building_id not in owned_ids]
        missing_names = [building_names.get(building_id, building_id) for building_id in missing_ids]
        token_cost = _int_value(row.get("token_cost"))
        gold_cost = _int_value(row.get("gold_cost"))
        duration_minutes = _int_value(row.get("duration_minutes") or row.get("duration_min"))
        category = str(row.get("category") or _raid_rule_category_fallback(rule_id))
        effect_type = str(row.get("effect_type") or _raid_rule_effect_fallback(category))

        payloads.append(
            {
                "rule_id": rule_id,
                "name": row.get("name") or _humanize_identifier(rule_id) or "Рейд",
                "tier": _int_value(row.get("tier")) or 1,
                "category": category,
                "category_label": _raid_category_label(category),
                "description": row.get("description")
                or "Краткая не-боевая операция с временным эффектом.",
                "token_cost": token_cost,
                "gold_cost": gold_cost,
                "duration_minutes": duration_minutes,
                "effect_type": effect_type,
                "allowed_target_types": _split_ids(row.get("allowed_target_types"))
                or ["territory"],
                "required_building_ids": required_ids,
                "required_building_labels": [
                    building_names.get(building_id, building_id)
                    for building_id in required_ids
                ],
                "visibility": row.get("visibility") or "source_target_and_masters",
                "counterplay": row.get("counterplay") or "master_review",
                "locked_reason": (
                    f"Нужно построить: {', '.join(missing_names)}"
                    if missing_names
                    else None
                ),
            }
        )
    return payloads


def _raid_target_payloads(
    territories: list[dict[str, Any]],
    *,
    raid_effects: list[dict[str, Any]],
    viewer_domain_id: str,
    domains: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    domain_names = {
        str(domain.get("domain_id")): str(domain.get("name") or domain.get("domain_id"))
        for domain in domains
    }
    active_effects_by_target: dict[str, list[dict[str, Any]]] = {}
    for effect in raid_effects:
        if effect.get("status") != "active":
            continue
        target_id = str(effect.get("target_territory_id") or "")
        if not target_id:
            continue
        active_effects_by_target.setdefault(target_id, []).append(
            _raid_effect_payload(effect)
        )

    payloads: list[dict[str, Any]] = []
    for territory in territories:
        territory_id = str(territory.get("territory_id") or "")
        owner_domain_id = _optional(territory.get("owner_domain_id"))
        is_residence = str(territory.get("bonus_type") or "") == "residence"
        is_owned_by_viewer = owner_domain_id == viewer_domain_id
        can_target = bool(owner_domain_id and not is_owned_by_viewer)
        disabled_reason = ""
        if not owner_domain_id:
            disabled_reason = "Нейтральные земли рейдом не берутся"
        elif is_owned_by_viewer:
            disabled_reason = "Своя территория не цель рейда"

        payloads.append(
            {
                "target_territory_id": territory_id,
                "name": territory.get("name") or _humanize_identifier(territory_id),
                "owner_domain_id": owner_domain_id,
                "owner_label": domain_names.get(owner_domain_id or "", "ничья"),
                "tier": _int_value(territory.get("tier")) or 1,
                "bonus_type": territory.get("bonus_type") or "",
                "bonus_label": _bonus_label(territory.get("bonus_type")),
                "is_residence": is_residence,
                "is_raid_only": is_residence,
                "active_effects": active_effects_by_target.get(territory_id, []),
                "raid_resistance_label": (
                    "детали скрыты"
                    if owner_domain_id and not is_owned_by_viewer
                    else "свои укрепления"
                ),
                "visibility_level": (
                    "hidden_details"
                    if owner_domain_id and not is_owned_by_viewer
                    else "owner_full"
                ),
                "can_target": can_target,
                "disabled_reason": disabled_reason,
            }
        )
    return payloads


def _raid_effect_payload(effect: dict[str, Any]) -> dict[str, Any]:
    payload = _loads_json(effect.get("payload_json"), {})
    resistance = _int_value(payload.get("resistance"))
    loot_gold = _int_value(payload.get("loot_gold"))
    return {
        "raid_effect_id": effect.get("raid_effect_id"),
        "rule_id": effect.get("rule_id"),
        "source_domain_id": effect.get("source_domain_id"),
        "target_domain_id": effect.get("target_domain_id"),
        "target_territory_id": effect.get("target_territory_id"),
        "status": effect.get("status"),
        "effect_type": payload.get("effect_type") or effect.get("rule_id"),
        "started_at": effect.get("started_at"),
        "expires_at": effect.get("expires_at"),
        "expired_at": effect.get("expired_at"),
        "resisted": resistance > 0,
        "loot_applied": loot_gold > 0,
        "loot_gold": loot_gold,
        "visibility": payload.get("visibility") or "source_target_and_masters",
        "counterplay": payload.get("counterplay") or "",
        "result_label": (
            f"Добыча: {loot_gold} золота"
            if loot_gold
            else "Сопротивление цели"
            if resistance
            else "Эффект наложен"
        ),
    }


def _raid_rule_category_fallback(rule_id: str) -> str:
    if "loot" in rule_id:
        return "loot"
    if "recruit" in rule_id:
        return "recruit"
    if "order" in rule_id or "intrigue" in rule_id:
        return "intrigue"
    if "residence" in rule_id:
        return "residence"
    if "garrison" in rule_id or "military" in rule_id:
        return "military"
    return "economy"


def _raid_rule_effect_fallback(category: str) -> str:
    return {
        "economy": "income_down",
        "military": "defense_down",
        "recruit": "recruit_block",
        "intrigue": "order_visibility_disrupt",
        "loot": "loot_once",
        "residence": "residence_pressure",
    }.get(category, "temporary_debuff")


def _raid_category_label(category: object) -> str:
    return {
        "economy": "Экономика",
        "military": "Военная диверсия",
        "recruit": "Саботаж найма",
        "intrigue": "Интрига",
        "loot": "Налет за добычей",
        "residence": "Рейд резиденции",
    }.get(str(category or ""), _humanize_identifier(category))


def _bonus_label(value: object) -> str:
    return {
        "residence": "резиденция",
        "gold_income": "доход",
        "recruit": "найм",
        "order": "заказы",
        "defense": "оборона",
        "magic": "магия",
        "resource": "ресурс",
        "research": "исследование",
        "artifact": "артефакт",
        "special": "особое",
        "raid_cover": "укрытие",
        "visibility": "видимость",
    }.get(str(value or ""), _humanize_identifier(value))


@lru_cache(maxsize=1)
def _lord_map_layout() -> dict[str, Any]:
    if not LORD_MAP_LAYOUT_PATH.exists():
        return {}
    return json.loads(LORD_MAP_LAYOUT_PATH.read_text(encoding="utf-8"))


def _lord_payload(lord: dict[str, str], domain_id: str) -> dict[str, str]:
    return {
        "lord_id": lord["player_id"],
        "display_name": lord["display_name"],
        "domain_id": domain_id,
        "level": lord["level"],
        "xp": lord["xp"],
        "gold": lord["gold"],
        "reputation": lord["reputation"],
    }


def _territory_payload(
    connection: sqlite3.Connection,
    territory: dict[str, str],
    territory_runtime: dict[str, dict[str, str]],
    map_nodes: list[dict[str, str]],
    pending_rewards: list[dict[str, str]],
    *,
    viewer_domain_id: str,
) -> dict[str, Any]:
    territory_id = territory["territory_id"]
    node = next(
        (row for row in map_nodes if row.get("territory_id") == territory_id),
        {},
    )
    runtime = territory_runtime.get(territory_id, {})
    owner_domain_id = runtime.get("owner_domain_id", territory.get("owner_domain_id", ""))
    garrisons = visible_garrisons_for(connection, territory_id, viewer_domain_id)
    fort = _territory_fort_payload(connection, territory_id)
    if fort is not None:
        garrison_capacity = _int_value(fort.get("garrison_capacity"))
        exact_slots_visible = owner_domain_id == viewer_domain_id or not owner_domain_id
        if exact_slots_visible:
            garrison_slots_used = _active_stack_count(garrisons)
            fort = {
                **fort,
                "garrison_slots_used": garrison_slots_used,
                "garrison_slots_free": max(0, garrison_capacity - garrison_slots_used),
            }

    return {
        **territory,
        "owner_domain_id": owner_domain_id,
        "status": runtime.get("status", "controlled" if territory.get("owner_domain_id") else "neutral"),
        "contested_by_domain_id": runtime.get("contested_by_domain_id", ""),
        "node_id": node.get("node_id", ""),
        "node_name": node.get("name", territory["name"]),
        "node_type": node.get("node_type", ""),
        "income_per_hour": _territory_income_per_hour(territory),
        "fort": fort,
        "garrisons": garrisons,
        "pending_rewards": [
            row for row in pending_rewards if row.get("territory_id") == territory_id
        ],
    }


def _building_catalog_payload(
    rows: list[dict[str, str]], owned_buildings: list[dict[str, str]]
) -> list[dict[str, str]]:
    owned_ids = {row["building_id"] for row in owned_buildings}
    return [
        {
            **row,
            "status": "owned" if row.get("building_id") in owned_ids else "available",
        }
        for row in rows
    ]


def _recruit_market_payload(
    connection: sqlite3.Connection,
    offers: list[dict[str, str]],
    army_reserve: list[dict[str, str]],
) -> list[dict[str, Any]]:
    unit_cards = {row["card_id"]: row for row in _table(connection, "army_unit_cards")}
    stock_by_card: dict[str, int] = {}
    for reserve in army_reserve:
        if reserve.get("status") not in {"available", "active"}:
            continue
        card_id = str(reserve.get("card_id") or "")
        stock_by_card[card_id] = stock_by_card.get(card_id, 0) + _int_value(
            reserve.get("count")
        )

    payload_by_card: dict[str, dict[str, Any]] = {}
    for offer in offers:
        status = str(offer.get("status") or "")
        if status not in {"available", "held"}:
            continue
        card_id = str(offer.get("card_id") or "")
        card = unit_cards.get(card_id)
        unit_payload = None
        if card is not None:
            unit_payload = {
                "card_id": card_id,
                "unit_class": card.get("unit_class", ""),
                "tier": _int_value(card.get("tier")),
                "attack": _int_value(card.get("attack")),
                "defense": _int_value(card.get("defense")),
                "hp": _int_value(card.get("hp")),
                "initiative": _int_value(card.get("initiative")),
                "move_range": _int_value(card.get("move_range")),
                "attack_range": _int_value(card.get("attack_range")),
                "cost": _int_value(card.get("cost")),
                "source_id": card.get("source_id", ""),
            }
        stock = stock_by_card.get(card_id, 0)
        rate_per_hour = (
            recruit_growth_per_hour_for_unit_class(str(card.get("unit_class", "")))
            if card is not None
            else 0
        )
        entry = {
            **offer,
            "cost": _int_value(offer.get("cost")),
            "current_stock": stock,
            "stock": stock,
            "rate_per_hour": rate_per_hour,
            "unit": unit_payload,
        }
        previous = payload_by_card.get(card_id)
        if previous is None or _recruit_offer_payload_sort_key(entry) > _recruit_offer_payload_sort_key(previous):
            payload_by_card[card_id] = entry
    return sorted(
        payload_by_card.values(),
        key=lambda item: (
            str(item.get("unit", {}).get("unit_class") if item.get("unit") else ""),
            str(item.get("card_id") or ""),
        ),
    )


def _recruit_offer_payload_sort_key(offer: dict[str, Any]) -> tuple[int, str, str]:
    status_rank = {"held": 2, "available": 1}.get(str(offer.get("status") or ""), 0)
    return (
        status_rank,
        str(offer.get("updated_at") or ""),
        str(offer.get("offer_id") or ""),
    )


def _territory_fort_payload(
    connection: sqlite3.Connection, territory_id: str
) -> dict[str, Any] | None:
    if (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'territory_forts'"
        ).fetchone()
        is None
    ):
        return None
    row = connection.execute(
        """
        SELECT fort_id, territory_id, name, theme, garrison_capacity,
               art_prompt_id, background_asset_id, card_asset_id
        FROM territory_forts
        WHERE territory_id = ?
        LIMIT 1
        """,
        (territory_id,),
    ).fetchone()
    if row is None:
        return None
    payload = dict(row)
    payload["garrison_capacity"] = int(payload["garrison_capacity"])
    return payload


def _garrison_targets(
    owned_territories: list[dict[str, Any]],
    neutral_territories: list[dict[str, Any]],
    other_territories: list[dict[str, Any]],
    domain_id: str,
) -> list[dict[str, Any]]:
    targets = [
        {**territory, "garrison_target_reason": "controlled"}
        for territory in owned_territories
    ]
    for territory in [*neutral_territories, *other_territories]:
        if (
            territory.get("status") == "capture_pending_garrison"
            and territory.get("contested_by_domain_id") == domain_id
        ):
            targets.append(
                {**territory, "garrison_target_reason": "capture_pending_garrison"}
            )
    return targets


def _visible_claims(connection: sqlite3.Connection, domain_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            claim.claim_id,
            claim.territory_id,
            claim.claimant_domain_id,
            claim.defender_domain_id,
            claim.status,
            claim.source,
            claim.created_at,
            claim.resolved_at,
            claim.battle_required,
            territory.name AS territory_name,
            node.node_id,
            node.name AS node_name
        FROM territory_claim_runtime claim
        LEFT JOIN territories territory ON territory.territory_id = claim.territory_id
        LEFT JOIN map_nodes node ON node.territory_id = claim.territory_id
        WHERE claim.status IN (
            'in_battle',
            'contested',
            'contested_pending_tick',
            'awaiting_garrison',
            'capture_pending_garrison'
        )
          AND (
            claim.claimant_domain_id = ?
            OR claim.defender_domain_id = ?
          )
        ORDER BY claim.created_at, claim.claim_id
        """,
        (domain_id, domain_id),
    ).fetchall()
    return [
        {
            **dict(row),
            "battle_required": bool(row["battle_required"]),
        }
        for row in rows
    ]


def _action_surfaces(lord_id: str) -> list[dict[str, str]]:
    base = f"/api/lords/{lord_id}"
    return [
        {
            "id": "move",
            "label": "Movement",
            "method": "POST",
            "endpoint": f"{base}/move",
            "status": "ready",
        },
        {
            "id": "garrisons",
            "label": "Garrisons",
            "method": "POST",
            "endpoint": f"{base}/garrisons/transfer",
            "status": "ready",
        },
        {
            "id": "buildings",
            "label": "Buildings",
            "method": "POST",
            "endpoint": f"{base}/buildings",
            "status": "ready",
        },
        {
            "id": "recruit",
            "label": "Recruit",
            "method": "POST",
            "endpoint": f"{base}/recruit",
            "status": "ready",
        },
        {
            "id": "raids",
            "label": "Raids",
            "method": "POST",
            "endpoint": f"{base}/raids",
            "status": "ready",
        },
        {
            "id": "orders",
            "label": "Orders",
            "method": "POST",
            "endpoint": f"{base}/orders",
            "status": "ready",
        },
        {
            "id": "lord_battles",
            "label": "Lord battles",
            "method": "POST",
            "endpoint": "/api/lord-battles",
            "status": "ready",
        },
    ]


def _runtime_owner(
    territory: dict[str, str], territory_runtime: dict[str, dict[str, str]]
) -> str:
    runtime = territory_runtime.get(territory["territory_id"], {})
    return runtime.get("owner_domain_id") or territory.get("owner_domain_id", "")


def _runtime_domain(
    connection: sqlite3.Connection, domain_id: str
) -> dict[str, str] | None:
    try:
        row = connection.execute(
            "SELECT * FROM domain_runtime_state WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def _runtime_rows(
    connection: sqlite3.Connection, table_name: str, order_column: str
) -> list[dict[str, str]]:
    try:
        rows = connection.execute(
            f"SELECT * FROM {table_name} ORDER BY {order_column}"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(row) for row in rows]


def _latest_for_domain(rows: list[dict[str, str]], domain_id: str) -> dict[str, str] | None:
    matching = [row for row in rows if row.get("domain_id") == domain_id]
    if not matching:
        return None
    return sorted(matching, key=lambda row: row.get("act_id", ""))[-1]


def _table(connection: sqlite3.Connection, table_name: str) -> list[dict[str, str]]:
    try:
        return fetch_table(connection, table_name)
    except sqlite3.OperationalError:
        return []


def _territory_income_per_hour(territory: dict[str, Any]) -> int:
    income_by_tier = {1: 8, 2: 14, 3: 22}
    return income_by_tier.get(_int_value(territory.get("tier")), 0)


def _active_stack_count(rows: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        if not row.get("hidden")
        and str(row.get("status") or "active") == "active"
        and _int_value(row.get("count")) > 0
    )


def _timer_summary(connection: sqlite3.Connection) -> dict[str, Any]:
    current_time = datetime.now(UTC)
    state_row = connection.execute(
        """
        SELECT current_act_id, status, active_started_at, updated_at
        FROM act_state
        WHERE id = 1
        """
    ).fetchone()
    applied_count = connection.execute(
        "SELECT COUNT(*) FROM applied_timer_ticks"
    ).fetchone()[0]
    last_tick_row = connection.execute(
        """
        SELECT timer_id, act_id, effect_type, due_at, applied_at, payload_json
        FROM applied_timer_ticks
        ORDER BY applied_at DESC, timer_id DESC
        LIMIT 1
        """
    ).fetchone()
    current_act_id = state_row["current_act_id"] if state_row else None
    active_started_at = state_row["active_started_at"] if state_row else None
    next_tick = _next_timer_tick(connection, current_act_id, active_started_at, current_time)

    return {
        "server_time": current_time.isoformat(timespec="seconds"),
        "status": state_row["status"] if state_row else "not_started",
        "current_act_id": current_act_id,
        "active_started_at": active_started_at,
        "updated_at": state_row["updated_at"] if state_row else None,
        "applied_tick_count": int(applied_count),
        "last_tick": _timer_tick_payload(last_tick_row),
        "next_tick": next_tick,
    }


def _next_timer_tick(
    connection: sqlite3.Connection,
    current_act_id: object,
    active_started_at: object,
    current_time: datetime,
) -> dict[str, Any] | None:
    if not current_act_id or not active_started_at:
        return None
    act_row = connection.execute(
        """
        SELECT act_id, start_offset_min, end_offset_min
        FROM acts
        WHERE act_id = ?
        """,
        (current_act_id,),
    ).fetchone()
    if act_row is None:
        return None

    started_at = _parse_iso(str(active_started_at))
    elapsed_minutes = int((current_time - started_at).total_seconds() // 60)
    if elapsed_minutes < 0:
        elapsed_minutes = 0
    act_duration = max(
        0,
        _int_value(act_row["end_offset_min"]) - _int_value(act_row["start_offset_min"]),
    )
    timer_rows = connection.execute(
        """
        SELECT timer_id, act_id, timer_type, offset_min, interval_min, effect_type
        FROM auto_timers
        WHERE act_id = ?
        ORDER BY _row_number
        """,
        (current_act_id,),
    ).fetchall()
    candidates: list[dict[str, Any]] = []
    for timer_row in timer_rows:
        first_due = max(
            0,
            _int_value(timer_row["offset_min"]) - _int_value(act_row["start_offset_min"]),
        )
        interval = _int_value(timer_row["interval_min"])
        if str(timer_row["timer_type"]) == "one_shot" or interval <= 0:
            due_offset = first_due if elapsed_minutes < first_due else None
        elif elapsed_minutes < first_due:
            due_offset = first_due
        else:
            steps_after_first = ((elapsed_minutes - first_due) // interval) + 1
            due_offset = first_due + steps_after_first * interval

        if due_offset is None or due_offset > act_duration:
            continue

        due_at = started_at + timedelta(minutes=due_offset)
        seconds_until = max(0, int((due_at - current_time).total_seconds()))
        candidates.append(
            {
                "timer_id": timer_row["timer_id"],
                "act_id": timer_row["act_id"],
                "effect_type": timer_row["effect_type"],
                "due_at": due_at.isoformat(timespec="seconds"),
                "seconds_until": seconds_until,
                "minutes_until": seconds_until // 60,
            }
        )

    if not candidates:
        return None
    return min(candidates, key=lambda item: item["seconds_until"])


def _timer_tick_payload(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    payload = {
        "timer_id": row["timer_id"],
        "act_id": row["act_id"],
        "effect_type": row["effect_type"],
        "due_at": row["due_at"],
        "applied_at": row["applied_at"],
    }
    try:
        effect_payload = json.loads(row["payload_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        effect_payload = {}
    if isinstance(effect_payload, dict):
        payload["payload"] = effect_payload
    return payload


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _int_value(value: object) -> int:
    if value in {None, ""}:
        return 0
    return int(value)


def _coalesce(*values: object) -> str | None:
    for value in values:
        text = _optional(value)
        if text is not None:
            return text
    return None
