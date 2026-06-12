"""Helpers for territory-specific strategic bonuses."""

from __future__ import annotations

import sqlite3
from typing import Any


NUMERIC_EFFECT_TYPES = {
    "home_base",
    "income_flat",
    "influence_flat",
    "mp_refill_flat",
    "raid_defense_flat",
    "raid_token_cap",
}
RECRUIT_CARD_UNLOCK = "recruit_card_unlock"
ALL_EFFECT_TYPES = NUMERIC_EFFECT_TYPES | {RECRUIT_CARD_UNLOCK}


def territory_bonus_payloads(
    connection: sqlite3.Connection, territory_id: str
) -> list[dict[str, Any]]:
    if not _table_exists(connection, "territory_bonuses"):
        return []
    rows = connection.execute(
        """
        SELECT bonus_id, territory_id, effect_type, effect_value, public_label,
               strategic_role, stacking_rule, notes
        FROM territory_bonuses
        WHERE territory_id = ?
        ORDER BY _row_number, bonus_id
        """,
        (territory_id,),
    ).fetchall()
    return [_bonus_payload(row) for row in rows]


def territory_numeric_bonus(
    connection: sqlite3.Connection, territory_id: str, effect_type: str
) -> int:
    if not _table_exists(connection, "territory_bonuses"):
        return 0
    return sum(
        _to_int(row["effect_value"])
        for row in connection.execute(
            """
            SELECT effect_value
            FROM territory_bonuses
            WHERE territory_id = ? AND effect_type = ?
            """,
            (territory_id, effect_type),
        ).fetchall()
    )


def controlled_domain_numeric_bonus(
    connection: sqlite3.Connection, domain_id: str, effect_type: str
) -> int:
    return sum(
        _to_int(row["effect_value"])
        for row in controlled_domain_bonus_rows(
            connection,
            domain_id,
            effect_type=effect_type,
        )
    )


def controlled_domain_bonus_rows(
    connection: sqlite3.Connection,
    domain_id: str,
    *,
    effect_type: str | None = None,
) -> list[dict[str, Any]]:
    if not _table_exists(connection, "territory_bonuses"):
        return []
    where_effect = "AND b.effect_type = ?" if effect_type else ""
    params: tuple[object, ...] = (domain_id, effect_type) if effect_type else (domain_id,)
    owner_sql = _controlled_owner_sql(connection)
    rows = connection.execute(
        f"""
        SELECT b.bonus_id, b.territory_id, b.effect_type, b.effect_value,
               b.public_label, b.strategic_role, b.stacking_rule, b.notes
        FROM territory_bonuses b
        JOIN ({owner_sql}) owned ON owned.territory_id = b.territory_id
        WHERE owned.owner_domain_id = ?
          AND owned.status = 'controlled'
          {where_effect}
        ORDER BY b._row_number, b.bonus_id
        """,
        params,
    ).fetchall()
    return [_bonus_payload(row) for row in rows]


def controlled_domain_recruit_card_ids(
    connection: sqlite3.Connection, domain_id: str
) -> list[str]:
    card_ids: set[str] = set()
    for row in controlled_domain_bonus_rows(
        connection,
        domain_id,
        effect_type=RECRUIT_CARD_UNLOCK,
    ):
        for card_id in str(row.get("effect_value") or "").split(";"):
            card_id = card_id.strip()
            if card_id:
                card_ids.add(card_id)
    return sorted(card_ids)


def _controlled_owner_sql(connection: sqlite3.Connection) -> str:
    if _table_exists(connection, "territory_runtime_state"):
        return """
            SELECT territory_id, owner_domain_id, status
            FROM territory_runtime_state
        """
    return """
        SELECT territory_id,
               owner_domain_id,
               CASE
                   WHEN owner_domain_id IS NULL OR owner_domain_id = '' THEN 'neutral'
                   ELSE 'controlled'
               END AS status
        FROM territories
    """


def _bonus_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = {key: row[key] for key in row.keys()}
    payload["effect_value_int"] = _to_int(payload.get("effect_value"))
    return payload


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        is not None
    )


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default
