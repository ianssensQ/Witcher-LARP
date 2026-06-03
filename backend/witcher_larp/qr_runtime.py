"""QR/manual-ID lookup, rate-limit and review-context helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import re
import sqlite3


DEFAULT_MANUAL_RATE_LIMIT = "5_per_minute"
DEFAULT_RATE_WINDOW_SECONDS = 60
VALID_SOURCES = {"qr_scan", "manual_id"}


@dataclass(frozen=True)
class QrLookupRequest:
    code: str
    player_id: str | None
    device_id: str | None
    source: str
    physical_presence_confirmed: bool


def ensure_qr_runtime_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS qr_attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT,
            device_id TEXT,
            input_code TEXT NOT NULL,
            normalized_code TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT,
            qr_id TEXT,
            event_context_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )
        """
    )


def has_qr_content(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'qr_objects'
        """
    ).fetchone()
    return row is not None


def lookup_qr_runtime(
    connection: sqlite3.Connection, request: QrLookupRequest
) -> dict[str, object]:
    ensure_qr_runtime_schema(connection)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    source = request.source if request.source in VALID_SOURCES else "manual_id"
    normalized_code = normalize_qr_code(request.code)
    rate_limit_count, rate_window_seconds = fetch_manual_rate_limit(connection)
    bad_attempts_before = _bad_lookup_attempt_count(
        connection,
        player_id=request.player_id,
        device_id=request.device_id,
        since=_iso_before(rate_window_seconds),
    )
    locked_by_manual_rate = (
        _is_rate_limited_source(source, request)
        and bad_attempts_before >= rate_limit_count
    )

    qr = _fetch_qr(connection, normalized_code)
    act = _fetch_by_id(connection, "acts", "act_id", qr["act_id"]) if qr else None
    act_lock_reason = _act_lock_reason(connection, qr, act) if qr else None
    scenario = (
        _fetch_by_id(connection, "pve_scenarios", "scenario_id", qr["scenario_id"])
        if qr and act_lock_reason is None
        else None
    )

    if locked_by_manual_rate:
        status = "needs_master_review"
        reason = "manual_rate_limit"
        event_type = "qr_attempt"
    elif qr is None:
        would_exceed = (
            _is_rate_limited_source(source, request)
            and bad_attempts_before + 1 >= rate_limit_count
        )
        status = "needs_master_review" if would_exceed else "unknown_qr"
        reason = "manual_rate_limit" if would_exceed else "unknown_qr"
        event_type = "qr_attempt"
    elif act_lock_reason is not None:
        status = "locked"
        reason = act_lock_reason
        event_type = "qr_attempt"
    elif qr.get("physical_presence_required") == "true" and not request.physical_presence_confirmed:
        status = "needs_master_review"
        reason = "honesty_violation_suspected"
        event_type = "qr_attempt"
    else:
        status = "ok"
        reason = None
        event_type = "qr_scene_started"

    context = _event_context(
        request=request,
        source=source,
        normalized_code=normalized_code,
        status=status,
        reason=reason,
        event_type=event_type,
        qr=qr,
        scenario=scenario,
        act=act,
        act_locked=act_lock_reason is not None,
        created_at=now,
    )
    _record_attempt(
        connection,
        request=request,
        normalized_code=normalized_code,
        source=source,
        status=status,
        reason=reason,
        qr_id=str(qr["qr_id"]) if qr else None,
        event_context=context,
        created_at=now,
    )
    attempts_in_window = _bad_lookup_attempt_count(
        connection,
        player_id=request.player_id,
        device_id=request.device_id,
        since=_iso_before(rate_window_seconds),
    )

    return {
        "status": status,
        "event_type": event_type,
        "reason": reason,
        "message": _message_for(status, reason),
        "qr": _qr_payload(qr, locked=act_lock_reason is not None),
        "scenario": scenario,
        "act": _act_payload(act, locked=act_lock_reason is not None),
        "event_context": context,
        "attempts_in_window": attempts_in_window,
        "rate_limit": {
            "limit": rate_limit_count,
            "window_seconds": rate_window_seconds,
            "lockout_until": _lockout_until(rate_window_seconds) if reason == "manual_rate_limit" else None,
        },
    }


def normalize_qr_code(value: str) -> str:
    text = value.strip()
    for marker in (
        "witcher-larp://qr?id=",
        "witcher-larp://qr?code=",
        "witcher-larp://scene?qr=",
    ):
        if text.lower().startswith(marker):
            text = text[len(marker) :]
            break
    return text.strip().upper()


def fetch_manual_rate_limit(connection: sqlite3.Connection) -> tuple[int, int]:
    rate_limit = DEFAULT_MANUAL_RATE_LIMIT
    if _table_exists(connection, "qr_policies"):
        row = connection.execute(
            """
            SELECT manual_rate_limit
            FROM qr_policies
            WHERE manual_entry_allowed = 'true'
            ORDER BY _row_number
            LIMIT 1
            """
        ).fetchone()
        if row is not None and row["manual_rate_limit"]:
            rate_limit = str(row["manual_rate_limit"])

    match = re.fullmatch(r"(\d+)_per_(minute|hour)", rate_limit)
    if match is None:
        return 5, 60
    limit = int(match.group(1))
    window = 60 if match.group(2) == "minute" else 3600
    return limit, window


def _fetch_qr(connection: sqlite3.Connection, normalized_code: str) -> dict[str, str] | None:
    row = connection.execute(
        """
        SELECT *
        FROM qr_objects
        WHERE UPPER(manual_code) = ?
        LIMIT 1
        """,
        (normalized_code,),
    ).fetchone()
    return _row_to_dict(row)


def _fetch_by_id(
    connection: sqlite3.Connection, table: str, id_column: str, row_id: str
) -> dict[str, str] | None:
    row = connection.execute(
        f'SELECT * FROM "{table}" WHERE "{id_column}" = ? LIMIT 1',
        (row_id,),
    ).fetchone()
    return _row_to_dict(row)


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, str] | None:
    if row is None:
        return None
    return {
        key: row[key]
        for key in row.keys()
        if key not in {"_import_run_id", "_row_number"}
    }


def _qr_payload(qr: dict[str, str] | None, *, locked: bool) -> dict[str, object] | None:
    if qr is None:
        return None
    if not locked:
        return qr
    return {
        "qr_id": qr.get("qr_id"),
        "qr_mode": qr.get("qr_mode"),
        "act_id": qr.get("act_id"),
        "requires_act_unlock": True,
        "locked": True,
    }


def _act_payload(act: dict[str, str] | None, *, locked: bool) -> dict[str, object] | None:
    if act is None:
        return None
    if not locked:
        return act
    return {
        "act_id": act.get("act_id"),
        "unlock_required": act.get("unlock_required") == "true",
        "requires_act_unlock": True,
        "locked": True,
    }


def _event_context(
    *,
    request: QrLookupRequest,
    source: str,
    normalized_code: str,
    status: str,
    reason: str | None,
    event_type: str,
    qr: dict[str, str] | None,
    scenario: dict[str, str] | None,
    act: dict[str, str] | None,
    act_locked: bool,
    created_at: str,
) -> dict[str, object]:
    return {
        "event_type": event_type,
        "local_status": status,
        "review_reason": reason,
        "source": source,
        "input_code": request.code,
        "normalized_code": normalized_code,
        "player_id": request.player_id,
        "device_id": request.device_id,
        "qr_id": qr.get("qr_id") if qr else None,
        "manual_code": None if act_locked else qr.get("manual_code") if qr else None,
        "qr_mode": qr.get("qr_mode") if qr else None,
        "consumption_rule": None if act_locked else qr.get("consumption_rule") if qr else None,
        "act_id": qr.get("act_id") if qr else None,
        "scenario_id": None if act_locked else qr.get("scenario_id") if qr else None,
        "scene_type": scenario.get("scene_type") if scenario else None,
        "location_node_id": None if act_locked else qr.get("location_node_id") if qr else None,
        "physical_presence_required": qr.get("physical_presence_required") == "true" if qr else True,
        "physical_presence_confirmed": request.physical_presence_confirmed,
        "honesty_notice": "physical_presence_only",
        "requires_act_unlock": act_locked or (act.get("unlock_required") == "true" if act else False),
        "offline_instruction": None if act_locked else _offline_instruction(qr),
        "created_at": created_at,
    }


def _act_lock_reason(
    connection: sqlite3.Connection,
    qr: dict[str, str] | None,
    act: dict[str, str] | None,
) -> str | None:
    if qr is None:
        return None
    act_id = str(qr.get("act_id", ""))
    if act_id == "act1" or not act_id:
        return None
    if act is not None and act.get("unlock_required") != "true":
        return None
    if _act_has_authoritative_unlock(connection, act_id):
        return None
    return "requires_act_unlock"


def _act_has_authoritative_unlock(connection: sqlite3.Connection, act_id: str) -> bool:
    if not _table_exists(connection, "act_history"):
        return False
    row = connection.execute(
        """
        SELECT physical_announcement_state, unlock_revealed_at
        FROM act_history
        WHERE act_id = ?
        """,
        (act_id,),
    ).fetchone()
    return row is not None and (
        _is_announced(row["physical_announcement_state"]) or bool(row["unlock_revealed_at"])
    )


def _record_attempt(
    connection: sqlite3.Connection,
    *,
    request: QrLookupRequest,
    normalized_code: str,
    source: str,
    status: str,
    reason: str | None,
    qr_id: str | None,
    event_context: dict[str, object],
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO qr_attempts (
            player_id, device_id, input_code, normalized_code, source,
            status, reason, qr_id, event_context_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request.player_id,
            request.device_id,
            request.code,
            normalized_code,
            source,
            status,
            reason,
            qr_id,
            json.dumps(event_context, ensure_ascii=False, sort_keys=True),
            created_at,
        ),
    )
    connection.execute(
        """
        INSERT INTO event_log (event_type, payload_json, source, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            str(event_context["event_type"]),
            json.dumps(event_context, ensure_ascii=False, sort_keys=True),
            source,
            created_at,
        ),
    )


def _bad_lookup_attempt_count(
    connection: sqlite3.Connection,
    *,
    player_id: str | None,
    device_id: str | None,
    since: str,
) -> int:
    identity_clauses: list[str] = []
    parameters: list[object] = [since]
    if player_id:
        identity_clauses.append("player_id = ?")
        parameters.append(player_id)
    if device_id:
        identity_clauses.append("device_id = ?")
        parameters.append(device_id)
    if not identity_clauses:
        identity_filter = "(COALESCE(player_id, '') = '' AND COALESCE(device_id, '') = '')"
    else:
        identity_filter = "(" + " OR ".join(identity_clauses) + ")"

    row = connection.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM qr_attempts
        WHERE created_at >= ?
          AND {identity_filter}
          AND (
            source = 'manual_id'
            OR COALESCE(player_id, '') = ''
            OR COALESCE(device_id, '') = ''
          )
          AND (status = 'unknown_qr' OR reason = 'manual_rate_limit')
        """,
        tuple(parameters),
    ).fetchone()
    return int(row["count"]) if row is not None else 0


def _is_rate_limited_source(source: str, request: QrLookupRequest) -> bool:
    return source == "manual_id" or not request.player_id or not request.device_id


def _iso_before(seconds: int) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat(timespec="seconds")


def _lockout_until(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def _offline_instruction(qr: dict[str, str] | None) -> str | None:
    if qr is None:
        return None
    if qr.get("qr_mode") == "unique_object" or qr.get("consumption_rule") == "consume_once":
        return "success_take_physical_qr_failure_leave_it"
    return "repeatable_scene_no_physical_qr_consumption"


def _message_for(status: str, reason: str | None) -> str:
    if status == "ok":
        return "QR scene can start after confirmed physical presence."
    if reason == "requires_act_unlock":
        return "QR scene is locked until the act is physically announced or unlocked by masters."
    if reason == "honesty_violation_suspected":
        return "Physical presence was not confirmed; attempt needs master review."
    if reason == "manual_rate_limit":
        return "Too many wrong manual QR IDs; attempt needs master review."
    if status == "unknown_qr":
        return "Unknown QR/manual ID. Check the printed opaque code."
    return "QR attempt recorded."


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone()
    return row is not None


def _is_announced(value: object) -> bool:
    return str(value or "").strip().lower() in {
        "announced",
        "completed",
        "done",
        "physical_announced",
    }
