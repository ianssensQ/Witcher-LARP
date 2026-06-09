"""Read-only auth and state helpers for the static lord panel shell."""

from __future__ import annotations

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
    Path(__file__).resolve().parent
    / "web"
    / "lord"
    / "assets"
    / "lord_map_layout.json"
)


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
    orders = [
        order
        for order in _runtime_rows(connection, "order_runtime_state", "order_id")
        if order.get("lord_id") == lord_id
    ]
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

    snapshot_version = latest_snapshot_version(connection)
    active_orders = [
        order for order in orders if order.get("status") in ACTIVE_ORDER_STATUSES
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
        "recruit_market": recruit_market,
        "army_reserve": army_reserve,
        "active_army": active_army,
        "owned_buildings": owned_buildings,
        "building_catalog": _building_catalog_payload(building_catalog, owned_buildings),
        "raid_effects": raid_effects,
        "map_nodes": map_nodes,
        "map_edges": map_edges,
        "lord_map_layout": _lord_map_layout(),
        "lord_map_intel": build_lord_map_intel(connection, domain_id),
        "pending_move": active_pending_lord_move(connection, domain_id),
        "diplomacy_signals": build_diplomacy_signals(connection, domain_id),
        "anti_snowball": anti_snowball_cut_for_domain(connection, domain_id),
        "action_surfaces": _action_surfaces(lord_id),
    }


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
    return {
        **territory,
        "owner_domain_id": runtime.get("owner_domain_id", territory.get("owner_domain_id", "")),
        "status": runtime.get("status", "controlled" if territory.get("owner_domain_id") else "neutral"),
        "contested_by_domain_id": runtime.get("contested_by_domain_id", ""),
        "node_id": node.get("node_id", ""),
        "node_name": node.get("name", territory["name"]),
        "node_type": node.get("node_type", ""),
        "fort": _territory_fort_payload(connection, territory_id),
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

    payload: list[dict[str, Any]] = []
    for offer in offers:
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
        payload.append(
            {
                **offer,
                "cost": _int_value(offer.get("cost")),
                "current_stock": stock,
                "stock": stock,
                "rate_per_hour": rate_per_hour,
                "unit": unit_payload,
            }
        )
    return payload


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
