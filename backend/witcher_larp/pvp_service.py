"""Personal PvP and custom Gwent runtime service."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import sqlite3
from typing import Any
from uuid import uuid4

from .asset_service import AssetContractError
from .asset_service import assert_asset_unlocked, debit_asset_ownership, lock_owned_asset
from .asset_service import ownership_for_asset, settle_owned_asset_lock
from .gwent_effects import GWENT_ROWS, GWENT_WEATHER_BY_EFFECT
from .gwent_effects import is_gwent_effect_supported
from .runtime_schema import ensure_runtime_schema, log_event
from .timer_service import ensure_runtime_content_state


PVP_PLAYER_ROLES = {"witcher", "sorceress"}
ACTIVE_CHALLENGE_STATES = {"assigned", "queued", "deferred", "started", "needs_master_review"}
FINAL_CHALLENGE_STATES = {"resolved", "cancelled", "rejected"}
REFUNDABLE_PRE_START_REFUSALS = {"safety_stop", "unsafe_path", "force_majeure"}
GOLD_STAKE_ASSET_TYPE = "gold"
GOLD_STAKE_ASSET_ID = "gold"
GWENT_PENDING_ROUND_STATUS = "pending_player_submissions"
GWENT_ROUND_REVIEW_STATUS = "needs_master_review"
INCOMPLETE_ROUND_REVIEW_REASON = "incomplete_round_requires_master_review"
CONTRADICTORY_ROUND_REVIEW_REASON = "contradictory_round_submission_requires_master_review"
REVIEW_SEVERITY_BY_REASON = {
    "active_scene": "P2",
    "table_overload": "P2",
    "valid_ignore": "P2",
    "start_window_timeout": "P2",
    "double_loss_tie": "P2",
    INCOMPLETE_ROUND_REVIEW_REASON: "P1",
    CONTRADICTORY_ROUND_REVIEW_REASON: "P1",
    "safety_stop": "P0",
    "unsafe_path": "P1",
    "force_majeure": "P1",
}


class PvpError(ValueError):
    """Raised when a PvP operation cannot be accepted by the runtime."""


@dataclass(frozen=True)
class ChallengeCreateInput:
    challenger_id: str
    target_id: str
    stake: dict[str, Any]
    challenge_id: str | None = None
    mandatory: bool = True
    master_approval: bool = False
    source: str = "pvp_api"


@dataclass(frozen=True)
class ChallengeStartInput:
    challenge_id: str
    master_approval: bool = False
    mulligans_by_player: dict[str, list[str]] | None = None
    source: str = "pvp_api"


def ensure_pvp_runtime_state(connection: sqlite3.Connection) -> None:
    ensure_runtime_schema(connection)
    ensure_runtime_content_state(connection)
    now = _iso()
    if _table_exists(connection, "pvp_tables"):
        rows = connection.execute(
            """
            SELECT table_id, status, zone_name
            FROM pvp_tables
            ORDER BY _row_number
            """
        ).fetchall()
    else:
        rows = []

    if not rows:
        rows = [
            {"table_id": "pvp_table_1", "status": "open", "zone_name": "main_house_table"},
            {"table_id": "pvp_table_2", "status": "open", "zone_name": "main_house_table"},
        ]

    for row in rows:
        table_id = str(row["table_id"])
        status = str(row["status"] or "open")
        zone_name = str(row["zone_name"] or "main_house_table")
        connection.execute(
            """
            INSERT INTO pvp_table_runtime (
                table_id, status, zone_name, current_challenge_id,
                current_match_id, updated_at
            )
            VALUES (?, ?, ?, NULL, NULL, ?)
            ON CONFLICT(table_id) DO UPDATE SET
                zone_name = excluded.zone_name,
                updated_at = CASE
                    WHEN pvp_table_runtime.status = 'disabled'
                    THEN pvp_table_runtime.updated_at
                    ELSE excluded.updated_at
                END
            """,
            (table_id, status, zone_name, now),
        )

    throttle = _fetch_throttle_state(connection)
    rule = _fetch_throttle_rule(connection, str(throttle["mode"]))
    if rule is not None:
        connection.execute(
            """
            UPDATE pvp_throttle_state
            SET max_tables = ?,
                max_started_per_player_per_act = ?,
                final_lock_behavior = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (
                _to_int(rule["max_tables"]),
                _to_int(rule["max_started_per_player_per_act"]),
                str(rule["final_lock_behavior"]),
                now,
            ),
        )


def set_pvp_throttle_mode(
    connection: sqlite3.Connection,
    mode: str,
    *,
    operator: str = "master",
    source: str = "master_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    normalized = mode.strip().lower()
    rule = _fetch_throttle_rule(connection, normalized)
    if rule is None:
        raise PvpError(f"Unsupported PvP throttle mode: {mode}")
    current_time = now or datetime.now(UTC)
    connection.execute(
        """
        UPDATE pvp_throttle_state
        SET mode = ?,
            max_tables = ?,
            max_started_per_player_per_act = ?,
            final_lock_behavior = ?,
            updated_at = ?
        WHERE id = 1
        """,
        (
            normalized,
            _to_int(rule["max_tables"]),
            _to_int(rule["max_started_per_player_per_act"]),
            str(rule["final_lock_behavior"]),
            _iso(current_time),
        ),
    )
    payload = {
        "mode": normalized,
        "max_tables": _to_int(rule["max_tables"]),
        "max_started_per_player_per_act": _to_int(rule["max_started_per_player_per_act"]),
        "final_lock_behavior": str(rule["final_lock_behavior"]),
        "operator": operator,
        "updated_at": _iso(current_time),
    }
    log_event(connection, "pvp_throttle_changed", payload, source=source, created_at=current_time)
    return get_pvp_tables(connection)


def get_pvp_tables(connection: sqlite3.Connection) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    throttle = _fetch_throttle_state(connection)
    active_limit = int(throttle["max_tables"])
    tables = []
    for index, row in enumerate(
        connection.execute(
            """
            SELECT table_id, status, zone_name, current_challenge_id, current_match_id
            FROM pvp_table_runtime
            ORDER BY table_id
            """
        ).fetchall()
    ):
        effective_status = str(row["status"])
        if index >= active_limit and effective_status == "open":
            effective_status = "disabled_by_throttle"
        tables.append(
            {
                "table_id": row["table_id"],
                "status": effective_status,
                "runtime_status": row["status"],
                "zone_name": row["zone_name"],
                "current_challenge_id": row["current_challenge_id"],
                "current_match_id": row["current_match_id"],
            }
        )
    queued = [
        _challenge_row_to_dict(row)
        for row in connection.execute(
            """
            SELECT *
            FROM pvp_challenges
            WHERE status = 'queued'
            ORDER BY created_at, challenge_id
            """
        ).fetchall()
    ]
    return {"throttle": throttle, "tables": tables, "queued_challenges": queued}


def create_pvp_challenge(
    connection: sqlite3.Connection,
    request: ChallengeCreateInput,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    challenge_id = request.challenge_id or f"pvp_challenge_{uuid4().hex}"
    existing = _fetch_challenge(connection, challenge_id)
    if existing is not None:
        return _challenge_payload(connection, existing, duplicate=True)

    if request.challenger_id == request.target_id:
        raise PvpError("PvP challenge requires two different players.")
    challenger = _require_personal_pvp_player(connection, request.challenger_id)
    target = _require_personal_pvp_player(connection, request.target_id)
    if _final_lock_active(connection) and not request.master_approval:
        raise PvpError("New PvP challenges are locked after final lock.")
    if _active_challenge_exists(connection, request.challenger_id):
        raise PvpError(f"Player already has an active PvP challenge: {request.challenger_id}")
    if _active_challenge_exists(connection, request.target_id):
        raise PvpError(f"Player already has an active PvP challenge: {request.target_id}")

    rules = _gwent_rules(connection)
    _validate_player_gwent_preflight(connection, request.challenger_id, rules)
    _validate_player_gwent_preflight(connection, request.target_id, rules)

    act_id = _current_act_id(connection)
    stake = _validate_stake(request.stake)
    if _stake_locked(connection, stake["asset_type"], stake["asset_id"]):
        raise PvpError(f"Stake asset is already locked: {stake['asset_id']}")
    if _is_gold_stake(stake):
        _assert_gold_stake_available(
            connection,
            player_id=request.challenger_id,
            amount=_stake_quantity(stake),
        )
    else:
        try:
            assert_asset_unlocked(
                connection,
                asset_type=stake["asset_type"],
                asset_id=stake["asset_id"],
                owner_player_id=request.challenger_id,
                purpose="PvP stake",
            )
            _assert_stake_asset_owned(
                connection,
                stake=stake,
                owner_player_id=request.challenger_id,
            )
        except AssetContractError as exc:
            raise PvpError(exc.message) from exc

    if request.mandatory and not request.master_approval:
        _spend_challenge_token(connection, request.challenger_id, current_time)

    throttle = _fetch_throttle_state(connection)
    table = _available_table(connection, throttle)
    start_window_min = _start_window_minutes(connection, act_id)
    deadline = current_time + timedelta(minutes=start_window_min) if table is not None else None
    status = "assigned" if table is not None else "queued"
    table_id = str(table["table_id"]) if table is not None else None
    zone_name = _zone_for_assignment(connection, table)

    connection.execute(
        """
        INSERT INTO pvp_challenges (
            challenge_id, challenger_id, target_id, act_id, status, mandatory,
            stake_json, table_id, assigned_zone, start_window_deadline,
            master_approval, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            challenge_id,
            request.challenger_id,
            request.target_id,
            act_id,
            status,
            1 if request.mandatory else 0,
            _json_dumps(stake),
            table_id,
            zone_name,
            _iso(deadline) if deadline is not None else None,
            1 if request.master_approval else 0,
            _iso(current_time),
            _iso(current_time),
        ),
    )
    _lock_stake(
        connection,
        challenge_id=challenge_id,
        owner_player_id=request.challenger_id,
        pending_target_player_id=request.target_id,
        stake=stake,
        now=current_time,
    )
    if table is not None:
        _occupy_table(connection, table_id, challenge_id=challenge_id, match_id=None, now=current_time)

    event_type = "pvp_challenge_queued" if status == "queued" else "pvp_challenge_created"
    payload = {
        "challenge_id": challenge_id,
        "challenger_id": request.challenger_id,
        "target_id": request.target_id,
        "challenger_role": challenger["role_type"],
        "target_role": target["role_type"],
        "act_id": act_id,
        "mandatory": request.mandatory,
        "status": status,
        "table_id": table_id,
        "assigned_zone": zone_name,
        "start_window_deadline": _iso(deadline) if deadline is not None else None,
        "stake": stake,
        "pvp_tables": throttle["max_tables"],
        "throttle_mode": throttle["mode"],
        "balance_profile": "15_person_full_gwent",
    }
    log_event(connection, event_type, payload, source=request.source, created_at=current_time)
    return _challenge_payload(connection, _fetch_challenge_required(connection, challenge_id))


def start_pvp_challenge(
    connection: sqlite3.Connection,
    request: ChallengeStartInput,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    challenge = _fetch_challenge_required(connection, request.challenge_id)
    if str(challenge["status"]) == "started":
        match = _match_by_challenge(connection, request.challenge_id)
        return {"challenge": _challenge_row_to_dict(challenge), "match": _match_payload(connection, match)}
    if str(challenge["status"]) in FINAL_CHALLENGE_STATES:
        return {"challenge": _challenge_row_to_dict(challenge), "match": None}
    if str(challenge["status"]) == "needs_master_review":
        return {"challenge": _challenge_row_to_dict(challenge), "match": None}

    throttle = _fetch_throttle_state(connection)
    if str(challenge["status"]) in {"queued", "deferred"} and not challenge["table_id"]:
        table = _available_table(connection, throttle)
        if table is None:
            return {"challenge": _challenge_payload(connection, challenge), "match": None}
        _assign_table_to_challenge(connection, challenge, table, now=current_time)
        challenge = _fetch_challenge_required(connection, request.challenge_id)

    deadline_value = challenge["start_window_deadline"]
    if not deadline_value:
        deadline = current_time + timedelta(minutes=_start_window_minutes(connection, str(challenge["act_id"])))
        connection.execute(
            """
            UPDATE pvp_challenges
            SET start_window_deadline = ?,
                updated_at = ?
            WHERE challenge_id = ?
            """,
            (_iso(deadline), _iso(current_time), request.challenge_id),
        )
        challenge = _fetch_challenge_required(connection, request.challenge_id)
    else:
        deadline = _parse_iso(str(deadline_value))
    if current_time > deadline and not request.master_approval:
        reviewed = _mark_challenge_for_review(
            connection,
            challenge,
            reason="start_window_timeout",
            now=current_time,
            release_table=True,
        )
        return {"challenge": reviewed, "match": None}

    if _started_cap_reached(connection, challenge, throttle) and not request.master_approval:
        reviewed = _mark_challenge_for_review(
            connection,
            challenge,
            reason="started mandatory match cap reached",
            now=current_time,
            release_table=True,
        )
        return {"challenge": reviewed, "match": None}

    challenger_id = str(challenge["challenger_id"])
    target_id = str(challenge["target_id"])
    rules = _gwent_rules(connection)
    deck_state = {
        challenger_id: _build_player_deck_state(
            connection,
            challenger_id,
            rules,
            (request.mulligans_by_player or {}).get(challenger_id, []),
        ),
        target_id: _build_player_deck_state(
            connection,
            target_id,
            rules,
            (request.mulligans_by_player or {}).get(target_id, []),
        ),
        "rules": rules,
        "cards_burn_after_round": False,
    }
    match_id = f"gwent_match_{uuid4().hex}"
    round_losses = {challenger_id: 0, target_id: 0}
    table_id = str(challenge["table_id"] or "")
    connection.execute(
        """
        INSERT INTO gwent_runtime_matches (
            match_id, challenge_id, challenger_id, target_id, act_id, status,
            table_id, deck_state_json, round_losses_json, created_at, started_at,
            balance_report_json
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
        """,
        (
            match_id,
            request.challenge_id,
            challenger_id,
            target_id,
            challenge["act_id"],
            table_id,
            _json_dumps(deck_state),
            _json_dumps(round_losses),
            _iso(current_time),
            _iso(current_time),
            _json_dumps(_balance_report_base(challenge, table_id, current_time)),
        ),
    )
    connection.execute(
        """
        UPDATE pvp_challenges
        SET status = 'started',
            started_at = ?,
            updated_at = ?,
            master_approval = CASE WHEN ? THEN 1 ELSE master_approval END
        WHERE challenge_id = ?
        """,
        (
            _iso(current_time),
            _iso(current_time),
            1 if request.master_approval else 0,
            request.challenge_id,
        ),
    )
    if table_id:
        _occupy_table(connection, table_id, challenge_id=request.challenge_id, match_id=match_id, now=current_time)
    connection.execute(
        """
        UPDATE pvp_stake_ledger
        SET match_id = ?
        WHERE challenge_id = ? AND status = 'locked'
        """,
        (match_id, request.challenge_id),
    )
    log_event(
        connection,
        "gwent_match_started",
        {
            "match_id": match_id,
            "challenge_id": request.challenge_id,
            "players": [challenger_id, target_id],
            "table_id": table_id,
            "started_at": _iso(current_time),
            "no_match_time_limit_after_start": True,
            "target_duration_min": 20,
            "master_acceleration_review_min": 25,
        },
        source=request.source,
        created_at=current_time,
    )
    match = _fetch_match_required(connection, match_id)
    return {
        "challenge": _challenge_payload(connection, _fetch_challenge_required(connection, request.challenge_id)),
        "match": _match_payload(connection, match),
    }


def record_gwent_round(
    connection: sqlite3.Connection,
    match_id: str,
    round_state: dict[str, Any],
    *,
    round_number: int | None = None,
    actor_id: str | None = None,
    master_override: bool = False,
    source: str = "pvp_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    match = _fetch_match_required(connection, match_id)
    if str(match["status"]) in {"finished", "needs_master_review"}:
        return {"match": _match_payload(connection, match), "round": None, "duplicate": False}
    next_round = round_number or _next_round_number(connection, match_id)
    if next_round < 1 or next_round > 3:
        raise PvpError("Gwent match supports best-of-3 rounds.")
    existing = connection.execute(
        """
        SELECT *
        FROM gwent_rounds
        WHERE match_id = ? AND round_number = ?
        """,
        (match_id, next_round),
    ).fetchone()
    if existing is not None:
        if not _is_pending_round_row(existing):
            return {
                "match": _match_payload(connection, match),
                "round": _round_row_to_dict(existing),
                "duplicate": True,
            }

    players = [str(match["challenger_id"]), str(match["target_id"])]
    deck_state = _json_loads(str(match["deck_state_json"]), {})
    incoming_submissions = _round_submissions_from_state(round_state, players, actor_id=actor_id)
    if not incoming_submissions:
        raise PvpError("Gwent round submission requires a play or pass flag.")
    _validate_round_submission_state(
        connection,
        match,
        _round_state_from_submissions(incoming_submissions, players),
        deck_state,
    )

    if existing is not None:
        return _merge_pending_gwent_round(
            connection,
            match,
            existing,
            incoming_submissions,
            players=players,
            deck_state=deck_state,
            master_override=master_override,
            source=source,
            now=current_time,
        )

    if master_override and not _all_round_players_ready(incoming_submissions, players):
        return _mark_gwent_round_for_review(
            connection,
            match,
            round_number=next_round,
            submissions=incoming_submissions,
            players=players,
            reason=INCOMPLETE_ROUND_REVIEW_REASON,
            now=current_time,
        )
    if not _all_round_players_ready(incoming_submissions, players):
        return _insert_pending_gwent_round(
            connection,
            match,
            round_number=next_round,
            submissions=incoming_submissions,
            players=players,
            source=source,
            now=current_time,
        )

    return _store_resolved_gwent_round(
        connection,
        match,
        round_number=next_round,
        round_state=round_state,
        deck_state=deck_state,
        source=source,
        now=current_time,
    )


def _store_resolved_gwent_round(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    *,
    round_number: int,
    round_state: dict[str, Any],
    deck_state: dict[str, Any],
    source: str,
    now: datetime,
    existing_round_id: int | None = None,
) -> dict[str, Any]:
    match_id = str(match["match_id"])
    resolved = _resolve_round_state(connection, match, round_state, deck_state)
    losses = _json_loads(str(match["round_losses_json"]), {})
    challenger_id = str(match["challenger_id"])
    target_id = str(match["target_id"])
    losses.setdefault(challenger_id, 0)
    losses.setdefault(target_id, 0)
    winner_id = resolved["winner_id"]
    if resolved["tie"]:
        losses[challenger_id] = int(losses[challenger_id]) + 1
        losses[target_id] = int(losses[target_id]) + 1
    else:
        loser_id = target_id if winner_id == challenger_id else challenger_id
        losses[loser_id] = int(losses[loser_id]) + 1

    match_status = "active"
    match_winner_id: str | None = None
    review_reason: str | None = None
    if int(losses[challenger_id]) >= 2 and int(losses[target_id]) >= 2:
        match_status = "needs_master_review"
        review_reason = "double_loss_tie_requires_master_review"
    elif int(losses[challenger_id]) >= 2:
        match_status = "awaiting_finish"
        match_winner_id = target_id
    elif int(losses[target_id]) >= 2:
        match_status = "awaiting_finish"
        match_winner_id = challenger_id

    if existing_round_id is None:
        connection.execute(
            """
            INSERT INTO gwent_rounds (
                match_id, round_number, round_state_json, row_scores_json,
                passed_json, winner_id, tie, review_required, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                round_number,
                _json_dumps(resolved["round_state"]),
                _json_dumps(resolved["row_scores"]),
                _json_dumps(resolved["passed"]),
                winner_id,
                1 if resolved["tie"] else 0,
                1 if review_reason else 0,
                _iso(now),
            ),
        )
    else:
        connection.execute(
            """
            UPDATE gwent_rounds
            SET round_state_json = ?,
                row_scores_json = ?,
                passed_json = ?,
                winner_id = ?,
                tie = ?,
                review_required = ?
            WHERE round_id = ?
            """,
            (
                _json_dumps(resolved["round_state"]),
                _json_dumps(resolved["row_scores"]),
                _json_dumps(resolved["passed"]),
                winner_id,
                1 if resolved["tie"] else 0,
                1 if review_reason else 0,
                existing_round_id,
            ),
        )
    connection.execute(
        """
        UPDATE gwent_runtime_matches
        SET status = ?,
            deck_state_json = ?,
            round_losses_json = ?,
            winner_id = ?,
            review_reason = ?
        WHERE match_id = ?
        """,
        (
            match_status,
            _json_dumps(resolved["deck_state"]),
            _json_dumps(losses),
            match_winner_id,
            review_reason,
            match_id,
        ),
    )
    if review_reason:
        _mark_match_resources_for_review(connection, match, reason=review_reason, now=now)

    payload = {
        "match_id": match_id,
        "round_number": round_number,
        "winner_id": winner_id,
        "tie": resolved["tie"],
        "row_scores": resolved["row_scores"],
        "round_losses": losses,
        "match_status": match_status,
        "match_winner_id": match_winner_id,
        "review_reason": review_reason,
        "effects_applied": resolved["effects_applied"],
    }
    log_event(connection, "gwent_round_finished", payload, source=source, created_at=now)
    stored_round = connection.execute(
        """
        SELECT *
        FROM gwent_rounds
        WHERE match_id = ? AND round_number = ?
        """,
        (match_id, round_number),
    ).fetchone()
    return {
        "match": _match_payload(connection, _fetch_match_required(connection, match_id)),
        "round": _round_row_to_dict(stored_round),
        "duplicate": False,
    }


def _merge_pending_gwent_round(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    existing: sqlite3.Row,
    incoming_submissions: dict[str, dict[str, Any]],
    *,
    players: list[str],
    deck_state: dict[str, Any],
    master_override: bool,
    source: str,
    now: datetime,
) -> dict[str, Any]:
    pending_state = _json_loads(str(existing["round_state_json"]), {})
    submissions = _pending_submissions(pending_state, players)
    order = _pending_submission_order(pending_state, submissions)
    changed = False
    for player_id, incoming in incoming_submissions.items():
        if player_id in submissions:
            if _canonical_submission(submissions[player_id]) == _canonical_submission(incoming):
                continue
            return _mark_gwent_round_for_review(
                connection,
                match,
                round_number=int(existing["round_number"]),
                submissions={**submissions, **incoming_submissions},
                players=players,
                reason=CONTRADICTORY_ROUND_REVIEW_REASON,
                now=now,
                existing_round_id=int(existing["round_id"]),
            )
        submissions[player_id] = incoming
        order.append(player_id)
        changed = True

    if not changed:
        return {
            "match": _match_payload(connection, match),
            "round": _round_row_to_dict(existing),
            "duplicate": True,
        }

    if master_override and not _all_round_players_ready(submissions, players):
        return _mark_gwent_round_for_review(
            connection,
            match,
            round_number=int(existing["round_number"]),
            submissions=submissions,
            players=players,
            reason=INCOMPLETE_ROUND_REVIEW_REASON,
            now=now,
            existing_round_id=int(existing["round_id"]),
        )
    if not _all_round_players_ready(submissions, players):
        return _update_pending_gwent_round(
            connection,
            match,
            existing,
            submissions=submissions,
            order=order,
            players=players,
            source=source,
            now=now,
        )

    return _store_resolved_gwent_round(
        connection,
        match,
        round_number=int(existing["round_number"]),
        round_state=_round_state_from_submissions(submissions, players, order=order),
        deck_state=deck_state,
        source=source,
        now=now,
        existing_round_id=int(existing["round_id"]),
    )


def _insert_pending_gwent_round(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    *,
    round_number: int,
    submissions: dict[str, dict[str, Any]],
    players: list[str],
    source: str,
    now: datetime,
) -> dict[str, Any]:
    pending_state = _pending_round_state(submissions, players)
    connection.execute(
        """
        INSERT INTO gwent_rounds (
            match_id, round_number, round_state_json, row_scores_json,
            passed_json, winner_id, tie, review_required, created_at
        )
        VALUES (?, ?, ?, '{}', ?, NULL, 0, 0, ?)
        """,
        (
            match["match_id"],
            round_number,
            _json_dumps(pending_state),
            _json_dumps(_passed_from_submissions(submissions, players)),
            _iso(now),
        ),
    )
    log_event(
        connection,
        "gwent_round_submission_pending",
        {
            "match_id": match["match_id"],
            "round_number": round_number,
            "ready_players": pending_state["ready_players"],
            "missing_players": pending_state["missing_players"],
        },
        source=source,
        created_at=now,
    )
    stored_round = connection.execute(
        """
        SELECT *
        FROM gwent_rounds
        WHERE match_id = ? AND round_number = ?
        """,
        (match["match_id"], round_number),
    ).fetchone()
    return {
        "match": _match_payload(connection, _fetch_match_required(connection, str(match["match_id"]))),
        "round": _round_row_to_dict(stored_round),
        "duplicate": False,
    }


def _update_pending_gwent_round(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    existing: sqlite3.Row,
    *,
    submissions: dict[str, dict[str, Any]],
    order: list[str],
    players: list[str],
    source: str,
    now: datetime,
) -> dict[str, Any]:
    pending_state = _pending_round_state(submissions, players, order=order)
    connection.execute(
        """
        UPDATE gwent_rounds
        SET round_state_json = ?,
            passed_json = ?
        WHERE round_id = ?
        """,
        (
            _json_dumps(pending_state),
            _json_dumps(_passed_from_submissions(submissions, players)),
            existing["round_id"],
        ),
    )
    log_event(
        connection,
        "gwent_round_submission_pending",
        {
            "match_id": match["match_id"],
            "round_number": int(existing["round_number"]),
            "ready_players": pending_state["ready_players"],
            "missing_players": pending_state["missing_players"],
        },
        source=source,
        created_at=now,
    )
    stored_round = connection.execute("SELECT * FROM gwent_rounds WHERE round_id = ?", (existing["round_id"],)).fetchone()
    return {
        "match": _match_payload(connection, _fetch_match_required(connection, str(match["match_id"]))),
        "round": _round_row_to_dict(stored_round),
        "duplicate": False,
    }


def _mark_gwent_round_for_review(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    *,
    round_number: int,
    submissions: dict[str, dict[str, Any]],
    players: list[str],
    reason: str,
    now: datetime,
    existing_round_id: int | None = None,
) -> dict[str, Any]:
    review_state = _pending_round_state(submissions, players)
    review_state["status"] = GWENT_ROUND_REVIEW_STATUS
    review_state["review_reason"] = reason
    if existing_round_id is None:
        connection.execute(
            """
            INSERT INTO gwent_rounds (
                match_id, round_number, round_state_json, row_scores_json,
                passed_json, winner_id, tie, review_required, created_at
            )
            VALUES (?, ?, ?, '{}', ?, NULL, 0, 1, ?)
            """,
            (
                match["match_id"],
                round_number,
                _json_dumps(review_state),
                _json_dumps(_passed_from_submissions(submissions, players)),
                _iso(now),
            ),
        )
    else:
        connection.execute(
            """
            UPDATE gwent_rounds
            SET round_state_json = ?,
                row_scores_json = '{}',
                passed_json = ?,
                winner_id = NULL,
                tie = 0,
                review_required = 1
            WHERE round_id = ?
            """,
            (
                _json_dumps(review_state),
                _json_dumps(_passed_from_submissions(submissions, players)),
                existing_round_id,
            ),
        )
    reviewed_match = _mark_match_for_review(connection, match, reason=reason, now=now)
    stored_round = connection.execute(
        """
        SELECT *
        FROM gwent_rounds
        WHERE match_id = ? AND round_number = ?
        """,
        (match["match_id"], round_number),
    ).fetchone()
    log_event(
        connection,
        "gwent_round_review_required",
        {
            "match_id": match["match_id"],
            "round_number": round_number,
            "reason": reason,
            "ready_players": review_state["ready_players"],
            "missing_players": review_state["missing_players"],
        },
        source="master_review",
        created_at=now,
    )
    return {"match": reviewed_match, "round": _round_row_to_dict(stored_round), "duplicate": False}


def finish_gwent_match(
    connection: sqlite3.Connection,
    match_id: str,
    *,
    winner_id: str | None = None,
    outcome: str = "normal",
    source: str = "pvp_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    match = _fetch_match_required(connection, match_id)
    if match["result_applied_at"]:
        return {
            "match": _match_payload(connection, match),
            "stake_transfer": _stake_payload(connection, str(match["challenge_id"])),
            "duplicate": True,
        }
    if str(match["status"]) == "needs_master_review":
        return {
            "match": _match_payload(connection, match),
            "stake_transfer": {"status": "not_applied", "reason": match["review_reason"]},
            "duplicate": False,
        }
    if str(match["status"]) != "awaiting_finish":
        reviewed = _mark_match_for_review(
            connection,
            match,
            reason="finish_before_match_winner_requires_master_review",
            now=current_time,
        )
        return {
            "match": reviewed,
            "stake_transfer": {
                "status": "not_applied",
                "reason": reviewed["review_reason"],
            },
            "duplicate": False,
        }

    players = {str(match["challenger_id"]), str(match["target_id"])}
    resolved_winner = str(match["winner_id"]) if match["winner_id"] else None
    if resolved_winner not in players:
        reviewed = _mark_match_for_review(
            connection,
            match,
            reason=f"{outcome}_requires_master_review",
            now=current_time,
        )
        return {
            "match": reviewed,
            "stake_transfer": {"status": "not_applied", "reason": reviewed["review_reason"]},
            "duplicate": False,
        }
    if winner_id is not None and winner_id != resolved_winner:
        reason = (
            f"{outcome}_requires_master_review"
            if winner_id not in players
            else "winner_override_requires_master_review"
        )
        reviewed = _mark_match_for_review(
            connection,
            match,
            reason=reason,
            now=current_time,
        )
        return {
            "match": reviewed,
            "stake_transfer": {"status": "not_applied", "reason": reviewed["review_reason"]},
            "duplicate": False,
        }
    loser_id = str(match["target_id"]) if resolved_winner == str(match["challenger_id"]) else str(match["challenger_id"])
    stake_transfer = _apply_stake_once(
        connection,
        challenge_id=str(match["challenge_id"]),
        match_id=match_id,
        winner_id=resolved_winner,
        loser_id=loser_id,
        now=current_time,
    )
    started_at = _parse_iso(str(match["started_at"]))
    duration_seconds = int((current_time - started_at).total_seconds())
    balance_report = _json_loads(str(match["balance_report_json"]), {})
    balance_report.update(
        {
            "finished_at": _iso(current_time),
            "duration_seconds": duration_seconds,
            "duration_minutes": round(duration_seconds / 60, 2),
            "over_20_min_target": duration_seconds > 20 * 60,
            "over_25_min_review_soft_cap": duration_seconds > 25 * 60,
            "outcome": outcome,
            "winner_id": resolved_winner,
            "stake_transfer_status": stake_transfer["status"],
        }
    )
    connection.execute(
        """
        UPDATE gwent_runtime_matches
        SET status = 'finished',
            winner_id = ?,
            finished_at = ?,
            result_applied_at = ?,
            duration_seconds = ?,
            balance_report_json = ?
        WHERE match_id = ?
        """,
        (
            resolved_winner,
            _iso(current_time),
            _iso(current_time),
            duration_seconds,
            _json_dumps(balance_report),
            match_id,
        ),
    )
    connection.execute(
        """
        UPDATE pvp_challenges
        SET status = 'resolved',
            resolved_at = ?,
            updated_at = ?
        WHERE challenge_id = ?
        """,
        (_iso(current_time), _iso(current_time), match["challenge_id"]),
    )
    if match["table_id"]:
        _release_table(connection, str(match["table_id"]), now=current_time)

    log_event(
        connection,
        "gwent_match_finished",
        {
            "match_id": match_id,
            "challenge_id": match["challenge_id"],
            "winner_id": resolved_winner,
            "loser_id": loser_id,
            "duration_seconds": duration_seconds,
            "stake_transfer": stake_transfer,
            "balance_report": balance_report,
        },
        source=source,
        created_at=current_time,
    )
    return {
        "match": _match_payload(connection, _fetch_match_required(connection, match_id)),
        "stake_transfer": stake_transfer,
        "duplicate": False,
    }


def record_pvp_refusal(
    connection: sqlite3.Connection,
    challenge_id: str,
    *,
    reason: str,
    actor_id: str | None = None,
    source: str = "pvp_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    challenge = _fetch_challenge_required(connection, challenge_id)
    rule = _refusal_rule(connection, reason)
    outcome = str(rule["default_outcome"])
    token_refunded = False
    match = _match_by_challenge(connection, challenge_id)
    in_started_match = (
        match is not None
        and str(match["status"]) not in {"finished", "needs_master_review"}
    )
    if not in_started_match and _should_refund_pre_start_refusal(challenge, reason):
        _refund_challenge_token(connection, str(challenge["challenger_id"]), current_time)
        token_refunded = True
    stake_refund = None
    if in_started_match:
        _mark_match_for_review(
            connection,
            match,
            reason=f"refusal:{reason}",
            now=current_time,
        )
    elif outcome == "deferred_window":
        if challenge["table_id"]:
            _release_table(connection, str(challenge["table_id"]), now=current_time)
        deadline = current_time + timedelta(minutes=_start_window_minutes(connection, str(challenge["act_id"])))
        connection.execute(
            """
            UPDATE pvp_challenges
            SET status = 'deferred',
                table_id = NULL,
                refusal_reason = ?,
                start_window_deadline = ?,
                updated_at = ?
            WHERE challenge_id = ?
            """,
            (reason, _iso(deadline), _iso(current_time), challenge_id),
        )
    elif outcome == "queued":
        if challenge["table_id"]:
            _release_table(connection, str(challenge["table_id"]), now=current_time)
        connection.execute(
            """
            UPDATE pvp_challenges
            SET status = 'queued',
                table_id = NULL,
                start_window_deadline = NULL,
                refusal_reason = ?,
                updated_at = ?
            WHERE challenge_id = ?
            """,
            (reason, _iso(current_time), challenge_id),
        )
    else:
        _mark_challenge_for_review(
            connection,
            challenge,
            reason=f"refusal:{reason}",
            now=current_time,
            release_table=True,
        )
    if not in_started_match and reason in REFUNDABLE_PRE_START_REFUSALS:
        stake_refund = _refund_gold_stake_once(
            connection,
            challenge_id=challenge_id,
            now=current_time,
        )

    log_event(
        connection,
        "pvp_refusal_recorded",
        {
            "challenge_id": challenge_id,
            "reason": reason,
            "actor_id": actor_id,
            "default_outcome": outcome,
            "severity": rule["severity"],
            "challenge_token_refunded": token_refunded,
            "stake_refund": stake_refund,
        },
        source=source,
        created_at=current_time,
    )
    return _challenge_payload(connection, _fetch_challenge_required(connection, challenge_id))


def convert_personal_card_to_lord(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    lord_id: str,
    personal_card_id: str,
    source: str = "pvp_api",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    existing = connection.execute(
        """
        SELECT *
        FROM personal_card_conversions
        WHERE player_id = ? AND personal_card_id = ?
        """,
        (player_id, personal_card_id),
    ).fetchone()
    if existing is not None:
        return {**_conversion_row_to_dict(existing), "duplicate": True}

    _require_personal_pvp_player(connection, player_id)
    card = _fetch_required(connection, "cards", "card_id", personal_card_id)
    if str(card["card_type"]) != "personal_to_army" or not card["army_unit_card_id"]:
        raise PvpError(f"Card cannot be converted to a lord unit: {personal_card_id}")
    domain = _fetch_optional(
        connection,
        "domains",
        "lord_player_id",
        lord_id,
    )
    if domain is None:
        raise PvpError(f"Unknown lord player for card conversion: {lord_id}")
    army_card_id = str(card["army_unit_card_id"])
    tier = _to_int(card["tier"])
    try:
        assert_asset_unlocked(
            connection,
            asset_type="card",
            asset_id=personal_card_id,
            owner_player_id=player_id,
            purpose="lord card transfer",
        )
        ownership_before = ownership_for_asset(
            connection,
            owner_player_id=player_id,
            asset_type="card",
            asset_id=personal_card_id,
        )
        if _to_int(ownership_before["quantity"]) < 1:
            raise AssetContractError(
                "asset_owner_mismatch",
                f"{player_id} does not own personal card {personal_card_id}.",
                409,
            )
        ownership_after = debit_asset_ownership(
            connection,
            owner_player_id=player_id,
            asset_type="card",
            asset_id=personal_card_id,
            quantity=1,
            now=current_time,
        )
    except AssetContractError as exc:
        raise PvpError(exc.message) from exc
    conversion_id = f"card_conversion_{uuid4().hex}"
    connection.execute(
        """
        INSERT INTO personal_card_conversions (
            conversion_id, player_id, lord_id, domain_id, personal_card_id,
            army_unit_card_id, tier, status, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'converted', ?, ?)
        """,
        (
            conversion_id,
            player_id,
            lord_id,
            domain["domain_id"],
            personal_card_id,
            army_card_id,
            tier,
            source,
            _iso(current_time),
        ),
    )
    reserve_id = f"reserve_{domain['domain_id']}_{army_card_id}_conversion"
    connection.execute(
        """
        INSERT INTO army_reserve_runtime (
            reserve_id, domain_id, card_id, count, status, updated_at
        )
        VALUES (?, ?, ?, 1, 'available', ?)
        ON CONFLICT(reserve_id) DO UPDATE SET
            count = count + 1,
            updated_at = excluded.updated_at
        """,
        (reserve_id, domain["domain_id"], army_card_id, _iso(current_time)),
    )
    payload = {
        "conversion_id": conversion_id,
        "player_id": player_id,
        "lord_id": lord_id,
        "domain_id": domain["domain_id"],
        "personal_card_id": personal_card_id,
        "army_unit_card_id": army_card_id,
        "tier": tier,
        "reserve_id": reserve_id,
        "ownership_debit": {
            "asset_type": "card",
            "asset_id": personal_card_id,
            "owner_player_id": player_id,
            "quantity_before": _to_int(ownership_before["quantity"]),
            "quantity_debited": 1,
            "quantity_after": _to_int(ownership_after["quantity"]),
        },
        "duplicate": False,
    }
    log_event(connection, "personal_card_converted_to_lord", payload, source=source, created_at=current_time)
    return payload


def _build_player_deck_state(
    connection: sqlite3.Connection,
    player_id: str,
    rules: dict[str, int | str],
    mulligans: list[str],
) -> dict[str, Any]:
    if len(mulligans) > int(rules["mulligans"]):
        raise PvpError("Gwent mulligan count exceeds the configured limit.")
    deck = _deck_for_player(connection, player_id)
    cards = _cards_by_id(connection)
    leader = cards.get(str(deck["leader_card_id"]))
    if leader is None or str(leader["type"]) != "leader":
        raise PvpError(f"Gwent deck leader is invalid for player: {player_id}")
    _assert_stage1_gwent_effect_supported(
        str(leader["card_id"]),
        str(leader["type"]),
        str(leader["effect"] or "none"),
    )
    card_ids = _split_ids(str(deck["card_ids"]))
    _validate_deck_cards(player_id, card_ids, cards, rules)
    hand = card_ids[: int(rules["hand_size"])]
    draw_pile = card_ids[int(rules["hand_size"]) :]
    for card_id in mulligans:
        if card_id not in hand:
            raise PvpError(f"Mulligan card is not in opening hand: {card_id}")
        if not draw_pile:
            break
        hand.remove(card_id)
        hand.append(draw_pile.pop(0))
        draw_pile.append(card_id)
    return {
        "deck_id": deck["deck_id"],
        "leader_card_id": deck["leader_card_id"],
        "draw_pile": draw_pile,
        "hand": hand,
        "mulligans": mulligans,
        "rows": {row: [] for row in GWENT_ROWS},
        "passed": False,
        "graveyard": [],
        "cards_burned": False,
        "leader_used": False,
    }


def _validate_player_gwent_preflight(
    connection: sqlite3.Connection,
    player_id: str,
    rules: dict[str, int | str],
) -> None:
    deck = _deck_for_player(connection, player_id)
    cards = _cards_by_id(connection)
    leader = cards.get(str(deck["leader_card_id"]))
    if leader is None or str(leader["type"]) != "leader":
        raise PvpError(f"Gwent deck leader is invalid for player: {player_id}")
    _assert_stage1_gwent_effect_supported(
        str(leader["card_id"]),
        str(leader["type"]),
        str(leader["effect"] or "none"),
    )
    _validate_deck_cards(player_id, _split_ids(str(deck["card_ids"])), cards, rules)


def _validate_deck_cards(
    player_id: str,
    card_ids: list[str],
    cards: dict[str, sqlite3.Row],
    rules: dict[str, int | str],
) -> None:
    missing = [card_id for card_id in card_ids if card_id not in cards]
    if missing:
        raise PvpError(f"Gwent deck has unknown cards for {player_id}: {', '.join(missing)}")
    for card_id in card_ids:
        card = cards[card_id]
        _assert_stage1_gwent_effect_supported(
            card_id,
            str(card["type"]),
            str(card["effect"] or "none"),
        )
    unit_count = sum(1 for card_id in card_ids if str(cards[card_id]["type"]) == "unit")
    special_count = sum(1 for card_id in card_ids if str(cards[card_id]["type"]) == "special")
    if unit_count < int(rules["deck_min_unit_cards"]):
        raise PvpError(f"Gwent deck for {player_id} has fewer than 22 unit cards.")
    if special_count > int(rules["max_special_cards"]):
        raise PvpError(f"Gwent deck for {player_id} exceeds the special card cap.")


def _normalize_match_deck_state(
    deck_state: dict[str, Any],
    players: list[str],
) -> dict[str, Any]:
    if not isinstance(deck_state, dict):
        raise PvpError("Gwent match has invalid deck state.")
    normalized = dict(deck_state)
    for player_id in players:
        raw_player_state = normalized.get(player_id)
        if not isinstance(raw_player_state, dict):
            raise PvpError(f"Gwent match has no deck state for player: {player_id}")
        player_state = dict(raw_player_state)
        rows = player_state.get("rows")
        if not isinstance(rows, dict):
            rows = {}
        player_state["hand"] = list(player_state.get("hand") or [])
        player_state["draw_pile"] = list(player_state.get("draw_pile") or [])
        player_state["mulligans"] = list(player_state.get("mulligans") or [])
        player_state["graveyard"] = list(player_state.get("graveyard") or [])
        player_state["leader_used"] = bool(player_state.get("leader_used", False))
        player_state["rows"] = {
            row: list(rows.get(row) or [])
            for row in GWENT_ROWS
        }
        player_state["passed"] = bool(player_state.get("passed", False))
        player_state["cards_burned"] = bool(player_state.get("cards_burned", False))
        normalized[player_id] = player_state
    return normalized


def _assert_stage1_gwent_effect_supported(card_id: str, card_type: str, effect: str) -> None:
    if card_type not in {"unit", "special", "leader"}:
        raise PvpError(f"Unsupported Gwent card type for {card_id}: {card_type}")
    if is_gwent_effect_supported(card_type, effect):
        return
    raise PvpError(f"Gwent effect is not implemented in Stage 1: {card_id} ({effect})")


def _consume_card_from_hand(
    player_state: dict[str, Any],
    player_id: str,
    card_id: str,
) -> None:
    hand = player_state["hand"]
    if card_id not in hand:
        raise PvpError(f"Gwent card is not in current hand for {player_id}: {card_id}")
    hand.remove(card_id)


def _return_card_to_hand(player_state: dict[str, Any], card_id: str) -> None:
    player_state["hand"].append(card_id)


def _remove_pending_discard(cards: list[str], card_id: str) -> None:
    if card_id in cards:
        cards.remove(card_id)


def _resolve_round_state(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    round_state: dict[str, Any],
    deck_state: dict[str, Any],
) -> dict[str, Any]:
    cards = _cards_by_id(connection)
    players = [str(match["challenger_id"]), str(match["target_id"])]
    deck_state = _normalize_match_deck_state(deck_state, players)
    board = {player: {row: [] for row in GWENT_ROWS} for player in players}
    weather_rows: set[str] = set()
    horn_rows = {player: set() for player in players}
    effects_applied: list[dict[str, Any]] = []
    returned_cards: list[dict[str, Any]] = []
    scorch_pending: list[dict[str, Any]] = []
    consumed_cards: dict[str, list[str]] = {player: [] for player in players}

    for play in _normalize_plays(round_state):
        player_id = str(play.get("player_id"))
        card_id = str(play.get("card_id"))
        if player_id not in board:
            raise PvpError(f"Round play references a non-participant: {player_id}")
        card = cards.get(card_id)
        if card is None:
            raise PvpError(f"Round play references an unknown Gwent card: {card_id}")
        card_type = str(card["type"])
        effect = str(card["effect"] or "none")
        _assert_stage1_gwent_effect_supported(card_id, card_type, effect)

        player_state = deck_state[player_id]
        if card_type == "leader":
            _apply_leader_play(
                play,
                card,
                player_state,
                horn_rows,
                weather_rows,
                effects_applied,
            )
            continue

        _consume_card_from_hand(player_state, player_id, card_id)
        consumed_cards[player_id].append(card_id)
        if card_type == "special":
            returned_before = len(returned_cards)
            _apply_special_play(
                play,
                card,
                player_state,
                board,
                weather_rows,
                horn_rows,
                effects_applied,
                returned_cards,
                scorch_pending,
            )
            for returned in returned_cards[returned_before:]:
                if returned["player_id"] == player_id:
                    _remove_pending_discard(consumed_cards[player_id], str(returned["card_id"]))
                    _return_card_to_hand(player_state, str(returned["card_id"]))
            continue
        row_name = _row_for_card(card, str(play.get("row") or ""))
        board_player_id = _opponent_id(players, player_id) if effect == "spy" else player_id
        unit = {
            "player_id": board_player_id,
            "played_by": player_id,
            "card_id": card_id,
            "row": row_name,
            "base_strength": _to_int(card["strength"]),
            "effect": effect,
            "hero": effect == "hero",
            "removed": False,
        }
        board[board_player_id][row_name].append(unit)
        if effect.startswith("scorch_"):
            scorch_pending.append({"effect": effect, "source_card_id": card_id})
        if effect == "spy":
            drawn = _draw_cards(player_state, 2)
            effects_applied.append(
                {
                    "card_id": card_id,
                    "effect": "spy",
                    "scope": "unit",
                    "placed_for_player_id": board_player_id,
                    "drawn_card_ids": drawn,
                }
            )
        elif effect == "medic":
            revived = _apply_medic(
                play,
                player_id,
                player_state,
                cards,
                board,
                consumed_cards[player_id],
                effects_applied,
            )
            if revived is None:
                effects_applied.append({"card_id": card_id, "effect": "medic", "scope": "unit", "revived_card_id": None})
        elif effect == "muster":
            mustered = _apply_muster(
                player_id,
                card_id,
                card,
                player_state,
                cards,
                board,
                consumed_cards[player_id],
            )
            effects_applied.append(
                {
                    "card_id": card_id,
                    "effect": "muster",
                    "scope": "unit",
                    "mustered_card_ids": mustered,
                }
            )
        elif effect in {"morale", "bond", "tight_bond", "agile", "hero"} or effect.startswith("scorch_"):
            effects_applied.append({"card_id": card_id, "effect": effect, "scope": "unit"})

    for scorch in scorch_pending:
        _apply_scorch(board, scorch, effects_applied)

    row_scores: dict[str, dict[str, int]] = {player: {} for player in players}
    totals: dict[str, int] = {}
    for player_id in players:
        total = 0
        for row_name in GWENT_ROWS:
            row_total = _score_row(board[player_id][row_name], row_name, weather_rows, row_name in horn_rows[player_id])
            row_scores[player_id][row_name] = row_total
            total += row_total
        totals[player_id] = total

    if totals[players[0]] == totals[players[1]]:
        winner_id = None
        tie = True
    else:
        winner_id = players[0] if totals[players[0]] > totals[players[1]] else players[1]
        tie = False
    passed = round_state.get("passed") or round_state.get("passed_flags") or {}
    if not isinstance(passed, dict):
        passed = {}
    for player_id in players:
        player_state = deck_state[player_id]
        player_state["graveyard"].extend(consumed_cards[player_id])
        player_state["rows"] = {row: [] for row in GWENT_ROWS}
        player_state["passed"] = bool(passed.get(player_id, True))
        player_state["cards_burned"] = False
    return {
        "round_state": {
            "plays": _normalize_plays(round_state),
            "board": board,
            "weather_rows": sorted(weather_rows),
            "horn_rows": {player: sorted(rows) for player, rows in horn_rows.items()},
            "returned_cards": returned_cards,
            "consumed_cards": consumed_cards,
            "hands_after_round": {player: list(deck_state[player]["hand"]) for player in players},
            "graveyards_after_round": {player: list(deck_state[player]["graveyard"]) for player in players},
            "effects_applied": effects_applied,
            "cards_burned": False,
            "total_scores": totals,
        },
        "deck_state": deck_state,
        "row_scores": row_scores,
        "passed": {player: bool(passed.get(player, True)) for player in players},
        "winner_id": winner_id,
        "tie": tie,
        "effects_applied": effects_applied,
    }


def _apply_special_play(
    play: dict[str, Any],
    card: sqlite3.Row,
    player_state: dict[str, Any],
    board: dict[str, dict[str, list[dict[str, Any]]]],
    weather_rows: set[str],
    horn_rows: dict[str, set[str]],
    effects_applied: list[dict[str, Any]],
    returned_cards: list[dict[str, Any]],
    scorch_pending: list[dict[str, Any]],
) -> None:
    player_id = str(play.get("player_id"))
    card_id = str(card["card_id"])
    effect = str(card["effect"] or "none")
    if effect in GWENT_WEATHER_BY_EFFECT:
        weather_rows.add(GWENT_WEATHER_BY_EFFECT[effect])
    elif effect == "clear_weather":
        weather_rows.clear()
    elif effect in {"commanders_horn", "custom_larp_order_banner"}:
        horn_rows[player_id].add(_row_name(str(play.get("row") or "melee")))
    elif effect == "decoy":
        target_card_id = str(play.get("target_card_id") or "")
        if not target_card_id:
            raise PvpError("Gwent decoy requires target_card_id.")
        returned = _remove_card_from_board(board[player_id], target_card_id)
        if returned is None:
            raise PvpError(f"Gwent decoy target is not a non-hero unit on board: {target_card_id}")
        returned_cards.append({"player_id": player_id, "card_id": target_card_id})
    elif effect in {"scorch", "custom_larp_oathbreak"}:
        scorch_pending.append({"effect": "scorch", "source_card_id": card_id})
    elif effect == "custom_larp_spyglass":
        drawn = _draw_cards(player_state, 1)
        effects_applied.append(
            {
                "card_id": card_id,
                "effect": effect,
                "scope": "special",
                "drawn_card_ids": drawn,
            }
        )
        return
    elif effect == "custom_larp_last_stand":
        for row_name in GWENT_ROWS:
            horn_rows[player_id].add(row_name)
    effects_applied.append({"card_id": card_id, "effect": effect, "scope": "special"})


def _apply_leader_play(
    play: dict[str, Any],
    card: sqlite3.Row,
    player_state: dict[str, Any],
    horn_rows: dict[str, set[str]],
    weather_rows: set[str],
    effects_applied: list[dict[str, Any]],
) -> None:
    player_id = str(play.get("player_id"))
    card_id = str(card["card_id"])
    if str(player_state.get("leader_card_id")) != card_id:
        raise PvpError(f"Gwent leader is not assigned to player deck: {card_id}")
    if bool(player_state.get("leader_used")):
        raise PvpError(f"Gwent leader was already used by player: {player_id}")
    effect = str(card["effect"] or "none")
    if effect == "leader_order_rally":
        horn_rows[player_id].add(_row_name(str(play.get("row") or "melee")))
    elif effect == "clear_weather":
        weather_rows.clear()
    player_state["leader_used"] = True
    effects_applied.append({"card_id": card_id, "effect": effect, "scope": "leader"})


def _draw_cards(player_state: dict[str, Any], count: int) -> list[str]:
    drawn = []
    for _ in range(count):
        draw_pile = player_state["draw_pile"]
        if not draw_pile:
            break
        card_id = str(draw_pile.pop(0))
        player_state["hand"].append(card_id)
        drawn.append(card_id)
    return drawn


def _apply_medic(
    play: dict[str, Any],
    player_id: str,
    player_state: dict[str, Any],
    cards: dict[str, sqlite3.Row],
    board: dict[str, dict[str, list[dict[str, Any]]]],
    consumed: list[str],
    effects_applied: list[dict[str, Any]],
) -> str | None:
    target_card_id = str(play.get("revive_card_id") or "")
    graveyard = player_state["graveyard"]
    if target_card_id:
        if target_card_id not in graveyard:
            raise PvpError(f"Gwent medic target is not in graveyard: {target_card_id}")
    else:
        target_card_id = _first_medic_target(graveyard, cards)
    if not target_card_id:
        return None
    target = cards.get(target_card_id)
    if target is None or str(target["type"]) != "unit" or str(target["effect"]) == "hero":
        raise PvpError(f"Gwent medic target is not a revivable unit: {target_card_id}")
    graveyard.remove(target_card_id)
    row_name = _row_for_card(target, str(play.get("revive_row") or ""))
    board[player_id][row_name].append(
        {
            "player_id": player_id,
            "played_by": player_id,
            "card_id": target_card_id,
            "row": row_name,
            "base_strength": _to_int(target["strength"]),
            "effect": str(target["effect"] or "none"),
            "hero": False,
            "removed": False,
            "revived_by_medic": True,
        }
    )
    consumed.append(target_card_id)
    effects_applied.append(
        {
            "card_id": str(play.get("card_id")),
            "effect": "medic",
            "scope": "unit",
            "revived_card_id": target_card_id,
        }
    )
    return target_card_id


def _first_medic_target(graveyard: list[str], cards: dict[str, sqlite3.Row]) -> str:
    for card_id in graveyard:
        card = cards.get(card_id)
        if card is not None and str(card["type"]) == "unit" and str(card["effect"]) != "hero":
            return card_id
    return ""


def _apply_muster(
    player_id: str,
    source_card_id: str,
    source_card: sqlite3.Row,
    player_state: dict[str, Any],
    cards: dict[str, sqlite3.Row],
    board: dict[str, dict[str, list[dict[str, Any]]]],
    consumed: list[str],
) -> list[str]:
    mustered: list[str] = []
    source_faction = str(source_card["faction"])
    source_row = str(source_card["row"])
    candidates = list(player_state["hand"]) + list(player_state["draw_pile"])
    for card_id in candidates:
        if card_id == source_card_id:
            continue
        card = cards.get(card_id)
        if (
            card is None
            or str(card["type"]) != "unit"
            or str(card["effect"]) != "muster"
            or str(card["faction"]) != source_faction
            or str(card["row"]) != source_row
        ):
            continue
        if card_id in player_state["hand"]:
            player_state["hand"].remove(card_id)
        elif card_id in player_state["draw_pile"]:
            player_state["draw_pile"].remove(card_id)
        row_name = _row_for_card(card, "")
        board[player_id][row_name].append(
            {
                "player_id": player_id,
                "played_by": player_id,
                "card_id": card_id,
                "row": row_name,
                "base_strength": _to_int(card["strength"]),
                "effect": "muster",
                "hero": False,
                "removed": False,
                "mustered": True,
            }
        )
        consumed.append(card_id)
        mustered.append(card_id)
    return mustered


def _apply_scorch(
    board: dict[str, dict[str, list[dict[str, Any]]]],
    scorch: dict[str, Any],
    effects_applied: list[dict[str, Any]],
) -> None:
    effect = str(scorch["effect"])
    row_filter = effect.removeprefix("scorch_") if effect.startswith("scorch_") else None
    candidates: list[dict[str, Any]] = []
    for rows in board.values():
        for row_name, units in rows.items():
            if row_filter and row_filter != row_name:
                continue
            for unit in units:
                if not unit["removed"] and not unit["hero"]:
                    candidates.append(unit)
    if not candidates:
        return
    max_strength = max(int(unit["base_strength"]) for unit in candidates)
    if max_strength < 10:
        return
    removed_ids = []
    for unit in candidates:
        if int(unit["base_strength"]) == max_strength:
            unit["removed"] = True
            removed_ids.append(unit["card_id"])
    effects_applied.append(
        {
            "card_id": scorch["source_card_id"],
            "effect": effect,
            "scope": "scorch",
            "removed_card_ids": removed_ids,
        }
    )


def _score_row(
    units: list[dict[str, Any]],
    row_name: str,
    weather_rows: set[str],
    horn_active: bool,
) -> int:
    active_units = [unit for unit in units if not unit["removed"]]
    bond_counts: dict[str, int] = {}
    morale_count = 0
    for unit in active_units:
        if unit["effect"] in {"bond", "tight_bond"}:
            bond_counts[str(unit["card_id"])] = bond_counts.get(str(unit["card_id"]), 0) + 1
        if unit["effect"] == "morale":
            morale_count += 1

    total = 0
    for unit in active_units:
        strength = int(unit["base_strength"])
        if not unit["hero"] and row_name in weather_rows:
            strength = 1
        if not unit["hero"] and unit["effect"] in {"bond", "tight_bond"}:
            strength *= max(1, bond_counts.get(str(unit["card_id"]), 1))
        if not unit["hero"] and unit["effect"] != "morale":
            strength += morale_count
        if not unit["hero"] and horn_active:
            strength *= 2
        total += strength
    return total


def _mark_challenge_for_review(
    connection: sqlite3.Connection,
    challenge: sqlite3.Row,
    *,
    reason: str,
    now: datetime,
    release_table: bool,
) -> dict[str, Any]:
    if release_table and challenge["table_id"]:
        _release_table(connection, str(challenge["table_id"]), now=now)
    connection.execute(
        """
        UPDATE pvp_challenges
        SET status = 'needs_master_review',
            review_reason = ?,
            updated_at = ?
        WHERE challenge_id = ?
        """,
        (reason, _iso(now), challenge["challenge_id"]),
    )
    _record_pvp_review(
        connection,
        challenge_id=str(challenge["challenge_id"]),
        match_id=None,
        reason=reason,
        now=now,
    )
    return _challenge_payload(connection, _fetch_challenge_required(connection, str(challenge["challenge_id"])))


def _mark_match_for_review(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    *,
    reason: str,
    now: datetime,
) -> dict[str, Any]:
    connection.execute(
        """
        UPDATE gwent_runtime_matches
        SET status = 'needs_master_review',
            review_reason = ?
        WHERE match_id = ?
        """,
        (reason, match["match_id"]),
    )
    _mark_match_resources_for_review(connection, match, reason=reason, now=now)
    return _match_payload(connection, _fetch_match_required(connection, str(match["match_id"])))


def _mark_match_resources_for_review(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    *,
    reason: str,
    now: datetime,
) -> None:
    connection.execute(
        """
        UPDATE pvp_challenges
        SET status = 'needs_master_review',
            review_reason = ?,
            updated_at = ?
        WHERE challenge_id = ?
        """,
        (reason, _iso(now), match["challenge_id"]),
    )
    if match["table_id"]:
        _release_table(connection, str(match["table_id"]), now=now)
    _record_pvp_review(
        connection,
        challenge_id=str(match["challenge_id"]),
        match_id=str(match["match_id"]),
        reason=reason,
        now=now,
    )


def _record_pvp_review(
    connection: sqlite3.Connection,
    *,
    challenge_id: str | None,
    match_id: str | None,
    reason: str,
    now: datetime,
) -> None:
    connection.execute(
        """
        INSERT INTO pvp_reviews (
            challenge_id, match_id, reason, severity, status, created_at
        )
        VALUES (?, ?, ?, ?, 'needs_master_review', ?)
        """,
        (
            challenge_id,
            match_id,
            reason,
            REVIEW_SEVERITY_BY_REASON.get(reason.replace("refusal:", ""), "P2"),
            _iso(now),
        ),
    )


def _lock_stake(
    connection: sqlite3.Connection,
    *,
    challenge_id: str,
    owner_player_id: str,
    pending_target_player_id: str,
    stake: dict[str, Any],
    now: datetime,
) -> None:
    quantity = _stake_quantity(stake)
    if _is_gold_stake(stake):
        _reserve_gold_stake(
            connection,
            player_id=owner_player_id,
            amount=quantity,
            now=now,
        )
    connection.execute(
        """
        INSERT INTO pvp_stake_ledger (
            stake_ledger_id, challenge_id, asset_type, asset_id,
            quantity, owner_player_id, pending_target_player_id, status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'locked', ?)
        """,
        (
            f"stake_{challenge_id}",
            challenge_id,
            stake["asset_type"],
            stake["asset_id"],
            quantity,
            owner_player_id,
            pending_target_player_id,
            _iso(now),
        ),
    )
    if _is_gold_stake(stake):
        return
    try:
        lock_owned_asset(
            connection,
            lock_id=f"lock_pvp_{challenge_id}_{stake['asset_type']}_{stake['asset_id']}",
            owner_player_id=owner_player_id,
            asset_type=stake["asset_type"],
            asset_id=stake["asset_id"],
            quantity=quantity,
            lock_type="pvp_stake",
            source_ref_id=challenge_id,
            reason="pending PvP stake",
            require_existing_owner=True,
            now=now,
        )
    except AssetContractError as exc:
        raise PvpError(exc.message) from exc


def _apply_stake_once(
    connection: sqlite3.Connection,
    *,
    challenge_id: str,
    match_id: str,
    winner_id: str,
    loser_id: str,
    now: datetime,
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT *
        FROM pvp_stake_ledger
        WHERE challenge_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (challenge_id,),
    ).fetchone()
    if row is None:
        return {"status": "not_applied", "reason": "no stake ledger", "challenge_id": challenge_id}
    if str(row["status"]) != "locked":
        return _stake_row_to_dict(row)
    quantity = _stake_quantity(dict(row))
    connection.execute(
        """
        UPDATE pvp_stake_ledger
        SET match_id = ?,
            status = 'applied',
            winner_id = ?,
            loser_id = ?,
            applied_at = ?
        WHERE stake_ledger_id = ?
        """,
        (match_id, winner_id, loser_id, _iso(now), row["stake_ledger_id"]),
    )
    if _is_gold_stake(dict(row)):
        connection.execute(
            """
            UPDATE player_runtime_state
            SET gold = gold + ?, updated_at = ?
            WHERE player_id = ?
            """,
            (quantity, _iso(now), winner_id),
        )
    else:
        try:
            settle_owned_asset_lock(
                connection,
                lock_type="pvp_stake",
                source_ref_id=challenge_id,
                target_player_id=winner_id,
                final_status="consumed",
                reason="PvP stake resolved",
                now=now,
            )
        except AssetContractError as exc:
            raise PvpError(exc.message) from exc
    return _stake_row_to_dict(
        connection.execute(
            "SELECT * FROM pvp_stake_ledger WHERE stake_ledger_id = ?",
            (row["stake_ledger_id"],),
        ).fetchone()
    )


def _available_table(
    connection: sqlite3.Connection, throttle: dict[str, Any]
) -> sqlite3.Row | None:
    if str(throttle["mode"]) == "paused" or int(throttle["max_tables"]) <= 0:
        return None
    active_table_ids = [
        row["table_id"]
        for row in connection.execute(
            """
            SELECT table_id
            FROM pvp_table_runtime
            ORDER BY table_id
            LIMIT ?
            """,
            (int(throttle["max_tables"]),),
        ).fetchall()
    ]
    if not active_table_ids:
        return None
    placeholders = ", ".join("?" for _ in active_table_ids)
    return connection.execute(
        f"""
        SELECT *
        FROM pvp_table_runtime
        WHERE status = 'open' AND table_id IN ({placeholders})
        ORDER BY table_id
        LIMIT 1
        """,
        tuple(active_table_ids),
    ).fetchone()


def _assign_table_to_challenge(
    connection: sqlite3.Connection,
    challenge: sqlite3.Row,
    table: sqlite3.Row,
    *,
    now: datetime,
) -> None:
    deadline = now + timedelta(minutes=_start_window_minutes(connection, str(challenge["act_id"])))
    connection.execute(
        """
        UPDATE pvp_challenges
        SET status = 'assigned',
            table_id = ?,
            assigned_zone = ?,
            start_window_deadline = ?,
            updated_at = ?
        WHERE challenge_id = ?
        """,
        (
            table["table_id"],
            table["zone_name"],
            _iso(deadline),
            _iso(now),
            challenge["challenge_id"],
        ),
    )
    _occupy_table(connection, str(table["table_id"]), challenge_id=str(challenge["challenge_id"]), match_id=None, now=now)


def _occupy_table(
    connection: sqlite3.Connection,
    table_id: str | None,
    *,
    challenge_id: str,
    match_id: str | None,
    now: datetime,
) -> None:
    if not table_id:
        return
    connection.execute(
        """
        UPDATE pvp_table_runtime
        SET status = 'occupied',
            current_challenge_id = ?,
            current_match_id = ?,
            updated_at = ?
        WHERE table_id = ?
        """,
        (challenge_id, match_id, _iso(now), table_id),
    )


def _release_table(connection: sqlite3.Connection, table_id: str, *, now: datetime) -> None:
    connection.execute(
        """
        UPDATE pvp_table_runtime
        SET status = 'open',
            current_challenge_id = NULL,
            current_match_id = NULL,
            updated_at = ?
        WHERE table_id = ?
        """,
        (_iso(now), table_id),
    )


def _started_cap_reached(
    connection: sqlite3.Connection,
    challenge: sqlite3.Row,
    throttle: dict[str, Any],
) -> bool:
    if not bool(challenge["mandatory"]):
        return False
    cap = int(throttle["max_started_per_player_per_act"])
    if cap <= 0:
        return True
    for player_id in (str(challenge["challenger_id"]), str(challenge["target_id"])):
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM gwent_runtime_matches m
            JOIN pvp_challenges c ON c.challenge_id = m.challenge_id
            WHERE m.act_id = ?
              AND c.mandatory = 1
              AND m.status IN ('active', 'awaiting_finish', 'needs_master_review', 'finished')
              AND (? IN (m.challenger_id, m.target_id))
            """,
            (challenge["act_id"], player_id),
        ).fetchone()[0]
        if int(count) >= cap:
            return True
    return False


def _spend_challenge_token(
    connection: sqlite3.Connection, player_id: str, now: datetime
) -> None:
    row = connection.execute(
        """
        SELECT challenge_tokens
        FROM player_runtime_state
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if row is None or _to_int(row["challenge_tokens"]) <= 0:
        raise PvpError(f"Player has no challenge tokens: {player_id}")
    connection.execute(
        """
        UPDATE player_runtime_state
        SET challenge_tokens = challenge_tokens - 1,
            updated_at = ?
        WHERE player_id = ?
        """,
        (_iso(now), player_id),
    )


def _refund_challenge_token(
    connection: sqlite3.Connection, player_id: str, now: datetime
) -> None:
    connection.execute(
        """
        UPDATE player_runtime_state
        SET challenge_tokens = challenge_tokens + 1,
            updated_at = ?
        WHERE player_id = ?
        """,
        (_iso(now), player_id),
    )


def _should_refund_pre_start_refusal(challenge: sqlite3.Row, reason: str) -> bool:
    if reason not in REFUNDABLE_PRE_START_REFUSALS:
        return False
    if not bool(challenge["mandatory"]) or bool(challenge["master_approval"]):
        return False
    if challenge["started_at"]:
        return False
    return str(challenge["status"]) not in {"started", "needs_master_review", *FINAL_CHALLENGE_STATES}


def _challenge_payload(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    duplicate: bool = False,
) -> dict[str, Any]:
    payload = _challenge_row_to_dict(row)
    stake = _stake_payload(connection, str(row["challenge_id"]))
    payload["stake"] = stake
    payload["duplicate"] = duplicate
    return payload


def _match_payload(connection: sqlite3.Connection, row: sqlite3.Row | dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    rounds = [
        _round_row_to_dict(round_row)
        for round_row in connection.execute(
            """
            SELECT *
            FROM gwent_rounds
            WHERE match_id = ?
            ORDER BY round_number
            """,
            (row["match_id"],),
        ).fetchall()
    ]
    return {
        "match_id": row["match_id"],
        "challenge_id": row["challenge_id"],
        "challenger_id": row["challenger_id"],
        "target_id": row["target_id"],
        "act_id": row["act_id"],
        "status": row["status"],
        "table_id": row["table_id"],
        "deck_state": _json_loads(str(row["deck_state_json"]), {}),
        "round_losses": _json_loads(str(row["round_losses_json"]), {}),
        "winner_id": row["winner_id"],
        "review_reason": row["review_reason"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "result_applied_at": row["result_applied_at"],
        "duration_seconds": row["duration_seconds"],
        "balance_report": _json_loads(str(row["balance_report_json"]), {}),
        "rounds": rounds,
    }


def _challenge_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "challenge_id": row["challenge_id"],
        "challenger_id": row["challenger_id"],
        "target_id": row["target_id"],
        "act_id": row["act_id"],
        "status": row["status"],
        "mandatory": bool(row["mandatory"]),
        "stake_json": _json_loads(str(row["stake_json"]), {}),
        "table_id": row["table_id"],
        "assigned_zone": row["assigned_zone"],
        "start_window_deadline": row["start_window_deadline"],
        "refusal_reason": row["refusal_reason"],
        "review_reason": row["review_reason"],
        "master_approval": bool(row["master_approval"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "resolved_at": row["resolved_at"],
    }


def _round_row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "round_id": int(row["round_id"]),
        "match_id": row["match_id"],
        "round_number": int(row["round_number"]),
        "round_state": _json_loads(str(row["round_state_json"]), {}),
        "row_scores": _json_loads(str(row["row_scores_json"]), {}),
        "passed": _json_loads(str(row["passed_json"]), {}),
        "winner_id": row["winner_id"],
        "tie": bool(row["tie"]),
        "review_required": bool(row["review_required"]),
        "created_at": row["created_at"],
    }


def _stake_payload(connection: sqlite3.Connection, challenge_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT *
        FROM pvp_stake_ledger
        WHERE challenge_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (challenge_id,),
    ).fetchone()
    return _stake_row_to_dict(row) if row is not None else None


def _stake_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "stake_ledger_id": row["stake_ledger_id"],
        "challenge_id": row["challenge_id"],
        "match_id": row["match_id"],
        "asset_type": row["asset_type"],
        "asset_id": row["asset_id"],
        "quantity": _to_int(row["quantity"]),
        "owner_player_id": row["owner_player_id"],
        "pending_target_player_id": row["pending_target_player_id"],
        "status": row["status"],
        "winner_id": row["winner_id"],
        "loser_id": row["loser_id"],
        "created_at": row["created_at"],
        "applied_at": row["applied_at"],
    }


def _conversion_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "conversion_id": row["conversion_id"],
        "player_id": row["player_id"],
        "lord_id": row["lord_id"],
        "domain_id": row["domain_id"],
        "personal_card_id": row["personal_card_id"],
        "army_unit_card_id": row["army_unit_card_id"],
        "tier": int(row["tier"]),
        "status": row["status"],
        "source": row["source"],
        "created_at": row["created_at"],
    }


def _balance_report_base(
    challenge: sqlite3.Row,
    table_id: str,
    started_at: datetime,
) -> dict[str, Any]:
    return {
        "profile": "15_person_full_gwent",
        "challenge_id": challenge["challenge_id"],
        "act_id": challenge["act_id"],
        "table_id": table_id,
        "start_window_deadline": challenge["start_window_deadline"],
        "started_at": _iso(started_at),
        "target_duration_min": 20,
        "master_acceleration_review_min": 25,
        "no_match_time_limit_after_start": True,
    }


def _round_submissions_from_state(
    round_state: dict[str, Any],
    players: list[str],
    *,
    actor_id: str | None,
) -> dict[str, dict[str, Any]]:
    submissions: dict[str, dict[str, Any]] = {}
    for play in _normalize_plays(round_state):
        player_id = str(play.get("player_id") or "")
        if player_id not in players:
            raise PvpError(f"Round play references a non-participant: {player_id}")
        if actor_id is not None and player_id != actor_id:
            raise PvpError("Round play player_id must match authenticated player.")
        submissions.setdefault(player_id, {"plays": []})["plays"].append(dict(play))

    raw_passed = round_state.get("passed")
    if raw_passed is None:
        raw_passed = round_state.get("passed_flags")
    if raw_passed is None:
        raw_passed = {}
    if not isinstance(raw_passed, dict):
        raise PvpError("Gwent round_state.passed must be an object.")
    for player_id, passed in raw_passed.items():
        normalized_player_id = str(player_id)
        if normalized_player_id not in players:
            raise PvpError(f"Round passed payload references a non-participant: {normalized_player_id}")
        if actor_id is not None and normalized_player_id != actor_id:
            raise PvpError("Round passed payload must match authenticated player.")
        submissions.setdefault(normalized_player_id, {"plays": []})["passed"] = bool(passed)

    return {
        player_id: {
            "plays": list(submission.get("plays") or []),
            **({"passed": bool(submission["passed"])} if "passed" in submission else {}),
        }
        for player_id, submission in submissions.items()
        if submission.get("plays") or "passed" in submission
    }


def _validate_round_submission_state(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    round_state: dict[str, Any],
    deck_state: dict[str, Any],
) -> None:
    _resolve_round_state(connection, match, round_state, deepcopy(deck_state))


def _is_pending_round_row(row: sqlite3.Row) -> bool:
    state = _json_loads(str(row["round_state_json"]), {})
    return isinstance(state, dict) and str(state.get("status") or "") == GWENT_PENDING_ROUND_STATUS


def _pending_submissions(
    pending_state: dict[str, Any],
    players: list[str],
) -> dict[str, dict[str, Any]]:
    raw_submissions = pending_state.get("submissions") if isinstance(pending_state, dict) else {}
    if not isinstance(raw_submissions, dict):
        return {}
    submissions: dict[str, dict[str, Any]] = {}
    for player_id in players:
        raw_submission = raw_submissions.get(player_id)
        if not isinstance(raw_submission, dict):
            continue
        plays = raw_submission.get("plays") or []
        if not isinstance(plays, list):
            plays = []
        submission: dict[str, Any] = {"plays": [dict(play) for play in plays if isinstance(play, dict)]}
        if "passed" in raw_submission:
            submission["passed"] = bool(raw_submission["passed"])
        if submission["plays"] or "passed" in submission:
            submissions[player_id] = submission
    return submissions


def _pending_submission_order(
    pending_state: dict[str, Any],
    submissions: dict[str, dict[str, Any]],
) -> list[str]:
    raw_order = pending_state.get("submission_order") if isinstance(pending_state, dict) else []
    order = [str(player_id) for player_id in raw_order] if isinstance(raw_order, list) else []
    ordered = [player_id for player_id in order if player_id in submissions]
    for player_id in submissions:
        if player_id not in ordered:
            ordered.append(player_id)
    return ordered


def _pending_round_state(
    submissions: dict[str, dict[str, Any]],
    players: list[str],
    *,
    order: list[str] | None = None,
) -> dict[str, Any]:
    ready_players = [player_id for player_id in players if player_id in submissions]
    missing_players = [player_id for player_id in players if player_id not in submissions]
    submission_order = list(order or [player_id for player_id in players if player_id in submissions])
    return {
        "status": GWENT_PENDING_ROUND_STATUS,
        "submissions": submissions,
        "submission_order": submission_order,
        "ready_players": ready_players,
        "missing_players": missing_players,
    }


def _all_round_players_ready(
    submissions: dict[str, dict[str, Any]],
    players: list[str],
) -> bool:
    return all(player_id in submissions for player_id in players)


def _round_state_from_submissions(
    submissions: dict[str, dict[str, Any]],
    players: list[str],
    *,
    order: list[str] | None = None,
) -> dict[str, Any]:
    ordered_players = list(order or [player_id for player_id in players if player_id in submissions])
    plays: list[dict[str, Any]] = []
    for player_id in ordered_players:
        submission = submissions.get(player_id) or {}
        plays.extend(dict(play) for play in submission.get("plays") or [])
    return {
        "plays": plays,
        "passed": _passed_from_submissions(submissions, players),
    }


def _passed_from_submissions(
    submissions: dict[str, dict[str, Any]],
    players: list[str],
) -> dict[str, bool]:
    return {
        player_id: bool(submission["passed"])
        for player_id in players
        if (submission := submissions.get(player_id)) is not None and "passed" in submission
    }


def _canonical_submission(submission: dict[str, Any]) -> str:
    return _json_dumps(
        {
            "plays": list(submission.get("plays") or []),
            **({"passed": bool(submission["passed"])} if "passed" in submission else {}),
        }
    )


def _normalize_plays(round_state: dict[str, Any]) -> list[dict[str, Any]]:
    raw = round_state.get("plays")
    if raw is None:
        raw = round_state.get("round_state", {}).get("plays") if isinstance(round_state.get("round_state"), dict) else []
    if not isinstance(raw, list):
        raise PvpError("Gwent round_state.plays must be a list.")
    normalized = []
    for play in raw:
        if not isinstance(play, dict):
            raise PvpError("Each Gwent play must be an object.")
        normalized.append(dict(play))
    return normalized


def _opponent_id(players: list[str], player_id: str) -> str:
    for other_id in players:
        if other_id != player_id:
            return other_id
    raise PvpError(f"Gwent play has no opponent for player: {player_id}")


def _row_for_card(card: sqlite3.Row, requested_row: str) -> str:
    card_row = str(card["row"])
    effect = str(card["effect"] or "none")
    if effect == "agile" and requested_row in {"melee", "ranged"}:
        return requested_row
    if card_row in GWENT_ROWS:
        return card_row
    return _row_name(requested_row or "melee")


def _row_name(value: str) -> str:
    if value not in GWENT_ROWS:
        raise PvpError(f"Unsupported Gwent row: {value}")
    return value


def _remove_card_from_board(
    rows: dict[str, list[dict[str, Any]]],
    target_card_id: str,
) -> dict[str, Any] | None:
    for units in rows.values():
        for unit in units:
            if unit["card_id"] == target_card_id and not unit["removed"] and not unit["hero"]:
                unit["removed"] = True
                unit["returned_by_decoy"] = True
                return unit
    return None


def _gwent_rules(connection: sqlite3.Connection) -> dict[str, int | str]:
    defaults: dict[str, int | str] = {
        "deck_min_unit_cards": 22,
        "max_special_cards": 10,
        "hand_size": 10,
        "mulligans": 2,
        "row_count": 3,
        "tie_handling": "tie_no_stake_transfer",
    }
    row = _first_row(connection, "gwent_rules")
    if row is None:
        return defaults
    return {
        "deck_min_unit_cards": _to_int(row["deck_min_unit_cards"]),
        "max_special_cards": _to_int(row["max_special_cards"]),
        "hand_size": _to_int(row["hand_size"]),
        "mulligans": _to_int(row["mulligans"]),
        "row_count": _to_int(row["row_count"]),
        "tie_handling": str(row["tie_handling"]),
    }


def _deck_for_player(connection: sqlite3.Connection, player_id: str) -> sqlite3.Row:
    if not _table_exists(connection, "gwent_decks"):
        raise PvpError("No imported Gwent decks are available.")
    row = connection.execute(
        """
        SELECT *
        FROM gwent_decks
        WHERE player_id = ?
        ORDER BY _row_number
        LIMIT 1
        """,
        (player_id,),
    ).fetchone()
    if row is None:
        raise PvpError(f"No Gwent deck for player: {player_id}")
    return row


def _cards_by_id(connection: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    if not _table_exists(connection, "gwent_cards"):
        raise PvpError("No imported Gwent cards are available.")
    return {
        str(row["card_id"]): row
        for row in connection.execute(
            """
            SELECT *
            FROM gwent_cards
            ORDER BY _row_number
            """
        ).fetchall()
    }


def _fetch_throttle_state(connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT mode, max_tables, max_started_per_player_per_act, final_lock_behavior
        FROM pvp_throttle_state
        WHERE id = 1
        """
    ).fetchone()
    if row is None:
        return {
            "mode": "normal",
            "max_tables": 2,
            "max_started_per_player_per_act": 2,
            "final_lock_behavior": "no_new_challenges_after_final_lock",
        }
    return {
        "mode": row["mode"],
        "max_tables": _to_int(row["max_tables"]),
        "max_started_per_player_per_act": _to_int(row["max_started_per_player_per_act"]),
        "final_lock_behavior": row["final_lock_behavior"],
    }


def _fetch_throttle_rule(connection: sqlite3.Connection, mode: str) -> sqlite3.Row | None:
    if not _table_exists(connection, "pvp_throttle_rules"):
        if mode == "normal":
            return _dict_row(
                {
                    "mode": "normal",
                    "max_tables": 2,
                    "max_started_per_player_per_act": 2,
                    "final_lock_behavior": "no_new_challenges_after_final_lock",
                }
            )
        if mode == "limited":
            return _dict_row(
                {
                    "mode": "limited",
                    "max_tables": 1,
                    "max_started_per_player_per_act": 1,
                    "final_lock_behavior": "no_new_challenges_after_final_lock",
                }
            )
        if mode == "paused":
            return _dict_row(
                {
                    "mode": "paused",
                    "max_tables": 0,
                    "max_started_per_player_per_act": 0,
                    "final_lock_behavior": "no_new_challenges_after_final_lock",
                }
            )
        return None
    return connection.execute(
        """
        SELECT *
        FROM pvp_throttle_rules
        WHERE mode = ?
        LIMIT 1
        """,
        (mode,),
    ).fetchone()


def _refusal_rule(connection: sqlite3.Connection, reason: str) -> dict[str, str]:
    if _table_exists(connection, "pvp_refusal_rules"):
        row = connection.execute(
            """
            SELECT reason, severity, default_outcome
            FROM pvp_refusal_rules
            WHERE reason = ?
            LIMIT 1
            """,
            (reason,),
        ).fetchone()
        if row is not None:
            return {
                "reason": str(row["reason"]),
                "severity": str(row["severity"]),
                "default_outcome": str(row["default_outcome"]),
            }
    fallback = {
        "active_scene": ("P2", "deferred_window"),
        "table_overload": ("P2", "queued"),
        "valid_ignore": ("P2", "no_penalty_review"),
        "safety_stop": ("P0", "needs_master_review"),
        "unsafe_path": ("P1", "needs_master_review"),
        "force_majeure": ("P1", "needs_master_review"),
    }
    if reason not in fallback:
        raise PvpError(f"Unsupported PvP refusal reason: {reason}")
    severity, outcome = fallback[reason]
    return {"reason": reason, "severity": severity, "default_outcome": outcome}


def _require_personal_pvp_player(
    connection: sqlite3.Connection, player_id: str
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT player_id, role_type, challenge_tokens
        FROM player_runtime_state
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if row is None:
        raise PvpError(f"Unknown player_id: {player_id}")
    if str(row["role_type"]) not in PVP_PLAYER_ROLES:
        raise PvpError(f"Player cannot join personal PvP: {player_id}")
    return {"player_id": row["player_id"], "role_type": row["role_type"], "challenge_tokens": row["challenge_tokens"]}


def _current_act_id(connection: sqlite3.Connection) -> str:
    row = connection.execute(
        "SELECT current_act_id FROM act_state WHERE id = 1"
    ).fetchone()
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


def _final_lock_active(connection: sqlite3.Connection) -> bool:
    row = connection.execute("SELECT locked_at FROM final_lock_state WHERE id = 1").fetchone()
    return bool(row and row["locked_at"])


def _active_challenge_exists(connection: sqlite3.Connection, player_id: str) -> bool:
    placeholders = ", ".join("?" for _ in ACTIVE_CHALLENGE_STATES)
    row = connection.execute(
        f"""
        SELECT 1
        FROM pvp_challenges
        WHERE status IN ({placeholders})
          AND (challenger_id = ? OR target_id = ?)
        LIMIT 1
        """,
        (*sorted(ACTIVE_CHALLENGE_STATES), player_id, player_id),
    ).fetchone()
    return row is not None


def _validate_stake(stake: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(stake, dict):
        raise PvpError("PvP stake must be an object.")
    asset_type = str(stake.get("asset_type") or "").strip().lower()
    if asset_type == GOLD_STAKE_ASSET_TYPE:
        raw_amount = stake.get("amount", stake.get("quantity", stake.get("gold")))
        try:
            amount = int(raw_amount)
        except (TypeError, ValueError) as exc:
            raise PvpError("Gold PvP stake requires a positive amount.") from exc
        if amount <= 0:
            raise PvpError("Gold PvP stake requires a positive amount.")
        return {
            "asset_type": GOLD_STAKE_ASSET_TYPE,
            "asset_id": GOLD_STAKE_ASSET_ID,
            "quantity": amount,
            "transfer_on_finish": bool(stake.get("transfer_on_finish", True)),
        }
    asset_id = str(stake.get("asset_id") or "").strip()
    if not asset_type or not asset_id:
        raise PvpError("PvP stake requires asset_type and asset_id.")
    return {
        "asset_type": asset_type,
        "asset_id": asset_id,
        "quantity": 1,
        "transfer_on_finish": bool(stake.get("transfer_on_finish", True)),
    }


def _assert_stake_asset_owned(
    connection: sqlite3.Connection,
    *,
    stake: dict[str, Any],
    owner_player_id: str,
) -> None:
    asset_type = stake["asset_type"]
    asset_id = stake["asset_id"]
    if not _stake_asset_exists(connection, asset_type, asset_id):
        raise AssetContractError(
            "unknown_stake_asset",
            f"Unknown PvP stake asset: {asset_type}:{asset_id}.",
            404,
        )
    ownership = ownership_for_asset(
        connection,
        owner_player_id=owner_player_id,
        asset_type=asset_type,
        asset_id=asset_id,
    )
    if _to_int(ownership["quantity"]) < 1:
        raise AssetContractError(
            "asset_owner_mismatch",
            f"{owner_player_id} does not own PvP stake asset {asset_type}:{asset_id}.",
            409,
        )


def _is_gold_stake(stake: dict[str, Any]) -> bool:
    return (
        str(stake.get("asset_type") or "").strip().lower() == GOLD_STAKE_ASSET_TYPE
        and str(stake.get("asset_id") or "").strip().lower() == GOLD_STAKE_ASSET_ID
    )


def _stake_quantity(stake: dict[str, Any]) -> int:
    try:
        quantity = int(stake.get("quantity", 1))
    except (TypeError, ValueError) as exc:
        raise PvpError("PvP stake quantity must be a positive integer.") from exc
    if quantity <= 0:
        raise PvpError("PvP stake quantity must be a positive integer.")
    return quantity


def _assert_gold_stake_available(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    amount: int,
) -> None:
    row = connection.execute(
        """
        SELECT gold
        FROM player_runtime_state
        WHERE player_id = ?
        """,
        (player_id,),
    ).fetchone()
    if row is None or _to_int(row["gold"]) < amount:
        available = 0 if row is None else _to_int(row["gold"])
        raise PvpError(
            f"{player_id} does not have enough gold for PvP stake: needs {amount}, has {available}."
        )


def _reserve_gold_stake(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    amount: int,
    now: datetime,
) -> None:
    updated = connection.execute(
        """
        UPDATE player_runtime_state
        SET gold = gold - ?, updated_at = ?
        WHERE player_id = ? AND gold >= ?
        """,
        (amount, _iso(now), player_id, amount),
    )
    if not updated.rowcount:
        _assert_gold_stake_available(connection, player_id=player_id, amount=amount)


def _refund_gold_stake_once(
    connection: sqlite3.Connection,
    *,
    challenge_id: str,
    now: datetime,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT *
        FROM pvp_stake_ledger
        WHERE challenge_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (challenge_id,),
    ).fetchone()
    if row is None or not _is_gold_stake(dict(row)):
        return None
    if str(row["status"]) != "locked":
        return _stake_row_to_dict(row)
    amount = _stake_quantity(dict(row))
    connection.execute(
        """
        UPDATE player_runtime_state
        SET gold = gold + ?, updated_at = ?
        WHERE player_id = ?
        """,
        (amount, _iso(now), row["owner_player_id"]),
    )
    connection.execute(
        """
        UPDATE pvp_stake_ledger
        SET status = 'refunded',
            applied_at = ?
        WHERE stake_ledger_id = ? AND status = 'locked'
        """,
        (_iso(now), row["stake_ledger_id"]),
    )
    return _stake_row_to_dict(
        connection.execute(
            "SELECT * FROM pvp_stake_ledger WHERE stake_ledger_id = ?",
            (row["stake_ledger_id"],),
        ).fetchone()
    )


def _stake_asset_exists(connection: sqlite3.Connection, asset_type: str, asset_id: str) -> bool:
    content_refs = {
        "item": (("items", "item_id"),),
        "card": (("cards", "card_id"), ("gwent_cards", "card_id")),
        "artifact": (("artifacts", "artifact_id"),),
        "order_object": (("items", "item_id"),),
        "final_object": (("items", "item_id"), ("artifacts", "artifact_id")),
    }
    refs = content_refs.get(str(asset_type).strip().lower())
    if refs is None:
        ownership_for_asset(
            connection,
            owner_player_id="__stake_type_validation__",
            asset_type=asset_type,
            asset_id=asset_id,
        )
        return False
    for table_name, id_column in refs:
        if not _table_exists(connection, table_name):
            continue
        row = connection.execute(
            f"SELECT 1 FROM {table_name} WHERE {id_column} = ? LIMIT 1",
            (asset_id,),
        ).fetchone()
        if row is not None:
            return True
    return False


def _stake_locked(connection: sqlite3.Connection, asset_type: str, asset_id: str) -> bool:
    if str(asset_type).strip().lower() == GOLD_STAKE_ASSET_TYPE:
        return False
    row = connection.execute(
        """
        SELECT 1
        FROM pvp_stake_ledger
        WHERE asset_type = ? AND asset_id = ? AND status = 'locked'
        LIMIT 1
        """,
        (asset_type, asset_id),
    ).fetchone()
    return row is not None


def _start_window_minutes(connection: sqlite3.Connection, act_id: str) -> int:
    if _table_exists(connection, "challenge_tokens"):
        row = connection.execute(
            """
            SELECT start_window_min
            FROM challenge_tokens
            WHERE act_id = ?
            LIMIT 1
            """,
            (act_id,),
        ).fetchone()
        if row is not None:
            return _to_int(row["start_window_min"]) or 30
    return 30


def _zone_for_assignment(connection: sqlite3.Connection, table: sqlite3.Row | None) -> str:
    if table is not None:
        return str(table["zone_name"])
    row = connection.execute(
        """
        SELECT zone_name
        FROM pvp_table_runtime
        ORDER BY table_id
        LIMIT 1
        """
    ).fetchone()
    return str(row["zone_name"]) if row is not None else "main_house_table"


def _fetch_challenge(connection: sqlite3.Connection, challenge_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM pvp_challenges WHERE challenge_id = ?",
        (challenge_id,),
    ).fetchone()


def _fetch_challenge_required(connection: sqlite3.Connection, challenge_id: str) -> sqlite3.Row:
    row = _fetch_challenge(connection, challenge_id)
    if row is None:
        raise PvpError(f"Unknown PvP challenge: {challenge_id}")
    return row


def _fetch_match_required(connection: sqlite3.Connection, match_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM gwent_runtime_matches WHERE match_id = ?",
        (match_id,),
    ).fetchone()
    if row is None:
        raise PvpError(f"Unknown Gwent match: {match_id}")
    return row


def _match_by_challenge(connection: sqlite3.Connection, challenge_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM gwent_runtime_matches WHERE challenge_id = ?",
        (challenge_id,),
    ).fetchone()


def _next_round_number(connection: sqlite3.Connection, match_id: str) -> int:
    row = connection.execute(
        "SELECT COALESCE(MAX(round_number), 0) + 1 AS next_round FROM gwent_rounds WHERE match_id = ?",
        (match_id,),
    ).fetchone()
    return int(row["next_round"])


def _fetch_required(
    connection: sqlite3.Connection,
    table_name: str,
    id_column: str,
    row_id: str,
) -> sqlite3.Row:
    row = _fetch_optional(connection, table_name, id_column, row_id)
    if row is None:
        raise PvpError(f"Unknown {table_name}.{id_column}: {row_id}")
    return row


def _fetch_optional(
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


def _first_row(connection: sqlite3.Connection, table_name: str) -> sqlite3.Row | None:
    if not _table_exists(connection, table_name):
        return None
    return connection.execute(f'SELECT * FROM "{table_name}" ORDER BY _row_number LIMIT 1').fetchone()


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


def _split_ids(value: str) -> list[str]:
    return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: str, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")


def _to_int(value: object) -> int:
    if value is None or str(value) == "":
        return 0
    return int(value)


def _dict_row(payload: dict[str, Any]) -> dict[str, Any]:
    return payload
