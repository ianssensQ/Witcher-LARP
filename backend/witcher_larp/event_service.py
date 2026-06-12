"""Idempotent event intake persistence and lightweight validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import sqlite3
from typing import Any

from .asset_service import AssetContractError
from .event_schema import ensure_event_schema
from .event_models import (
    EventStatus,
    EventSyncEvent,
    EventSyncRequest,
    EventSyncResponse,
    EventSyncResult,
)
from .pve_runtime import (
    APP_GENERATED_ROLL_SOURCE,
    MASTER_RECOVERED_ROLL_SOURCES,
    PVE_RESULTS,
    PveSideEffectConflictError,
    resolve_pve_scene,
)
from .pve_runtime import apply_pve_completion_side_effects, validate_pve_completion
from .repository import latest_snapshot_version
from .reward_service import create_pending_reward_approval


MASTER_ACTOR_TYPES = {"master", "npc_master", "npc", "king", "wanderer"}
PLAYER_ROLE_TYPES = {"player", "lord", "sorceress", "witcher"}
MASTER_ONLY_EVENT_TYPES = {"paper_recovered"}
MOBILE_PLAYER_ROLE_TYPES = {"sorceress", "witcher"}
PLAYER_ONLY_SYNC_EVENT_TYPES = {
    "pve_completed",
    "qr_attempt",
    "qr_scene_started",
    "reward_approval_requested",
}


@dataclass(frozen=True)
class EventDecision:
    status: EventStatus
    reason: str | None
    metadata: dict[str, Any]


def sync_events(
    connection: sqlite3.Connection, request: EventSyncRequest
) -> EventSyncResponse:
    ensure_event_schema(connection)
    server_time = _utc_now()
    tracker = _client_sequence_tracker(connection, request)
    results: list[EventSyncResult] = []
    for event in request.events:
        existing = _existing_event_row(connection, event.event_id)
        preflight_decision = None
        if existing is None:
            preflight_decision = _preflight_event_decision(
                connection,
                request,
                event,
                tracker,
            )
        results.append(
            _sync_single_event(
                connection,
                request,
                event,
                server_time,
                existing=existing,
                preflight_decision=preflight_decision,
            )
        )
    _record_client_sync_state(connection, request, server_time, tracker)
    return EventSyncResponse(
        server_time=server_time,
        snapshot_version=latest_snapshot_version(connection),
        results=results,
    )


def _existing_event_row(connection: sqlite3.Connection, event_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT server_event_id, status, reason
        FROM events
        WHERE event_id = ?
        """,
        (event_id,),
    ).fetchone()


def _duplicate_event_result(event_id: str, existing: sqlite3.Row) -> EventSyncResult:
    original_status = _event_status_from_db(existing["status"])
    visible_status = (
        EventStatus.DUPLICATE
        if original_status == EventStatus.ACCEPTED
        else original_status
    )
    reason = existing["reason"]
    if visible_status == EventStatus.DUPLICATE and not reason:
        reason = "event_id already processed"
    return EventSyncResult(
        event_id=event_id,
        status=visible_status,
        reason=reason,
        server_event_id=int(existing["server_event_id"]),
    )


def _event_status_from_db(value: object) -> EventStatus:
    try:
        return EventStatus(str(value))
    except ValueError:
        return EventStatus.NEEDS_MASTER_REVIEW


def _client_sequence_tracker(
    connection: sqlite3.Connection,
    request: EventSyncRequest,
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT player_id, last_event_sequence
        FROM client_sync_state
        WHERE client_id = ?
        """,
        (request.device_id,),
    ).fetchone()
    last_sequence = int(row["last_event_sequence"]) if row is not None else 0
    return {
        "last_sequence": last_sequence,
        "next_expected": last_sequence + 1,
        "highest_contiguous": last_sequence,
        "seen_sequences": set(),
    }


def _preflight_event_decision(
    connection: sqlite3.Connection,
    request: EventSyncRequest,
    event: EventSyncEvent,
    tracker: dict[str, Any],
) -> EventDecision | None:
    actor_reason = _payload_actor_scope_reason(request, event)
    if actor_reason is not None:
        return EventDecision(
            EventStatus.REJECTED,
            actor_reason,
            {
                "device_id": request.device_id,
                "actor_id": request.actor_id,
                "actor_type": request.actor_type,
                "client_sequence": event.client_sequence,
                "event_type": event.event_type,
                "audit_review": True,
                "review_severity": "P0",
                "auth_boundary": "event_payload_actor_mismatch",
            },
        )

    sequence_decision = _client_sequence_decision(request, event, tracker)
    if sequence_decision is not None:
        return sequence_decision

    tracker["seen_sequences"].add(event.client_sequence)
    tracker["highest_contiguous"] = max(
        int(tracker["highest_contiguous"]),
        event.client_sequence,
    )
    tracker["next_expected"] = event.client_sequence + 1
    return None


def _payload_actor_scope_reason(
    request: EventSyncRequest,
    event: EventSyncEvent,
) -> str | None:
    if event.event_type not in PLAYER_ONLY_SYNC_EVENT_TYPES:
        return None
    payload_player_id = str(event.payload.get("player_id") or "").strip()
    if payload_player_id and payload_player_id != request.actor_id:
        return "event payload player_id does not match authenticated actor"
    if event.event_type == "pve_completed":
        roll_player_id = str(_pve_payload_roll_entry(event.payload).get("player_id") or "").strip()
        if roll_player_id and roll_player_id != request.actor_id:
            return "event roll_log player_id does not match authenticated actor"
    return None


def _client_sequence_decision(
    request: EventSyncRequest,
    event: EventSyncEvent,
    tracker: dict[str, Any],
) -> EventDecision | None:
    sequence = event.client_sequence
    metadata: dict[str, Any] = {
        "device_id": request.device_id,
        "actor_id": request.actor_id,
        "actor_type": request.actor_type,
        "client_sequence": sequence,
        "event_type": event.event_type,
        "last_event_sequence": int(tracker["last_sequence"]),
        "expected_client_sequence": int(tracker["next_expected"]),
        "sequence_boundary": "client_sequence",
    }
    if sequence in tracker["seen_sequences"]:
        metadata.update({"audit_review": True, "review_severity": "P1"})
        return EventDecision(
            EventStatus.REJECTED,
            f"duplicate client_sequence in sync batch: {sequence}",
            metadata,
        )
    if sequence < int(tracker["next_expected"]):
        metadata.update({"audit_review": True, "review_severity": "P1"})
        return EventDecision(
            EventStatus.REJECTED,
            (
                "client_sequence already processed or out of order: "
                f"{sequence} < {int(tracker['next_expected'])}"
            ),
            metadata,
        )
    if sequence > int(tracker["next_expected"]):
        metadata.update({"audit_review": True, "review_severity": "P1"})
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            (
                "client_sequence gap detected: "
                f"expected {int(tracker['next_expected'])}, got {sequence}"
            ),
            metadata,
        )
    return None


def _sync_single_event(
    connection: sqlite3.Connection,
    request: EventSyncRequest,
    event: EventSyncEvent,
    received_at: str,
    *,
    existing: sqlite3.Row | None = None,
    preflight_decision: EventDecision | None = None,
) -> EventSyncResult:
    existing = existing if existing is not None else _existing_event_row(connection, event.event_id)
    if existing is not None:
        return _duplicate_event_result(event.event_id, existing)

    decision = preflight_decision or _decide_event(connection, request, event)
    payload_json = _json_dumps(event.payload)
    metadata_json = _json_dumps(decision.metadata)
    applied_at = received_at if decision.status == EventStatus.ACCEPTED else None
    event_source = _source_for_event(event)
    cursor = connection.execute(
        """
        INSERT INTO events (
            event_id, device_id, actor_id, actor_type, client_sequence,
            client_created_at, event_type, status, reason, payload_json,
            metadata_json, source, received_at, applied_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.event_id,
            request.device_id,
            request.actor_id,
            request.actor_type,
            event.client_sequence,
            str(event.created_at),
            event.event_type,
            decision.status.value,
            decision.reason,
            payload_json,
            metadata_json,
            event_source,
            received_at,
            applied_at,
        ),
    )
    server_event_id = int(cursor.lastrowid)
    _record_event_log(connection, request, event, decision, server_event_id)
    _record_review_if_needed(connection, event, decision, server_event_id)
    decision = _record_pending_reward_if_needed(
        connection,
        request,
        event,
        decision,
        server_event_id,
    )
    decision = _apply_pve_side_effects_if_needed(
        connection,
        request,
        event,
        decision,
        server_event_id,
        received_at,
    )

    return EventSyncResult(
        event_id=event.event_id,
        status=decision.status,
        reason=decision.reason,
        server_event_id=server_event_id,
    )


def _decide_event(
    connection: sqlite3.Connection, request: EventSyncRequest, event: EventSyncEvent
) -> EventDecision:
    metadata: dict[str, Any] = {
        "device_id": request.device_id,
        "actor_id": request.actor_id,
        "actor_type": request.actor_type,
        "client_sequence": event.client_sequence,
        "event_type": event.event_type,
    }
    actor_reason = _actor_validation_reason(connection, request.actor_id, request.actor_type)
    if actor_reason is not None:
        return EventDecision(EventStatus.REJECTED, actor_reason, metadata)
    canonical_role_type = _canonical_player_role_type(connection, request.actor_id)
    if canonical_role_type is not None:
        metadata["canonical_actor_role_type"] = canonical_role_type

    player_only_reason = _player_only_sync_scope_reason(connection, request, event.event_type)
    if player_only_reason is not None:
        metadata.update(
            {
                "audit_review": True,
                "review_severity": "P0",
                "auth_boundary": "player_only_mobile_event",
            }
        )
        return EventDecision(EventStatus.REJECTED, player_only_reason, metadata)

    if event.event_type in MASTER_ONLY_EVENT_TYPES and request.actor_type.lower() not in MASTER_ACTOR_TYPES:
        metadata.update(
            {
                "audit_review": True,
                "review_severity": "P0",
                "auth_boundary": "master_only_event",
            }
        )
        return EventDecision(
            EventStatus.REJECTED,
            f"{event.event_type} requires master auth context",
            metadata,
        )

    review_reason = event.payload.get("review_reason") or event.payload.get("reason")
    if event.payload.get("requires_master_review") is True:
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            str(review_reason or "client requested master review"),
            metadata,
        )

    if event.event_type == "pve_completed":
        return _decide_pve_completed(connection, request, event, metadata)
    if event.event_type == "act_unlocked_offline":
        return _decide_act_unlocked_offline(connection, event, metadata)
    if event.event_type == "reward_approval_requested":
        return _decide_reward_approval_requested(connection, event, metadata)
    if event.event_type in {"qr_attempt", "qr_scene_started"}:
        return _decide_qr_runtime_event(event, metadata)
    if event.event_type == "paper_recovered":
        return _decide_paper_recovered(connection, event, metadata)

    return EventDecision(
        EventStatus.NEEDS_MASTER_REVIEW,
        f"unsupported event_type: {event.event_type}",
        metadata,
    )


def _decide_pve_completed(
    connection: sqlite3.Connection,
    request: EventSyncRequest,
    event: EventSyncEvent,
    metadata: dict[str, Any],
) -> EventDecision:
    player_only_reason = _player_only_sync_scope_reason(connection, request, event.event_type)
    if player_only_reason is not None:
        metadata.update(
            {
                "audit_review": True,
                "review_severity": "P0",
                "auth_boundary": "player_only_mobile_event",
            }
        )
        return EventDecision(EventStatus.REJECTED, player_only_reason, metadata)

    for field_name in ("qr_id", "scenario_id", "result"):
        if not event.payload.get(field_name):
            return EventDecision(EventStatus.REJECTED, f"missing pve field: {field_name}", metadata)

    result = str(event.payload["result"])
    if result not in PVE_RESULTS:
        return EventDecision(EventStatus.REJECTED, f"unsupported pve result: {result}", metadata)

    qr_id = str(event.payload["qr_id"])
    scenario_id = str(event.payload["scenario_id"])
    metadata.update({"qr_id": qr_id, "scenario_id": scenario_id, "result": result})

    qr_row = _fetch_optional_row(
        connection,
        "qr_objects",
        "SELECT scenario_id, act_id FROM qr_objects WHERE qr_id = ?",
        (qr_id,),
    )
    if qr_row is None:
        return EventDecision(EventStatus.NEEDS_MASTER_REVIEW, f"unknown qr_id: {qr_id}", metadata)
    if str(qr_row["scenario_id"]) != scenario_id:
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            f"qr scenario mismatch: {qr_id}",
            metadata,
        )
    metadata["act_id"] = qr_row["act_id"]
    creation_authority_reason = _pve_event_creation_authority_reason(
        connection,
        event,
        act_id=str(qr_row["act_id"]),
    )
    if creation_authority_reason is not None:
        metadata["audit_review"] = True
        metadata["review_severity"] = "P1"
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            creation_authority_reason,
            metadata,
        )
    roll_source = _pve_payload_roll_source(event.payload)
    if roll_source:
        metadata["roll_source"] = roll_source
    paper_recovered_pve = (
        metadata.get("source") == "paper_recovered"
        and metadata.get("recovered_event_type") == "pve_completed"
    )
    if (
        roll_source in MASTER_RECOVERED_ROLL_SOURCES
        and request.actor_type.lower() not in MASTER_ACTOR_TYPES
        and not paper_recovered_pve
    ):
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            "master/paper recovered pve roll source requires master auth context",
            metadata,
        )

    validation = validate_pve_completion(
        connection,
        player_id=request.actor_id,
        payload=event.payload,
    )
    metadata.update(validation.metadata)
    if validation.status == "rejected":
        return EventDecision(EventStatus.REJECTED, validation.reason, metadata)
    if validation.status == "needs_master_review":
        return EventDecision(EventStatus.NEEDS_MASTER_REVIEW, validation.reason, metadata)
    duplicate_check_reason = _pve_duplicate_check_reason(
        connection,
        actor_id=request.actor_id,
        payload=event.payload,
    )
    if duplicate_check_reason is not None:
        return EventDecision(EventStatus.NEEDS_MASTER_REVIEW, duplicate_check_reason, metadata)

    if result != "success":
        return EventDecision(EventStatus.ACCEPTED, None, metadata)

    scenario_row = _fetch_optional_row(
        connection,
        "pve_scenarios",
        "SELECT reward_id FROM pve_scenarios WHERE scenario_id = ?",
        (scenario_id,),
    )
    if scenario_row is None:
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            f"unknown pve scenario_id: {scenario_id}",
            metadata,
        )
    scenario_reward_id = str(scenario_row["reward_id"] or "").strip()
    client_has_reward_id = "reward_id" in event.payload
    client_reward_id = str(event.payload.get("reward_id") or "").strip()
    metadata["scenario_reward_id"] = scenario_reward_id or None
    if client_has_reward_id:
        metadata["client_reward_id"] = client_reward_id or None
    if not scenario_reward_id:
        metadata["reward_id"] = None
        metadata["reward_status"] = "none"
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            "pve scenario has no reward_id",
            metadata,
        )
    if client_has_reward_id and client_reward_id != scenario_reward_id:
        metadata["reward_id"] = scenario_reward_id
        metadata["reward_status"] = "none"
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            f"pve reward_id mismatch for scenario {scenario_id}",
            metadata,
        )

    return _decide_pve_reward(connection, scenario_reward_id, metadata)


def _pve_duplicate_check_reason(
    connection: sqlite3.Connection,
    *,
    actor_id: str,
    payload: dict[str, Any],
) -> str | None:
    if _pve_payload_roll_source(payload) != APP_GENERATED_ROLL_SOURCE:
        return None
    check_id = _pve_payload_check_id(payload)
    if not check_id:
        return None
    roll_value = _pve_payload_roll_value(payload)
    roll_id = _pve_payload_roll_id(payload)
    rows = connection.execute(
        """
        SELECT event_id, payload_json
        FROM events
        WHERE actor_id = ?
          AND event_type = 'pve_completed'
          AND status IN (?, ?, ?)
        ORDER BY server_event_id
        """,
        (
            actor_id,
            EventStatus.ACCEPTED.value,
            EventStatus.PENDING_MASTER_APPROVAL.value,
            EventStatus.NEEDS_MASTER_REVIEW.value,
        ),
    ).fetchall()
    for row in rows:
        prior_payload = _json_loads_dict(row["payload_json"])
        if _pve_payload_check_id(prior_payload) != check_id:
            continue
        prior_roll_value = _pve_payload_roll_value(prior_payload)
        prior_roll_id = _pve_payload_roll_id(prior_payload)
        if prior_roll_value != roll_value or prior_roll_id != roll_id:
            return "pve check_id already has a different d20 roll and needs master review"
        return "duplicate pve roll for same check_id requires master review"
    return None


def _pve_payload_roll_entry(payload: dict[str, Any]) -> dict[str, Any]:
    roll_log = payload.get("roll_log", [])
    if isinstance(roll_log, list) and roll_log and isinstance(roll_log[0], dict):
        return roll_log[0]
    return {}


def _pve_payload_roll_source(payload: dict[str, Any]) -> str:
    roll_entry = _pve_payload_roll_entry(payload)
    return str(roll_entry.get("source") or payload.get("roll_source") or "")


def _pve_payload_check_id(payload: dict[str, Any]) -> str:
    roll_entry = _pve_payload_roll_entry(payload)
    return str(roll_entry.get("check_id") or payload.get("check_id") or "")


def _pve_payload_roll_id(payload: dict[str, Any]) -> str:
    roll_entry = _pve_payload_roll_entry(payload)
    return str(roll_entry.get("roll_id") or payload.get("roll_id") or "")


def _pve_payload_roll_value(payload: dict[str, Any]) -> int:
    roll_entry = _pve_payload_roll_entry(payload)
    if "roll_value" in roll_entry:
        return _to_int(roll_entry["roll_value"])
    if "roll" in roll_entry:
        return _to_int(roll_entry["roll"])
    if "roll" in payload:
        return _to_int(payload["roll"])
    return 0


def _json_loads_dict(raw_json: object) -> dict[str, Any]:
    try:
        parsed = json.loads(str(raw_json or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _to_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _decide_act_unlocked_offline(
    connection: sqlite3.Connection, event: EventSyncEvent, metadata: dict[str, Any]
) -> EventDecision:
    act_id = event.payload.get("act_id")
    code = event.payload.get("code")
    supplied_hash = event.payload.get("code_sha256") or event.payload.get("verifier_sha256")
    if not act_id or (not code and not supplied_hash):
        return EventDecision(EventStatus.REJECTED, "missing act unlock act_id or code", metadata)

    metadata.update(
        {
            "act_id": str(act_id),
            "code_supplied": bool(code),
            "code_sha256_supplied": bool(supplied_hash),
        }
    )
    row = _fetch_optional_row(
        connection,
        "act_unlock_codes",
        "SELECT unlock_id, code FROM act_unlock_codes WHERE act_id = ?",
        (str(act_id),),
    )
    if row is None:
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            f"unknown act unlock target: {act_id}",
            metadata,
        )

    metadata["unlock_id"] = row["unlock_id"]
    authority_reason = _act_unlock_authority_reason(connection, str(act_id))
    if authority_reason is not None:
        return EventDecision(EventStatus.REJECTED, authority_reason, metadata)
    expected_code = str(row["code"]).strip().upper()
    expected_hash = hashlib.sha256(expected_code.encode("utf-8")).hexdigest()
    supplied_code_hash = (
        hashlib.sha256(str(code).strip().upper().encode("utf-8")).hexdigest()
        if code
        else str(supplied_hash).strip().lower()
    )
    if supplied_code_hash != expected_hash:
        return EventDecision(EventStatus.REJECTED, "invalid act unlock code", metadata)
    return EventDecision(EventStatus.ACCEPTED, None, metadata)


def _decide_reward_approval_requested(
    connection: sqlite3.Connection, event: EventSyncEvent, metadata: dict[str, Any]
) -> EventDecision:
    reward_id = event.payload.get("reward_id")
    if not reward_id:
        return EventDecision(EventStatus.REJECTED, "missing reward_id", metadata)
    return _decide_reward(connection, str(reward_id), metadata)


def _decide_reward(
    connection: sqlite3.Connection, reward_id: str, metadata: dict[str, Any]
) -> EventDecision:
    metadata["reward_id"] = reward_id
    row = _fetch_optional_row(
        connection,
        "rewards",
        "SELECT reward_id, rarity, approval_policy FROM rewards WHERE reward_id = ?",
        (reward_id,),
    )
    if row is None:
        return EventDecision(EventStatus.NEEDS_MASTER_REVIEW, f"unknown reward_id: {reward_id}", metadata)

    approval_policy = str(row["approval_policy"])
    metadata.update(
        {
            "reward_rarity": row["rarity"],
            "reward_approval_policy": approval_policy,
        }
    )
    if approval_policy == EventStatus.PENDING_MASTER_APPROVAL.value:
        metadata["reward_status"] = EventStatus.PENDING_MASTER_APPROVAL.value
        return EventDecision(
            EventStatus.PENDING_MASTER_APPROVAL,
            "reward requires master approval",
            metadata,
        )
    metadata["reward_status"] = "auto"
    return EventDecision(EventStatus.ACCEPTED, None, metadata)


def _decide_pve_reward(
    connection: sqlite3.Connection, reward_id: str, metadata: dict[str, Any]
) -> EventDecision:
    return _decide_reward(connection, reward_id, metadata)


def _decide_qr_runtime_event(
    event: EventSyncEvent,
    metadata: dict[str, Any],
) -> EventDecision:
    review_reason = event.payload.get("review_reason") or event.payload.get("reason")
    local_status = str(event.payload.get("local_status") or event.payload.get("status") or "")
    metadata.update(
        {
            "qr_id": event.payload.get("qr_id"),
            "manual_code": event.payload.get("manual_code"),
            "normalized_code": event.payload.get("normalized_code"),
            "source": event.payload.get("source"),
            "local_status": local_status or None,
            "review_reason": review_reason,
        }
    )
    if review_reason in {"honesty_violation_suspected", "manual_rate_limit"}:
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            str(review_reason),
            metadata,
        )
    if local_status == EventStatus.NEEDS_MASTER_REVIEW.value:
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            str(review_reason or "qr attempt requires master review"),
            metadata,
        )
    return EventDecision(EventStatus.ACCEPTED, None, metadata)


def _decide_paper_recovered(
    connection: sqlite3.Connection,
    event: EventSyncEvent,
    metadata: dict[str, Any],
) -> EventDecision:
    metadata["source"] = "paper_recovered"
    source_form_type = str(event.payload.get("source_form_type") or "").strip()
    paper_form_id = str(event.payload.get("paper_form_id") or "").strip()
    metadata.update(
        {
            "paper_form_id": paper_form_id or None,
            "source_form_type": source_form_type or None,
            "conflict_status": event.payload.get("conflict_status"),
        }
    )
    if not source_form_type:
        return EventDecision(
            EventStatus.REJECTED,
            "paper recovery missing required field: source_form_type",
            metadata,
        )

    form = _paper_form_definition(connection, source_form_type)
    if form is None:
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            f"unknown paper source_form_type: {source_form_type}",
            metadata,
        )
    required_fields = _paper_required_fields(form)
    if required_fields is None:
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            f"paper form definition is invalid: {source_form_type}",
            metadata,
        )
    missing = [
        field_name
        for field_name in required_fields
        if not _payload_has_value(event.payload, field_name)
    ]
    if missing:
        metadata["missing_fields"] = missing
        return EventDecision(
            EventStatus.REJECTED,
            f"paper recovery missing required field(s): {', '.join(missing)}",
            metadata,
        )

    timestamp_reason = _paper_timestamp_reason(event.payload.get("timestamp"))
    if timestamp_reason is not None:
        return EventDecision(EventStatus.REJECTED, timestamp_reason, metadata)

    duplicate_id = _paper_duplicate_event_id(connection, paper_form_id)
    if duplicate_id is not None:
        metadata["duplicate_paper_event_id"] = duplicate_id
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            f"duplicate paper_form_id requires master review: {paper_form_id}",
            metadata,
        )

    metadata.update(
        {
            "recovery_event_type": form["recovery_event_type"],
            "conflict_policy": form["conflict_policy"],
        }
    )
    conflict_status = str(event.payload.get("conflict_status") or "").strip().lower()
    if conflict_status not in {"clean", "no_conflict", "auto_apply", "safe_auto_apply"}:
        if source_form_type == "paper_pve_result":
            return _decide_paper_pve_result(
                connection,
                event,
                metadata,
                review_reason=str(
                    event.payload.get("reason")
                    or f"paper recovery conflict requires master review: {conflict_status}"
                ),
            )
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            str(event.payload.get("reason") or f"paper recovery conflict requires master review: {conflict_status}"),
            metadata,
        )

    if source_form_type == "paper_pve_result":
        return _decide_paper_pve_result(connection, event, metadata)

    metadata["paper_auto_applied"] = False
    metadata["review_severity"] = "P1"
    return EventDecision(
        EventStatus.NEEDS_MASTER_REVIEW,
        f"paper recovery form requires domain-specific master review: {source_form_type}",
        metadata,
    )


def _decide_paper_pve_result(
    connection: sqlite3.Connection,
    event: EventSyncEvent,
    metadata: dict[str, Any],
    *,
    review_reason: str | None = None,
) -> EventDecision:
    payload = event.payload
    player_id = str(payload.get("player_id") or "").strip()
    qr_id = str(payload.get("qr_id") or "").strip()
    result = str(payload.get("result") or "").strip()
    metadata.update(
        {
            "paper_recovered_player_id": player_id or None,
            "paper_recovered_qr_id": qr_id or None,
            "paper_recovered_result": result or None,
            "recovered_event_type": "pve_completed",
        }
    )
    if result not in PVE_RESULTS:
        metadata["paper_auto_applied"] = False
        return EventDecision(
            EventStatus.REJECTED,
            f"unsupported pve result: {result}",
            metadata,
        )

    recovered_payload, recovery_reason = _paper_pve_payload(connection, event, metadata)
    if recovered_payload is None:
        metadata["paper_auto_applied"] = False
        return EventDecision(EventStatus.NEEDS_MASTER_REVIEW, recovery_reason, metadata)

    recovered_request = EventSyncRequest(
        device_id="paper_recovery",
        actor_id=player_id,
        actor_type="player",
        events=[],
    )
    recovered_event = EventSyncEvent(
        event_id=f"{event.event_id}:pve_completed",
        client_sequence=event.client_sequence,
        created_at=event.created_at,
        event_type="pve_completed",
        payload=recovered_payload,
    )
    decision = _decide_pve_completed(
        connection,
        recovered_request,
        recovered_event,
        metadata,
    )
    can_apply = decision.status in {
        EventStatus.ACCEPTED,
        EventStatus.PENDING_MASTER_APPROVAL,
    }
    decision.metadata["paper_auto_applied"] = can_apply and review_reason is None
    if can_apply:
        decision.metadata["recovered_pve_payload"] = recovered_payload
    if review_reason is not None:
        decision.metadata["review_severity"] = "P1"
        return EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            review_reason,
            decision.metadata,
        )
    return decision


def _paper_pve_payload(
    connection: sqlite3.Connection,
    event: EventSyncEvent,
    metadata: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    payload = event.payload
    player_id = str(payload.get("player_id") or "").strip()
    qr_id = str(payload.get("qr_id") or "").strip()
    result = str(payload.get("result") or "").strip()
    roll_value = _paper_roll_value(payload)
    if roll_value is None:
        metadata["paper_recovered_roll"] = None
        return (
            None,
            "paper pve recovery requires roll or roll_log evidence, or explicit master override review",
        )
    timestamp = _parse_server_time(str(payload.get("timestamp") or ""))
    unlock_source = str(payload.get("unlock_source") or "") or None
    check_id = f"paper:{str(payload.get('paper_form_id') or event.event_id)}"

    last_reason = f"paper pve result cannot be replayed against current scenario: {result}"
    try:
        recovered = resolve_pve_scene(
            connection,
            player_id=player_id,
            qr_id=qr_id,
            roll=roll_value,
            result_override="timeout" if result == "timeout" else None,
            unlock_source=unlock_source,
            check_id=check_id,
            roll_source="paper_recovered",
            now=timestamp,
        )
    except LookupError as exc:
        return None, str(exc)
    if str(recovered.get("result") or "") != result:
        return None, last_reason
    _overlay_paper_pve_claims(recovered, payload)
    recovered.update(
        {
            "paper_form_id": payload.get("paper_form_id"),
            "paper_operator": payload.get("operator"),
            "paper_reason": payload.get("reason"),
            "paper_recovered_event_id": event.event_id,
        }
    )
    metadata["paper_recovered_roll"] = roll_value
    return recovered, ""


def _paper_roll_value(payload: dict[str, Any]) -> int | None:
    for field_name in ("roll", "roll_value"):
        if _payload_has_value(payload, field_name):
            roll = _to_int(payload.get(field_name))
            if 1 <= roll <= 20:
                return roll
    roll_log = payload.get("roll_log")
    if isinstance(roll_log, list) and roll_log and isinstance(roll_log[0], dict):
        roll_entry = roll_log[0]
        for field_name in ("roll", "roll_value", "value"):
            if _payload_has_value(roll_entry, field_name):
                roll = _to_int(roll_entry.get(field_name))
                if 1 <= roll <= 20:
                    return roll
    return None


def _overlay_paper_pve_claims(recovered: dict[str, Any], payload: dict[str, Any]) -> None:
    for field_name in ("scenario_id", "reward_id", "physical_presence_confirmed"):
        if field_name in payload:
            recovered[field_name] = payload[field_name]


def _record_event_log(
    connection: sqlite3.Connection,
    request: EventSyncRequest,
    event: EventSyncEvent,
    decision: EventDecision,
    server_event_id: int,
) -> None:
    connection.execute(
        """
        INSERT INTO event_log (event_type, payload_json, source)
        VALUES (?, ?, ?)
        """,
        (
            event.event_type,
            _json_dumps(
                {
                    "server_event_id": server_event_id,
                    "event_id": event.event_id,
                    "device_id": request.device_id,
                    "actor_id": request.actor_id,
                    "actor_type": request.actor_type,
                    "status": decision.status.value,
                    "reason": decision.reason,
                    "metadata": decision.metadata,
                }
            ),
            _source_for_event(event),
        ),
    )


def _record_review_if_needed(
    connection: sqlite3.Connection,
    event: EventSyncEvent,
    decision: EventDecision,
    server_event_id: int,
) -> None:
    if decision.status != EventStatus.NEEDS_MASTER_REVIEW and not decision.metadata.get("audit_review"):
        return
    connection.execute(
        """
        INSERT INTO event_reviews (server_event_id, event_id, status, reason, severity)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            server_event_id,
            event.event_id,
            decision.status.value,
            decision.reason or "needs master review",
            str(decision.metadata.get("review_severity") or "P2"),
        ),
    )


def _record_pending_reward_if_needed(
    connection: sqlite3.Connection,
    request: EventSyncRequest,
    event: EventSyncEvent,
    decision: EventDecision,
    server_event_id: int,
) -> EventDecision:
    if decision.status != EventStatus.PENDING_MASTER_APPROVAL:
        return decision
    reward_id = decision.metadata.get("reward_id")
    if not reward_id:
        return decision
    player_id = _side_effect_player_id(request, decision)
    approval_id = f"approval_event_{server_event_id}"
    try:
        create_pending_reward_approval(
            connection,
            approval_id=approval_id,
            reward_id=str(reward_id),
            player_id=player_id,
            source_event_id=server_event_id,
        )
        return decision
    except AssetContractError as exc:
        metadata = {
            **decision.metadata,
            "reward_approval_conflict": {
                "code": exc.code,
                "message": exc.message,
                "reward_id": str(reward_id),
            },
        }
        review_decision = EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            exc.message,
            metadata,
        )
        connection.execute(
            """
            UPDATE events
            SET status = ?,
                reason = ?,
                metadata_json = ?,
                applied_at = NULL
            WHERE server_event_id = ?
            """,
            (
                review_decision.status.value,
                review_decision.reason,
                _json_dumps(review_decision.metadata),
                server_event_id,
            ),
        )
        _record_review_if_needed(
            connection,
            event,
            review_decision,
            server_event_id,
        )
        log_payload = {
            "server_event_id": server_event_id,
            "actor_id": player_id,
            "reward_id": str(reward_id),
            "reason": exc.message,
            "code": exc.code,
        }
        connection.execute(
            """
            INSERT INTO event_log (event_type, payload_json, source)
            VALUES ('reward_approval_conflict_review', ?, 'event_sync')
            """,
            (_json_dumps(log_payload),),
        )
        return review_decision


def _apply_pve_side_effects_if_needed(
    connection: sqlite3.Connection,
    request: EventSyncRequest,
    event: EventSyncEvent,
    decision: EventDecision,
    server_event_id: int,
    received_at: str,
) -> EventDecision:
    pve_payload = _side_effect_pve_payload(event, decision)
    if pve_payload is None:
        return decision
    if decision.status not in {
        EventStatus.ACCEPTED,
        EventStatus.PENDING_MASTER_APPROVAL,
    }:
        return decision
    player_id = _side_effect_player_id(request, decision)
    try:
        applied = apply_pve_completion_side_effects(
            connection,
            player_id=player_id,
            payload=pve_payload,
            metadata=decision.metadata,
            status=decision.status.value,
            server_event_id=server_event_id,
            now=_parse_server_time(received_at),
        )
    except PveSideEffectConflictError as exc:
        metadata = {
            **decision.metadata,
            "side_effect_conflict": str(exc),
            "audit_review": True,
            "review_severity": "P1",
        }
        review_decision = EventDecision(
            EventStatus.NEEDS_MASTER_REVIEW,
            str(exc),
            metadata,
        )
        connection.execute(
            """
            UPDATE events
            SET status = ?,
                reason = ?,
                metadata_json = ?,
                applied_at = NULL
            WHERE server_event_id = ?
            """,
            (
                review_decision.status.value,
                review_decision.reason,
                _json_dumps(review_decision.metadata),
                server_event_id,
            ),
        )
        _record_review_if_needed(connection, event, review_decision, server_event_id)
        return review_decision
    decision.metadata["pve_side_effects"] = applied
    connection.execute(
        """
        UPDATE events
        SET metadata_json = ?
        WHERE server_event_id = ?
        """,
        (_json_dumps(decision.metadata), server_event_id),
    )
    return decision


def _side_effect_player_id(request: EventSyncRequest, decision: EventDecision) -> str:
    recovered_player_id = str(decision.metadata.get("paper_recovered_player_id") or "").strip()
    return recovered_player_id or request.actor_id


def _side_effect_pve_payload(
    event: EventSyncEvent,
    decision: EventDecision,
) -> dict[str, Any] | None:
    if event.event_type == "pve_completed":
        return event.payload
    if (
        event.event_type == "paper_recovered"
        and decision.metadata.get("recovered_event_type") == "pve_completed"
    ):
        payload = decision.metadata.get("recovered_pve_payload")
        return payload if isinstance(payload, dict) else None
    return None


def _record_client_sync_state(
    connection: sqlite3.Connection,
    request: EventSyncRequest,
    server_time: str,
    tracker: dict[str, Any],
) -> None:
    if not request.events:
        return
    last_sequence = int(tracker.get("highest_contiguous") or tracker.get("last_sequence") or 0)
    connection.execute(
        """
        INSERT INTO client_sync_state (
            client_id, player_id, snapshot_version, last_seen_at, last_event_sequence
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(client_id) DO UPDATE SET
            player_id = excluded.player_id,
            snapshot_version = excluded.snapshot_version,
            last_seen_at = excluded.last_seen_at,
            last_event_sequence = CASE
                WHEN excluded.last_event_sequence > client_sync_state.last_event_sequence
                THEN excluded.last_event_sequence
                ELSE client_sync_state.last_event_sequence
            END
        """,
        (
            request.device_id,
            request.actor_id,
            latest_snapshot_version(connection),
            server_time,
            last_sequence,
        ),
    )


def _actor_validation_reason(
    connection: sqlite3.Connection, actor_id: str, actor_type: str
) -> str | None:
    normalized_actor_type = actor_type.lower()
    if normalized_actor_type in MASTER_ACTOR_TYPES:
        return None
    if normalized_actor_type not in PLAYER_ROLE_TYPES:
        return f"unsupported actor_type: {actor_type}"
    if not _table_exists(connection, "players"):
        return None

    row = connection.execute(
        "SELECT role_type FROM players WHERE player_id = ?",
        (actor_id,),
    ).fetchone()
    if row is None:
        return f"unknown actor_id: {actor_id}"
    if normalized_actor_type != "player" and str(row["role_type"]) != normalized_actor_type:
        return f"actor_type mismatch: {actor_type}"
    return None


def _player_only_sync_scope_reason(
    connection: sqlite3.Connection,
    request: EventSyncRequest,
    event_type: str,
) -> str | None:
    if event_type not in PLAYER_ONLY_SYNC_EVENT_TYPES:
        return None
    if not _table_exists(connection, "players"):
        return None
    canonical_role_type = _canonical_player_role_type(connection, request.actor_id)
    if canonical_role_type in MOBILE_PLAYER_ROLE_TYPES:
        return None
    role_label = canonical_role_type or request.actor_type
    return (
        f"{event_type} requires witcher or sorceress player actor; "
        f"got {role_label}"
    )


def _canonical_player_role_type(connection: sqlite3.Connection, actor_id: str) -> str | None:
    if not _table_exists(connection, "players"):
        return None
    row = connection.execute(
        "SELECT role_type FROM players WHERE player_id = ?",
        (actor_id,),
    ).fetchone()
    if row is None:
        return None
    return str(row["role_type"])


def _fetch_optional_row(
    connection: sqlite3.Connection,
    table_name: str,
    sql: str,
    parameters: tuple[Any, ...],
) -> sqlite3.Row | None:
    if not _table_exists(connection, table_name):
        return None
    return connection.execute(sql, parameters).fetchone()


def _act_unlock_authority_reason(connection: sqlite3.Connection, act_id: str) -> str | None:
    if not _table_exists(connection, "act_history"):
        return "act unlock code has not been revealed by masters"
    row = connection.execute(
        """
        SELECT physical_announcement_state, unlock_revealed_at
        FROM act_history
        WHERE act_id = ?
        """,
        (act_id,),
    ).fetchone()
    if row is None:
        return "act unlock code has not been revealed by masters"
    if not _is_announced(row["physical_announcement_state"]):
        return "act physical announcement is not recorded"
    if not row["unlock_revealed_at"]:
        return "act unlock code has not been revealed by masters"
    return None


def _pve_event_creation_authority_reason(
    connection: sqlite3.Connection,
    event: EventSyncEvent,
    *,
    act_id: str,
) -> str | None:
    if act_id == "act1" or not _table_exists(connection, "act_history"):
        return None
    unlock_source = str(event.payload.get("unlock_source") or "")
    row = connection.execute(
        """
        SELECT physical_announcement_at, unlock_revealed_at
        FROM act_history
        WHERE act_id = ?
        """,
        (act_id,),
    ).fetchone()
    if row is None:
        return None
    authority_at_raw = (
        row["unlock_revealed_at"]
        if unlock_source == "master_unlock_code"
        else row["physical_announcement_at"]
    )
    if not authority_at_raw:
        return None
    event_created_at = _parse_event_created_at(event.created_at)
    authority_at = _parse_server_time(str(authority_at_raw))
    if event_created_at is None or authority_at is None:
        return None
    if event_created_at < authority_at:
        return "pve event was created before act unlock was authoritative"
    return None


def _is_announced(value: object) -> bool:
    return str(value or "").strip().lower() in {
        "announced",
        "completed",
        "done",
        "physical_announced",
    }


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


def _source_for_event(event: EventSyncEvent) -> str:
    if event.event_type == "paper_recovered":
        return "paper_recovered"
    if event.event_type in {"qr_attempt", "qr_scene_started"}:
        return "mobile_qr"
    return "event_sync"


def _paper_form_definition(
    connection: sqlite3.Connection, source_form_type: str
) -> sqlite3.Row | None:
    if not _table_exists(connection, "paper_forms"):
        return None
    return connection.execute(
        """
        SELECT form_type, required_fields_json, recovery_event_type, conflict_policy
        FROM paper_forms
        WHERE form_type = ?
        LIMIT 1
        """,
        (source_form_type,),
    ).fetchone()


def _paper_required_fields(form: sqlite3.Row) -> list[str] | None:
    try:
        parsed = json.loads(str(form["required_fields_json"] or "[]"))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    return [str(item) for item in parsed]


def _paper_timestamp_reason(value: object) -> str | None:
    try:
        datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return "paper recovery timestamp must be ISO-8601"
    return None


def _paper_duplicate_event_id(connection: sqlite3.Connection, paper_form_id: str) -> str | None:
    if not paper_form_id:
        return None
    rows = connection.execute(
        """
        SELECT event_id, status, payload_json
        FROM events
        WHERE event_type = 'paper_recovered'
        ORDER BY server_event_id
        """
    ).fetchall()
    for row in rows:
        if str(row["status"]) == EventStatus.REJECTED.value:
            continue
        try:
            payload = json.loads(str(row["payload_json"] or "{}"))
        except json.JSONDecodeError:
            continue
        if str(payload.get("paper_form_id") or "") == paper_form_id:
            return str(row["event_id"])
    return None


def _payload_has_value(payload: dict[str, Any], field_name: str) -> bool:
    value = payload.get(field_name)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _parse_server_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_event_created_at(value: str | int | float) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC)
    return _parse_server_time(str(value))
