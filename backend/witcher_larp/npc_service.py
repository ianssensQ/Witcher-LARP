"""NPC King/Wanderer runtime events, deal capture and review routing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import sqlite3
from typing import Any

from .reputation_service import ReputationError, apply_reputation_change
from .runtime_schema import log_event
from .timer_service import ensure_runtime_content_state


NPC_ROLES = {"npc_king", "npc_wanderer"}
KING_EVENT_TYPES = {"king_ruling", "dispute_judgment", "major_order", "influence_grant"}
WANDERER_EVENT_TYPES = {
    "stranger_deal",
    "wanderer_deal",
    "dark_artifact",
    "alternate_victory_hook",
    "field_intervention",
}
DEAL_EVENT_TYPES = {
    "stranger_deal",
    "wanderer_deal",
    "dark_artifact",
    "alternate_victory_hook",
}
FINAL_REVIEW_STATUSES = {"approved", "rejected", "corrected"}
FINAL_NPC_EVENT_STATUSES = {"resolved", "dismissed", "closed"}

REVIEW_FALLBACKS: dict[str, dict[str, object]] = {
    "P0": {
        "meaning": "stop_and_resolve_now",
        "response_window": "immediate",
        "review_route": "stop_now",
        "default_owner": "npc_master",
        "blocks_progress": True,
    },
    "P1": {
        "meaning": "resolve_before_next_act_or_final",
        "response_window": "next_buffer",
        "review_route": "before_next_act_or_final",
        "default_owner": "npc_master",
        "blocks_progress": True,
    },
    "P2": {
        "meaning": "review_in_buffer",
        "response_window": "buffer",
        "review_route": "act_buffer",
        "default_owner": "npc_master",
        "blocks_progress": False,
    },
    "P3": {
        "meaning": "log_only",
        "response_window": "post_game",
        "review_route": "post_game_log",
        "default_owner": "master",
        "blocks_progress": False,
    },
}


class NpcEventError(ValueError):
    """Raised when an NPC event cannot be recorded."""


@dataclass(frozen=True)
class NpcEventInput:
    seed_event_id: str | None = None
    npc_role: str | None = None
    event_type: str | None = None
    target_ids: list[str] | None = None
    price: dict[str, Any] | None = None
    condition: dict[str, Any] | None = None
    consequence: dict[str, Any] | None = None
    reputation_delta: int = 0
    visibility: str = "master_and_targets"
    severity: str | None = None
    final_flag: bool = False
    operator: str = "master"
    source: str = "master_api"


def record_npc_event(
    connection: sqlite3.Connection, event_input: NpcEventInput
) -> dict[str, object]:
    ensure_runtime_content_state(connection)
    seed = _fetch_seed_event(connection, event_input.seed_event_id)
    npc_role = event_input.npc_role or _seed_value(seed, "npc_role")
    event_type = event_input.event_type or _seed_value(seed, "event_type")
    if not npc_role or not event_type:
        raise NpcEventError("NPC event requires npc_role and event_type.")
    if npc_role not in NPC_ROLES:
        raise NpcEventError(f"Unsupported NPC role: {npc_role}")
    _validate_event_type(npc_role, event_type)

    target_ids = (
        event_input.target_ids
        if event_input.target_ids is not None
        else _target_ids_from_seed(_seed_value(seed, "target_id"))
    )
    price = event_input.price if event_input.price is not None else _json_from_seed(seed, "price_json")
    condition = event_input.condition if event_input.condition is not None else {}
    consequence = (
        event_input.consequence
        if event_input.consequence is not None
        else _json_from_seed(seed, "consequence_json")
    )
    severity = event_input.severity or _seed_value(seed, "severity") or "P2"
    route = severity_route(connection, severity)
    created_at = _utc_now()
    target_scope = "global" if not target_ids else "addressed"

    cursor = connection.execute(
        """
        INSERT INTO npc_runtime_events (
            npc_event_id, npc_role, event_type, target_scope, target_ids_json,
            price_json, condition_json, consequence_json, reputation_delta,
            visibility, severity, severity_meaning, review_route, review_owner,
            blocks_progress, final_flag, operator, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_input.seed_event_id,
            npc_role,
            event_type,
            target_scope,
            _json_dumps(target_ids),
            _json_dumps(price),
            _json_dumps(condition),
            _json_dumps(consequence),
            int(event_input.reputation_delta),
            event_input.visibility,
            route["severity"],
            route["meaning"],
            route["review_route"],
            route["default_owner"],
            1 if route["blocks_progress"] else 0,
            1 if event_input.final_flag else 0,
            event_input.operator,
            event_input.source,
            created_at,
        ),
    )
    runtime_event_id = int(cursor.lastrowid)
    reputation_changes = _apply_reputation_delta(
        connection,
        target_ids,
        int(event_input.reputation_delta),
        reason=f"{npc_role}:{event_type}",
        source=event_input.source,
    )
    influence_changes = _apply_influence_delta(
        connection,
        target_ids,
        event_type=event_type,
        consequence=consequence,
        source=event_input.source,
    )
    deal = _capture_deal_if_needed(
        connection,
        runtime_event_id=runtime_event_id,
        npc_role=npc_role,
        event_type=event_type,
        target_ids=target_ids,
        price=price,
        condition=condition,
        consequence=consequence,
        final_flag=event_input.final_flag,
        created_at=created_at,
    )

    log_payload = {
        "npc_runtime_event_id": runtime_event_id,
        "seed_event_id": event_input.seed_event_id,
        "npc_role": npc_role,
        "event_type": event_type,
        "target_scope": target_scope,
        "target_ids": target_ids,
        "severity": route["severity"],
        "review_route": route["review_route"],
        "blocks_progress": route["blocks_progress"],
        "final_flag": event_input.final_flag,
        "deal_id": deal.get("deal_id") if deal else None,
        "reputation_changes": reputation_changes,
        "influence_changes": influence_changes,
    }
    log_event(connection, "npc_event_recorded", log_payload, source=event_input.source)
    if deal is not None:
        log_event(connection, "npc_deal_recorded", deal, source=event_input.source)

    return {
        **_fetch_npc_event_by_id(connection, runtime_event_id, visibility="master"),
        "reputation_changes": reputation_changes,
        "influence_changes": influence_changes,
        "deal": deal,
    }


def severity_route(connection: sqlite3.Connection, severity: str) -> dict[str, object]:
    normalized = severity.upper()
    if normalized not in REVIEW_FALLBACKS:
        raise NpcEventError(f"Unsupported review severity: {severity}")
    fallback = REVIEW_FALLBACKS[normalized]
    row = None
    if _table_exists(connection, "review_severity_rules"):
        row = connection.execute(
            """
            SELECT severity, meaning, response_window, default_owner
            FROM review_severity_rules
            WHERE severity = ?
            """,
            (normalized,),
        ).fetchone()
    meaning = str(row["meaning"]) if row is not None else str(fallback["meaning"])
    response_window = (
        str(row["response_window"]) if row is not None else str(fallback["response_window"])
    )
    return {
        "severity": normalized,
        "meaning": meaning,
        "response_window": response_window,
        "review_route": _route_for_response_window(response_window, normalized),
        "default_owner": (
            str(row["default_owner"]) if row is not None else str(fallback["default_owner"])
        ),
        "blocks_progress": normalized in {"P0", "P1"},
    }


def list_npc_events(
    connection: sqlite3.Connection, *, visibility: str = "master"
) -> list[dict[str, object]]:
    ensure_runtime_content_state(connection)
    rows = connection.execute(
        """
        SELECT *
        FROM npc_runtime_events
        ORDER BY npc_runtime_event_id
        """
    ).fetchall()
    return [_npc_event_row_to_dict(row, visibility=visibility) for row in rows]


def list_npc_deals(
    connection: sqlite3.Connection, *, visibility: str = "master"
) -> list[dict[str, object]]:
    ensure_runtime_content_state(connection)
    rows = connection.execute(
        """
        SELECT *
        FROM npc_deals
        ORDER BY deal_id
        """
    ).fetchall()
    return [_npc_deal_row_to_dict(row, visibility=visibility) for row in rows]


def review_queue(connection: sqlite3.Connection) -> dict[str, object]:
    items: list[dict[str, object]] = []
    if _table_exists(connection, "event_reviews"):
        review_rows = connection.execute(
            """
            SELECT er.review_id, er.server_event_id, er.event_id, er.status,
                   er.reason, er.severity, er.created_at, er.decision,
                   er.decision_reason, er.decided_by, er.decided_at,
                   er.correction_id, e.event_type,
                   e.actor_id, e.actor_type
            FROM event_reviews er
            LEFT JOIN events e ON e.server_event_id = er.server_event_id
            WHERE er.status NOT IN ('approved', 'rejected', 'corrected')
            ORDER BY er.review_id
            """
        ).fetchall()
        for row in review_rows:
            route = severity_route(connection, str(row["severity"]))
            items.append(
                {
                    "queue_type": "event_review",
                    "review_id": int(row["review_id"]),
                    "server_event_id": int(row["server_event_id"]),
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "actor_id": row["actor_id"],
                    "actor_type": row["actor_type"],
                    "status": row["status"],
                    "reason": row["reason"],
                    "decision": row["decision"],
                    "decision_reason": row["decision_reason"],
                    "decided_by": row["decided_by"],
                    "decided_at": row["decided_at"],
                    "correction_id": row["correction_id"],
                    **route,
                    "created_at": row["created_at"],
                }
            )

    for event in list_npc_events(connection, visibility="master"):
        if event["status"] in FINAL_NPC_EVENT_STATUSES or not event["blocks_progress"]:
            continue
        items.append(
            {
                "queue_type": "npc_event",
                "npc_runtime_event_id": event["npc_runtime_event_id"],
                "npc_role": event["npc_role"],
                "event_type": event["event_type"],
                "target_scope": event["target_scope"],
                "target_ids": event["target_ids"],
                "reason": event["severity_meaning"],
                "severity": event["severity"],
                "meaning": event["severity_meaning"],
                "response_window": event["response_window"],
                "review_route": event["review_route"],
                "default_owner": event["review_owner"],
                "blocks_progress": event["blocks_progress"],
                "status": event["status"],
                "resolved_at": event["resolved_at"],
                "created_at": event["created_at"],
            }
        )

    items.sort(key=lambda item: (_severity_rank(str(item["severity"])), str(item["created_at"])))
    return {"items": items}


def resolve_npc_event(
    connection: sqlite3.Connection,
    npc_runtime_event_id: int,
    *,
    operator: str,
    reason: str,
    status: str = "resolved",
    source: str = "master_api",
) -> dict[str, object]:
    ensure_runtime_content_state(connection)
    normalized_status = status.strip().lower()
    if normalized_status not in FINAL_NPC_EVENT_STATUSES:
        raise NpcEventError(f"Unsupported NPC event resolution status: {status}")
    reason = reason.strip()
    operator = operator.strip() or "master"
    if not reason:
        raise NpcEventError("NPC event resolution reason is required.")

    event = _fetch_npc_event_by_id(connection, npc_runtime_event_id, visibility="master")
    if event["status"] in FINAL_NPC_EVENT_STATUSES:
        return {**event, "duplicate": True}

    resolved_at = _utc_now()
    connection.execute(
        """
        UPDATE npc_runtime_events
        SET status = ?,
            blocks_progress = 0,
            resolved_at = ?,
            resolved_by = ?,
            resolution_reason = ?
        WHERE npc_runtime_event_id = ?
        """,
        (
            normalized_status,
            resolved_at,
            operator,
            reason,
            npc_runtime_event_id,
        ),
    )
    resolved = _fetch_npc_event_by_id(connection, npc_runtime_event_id, visibility="master")
    log_event(
        connection,
        "npc_event_resolved",
        {
            "npc_runtime_event_id": npc_runtime_event_id,
            "status": normalized_status,
            "operator": operator,
            "reason": reason,
        },
        source=source,
    )
    return {**resolved, "duplicate": False}


def _apply_reputation_delta(
    connection: sqlite3.Connection,
    target_ids: list[str],
    delta: int,
    *,
    reason: str,
    source: str,
) -> list[dict[str, object]]:
    if delta == 0:
        return []
    changes: list[dict[str, object]] = []
    for target_id in target_ids:
        if not _is_player(connection, target_id):
            continue
        try:
            changes.append(
                apply_reputation_change(
                    connection,
                    target_id,
                    delta,
                    reason=reason,
                    source=source,
                )
            )
        except ReputationError as exc:
            raise NpcEventError(str(exc)) from exc
    if not changes:
        raise NpcEventError("reputation_delta requires a witcher or sorceress target.")
    return changes


def _apply_influence_delta(
    connection: sqlite3.Connection,
    target_ids: list[str],
    *,
    event_type: str,
    consequence: dict[str, Any],
    source: str,
) -> list[dict[str, object]]:
    delta = _influence_delta(event_type, consequence)
    if delta == 0:
        return []
    ensure_runtime_content_state(connection)
    now = _utc_now()
    changes = []
    for domain_id in _target_domain_ids(connection, target_ids):
        before = connection.execute(
            "SELECT influence FROM domain_runtime_state WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()
        before_value = int(before["influence"]) if before is not None else 0
        after_value = before_value + delta
        connection.execute(
            """
            UPDATE domain_runtime_state
            SET influence = ?, updated_at = ?
            WHERE domain_id = ?
            """,
            (after_value, now, domain_id),
        )
        changes.append(
            {
                "domain_id": domain_id,
                "delta": delta,
                "value_before": before_value,
                "value_after": after_value,
                "source": source,
            }
        )
    return changes


def _influence_delta(event_type: str, consequence: dict[str, Any]) -> int:
    if "influence_delta" in consequence:
        return int(consequence["influence_delta"])
    if "influence" in consequence:
        return int(consequence["influence"])
    effect = str(consequence.get("effect") or "")
    if effect.startswith("influence_plus_"):
        return int(effect.removeprefix("influence_plus_"))
    if effect.startswith("influence_minus_"):
        return -int(effect.removeprefix("influence_minus_"))
    return 1 if event_type == "influence_grant" else 0


def _target_domain_ids(connection: sqlite3.Connection, target_ids: list[str]) -> list[str]:
    domain_ids: list[str] = []
    for target_id in target_ids:
        domain = connection.execute(
            "SELECT domain_id FROM domain_runtime_state WHERE domain_id = ?",
            (target_id,),
        ).fetchone()
        if domain is not None:
            domain_ids.append(str(domain["domain_id"]))
            continue
        lord_domain = connection.execute(
            """
            SELECT domain_id
            FROM domain_runtime_state
            WHERE lord_player_id = ?
            """,
            (target_id,),
        ).fetchone()
        if lord_domain is not None:
            domain_ids.append(str(lord_domain["domain_id"]))
    return sorted(set(domain_ids))


def _capture_deal_if_needed(
    connection: sqlite3.Connection,
    *,
    runtime_event_id: int,
    npc_role: str,
    event_type: str,
    target_ids: list[str],
    price: dict[str, Any],
    condition: dict[str, Any],
    consequence: dict[str, Any],
    final_flag: bool,
    created_at: str,
) -> dict[str, object] | None:
    should_capture = (
        event_type in DEAL_EVENT_TYPES
        or "hidden_price" in price
        or final_flag
    )
    if not should_capture:
        return None
    cursor = connection.execute(
        """
        INSERT INTO npc_deals (
            npc_runtime_event_id, npc_role, target_ids_json, price_json,
            condition_json, consequence_json, final_flag, hidden_price,
            status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'captured', ?)
        """,
        (
            runtime_event_id,
            npc_role,
            _json_dumps(target_ids),
            _json_dumps(price),
            _json_dumps(condition),
            _json_dumps(consequence),
            1 if final_flag else 0,
            1 if "hidden_price" in price else 0,
            created_at,
        ),
    )
    deal_id = int(cursor.lastrowid)
    return _fetch_deal_by_id(connection, deal_id, visibility="master")


def _fetch_npc_event_by_id(
    connection: sqlite3.Connection, runtime_event_id: int, *, visibility: str
) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT *
        FROM npc_runtime_events
        WHERE npc_runtime_event_id = ?
        """,
        (runtime_event_id,),
    ).fetchone()
    if row is None:
        raise NpcEventError(f"Missing NPC runtime event {runtime_event_id}.")
    return _npc_event_row_to_dict(row, visibility=visibility)


def _fetch_deal_by_id(
    connection: sqlite3.Connection, deal_id: int, *, visibility: str
) -> dict[str, object]:
    row = connection.execute(
        """
        SELECT *
        FROM npc_deals
        WHERE deal_id = ?
        """,
        (deal_id,),
    ).fetchone()
    if row is None:
        raise NpcEventError(f"Missing NPC deal {deal_id}.")
    return _npc_deal_row_to_dict(row, visibility=visibility)


def _npc_event_row_to_dict(row: sqlite3.Row, *, visibility: str) -> dict[str, object]:
    price = _json_loads(row["price_json"], {})
    route = severity_route_from_row(row)
    return {
        "npc_runtime_event_id": int(row["npc_runtime_event_id"]),
        "seed_event_id": row["npc_event_id"],
        "npc_role": row["npc_role"],
        "event_type": row["event_type"],
        "target_scope": row["target_scope"],
        "target_ids": _json_loads(row["target_ids_json"], []),
        "price": _price_for_visibility(price, visibility),
        "condition": _json_loads(row["condition_json"], {}),
        "consequence": _json_loads(row["consequence_json"], {}),
        "reputation_delta": int(row["reputation_delta"]),
        "visibility": row["visibility"],
        "severity": row["severity"],
        "severity_meaning": row["severity_meaning"],
        "response_window": route["response_window"],
        "review_route": row["review_route"],
        "review_owner": row["review_owner"],
        "blocks_progress": bool(row["blocks_progress"]),
        "final_flag": bool(row["final_flag"]),
        "status": row["status"],
        "resolved_at": row["resolved_at"],
        "resolved_by": row["resolved_by"],
        "resolution_reason": row["resolution_reason"],
        "operator": row["operator"],
        "source": row["source"],
        "created_at": row["created_at"],
    }


def _npc_deal_row_to_dict(row: sqlite3.Row, *, visibility: str) -> dict[str, object]:
    price = _json_loads(row["price_json"], {})
    return {
        "deal_id": int(row["deal_id"]),
        "npc_runtime_event_id": int(row["npc_runtime_event_id"]),
        "npc_role": row["npc_role"],
        "target_ids": _json_loads(row["target_ids_json"], []),
        "price": _price_for_visibility(price, visibility),
        "condition": _json_loads(row["condition_json"], {}),
        "consequence": _json_loads(row["consequence_json"], {}),
        "final_flag": bool(row["final_flag"]),
        "hidden_price": bool(row["hidden_price"]),
        "status": row["status"],
        "created_at": row["created_at"],
    }


def severity_route_from_row(row: sqlite3.Row) -> dict[str, object]:
    return {
        "severity": row["severity"],
        "meaning": row["severity_meaning"],
        "response_window": _response_window_for_route(row["review_route"]),
        "review_route": row["review_route"],
        "default_owner": row["review_owner"],
        "blocks_progress": bool(row["blocks_progress"]),
    }


def _fetch_seed_event(
    connection: sqlite3.Connection, seed_event_id: str | None
) -> sqlite3.Row | None:
    if not seed_event_id:
        return None
    if not _table_exists(connection, "npc_events"):
        raise NpcEventError("No imported npc_events content is available.")
    row = connection.execute(
        """
        SELECT *
        FROM npc_events
        WHERE event_id = ?
        """,
        (seed_event_id,),
    ).fetchone()
    if row is None:
        raise NpcEventError(f"Unknown NPC seed event: {seed_event_id}")
    return row


def _validate_event_type(npc_role: str, event_type: str) -> None:
    if npc_role == "npc_king" and event_type not in KING_EVENT_TYPES:
        raise NpcEventError(f"Unsupported King event_type: {event_type}")
    if npc_role == "npc_wanderer" and event_type not in WANDERER_EVENT_TYPES:
        raise NpcEventError(f"Unsupported Wanderer event_type: {event_type}")


def _seed_value(row: sqlite3.Row | None, key: str) -> str | None:
    if row is None:
        return None
    value = row[key] if key in row.keys() else None
    return str(value) if value not in (None, "") else None


def _target_ids_from_seed(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


def _json_from_seed(row: sqlite3.Row | None, key: str) -> dict[str, Any]:
    value = _seed_value(row, key)
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise NpcEventError(f"{key} must be a JSON object.")
    return parsed


def _price_for_visibility(price: dict[str, Any], visibility: str) -> dict[str, Any]:
    if visibility == "master" or "hidden_price" not in price:
        return price
    return {"hidden_price": "master_only", "hidden": True}


def _route_for_response_window(response_window: str, severity: str) -> str:
    if response_window == "immediate":
        return "stop_now"
    if response_window == "next_buffer":
        return "before_next_act_or_final"
    if response_window == "buffer":
        return "act_buffer"
    if response_window == "post_game":
        return "post_game_log"
    return str(REVIEW_FALLBACKS[severity]["review_route"])


def _response_window_for_route(review_route: str) -> str:
    return {
        "stop_now": "immediate",
        "before_next_act_or_final": "next_buffer",
        "act_buffer": "buffer",
        "post_game_log": "post_game",
    }.get(review_route, "buffer")


def _is_player(connection: sqlite3.Connection, player_id: str) -> bool:
    if not _table_exists(connection, "players"):
        return False
    row = connection.execute(
        "SELECT 1 FROM players WHERE player_id = ?",
        (player_id,),
    ).fetchone()
    return row is not None


def _severity_rank(severity: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(severity, 99)


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


def _json_loads(value: str, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
