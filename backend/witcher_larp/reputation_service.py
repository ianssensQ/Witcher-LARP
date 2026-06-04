"""Good/Evil reputation runtime state and visibility helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import sqlite3
from typing import Any

from .runtime_schema import log_event


REPUTATION_MIN = -5
REPUTATION_MAX = 5
REPUTATION_ROLES = {"witcher", "sorceress"}

CANONICAL_LABELS: dict[str, str] = {
    "darkness": "Тьма",
    "тьма": "Тьма",
    "tainted": "Запятнанный",
    "запятнанный": "Запятнанный",
    "neutral": "Нейтральный",
    "нейтральный": "Нейтральный",
    "good": "Добро",
    "добро": "Добро",
    "light": "Свет",
    "свет": "Свет",
}

FALLBACK_RULES = (
    ("rep_darkness", -5, -4, "Darkness", "feared"),
    ("rep_tainted", -3, -2, "Tainted", "untrusted"),
    ("rep_neutral", -1, 1, "Neutral", "uncertain"),
    ("rep_good", 2, 3, "Good", "trusted"),
    ("rep_light", 4, 5, "Light", "celebrated"),
)

THRESHOLD_ACCESS: dict[str, dict[str, object]] = {
    "Тьма": {
        "axis": "dark",
        "tier": 2,
        "benefits": ["wanderer_hidden_price_deals", "dark_artifact_hooks"],
        "costs": ["king_ruling_scrutiny", "light_influence_blocked"],
        "opposite": "Свет",
    },
    "Запятнанный": {
        "axis": "dark",
        "tier": 1,
        "benefits": ["wanderer_temptation_access"],
        "costs": ["king_favor_more_expensive"],
        "opposite": "Добро",
    },
    "Нейтральный": {
        "axis": "neutral",
        "tier": 0,
        "benefits": ["no_threshold_lock"],
        "costs": ["no_threshold_bonus"],
        "opposite": "Нейтральный",
    },
    "Добро": {
        "axis": "light",
        "tier": 1,
        "benefits": ["king_minor_favor", "public_trust_hooks"],
        "costs": ["wanderer_price_increases"],
        "opposite": "Запятнанный",
    },
    "Свет": {
        "axis": "light",
        "tier": 2,
        "benefits": ["king_influence_awards", "light_ruling_access"],
        "costs": ["dark_deals_hidden_cost_double"],
        "opposite": "Тьма",
    },
}


class ReputationError(ValueError):
    """Raised when a reputation operation cannot be applied."""


@dataclass(frozen=True)
class ReputationRule:
    rule_id: str
    min_value: int
    max_value: int
    label: str
    canonical_label: str
    player_descriptor: str


def get_reputation_view(
    connection: sqlite3.Connection, player_id: str, *, visibility: str = "player"
) -> dict[str, object]:
    state = _ensure_player_state(connection, player_id)
    rule = _rule_for_value(connection, state["value"])
    base: dict[str, object] = {
        "player_id": player_id,
        "role_type": state["role_type"],
        "state_label": rule.label,
        "canonical_label": rule.canonical_label,
        "player_descriptor": rule.player_descriptor,
        "threshold_access": threshold_access(rule),
    }
    if visibility == "master":
        base["threshold_range"] = {
            "min": rule.min_value,
            "max": rule.max_value,
        }
        base["value"] = int(state["value"])
        base["change_log"] = _change_log(connection, player_id)
    else:
        base["value_visibility"] = "hidden_from_player"
    return base


def apply_reputation_change(
    connection: sqlite3.Connection,
    player_id: str,
    delta: int,
    *,
    reason: str,
    visibility: str = "player_and_master",
    source: str = "master_api",
    source_event_id: int | None = None,
) -> dict[str, object]:
    state = _ensure_player_state(connection, player_id)
    value_before = int(state["value"])
    value_after = _clamp(value_before + int(delta))
    rule = _rule_for_value(connection, value_after)
    created_at = _utc_now()

    connection.execute(
        """
        UPDATE reputation_state
        SET value = ?, label = ?, player_descriptor = ?, updated_at = ?
        WHERE player_id = ?
        """,
        (value_after, rule.label, rule.player_descriptor, created_at, player_id),
    )
    cursor = connection.execute(
        """
        INSERT INTO reputation_changes (
            player_id, delta, value_before, value_after, label_after,
            player_descriptor_after, reason, visibility, source, source_event_id,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            player_id,
            int(delta),
            value_before,
            value_after,
            rule.label,
            rule.player_descriptor,
            reason,
            visibility,
            source,
            source_event_id,
            created_at,
        ),
    )
    change_id = int(cursor.lastrowid)
    log_event(
        connection,
        "reputation_changed",
        {
            "change_id": change_id,
            "player_id": player_id,
            "delta": int(delta),
            "value_before": value_before,
            "value_after": value_after,
            "state_label": rule.label,
            "canonical_label": rule.canonical_label,
            "reason": reason,
            "visibility": visibility,
        },
        source=source,
    )

    return {
        "change_id": change_id,
        "player_id": player_id,
        "delta": int(delta),
        "value_before": value_before,
        "value_after": value_after,
        "state_label": rule.label,
        "canonical_label": rule.canonical_label,
        "player_descriptor": rule.player_descriptor,
        "threshold_access": threshold_access(rule),
    }


def threshold_access(rule: ReputationRule) -> dict[str, object]:
    access = dict(THRESHOLD_ACCESS[rule.canonical_label])
    access["state"] = rule.canonical_label
    return access


def _ensure_player_state(connection: sqlite3.Connection, player_id: str) -> sqlite3.Row:
    existing = connection.execute(
        """
        SELECT player_id, role_type, value, label, player_descriptor
        FROM reputation_state
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if existing is not None:
        return existing

    player = connection.execute(
        """
        SELECT player_id, role_type, reputation
        FROM players
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if player is None:
        raise ReputationError(f"Unknown reputation target: {player_id}")
    role_type = str(player["role_type"])
    if role_type not in REPUTATION_ROLES:
        raise ReputationError("Reputation applies only to witchers and sorceresses.")

    start_value = _clamp(_to_int(player["reputation"]))
    rule = _rule_for_value(connection, start_value)
    now = _utc_now()
    connection.execute(
        """
        INSERT INTO reputation_state (
            player_id, role_type, value, label, player_descriptor, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(player_id) DO NOTHING
        """,
        (player_id, role_type, start_value, rule.label, rule.player_descriptor, now),
    )
    return connection.execute(
        """
        SELECT player_id, role_type, value, label, player_descriptor
        FROM reputation_state
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()


def _rule_for_value(connection: sqlite3.Connection, value: int) -> ReputationRule:
    value = _clamp(value)
    row = None
    if _table_exists(connection, "reputation_rules"):
        row = connection.execute(
            """
            SELECT rule_id, min_value, max_value, label, player_descriptor
            FROM reputation_rules
            WHERE CAST(min_value AS INTEGER) <= ?
              AND CAST(max_value AS INTEGER) >= ?
            ORDER BY CAST(min_value AS INTEGER)
            LIMIT 1
            """,
            (value, value),
        ).fetchone()

    if row is not None:
        label = str(row["label"])
        return ReputationRule(
            rule_id=str(row["rule_id"]),
            min_value=_to_int(row["min_value"]),
            max_value=_to_int(row["max_value"]),
            label=label,
            canonical_label=_canonical_label(label),
            player_descriptor=str(row["player_descriptor"]),
        )

    for rule_id, min_value, max_value, label, descriptor in FALLBACK_RULES:
        if min_value <= value <= max_value:
            return ReputationRule(
                rule_id=rule_id,
                min_value=min_value,
                max_value=max_value,
                label=label,
                canonical_label=_canonical_label(label),
                player_descriptor=descriptor,
            )
    raise ReputationError(f"No reputation rule covers value {value}.")


def _change_log(connection: sqlite3.Connection, player_id: str) -> list[dict[str, object]]:
    rows = connection.execute(
        """
        SELECT change_id, delta, value_before, value_after, label_after,
               player_descriptor_after, reason, visibility, source, created_at
        FROM reputation_changes
        WHERE player_id = ?
        ORDER BY change_id
        """,
        (player_id,),
    ).fetchall()
    return [
        {
            "change_id": int(row["change_id"]),
            "delta": int(row["delta"]),
            "value_before": int(row["value_before"]),
            "value_after": int(row["value_after"]),
            "state_label": row["label_after"],
            "canonical_label": _canonical_label(str(row["label_after"])),
            "player_descriptor": row["player_descriptor_after"],
            "reason": row["reason"],
            "visibility": row["visibility"],
            "source": row["source"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _canonical_label(label: str) -> str:
    try:
        return CANONICAL_LABELS[label.casefold()]
    except KeyError as exc:
        raise ReputationError(f"Unknown reputation label: {label}") from exc


def _clamp(value: int) -> int:
    return max(REPUTATION_MIN, min(REPUTATION_MAX, value))


def _to_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(value)


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


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
