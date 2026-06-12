"""Sorceress runtime: mana spells, potions, favorites and intrigue evidence."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from typing import Any
from uuid import uuid4

from .asset_service import AssetContractError
from .asset_service import active_locks_for_source, assert_asset_unlocked
from .asset_service import debit_asset_ownership, grant_asset_ownership, ownership_for_asset
from .asset_service import lock_owned_asset, settle_owned_asset_lock
from .runtime_schema import ensure_runtime_schema, log_event
from .timer_service import ensure_runtime_content_state


ACTIVE_FAVORITE_STATUSES = {"pending", "accepted"}
POTION_TRANSFER_MODES = {"gift", "sell", "exchange"}


class SorceressError(ValueError):
    """Raised when a sorceress runtime action cannot be applied."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def ensure_sorceress_runtime_state(connection: sqlite3.Connection) -> None:
    ensure_runtime_schema(connection)
    ensure_runtime_content_state(connection)
    current_time = datetime.now(UTC)
    now = _iso(current_time)

    if _table_exists(connection, "potion_markets"):
        for row in connection.execute(
            """
            SELECT market_id, seller_role, potion_id, stock, refresh_rule
            FROM potion_markets
            ORDER BY _row_number
            """
        ).fetchall():
            connection.execute(
                """
                INSERT INTO potion_market_runtime (
                    market_id, seller_role, potion_id, stock, refresh_rule, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_id) DO NOTHING
                """,
                (
                    row["market_id"],
                    row["seller_role"],
                    row["potion_id"],
                    _to_int(row["stock"]),
                    row["refresh_rule"],
                    now,
                ),
            )

    if _table_exists(connection, "trade_transfers"):
        for row in connection.execute(
            """
            SELECT transfer_id, from_player_id, to_player_id, asset_type, asset_id, status
            FROM trade_transfers
            ORDER BY _row_number
            """
        ).fetchall():
            transfer_id = str(row["transfer_id"])
            existing = _fetch_optional_row(
                connection,
                "trade_transfer_runtime",
                "transfer_id",
                transfer_id,
            )
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO trade_transfer_runtime (
                        transfer_id, from_player_id, to_player_id, asset_type, asset_id,
                        quantity, price_gold, mode, status, accepted_at, source, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 1, 0, 'seed', ?, ?, 'seed', ?, ?)
                    """,
                    (
                        transfer_id,
                        row["from_player_id"],
                        row["to_player_id"],
                        row["asset_type"],
                        row["asset_id"],
                        row["status"],
                        now if row["status"] == "accepted" else None,
                        now,
                        now,
                    ),
                )
            transfer = _fetch_required_row(
                connection,
                "trade_transfer_runtime",
                "transfer_id",
                transfer_id,
            )
            _apply_seed_trade_transfer_effects(
                connection,
                transfer,
                imported_new=existing is None,
                now=current_time,
            )

    if _table_exists(connection, "favorites"):
        rule = _favorite_rule(connection)
        for row in connection.execute(
            """
            SELECT favorite_id, sorceress_id, favored_player_id, slot, status, changed_in_act
            FROM favorites
            ORDER BY _row_number
            """
        ).fetchall():
            status = str(row["status"] or "pending")
            favorite_id = str(row["favorite_id"])
            connection.execute(
                """
                INSERT INTO favorite_runtime (
                    favorite_id, sorceress_id, favored_player_id, slot, status,
                    changed_in_act, consent_required, passive_bonus_allowed,
                    created_at, accepted_at, source, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 'seed', ?)
                ON CONFLICT(favorite_id) DO NOTHING
                """,
                (
                    favorite_id,
                    row["sorceress_id"],
                    row["favored_player_id"],
                    row["slot"],
                    status,
                    row["changed_in_act"] or _current_act_id(connection),
                    1 if rule["passive_bonus_allowed"] else 0,
                    now,
                    now if status == "accepted" else None,
                    now,
                ),
            )
            _record_favorite_history(
                connection,
                history_id=f"history_seed_{favorite_id}",
                favorite_id=favorite_id,
                sorceress_id=str(row["sorceress_id"]),
                favored_player_id=str(row["favored_player_id"]),
                slot=str(row["slot"]),
                act_id=str(row["changed_in_act"] or _current_act_id(connection)),
                action="seeded",
                passive_bonus_allowed=rule["passive_bonus_allowed"],
                source="seed",
                created_at=now,
            )


def _apply_seed_trade_transfer_effects(
    connection: sqlite3.Connection,
    transfer: sqlite3.Row,
    *,
    imported_new: bool,
    now: datetime,
) -> None:
    if str(transfer["source"]) != "seed":
        return
    transfer_id = str(transfer["transfer_id"])
    status = str(transfer["status"])
    if status == "pending_locked":
        if active_locks_for_source(
            connection,
            lock_type="trade_transfer",
            source_ref_id=transfer_id,
        ):
            return
        try:
            lock_owned_asset(
                connection,
                lock_id=f"lock_trade_{transfer_id}_{transfer['asset_type']}_{transfer['asset_id']}",
                owner_player_id=str(transfer["from_player_id"]),
                asset_type=str(transfer["asset_type"]),
                asset_id=str(transfer["asset_id"]),
                quantity=_to_int(transfer["quantity"]) or 1,
                lock_type="trade_transfer",
                source_ref_id=transfer_id,
                reason="seed pending trade transfer",
                require_existing_owner=False,
                now=now,
            )
        except AssetContractError as exc:
            timestamp = _iso(now)
            connection.execute(
                """
                UPDATE trade_transfer_runtime
                SET status = 'contested_review',
                    closed_at = ?,
                    close_reason = ?,
                    closed_by_player_id = 'seed_import',
                    updated_at = ?
                WHERE transfer_id = ?
                """,
                (timestamp, exc.message, timestamp, transfer_id),
            )
            log_event(
                connection,
                "trade_transfer_seed_lock_conflict",
                {
                    "transfer_id": transfer_id,
                    "asset_type": transfer["asset_type"],
                    "asset_id": transfer["asset_id"],
                    "from_player_id": transfer["from_player_id"],
                    "to_player_id": transfer["to_player_id"],
                    "code": exc.code,
                    "reason": exc.message,
                },
                source="seed",
                created_at=now,
            )
            return
        log_event(
            connection,
            "trade_transfer_seed_lock_created",
            _trade_transfer_payload(
                _fetch_required_row(
                    connection,
                    "trade_transfer_runtime",
                    "transfer_id",
                    transfer_id,
                )
            ),
            source="seed",
            created_at=now,
        )
        return

    if status != "accepted" or not imported_new:
        return
    if _seed_trade_effect_logged(connection, transfer_id):
        return

    asset_type = str(transfer["asset_type"])
    asset_id = str(transfer["asset_id"])
    quantity = _to_int(transfer["quantity"]) or 1
    if asset_type == "potion":
        from_inventory = _inventory_quantity(connection, str(transfer["from_player_id"]), asset_id)
        if from_inventory >= quantity:
            _take_inventory(
                connection,
                str(transfer["from_player_id"]),
                asset_id,
                quantity,
                now=_iso(now),
            )
        _add_inventory(
            connection,
            str(transfer["to_player_id"]),
            asset_id,
            quantity,
            now=_iso(now),
        )
    else:
        from_ownership = ownership_for_asset(
            connection,
            owner_player_id=str(transfer["from_player_id"]),
            asset_type=asset_type,
            asset_id=asset_id,
        )
        if _to_int(from_ownership["quantity"]) >= quantity:
            debit_asset_ownership(
                connection,
                owner_player_id=str(transfer["from_player_id"]),
                asset_type=asset_type,
                asset_id=asset_id,
                quantity=quantity,
                now=now,
            )
        grant_asset_ownership(
            connection,
            owner_player_id=str(transfer["to_player_id"]),
            asset_type=asset_type,
            asset_id=asset_id,
            quantity=quantity,
            source="seed_trade_transfer",
            source_ref_id=transfer_id,
            now=now,
        )

    log_event(
        connection,
        "trade_transfer_seed_effect_applied",
        _trade_transfer_payload(transfer),
        source="seed",
        created_at=now,
    )


def get_sorceress_state(
    connection: sqlite3.Connection, sorceress_id: str
) -> dict[str, Any]:
    ensure_sorceress_runtime_state(connection)
    player = _require_sorceress(connection, sorceress_id)
    return {
        "player": _player_payload(player),
        "spells": [_spell_payload(row) for row in _table_rows(connection, "spells")],
        "potion_markets": _potion_markets(connection),
        "potion_inventory": _inventory_for_player(connection, sorceress_id),
        "favorites": _favorites_for_sorceress(connection, sorceress_id),
        "alignment_evidence": _alignment_evidence_for_sorceress(connection, sorceress_id),
        "spell_casts": _spell_casts_for_sorceress(connection, sorceress_id),
        "locked_magical_intent": _locked_intents_for_sorceress(connection, sorceress_id),
        "rules": {"favorite": _favorite_rule(connection), "max_potions_per_scene": 1},
    }


def cast_spell(
    connection: sqlite3.Connection,
    *,
    sorceress_id: str,
    spell_id: str,
    target_id: str,
    target_type: str | None = None,
    visibility: str = "player_and_master",
    cast_id: str | None = None,
    source: str = "sorceress_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_sorceress_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    new_cast_id = cast_id or f"spell_cast_{uuid4().hex}"
    existing = _fetch_optional_row(
        connection,
        "sorceress_spell_casts",
        "cast_id",
        new_cast_id,
    )
    if existing is not None:
        return {**_spell_cast_payload(connection, existing), "duplicate": True}

    player = _require_sorceress(connection, sorceress_id)
    spell = _fetch_required_row(connection, "spells", "spell_id", spell_id)
    resolved_target_type = target_type or str(spell["target_type"])
    if resolved_target_type != str(spell["target_type"]):
        raise SorceressError(
            "spell_target_type_mismatch",
            f"Spell {spell_id} targets {spell['target_type']}, not {resolved_target_type}.",
        )
    _validate_spell_target(connection, sorceress_id, resolved_target_type, target_id)
    effect = _json_loads(str(spell["effect_json"]), {})
    cost_mana = _to_int(spell["cost_mana"])
    if _to_int(player["mana"]) < cost_mana:
        raise SorceressError("insufficient_mana", "Not enough mana to cast this spell.")

    review_reason = None
    status = "accepted"
    if _final_lock_active(connection) and _is_locked_intent_spell(spell, effect):
        status = "needs_master_review"
        review_reason = "magical intent after final lock requires master review"

    if status == "accepted":
        connection.execute(
            """
            UPDATE player_runtime_state
            SET mana = mana - ?, updated_at = ?
            WHERE player_id = ?
            """,
            (cost_mana, _iso(current_time), sorceress_id),
        )

    _insert_spell_cast(
        connection,
        cast_id=new_cast_id,
        sorceress_id=sorceress_id,
        spell_id=spell_id,
        target_type=resolved_target_type,
        target_id=target_id,
        cost_mana=cost_mana,
        effect=effect,
        counterplay=str(spell["counterplay"]),
        visibility=visibility,
        status=status,
        review_reason=review_reason,
        source=source,
        created_at=_iso(current_time),
    )

    if status == "accepted":
        _insert_magic_effect(
            connection,
            cast_id=new_cast_id,
            sorceress_id=sorceress_id,
            spell_id=spell_id,
            target_type=resolved_target_type,
            target_id=target_id,
            effect=effect,
            counterplay=str(spell["counterplay"]),
            visibility=visibility,
            status="active",
            created_at=_iso(current_time),
        )

    if _is_locked_intent_spell(spell, effect):
        _insert_locked_intent(
            connection,
            sorceress_id=sorceress_id,
            cast_id=new_cast_id,
            target_id=target_id,
            intent=effect,
            status="locked" if status == "accepted" else "needs_master_review",
            review_reason=review_reason,
            locked_at=_iso(current_time) if status == "accepted" else None,
            created_at=_iso(current_time),
        )

    payload = _spell_cast_payload(
        connection,
        _fetch_required_row(connection, "sorceress_spell_casts", "cast_id", new_cast_id),
    )
    log_event(connection, "sorceress_spell_cast", payload, source=source, created_at=current_time)
    return {**payload, "duplicate": False}


def buy_potion(
    connection: sqlite3.Connection,
    *,
    buyer_id: str,
    potion_id: str,
    quantity: int = 1,
    source: str = "sorceress_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_sorceress_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    if quantity <= 0:
        raise SorceressError("invalid_quantity", "Potion quantity must be positive.")
    buyer = _require_sorceress(connection, buyer_id)
    potion = _fetch_required_row(connection, "potions", "potion_id", potion_id)
    market = _market_for_potion(connection, potion_id)
    if str(market["seller_role"]) != "sorceress":
        raise SorceressError("invalid_market_role", "Potion wholesale market is sorceress-only.")
    if _to_int(market["stock"]) < quantity:
        raise SorceressError("market_stock_empty", "Not enough potion market stock.")

    total_cost = _to_int(potion["wholesale_cost"]) * quantity
    if _to_int(buyer["gold"]) < total_cost:
        raise SorceressError("insufficient_gold", "Not enough gold for wholesale potion buy.")

    timestamp = _iso(current_time)
    connection.execute(
        """
        UPDATE player_runtime_state
        SET gold = gold - ?, updated_at = ?
        WHERE player_id = ?
        """,
        (total_cost, timestamp, buyer_id),
    )
    connection.execute(
        """
        UPDATE potion_market_runtime
        SET stock = stock - ?, updated_at = ?
        WHERE market_id = ?
        """,
        (quantity, timestamp, market["market_id"]),
    )
    _add_inventory(connection, buyer_id, potion_id, quantity, now=timestamp)

    payload = {
        "buyer_id": buyer_id,
        "potion_id": potion_id,
        "quantity": quantity,
        "unit_cost": _to_int(potion["wholesale_cost"]),
        "total_cost": total_cost,
        "market": _market_payload(
            _fetch_required_row(connection, "potion_market_runtime", "market_id", str(market["market_id"]))
        ),
        "inventory": _inventory_item(connection, buyer_id, potion_id),
    }
    log_event(connection, "sorceress_potion_bought", payload, source=source, created_at=current_time)
    return payload


def transfer_potion(
    connection: sqlite3.Connection,
    *,
    from_player_id: str,
    to_player_id: str,
    potion_id: str,
    quantity: int = 1,
    price_gold: int = 0,
    mode: str = "gift",
    transfer_id: str | None = None,
    auto_accept: bool = False,
    source: str = "sorceress_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_sorceress_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    new_transfer_id = transfer_id or f"trade_transfer_{uuid4().hex}"
    existing = _fetch_optional_row(
        connection,
        "trade_transfer_runtime",
        "transfer_id",
        new_transfer_id,
    )
    if existing is not None:
        return {**_trade_transfer_payload(existing), "duplicate": True}
    if quantity <= 0:
        raise SorceressError("invalid_quantity", "Potion transfer quantity must be positive.")

    normalized_mode = mode.strip().lower()
    if normalized_mode not in POTION_TRANSFER_MODES:
        raise SorceressError("invalid_transfer_mode", f"Unsupported potion transfer mode: {mode}.")
    _require_sorceress(connection, from_player_id)
    to_player = _require_player(connection, to_player_id)
    potion = _fetch_required_row(connection, "potions", "potion_id", potion_id)
    _assert_potion_transfer_target(connection, from_player_id, to_player)
    _assert_potion_price(potion, quantity=quantity, price_gold=price_gold, mode=normalized_mode)
    if auto_accept and price_gold > 0:
        _assert_gold_available(connection, to_player_id, price_gold)
    try:
        assert_asset_unlocked(
            connection,
            asset_type="potion",
            asset_id=potion_id,
            owner_player_id=from_player_id,
            purpose="trade transfer",
        )
    except AssetContractError as exc:
        raise _asset_to_sorceress_error(exc) from exc

    timestamp = _iso(current_time)
    _take_inventory(connection, from_player_id, potion_id, quantity, now=timestamp)
    try:
        lock_owned_asset(
            connection,
            lock_id=f"lock_trade_{new_transfer_id}_potion_{potion_id}",
            owner_player_id=from_player_id,
            asset_type="potion",
            asset_id=potion_id,
            quantity=quantity,
            lock_type="trade_transfer",
            source_ref_id=new_transfer_id,
            reason="pending potion transfer",
            require_existing_owner=False,
            now=current_time,
        )
    except AssetContractError as exc:
        _add_inventory(connection, from_player_id, potion_id, quantity, now=timestamp)
        raise _asset_to_sorceress_error(exc) from exc
    connection.execute(
        """
        INSERT INTO trade_transfer_runtime (
            transfer_id, from_player_id, to_player_id, asset_type, asset_id,
            quantity, price_gold, mode, status, source, created_at, updated_at
        )
        VALUES (?, ?, ?, 'potion', ?, ?, ?, ?, 'pending_locked', ?, ?, ?)
        """,
        (
            new_transfer_id,
            from_player_id,
            to_player_id,
            potion_id,
            quantity,
            int(price_gold),
            normalized_mode,
            source,
            timestamp,
            timestamp,
        ),
    )
    created = _trade_transfer_payload(
        _fetch_required_row(connection, "trade_transfer_runtime", "transfer_id", new_transfer_id)
    )
    log_event(connection, "trade_transfer_requested", created, source=source, created_at=current_time)
    if auto_accept:
        return accept_trade_transfer(
            connection,
            new_transfer_id,
            accepted_by_player_id=to_player_id,
            source=source,
            now=current_time,
        )
    return {**created, "duplicate": False}


def create_trade_transfer(
    connection: sqlite3.Connection,
    *,
    from_player_id: str,
    to_player_id: str,
    asset_type: str,
    asset_id: str,
    quantity: int = 1,
    price_gold: int = 0,
    mode: str = "gift",
    transfer_id: str | None = None,
    auto_accept: bool = False,
    source: str = "trade_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_sorceress_runtime_state(connection)
    normalized_type = asset_type.strip().lower()
    if normalized_type == "potion":
        return transfer_potion(
            connection,
            from_player_id=from_player_id,
            to_player_id=to_player_id,
            potion_id=asset_id,
            quantity=quantity,
            price_gold=price_gold,
            mode=mode,
            transfer_id=transfer_id,
            auto_accept=auto_accept,
            source=source,
            now=now,
        )

    current_time = now or datetime.now(UTC)
    new_transfer_id = transfer_id or f"trade_transfer_{uuid4().hex}"
    existing = _fetch_optional_row(
        connection,
        "trade_transfer_runtime",
        "transfer_id",
        new_transfer_id,
    )
    if existing is not None:
        return {**_trade_transfer_payload(existing), "duplicate": True}
    if quantity <= 0:
        raise SorceressError("invalid_quantity", "Transfer quantity must be positive.")

    normalized_mode = mode.strip().lower()
    if normalized_mode not in POTION_TRANSFER_MODES:
        raise SorceressError("invalid_transfer_mode", f"Unsupported transfer mode: {mode}.")
    _require_player(connection, from_player_id)
    _require_player(connection, to_player_id)
    if price_gold < 0:
        raise SorceressError("invalid_price", "Transfer price cannot be negative.")
    if normalized_mode == "gift" and price_gold != 0:
        raise SorceressError("gift_price_forbidden", "Gift transfer must have zero price.")
    if auto_accept and price_gold > 0:
        _assert_gold_available(connection, to_player_id, price_gold)

    try:
        lock_owned_asset(
            connection,
            lock_id=f"lock_trade_{new_transfer_id}_{normalized_type}_{asset_id}",
            owner_player_id=from_player_id,
            asset_type=normalized_type,
            asset_id=asset_id,
            quantity=quantity,
            lock_type="trade_transfer",
            source_ref_id=new_transfer_id,
            reason="pending asset transfer",
            require_existing_owner=True,
            now=current_time,
        )
    except AssetContractError as exc:
        raise _asset_to_sorceress_error(exc) from exc

    timestamp = _iso(current_time)
    connection.execute(
        """
        INSERT INTO trade_transfer_runtime (
            transfer_id, from_player_id, to_player_id, asset_type, asset_id,
            quantity, price_gold, mode, status, source, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending_locked', ?, ?, ?)
        """,
        (
            new_transfer_id,
            from_player_id,
            to_player_id,
            normalized_type,
            asset_id,
            quantity,
            int(price_gold),
            normalized_mode,
            source,
            timestamp,
            timestamp,
        ),
    )
    created = _trade_transfer_payload(
        _fetch_required_row(connection, "trade_transfer_runtime", "transfer_id", new_transfer_id)
    )
    log_event(connection, "trade_transfer_requested", created, source=source, created_at=current_time)
    if auto_accept:
        return accept_trade_transfer(
            connection,
            new_transfer_id,
            accepted_by_player_id=to_player_id,
            source=source,
            now=current_time,
        )
    return {**created, "duplicate": False}


def accept_trade_transfer(
    connection: sqlite3.Connection,
    transfer_id: str,
    *,
    accepted_by_player_id: str,
    source: str = "trade_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_sorceress_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    transfer = _fetch_required_row(connection, "trade_transfer_runtime", "transfer_id", transfer_id)
    if str(transfer["to_player_id"]) != accepted_by_player_id:
        raise SorceressError("trade_consent_mismatch", "Only the target player can accept this transfer.")
    if str(transfer["status"]) == "accepted":
        return {**_trade_transfer_payload(transfer), "duplicate": True}
    if str(transfer["status"]) != "pending_locked":
        raise SorceressError("trade_not_pending", "Only pending locked transfers can be accepted.")

    price_gold = _to_int(transfer["price_gold"])
    if price_gold > 0:
        _assert_gold_available(connection, accepted_by_player_id, price_gold)
        timestamp = _iso(current_time)
        connection.execute(
            """
            UPDATE player_runtime_state
            SET gold = gold - ?, updated_at = ?
            WHERE player_id = ?
            """,
            (price_gold, timestamp, accepted_by_player_id),
        )
        connection.execute(
            """
            UPDATE player_runtime_state
            SET gold = gold + ?, updated_at = ?
            WHERE player_id = ?
            """,
            (price_gold, timestamp, transfer["from_player_id"]),
        )

    asset_type = str(transfer["asset_type"])
    if asset_type == "potion":
        _add_inventory(
            connection,
            str(transfer["to_player_id"]),
            str(transfer["asset_id"]),
            _to_int(transfer["quantity"]),
            now=_iso(current_time),
        )
        try:
            settle_owned_asset_lock(
                connection,
                lock_type="trade_transfer",
                source_ref_id=transfer_id,
                target_player_id=str(transfer["to_player_id"]),
                final_status="consumed",
                reason="potion transfer accepted",
                now=current_time,
            )
        except AssetContractError as exc:
            raise _asset_to_sorceress_error(exc) from exc
    else:
        try:
            if not active_locks_for_source(
                connection,
                lock_type="trade_transfer",
                source_ref_id=transfer_id,
            ):
                lock_owned_asset(
                    connection,
                    lock_id=f"lock_trade_{transfer_id}_{asset_type}_{transfer['asset_id']}",
                    owner_player_id=str(transfer["from_player_id"]),
                    asset_type=asset_type,
                    asset_id=str(transfer["asset_id"]),
                    quantity=_to_int(transfer["quantity"]) or 1,
                    lock_type="trade_transfer",
                    source_ref_id=transfer_id,
                    reason="late lock for seeded transfer",
                    require_existing_owner=True,
                    now=current_time,
                )
            settle_owned_asset_lock(
                connection,
                lock_type="trade_transfer",
                source_ref_id=transfer_id,
                target_player_id=str(transfer["to_player_id"]),
                final_status="consumed",
                reason="asset transfer accepted",
                now=current_time,
            )
        except AssetContractError as exc:
            raise _asset_to_sorceress_error(exc) from exc

    connection.execute(
        """
        UPDATE trade_transfer_runtime
        SET status = 'accepted', accepted_at = ?, updated_at = ?
        WHERE transfer_id = ?
        """,
        (_iso(current_time), _iso(current_time), transfer_id),
    )
    payload = _trade_transfer_payload(
        _fetch_required_row(connection, "trade_transfer_runtime", "transfer_id", transfer_id)
    )
    log_event(connection, "trade_transfer_accepted", payload, source=source, created_at=current_time)
    return {**payload, "duplicate": False}


def decline_trade_transfer(
    connection: sqlite3.Connection,
    transfer_id: str,
    *,
    declined_by_player_id: str,
    reason: str = "declined",
    source: str = "trade_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_sorceress_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    transfer = _fetch_required_row(connection, "trade_transfer_runtime", "transfer_id", transfer_id)
    if str(transfer["status"]) in {"declined", "cancelled", "timed_out"}:
        return {**_trade_transfer_payload(transfer), "duplicate": True}
    if str(transfer["status"]) == "accepted":
        raise SorceressError("trade_already_accepted", "Accepted transfers cannot be declined.")
    if str(transfer["status"]) != "pending_locked":
        raise SorceressError("trade_not_pending", "Only pending locked transfers can be declined.")
    if declined_by_player_id not in {str(transfer["to_player_id"]), str(transfer["from_player_id"])}:
        raise SorceressError("trade_consent_mismatch", "Only transfer participants can close this transfer.")

    terminal_status = (
        "cancelled"
        if declined_by_player_id == str(transfer["from_player_id"])
        else "declined"
    )
    if str(transfer["asset_type"]) == "potion":
        _add_inventory(
            connection,
            str(transfer["from_player_id"]),
            str(transfer["asset_id"]),
            _to_int(transfer["quantity"]),
            now=_iso(current_time),
        )
    try:
        settle_owned_asset_lock(
            connection,
            lock_type="trade_transfer",
            source_ref_id=transfer_id,
            target_player_id=None,
            final_status="released",
            reason=reason,
            now=current_time,
        )
    except AssetContractError as exc:
        raise _asset_to_sorceress_error(exc) from exc
    connection.execute(
        """
        UPDATE trade_transfer_runtime
        SET status = ?,
            closed_at = ?,
            close_reason = ?,
            closed_by_player_id = ?,
            updated_at = ?
        WHERE transfer_id = ?
        """,
        (
            terminal_status,
            _iso(current_time),
            reason,
            declined_by_player_id,
            _iso(current_time),
            transfer_id,
        ),
    )
    payload = _trade_transfer_payload(
        _fetch_required_row(connection, "trade_transfer_runtime", "transfer_id", transfer_id)
    )
    log_event(connection, "trade_transfer_declined", payload, source=source, created_at=current_time)
    return {**payload, "duplicate": False}


def use_potion_in_scene(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    potion_id: str,
    scene_id: str,
    source: str = "mobile_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_sorceress_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    _require_player(connection, player_id)
    _fetch_required_row(connection, "potions", "potion_id", potion_id)
    existing = connection.execute(
        """
        SELECT usage_id, potion_id
        FROM potion_scene_usage
        WHERE player_id = ? AND scene_id = ?
        """,
        (player_id, scene_id),
    ).fetchone()
    if existing is not None:
        raise SorceressError(
            "potion_scene_cap",
            "Only one potion can be used in a scene by default.",
        )

    timestamp = _iso(current_time)
    _take_inventory(connection, player_id, potion_id, 1, now=timestamp)
    usage_id = f"potion_use_{uuid4().hex}"
    connection.execute(
        """
        INSERT INTO potion_scene_usage (
            usage_id, player_id, potion_id, scene_id, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (usage_id, player_id, potion_id, scene_id, source, timestamp),
    )
    payload = {
        "usage_id": usage_id,
        "player_id": player_id,
        "potion_id": potion_id,
        "scene_id": scene_id,
        "max_potions_per_scene": 1,
        "inventory": _inventory_item(connection, player_id, potion_id),
    }
    log_event(connection, "potion_scene_used", payload, source=source, created_at=current_time)
    return payload


def create_favorite_request(
    connection: sqlite3.Connection,
    *,
    sorceress_id: str,
    favored_player_id: str,
    slot: str,
    favorite_id: str | None = None,
    passive_bonus_requested: bool = False,
    source: str = "favorites_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_sorceress_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    new_favorite_id = favorite_id or f"favorite_{uuid4().hex}"
    existing = _fetch_optional_row(connection, "favorite_runtime", "favorite_id", new_favorite_id)
    if existing is not None:
        return {**_favorite_payload(existing), "duplicate": True}
    rule = _favorite_rule(connection)
    if passive_bonus_requested and not rule["passive_bonus_allowed"]:
        raise SorceressError("passive_bonus_forbidden", "Favorites do not grant passive runtime bonuses.")
    _require_sorceress(connection, sorceress_id)
    _require_player(connection, favored_player_id)
    normalized_slot = _favorite_slot(slot)
    act_id = _current_act_id(connection)
    _assert_favorite_caps(
        connection,
        sorceress_id=sorceress_id,
        favored_player_id=favored_player_id,
        slot=normalized_slot,
        act_id=act_id,
        rule=rule,
    )

    timestamp = _iso(current_time)
    connection.execute(
        """
        INSERT INTO favorite_runtime (
            favorite_id, sorceress_id, favored_player_id, slot, status,
            changed_in_act, consent_required, passive_bonus_allowed,
            created_at, source, updated_at
        )
        VALUES (?, ?, ?, ?, 'pending', ?, 1, 0, ?, ?, ?)
        """,
        (
            new_favorite_id,
            sorceress_id,
            favored_player_id,
            normalized_slot,
            act_id,
            timestamp,
            source,
            timestamp,
        ),
    )
    _record_favorite_history(
        connection,
        history_id=f"history_{uuid4().hex}",
        favorite_id=new_favorite_id,
        sorceress_id=sorceress_id,
        favored_player_id=favored_player_id,
        slot=normalized_slot,
        act_id=act_id,
        action="requested",
        passive_bonus_allowed=False,
        source=source,
        created_at=timestamp,
    )
    favorite = _favorite_payload(
        _fetch_required_row(connection, "favorite_runtime", "favorite_id", new_favorite_id)
    )
    log_event(connection, "favorite_requested", favorite, source=source, created_at=current_time)
    return {**favorite, "duplicate": False}


def accept_favorite(
    connection: sqlite3.Connection,
    favorite_id: str,
    *,
    accepted_by_player_id: str,
    source: str = "favorites_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_sorceress_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    favorite = _fetch_required_row(connection, "favorite_runtime", "favorite_id", favorite_id)
    if str(favorite["favored_player_id"]) != accepted_by_player_id:
        raise SorceressError("favorite_consent_mismatch", "Only the favored player can accept.")
    if str(favorite["status"]) == "accepted":
        return {**_favorite_payload(favorite), "duplicate": True}
    if str(favorite["status"]) != "pending":
        raise SorceressError("favorite_not_pending", "Only pending favorites can be accepted.")
    rule = _favorite_rule(connection)
    accepted_count = connection.execute(
        """
        SELECT COUNT(DISTINCT sorceress_id)
        FROM favorite_runtime
        WHERE favored_player_id = ?
          AND status = 'accepted'
          AND favorite_id <> ?
        """,
        (favorite["favored_player_id"], favorite_id),
    ).fetchone()[0]
    if int(accepted_count) >= rule["max_sorceresses_per_favored"]:
        raise SorceressError(
            "favored_player_cap_exceeded",
            "Favored player already has the maximum accepted sorceresses.",
        )

    timestamp = _iso(current_time)
    connection.execute(
        """
        UPDATE favorite_runtime
        SET status = 'accepted', accepted_at = ?, updated_at = ?
        WHERE favorite_id = ?
        """,
        (timestamp, timestamp, favorite_id),
    )
    _record_favorite_history(
        connection,
        history_id=f"history_{uuid4().hex}",
        favorite_id=favorite_id,
        sorceress_id=str(favorite["sorceress_id"]),
        favored_player_id=str(favorite["favored_player_id"]),
        slot=str(favorite["slot"]),
        act_id=str(favorite["changed_in_act"]),
        action="accepted",
        passive_bonus_allowed=False,
        source=source,
        created_at=timestamp,
    )
    payload = _favorite_payload(
        _fetch_required_row(connection, "favorite_runtime", "favorite_id", favorite_id)
    )
    log_event(connection, "favorite_accepted", payload, source=source, created_at=current_time)
    return {**payload, "duplicate": False}


def record_alignment_evidence(
    connection: sqlite3.Connection,
    *,
    sorceress_id: str,
    alignment_state: str,
    evidence_type: str,
    payload: dict[str, Any] | None = None,
    visibility: str = "master_and_final_summary",
    final_flag: bool = False,
    source: str = "sorceress_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_sorceress_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    _require_sorceress(connection, sorceress_id)
    rule = _alignment_rule(connection, alignment_state)
    evidence_id = f"sorceress_evidence_{uuid4().hex}"
    timestamp = _iso(current_time)
    connection.execute(
        """
        INSERT INTO sorceress_alignment_evidence (
            evidence_id, sorceress_id, alignment_state, evidence_type,
            payload_json, visibility, final_flag, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence_id,
            sorceress_id,
            alignment_state,
            evidence_type,
            _json_dumps(payload or {}),
            visibility,
            1 if final_flag else 0,
            source,
            timestamp,
        ),
    )
    result = {
        "evidence_id": evidence_id,
        "sorceress_id": sorceress_id,
        "alignment_state": alignment_state,
        "evidence_required": rule["evidence_required"],
        "evidence_type": evidence_type,
        "payload": payload or {},
        "visibility": visibility,
        "final_flag": final_flag,
        "created_at": timestamp,
    }
    log_event(connection, "sorceress_alignment_evidence", result, source=source, created_at=current_time)
    return result


def _insert_spell_cast(
    connection: sqlite3.Connection,
    *,
    cast_id: str,
    sorceress_id: str,
    spell_id: str,
    target_type: str,
    target_id: str,
    cost_mana: int,
    effect: dict[str, Any],
    counterplay: str,
    visibility: str,
    status: str,
    review_reason: str | None,
    source: str,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO sorceress_spell_casts (
            cast_id, sorceress_id, spell_id, target_type, target_id,
            cost_mana, effect_json, counterplay, visibility, status,
            review_reason, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cast_id,
            sorceress_id,
            spell_id,
            target_type,
            target_id,
            cost_mana,
            _json_dumps(effect),
            counterplay,
            visibility,
            status,
            review_reason,
            source,
            created_at,
        ),
    )


def _insert_magic_effect(
    connection: sqlite3.Connection,
    *,
    cast_id: str,
    sorceress_id: str,
    spell_id: str,
    target_type: str,
    target_id: str,
    effect: dict[str, Any],
    counterplay: str,
    visibility: str,
    status: str,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO magic_effects (
            effect_id, cast_id, sorceress_id, spell_id, target_type, target_id,
            effect_json, counterplay, visibility, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"magic_effect_{uuid4().hex}",
            cast_id,
            sorceress_id,
            spell_id,
            target_type,
            target_id,
            _json_dumps(effect),
            counterplay,
            visibility,
            status,
            created_at,
        ),
    )


def _insert_locked_intent(
    connection: sqlite3.Connection,
    *,
    sorceress_id: str,
    cast_id: str,
    target_id: str,
    intent: dict[str, Any],
    status: str,
    review_reason: str | None,
    locked_at: str | None,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO locked_magical_intent (
            intent_id, sorceress_id, cast_id, target_id, intent_json,
            status, review_reason, locked_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"magical_intent_{uuid4().hex}",
            sorceress_id,
            cast_id,
            target_id,
            _json_dumps(intent),
            status,
            review_reason,
            locked_at,
            created_at,
        ),
    )


def _record_favorite_history(
    connection: sqlite3.Connection,
    *,
    history_id: str,
    favorite_id: str,
    sorceress_id: str,
    favored_player_id: str,
    slot: str,
    act_id: str,
    action: str,
    passive_bonus_allowed: bool,
    source: str,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO favorite_history (
            history_id, favorite_id, sorceress_id, favored_player_id, slot,
            act_id, action, passive_bonus_allowed, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(history_id) DO NOTHING
        """,
        (
            history_id,
            favorite_id,
            sorceress_id,
            favored_player_id,
            slot,
            act_id,
            action,
            1 if passive_bonus_allowed else 0,
            source,
            created_at,
        ),
    )


def _assert_favorite_caps(
    connection: sqlite3.Connection,
    *,
    sorceress_id: str,
    favored_player_id: str,
    slot: str,
    act_id: str,
    rule: dict[str, int | bool],
) -> None:
    duplicate = connection.execute(
        f"""
        SELECT favorite_id
        FROM favorite_runtime
        WHERE sorceress_id = ?
          AND favored_player_id = ?
          AND status IN ({_placeholders(ACTIVE_FAVORITE_STATUSES)})
        LIMIT 1
        """,
        (sorceress_id, favored_player_id, *sorted(ACTIVE_FAVORITE_STATUSES)),
    ).fetchone()
    if duplicate is not None:
        raise SorceressError("favorite_duplicate", "Favorite relationship is already active.")

    slot_count = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM favorite_runtime
        WHERE sorceress_id = ?
          AND slot = ?
          AND status IN ({_placeholders(ACTIVE_FAVORITE_STATUSES)})
        """,
        (sorceress_id, slot, *sorted(ACTIVE_FAVORITE_STATUSES)),
    ).fetchone()[0]
    cap = rule["max_primary"] if slot == "primary" else rule["max_secondary"]
    if int(slot_count) >= int(cap):
        raise SorceressError("favorite_slot_cap_exceeded", f"Sorceress already has an active {slot} favorite.")

    favored_count = connection.execute(
        f"""
        SELECT COUNT(DISTINCT sorceress_id)
        FROM favorite_runtime
        WHERE favored_player_id = ?
          AND status IN ({_placeholders(ACTIVE_FAVORITE_STATUSES)})
        """,
        (favored_player_id, *sorted(ACTIVE_FAVORITE_STATUSES)),
    ).fetchone()[0]
    if int(favored_count) >= int(rule["max_sorceresses_per_favored"]):
        raise SorceressError(
            "favored_player_cap_exceeded",
            "Favored player already has the maximum sorceress attention.",
        )

    change_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM favorite_runtime
        WHERE sorceress_id = ?
          AND changed_in_act = ?
        """,
        (sorceress_id, act_id),
    ).fetchone()[0]
    if int(change_count) >= int(rule["change_limit_per_act"]):
        raise SorceressError("favorite_change_limit", "Sorceress can change favorites once per act.")


def _assert_potion_transfer_target(
    connection: sqlite3.Connection, sorceress_id: str, to_player: sqlite3.Row
) -> None:
    if str(to_player["role_type"]) == "witcher":
        return
    if _accepted_favorite(connection, sorceress_id, str(to_player["player_id"])):
        return
    raise SorceressError(
        "invalid_potion_transfer_target",
        "Potions can be transferred to witchers or accepted favorites.",
    )


def _assert_potion_price(
    potion: sqlite3.Row,
    *,
    quantity: int,
    price_gold: int,
    mode: str,
) -> None:
    if price_gold < 0:
        raise SorceressError("invalid_price", "Potion transfer price cannot be negative.")
    if mode == "gift" and price_gold != 0:
        raise SorceressError("gift_price_forbidden", "Gift potion transfer must have zero price.")
    if mode == "exchange" and price_gold != 0:
        raise SorceressError("exchange_price_forbidden", "Potion exchange must not carry a gold price.")
    if mode == "sell":
        min_price = _to_int(potion["resale_min"]) * quantity
        max_price = _to_int(potion["resale_max"]) * quantity
        if price_gold < min_price or price_gold > max_price:
            raise SorceressError(
                "resale_price_out_of_band",
                f"Potion resale price must be between {min_price} and {max_price} gold.",
            )


def _validate_spell_target(
    connection: sqlite3.Connection,
    sorceress_id: str,
    target_type: str,
    target_id: str,
) -> None:
    if not target_id:
        raise SorceressError("missing_target", "Spell target_id is required.")
    if target_type == "player":
        _require_player(connection, target_id)
        return
    if target_type == "favorite":
        if not _accepted_favorite(connection, sorceress_id, target_id):
            raise SorceressError("favorite_not_accepted", "Favorite spell target requires accepted consent.")
        return
    if target_type == "lord":
        _require_player_role(connection, target_id, "lord")
        return
    if target_type == "territory":
        _fetch_required_row(connection, "territories", "territory_id", target_id)
        return
    if target_type == "order":
        if _fetch_optional_row(connection, "order_runtime_state", "order_id", target_id) is None:
            _fetch_required_row(connection, "orders", "order_id", target_id)
        return
    if target_type == "object":
        for table_name, id_column in (
            ("qr_objects", "qr_id"),
            ("items", "item_id"),
            ("artifacts", "artifact_id"),
        ):
            if _fetch_optional_row(connection, table_name, id_column, target_id) is not None:
                return
        raise SorceressError("unknown_spell_target", f"Unknown object spell target: {target_id}.")
    if target_type == "scene":
        if _fetch_optional_row(connection, "pve_scenarios", "scenario_id", target_id) is not None:
            return
        if _fetch_optional_row(connection, "qr_objects", "qr_id", target_id) is not None:
            return
        raise SorceressError("unknown_spell_target", f"Unknown scene spell target: {target_id}.")
    if target_type == "final_hook":
        _fetch_required_row(connection, "final_hooks", "final_hook_id", target_id)
        return
    if target_type == "visibility":
        return
    raise SorceressError("unsupported_spell_target", f"Unsupported spell target type: {target_type}.")


def _market_for_potion(connection: sqlite3.Connection, potion_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT *
        FROM potion_market_runtime
        WHERE potion_id = ?
        ORDER BY market_id
        LIMIT 1
        """,
        (potion_id,),
    ).fetchone()
    if row is None:
        raise SorceressError("unknown_potion_market", f"No potion market for {potion_id}.")
    return row


def _favorite_rule(connection: sqlite3.Connection) -> dict[str, int | bool]:
    row = None
    if _table_exists(connection, "favorite_rules"):
        row = connection.execute(
            """
            SELECT max_primary, max_secondary, max_sorceresses_per_favored,
                   change_limit_per_act, passive_bonus_allowed
            FROM favorite_rules
            ORDER BY _row_number
            LIMIT 1
            """
        ).fetchone()
    if row is None:
        return {
            "max_primary": 1,
            "max_secondary": 1,
            "max_sorceresses_per_favored": 2,
            "change_limit_per_act": 1,
            "passive_bonus_allowed": False,
        }
    return {
        "max_primary": _to_int(row["max_primary"]),
        "max_secondary": _to_int(row["max_secondary"]),
        "max_sorceresses_per_favored": _to_int(row["max_sorceresses_per_favored"]),
        "change_limit_per_act": _to_int(row["change_limit_per_act"]),
        "passive_bonus_allowed": _truthy(row["passive_bonus_allowed"]),
    }


def _alignment_rule(connection: sqlite3.Connection, alignment_state: str) -> dict[str, str]:
    if not _table_exists(connection, "sorceress_alignment_rules"):
        raise SorceressError("missing_alignment_rules", "No sorceress alignment rules are imported.")
    row = connection.execute(
        """
        SELECT alignment_state, evidence_required
        FROM sorceress_alignment_rules
        WHERE alignment_state = ?
        LIMIT 1
        """,
        (alignment_state,),
    ).fetchone()
    if row is None:
        raise SorceressError("unknown_alignment_state", f"Unknown sorceress alignment state: {alignment_state}.")
    return {"alignment_state": str(row["alignment_state"]), "evidence_required": str(row["evidence_required"])}


def _add_inventory(
    connection: sqlite3.Connection,
    player_id: str,
    potion_id: str,
    quantity: int,
    *,
    now: str,
) -> None:
    inventory_id = f"inventory_{player_id}_{potion_id}"
    connection.execute(
        """
        INSERT INTO potion_inventory (inventory_id, player_id, potion_id, quantity, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(player_id, potion_id) DO UPDATE SET
            quantity = potion_inventory.quantity + excluded.quantity,
            updated_at = excluded.updated_at
        """,
        (inventory_id, player_id, potion_id, quantity, now),
    )


def _take_inventory(
    connection: sqlite3.Connection,
    player_id: str,
    potion_id: str,
    quantity: int,
    *,
    now: str,
) -> None:
    cursor = connection.execute(
        """
        UPDATE potion_inventory
        SET quantity = quantity - ?, updated_at = ?
        WHERE player_id = ? AND potion_id = ? AND quantity >= ?
        """,
        (quantity, now, player_id, potion_id, quantity),
    )
    if cursor.rowcount == 0:
        raise SorceressError("insufficient_potion_inventory", "Not enough potion inventory.")


def _inventory_quantity(connection: sqlite3.Connection, player_id: str, potion_id: str) -> int:
    return _to_int(_inventory_item(connection, player_id, potion_id)["quantity"])


def _inventory_item(
    connection: sqlite3.Connection,
    player_id: str,
    potion_id: str,
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT inventory_id, player_id, potion_id, quantity, updated_at
        FROM potion_inventory
        WHERE player_id = ? AND potion_id = ?
        """,
        (player_id, potion_id),
    ).fetchone()
    if row is None:
        return {
            "inventory_id": f"inventory_{player_id}_{potion_id}",
            "player_id": player_id,
            "potion_id": potion_id,
            "quantity": 0,
            "updated_at": None,
        }
    return _clean_row(row)


def _inventory_for_player(connection: sqlite3.Connection, player_id: str) -> list[dict[str, Any]]:
    return [
        _clean_row(row)
        for row in connection.execute(
            """
            SELECT inventory_id, player_id, potion_id, quantity, updated_at
            FROM potion_inventory
            WHERE player_id = ?
            ORDER BY potion_id
            """,
            (player_id,),
        ).fetchall()
    ]


def _potion_markets(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT m.market_id, m.seller_role, m.potion_id, m.stock, m.refresh_rule,
               m.updated_at, p.rarity, p.wholesale_cost, p.resale_min, p.resale_max,
               p.effect_json
        FROM potion_market_runtime m
        LEFT JOIN potions p ON p.potion_id = m.potion_id
        ORDER BY m.market_id
        """
    ).fetchall()
    return [_market_payload(row) for row in rows]


def _market_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "market_id": row["market_id"],
        "seller_role": row["seller_role"],
        "potion_id": row["potion_id"],
        "stock": _to_int(row["stock"]),
        "refresh_rule": row["refresh_rule"],
        "updated_at": row["updated_at"],
        "rarity": row["rarity"] if "rarity" in row.keys() else None,
        "wholesale_cost": _to_int(row["wholesale_cost"]) if "wholesale_cost" in row.keys() else None,
        "resale_min": _to_int(row["resale_min"]) if "resale_min" in row.keys() else None,
        "resale_max": _to_int(row["resale_max"]) if "resale_max" in row.keys() else None,
        "effect": _json_loads(str(row["effect_json"]), {}) if "effect_json" in row.keys() else {},
    }


def _favorites_for_sorceress(connection: sqlite3.Connection, sorceress_id: str) -> list[dict[str, Any]]:
    return [
        _favorite_payload(row)
        for row in connection.execute(
            """
            SELECT *
            FROM favorite_runtime
            WHERE sorceress_id = ?
            ORDER BY created_at, favorite_id
            """,
            (sorceress_id,),
        ).fetchall()
    ]


def _spell_casts_for_sorceress(connection: sqlite3.Connection, sorceress_id: str) -> list[dict[str, Any]]:
    return [
        _spell_cast_payload(connection, row)
        for row in connection.execute(
            """
            SELECT *
            FROM sorceress_spell_casts
            WHERE sorceress_id = ?
            ORDER BY created_at, cast_id
            """,
            (sorceress_id,),
        ).fetchall()
    ]


def _alignment_evidence_for_sorceress(connection: sqlite3.Connection, sorceress_id: str) -> list[dict[str, Any]]:
    return [
        {
            **_clean_row(row),
            "payload": _json_loads(str(row["payload_json"]), {}),
            "final_flag": bool(row["final_flag"]),
        }
        for row in connection.execute(
            """
            SELECT *
            FROM sorceress_alignment_evidence
            WHERE sorceress_id = ?
            ORDER BY created_at, evidence_id
            """,
            (sorceress_id,),
        ).fetchall()
    ]


def _locked_intents_for_sorceress(connection: sqlite3.Connection, sorceress_id: str) -> list[dict[str, Any]]:
    return [
        {
            **_clean_row(row),
            "intent": _json_loads(str(row["intent_json"]), {}),
        }
        for row in connection.execute(
            """
            SELECT *
            FROM locked_magical_intent
            WHERE sorceress_id = ?
            ORDER BY created_at, intent_id
            """,
            (sorceress_id,),
        ).fetchall()
    ]


def _spell_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = _clean_row(row)
    payload["tier"] = _to_int(payload.get("tier"))
    payload["cost_mana"] = _to_int(payload.get("cost_mana"))
    payload["effect"] = _json_loads(str(payload.pop("effect_json", "{}")), {})
    return payload


def _spell_cast_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    mana = connection.execute(
        """
        SELECT mana, max_mana
        FROM player_runtime_state
        WHERE player_id = ?
        """,
        (row["sorceress_id"],),
    ).fetchone()
    return {
        "cast_id": row["cast_id"],
        "sorceress_id": row["sorceress_id"],
        "spell_id": row["spell_id"],
        "target_type": row["target_type"],
        "target_id": row["target_id"],
        "cost_mana": _to_int(row["cost_mana"]),
        "effect": _json_loads(str(row["effect_json"]), {}),
        "counterplay": row["counterplay"],
        "visibility": row["visibility"],
        "status": row["status"],
        "review_reason": row["review_reason"],
        "created_at": row["created_at"],
        "mana_after": _to_int(mana["mana"]) if mana is not None else None,
        "max_mana": _to_int(mana["max_mana"]) if mana is not None else None,
    }


def _favorite_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "favorite_id": row["favorite_id"],
        "sorceress_id": row["sorceress_id"],
        "favored_player_id": row["favored_player_id"],
        "slot": row["slot"],
        "status": row["status"],
        "changed_in_act": row["changed_in_act"],
        "consent_required": bool(row["consent_required"]),
        "passive_bonus_allowed": bool(row["passive_bonus_allowed"]),
        "created_at": row["created_at"],
        "accepted_at": row["accepted_at"],
        "ended_at": row["ended_at"],
        "source": row["source"],
        "updated_at": row["updated_at"],
        "final_summary_signal": {
            "category": "sorceress_favorites",
            "include_history": True,
            "passive_runtime_bonus": bool(row["passive_bonus_allowed"]),
        },
    }


def _trade_transfer_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = {
        "transfer_id": row["transfer_id"],
        "from_player_id": row["from_player_id"],
        "to_player_id": row["to_player_id"],
        "asset_type": row["asset_type"],
        "asset_id": row["asset_id"],
        "quantity": _to_int(row["quantity"]),
        "price_gold": _to_int(row["price_gold"]),
        "mode": row["mode"],
        "status": row["status"],
        "accepted_at": row["accepted_at"],
        "source": row["source"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    for column_name in ("closed_at", "close_reason", "closed_by_player_id"):
        if column_name in row.keys():
            payload[column_name] = row[column_name]
    return payload


def _seed_trade_effect_logged(connection: sqlite3.Connection, transfer_id: str) -> bool:
    if not _table_exists(connection, "event_log"):
        return False
    row = connection.execute(
        """
        SELECT 1
        FROM event_log
        WHERE event_type = 'trade_transfer_seed_effect_applied'
          AND payload_json LIKE ?
        LIMIT 1
        """,
        (f'%"{transfer_id}"%',),
    ).fetchone()
    return row is not None


def _player_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "player_id": row["player_id"],
        "role_type": row["role_type"],
        "level": _to_int(row["level"]),
        "xp": _to_int(row["xp"]),
        "gold": _to_int(row["gold"]),
        "stats": _json_loads(str(row["stats_json"]), {}),
        "mana": _to_int(row["mana"]),
        "max_mana": _to_int(row["max_mana"]),
        "challenge_tokens": _to_int(row["challenge_tokens"]),
    }


def _accepted_favorite(connection: sqlite3.Connection, sorceress_id: str, player_id: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM favorite_runtime
        WHERE sorceress_id = ?
          AND favored_player_id = ?
          AND status = 'accepted'
        LIMIT 1
        """,
        (sorceress_id, player_id),
    ).fetchone()
    return row is not None


def _is_locked_intent_spell(spell: sqlite3.Row, effect: dict[str, Any]) -> bool:
    return str(spell["target_type"]) == "final_hook" or effect.get("effect") == "locked_magical_intent"


def _final_lock_active(connection: sqlite3.Connection) -> bool:
    row = connection.execute("SELECT locked_at FROM final_lock_state WHERE id = 1").fetchone()
    return bool(row and row["locked_at"])


def _current_act_id(connection: sqlite3.Connection) -> str:
    row = connection.execute("SELECT current_act_id FROM act_state WHERE id = 1").fetchone()
    if row is not None and row["current_act_id"]:
        return str(row["current_act_id"])
    if _table_exists(connection, "acts"):
        act = connection.execute(
            """
            SELECT act_id
            FROM acts
            WHERE act_type = 'story'
            ORDER BY sequence
            LIMIT 1
            """
        ).fetchone()
        if act is not None:
            return str(act["act_id"])
    return "act1"


def _require_sorceress(connection: sqlite3.Connection, player_id: str) -> sqlite3.Row:
    return _require_player_role(connection, player_id, "sorceress")


def _require_player_role(
    connection: sqlite3.Connection,
    player_id: str,
    role_type: str,
) -> sqlite3.Row:
    row = _require_player(connection, player_id)
    if str(row["role_type"]) != role_type:
        raise SorceressError("role_not_allowed", f"Player {player_id} is not a {role_type}.")
    return row


def _require_player(connection: sqlite3.Connection, player_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT player_id, role_type, level, xp, gold, stats_json, mana,
               max_mana, challenge_tokens
        FROM player_runtime_state
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if row is None:
        raise SorceressError("unknown_player", f"Unknown player_id: {player_id}.")
    return row


def _assert_gold_available(connection: sqlite3.Connection, player_id: str, price_gold: int) -> None:
    player = _require_player(connection, player_id)
    if _to_int(player["gold"]) < price_gold:
        raise SorceressError("insufficient_gold", "Not enough gold to accept transfer.")


def _fetch_required_row(
    connection: sqlite3.Connection,
    table_name: str,
    id_column: str,
    row_id: str,
) -> sqlite3.Row:
    row = _fetch_optional_row(connection, table_name, id_column, row_id)
    if row is None:
        raise SorceressError("unknown_runtime_object", f"Unknown {table_name}.{id_column}: {row_id}.")
    return row


def _fetch_optional_row(
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


def _table_rows(connection: sqlite3.Connection, table_name: str) -> list[sqlite3.Row]:
    if not _table_exists(connection, table_name):
        return []
    return connection.execute(f'SELECT * FROM "{table_name}" ORDER BY _row_number').fetchall()


def _favorite_slot(slot: str) -> str:
    normalized = slot.strip().lower()
    if normalized not in {"primary", "secondary"}:
        raise SorceressError("invalid_favorite_slot", "Favorite slot must be primary or secondary.")
    return normalized


def _placeholders(values: set[str]) -> str:
    return ", ".join("?" for _ in values)


def _clean_row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


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


def _json_loads(value: str, fallback: Any | None = None) -> Any:
    if not value:
        return {} if fallback is None else fallback
    return json.loads(value)


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")


def _to_int(value: object) -> int:
    if value is None or str(value) == "":
        return 0
    return int(value)


def _asset_to_sorceress_error(exc: AssetContractError) -> SorceressError:
    return SorceressError(exc.code, exc.message, exc.status_code)
