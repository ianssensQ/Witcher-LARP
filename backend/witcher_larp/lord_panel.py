"""Read-only auth and state helpers for the static lord panel shell."""

from __future__ import annotations

from typing import Any
import sqlite3

from pydantic import BaseModel, Field

from .lord_runtime import ACTIVE_ORDER_STATUSES
from .lord_runtime import anti_snowball_cut_for_domain, build_diplomacy_signals
from .lord_runtime import ensure_lord_runtime_state, visible_garrisons_for
from .repository import fetch_table, latest_snapshot_version


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
    orders = [
        order
        for order in _runtime_rows(connection, "order_runtime_state", "order_id")
        if order.get("lord_id") == lord_id
    ]
    recruit_market = [
        offer
        for offer in _runtime_rows(connection, "recruit_offer_runtime", "offer_id")
        if offer.get("domain_id") == domain_id
    ]
    army_reserve = [
        reserve
        for reserve in _runtime_rows(connection, "army_reserve_runtime", "reserve_id")
        if reserve.get("domain_id") == domain_id
    ]
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

    snapshot_version = latest_snapshot_version(connection)
    active_orders = [
        order for order in orders if order.get("status") in ACTIVE_ORDER_STATUSES
    ]
    owned_ids = {item["territory_id"] for item in owned_territories}
    pending_domain_rewards = [
        reward
        for reward in pending_rewards
        if reward.get("domain_id") == domain_id or reward.get("territory_id") in owned_ids
    ]

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
            "available_recruits": sum(
                1 for offer in recruit_market if offer.get("status") == "available"
            ),
            "owned_buildings": len(owned_buildings),
            "active_raids": sum(1 for raid in raid_effects if raid.get("status") == "active"),
        },
        "territories": owned_territories,
        "neutral_territories": neutral_territories,
        "other_territories": other_territories,
        "orders": orders,
        "recruit_market": recruit_market,
        "army_reserve": army_reserve,
        "active_army": active_army,
        "owned_buildings": owned_buildings,
        "building_catalog": _building_catalog_payload(building_catalog, owned_buildings),
        "raid_effects": raid_effects,
        "map_edges": map_edges,
        "diplomacy_signals": build_diplomacy_signals(connection, domain_id),
        "anti_snowball": anti_snowball_cut_for_domain(connection, domain_id),
        "action_surfaces": _action_surfaces(lord_id),
    }


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
    return {
        **territory,
        "owner_domain_id": runtime.get("owner_domain_id", territory.get("owner_domain_id", "")),
        "status": runtime.get("status", "controlled" if territory.get("owner_domain_id") else "neutral"),
        "contested_by_domain_id": runtime.get("contested_by_domain_id", ""),
        "node_id": node.get("node_id", ""),
        "node_name": node.get("name", territory["name"]),
        "node_type": node.get("node_type", ""),
        "garrisons": visible_garrisons_for(connection, territory_id, viewer_domain_id),
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


def _optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _coalesce(*values: object) -> str | None:
    for value in values:
        text = _optional(value)
        if text is not None:
            return text
    return None
