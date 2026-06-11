"""Read-only auth and state helpers for the lord browser frontend."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import lru_cache
import json
from pathlib import Path
from typing import Any
import sqlite3

from pydantic import BaseModel, Field

from .building_effects import ADDRESSED_ORDER_BUILDING_ID
from .building_effects import ADDRESSED_ORDER_LIMIT_WITH_BUILDING
from .building_effects import PUBLIC_ORDER_BUILDING_ID
from .building_effects import PUBLIC_ORDER_LIMIT_WITH_BUILDING
from .building_effects import building_effect_labels
from .lord_runtime import ACTIVE_ORDER_STATUSES
from .lord_runtime import active_pending_lord_move, build_lord_map_intel
from .lord_runtime import anti_snowball_cut_for_domain, build_diplomacy_signals
from .lord_runtime import ensure_lord_runtime_state, reconcile_pending_lord_moves
from .lord_runtime import raid_order_public_cap_penalty_for_domain
from .lord_runtime import raid_defense_summary, raid_income_multiplier_for_territory
from .lord_runtime import raid_recruit_blocked_for_territory
from .lord_runtime import raid_token_surcharge_for_domain
from .lord_runtime import recruit_growth_per_hour_for_unit_class
from .lord_battle_service import list_lord_battles
from .repository import fetch_table, latest_snapshot_version

LORD_MAP_LAYOUT_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "seed"
    / "lord_map_layout.json"
)

PUBLIC_ORDER_LIMIT = PUBLIC_ORDER_LIMIT_WITH_BUILDING
ADDRESSED_ORDER_LIMIT = ADDRESSED_ORDER_LIMIT_WITH_BUILDING

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
    garrisons_by_territory = _garrisons_by_territory(connection)
    forts_by_territory = _territory_forts_by_territory(connection)

    owned_territories = [
        _territory_payload(
            connection,
            territory,
            territory_runtime,
            map_nodes,
            pending_rewards,
            garrisons_by_territory,
            forts_by_territory,
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
            garrisons_by_territory,
            forts_by_territory,
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
            garrisons_by_territory,
            forts_by_territory,
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
        raid_token_surcharge=raid_token_surcharge_for_domain(connection, domain_id),
    )
    raid_targets = _raid_target_payloads(
        connection,
        [
            *owned_territories,
            *neutral_territories,
            *other_territories,
        ],
        raid_effects=raid_effects,
        viewer_domain_id=domain_id,
        domains=domains,
        owned_buildings=owned_buildings,
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
    all_territories = [
        *owned_territories,
        *neutral_territories,
        *other_territories,
    ]
    battles = list_lord_battles(
        connection,
        domain_id=domain_id,
        viewer_domain_id=domain_id,
        viewer_role_type="lord",
    )["items"]
    claims = _visible_claims(connection, domain_id)
    pending_domain_rewards = [
        reward
        for reward in pending_rewards
        if reward.get("domain_id") == domain_id or reward.get("territory_id") in owned_ids
    ]
    anti_snowball = anti_snowball_cut_for_domain(connection, domain_id)
    territory_income = sum(
        _territory_income_per_hour(connection, territory) for territory in owned_territories
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
    building_catalog_payload = _building_catalog_payload(
        connection, building_catalog, owned_buildings
    )
    territory_views = _territory_view_payloads(
        connection,
        all_territories,
        domain_id=domain_id,
        domains=domains,
        domain_payload=domain_payload,
        map_nodes=map_nodes,
        active_army=active_army,
        recruit_market=recruit_market,
        building_catalog=building_catalog_payload,
        owned_buildings=owned_buildings,
        pending_move=pending_move,
    )
    active_army_location = _active_army_location_payload(
        active_army,
        map_nodes,
        domain_payload=domain_payload,
    )
    active_army_location["pending_move_active"] = pending_move is not None
    active_army_location["pending_move"] = pending_move
    active_battles = _active_battle_payloads(
        battles,
        domain_id=domain_id,
        domain_names=_domain_name_map(domains),
        territory_names=_territory_name_map(all_territories),
    )
    battle_alerts = _battle_alert_payloads(active_battles, claims)
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
        "resources": _lord_resource_payload(domain_payload),
        "movement": movement,
        "active_army_location": active_army_location,
        "summary": {
            "owned_territories": len(owned_territories),
            "neutral_territories": len(neutral_territories),
            "other_territories": len(other_territories),
            "active_orders": len(active_orders),
            "pending_rewards": len(pending_domain_rewards),
            "garrison_targets": len(garrison_targets),
            "active_battles": len(active_battles),
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
        "territory_views": territory_views,
        "garrison_targets": garrison_targets,
        "claims": claims,
        "battles": battles,
        "active_battles": active_battles,
        "battle_alerts": battle_alerts,
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
        "building_catalog": building_catalog_payload,
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


def build_lord_summary_state(
    connection: sqlite3.Connection, lord_id: str
) -> dict[str, Any] | None:
    """Return the small polling payload for live lord screens."""

    ensure_lord_runtime_state(connection)
    lord = _lord_by_id(connection, lord_id)
    if lord is None:
        return None

    domain = _domain_for_lord(connection, lord_id, lord.get("lord_id"))
    domain_id = domain.get("domain_id") if domain else lord.get("lord_id", "")
    reconcile_pending_lord_moves(connection, domain_id=domain_id)
    runtime_domain = _runtime_domain(connection, domain_id) or {}
    domain_payload = {**domain, **runtime_domain} if domain else runtime_domain
    pending_move = active_pending_lord_move(connection, domain_id)
    battles = _active_lord_battle_summaries(connection, domain_id)

    movement = {
        "domain_id": domain_id,
        "current_node_id": domain_payload.get("current_node_id"),
        "current_mp": _int_value(domain_payload.get("current_mp")),
        "mp_cap": _int_value(domain_payload.get("mp_cap")),
    }
    return {
        "snapshot_version": latest_snapshot_version(connection),
        "lord": _lord_payload(lord, domain_id),
        "domain": domain_payload,
        "resources": _lord_resource_payload(domain_payload),
        "movement": movement,
        "pending_move": pending_move,
        "route_options": {
            "current_node_id": domain_payload.get("current_node_id"),
            "mp_available": movement["current_mp"],
            "mp_cap": movement["mp_cap"],
            "pending_move_active": pending_move is not None,
        },
        "summary": {
            "active_battles": len(battles),
        },
        "battles": battles,
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
    interest_rows = _table(connection, "order_interest_objects")
    if interest_rows:
        map_nodes = {row.get("node_id"): row for row in _table(connection, "map_nodes")}
        pve_scenarios = {row.get("scenario_id"): row for row in _table(connection, "pve_scenarios")}
        rewards = {row.get("reward_id"): row for row in _table(connection, "rewards")}
        targets = []
        for interest in interest_rows:
            if str(interest.get("status") or "available") == "retired":
                continue
            scenario = pve_scenarios.get(interest.get("scenario_id"), {})
            reward = rewards.get(scenario.get("reward_id"), {})
            node = map_nodes.get(interest.get("location_node_id"), {})
            interest_type = str(interest.get("interest_type") or "")
            tier = _int_value(interest.get("tier") or scenario.get("tier"))
            targets.append(
                {
                    "target_id": interest.get("interest_id"),
                    "target_type": interest_type,
                    "target_type_label": _order_interest_type_label(interest_type),
                    "label": interest.get("display_name") or _humanize_identifier(interest.get("interest_id")),
                    "location_id": interest.get("location_node_id"),
                    "location_label": node.get("name") or _humanize_identifier(interest.get("location_node_id")),
                    "act_id": interest.get("act_id") or scenario.get("act_id"),
                    "tier": tier,
                    "status": interest.get("status") or "available",
                    "asset_id": interest.get("asset_id"),
                    "pve_scene_type": scenario.get("scene_type"),
                    "pve_xp": _int_value(reward.get("xp")),
                    "pve_reward_id": scenario.get("reward_id"),
                    "suggested_payment_gold": _int_value(interest.get("suggested_payment_gold")),
                    "source": "order_interest_objects",
                }
            )
        return [
            target
            for target in sorted(
                targets,
                key=lambda item: (
                    str(item.get("act_id") or ""),
                    _int_value(item.get("tier")),
                    str(item.get("target_type_label") or ""),
                    str(item.get("label") or ""),
                ),
            )
            if target.get("target_id")
        ]

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

    for card in _table(connection, "cards"):
        targets.append(
            {
                "target_id": card.get("card_id"),
                "target_type": "card",
                "target_type_label": "Карта",
                "label": _card_label(card),
                "location_label": "карта",
                "act_id": None,
                "source": "cards",
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


def _order_cap_payload(connection: sqlite3.Connection, lord_id: str) -> dict[str, Any]:
    count_statuses = _order_statuses_counting_against_cap(connection)
    domain = _row_by_id(connection, "domains", "lord_player_id", lord_id)
    domain_id = str(domain.get("domain_id") or "") if domain else ""
    public_penalty = raid_order_public_cap_penalty_for_domain(connection, domain_id) if domain_id else 0
    public_unlocked = _domain_has_building(connection, domain_id, PUBLIC_ORDER_BUILDING_ID)
    addressed_unlocked = _domain_has_building(
        connection,
        domain_id,
        ADDRESSED_ORDER_BUILDING_ID,
    )
    public_limit = PUBLIC_ORDER_LIMIT if public_unlocked else 0
    public_limit = max(0, public_limit - public_penalty)
    addressed_limit = ADDRESSED_ORDER_LIMIT if addressed_unlocked else 0
    return {
        "public_active": _order_count_for_visibility(
            connection, lord_id, "public", count_statuses
        ),
        "public_limit": public_limit,
        "addressed_active": _order_count_for_visibility(
            connection, lord_id, "addressed", count_statuses
        ),
        "addressed_limit": addressed_limit,
        "raid_public_penalty": public_penalty,
        "public_unlocked": public_unlocked,
        "addressed_unlocked": addressed_unlocked,
    }


def _domain_has_building(
    connection: sqlite3.Connection,
    domain_id: str,
    building_id: str,
) -> bool:
    if not domain_id:
        return False
    try:
        row = connection.execute(
            """
            SELECT 1
            FROM domain_buildings
            WHERE domain_id = ? AND building_id = ?
            LIMIT 1
            """,
            (domain_id, building_id),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None


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


def _card_label(card: dict[str, Any]) -> str:
    name = _optional(card.get("name")) or _humanize_identifier(card.get("card_id"))
    tier = _optional(card.get("tier"))
    return f"Карта: {name}" + (f", тир {tier}" if tier else "")


def _order_interest_type_label(value: object) -> str:
    return {
        "artifact": "Артефакт",
        "card": "Карта",
        "treasure": "Сокровище",
    }.get(str(value or ""), _humanize_identifier(value))


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
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
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
    raid_token_surcharge: int = 0,
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
        base_token_cost = _int_value(row.get("token_cost"))
        token_cost = base_token_cost + max(0, raid_token_surcharge)
        gold_cost = 0
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
                "base_token_cost": base_token_cost,
                "token_cost": token_cost,
                "token_surcharge": max(0, raid_token_surcharge),
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
    connection: sqlite3.Connection,
    territories: list[dict[str, Any]],
    *,
    raid_effects: list[dict[str, Any]],
    viewer_domain_id: str,
    domains: list[dict[str, Any]],
    owned_buildings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    domain_names = {
        str(domain.get("domain_id")): str(domain.get("name") or domain.get("domain_id"))
        for domain in domains
    }
    owned_building_ids = {str(building.get("building_id")) for building in owned_buildings}
    has_map_room = "b_map_room" in owned_building_ids
    has_scrying_room = "b_scrying_room" in owned_building_ids
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
        can_target = bool(owner_domain_id and not is_owned_by_viewer and has_map_room)
        disabled_reason = ""
        if not owner_domain_id:
            disabled_reason = "Нейтральные земли рейдом не берутся"
        elif is_owned_by_viewer:
            disabled_reason = "Своя территория не цель рейда"
        elif not has_map_room:
            disabled_reason = "Нужна Картографическая для разведки цели"

        defense = (
            raid_defense_summary(
                connection,
                target_territory_id=territory_id,
                owner_domain_id=owner_domain_id,
                target_type="residence" if is_residence else "territory",
            )
            if owner_domain_id
            else {
                "raid_defense_score": 0,
                "garrison_power": 0,
                "risk_label": "нет",
                "has_wards": False,
                "active_army_present": False,
            }
        )
        if is_owned_by_viewer:
            resistance_label = "свои укрепления"
            visibility_level = "owner_full"
        elif has_scrying_room:
            resistance_label = (
                f"риск {defense['risk_label']} · защита {defense['raid_defense_score']}"
            )
            visibility_level = "scrying_exact"
        elif has_map_room:
            resistance_label = f"риск {defense['risk_label']}"
            visibility_level = "mapped_risk"
        else:
            resistance_label = "цель не разведана"
            visibility_level = "needs_map_room"

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
                "raid_resistance_label": resistance_label,
                "visibility_level": visibility_level,
                "raid_defense_score": defense["raid_defense_score"] if has_scrying_room or is_owned_by_viewer else None,
                "garrison_power": defense["garrison_power"] if has_scrying_room or is_owned_by_viewer else None,
                "risk_label": defense["risk_label"],
                "has_wards": defense["has_wards"] if has_scrying_room or is_owned_by_viewer else None,
                "active_army_present": defense["active_army_present"] if has_scrying_room or is_owned_by_viewer else None,
                "can_target": can_target,
                "disabled_reason": disabled_reason,
            }
        )
    return payloads


def _raid_effect_payload(effect: dict[str, Any]) -> dict[str, Any]:
    payload = _loads_json(effect.get("payload_json"), {})
    resistance = _int_value(payload.get("resistance"))
    loot_gold = _int_value(payload.get("loot_gold"))
    resistance_outcome = str(payload.get("resistance_outcome") or "")
    target_raid_tokens_lost = _int_value(payload.get("target_raid_tokens_lost"))
    if loot_gold:
        result_label = f"Добыча: {loot_gold} золота"
    elif target_raid_tokens_lost:
        result_label = f"Цель теряет жетон рейда: {target_raid_tokens_lost}"
    elif resistance_outcome == "blocked" or effect.get("status") == "blocked":
        result_label = "Защита сорвала рейд"
    elif resistance_outcome == "weakened":
        result_label = "Эффект ослаблен защитой"
    else:
        result_label = "Эффект наложен"
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
        "resisted": resistance_outcome in {"weakened", "blocked"} or resistance > 0,
        "blocked": resistance_outcome == "blocked" or effect.get("status") == "blocked",
        "loot_applied": loot_gold > 0,
        "loot_gold": loot_gold,
        "target_raid_tokens_lost": target_raid_tokens_lost,
        "resistance_outcome": resistance_outcome,
        "effect_multiplier": _int_value(payload.get("effect_multiplier")),
        "visibility": payload.get("visibility") or "source_target_and_masters",
        "counterplay": payload.get("counterplay") or "",
        "result_label": result_label,
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
    garrisons_by_territory: dict[str, list[dict[str, Any]]],
    forts_by_territory: dict[str, dict[str, Any]],
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
    garrisons = _visible_garrisons_for_rows(
        garrisons_by_territory.get(territory_id, []),
        viewer_domain_id,
    )
    fort = forts_by_territory.get(territory_id)
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
        "income_per_hour": _territory_income_per_hour(connection, territory),
        "fort": fort,
        "garrisons": garrisons,
        "pending_rewards": [
            row for row in pending_rewards if row.get("territory_id") == territory_id
        ],
    }


def _garrisons_by_territory(
    connection: sqlite3.Connection,
) -> dict[str, list[dict[str, Any]]]:
    try:
        rows = connection.execute(
            """
            SELECT garrison_id, territory_id, domain_id, card_id, count, status
            FROM garrison_runtime_state
            WHERE status = 'active' AND count > 0
            ORDER BY territory_id, garrison_id
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return {}

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        payload = dict(row)
        grouped.setdefault(str(payload.get("territory_id") or ""), []).append(payload)
    return grouped


def _visible_garrisons_for_rows(
    rows: list[dict[str, Any]], viewer_domain_id: str
) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for row in rows:
        if row.get("domain_id") == viewer_domain_id:
            visible.append(dict(row))
        else:
            visible.append(
                {
                    "territory_id": row.get("territory_id"),
                    "domain_id": row.get("domain_id"),
                    "status": "hidden_foreign_garrison",
                    "hidden": True,
                }
            )
    return visible


def _territory_forts_by_territory(
    connection: sqlite3.Connection,
) -> dict[str, dict[str, Any]]:
    try:
        rows = connection.execute(
            """
            SELECT fort_id, territory_id, name, theme, garrison_capacity,
                   art_prompt_id, background_asset_id, card_asset_id
            FROM territory_forts
            ORDER BY territory_id, fort_id
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return {}

    forts: dict[str, dict[str, Any]] = {}
    for row in rows:
        payload = dict(row)
        payload["garrison_capacity"] = _int_value(payload.get("garrison_capacity"))
        forts.setdefault(str(payload.get("territory_id") or ""), payload)
    return forts


BUILDING_BRANCH_LABELS = {
    "military": "Военная ветка",
    "economy": "Экономика",
    "order": "Приказы и разведка",
    "magic": "Магическая ветка",
}

BUILDING_PROPERTY_LABELS = {
    "b_mage_study": ["Магическая ветка: защита и разведка владения"],
    "b_market": ["Экономическая база: торговля и денежный рост"],
    "b_tax_office": ["Экономика: усиление сбора дохода"],
    "b_storehouse": ["Экономика: лимит накопления открытых войск"],
    "b_bank": ["Экономика: укрепляет казну дома"],
    "b_treasury_hall": ["Экономика: поздняя финансовая опора"],
    "b_notice_board": ["Приказы: публичные поручения для игроков"],
    "b_envoy_hall": ["Приказы: дипломатия и адресные поручения"],
    "b_map_room": ["Разведка: открывает стратегические цели"],
    "b_alchemy_lab": ["Магия: реагенты и подготовка защитных практик"],
    "b_scrying_room": ["Магия: видения и разведка угроз"],
    "b_wards": ["Магия: защитные обереги владений"],
    "b_ritual_chamber": ["Магия: очищение активных рейд-эффектов"],
}

UNIT_CARD_LABELS = {
    "unit_infantry_t1": "мечники",
    "unit_guard_t1": "стража",
    "unit_ranged_t1": "лучники",
    "unit_cavalry_t2": "кавалерия",
    "unit_heavy_siege_t3": "осадники",
    "unit_specialist_t3": "инженеры",
}


def _building_property_labels(building: dict[str, Any]) -> list[str]:
    building_id = str(building.get("building_id") or "")
    if building_id in BUILDING_PROPERTY_LABELS:
        return BUILDING_PROPERTY_LABELS[building_id]
    branch = str(building.get("branch") or "")
    branch_label = BUILDING_BRANCH_LABELS.get(branch, "Развитие владения")
    tier = _int_value(building.get("tier"))
    return [f"{branch_label}: здание уровня {tier}" if tier else branch_label]


def _building_catalog_payload(
    connection: sqlite3.Connection,
    rows: list[dict[str, str]],
    owned_buildings: list[dict[str, str]],
    *,
    territory_id: str | None = None,
) -> list[dict[str, Any]]:
    scoped_territory_id = str(territory_id or "")
    owned_ids = {
        str(row["building_id"])
        for row in owned_buildings
        if not scoped_territory_id
        or str(row.get("territory_id") or "") == scoped_territory_id
    }
    buildings_by_id = {str(row.get("building_id") or ""): row for row in rows}
    unlocks_by_prerequisite: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        for prerequisite_id in _split_ids(row.get("prerequisite_ids")):
            unlocks_by_prerequisite.setdefault(prerequisite_id, []).append(row)
    unit_cards_by_id = {
        str(row.get("card_id") or ""): row for row in _table(connection, "army_unit_cards")
    }

    payloads: list[dict[str, Any]] = []
    for row in rows:
        building_id = str(row.get("building_id") or "")
        prerequisite_ids = _split_ids(row.get("prerequisite_ids"))
        missing_prerequisite_ids = [
            prerequisite_id
            for prerequisite_id in prerequisite_ids
            if prerequisite_id not in owned_ids
        ]
        if building_id in owned_ids:
            status = "built" if scoped_territory_id else "owned"
        elif missing_prerequisite_ids:
            status = "locked"
        else:
            status = "available"
        effects = _building_effects_payload(
            row,
            unlocks_by_prerequisite.get(building_id, []),
            unit_cards_by_id,
        )
        payloads.append(
            {
                **row,
                "tier": _int_value(row.get("tier")),
                "gold_cost": _int_value(row.get("gold_cost")),
                "capacity_delta": _int_value(row.get("capacity_delta")),
                "raid_unlock": _bool_value(row.get("raid_unlock")),
                "raid_token_delta": _int_value(row.get("raid_token_delta")),
                "prerequisite_ids": prerequisite_ids,
                "missing_prerequisite_ids": missing_prerequisite_ids,
                "missing_prerequisites": [
                    {
                        "building_id": prerequisite_id,
                        "name": buildings_by_id.get(prerequisite_id, {}).get(
                            "name", prerequisite_id
                        ),
                    }
                    for prerequisite_id in missing_prerequisite_ids
                ],
                "status": status,
                "can_build": status == "available",
                "effects": effects,
                "effect_labels": _building_effect_labels(effects),
                "purchase_payload": {
                    "building_id": building_id,
                    "territory_id": scoped_territory_id,
                }
                if scoped_territory_id
                else {"building_id": building_id},
            }
        )
    return payloads


def _building_effects_payload(
    building: dict[str, Any],
    unlocked_buildings: list[dict[str, Any]],
    unit_cards_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    recruit_unlocks = []
    for card_id in _split_ids(building.get("recruit_unlock_ids")):
        card = unit_cards_by_id.get(card_id, {})
        recruit_unlocks.append(
            {
                "card_id": card_id,
                "unit_class": card.get("unit_class", ""),
                "tier": _int_value(card.get("tier")),
                "label": _unit_card_label(card_id, card),
            }
        )
    return {
        "building_id": str(building.get("building_id") or ""),
        "branch": str(building.get("branch") or ""),
        "properties": _building_property_labels(building),
        "unlocks": [
            {
                "building_id": str(row.get("building_id") or ""),
                "name": row.get("name") or _humanize_identifier(row.get("building_id")),
                "branch": row.get("branch") or "",
                "tier": _int_value(row.get("tier")),
            }
            for row in unlocked_buildings
        ],
        "capacity_delta": _int_value(building.get("capacity_delta")),
        "raid_unlock": _bool_value(building.get("raid_unlock")),
        "raid_token_delta": _int_value(building.get("raid_token_delta")),
        "recruit_unlocks": recruit_unlocks,
    }


def _building_effect_labels(effects: dict[str, Any]) -> list[str]:
    building_id = str(effects.get("building_id") or "")
    return building_effect_labels(building_id)


def _append_unique_labels(labels: list[str], additions: list[str]) -> None:
    seen = set(labels)
    for item in additions:
        label = str(item).strip()
        if label and label not in seen:
            labels.append(label)
            seen.add(label)


def _unit_card_label(card_id: str, card: dict[str, Any]) -> str:
    if card_id in UNIT_CARD_LABELS:
        return UNIT_CARD_LABELS[card_id]
    unit_class = str(card.get("unit_class") or _humanize_identifier(card_id))
    tier = _int_value(card.get("tier"))
    return f"{unit_class} T{tier}" if tier else unit_class


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


LOCKED_TERRITORY_HOME_STATUSES = {
    "in_battle",
    "contested",
    "contested_pending_tick",
    "capture_pending_garrison",
}

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

TERRITORY_RECRUIT_CARD_IDS = {
    "defense": ["unit_guard_t1", "unit_infantry_t1", "unit_ranged_t1", "unit_heavy_siege_t3"],
    "gold_income": ["unit_infantry_t1", "unit_ranged_t1", "unit_cavalry_t2"],
    "recruit": ["unit_infantry_t1", "unit_guard_t1", "unit_ranged_t1", "unit_cavalry_t2"],
    "order": ["unit_infantry_t1", "unit_ranged_t1", "unit_specialist_t3"],
    "magic": ["unit_specialist_t3", "unit_ranged_t1", "unit_guard_t1"],
    "resource": ["unit_infantry_t1", "unit_guard_t1", "unit_specialist_t3"],
    "research": ["unit_specialist_t3", "unit_ranged_t1"],
    "artifact": ["unit_specialist_t3", "unit_guard_t1"],
    "special": ["unit_specialist_t3", "unit_ranged_t1", "unit_guard_t1"],
    "raid_cover": ["unit_guard_t1", "unit_specialist_t3"],
    "visibility": ["unit_specialist_t3", "unit_ranged_t1"],
}


def _lord_resource_payload(domain_payload: dict[str, Any]) -> dict[str, int]:
    mp_cap = _int_value(domain_payload.get("mp_cap"))
    current_mp = min(mp_cap, _int_value(domain_payload.get("current_mp"))) if mp_cap else 0
    raid_token_cap = _int_value(domain_payload.get("raid_token_cap"))
    raid_tokens = min(raid_token_cap, _int_value(domain_payload.get("raid_tokens"))) if raid_token_cap else _int_value(domain_payload.get("raid_tokens"))
    return {
        "gold": _int_value(_coalesce(domain_payload.get("gold"), domain_payload.get("starting_gold"))),
        "income_per_hour": _int_value(domain_payload.get("income_per_hour")),
        "raw_income_per_hour": _int_value(domain_payload.get("raw_income_per_hour")),
        "territory_income_per_hour": _int_value(domain_payload.get("territory_income_per_hour")),
        "current_mp": current_mp,
        "mp_cap": mp_cap,
        "raid_tokens": raid_tokens,
        "raid_token_cap": raid_token_cap,
        "ritual_cleanse_charges": _int_value(
            domain_payload.get("ritual_cleanse_charges")
        ),
    }


def _territory_view_payloads(
    connection: sqlite3.Connection,
    territories: list[dict[str, Any]],
    *,
    domain_id: str,
    domains: list[dict[str, Any]],
    domain_payload: dict[str, Any],
    map_nodes: list[dict[str, str]],
    active_army: list[dict[str, Any]],
    recruit_market: list[dict[str, Any]],
    building_catalog: list[dict[str, Any]],
    owned_buildings: list[dict[str, Any]],
    pending_move: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    active_location = _active_army_location_payload(
        active_army,
        map_nodes,
        domain_payload=domain_payload,
    )
    active_node_id = str(active_location.get("node_id") or "")
    active_label = str(active_location.get("node_name") or "другой территории")
    active_army_has_units = _active_stack_count(active_army) > 0
    domain_names = _domain_name_map(domains)

    payloads = []
    for territory in territories:
        territory_id = str(territory.get("territory_id") or "")
        owner_domain_id = _optional(territory.get("owner_domain_id"))
        status = str(territory.get("status") or "")
        node_id = str(territory.get("node_id") or "")
        is_owned = owner_domain_id == domain_id
        is_residence = _is_residence_territory(territory)
        is_selectable = is_owned
        active_army_present = (
            is_owned
            and active_army_has_units
            and bool(active_node_id)
            and active_node_id == node_id
            and pending_move is None
            and status not in LOCKED_TERRITORY_HOME_STATUSES
        )
        lock_reasons = _territory_lock_reasons(
            connection,
            territory,
            domain_id=domain_id,
            is_owned=is_owned,
            active_army_present=active_army_present,
            pending_move=pending_move,
        )
        active_army_lock_reason = _active_army_lock_reason(
            territory,
            is_owned=is_owned,
            active_army_has_units=active_army_has_units,
            active_node_id=active_node_id,
            active_label=active_label,
            pending_move=pending_move,
        )
        select_lock_reason = _territory_select_lock_reason(
            territory,
            is_owned=is_owned,
            owner_domain_id=owner_domain_id,
        )
        fort = territory.get("fort") if isinstance(territory.get("fort"), dict) else {}
        garrisons = territory.get("garrisons") if isinstance(territory.get("garrisons"), list) else []
        recruit_stock = _territory_recruit_stock_payload(
            connection,
            territory,
            recruit_market,
            is_owned=is_owned,
            base_lock_reasons=lock_reasons,
        )
        building_tree = _territory_building_tree_payload(
            connection,
            territory,
            building_catalog,
            owned_buildings,
            is_owned=is_owned,
        )
        payloads.append(
            {
                "territory_id": territory_id,
                "name": territory.get("name") or territory.get("node_name") or _humanize_identifier(territory_id),
                "short_name": _territory_short_name(territory),
                "owner_domain_id": owner_domain_id,
                "owner": {
                    "domain_id": owner_domain_id,
                    "name": domain_names.get(owner_domain_id or "", ""),
                    "relation": "self"
                    if is_owned
                    else "foreign"
                    if owner_domain_id
                    else "neutral",
                    "status": status,
                },
                "bonus_type": territory.get("bonus_type") or "",
                "bonus_label": _bonus_label(territory.get("bonus_type")),
                "tier": _int_value(territory.get("tier")),
                "status": status,
                "node_id": node_id,
                "node_name": territory.get("node_name") or territory.get("name") or "",
                "node_type": territory.get("node_type") or "",
                "is_owned": is_owned,
                "is_selectable": is_selectable,
                "is_residence": is_residence,
                "hero_here": active_army_present,
                "lock_reasons": lock_reasons,
                "lock_reason": select_lock_reason,
                "income_per_hour": _int_value(territory.get("income_per_hour")),
                "fort": fort,
                "garrisons": garrisons,
                "garrison_stacks": garrisons,
                "recruit_stock": recruit_stock,
                "recruit_lock_reason": "" if is_owned else "Территория не под контролем дома",
                "building_tree": building_tree,
                "building_tree_status": building_tree["status"],
                "building_tree_lock_reason": building_tree["lock_reason"],
                "active_army_present": active_army_present,
                "active_army_lock_reason": active_army_lock_reason,
                "background_asset_id": (fort or {}).get("background_asset_id", ""),
                "card_asset_id": (fort or {}).get("card_asset_id", ""),
            }
        )
    return payloads


def _domain_name_map(domains: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(domain.get("domain_id")): str(domain.get("name") or domain.get("domain_id"))
        for domain in domains
    }


def _territory_name_map(territories: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(territory.get("territory_id") or ""): str(
            territory.get("name")
            or territory.get("node_name")
            or territory.get("territory_id")
            or ""
        )
        for territory in territories
    }


def _active_army_location_payload(
    active_army: list[dict[str, Any]],
    map_nodes: list[dict[str, str]],
    *,
    domain_payload: dict[str, Any],
) -> dict[str, Any]:
    node_id = str(domain_payload.get("current_node_id") or "")
    if not node_id:
        for stack in active_army:
            if str(stack.get("status") or "active") != "active":
                continue
            if _int_value(stack.get("count")) <= 0:
                continue
            node_id = str(stack.get("location_node_id") or "")
            if node_id:
                break
    node = next((row for row in map_nodes if row.get("node_id") == node_id), {})
    return {
        "node_id": node_id,
        "node_name": node.get("name", ""),
        "territory_id": node.get("territory_id", ""),
    }


def _active_army_lock_reason(
    territory: dict[str, Any],
    *,
    is_owned: bool,
    active_army_has_units: bool,
    active_node_id: str,
    active_label: str,
    pending_move: dict[str, Any] | None,
) -> str:
    if pending_move is not None:
        return "Армия в пути до прибытия"
    if not active_army_has_units:
        return "Нет активной армии героя"
    if not is_owned:
        return "Активная армия действует только в своих владениях"
    status = str(territory.get("status") or "")
    if status in LOCKED_TERRITORY_HOME_STATUSES:
        return "Спорная территория заблокирована до решения конфликта"
    node_id = str(territory.get("node_id") or "")
    if not active_node_id or active_node_id != node_id:
        return f"Герой сейчас в локации: {active_label}"
    return ""


def _territory_select_lock_reason(
    territory: dict[str, Any],
    *,
    is_owned: bool,
    owner_domain_id: str | None,
) -> str:
    if is_owned:
        return ""
    if owner_domain_id:
        return "Территория принадлежит другому дому"
    return "Нейтральная территория еще не захвачена"


def _territory_lock_reasons(
    connection: sqlite3.Connection,
    territory: dict[str, Any],
    *,
    domain_id: str,
    is_owned: bool,
    active_army_present: bool,
    pending_move: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    territory_id = str(territory.get("territory_id") or "")
    status = str(territory.get("status") or "")
    contested_by_domain_id = _optional(territory.get("contested_by_domain_id"))
    if pending_move is not None:
        reasons.append(
            _lock_reason(
                "pending_move_active",
                "Армия в пути до прибытия.",
                ["movement", "active_army", "transfer"],
            )
        )
    if not is_owned:
        reasons.append(
            _lock_reason(
                "territory_not_owned",
                "Территория не под контролем этого дома.",
                ["select", "building", "recruit", "transfer"],
            )
        )
    if status in LOCKED_TERRITORY_HOME_STATUSES or contested_by_domain_id:
        reasons.append(
            _lock_reason(
                "territory_contested",
                "Спорная территория заблокирована до решения конфликта.",
                ["building", "recruit", "transfer", "raid"],
            )
        )
    if is_owned and not active_army_present:
        reasons.append(
            _lock_reason(
                "active_army_not_here",
                "Армия героя не находится в этой территории.",
                ["active_army", "transfer"],
            )
        )
    if is_owned and raid_recruit_blocked_for_territory(connection, territory_id):
        reasons.append(
            _lock_reason(
                "recruit_blocked_by_raid",
                "Активный рейд блокирует найм в эту территорию.",
                ["recruit"],
            )
        )
    return reasons


def _lock_reason(code: str, message: str, surfaces: list[str]) -> dict[str, Any]:
    return {
        "code": code,
        "reason_code": code,
        "message": message,
        "surfaces": surfaces,
    }


def _territory_recruit_stock_payload(
    connection: sqlite3.Connection,
    territory: dict[str, Any],
    recruit_market: list[dict[str, Any]],
    *,
    is_owned: bool,
    base_lock_reasons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed_cards = _territory_recruit_card_ids(territory)
    payload = []
    territory_id = str(territory.get("territory_id") or "")
    domain_gold = 0
    if is_owned:
        owner_domain_id = _optional(territory.get("owner_domain_id"))
        if owner_domain_id:
            domain_row = _row_by_id(
                connection, "domain_runtime_state", "domain_id", owner_domain_id
            )
            domain_gold = _int_value(domain_row.get("gold") if domain_row else 0)
    visible_garrisons = (
        territory.get("garrisons") if isinstance(territory.get("garrisons"), list) else []
    )
    garrison_cards = {
        str(stack.get("card_id") or "")
        for stack in visible_garrisons
        if not stack.get("hidden") and _int_value(stack.get("count")) > 0
    }
    fort = territory.get("fort") if isinstance(territory.get("fort"), dict) else {}
    garrison_capacity = _int_value((fort or {}).get("garrison_capacity"))
    slots_used = _int_value((fort or {}).get("garrison_slots_used"))
    slots_free = _int_value((fort or {}).get("garrison_slots_free"))
    recruit_base_locks = [
        reason
        for reason in base_lock_reasons
        if "recruit" in set(reason.get("surfaces", []))
    ]
    for offer in recruit_market:
        card_id = str(offer.get("card_id") or "")
        if allowed_cards and card_id not in allowed_cards:
            continue
        lock_reasons = list(recruit_base_locks)
        current_stock = _int_value(_coalesce(offer.get("current_stock"), offer.get("stock")))
        cost = _int_value(offer.get("cost"))
        if current_stock <= 0:
            lock_reasons.append(
                _lock_reason(
                    "insufficient_stock",
                    "Нет накопленного найма для этого отряда.",
                    ["recruit"],
                )
            )
        if is_owned and card_id not in garrison_cards and slots_free <= 0:
            lock_reasons.append(
                _lock_reason(
                    "garrison_capacity_full",
                    "В гарнизоне нет свободного слота для новой пачки.",
                    ["recruit", "garrison"],
                )
            )
        affordable_by_gold = domain_gold // cost if cost > 0 else current_stock
        if is_owned and current_stock > 0 and affordable_by_gold < 1:
            lock_reasons.append(
                _lock_reason(
                    "insufficient_gold",
                    "Недостаточно золота для найма этого отряда.",
                    ["recruit"],
                )
            )
        capacity_allows = card_id in garrison_cards or slots_free > 0
        max_purchasable = (
            min(current_stock, affordable_by_gold)
            if is_owned and capacity_allows and not recruit_base_locks
            else 0
        )
        payload.append(
            {
                "offer_id": offer.get("offer_id"),
                "card_id": card_id,
                "status": offer.get("status") or "available",
                "cost": cost,
                "cost_per_unit": cost,
                "rate_per_hour": _int_value(offer.get("rate_per_hour")),
                "current_stock": current_stock,
                "max_purchasable": max_purchasable,
                "gold_cost": cost,
                "garrison_capacity": garrison_capacity,
                "garrison_slots_used": slots_used,
                "garrison_slots_free": slots_free,
                "unit": offer.get("unit"),
                "can_recruit": not lock_reasons,
                "lock_reasons": lock_reasons,
                "purchase_payload": {
                    "action": "purchase_stock",
                    "card_id": card_id,
                    "territory_id": territory_id,
                    "quantity": 1,
                },
                "lock_reason": "" if is_owned else "Территория не под контролем дома",
            }
        )
    return payload


def _territory_building_tree_payload(
    connection: sqlite3.Connection,
    territory: dict[str, Any],
    building_catalog: list[dict[str, Any]],
    owned_buildings: list[dict[str, Any]],
    *,
    is_owned: bool,
) -> dict[str, Any]:
    territory_id = str(territory.get("territory_id") or "")
    if not _is_residence_territory(territory):
        return {
            "scope": "residence_only",
            "status": "locked",
            "territory_id": territory_id,
            "node_ids": [],
            "nodes": [],
            "lock_reason": "Здания строятся в главном замке",
        }
    visible_ids = _territory_building_ids(territory, building_catalog)
    visible_set = set(visible_ids)
    visible_rows = [
        building
        for building in building_catalog
        if not visible_set or str(building.get("building_id") or "") in visible_set
    ]
    nodes = _building_catalog_payload(
        connection,
        visible_rows,
        owned_buildings,
        territory_id=territory_id,
    )
    return {
        "scope": "residence",
        "status": "available" if is_owned else "locked",
        "territory_id": territory_id,
        "node_ids": [str(node.get("building_id")) for node in nodes if node.get("building_id")],
        "nodes": nodes,
        "lock_reason": "" if is_owned else "Строительство доступно только в своих владениях",
    }


def _territory_building_ids(
    territory: dict[str, Any],
    building_catalog: list[dict[str, Any]] | None = None,
) -> list[str]:
    if _is_residence_territory(territory):
        return []
    bonus_type = str(territory.get("bonus_type") or "")
    base_ids = TERRITORY_BUILDING_TREE_IDS.get(
        bonus_type,
        ["b_training_yard", "b_market", "b_wards"],
    )
    if not building_catalog:
        return base_ids
    buildings_by_id = {
        str(row.get("building_id") or ""): row
        for row in building_catalog
    }
    visible: set[str] = set()
    stack = list(base_ids)
    while stack:
        building_id = stack.pop()
        if building_id in visible:
            continue
        visible.add(building_id)
        building = buildings_by_id.get(building_id)
        if not building:
            continue
        stack.extend(_split_ids(building.get("prerequisite_ids")))
    return [
        str(row.get("building_id") or "")
        for row in building_catalog
        if str(row.get("building_id") or "") in visible
    ]


def _territory_recruit_card_ids(territory: dict[str, Any]) -> list[str]:
    if _is_residence_territory(territory):
        return []
    bonus_type = str(territory.get("bonus_type") or "")
    return TERRITORY_RECRUIT_CARD_IDS.get(
        bonus_type,
        ["unit_infantry_t1", "unit_guard_t1", "unit_ranged_t1"],
    )


def _is_residence_territory(territory: dict[str, Any]) -> bool:
    territory_id = str(territory.get("territory_id") or "")
    return (
        str(territory.get("bonus_type") or "") == "residence"
        or str(territory.get("node_type") or "") == "residence"
        or territory_id.startswith("territory_res_")
    )


def _territory_short_name(territory: dict[str, Any]) -> str:
    name = str(territory.get("name") or territory.get("node_name") or "")
    if not name:
        return "Земля"
    parts = name.replace("-", " ").split()
    if len(parts) == 1:
        return parts[0][:10]
    return parts[0][:8]


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


FINAL_LORD_BATTLE_STATUSES = {"finished", "needs_master_review"}


def _active_battle_payloads(
    battles: list[dict[str, Any]],
    *,
    domain_id: str,
    domain_names: dict[str, str],
    territory_names: dict[str, str],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for battle in battles:
        status = str(battle.get("status") or "")
        if status in FINAL_LORD_BATTLE_STATUSES:
            continue
        attacker_domain_id = str(battle.get("attacker_domain_id") or "")
        defender_domain_id = _optional(battle.get("defender_domain_id"))
        actor_side = (
            "attacker"
            if attacker_domain_id == domain_id
            else "defender"
            if defender_domain_id == domain_id
            else ""
        )
        opponent_domain_id = (
            defender_domain_id if actor_side == "attacker" else attacker_domain_id
        )
        active_side = str(battle.get("active_side") or "")
        can_act = bool(actor_side and active_side == actor_side)
        payloads.append(
            {
                "battle_id": battle.get("battle_id"),
                "battle_type": battle.get("battle_type"),
                "territory_id": battle.get("territory_id"),
                "territory_name": territory_names.get(
                    str(battle.get("territory_id") or ""), ""
                ),
                "claim_id": battle.get("claim_id"),
                "status": status,
                "actor_side": actor_side,
                "active_side": active_side,
                "active_stack_id": battle.get("active_stack_id"),
                "opponent_domain_id": opponent_domain_id,
                "opponent_name": domain_names.get(opponent_domain_id or "", "Neutral defense"),
                "can_act": can_act,
                "cta": {
                    "action": "open_battle",
                    "label": "Act in battle" if can_act else "View battle",
                    "battle_id": battle.get("battle_id"),
                    "territory_id": battle.get("territory_id"),
                    "territory_name": territory_names.get(
                        str(battle.get("territory_id") or ""), ""
                    ),
                },
            }
        )
    return payloads


def _battle_alert_payloads(
    active_battles: list[dict[str, Any]], claims: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for battle in active_battles:
        alerts.append(
            {
                "alert_id": f"battle:{battle.get('battle_id')}",
                "type": "active_battle",
                "severity": "danger" if battle.get("can_act") else "warning",
                "territory_id": battle.get("territory_id"),
                "territory_name": battle.get("territory_name"),
                "battle_id": battle.get("battle_id"),
                "claim_id": battle.get("claim_id"),
                "status": battle.get("status"),
                "cta": battle.get("cta"),
            }
        )
    battle_claim_ids = {
        str(battle.get("claim_id") or "") for battle in active_battles if battle.get("claim_id")
    }
    for claim in claims:
        claim_id = str(claim.get("claim_id") or "")
        if claim_id in battle_claim_ids:
            continue
        alerts.append(
            {
                "alert_id": f"claim:{claim_id}",
                "type": "claim",
                "severity": claim.get("alert_level") or "warning",
                "territory_id": claim.get("territory_id"),
                "territory_name": claim.get("territory_name"),
                "claim_id": claim_id,
                "status": claim.get("status"),
                "cta": claim.get("cta"),
            }
        )
    return alerts


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
    payloads = []
    for row in rows:
        claim = {
            **dict(row),
            "battle_required": bool(row["battle_required"]),
        }
        claim["cta"] = _claim_cta_payload(claim, domain_id)
        claim["alert_level"] = _claim_alert_level(claim)
        payloads.append(claim)
    return payloads


def _claim_cta_payload(claim: dict[str, Any], domain_id: str) -> dict[str, Any]:
    status = str(claim.get("status") or "")
    if status in {"awaiting_garrison", "capture_pending_garrison"}:
        return {
            "action": "open_garrison",
            "label": "Place garrison",
            "territory_id": claim.get("territory_id"),
            "claim_id": claim.get("claim_id"),
        }
    if claim.get("battle_required") or status in {"in_battle", "contested"}:
        return {
            "action": "open_battle",
            "label": "Open battle",
            "territory_id": claim.get("territory_id"),
            "claim_id": claim.get("claim_id"),
            "actor": "claimant"
            if claim.get("claimant_domain_id") == domain_id
            else "defender",
        }
    return {
        "action": "open_map",
        "label": "View claim",
        "territory_id": claim.get("territory_id"),
        "claim_id": claim.get("claim_id"),
    }


def _claim_alert_level(claim: dict[str, Any]) -> str:
    status = str(claim.get("status") or "")
    if status in {"in_battle", "contested", "contested_pending_tick"}:
        return "danger"
    if status in {"awaiting_garrison", "capture_pending_garrison"}:
        return "warning"
    return "info"


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


def _lord_by_id(connection: sqlite3.Connection, lord_id: str) -> dict[str, str] | None:
    try:
        row = connection.execute(
            """
            SELECT *
            FROM players
            WHERE player_id = ? AND role_type = 'lord'
            LIMIT 1
            """,
            (lord_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def _domain_for_lord(
    connection: sqlite3.Connection, lord_id: str, fallback_domain_id: object = None
) -> dict[str, str] | None:
    try:
        row = connection.execute(
            """
            SELECT *
            FROM domains
            WHERE lord_player_id = ? OR domain_id = ?
            ORDER BY _row_number
            LIMIT 1
            """,
            (lord_id, str(fallback_domain_id or "")),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


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


def _active_lord_battle_summaries(
    connection: sqlite3.Connection, domain_id: str
) -> list[dict[str, Any]]:
    try:
        rows = connection.execute(
            """
            SELECT battle_id, battle_type, territory_id, claim_id,
                   attacker_domain_id, defender_domain_id, defender_control,
                   status, round_number, active_side, active_stack_id,
                   turn_started_at, timeout_at, updated_at
            FROM lord_battles
            WHERE (attacker_domain_id = ? OR defender_domain_id = ?)
              AND status NOT IN ('finished', 'needs_master_review', 'cancelled', 'closed', 'resolved')
            ORDER BY updated_at DESC, battle_id
            """,
            (domain_id, domain_id),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(row) for row in rows]


def _table(connection: sqlite3.Connection, table_name: str) -> list[dict[str, str]]:
    try:
        return fetch_table(connection, table_name)
    except sqlite3.OperationalError:
        return []


def _territory_income_per_hour(
    connection: sqlite3.Connection, territory: dict[str, Any]
) -> int:
    income_by_tier = {1: 8, 2: 14, 3: 22}
    base_income = income_by_tier.get(_int_value(territory.get("tier")), 0)
    territory_id = str(territory.get("territory_id") or "")
    if not territory_id:
        return base_income
    multiplier = raid_income_multiplier_for_territory(connection, territory_id)
    return (base_income * multiplier) // 100


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


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _coalesce(*values: object) -> str | None:
    for value in values:
        text = _optional(value)
        if text is not None:
            return text
    return None
