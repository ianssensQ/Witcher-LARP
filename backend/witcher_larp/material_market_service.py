"""Material inventory, PvE drops and market buyback pricing."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import sqlite3
from typing import Any
from uuid import uuid4

from .runtime_schema import ensure_runtime_schema, log_event


PVE_DROP_RESULTS = {"success", "partial_success", "failure", "timeout"}


class MaterialMarketError(ValueError):
    """Raised when a material market operation cannot be applied."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def ensure_material_market_runtime_state(connection: sqlite3.Connection) -> None:
    ensure_runtime_schema(connection)
    if not _table_exists(connection, "material_markets"):
        return
    timestamp = _iso()
    for row in connection.execute(
        """
        SELECT market_id, material_id, base_price, min_price, max_price,
               target_stock, trend_window
        FROM material_markets
        ORDER BY _row_number
        """
    ).fetchall():
        connection.execute(
            """
            INSERT INTO material_market_state (
                market_id, material_id, base_price, min_price, max_price,
                target_stock, trend_window, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(market_id) DO UPDATE SET
                material_id = excluded.material_id,
                base_price = excluded.base_price,
                min_price = excluded.min_price,
                max_price = excluded.max_price,
                target_stock = excluded.target_stock,
                trend_window = excluded.trend_window,
                updated_at = excluded.updated_at
            """,
            (
                row["market_id"],
                row["material_id"],
                _to_int(row["base_price"]),
                _to_int(row["min_price"]),
                _to_int(row["max_price"]),
                max(1, _to_int(row["target_stock"])),
                max(1, _to_int(row["trend_window"])),
                timestamp,
            ),
        )


def material_market_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_material_market_runtime_state(connection)
    if not _table_exists(connection, "material_market_state"):
        return []
    rows = connection.execute(
        """
        SELECT market_id, material_id, base_price, min_price, max_price,
               target_stock, trend_window, updated_at
        FROM material_market_state
        ORDER BY material_id
        """
    ).fetchall()
    return [_market_payload(connection, row) for row in rows]


def material_inventory_rows(
    connection: sqlite3.Connection,
    *,
    player_id: str | None = None,
) -> list[dict[str, Any]]:
    ensure_runtime_schema(connection)
    if not _table_exists(connection, "material_inventory"):
        return []
    if player_id:
        rows = connection.execute(
            """
            SELECT inventory_id, player_id, material_id, quantity, updated_at
            FROM material_inventory
            WHERE player_id = ?
            ORDER BY material_id
            """,
            (player_id,),
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT inventory_id, player_id, material_id, quantity, updated_at
            FROM material_inventory
            ORDER BY player_id, material_id
            """
        ).fetchall()
    return [_inventory_payload(connection, row) for row in rows]


def apply_material_drop_for_pve(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    scenario_id: str,
    result: str,
    source_event_id: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_material_market_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    normalized_result = result.strip().lower()
    if normalized_result not in PVE_DROP_RESULTS:
        return {"status": "not_applied", "reason": "unsupported_result"}

    existing = connection.execute(
        """
        SELECT drop_id, source_event_id, player_id, scenario_id, material_id,
               quantity, rule_id, result, created_at
        FROM material_drop_log
        WHERE source_event_id = ?
        """,
        (source_event_id,),
    ).fetchone()
    if existing is not None:
        return {
            "status": "duplicate",
            "drop": _clean_row(existing),
            "market": _market_payload_for_material(connection, str(existing["material_id"])),
        }

    scenario = _fetch_optional(connection, "pve_scenarios", "scenario_id", scenario_id)
    if scenario is None:
        return {"status": "not_applied", "reason": "unknown_scenario"}
    rule = _choose_drop_rule(
        connection,
        player_id=player_id,
        scenario_id=scenario_id,
        scene_type=str(scenario["scene_type"]),
        tier=_to_int(scenario["tier"]),
        result=normalized_result,
        source_event_id=source_event_id,
    )
    if rule is None:
        return {"status": "not_applied", "reason": "no_matching_rule"}

    min_quantity = _to_int(rule["min_quantity"])
    max_quantity = _to_int(rule["max_quantity"])
    quantity = _deterministic_quantity(
        player_id=player_id,
        scenario_id=scenario_id,
        rule_id=str(rule["rule_id"]),
        result=normalized_result,
        source_event_id=source_event_id,
        min_quantity=min_quantity,
        max_quantity=max_quantity,
    )
    material_id = str(rule["material_id"])
    _add_material_inventory(
        connection,
        player_id=player_id,
        material_id=material_id,
        quantity=quantity,
        now=current_time,
    )
    drop_id = f"drop_pve_{source_event_id}"
    connection.execute(
        """
        INSERT INTO material_drop_log (
            drop_id, source_event_id, player_id, scenario_id, material_id,
            quantity, rule_id, result, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            drop_id,
            source_event_id,
            player_id,
            scenario_id,
            material_id,
            quantity,
            rule["rule_id"],
            normalized_result,
            _iso(current_time),
        ),
    )
    payload = {
        "status": "applied",
        "drop": {
            "drop_id": drop_id,
            "source_event_id": source_event_id,
            "player_id": player_id,
            "scenario_id": scenario_id,
            "material_id": material_id,
            "quantity": quantity,
            "rule_id": rule["rule_id"],
            "result": normalized_result,
            "created_at": _iso(current_time),
        },
        "inventory": _inventory_payload_for_material(connection, player_id, material_id),
        "market": _market_payload_for_material(connection, material_id),
    }
    log_event(
        connection,
        "material_drop_applied",
        payload,
        source="pve_runtime",
        created_at=current_time,
    )
    return payload


def sell_material_to_market(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    material_id: str,
    quantity: int,
    sale_id: str | None = None,
    source: str = "ios_player_app",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_material_market_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    normalized_quantity = int(quantity)
    if normalized_quantity <= 0:
        raise MaterialMarketError("invalid_quantity", "Material sale quantity must be positive.")
    if _fetch_optional(connection, "materials", "material_id", material_id) is None:
        raise MaterialMarketError("unknown_material", f"Unknown material: {material_id}.", 404)
    market_before = _market_payload_for_material(connection, material_id)
    if market_before is None:
        raise MaterialMarketError("market_unavailable", f"No market for material: {material_id}.", 404)
    inventory = _inventory_row(connection, player_id, material_id)
    available = _to_int(inventory["quantity"]) if inventory is not None else 0
    if available < normalized_quantity:
        raise MaterialMarketError(
            "insufficient_material",
            f"Not enough {material_id} to sell: {available} available.",
            409,
        )

    runtime_player = _ensure_player_runtime_state(connection, player_id, now=current_time)
    unit_price = _to_int(market_before["current_price"])
    total_gold = unit_price * normalized_quantity
    connection.execute(
        """
        UPDATE material_inventory
        SET quantity = quantity - ?,
            updated_at = ?
        WHERE player_id = ? AND material_id = ?
        """,
        (normalized_quantity, _iso(current_time), player_id, material_id),
    )
    connection.execute(
        """
        UPDATE player_runtime_state
        SET gold = gold + ?,
            updated_at = ?
        WHERE player_id = ?
        """,
        (total_gold, _iso(current_time), player_id),
    )
    normalized_sale_id = sale_id or f"sale_{uuid4().hex}"
    connection.execute(
        """
        INSERT INTO material_market_sales (
            sale_id, player_id, material_id, quantity, unit_price,
            total_gold, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            normalized_sale_id,
            player_id,
            material_id,
            normalized_quantity,
            unit_price,
            total_gold,
            source,
            _iso(current_time),
        ),
    )
    payload = {
        "sale_id": normalized_sale_id,
        "player_id": player_id,
        "material_id": material_id,
        "quantity": normalized_quantity,
        "unit_price": unit_price,
        "total_gold": total_gold,
        "gold_before": _to_int(runtime_player["gold"]),
        "gold_after": _to_int(runtime_player["gold"]) + total_gold,
        "inventory": _inventory_payload_for_material(connection, player_id, material_id),
        "market_before": market_before,
        "market": _market_payload_for_material(connection, material_id),
    }
    log_event(
        connection,
        "material_market_sale",
        payload,
        source=source,
        created_at=current_time,
    )
    return payload


def _choose_drop_rule(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    scenario_id: str,
    scene_type: str,
    tier: int,
    result: str,
    source_event_id: int,
) -> sqlite3.Row | None:
    if not _table_exists(connection, "material_drop_rules"):
        return None
    candidates = []
    for row in connection.execute(
        """
        SELECT rule_id, material_id, scene_type, tier, weight, min_quantity,
               max_quantity, result_filter
        FROM material_drop_rules
        WHERE tier = ?
        ORDER BY _row_number
        """,
        (str(tier),),
    ).fetchall():
        row_scene_type = str(row["scene_type"])
        if row_scene_type not in {"any", scene_type}:
            continue
        if not _drop_result_matches(str(row["result_filter"]), result):
            continue
        candidates.append(row)
    if not candidates:
        return None
    total_weight = sum(max(0, _to_int(row["weight"])) for row in candidates)
    if total_weight <= 0:
        return None
    roll = _hash_int(f"drop:{player_id}:{scenario_id}:{result}:{source_event_id}") % total_weight
    cursor = 0
    for row in candidates:
        cursor += max(0, _to_int(row["weight"]))
        if roll < cursor:
            return row
    return candidates[-1]


def _drop_result_matches(filter_value: str, result: str) -> bool:
    if filter_value == "any":
        return True
    if filter_value == "success_or_partial":
        return result in {"success", "partial_success"}
    if filter_value == "success":
        return result == "success"
    return False


def _deterministic_quantity(
    *,
    player_id: str,
    scenario_id: str,
    rule_id: str,
    result: str,
    source_event_id: int,
    min_quantity: int,
    max_quantity: int,
) -> int:
    if max_quantity <= min_quantity:
        return min_quantity
    span = max_quantity - min_quantity + 1
    roll = _hash_int(f"quantity:{player_id}:{scenario_id}:{rule_id}:{result}:{source_event_id}")
    return min_quantity + (roll % span)


def _add_material_inventory(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    material_id: str,
    quantity: int,
    now: datetime,
) -> None:
    _ensure_player_runtime_state(connection, player_id, now=now)
    timestamp = _iso(now)
    connection.execute(
        """
        INSERT INTO material_inventory (
            inventory_id, player_id, material_id, quantity, updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(player_id, material_id) DO UPDATE SET
            quantity = material_inventory.quantity + excluded.quantity,
            updated_at = excluded.updated_at
        """,
        (
            f"matinv_{player_id}_{material_id}",
            player_id,
            material_id,
            quantity,
            timestamp,
        ),
    )


def _ensure_player_runtime_state(
    connection: sqlite3.Connection,
    player_id: str,
    *,
    now: datetime,
) -> dict[str, Any]:
    ensure_runtime_schema(connection)
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

    player = _fetch_optional(connection, "players", "player_id", player_id)
    if player is None:
        raise MaterialMarketError("unknown_player", f"Unknown player: {player_id}.", 404)
    connection.execute(
        """
        INSERT INTO player_runtime_state (
            player_id, role_type, level, xp, gold, stats_json,
            unspent_stat_points, mana, max_mana, challenge_tokens, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?)
        ON CONFLICT(player_id) DO NOTHING
        """,
        (
            player_id,
            player["role_type"],
            _to_int(player["level"]),
            _to_int(player["xp"]),
            _to_int(player["gold"]),
            player["stats_json"],
            _iso(now),
        ),
    )
    return {
        "player_id": player_id,
        "role_type": str(player["role_type"]),
        "level": _to_int(player["level"]),
        "xp": _to_int(player["xp"]),
        "gold": _to_int(player["gold"]),
        "stats_json": str(player["stats_json"]),
        "unspent_stat_points": 0,
    }


def _market_payload_for_material(
    connection: sqlite3.Connection,
    material_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT market_id, material_id, base_price, min_price, max_price,
               target_stock, trend_window, updated_at
        FROM material_market_state
        WHERE material_id = ?
        LIMIT 1
        """,
        (material_id,),
    ).fetchone()
    return _market_payload(connection, row) if row is not None else None


def _market_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    material = _fetch_optional(connection, "materials", "material_id", str(row["material_id"]))
    total_quantity = _total_player_quantity(connection, str(row["material_id"]))
    base_price = _to_int(row["base_price"])
    min_price = _to_int(row["min_price"])
    max_price = _to_int(row["max_price"])
    target_stock = max(1, _to_int(row["target_stock"]))
    current_price = _current_price(
        total_quantity=total_quantity,
        target_stock=target_stock,
        base_price=base_price,
        min_price=min_price,
        max_price=max_price,
    )
    trend = "balanced"
    if current_price > base_price:
        trend = "scarce"
    elif current_price < base_price:
        trend = "surplus"
    return {
        "market_id": row["market_id"],
        "material_id": row["material_id"],
        "display_name": material["display_name"] if material is not None else row["material_id"],
        "rarity": material["rarity"] if material is not None else "",
        "category": material["category"] if material is not None else "",
        "description": material["description"] if material is not None else "",
        "base_price": base_price,
        "min_price": min_price,
        "max_price": max_price,
        "target_stock": target_stock,
        "trend_window": _to_int(row["trend_window"]),
        "total_player_quantity": total_quantity,
        "current_price": current_price,
        "trend": trend,
        "updated_at": row["updated_at"],
    }


def _current_price(
    *,
    total_quantity: int,
    target_stock: int,
    base_price: int,
    min_price: int,
    max_price: int,
) -> int:
    if total_quantity <= target_stock:
        scarcity_ratio = (target_stock - total_quantity) / target_stock
        price = base_price + round(scarcity_ratio * (max_price - base_price))
    else:
        surplus_ratio = min(total_quantity - target_stock, target_stock) / target_stock
        price = base_price - round(surplus_ratio * (base_price - min_price))
    return max(min_price, min(max_price, int(price)))


def _inventory_payload_for_material(
    connection: sqlite3.Connection,
    player_id: str,
    material_id: str,
) -> dict[str, Any]:
    row = _inventory_row(connection, player_id, material_id)
    if row is None:
        material = _fetch_optional(connection, "materials", "material_id", material_id)
        return {
            "inventory_id": f"matinv_{player_id}_{material_id}",
            "player_id": player_id,
            "material_id": material_id,
            "display_name": material["display_name"] if material is not None else material_id,
            "rarity": material["rarity"] if material is not None else "",
            "category": material["category"] if material is not None else "",
            "description": material["description"] if material is not None else "",
            "quantity": 0,
            "updated_at": "",
        }
    return _inventory_payload(connection, row)


def _inventory_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    material = _fetch_optional(connection, "materials", "material_id", str(row["material_id"]))
    return {
        "inventory_id": row["inventory_id"],
        "player_id": row["player_id"],
        "material_id": row["material_id"],
        "display_name": material["display_name"] if material is not None else row["material_id"],
        "rarity": material["rarity"] if material is not None else "",
        "category": material["category"] if material is not None else "",
        "description": material["description"] if material is not None else "",
        "quantity": _to_int(row["quantity"]),
        "updated_at": row["updated_at"],
    }


def _inventory_row(
    connection: sqlite3.Connection,
    player_id: str,
    material_id: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT inventory_id, player_id, material_id, quantity, updated_at
        FROM material_inventory
        WHERE player_id = ? AND material_id = ?
        """,
        (player_id, material_id),
    ).fetchone()


def _total_player_quantity(connection: sqlite3.Connection, material_id: str) -> int:
    row = connection.execute(
        """
        SELECT COALESCE(SUM(quantity), 0) AS total_quantity
        FROM material_inventory
        WHERE material_id = ?
        """,
        (material_id,),
    ).fetchone()
    return _to_int(row["total_quantity"] if row is not None else 0)


def _fetch_optional(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    value: str,
) -> sqlite3.Row | None:
    if not _table_exists(connection, table_name):
        return None
    return connection.execute(
        f'SELECT * FROM "{table_name}" WHERE "{column_name}" = ? LIMIT 1',
        (value,),
    ).fetchone()


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


def _hash_int(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def _clean_row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")
