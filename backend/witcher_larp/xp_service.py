"""Shared XP spending helpers for player level progression."""

from __future__ import annotations

import sqlite3


DEFAULT_LEVEL_COSTS = [0, 10, 25, 45, 70, 100, 135, 175, 220, 270]


def spend_xp_for_levels(
    connection: sqlite3.Connection,
    *,
    level_before: int,
    xp_available: int,
) -> tuple[int, int]:
    """Spend current XP on level-up costs and return remaining XP plus level."""
    costs = level_costs(connection)
    level = max(1, int(level_before or 0))
    remaining_xp = max(0, int(xp_available or 0))
    while True:
        next_cost = next_level_cost(costs, level)
        if next_cost <= 0 or remaining_xp < next_cost:
            break
        remaining_xp -= next_cost
        level += 1
    return remaining_xp, level


def level_costs(connection: sqlite3.Connection) -> list[int]:
    costs = list(DEFAULT_LEVEL_COSTS)
    if _table_exists(connection, "xp_rules"):
        row = connection.execute(
            """
            SELECT level_thresholds
            FROM xp_rules
            ORDER BY _row_number
            LIMIT 1
            """
        ).fetchone()
        level_thresholds = _row_value(row, "level_thresholds", 0) if row is not None else None
        if level_thresholds:
            parsed = [_to_int(part) for part in str(level_thresholds).split(";") if part]
            if parsed:
                costs = parsed
    return costs


def next_level_cost(costs: list[int], current_level: int) -> int:
    index = current_level - 1
    if costs and costs[0] == 0:
        index = current_level
    if index < 0 or index >= len(costs):
        return 0
    return int(costs[index])


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


def _to_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _row_value(row: object, key: str, index: int) -> object:
    if isinstance(row, sqlite3.Row):
        return row[key]
    if isinstance(row, tuple):
        return row[index]
    return None
