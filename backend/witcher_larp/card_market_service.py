"""Gwent card shop runtime for mobile inventory market."""

from __future__ import annotations

from datetime import UTC, datetime
import sqlite3
from typing import Any
from uuid import uuid4

from .asset_service import grant_asset_ownership
from .runtime_schema import ensure_runtime_schema, log_event
from .timer_service import ensure_runtime_content_state


CARD_MARKET_RARITY_COSTS = {
    "common": 10,
    "uncommon": 18,
    "rare": 30,
    "special": 22,
}


class CardMarketError(ValueError):
    """Raised when a card market operation cannot be applied."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def card_market_rows(
    connection: sqlite3.Connection,
    *,
    player_id: str | None = None,
) -> list[dict[str, Any]]:
    ensure_runtime_schema(connection)
    ensure_runtime_content_state(connection)
    if not _table_exists(connection, "gwent_cards"):
        return []

    player_cards = _player_available_card_ids(connection, player_id) if player_id else set()
    rows = connection.execute(
        """
        SELECT card_id, faction, row, type, strength, effect, rarity, ability_tags,
               name_group, bond_group, muster_group, display_name, effect_text,
               deck_limit, source_set
        FROM gwent_cards
        ORDER BY _row_number
        """
    ).fetchall()
    offers = []
    for row in rows:
        if not _card_is_shop_eligible(row):
            continue
        card_id = str(row["card_id"])
        offers.append(
            {
                **_card_payload(row),
                "offer_id": f"card_market_{card_id}",
                "unit_cost": card_market_price(row),
                "status": "owned" if card_id in player_cards else "available",
            }
        )
    return offers


def buy_card(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    card_id: str,
    purchase_id: str | None = None,
    source: str = "card_market_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_runtime_schema(connection)
    ensure_runtime_content_state(connection)
    current_time = now or datetime.now(UTC)
    normalized_card_id = card_id.strip()
    if not normalized_card_id:
        raise CardMarketError("missing_card", "Card id is required.")

    player = _require_player(connection, player_id)
    card = _shop_card_row(connection, normalized_card_id)
    if card is None:
        raise CardMarketError("card_not_for_sale", f"Card is not available in market: {card_id}.", 404)

    unit_cost = card_market_price(card)
    gold_before = _to_int(player["gold"])
    normalized_purchase_id = purchase_id or f"card_purchase_{uuid4().hex}"
    existing = _fetch_optional(
        connection,
        "card_market_purchases",
        "purchase_id",
        normalized_purchase_id,
    )
    if existing is not None:
        ownership = _card_ownership(connection, player_id, normalized_card_id)
        return {
            "purchase_id": normalized_purchase_id,
            "player_id": player_id,
            "card_id": normalized_card_id,
            "unit_cost": _to_int(existing["unit_cost"]),
            "gold_before": gold_before,
            "gold_after": gold_before,
            "ownership": ownership,
            "duplicate": True,
        }

    existing_cards = _player_available_card_ids(connection, player_id)
    if normalized_card_id in existing_cards:
        raise CardMarketError("card_already_owned", "Player already has this card.", 409)
    if gold_before < unit_cost:
        raise CardMarketError("insufficient_gold", "Not enough gold to buy this card.", 409)

    timestamp = _iso(current_time)
    connection.execute(
        """
        UPDATE player_runtime_state
        SET gold = gold - ?, updated_at = ?
        WHERE player_id = ?
        """,
        (unit_cost, timestamp, player_id),
    )
    connection.execute(
        """
        INSERT INTO card_market_purchases (
            purchase_id, player_id, card_id, unit_cost, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (normalized_purchase_id, player_id, normalized_card_id, unit_cost, source, timestamp),
    )
    ownership = grant_asset_ownership(
        connection,
        owner_player_id=player_id,
        asset_type="card",
        asset_id=normalized_card_id,
        quantity=1,
        source="card_market",
        source_ref_id=normalized_purchase_id,
        now=current_time,
    )
    payload = {
        "purchase_id": normalized_purchase_id,
        "player_id": player_id,
        "card_id": normalized_card_id,
        "unit_cost": unit_cost,
        "gold_before": gold_before,
        "gold_after": gold_before - unit_cost,
        "ownership": ownership,
        "duplicate": False,
    }
    log_event(connection, "card_market_purchase", payload, source=source, created_at=current_time)
    return payload


def card_market_price(row: sqlite3.Row | dict[str, Any]) -> int:
    rarity = str(row["rarity"]).strip().lower()
    base = CARD_MARKET_RARITY_COSTS.get(rarity, CARD_MARKET_RARITY_COSTS["common"])
    strength = max(0, _to_int(row["strength"]))
    type_value = str(row["type"]).strip().lower()
    row_value = str(row["row"]).strip().lower()
    special_surcharge = 4 if type_value == "special" or row_value in {"special", "weather"} else 0
    return base + min(strength, 10) * 2 + special_surcharge


def _shop_card_row(connection: sqlite3.Connection, card_id: str) -> sqlite3.Row | None:
    if not _table_exists(connection, "gwent_cards"):
        return None
    row = connection.execute(
        """
        SELECT card_id, faction, row, type, strength, effect, rarity, ability_tags,
               name_group, bond_group, muster_group, display_name, effect_text,
               deck_limit, source_set
        FROM gwent_cards
        WHERE card_id = ?
        LIMIT 1
        """,
        (card_id,),
    ).fetchone()
    if row is None or not _card_is_shop_eligible(row):
        return None
    return row


def _card_is_shop_eligible(row: sqlite3.Row) -> bool:
    type_value = str(row["type"]).strip().lower()
    row_value = str(row["row"]).strip().lower()
    rarity = str(row["rarity"]).strip().lower()
    effect = str(row["effect"]).strip().lower()
    ability_tags = {tag.lower() for tag in _split_ids(str(row["ability_tags"]))}
    if type_value == "leader" or row_value == "leader":
        return False
    if rarity in {"leader", "hero", "legendary"}:
        return False
    if effect == "hero" or "hero" in ability_tags:
        return False
    return type_value in {"unit", "special"}


def _player_available_card_ids(connection: sqlite3.Connection, player_id: str | None) -> set[str]:
    if not player_id:
        return set()
    available: set[str] = set()
    if _table_exists(connection, "gwent_decks"):
        for row in connection.execute(
            """
            SELECT leader_card_id, card_ids
            FROM gwent_decks
            WHERE player_id = ?
            """,
            (player_id,),
        ).fetchall():
            available.add(str(row["leader_card_id"]))
            available.update(_split_ids(str(row["card_ids"])))
    if _table_exists(connection, "gwent_deck_runtime"):
        for row in connection.execute(
            """
            SELECT leader_card_id, card_ids
            FROM gwent_deck_runtime
            WHERE player_id = ? AND status = 'active'
            """,
            (player_id,),
        ).fetchall():
            available.add(str(row["leader_card_id"]))
            available.update(_split_ids(str(row["card_ids"])))
    if _table_exists(connection, "asset_ownership"):
        for row in connection.execute(
            """
            SELECT asset_id
            FROM asset_ownership
            WHERE owner_player_id = ?
              AND asset_type = 'card'
              AND status = 'active'
              AND quantity > 0
            """,
            (player_id,),
        ).fetchall():
            available.add(str(row["asset_id"]))
    return {card_id for card_id in available if card_id}


def _require_player(connection: sqlite3.Connection, player_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT player_id, role_type, gold
        FROM player_runtime_state
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if row is None:
        raise CardMarketError("unknown_player", f"Unknown player: {player_id}.", 404)
    return row


def _card_ownership(
    connection: sqlite3.Connection,
    player_id: str,
    card_id: str,
) -> dict[str, Any] | None:
    if not _table_exists(connection, "asset_ownership"):
        return None
    row = connection.execute(
        """
        SELECT ownership_id, owner_player_id, asset_type, asset_id, quantity,
               status, source, source_ref_id, created_at, updated_at
        FROM asset_ownership
        WHERE owner_player_id = ?
          AND asset_type = 'card'
          AND asset_id = ?
          AND status = 'active'
        LIMIT 1
        """,
        (player_id, card_id),
    ).fetchone()
    return _row_payload(row) if row is not None else None


def _card_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "card_id": row["card_id"],
        "faction": row["faction"],
        "row": row["row"],
        "type": row["type"],
        "strength": _to_int(row["strength"]),
        "effect": row["effect"],
        "rarity": row["rarity"],
        "ability_tags": row["ability_tags"],
        "name_group": row["name_group"],
        "bond_group": row["bond_group"],
        "muster_group": row["muster_group"],
        "display_name": row["display_name"],
        "effect_text": row["effect_text"],
        "deck_limit": _to_int(row["deck_limit"], default=1),
        "source_set": row["source_set"],
    }


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
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _row_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _split_ids(value: str) -> list[str]:
    return [
        item.strip()
        for chunk in value.replace(";", ",").split(",")
        for item in [chunk.strip()]
        if item
    ]


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")
