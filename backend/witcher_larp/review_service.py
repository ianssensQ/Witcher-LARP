"""Master review and correction lifecycle for event intake rows."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from typing import Any

from .event_schema import ensure_event_schema
from .pve_runtime import PveSideEffectConflictError, apply_pve_completion_side_effects
from .runtime_schema import log_event


REVIEW_ACTIONS = {
    "approve": "approved",
    "reject": "rejected",
    "correct": "corrected",
}
EVENT_STATUS_AFTER_ACTION = {
    "approve": "accepted",
    "reject": "rejected",
    "correct": "accepted",
}
FINAL_REVIEW_STATUSES = set(REVIEW_ACTIONS.values())
VALID_SEVERITIES = {"P0", "P1", "P2", "P3"}


class ReviewDecisionError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400, code: str = "review_error") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def decide_event_review(
    connection: sqlite3.Connection,
    event_id: str,
    *,
    action: str,
    operator: str,
    reason: str,
    severity: str | None = None,
    correction: dict[str, Any] | None = None,
    source: str = "master_api",
) -> dict[str, Any]:
    ensure_event_schema(connection)
    normalized_action = _normalize_action(action)
    status_after = REVIEW_ACTIONS[normalized_action]
    event_status_after = EVENT_STATUS_AFTER_ACTION[normalized_action]
    reason = str(reason or "").strip()
    operator = str(operator or "").strip() or "master"
    source = str(source or "").strip() or "master_api"
    correction_payload = correction or {}

    if not reason:
        raise ReviewDecisionError("Review decision reason is required.")
    if not isinstance(correction_payload, dict):
        raise ReviewDecisionError("Review correction must be an object.")

    row = _latest_review_row(connection, event_id)
    if row is None:
        if _event_exists(connection, event_id):
            raise ReviewDecisionError(
                f"Event has no open master review: {event_id}",
                status_code=404,
                code="review_not_found",
            )
        raise ReviewDecisionError(
            f"Unknown event_id: {event_id}",
            status_code=404,
            code="event_not_found",
        )

    current_review_status = str(row["review_status"])
    if current_review_status in FINAL_REVIEW_STATUSES:
        return _existing_decision_response(
            connection,
            row,
            normalized_action,
            status_after,
        )

    decided_at = _utc_now()
    normalized_severity = _normalize_severity(severity or row["review_severity"])
    original_payload = _json_loads(row["payload_json"], {})
    original_metadata = _json_loads(row["metadata_json"], {})
    effective_payload = _effective_payload(original_payload, correction_payload)
    effective_metadata = _effective_metadata(original_metadata, correction_payload)
    correction_id = f"correction_review_{int(row['review_id'])}"

    master_review = {
        "action": normalized_action,
        "status": status_after,
        "reason": reason,
        "operator": operator,
        "severity": normalized_severity,
        "correction_id": correction_id,
        "decided_at": decided_at,
        "source": source,
    }
    side_effects = _apply_side_effects_if_safe(
        connection,
        row,
        action=normalized_action,
        event_status_after=event_status_after,
        payload=effective_payload,
        metadata=effective_metadata,
        decided_at=decided_at,
    )
    if side_effects is not None:
        master_review["side_effects"] = side_effects
    effective_metadata["master_review"] = master_review

    connection.execute(
        """
        UPDATE events
        SET status = ?,
            reason = ?,
            payload_json = ?,
            metadata_json = ?,
            applied_at = ?
        WHERE server_event_id = ?
        """,
        (
            event_status_after,
            reason,
            _json_dumps(effective_payload),
            _json_dumps(effective_metadata),
            decided_at if event_status_after == "accepted" else None,
            int(row["server_event_id"]),
        ),
    )
    connection.execute(
        """
        UPDATE event_reviews
        SET status = ?,
            decision = ?,
            decision_reason = ?,
            decided_by = ?,
            decided_at = ?,
            severity = ?,
            correction_id = ?
        WHERE review_id = ?
        """,
        (
            status_after,
            normalized_action,
            reason,
            operator,
            decided_at,
            normalized_severity,
            correction_id,
            int(row["review_id"]),
        ),
    )
    connection.execute(
        """
        INSERT INTO master_corrections (
            correction_id, review_id, server_event_id, event_id, action,
            operator, reason, severity, status_before, status_after,
            correction_json, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(correction_id) DO UPDATE SET
            action = excluded.action,
            operator = excluded.operator,
            reason = excluded.reason,
            severity = excluded.severity,
            status_before = excluded.status_before,
            status_after = excluded.status_after,
            correction_json = excluded.correction_json,
            source = excluded.source,
            created_at = excluded.created_at
        """,
        (
            correction_id,
            int(row["review_id"]),
            int(row["server_event_id"]),
            str(row["event_id"]),
            normalized_action,
            operator,
            reason,
            normalized_severity,
            current_review_status,
            status_after,
            _json_dumps(correction_payload),
            source,
            decided_at,
        ),
    )
    log_event(
        connection,
        "event_review_decided",
        {
            "correction_id": correction_id,
            "review_id": int(row["review_id"]),
            "server_event_id": int(row["server_event_id"]),
            "event_id": str(row["event_id"]),
            "action": normalized_action,
            "status_before": current_review_status,
            "status_after": status_after,
            "event_status_after": event_status_after,
            "reason": reason,
            "severity": normalized_severity,
            "operator": operator,
            "side_effects": side_effects,
        },
        source=source,
    )
    return _decision_response(
        connection,
        int(row["review_id"]),
        decision_status="applied",
    )


def _latest_review_row(connection: sqlite3.Connection, event_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            er.review_id,
            er.server_event_id,
            er.event_id,
            er.status AS review_status,
            er.reason AS review_reason,
            er.severity AS review_severity,
            er.created_at AS review_created_at,
            er.decision,
            er.decision_reason,
            er.decided_by,
            er.decided_at,
            er.correction_id,
            e.event_type,
            e.actor_id,
            e.actor_type,
            e.status AS event_status,
            e.reason AS event_reason,
            e.payload_json,
            e.metadata_json,
            e.source AS event_source,
            e.received_at,
            e.applied_at
        FROM event_reviews er
        JOIN events e ON e.server_event_id = er.server_event_id
        WHERE er.event_id = ?
        ORDER BY er.review_id DESC
        LIMIT 1
        """,
        (event_id,),
    ).fetchone()


def _event_exists(connection: sqlite3.Connection, event_id: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM events WHERE event_id = ? LIMIT 1",
        (event_id,),
    ).fetchone()
    return row is not None


def _existing_decision_response(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    action: str,
    expected_status: str,
) -> dict[str, Any]:
    current_status = str(row["review_status"])
    if current_status != expected_status:
        raise ReviewDecisionError(
            f"Review already decided as {current_status}.",
            status_code=409,
            code="review_already_decided",
        )
    response = _decision_response(
        connection,
        int(row["review_id"]),
        decision_status="duplicate",
    )
    response["decision"]["action"] = action
    return response


def _decision_response(
    connection: sqlite3.Connection,
    review_id: int,
    *,
    decision_status: str,
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT
            er.review_id,
            er.server_event_id,
            er.event_id,
            er.status AS review_status,
            er.reason AS review_reason,
            er.severity AS review_severity,
            er.created_at AS review_created_at,
            er.decision,
            er.decision_reason,
            er.decided_by,
            er.decided_at,
            er.correction_id,
            e.event_type,
            e.actor_id,
            e.actor_type,
            e.status AS event_status,
            e.reason AS event_reason,
            e.payload_json,
            e.metadata_json,
            e.source AS event_source,
            e.received_at,
            e.applied_at
        FROM event_reviews er
        JOIN events e ON e.server_event_id = er.server_event_id
        WHERE er.review_id = ?
        """,
        (review_id,),
    ).fetchone()
    if row is None:
        raise ReviewDecisionError("Review disappeared during decision.", status_code=500)
    correction = None
    if row["correction_id"]:
        correction_row = connection.execute(
            """
            SELECT correction_id, review_id, server_event_id, event_id, action,
                   operator, reason, severity, status_before, status_after,
                   correction_json, source, created_at
            FROM master_corrections
            WHERE correction_id = ?
            """,
            (row["correction_id"],),
        ).fetchone()
        correction = _correction_dict(correction_row) if correction_row is not None else None

    return {
        "decision": {
            "status": decision_status,
            "action": row["decision"],
        },
        "review": {
            "review_id": int(row["review_id"]),
            "server_event_id": int(row["server_event_id"]),
            "event_id": row["event_id"],
            "status": row["review_status"],
            "reason": row["review_reason"],
            "severity": row["review_severity"],
            "created_at": row["review_created_at"],
            "decision": row["decision"],
            "decision_reason": row["decision_reason"],
            "decided_by": row["decided_by"],
            "decided_at": row["decided_at"],
            "correction_id": row["correction_id"],
        },
        "event": {
            "server_event_id": int(row["server_event_id"]),
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "actor_id": row["actor_id"],
            "actor_type": row["actor_type"],
            "status": row["event_status"],
            "reason": row["event_reason"],
            "source": row["event_source"],
            "received_at": row["received_at"],
            "applied_at": row["applied_at"],
        },
        "correction": correction,
    }


def _correction_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "correction_id": row["correction_id"],
        "review_id": int(row["review_id"]),
        "server_event_id": int(row["server_event_id"]),
        "event_id": row["event_id"],
        "action": row["action"],
        "operator": row["operator"],
        "reason": row["reason"],
        "severity": row["severity"],
        "status_before": row["status_before"],
        "status_after": row["status_after"],
        "correction": _json_loads(row["correction_json"], {}),
        "source": row["source"],
        "created_at": row["created_at"],
    }


def _effective_payload(
    original_payload: dict[str, Any],
    correction: dict[str, Any],
) -> dict[str, Any]:
    payload_patch = correction.get("payload")
    if not isinstance(payload_patch, dict):
        return dict(original_payload)
    return {**original_payload, **payload_patch}


def _effective_metadata(
    original_metadata: dict[str, Any],
    correction: dict[str, Any],
) -> dict[str, Any]:
    metadata_patch = correction.get("metadata")
    if not isinstance(metadata_patch, dict):
        return dict(original_metadata)
    return {**original_metadata, **metadata_patch}


def _apply_side_effects_if_safe(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    action: str,
    event_status_after: str,
    payload: dict[str, Any],
    metadata: dict[str, Any],
    decided_at: str,
) -> dict[str, Any] | None:
    if event_status_after != "accepted":
        return {"status": "not_applied", "reason": f"{action} does not accept event"}
    pve_payload = payload
    player_id = str(row["actor_id"])
    if str(row["event_type"]) == "paper_recovered" and metadata.get("recovered_event_type") == "pve_completed":
        recovered_payload = metadata.get("recovered_pve_payload")
        if not isinstance(recovered_payload, dict):
            return {
                "status": "not_applied",
                "reason": "paper pve review has no replayable recovered payload",
            }
        pve_payload = recovered_payload
        player_id = str(metadata.get("paper_recovered_player_id") or row["actor_id"])
    elif str(row["event_type"]) != "pve_completed":
        return {"status": "not_applicable", "reason": "event type has audit-only review closure"}
    existing_attempt = connection.execute(
        "SELECT 1 FROM pve_attempts WHERE server_event_id = ? LIMIT 1",
        (int(row["server_event_id"]),),
    ).fetchone()
    if existing_attempt is not None:
        return {"status": "duplicate", "reason": "pve side effects already applied"}

    missing = [
        field
        for field in ("qr_id", "scenario_id", "result")
        if not pve_payload.get(field) and not metadata.get(field)
    ]
    if not (pve_payload.get("act_id") or metadata.get("act_id")):
        missing.append("act_id")
    if missing:
        return {
            "status": "not_applied",
            "reason": f"missing side-effect field(s): {', '.join(missing)}",
        }

    try:
        applied = apply_pve_completion_side_effects(
            connection,
            player_id=player_id,
            payload=pve_payload,
            metadata=metadata,
            status=event_status_after,
            server_event_id=int(row["server_event_id"]),
            now=_parse_time(decided_at),
        )
    except (PveSideEffectConflictError, KeyError, TypeError, ValueError, sqlite3.Error) as exc:
        return {"status": "not_applied", "reason": str(exc)}
    return {"status": "applied", "pve_completion": applied}


def _normalize_action(action: str) -> str:
    normalized = str(action or "").strip().lower()
    if normalized not in REVIEW_ACTIONS:
        raise ReviewDecisionError(
            f"Unsupported review action: {action}",
            code="invalid_review_action",
        )
    return normalized


def _normalize_severity(severity: object) -> str:
    normalized = str(severity or "P2").strip().upper()
    if normalized not in VALID_SEVERITIES:
        raise ReviewDecisionError(
            f"Unsupported review severity: {severity}",
            code="invalid_review_severity",
        )
    return normalized


def _json_loads(raw: object, default: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(str(raw or "{}"))
    except json.JSONDecodeError:
        return dict(default)
    return parsed if isinstance(parsed, dict) else dict(default)


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
