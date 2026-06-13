"""Personal PvP and custom Gwent runtime service."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import random
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
GWENT_BOT_PLAYER_ID = "p_gwent_bot_training"
GWENT_BOT_DISPLAY_NAME = "Тренировочный соперник"
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


def _row_get(row: sqlite3.Row | dict[str, Any], key: str, default: Any = "") -> Any:
    try:
        if hasattr(row, "keys") and key not in row.keys():
            return default
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _card_effects(card: sqlite3.Row | dict[str, Any]) -> list[str]:
    primary = str(_row_get(card, "effect", "none") or "none").strip()
    tags = [
        tag
        for tag in _split_ids(str(_row_get(card, "ability_tags", "") or ""))
        if tag and tag != primary
    ]
    effects = [effect for effect in [primary, *tags] if effect]
    if not effects:
        return ["none"]
    return effects


def _card_has_effect(card: sqlite3.Row | dict[str, Any], effect: str) -> bool:
    return effect in _card_effects(card)


def _unit_effects(unit: dict[str, Any]) -> list[str]:
    effects = unit.get("effects")
    if isinstance(effects, list) and effects:
        return [str(effect) for effect in effects]
    return [str(unit.get("effect") or "none")]


def _unit_has_effect(unit: dict[str, Any], effect: str) -> bool:
    return effect in _unit_effects(unit)


def _card_group(card: sqlite3.Row | dict[str, Any], column: str, fallback: str) -> str:
    value = str(_row_get(card, column, "") or "").strip()
    return value or fallback


def _unit_group(unit: dict[str, Any], column: str, fallback: str) -> str:
    value = str(unit.get(column) or "").strip()
    return value or fallback


def _gwent_shuffle_seed(challenge_id: str, player_id: str, deck_id: str) -> str:
    return f"{challenge_id}:{player_id}:{deck_id}:witcher3-gwent-v2"


def _shuffle_card_ids(card_ids: list[str], seed: str) -> list[str]:
    shuffled = list(card_ids)
    random.Random(seed).shuffle(shuffled)
    return shuffled


def _gwent_shuffle_audit(deck_state: dict[str, Any], players: list[str]) -> dict[str, Any]:
    return {
        player_id: {
            "deck_id": deck_state.get(player_id, {}).get("deck_id"),
            "shuffle_seed": deck_state.get(player_id, {}).get("shuffle_seed"),
            "shuffle_log": deck_state.get(player_id, {}).get("shuffle_log") or {},
        }
        for player_id in players
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
    deck_ids_by_player: dict[str, str] | None = None
    preferred_starting_player_id: str | None = None
    source: str = "pvp_api"


@dataclass(frozen=True)
class GwentPreparationInput:
    challenge_id: str
    player_id: str
    mulligans: list[str] | None = None
    deck_id: str | None = None
    preferred_starting_player_id: str | None = None
    source: str = "ios_gwent_app"


@dataclass(frozen=True)
class GwentActionInput:
    match_id: str
    player_id: str
    action: str
    round_number: int | None = None
    card_id: str | None = None
    row: str | None = None
    target_card_id: str | None = None
    discard_card_ids: list[str] | None = None
    revive_card_id: str | None = None
    revive_row: str | None = None
    action_id: str | None = None
    source: str = "pvp_api"


@dataclass(frozen=True)
class GwentBotMatchInput:
    player_id: str
    mulligans: list[str] | None = None
    deck_id: str | None = None
    source: str = "ios_gwent_app"


@dataclass(frozen=True)
class GwentDeckSaveInput:
    player_id: str
    leader_card_id: str
    card_ids: list[str]
    deck_id: str | None = None
    source: str = "ios_gwent_app"


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


def get_player_pvp_state(connection: sqlite3.Connection, player_id: str) -> dict[str, Any]:
    """Return the participant-scoped active Gwent state for a mobile client."""
    ensure_pvp_runtime_state(connection)
    normalized_player_id = str(player_id).strip()
    if not normalized_player_id:
        raise PvpError("player_id is required for PvP state.")

    active_challenge = _active_challenge_for_player(connection, normalized_player_id)
    active_match = _active_match_for_player(connection, normalized_player_id)
    if active_match is None and active_challenge is not None:
        active_match = _match_by_challenge(connection, str(active_challenge["challenge_id"]))
    recent_match = (
        None
        if active_match is not None
        else _recent_finished_match_for_player(connection, normalized_player_id)
    )
    runtime_row = connection.execute(
        """
        SELECT role_type, challenge_tokens
        FROM player_runtime_state
        WHERE player_id = ?
        """,
        (normalized_player_id,),
    ).fetchone()
    challenge_tokens = _to_int(runtime_row["challenge_tokens"]) if runtime_row is not None else 0

    match_payload = _match_payload(connection, active_match)
    current_round = _current_round_payload(connection, active_match, normalized_player_id)
    recent_match_payload = _player_scoped_match_payload(
        _match_payload(connection, recent_match),
        normalized_player_id,
        None,
    )
    player_deck_state = {}
    opponent_id = None
    table = None
    if match_payload is not None:
        players = [str(match_payload["challenger_id"]), str(match_payload["target_id"])]
        opponent_id = next((candidate for candidate in players if candidate != normalized_player_id), None)
        deck_state = match_payload.get("deck_state") if isinstance(match_payload, dict) else {}
        if isinstance(deck_state, dict):
            player_deck_state = dict(deck_state.get(normalized_player_id) or {})
        active_hand = (
            current_round.get("player_hand")
            if isinstance(current_round, dict) and isinstance(current_round.get("player_hand"), list)
            else None
        )
        if active_hand is not None:
            player_deck_state["hand"] = list(active_hand)
        table = _pvp_table_state(connection, str(match_payload.get("table_id") or ""))
        match_payload = _player_scoped_match_payload(match_payload, normalized_player_id, current_round)
    elif recent_match_payload is not None:
        players = [str(recent_match_payload["challenger_id"]), str(recent_match_payload["target_id"])]
        opponent_id = next((candidate for candidate in players if candidate != normalized_player_id), None)
        table = _pvp_table_state(connection, str(recent_match_payload.get("table_id") or ""))
    elif active_challenge is not None:
        opponent_id = (
            str(active_challenge["target_id"])
            if str(active_challenge["challenger_id"]) == normalized_player_id
            else str(active_challenge["challenger_id"])
        )
        table = _pvp_table_state(connection, str(active_challenge["table_id"] or ""))

    return {
        "player_id": normalized_player_id,
        "opponent_id": opponent_id,
        "role_type": str(runtime_row["role_type"]) if runtime_row is not None else None,
        "challenge_tokens": challenge_tokens,
        "can_create_challenge": bool(challenge_tokens > 0 and active_challenge is None and active_match is None),
        "active_challenge": _challenge_payload(connection, active_challenge) if active_challenge else None,
        "active_match": match_payload,
        "recent_match": recent_match_payload,
        "current_round": current_round,
        "player_deck_state": player_deck_state,
        "player_hand": list(player_deck_state.get("hand") or []),
        "leader_used": bool(player_deck_state.get("leader_used")),
        "table": table,
        "legal_actions": _player_gwent_legal_actions(
            connection,
            active_challenge,
            match_payload,
            current_round,
            player_deck_state,
            normalized_player_id,
        ),
    }


def _active_challenge_for_player(connection: sqlite3.Connection, player_id: str) -> sqlite3.Row | None:
    placeholders = ", ".join("?" for _ in ACTIVE_CHALLENGE_STATES)
    return connection.execute(
        f"""
        SELECT *
        FROM pvp_challenges
        WHERE (challenger_id = ? OR target_id = ?)
          AND status IN ({placeholders})
        ORDER BY COALESCE(updated_at, created_at) DESC, created_at DESC
        LIMIT 1
        """,
        (player_id, player_id, *sorted(ACTIVE_CHALLENGE_STATES)),
    ).fetchone()


def _active_match_for_player(connection: sqlite3.Connection, player_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM gwent_runtime_matches
        WHERE (challenger_id = ? OR target_id = ?)
          AND status != 'finished'
        ORDER BY COALESCE(started_at, created_at) DESC, created_at DESC
        LIMIT 1
        """,
        (player_id, player_id),
    ).fetchone()


def _recent_finished_match_for_player(connection: sqlite3.Connection, player_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM gwent_runtime_matches
        WHERE (challenger_id = ? OR target_id = ?)
          AND status = 'finished'
        ORDER BY COALESCE(finished_at, started_at, created_at) DESC, created_at DESC
        LIMIT 1
        """,
        (player_id, player_id),
    ).fetchone()


def _current_round_payload(
    connection: sqlite3.Connection,
    match: sqlite3.Row | None,
    player_id: str,
) -> dict[str, Any] | None:
    if match is None:
        return None
    row = connection.execute(
        """
        SELECT *
        FROM gwent_rounds
        WHERE match_id = ?
        ORDER BY round_number DESC
        LIMIT 1
        """,
        (match["match_id"],),
    ).fetchone()
    if row is not None and (_is_pending_round_row(row) or bool(row["review_required"])):
        payload = _round_row_to_dict(row) or {}
        round_state = payload.get("round_state") if isinstance(payload, dict) else {}
        if not isinstance(round_state, dict):
            round_state = {}
        ready_players = [str(player) for player in round_state.get("ready_players") or []]
        missing_players = [str(player) for player in round_state.get("missing_players") or []]
        status = str(round_state.get("status") or GWENT_ROUND_REVIEW_STATUS)
        payload.update(
            {
                "status": status,
                "ready_players": ready_players,
                "missing_players": missing_players,
                "player_submitted": player_id in ready_players,
            }
        )
        return payload
    deck_state = _json_loads(str(match["deck_state_json"]), {})
    active_round_payload = _active_round_player_payload(connection, match, deck_state, player_id)
    if active_round_payload is not None:
        return active_round_payload
    if row is None:
        return {
            "round_number": _next_round_number(connection, str(match["match_id"])),
            "status": "ready_for_submission",
            "ready_players": [],
            "missing_players": [str(match["challenger_id"]), str(match["target_id"])],
            "player_submitted": False,
        }
    payload = _round_row_to_dict(row) or {}
    round_state = payload.get("round_state") if isinstance(payload, dict) else {}
    if not isinstance(round_state, dict):
        round_state = {}
    ready_players = [str(player) for player in round_state.get("ready_players") or []]
    missing_players = [str(player) for player in round_state.get("missing_players") or []]
    status = str(round_state.get("status") or ("pending_player_submissions" if _is_pending_round_row(row) else "resolved"))
    payload.update(
        {
            "status": status,
            "ready_players": ready_players,
            "missing_players": missing_players,
            "player_submitted": player_id in ready_players,
        }
    )
    return payload


def _pvp_table_state(connection: sqlite3.Connection, table_id: str) -> dict[str, Any] | None:
    if not table_id:
        return None
    row = connection.execute(
        """
        SELECT table_id, status, zone_name, current_challenge_id, current_match_id
        FROM pvp_table_runtime
        WHERE table_id = ?
        """,
        (table_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "table_id": row["table_id"],
        "status": row["status"],
        "zone_name": row["zone_name"],
        "current_challenge_id": row["current_challenge_id"],
        "current_match_id": row["current_match_id"],
    }


def _player_scoped_match_payload(
    match: dict[str, Any] | None,
    player_id: str,
    current_round: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if match is None:
        return None
    scoped = deepcopy(match)
    deck_state = scoped.get("deck_state")
    if not isinstance(deck_state, dict):
        return scoped
    for deck_player_id, raw_state in list(deck_state.items()):
        if deck_player_id in {"rules", "cards_burn_after_round", "active_round", "action_ids", "bot"}:
            continue
        if not isinstance(raw_state, dict):
            continue
        state = dict(raw_state)
        hand = list(state.get("hand") or [])
        draw_pile = list(state.get("draw_pile") or [])
        state["hand_count"] = len(hand)
        state["draw_pile_count"] = len(draw_pile)
        if deck_player_id != player_id:
            state["hand"] = []
            state["draw_pile"] = []
            state["private_reveals"] = []
        deck_state[deck_player_id] = state
    active_round = deck_state.get("active_round")
    if isinstance(active_round, dict):
        deck_state["active_round"] = _public_active_round(active_round)
    if isinstance(current_round, dict) and isinstance(current_round.get("player_hand"), list):
        own_state = deck_state.get(player_id)
        if isinstance(own_state, dict):
            own_state["hand"] = list(current_round["player_hand"])
            own_state["hand_count"] = len(current_round["player_hand"])
    return scoped


def _public_active_round(active_round: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in active_round.items()
        if key not in {"base_deck_state", "action_ids"}
    }


def _player_playable_card_actions(
    connection: sqlite3.Connection,
    player_deck_state: dict[str, Any],
    current_round: dict[str, Any],
    player_id: str,
) -> list[dict[str, Any]]:
    hand = list(current_round.get("player_hand") or player_deck_state.get("hand") or [])
    if not hand:
        return []
    cards = _cards_by_id(connection)
    actions = []
    for card_id in hand:
        card = cards.get(str(card_id))
        if card is None:
            continue
        card_type = str(card["type"])
        effects = _card_effects(card)
        effect = effects[0]
        action: dict[str, Any] = {
            "action": "play_card",
            "card_id": str(card_id),
            "type": card_type,
            "effect": effect,
            "effects": effects,
            "allowed_rows": _allowed_rows_for_card(card),
            "requires_row": False,
            "requires_target": False,
            "target_kind": None,
            "targets": [],
        }
        if card_type == "special" and "commanders_horn" in effects:
            action["requires_row"] = True
            action["allowed_rows"] = list(GWENT_ROWS)
        elif card_type == "special" and "decoy" in effects:
            targets = _decoy_targets(current_round, player_id)
            action["requires_target"] = True
            action["target_kind"] = "own_non_hero_unit"
            action["targets"] = targets
        elif card_type == "unit" and "medic" in effects:
            targets = _medic_targets(player_deck_state, cards)
            action["target_kind"] = "graveyard_unit"
            action["targets"] = targets
        actions.append(action)
    return actions


def _allowed_rows_for_card(card: sqlite3.Row) -> list[str]:
    card_type = str(card["type"])
    effects = _card_effects(card)
    card_row = str(card["row"] or "")
    if card_type == "leader":
        return list(GWENT_ROWS)
    if card_type == "special":
        if "commanders_horn" in effects:
            return list(GWENT_ROWS)
        return []
    if "agile" in effects:
        return ["melee", "ranged"]
    if card_row in GWENT_ROWS:
        return [card_row]
    return ["melee"]


def _decoy_targets(current_round: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
    board = current_round.get("board") if isinstance(current_round, dict) else {}
    if not isinstance(board, dict):
        return []
    player_board = board.get(player_id)
    if not isinstance(player_board, dict):
        return []
    targets = []
    for row_name in GWENT_ROWS:
        units = player_board.get(row_name) or []
        if not isinstance(units, list):
            continue
        for unit in units:
            if not isinstance(unit, dict):
                continue
            if unit.get("removed") or _unit_has_effect(unit, "hero"):
                continue
            targets.append(
                {
                    "card_id": unit.get("card_id"),
                    "row": row_name,
                    "strength": unit.get("base_strength"),
                    "effect": unit.get("effect"),
                }
            )
    return targets


def _medic_targets(
    player_deck_state: dict[str, Any],
    cards: dict[str, sqlite3.Row],
) -> list[dict[str, Any]]:
    targets = []
    for card_id in player_deck_state.get("graveyard") or []:
        card = cards.get(str(card_id))
        if card is None or str(card["type"]) != "unit" or _card_has_effect(card, "hero"):
            continue
        targets.append(
            {
                "card_id": str(card_id),
                "row": str(card["row"]),
                "strength": _to_int(card["strength"]),
                "effect": str(card["effect"] or "none"),
            }
        )
    return targets


def _player_gwent_legal_actions(
    connection: sqlite3.Connection,
    challenge: sqlite3.Row | None,
    match: dict[str, Any] | None,
    current_round: dict[str, Any] | None,
    player_deck_state: dict[str, Any],
    player_id: str,
) -> dict[str, Any]:
    challenge_status = str(challenge["status"]) if challenge is not None else ""
    match_status = str(match.get("status") or "") if isinstance(match, dict) else ""
    round_status = str(current_round.get("status") or "") if isinstance(current_round, dict) else ""
    player_submitted = bool(current_round.get("player_submitted")) if isinstance(current_round, dict) else False
    round_number = int(current_round.get("round_number") or 1) if isinstance(current_round, dict) else 1
    phase = str(current_round.get("phase") or "") if isinstance(current_round, dict) else ""
    passed = current_round.get("passed") if isinstance(current_round, dict) else {}
    if not isinstance(passed, dict):
        passed = {}
    is_player_turn = bool(current_round.get("is_player_turn")) if isinstance(current_round, dict) else False
    already_passed = bool(passed.get(player_id))
    if phase == "active_turn":
        can_act = (
            match is not None
            and match_status == "active"
            and is_player_turn
            and not already_passed
            and 1 <= round_number <= 3
        )
        playable_cards = _player_playable_card_actions(
            connection,
            player_deck_state,
            current_round or {},
            player_id,
        )
        return {
            "can_start": False,
            "can_refuse": False,
            "can_play_card": can_act and bool(playable_cards),
            "can_pass": can_act,
            "can_use_leader": can_act
            and not bool(player_deck_state.get("leader_used"))
            and not bool(player_deck_state.get("leader_disabled")),
            "can_finish": match_status == "awaiting_finish",
            "round_number": round_number,
            "actor_id": player_id,
            "phase": phase,
            "turn_player_id": current_round.get("turn_player_id"),
            "is_player_turn": is_player_turn,
            "passed": passed,
            "playable_cards": playable_cards,
            "leader_card_id": player_deck_state.get("leader_card_id"),
        }
    can_play_round = (
        match is not None
        and match_status == "active"
        and round_status in {"ready_for_submission", GWENT_PENDING_ROUND_STATUS}
        and not player_submitted
        and 1 <= round_number <= 3
    )
    return {
        "can_start": challenge_status in {"assigned", "queued", "deferred"},
        "can_refuse": challenge_status in {"assigned", "queued", "deferred"},
        "can_play_card": can_play_round,
        "can_pass": can_play_round,
        "can_use_leader": can_play_round
        and not bool(player_deck_state.get("leader_used"))
        and not bool(player_deck_state.get("leader_disabled")),
        "can_finish": match_status == "awaiting_finish",
        "round_number": round_number,
        "actor_id": player_id,
        "phase": "round_submission",
        "turn_player_id": player_id if can_play_round else None,
        "is_player_turn": can_play_round,
        "playable_cards": _player_playable_card_actions(
            connection,
            player_deck_state,
            current_round or {},
            player_id,
        )
        if can_play_round
        else [],
    }


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
            deck_id=(request.deck_ids_by_player or {}).get(challenger_id),
            challenge_id=request.challenge_id,
        ),
        target_id: _build_player_deck_state(
            connection,
            target_id,
            rules,
            (request.mulligans_by_player or {}).get(target_id, []),
            deck_id=(request.deck_ids_by_player or {}).get(target_id),
            challenge_id=request.challenge_id,
        ),
        "rules": rules,
        "cards_burn_after_round": False,
    }
    starting_player_id, first_turn_effect = _resolve_first_turn_player(
        players=[challenger_id, target_id],
        deck_state=deck_state,
        preferred_starting_player_id=request.preferred_starting_player_id,
    )
    if first_turn_effect:
        deck_state.setdefault("faction_effects", []).append(first_turn_effect)
    deck_state["active_round"] = _new_active_round(
        match_id="",
        players=[challenger_id, target_id],
        deck_state=deck_state,
        round_number=1,
        starting_player_id=starting_player_id,
        now=current_time,
    )
    match_id = f"gwent_match_{uuid4().hex}"
    deck_state["active_round"]["match_id"] = match_id
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
            "starting_player_id": starting_player_id,
            "first_turn_effect": first_turn_effect,
            "shuffle_audit": _gwent_shuffle_audit(deck_state, [challenger_id, target_id]),
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


def prepare_gwent_challenge(
    connection: sqlite3.Connection,
    request: GwentPreparationInput,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    challenge = _fetch_challenge_required(connection, request.challenge_id)
    if str(challenge["status"]) == "started":
        match = _match_by_challenge(connection, request.challenge_id)
        return {
            "challenge": _challenge_payload(connection, challenge),
            "match": _match_payload(connection, match),
            "prep": _challenge_prep(challenge),
            "started": match is not None,
            "duplicate": True,
        }
    if str(challenge["status"]) in FINAL_CHALLENGE_STATES or str(challenge["status"]) == "needs_master_review":
        return {
            "challenge": _challenge_payload(connection, challenge),
            "match": None,
            "prep": _challenge_prep(challenge),
            "started": False,
            "duplicate": False,
        }

    player_id = str(request.player_id or "").strip()
    players = [str(challenge["challenger_id"]), str(challenge["target_id"])]
    if player_id not in players:
        raise PvpError(f"Gwent preparation references a non-participant: {player_id}")
    prep = _challenge_prep(challenge)
    prep.setdefault("ready_players", [])
    ready_players = [str(value) for value in prep.get("ready_players") or []]
    previous_mulligans = prep.get("mulligans_by_player", {}).get(player_id)
    previous_deck_id = ""
    if isinstance(prep.get("deck_ids_by_player"), dict):
        previous_deck_id = str(prep["deck_ids_by_player"].get(player_id) or "")
    previous_starting_player_id = ""
    if isinstance(prep.get("preferred_starting_player_ids_by_player"), dict):
        previous_starting_player_id = str(prep["preferred_starting_player_ids_by_player"].get(player_id) or "")
    if request.mulligans is None and player_id in ready_players and isinstance(previous_mulligans, list):
        mulligans = [str(card_id).strip() for card_id in previous_mulligans if str(card_id).strip()]
    else:
        mulligans = [str(card_id).strip() for card_id in (request.mulligans or []) if str(card_id).strip()]
    rules = _gwent_rules(connection)
    deck_id = str(request.deck_id or "").strip()
    effective_deck_id = deck_id or previous_deck_id
    _validate_player_mulligans(
        connection,
        player_id,
        rules,
        mulligans,
        deck_id=effective_deck_id or None,
        challenge_id=request.challenge_id,
    )
    preferred_starting_player_id = _validated_preferred_starting_player_id(
        connection,
        player_id=player_id,
        players=players,
        deck_id=effective_deck_id or None,
        requested_player_id=request.preferred_starting_player_id,
        previous_player_id=previous_starting_player_id,
        preserve_previous=(
            request.preferred_starting_player_id is None
            and player_id in ready_players
            and (not deck_id or deck_id == previous_deck_id)
        ),
    )

    duplicate = (
        player_id in ready_players
        and prep.get("mulligans_by_player", {}).get(player_id) == mulligans
        and (not deck_id or previous_deck_id == deck_id)
        and previous_starting_player_id == preferred_starting_player_id
    )
    if player_id not in ready_players:
        ready_players.append(player_id)
    prep["ready_players"] = ready_players
    prep.setdefault("mulligans_by_player", {})[player_id] = mulligans
    if deck_id:
        prep.setdefault("deck_ids_by_player", {})[player_id] = deck_id
    if preferred_starting_player_id:
        prep.setdefault("preferred_starting_player_ids_by_player", {})[player_id] = preferred_starting_player_id
    elif isinstance(prep.get("preferred_starting_player_ids_by_player"), dict):
        prep["preferred_starting_player_ids_by_player"].pop(player_id, None)
    prep.setdefault("updated_at_by_player", {})[player_id] = _iso(current_time)
    prep["updated_at"] = _iso(current_time)
    connection.execute(
        """
        UPDATE pvp_challenges
        SET prep_json = ?,
            updated_at = ?
        WHERE challenge_id = ?
        """,
        (_json_dumps(prep), _iso(current_time), request.challenge_id),
    )
    log_event(
        connection,
        "gwent_player_prepared",
        {
            "challenge_id": request.challenge_id,
            "player_id": player_id,
            "ready_players": ready_players,
            "missing_players": [candidate for candidate in players if candidate not in ready_players],
            "mulligan_count": len(mulligans),
            "deck_id": deck_id or None,
            "preferred_starting_player_id": preferred_starting_player_id or None,
        },
        source=request.source,
        created_at=current_time,
    )

    refreshed = _fetch_challenge_required(connection, request.challenge_id)
    if all(player in ready_players for player in players):
        started = start_pvp_challenge(
            connection,
            ChallengeStartInput(
                challenge_id=request.challenge_id,
                mulligans_by_player=prep.get("mulligans_by_player") or {},
                deck_ids_by_player=prep.get("deck_ids_by_player") or {},
                preferred_starting_player_id=_preferred_starting_player_from_prep(prep, players),
                source=request.source,
            ),
            now=current_time,
        )
        return {
            **started,
            "prep": _challenge_prep(_fetch_challenge_required(connection, request.challenge_id)),
            "started": started.get("match") is not None,
            "duplicate": duplicate,
        }

    return {
        "challenge": _challenge_payload(connection, refreshed),
        "match": None,
        "prep": _challenge_prep(refreshed),
        "started": False,
        "duplicate": duplicate,
    }


def start_gwent_bot_match(
    connection: sqlite3.Connection,
    request: GwentBotMatchInput,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    player_id = str(request.player_id).strip()
    if not player_id:
        raise PvpError("player_id is required for bot Gwent match.")
    _require_personal_pvp_player(connection, player_id)
    if _active_challenge_exists(connection, player_id):
        raise PvpError(f"Player already has an active PvP challenge: {player_id}")

    challenge_id = f"gwent_bot_challenge_{uuid4().hex}"
    match_id = f"gwent_bot_match_{uuid4().hex}"
    rules = _gwent_rules(connection)
    player_state = _build_player_deck_state(
        connection,
        player_id,
        rules,
        request.mulligans or [],
        deck_id=request.deck_id,
        challenge_id=challenge_id,
    )
    bot_state = _build_bot_deck_state(connection, player_id, rules, challenge_id=challenge_id)
    act_id = _current_act_id(connection)
    table_id = ""
    deck_state = {
        player_id: player_state,
        GWENT_BOT_PLAYER_ID: bot_state,
        "rules": rules,
        "cards_burn_after_round": False,
        "bot": {
            "player_id": GWENT_BOT_PLAYER_ID,
            "display_name": GWENT_BOT_DISPLAY_NAME,
            "difficulty": "training",
            "human_player_id": player_id,
        },
    }
    deck_state["active_round"] = _new_active_round(
        match_id=match_id,
        players=[player_id, GWENT_BOT_PLAYER_ID],
        deck_state=deck_state,
        round_number=1,
        starting_player_id=player_id,
        now=current_time,
    )
    round_losses = {player_id: 0, GWENT_BOT_PLAYER_ID: 0}
    connection.execute(
        """
        INSERT INTO pvp_challenges (
            challenge_id, challenger_id, target_id, act_id, status, mandatory,
            stake_json, table_id, assigned_zone, start_window_deadline,
            master_approval, created_at, updated_at, started_at
        )
        VALUES (?, ?, ?, ?, 'started', 0, ?, NULL, 'ios_training_table', NULL, 1, ?, ?, ?)
        """,
        (
            challenge_id,
            player_id,
            GWENT_BOT_PLAYER_ID,
            act_id,
            _json_dumps({"asset_type": "practice", "asset_id": "none", "quantity": 0}),
            _iso(current_time),
            _iso(current_time),
            _iso(current_time),
        ),
    )
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
            challenge_id,
            player_id,
            GWENT_BOT_PLAYER_ID,
            act_id,
            table_id,
            _json_dumps(deck_state),
            _json_dumps(round_losses),
            _iso(current_time),
            _iso(current_time),
            _json_dumps(
                {
                    "profile": "ios_training_bot_gwent",
                    "challenge_id": challenge_id,
                    "act_id": act_id,
                    "started_at": _iso(current_time),
                    "bot_player_id": GWENT_BOT_PLAYER_ID,
                    "stake_transfer_status": "practice_no_stake",
                }
            ),
        ),
    )
    log_event(
        connection,
        "gwent_bot_match_started",
        {
            "match_id": match_id,
            "challenge_id": challenge_id,
            "player_id": player_id,
            "bot_player_id": GWENT_BOT_PLAYER_ID,
            "started_at": _iso(current_time),
        },
        source=request.source,
        created_at=current_time,
    )
    match = _fetch_match_required(connection, match_id)
    current_round = _active_round_player_payload(connection, match, deck_state, player_id)
    return {
        "challenge": _challenge_payload(connection, _fetch_challenge_required(connection, challenge_id)),
        "match": _player_scoped_match_payload(_match_payload(connection, match), player_id, current_round),
        "current_round": current_round,
        "bot": deck_state["bot"],
    }


def save_gwent_runtime_deck(
    connection: sqlite3.Connection,
    request: GwentDeckSaveInput,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    player_id = str(request.player_id).strip()
    if not player_id:
        raise PvpError("player_id is required for Gwent deck save.")
    _require_personal_pvp_player(connection, player_id)
    cards = _cards_by_id(connection)
    leader_id = str(request.leader_card_id).strip()
    card_ids = [str(card_id).strip() for card_id in request.card_ids if str(card_id).strip()]
    leader = cards.get(leader_id)
    if leader is None or str(leader["type"]) != "leader":
        raise PvpError(f"Gwent deck leader is invalid for player: {player_id}")
    available = _player_available_gwent_card_ids(connection, player_id)
    missing_owned = [card_id for card_id in [leader_id, *card_ids] if card_id not in available]
    if missing_owned:
        raise PvpError(f"Gwent deck uses cards not owned by {player_id}: {', '.join(missing_owned)}")
    rules = _gwent_rules(connection)
    _validate_deck_cards(player_id, card_ids, cards, rules, leader=leader)
    deck_id = str(request.deck_id or "").strip() or f"runtime_deck_{player_id}_{uuid4().hex}"
    connection.execute(
        """
        INSERT INTO gwent_deck_runtime (
            deck_id, player_id, leader_card_id, card_ids, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, 'active', ?, ?)
        ON CONFLICT(deck_id) DO UPDATE SET
            leader_card_id = excluded.leader_card_id,
            card_ids = excluded.card_ids,
            status = 'active',
            updated_at = excluded.updated_at
        """,
        (
            deck_id,
            player_id,
            leader_id,
            ";".join(card_ids),
            _iso(current_time),
            _iso(current_time),
        ),
    )
    payload = {
        "deck_id": deck_id,
        "player_id": player_id,
        "leader_card_id": leader_id,
        "card_ids": card_ids,
        "status": "active",
        "updated_at": _iso(current_time),
    }
    log_event(connection, "gwent_runtime_deck_saved", payload, source=request.source, created_at=current_time)
    return {"deck": payload}


def record_gwent_action(
    connection: sqlite3.Connection,
    request: GwentActionInput,
    *,
    advance_bot: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_pvp_runtime_state(connection)
    current_time = now or datetime.now(UTC)
    match = _fetch_match_required(connection, request.match_id)
    if str(match["status"]) in {"finished", "needs_master_review", "awaiting_finish"}:
        return {
            "match": _match_payload(connection, match),
            "current_round": None,
            "duplicate": False,
        }
    if str(match["status"]) != "active":
        raise PvpError(f"Gwent match is not active: {request.match_id}")

    players = [str(match["challenger_id"]), str(match["target_id"])]
    player_id = str(request.player_id).strip()
    if player_id not in players:
        raise PvpError(f"Gwent action references a non-participant: {player_id}")

    deck_state = _json_loads(str(match["deck_state_json"]), {})
    deck_state = _normalize_match_deck_state(deck_state, players)
    action_id = str(request.action_id or "").strip()
    if action_id:
        action_ids = [str(value) for value in deck_state.get("action_ids") or []]
        if action_id in action_ids:
            return {
                "match": _player_scoped_match_payload(
                    _match_payload(connection, match),
                    player_id,
                    _active_round_player_payload(connection, match, deck_state, player_id),
                ),
                "current_round": _active_round_player_payload(connection, match, deck_state, player_id),
                "duplicate": True,
            }
        deck_state["action_ids"] = action_ids

    active_round = _ensure_active_round(match, deck_state, players, request.round_number, current_time)
    round_number = int(active_round["round_number"])
    if request.round_number is not None and int(request.round_number) != round_number:
        raise PvpError(f"Gwent action round mismatch: active round is {round_number}.")
    if bool(active_round.get("passed", {}).get(player_id)):
        raise PvpError(f"Gwent player has already passed this round: {player_id}")
    if str(active_round.get("turn_player_id") or "") != player_id:
        raise PvpError(f"Gwent action is out of turn for player: {player_id}")

    action = str(request.action or "").strip().lower()
    if action == "pass":
        active_round.setdefault("passed", {})[player_id] = True
        active_round.setdefault("action_log", []).append(
            {
                "action": "pass",
                "player_id": player_id,
                "action_id": action_id,
                "created_at": _iso(current_time),
            }
        )
    elif action in {"play_card", "play", "use_leader"}:
        play = _action_to_play(connection, request, player_id, deck_state, active_round)
        active_round.setdefault("plays", []).append(play)
        active_round.setdefault("action_log", []).append(
            {
                "action": "use_leader" if action == "use_leader" else "play_card",
                "player_id": player_id,
                "card_id": play["card_id"],
                "row": play.get("row"),
                "target_card_id": play.get("target_card_id"),
                "discard_card_ids": play.get("discard_card_ids"),
                "revive_card_id": play.get("revive_card_id"),
                "action_id": action_id,
                "created_at": _iso(current_time),
            }
        )
    else:
        raise PvpError(f"Unsupported Gwent action: {request.action}")

    preview = _preview_active_round(connection, match, deck_state)
    _auto_pass_empty_hands(active_round, players, preview["deck_state"], current_time)
    if _active_round_finished(active_round, players):
        base_deck_state = deepcopy(active_round["base_deck_state"])
        base_deck_state["action_ids"] = deck_state.get("action_ids", [])
        if "bot" in deck_state:
            base_deck_state["bot"] = deck_state["bot"]
        result = _store_resolved_gwent_round(
            connection,
            match,
            round_number=round_number,
            round_state=_round_state_for_active_round(active_round),
            deck_state=base_deck_state,
            source=request.source,
            now=current_time,
        )
        if action_id:
            stored = _fetch_match_required(connection, request.match_id)
            stored_deck_state = _json_loads(str(stored["deck_state_json"]), {})
            stored_action_ids = [str(value) for value in stored_deck_state.get("action_ids") or []]
            if action_id not in stored_action_ids:
                stored_action_ids.append(action_id)
                stored_deck_state["action_ids"] = stored_action_ids
                connection.execute(
                    "UPDATE gwent_runtime_matches SET deck_state_json = ? WHERE match_id = ?",
                    (_json_dumps(stored_deck_state), request.match_id),
                )
                result["match"] = _match_payload(connection, _fetch_match_required(connection, request.match_id))
        if advance_bot:
            _advance_gwent_bot_turns(connection, request.match_id, player_id, now=current_time)
            refreshed = _fetch_match_required(connection, request.match_id)
            refreshed_deck = _json_loads(str(refreshed["deck_state_json"]), {})
            current_round = _current_round_payload(connection, refreshed, player_id)
            return {
                "match": _player_scoped_match_payload(_match_payload(connection, refreshed), player_id, current_round),
                "round": result["round"],
                "current_round": current_round,
                "duplicate": result["duplicate"],
                "action": action,
                "action_id": action_id,
            }
        return {**result, "current_round": result["round"], "action": action, "action_id": action_id}

    if action_id:
        deck_state.setdefault("action_ids", []).append(action_id)
    active_round["turn_player_id"] = _next_turn_player(players, player_id, active_round.get("passed") or {})
    active_round["updated_at"] = _iso(current_time)
    active_round["board"] = preview["round_state"]["board"]
    active_round["weather_rows"] = preview["round_state"]["weather_rows"]
    active_round["horn_rows"] = preview["round_state"]["horn_rows"]
    active_round["row_scores"] = preview["row_scores"]
    active_round["total_scores"] = preview["round_state"]["total_scores"]
    active_round["effects_applied"] = preview["effects_applied"]
    active_round["hands_after_round"] = preview["round_state"]["hands_after_round"]
    active_round["graveyards_after_round"] = preview["round_state"]["graveyards_after_round"]
    deck_state["active_round"] = active_round
    connection.execute(
        """
        UPDATE gwent_runtime_matches
        SET deck_state_json = ?
        WHERE match_id = ?
        """,
        (_json_dumps(deck_state), request.match_id),
    )
    stored_match = _fetch_match_required(connection, request.match_id)
    if advance_bot:
        _advance_gwent_bot_turns(connection, request.match_id, player_id, now=current_time)
        stored_match = _fetch_match_required(connection, request.match_id)
        deck_state = _json_loads(str(stored_match["deck_state_json"]), {})
    current_round = _active_round_player_payload(connection, stored_match, deck_state, player_id)
    log_event(
        connection,
        "gwent_action_recorded",
        {
            "match_id": request.match_id,
            "round_number": round_number,
            "player_id": player_id,
            "action": action,
            "card_id": request.card_id,
            "row": request.row,
            "target_card_id": request.target_card_id,
            "revive_card_id": request.revive_card_id,
            "action_id": action_id,
            "next_turn_player_id": active_round["turn_player_id"],
        },
        source=request.source,
        created_at=current_time,
    )
    match_payload = _player_scoped_match_payload(_match_payload(connection, stored_match), player_id, current_round)
    return {
        "match": match_payload,
        "current_round": current_round,
        "round": current_round,
        "duplicate": False,
        "action": action,
        "action_id": action_id,
    }


def _advance_gwent_bot_turns(
    connection: sqlite3.Connection,
    match_id: str,
    human_player_id: str,
    *,
    now: datetime,
) -> None:
    for _ in range(40):
        match = _fetch_match_required(connection, match_id)
        if str(match["status"]) == "awaiting_finish":
            _auto_finish_bot_match(connection, match, now=now)
            return
        if str(match["status"]) != "active":
            return
        deck_state = _json_loads(str(match["deck_state_json"]), {})
        if not isinstance(deck_state, dict) or not isinstance(deck_state.get("bot"), dict):
            return
        bot_id = str(deck_state["bot"].get("player_id") or GWENT_BOT_PLAYER_ID)
        players = [str(match["challenger_id"]), str(match["target_id"])]
        if bot_id not in players:
            return
        current_round = _active_round_player_payload(connection, match, deck_state, bot_id)
        if not isinstance(current_round, dict) or str(current_round.get("turn_player_id") or "") != bot_id:
            return
        bot_action = _choose_gwent_bot_action(connection, match, deck_state, current_round, bot_id, human_player_id)
        try:
            record_gwent_action(
                connection,
                bot_action,
                advance_bot=False,
                now=now,
            )
        except PvpError as exc:
            recoverable = (
                "not in current hand" in str(exc)
                or "leader was already used" in str(exc)
            )
            if bot_action.action == "pass" or not recoverable:
                raise
            record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id=bot_id,
                    action="pass",
                    round_number=int(current_round.get("round_number") or 1),
                    action_id=f"bot-pass-fallback-{uuid4().hex}",
                    source="gwent_bot",
                ),
                advance_bot=False,
                now=now,
            )


def _auto_finish_bot_match(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    *,
    now: datetime,
) -> None:
    deck_state = _json_loads(str(match["deck_state_json"]), {})
    if not isinstance(deck_state, dict) or not isinstance(deck_state.get("bot"), dict):
        return
    winner_id = str(match["winner_id"] or "")
    if not winner_id:
        return
    finish_gwent_match(
        connection,
        str(match["match_id"]),
        winner_id=winner_id,
        outcome="practice_bot",
        source="gwent_bot",
        now=now,
    )


def _choose_gwent_bot_action(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    deck_state: dict[str, Any],
    current_round: dict[str, Any],
    bot_id: str,
    human_player_id: str,
) -> GwentActionInput:
    bot_state = deck_state.get(bot_id) if isinstance(deck_state, dict) else {}
    if not isinstance(bot_state, dict):
        bot_state = {}
    passed = current_round.get("passed") if isinstance(current_round.get("passed"), dict) else {}
    total_scores = current_round.get("total_scores") if isinstance(current_round.get("total_scores"), dict) else {}
    bot_score = _to_int(total_scores.get(bot_id) if isinstance(total_scores, dict) else 0)
    human_score = _to_int(total_scores.get(human_player_id) if isinstance(total_scores, dict) else 0)
    bot_hand = list(current_round.get("player_hand") or bot_state.get("hand") or [])
    should_pass = (
        not bot_hand
        or (bool(passed.get(human_player_id)) and bot_score > human_score)
        or (len(bot_hand) <= 2 and bot_score >= human_score)
    )
    if should_pass:
        return GwentActionInput(
            match_id=str(match["match_id"]),
            player_id=bot_id,
            action="pass",
            round_number=int(current_round.get("round_number") or 1),
            action_id=f"bot-pass-{uuid4().hex}",
            source="gwent_bot",
        )

    playable = _player_playable_card_actions(connection, bot_state, current_round, bot_id)
    cards = _cards_by_id(connection)
    candidates = []
    for action in playable:
        card_id = str(action.get("card_id") or "")
        if not card_id:
            continue
        if bool(action.get("requires_target")) and not action.get("targets"):
            continue
        card = cards.get(card_id)
        card_type = str(card["type"]) if card is not None else str(action.get("type") or "")
        strength = _to_int(card["strength"]) if card is not None else 0
        effect = str(action.get("effect") or (card["effect"] if card is not None else "none"))
        priority = 0 if card_type == "unit" else 1
        if effect in {"weather_melee", "weather_ranged", "weather_siege", "biting_frost", "impenetrable_fog", "torrential_rain"}:
            priority = 3
        candidates.append((priority, strength, action))
    if candidates:
        _, _, selected = sorted(candidates, key=lambda item: (item[0], item[1]))[0]
        allowed_rows = [str(row) for row in selected.get("allowed_rows") or []]
        target = None
        if selected.get("targets"):
            raw_target = selected["targets"][0]
            if isinstance(raw_target, dict):
                target = str(raw_target.get("card_id") or "") or None
        return GwentActionInput(
            match_id=str(match["match_id"]),
            player_id=bot_id,
            action="play_card",
            round_number=int(current_round.get("round_number") or 1),
            card_id=str(selected["card_id"]),
            row=allowed_rows[0] if allowed_rows else None,
            target_card_id=target if str(selected.get("target_kind") or "") == "own_non_hero_unit" else None,
            revive_card_id=target if str(selected.get("target_kind") or "") == "graveyard_unit" else None,
            action_id=f"bot-card-{uuid4().hex}",
            source="gwent_bot",
        )

    if not bool(bot_state.get("leader_used")) and bot_state.get("leader_card_id"):
        return GwentActionInput(
            match_id=str(match["match_id"]),
            player_id=bot_id,
            action="use_leader",
            round_number=int(current_round.get("round_number") or 1),
            card_id=str(bot_state["leader_card_id"]),
            row="melee",
            action_id=f"bot-leader-{uuid4().hex}",
            source="gwent_bot",
        )
    return GwentActionInput(
        match_id=str(match["match_id"]),
        player_id=bot_id,
        action="pass",
        round_number=int(current_round.get("round_number") or 1),
        action_id=f"bot-pass-{uuid4().hex}",
        source="gwent_bot",
    )


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
    source = str(source or "pvp_api").strip() or "pvp_api"
    if source.endswith("_fallback"):
        raise PvpError("Gwent round fallback sources are removed; use turn actions or master round submission.")
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
    if isinstance(deck_state, dict):
        deck_state.pop("active_round", None)
    incoming_submissions = _round_submissions_from_state(round_state, players, actor_id=actor_id)
    if not incoming_submissions:
        raise PvpError("Gwent round submission requires a play or pass flag.")
    validation_round_state = _round_state_from_submissions(incoming_submissions, players)
    _validate_round_submission_state(connection, match, validation_round_state, deck_state)

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
    players = [challenger_id, target_id]
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

    if match_status == "active":
        next_round_number = round_number + 1
        next_starter = winner_id if winner_id in {challenger_id, target_id} else players[next_round_number % len(players)]
        if next_round_number == 3:
            _apply_skellige_round_three_restore(
                resolved["deck_state"],
                players,
                _cards_by_id(connection),
                resolved["effects_applied"],
            )
        resolved["deck_state"]["active_round"] = _new_active_round(
            match_id=match_id,
            players=players,
            deck_state=resolved["deck_state"],
            round_number=next_round_number,
            starting_player_id=str(next_starter),
            now=now,
        )
    else:
        resolved["deck_state"].pop("active_round", None)

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

    resolved_round_state = _round_state_from_submissions(submissions, players, order=order)
    return _store_resolved_gwent_round(
        connection,
        match,
        round_number=int(existing["round_number"]),
        round_state=resolved_round_state,
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
    *,
    deck_id: str | None = None,
    challenge_id: str = "standalone",
    shuffle_seed: str | None = None,
) -> dict[str, Any]:
    deck = _deck_for_player(connection, player_id, deck_id=deck_id)
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
    _validate_deck_cards(player_id, card_ids, cards, rules, leader=leader)
    effective_shuffle_seed = shuffle_seed or _gwent_shuffle_seed(
        challenge_id,
        player_id,
        str(deck["deck_id"]),
    )
    shuffled_card_ids = _shuffle_card_ids(card_ids, effective_shuffle_seed)
    _validate_mulligans_for_hand(player_id, shuffled_card_ids, rules, mulligans)
    hand = shuffled_card_ids[: int(rules["hand_size"])]
    draw_pile = shuffled_card_ids[int(rules["hand_size"]) :]
    for card_id in mulligans:
        if card_id not in hand:
            raise PvpError(f"Mulligan card is not in opening hand: {card_id}")
        if not draw_pile:
            break
        hand.remove(card_id)
        hand.append(draw_pile.pop(0))
        draw_pile.append(card_id)
    state = {
        "deck_id": deck["deck_id"],
        "leader_card_id": deck["leader_card_id"],
        "faction": str(leader["faction"] or "neutral"),
        "shuffle_seed": effective_shuffle_seed,
        "shuffle_log": {
            "original_card_ids": card_ids,
            "shuffled_card_ids": shuffled_card_ids,
            "opening_hand": list(shuffled_card_ids[: int(rules["hand_size"])]),
        },
        "draw_pile": draw_pile,
        "hand": hand,
        "mulligans": mulligans,
        "rows": {row: [] for row in GWENT_ROWS},
        "passed": False,
        "graveyard": [],
        "cards_burned": False,
        "leader_used": False,
        "leader_disabled": False,
        "private_reveals": [],
        "start_effects": [],
    }
    _apply_starting_leader_effect(state, leader)
    return state


def _validate_player_mulligans(
    connection: sqlite3.Connection,
    player_id: str,
    rules: dict[str, int | str],
    mulligans: list[str],
    *,
    deck_id: str | None = None,
    challenge_id: str = "standalone",
) -> None:
    deck = _deck_for_player(connection, player_id, deck_id=deck_id)
    cards = _cards_by_id(connection)
    leader = cards.get(str(deck["leader_card_id"]))
    if leader is None or str(leader["type"]) != "leader":
        raise PvpError(f"Gwent deck leader is invalid for player: {player_id}")
    card_ids = _split_ids(str(deck["card_ids"]))
    _validate_deck_cards(player_id, card_ids, cards, rules, leader=leader)
    shuffled_card_ids = _shuffle_card_ids(
        card_ids,
        _gwent_shuffle_seed(challenge_id, player_id, str(deck["deck_id"])),
    )
    _validate_mulligans_for_hand(player_id, shuffled_card_ids, rules, mulligans)


def _validate_mulligans_for_hand(
    player_id: str,
    card_ids: list[str],
    rules: dict[str, int | str],
    mulligans: list[str],
) -> None:
    if len(mulligans) > int(rules["mulligans"]):
        raise PvpError("Gwent mulligan count exceeds the configured limit.")
    hand = card_ids[: int(rules["hand_size"])]
    for card_id in mulligans:
        if card_id not in hand:
            raise PvpError(f"Mulligan card is not in opening hand for {player_id}: {card_id}")


def _build_bot_deck_state(
    connection: sqlite3.Connection,
    source_player_id: str,
    rules: dict[str, int | str],
    *,
    challenge_id: str = "bot",
) -> dict[str, Any]:
    deck = _deck_for_player(connection, source_player_id)
    cards = _cards_by_id(connection)
    leader = cards.get(str(deck["leader_card_id"]))
    if leader is None or str(leader["type"]) != "leader":
        raise PvpError(f"Gwent deck leader is invalid for bot source player: {source_player_id}")
    _assert_stage1_gwent_effect_supported(
        str(leader["card_id"]),
        str(leader["type"]),
        str(leader["effect"] or "none"),
    )
    card_ids = list(reversed(_split_ids(str(deck["card_ids"]))))
    _validate_deck_cards(GWENT_BOT_PLAYER_ID, card_ids, cards, rules, leader=leader)
    shuffle_seed = _gwent_shuffle_seed(challenge_id, GWENT_BOT_PLAYER_ID, str(deck["deck_id"]))
    shuffled_card_ids = _shuffle_card_ids(card_ids, shuffle_seed)
    hand = shuffled_card_ids[: int(rules["hand_size"])]
    draw_pile = shuffled_card_ids[int(rules["hand_size"]) :]
    state = {
        "deck_id": f"bot_deck_{source_player_id}",
        "leader_card_id": deck["leader_card_id"],
        "faction": str(leader["faction"] or "neutral"),
        "shuffle_seed": shuffle_seed,
        "shuffle_log": {
            "original_card_ids": card_ids,
            "shuffled_card_ids": shuffled_card_ids,
            "opening_hand": list(shuffled_card_ids[: int(rules["hand_size"])]),
        },
        "draw_pile": draw_pile,
        "hand": hand,
        "mulligans": [],
        "rows": {row: [] for row in GWENT_ROWS},
        "passed": False,
        "graveyard": [],
        "cards_burned": False,
        "leader_used": False,
        "leader_disabled": False,
        "private_reveals": [],
        "start_effects": [],
        "bot": True,
    }
    _apply_starting_leader_effect(state, leader)
    return state


def _apply_starting_leader_effect(player_state: dict[str, Any], leader: sqlite3.Row) -> None:
    if not _card_has_effect(leader, "leader_francesca_draw"):
        return
    drawn = _draw_cards(player_state, 1)
    player_state["leader_used"] = True
    player_state.setdefault("start_effects", []).append(
        {
            "card_id": str(leader["card_id"]),
            "effect": "leader_francesca_draw",
            "scope": "leader",
            "drawn_card_ids": drawn,
        }
    )


def _new_active_round(
    *,
    match_id: str,
    players: list[str],
    deck_state: dict[str, Any],
    round_number: int,
    starting_player_id: str,
    now: datetime,
) -> dict[str, Any]:
    base_deck_state = deepcopy(deck_state)
    base_deck_state.pop("active_round", None)
    base_deck_state.pop("action_ids", None)
    return {
        "match_id": match_id,
        "round_number": round_number,
        "phase": "active_turn",
        "status": "ready_for_submission",
        "players": list(players),
        "turn_player_id": starting_player_id,
        "starting_player_id": starting_player_id,
        "plays": [],
        "passed": {player_id: False for player_id in players},
        "board": {player_id: {row: [] for row in GWENT_ROWS} for player_id in players},
        "weather_rows": [],
        "horn_rows": {player_id: [] for player_id in players},
        "row_scores": {player_id: {row: 0 for row in GWENT_ROWS} for player_id in players},
        "total_scores": {player_id: 0 for player_id in players},
        "effects_applied": [],
        "hands_after_round": {player_id: list(deck_state[player_id].get("hand") or []) for player_id in players},
        "graveyards_after_round": {player_id: list(deck_state[player_id].get("graveyard") or []) for player_id in players},
        "action_log": [],
        "base_deck_state": base_deck_state,
        "created_at": _iso(now),
        "updated_at": _iso(now),
    }


def _validated_preferred_starting_player_id(
    connection: sqlite3.Connection,
    *,
    player_id: str,
    players: list[str],
    deck_id: str | None,
    requested_player_id: str | None,
    previous_player_id: str,
    preserve_previous: bool,
) -> str:
    requested = str(requested_player_id or "").strip()
    previous = str(previous_player_id or "").strip()
    if not requested and preserve_previous:
        requested = previous
    if not requested:
        return ""
    if requested not in players:
        raise PvpError(f"Gwent preferred starting player is not a participant: {requested}")

    deck = _deck_for_player(connection, player_id, deck_id=deck_id)
    cards = _cards_by_id(connection)
    faction = _deck_faction_from_deck(deck, cards)
    if faction != "scoiatael":
        raise PvpError("Gwent first-turn choice requires a Scoia'tael deck.")
    return requested


def _preferred_starting_player_from_prep(prep: dict[str, Any], players: list[str]) -> str | None:
    choices = prep.get("preferred_starting_player_ids_by_player")
    if not isinstance(choices, dict):
        return None
    for chooser_id in players:
        preferred = str(choices.get(chooser_id) or "").strip()
        if preferred in players:
            return preferred
    return None


def _resolve_first_turn_player(
    *,
    players: list[str],
    deck_state: dict[str, Any],
    preferred_starting_player_id: str | None,
) -> tuple[str, dict[str, Any] | None]:
    preferred = str(preferred_starting_player_id or "").strip()
    scoiatael_players = [
        player_id
        for player_id in players
        if _deck_faction(deck_state.get(player_id, {}), {}) == "scoiatael"
    ]
    if not scoiatael_players:
        if preferred:
            raise PvpError("Gwent first-turn choice requires a Scoia'tael deck.")
        return _coin_toss_first_turn(players, deck_state, effect="coin_toss_first_turn")
    if len(scoiatael_players) > 1:
        if preferred:
            raise PvpError("Gwent Scoia'tael mirror first turn is resolved by coin toss.")
        starting_player_id, payload = _coin_toss_first_turn(
            players,
            deck_state,
            effect="faction_scoiatael_mirror_coin_toss",
        )
        payload["scope"] = "faction"
        payload["faction"] = "scoiatael"
        payload["scoiatael_player_ids"] = scoiatael_players
        return starting_player_id, payload
    chooser_id = scoiatael_players[0]
    starting_player_id = preferred if preferred in players else chooser_id
    return starting_player_id, {
        "effect": "faction_scoiatael_choose_first",
        "scope": "faction",
        "player_id": chooser_id,
        "faction": "scoiatael",
        "starting_player_id": starting_player_id,
    }


def _coin_toss_first_turn(
    players: list[str],
    deck_state: dict[str, Any],
    *,
    effect: str,
) -> tuple[str, dict[str, Any]]:
    seed = ":".join(
        [
            effect,
            *players,
            *[
                str(deck_state.get(player_id, {}).get("shuffle_seed") or "")
                for player_id in players
            ],
        ]
    )
    starting_player_id = random.Random(seed).choice(players)
    return starting_player_id, {
        "effect": effect,
        "scope": "match",
        "players": players,
        "starting_player_id": starting_player_id,
        "coin_toss_seed": seed,
    }


def _ensure_active_round(
    match: sqlite3.Row,
    deck_state: dict[str, Any],
    players: list[str],
    requested_round_number: int | None,
    now: datetime,
) -> dict[str, Any]:
    active_round = deck_state.get("active_round")
    if isinstance(active_round, dict):
        active_number = int(active_round.get("round_number") or 1)
        if requested_round_number is not None and int(requested_round_number) != active_number:
            raise PvpError(f"Gwent action round mismatch: active round is {active_number}.")
        return active_round
    next_round = int(requested_round_number or 1)
    starting_player_id = players[(next_round - 1) % len(players)]
    active_round = _new_active_round(
        match_id=str(match["match_id"]),
        players=players,
        deck_state=deck_state,
        round_number=next_round,
        starting_player_id=starting_player_id,
        now=now,
    )
    deck_state["active_round"] = active_round
    return active_round


def _action_to_play(
    connection: sqlite3.Connection,
    request: GwentActionInput,
    player_id: str,
    deck_state: dict[str, Any],
    active_round: dict[str, Any],
) -> dict[str, Any]:
    player_state = deck_state[player_id]
    cards = _cards_by_id(connection)
    action = str(request.action or "").strip().lower()
    card_id = str(request.card_id or "").strip()
    if action == "use_leader":
        card_id = card_id or str(player_state.get("leader_card_id") or "")
    if not card_id:
        raise PvpError("Gwent play action requires card_id.")
    card = cards.get(card_id)
    if card is None:
        raise PvpError(f"Round play references an unknown Gwent card: {card_id}")
    card_type = str(card["type"])
    if action == "use_leader" and card_type != "leader":
        raise PvpError(f"Gwent use_leader requires a leader card: {card_id}")
    if action != "use_leader" and card_type == "leader":
        action = "use_leader"
    if action == "use_leader":
        if bool(player_state.get("leader_disabled")):
            raise PvpError(f"Gwent leader is disabled for player: {player_id}")
        if bool(player_state.get("leader_used")):
            raise PvpError(f"Gwent leader was already used by player: {player_id}")

    allowed_rows = _allowed_rows_for_card(card)
    requested_row = str(request.row or "").strip()
    row = requested_row
    if allowed_rows:
        row = row or allowed_rows[0]
        if row not in allowed_rows:
            raise PvpError(f"Gwent card cannot be played on row {row}: {card_id}")
    play: dict[str, Any] = {"player_id": player_id, "card_id": card_id}
    if row:
        play["row"] = row

    effects = _card_effects(card)
    if card_type == "special" and "decoy" in effects:
        target_card_id = str(request.target_card_id or "").strip()
        if not target_card_id:
            raise PvpError("Gwent decoy requires target_card_id.")
        if target_card_id not in {str(target.get("card_id")) for target in _decoy_targets(active_round, player_id)}:
            raise PvpError(f"Gwent decoy target is not a non-hero unit on board: {target_card_id}")
        play["target_card_id"] = target_card_id
    if card_type == "unit" and "medic" in effects:
        revive_card_id = str(request.revive_card_id or "").strip()
        if revive_card_id:
            play["revive_card_id"] = revive_card_id
        revive_row = str(request.revive_row or "").strip()
        if revive_row:
            play["revive_row"] = revive_row
    if card_type == "leader":
        target_card_id = str(request.target_card_id or "").strip()
        if target_card_id:
            play["target_card_id"] = target_card_id
        discard_card_ids = [
            str(discard_card_id).strip()
            for discard_card_id in (request.discard_card_ids or [])
            if str(discard_card_id).strip()
        ]
        if discard_card_ids:
            play["discard_card_ids"] = discard_card_ids
    return play


def _preview_active_round(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    deck_state: dict[str, Any],
) -> dict[str, Any]:
    active_round = deck_state.get("active_round")
    if not isinstance(active_round, dict):
        raise PvpError("Gwent match has no active round.")
    base_deck_state = active_round.get("base_deck_state")
    if not isinstance(base_deck_state, dict):
        raise PvpError("Gwent active round has invalid base deck state.")
    return _resolve_round_state(
        connection,
        match,
        _round_state_for_active_round(active_round),
        deepcopy(base_deck_state),
    )


def _round_state_for_active_round(active_round: dict[str, Any]) -> dict[str, Any]:
    return {
        "plays": [dict(play) for play in active_round.get("plays") or []],
        "passed": {
            str(player_id): bool(passed)
            for player_id, passed in (active_round.get("passed") or {}).items()
        },
    }


def _active_round_finished(active_round: dict[str, Any], players: list[str]) -> bool:
    passed = active_round.get("passed") or {}
    return all(bool(passed.get(player_id)) for player_id in players)


def _auto_pass_empty_hands(
    active_round: dict[str, Any],
    players: list[str],
    deck_state: dict[str, Any],
    now: datetime,
) -> None:
    passed = active_round.setdefault("passed", {})
    action_log = active_round.setdefault("action_log", [])
    for player_id in players:
        if bool(passed.get(player_id)):
            continue
        player_state = deck_state.get(player_id, {})
        hand = player_state.get("hand") if isinstance(player_state, dict) else None
        if hand:
            continue
        passed[player_id] = True
        action_log.append(
            {
                "action": "auto_pass_no_cards",
                "player_id": player_id,
                "created_at": _iso(now),
            }
        )


def _next_turn_player(players: list[str], current_player_id: str, passed: dict[str, Any]) -> str:
    if not players:
        return current_player_id
    start_index = players.index(current_player_id) if current_player_id in players else 0
    for offset in range(1, len(players) + 1):
        candidate = players[(start_index + offset) % len(players)]
        if not bool(passed.get(candidate)):
            return candidate
    return current_player_id


def _active_round_player_payload(
    connection: sqlite3.Connection,
    match: sqlite3.Row,
    deck_state: dict[str, Any],
    player_id: str,
) -> dict[str, Any] | None:
    active_round = deck_state.get("active_round") if isinstance(deck_state, dict) else None
    if not isinstance(active_round, dict):
        return None
    preview = _preview_active_round(connection, match, deck_state)
    players = [str(match["challenger_id"]), str(match["target_id"])]
    passed = {
        player: bool((active_round.get("passed") or {}).get(player))
        for player in players
    }
    player_after = preview["deck_state"].get(player_id, {}) if isinstance(preview.get("deck_state"), dict) else {}
    row_scores = preview.get("row_scores") or {}
    total_scores = preview["round_state"].get("total_scores") if isinstance(preview.get("round_state"), dict) else {}
    ready_players = [player for player in players if passed.get(player)]
    missing_players = [player for player in players if not passed.get(player)]
    return {
        "match_id": match["match_id"],
        "round_number": int(active_round.get("round_number") or 1),
        "status": "ready_for_submission",
        "phase": "active_turn",
        "turn_player_id": active_round.get("turn_player_id"),
        "is_player_turn": str(active_round.get("turn_player_id") or "") == player_id,
        "starting_player_id": active_round.get("starting_player_id"),
        "players": players,
        "ready_players": ready_players,
        "missing_players": missing_players,
        "player_submitted": bool(passed.get(player_id)),
        "passed": passed,
        "plays": _public_plays(active_round.get("plays") or []),
        "board": preview["round_state"]["board"],
        "weather_rows": preview["round_state"]["weather_rows"],
        "horn_rows": preview["round_state"]["horn_rows"],
        "row_scores": row_scores,
        "total_scores": total_scores,
        "effects_applied": preview["effects_applied"],
        "player_hand": list(player_after.get("hand") or []),
        "player_graveyard": list(player_after.get("graveyard") or []),
        "created_at": active_round.get("created_at"),
        "updated_at": active_round.get("updated_at"),
    }


def _public_plays(plays: list[Any]) -> list[dict[str, Any]]:
    public = []
    for play in plays:
        if not isinstance(play, dict):
            continue
        public.append(
            {
                key: value
                for key, value in play.items()
                if key in {"player_id", "card_id", "row", "target_card_id", "discard_card_ids", "revive_card_id", "revive_row"}
            }
        )
    return public


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
    _validate_deck_cards(player_id, _split_ids(str(deck["card_ids"])), cards, rules, leader=leader)


def _validate_deck_cards(
    player_id: str,
    card_ids: list[str],
    cards: dict[str, sqlite3.Row],
    rules: dict[str, int | str],
    *,
    leader: sqlite3.Row | None = None,
) -> None:
    missing = [card_id for card_id in card_ids if card_id not in cards]
    if missing:
        raise PvpError(f"Gwent deck has unknown cards for {player_id}: {', '.join(missing)}")
    card_counts: dict[str, int] = {}
    for card_id in card_ids:
        card_counts[card_id] = card_counts.get(card_id, 0) + 1
    over_limit = []
    for card_id, count in card_counts.items():
        limit = max(1, _to_int(cards[card_id]["deck_limit"]))
        if count > limit:
            over_limit.append(f"{card_id} ({count}/{limit})")
    if over_limit:
        raise PvpError(f"Gwent deck for {player_id} exceeds card copy limit: {', '.join(over_limit)}")
    for card_id in card_ids:
        card = cards[card_id]
        if str(card["type"]) == "leader":
            raise PvpError(f"Gwent deck for {player_id} cannot include leader cards in the draw deck.")
        if leader is not None:
            leader_faction = str(leader["faction"] or "").strip().lower()
            card_faction = str(card["faction"] or "").strip().lower()
            if card_faction not in {leader_faction, "neutral"}:
                raise PvpError(
                    f"Gwent deck for {player_id} mixes faction {card_faction} "
                    f"with leader faction {leader_faction}: {card_id}"
                )
        for effect in _card_effects(card):
            _assert_stage1_gwent_effect_supported(card_id, str(card["type"]), effect)
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
        player_state["leader_disabled"] = bool(player_state.get("leader_disabled", False))
        player_state["private_reveals"] = list(player_state.get("private_reveals") or [])
        player_state["start_effects"] = list(player_state.get("start_effects") or [])
        player_state["faction"] = str(player_state.get("faction") or "")
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
    if card_id in hand:
        hand.remove(card_id)
        return
    if card_id in player_state.get("graveyard", []):
        raise PvpError(f"Gwent card has already been played by {player_id}: {card_id}")
    raise PvpError(f"Gwent card is not in current hand for {player_id}: {card_id}")


def _return_card_to_hand(player_state: dict[str, Any], card_id: str) -> None:
    player_state["hand"].append(card_id)


def _remove_pending_discard(cards: list[str], card_id: str) -> None:
    if card_id in cards:
        cards.remove(card_id)


def _unit_from_card(
    card: sqlite3.Row,
    *,
    player_id: str,
    played_by: str,
    row_name: str,
    **extra: Any,
) -> dict[str, Any]:
    card_id = str(card["card_id"])
    effects = _card_effects(card)
    name_group = _card_group(card, "name_group", card_id)
    unit = {
        "player_id": player_id,
        "played_by": played_by,
        "card_id": card_id,
        "row": row_name,
        "base_strength": _to_int(card["strength"]),
        "effect": effects[0],
        "effects": effects,
        "hero": "hero" in effects,
        "removed": False,
        "name_group": name_group,
        "bond_group": _card_group(card, "bond_group", name_group),
        "muster_group": _card_group(card, "muster_group", name_group),
    }
    unit.update(extra)
    return unit


def _active_unit_rows(
    units: list[dict[str, Any]],
    row_name: str,
) -> tuple[dict[str, int], int]:
    bond_counts: dict[str, int] = {}
    morale_count = 0
    for unit in units:
        if unit.get("removed"):
            continue
        if any(effect in _unit_effects(unit) for effect in {"bond", "tight_bond"}):
            group = _unit_group(unit, "bond_group", str(unit.get("card_id") or ""))
            bond_counts[group] = bond_counts.get(group, 0) + 1
        if _unit_has_effect(unit, "morale"):
            morale_count += 1
    return bond_counts, morale_count


def _effective_unit_strength(
    unit: dict[str, Any],
    *,
    row_name: str,
    weather_rows: set[str],
    horn_active: bool,
    bond_counts: dict[str, int],
    morale_count: int,
) -> int:
    strength = int(unit["base_strength"])
    if not _unit_has_effect(unit, "hero") and row_name in weather_rows:
        strength = 1
    if not _unit_has_effect(unit, "hero") and any(effect in _unit_effects(unit) for effect in {"bond", "tight_bond"}):
        group = _unit_group(unit, "bond_group", str(unit.get("card_id") or ""))
        strength *= max(1, bond_counts.get(group, 1))
    if not _unit_has_effect(unit, "hero") and horn_active:
        strength *= 2
    if not _unit_has_effect(unit, "hero") and not _unit_has_effect(unit, "morale"):
        strength += morale_count
    return strength


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
    for player_id in players:
        for row_name in GWENT_ROWS:
            for unit in deck_state[player_id].get("rows", {}).get(row_name, []):
                if not isinstance(unit, dict):
                    continue
                carried = dict(unit)
                carried["player_id"] = player_id
                carried.setdefault("played_by", player_id)
                carried.setdefault("row", row_name)
                carried["removed"] = False
                board[player_id][row_name].append(carried)
                consumed_cards[player_id].append(str(carried.get("card_id")))

    for play in _normalize_plays(round_state):
        player_id = str(play.get("player_id"))
        card_id = str(play.get("card_id"))
        if player_id not in board:
            raise PvpError(f"Round play references a non-participant: {player_id}")
        card = cards.get(card_id)
        if card is None:
            raise PvpError(f"Round play references an unknown Gwent card: {card_id}")
        card_type = str(card["type"])
        effects = _card_effects(card)
        effect = effects[0]
        for card_effect in effects:
            _assert_stage1_gwent_effect_supported(card_id, card_type, card_effect)

        player_state = deck_state[player_id]
        if card_type == "leader":
            _apply_leader_play(
                play,
                card,
                player_state,
                deck_state,
                cards,
                board,
                horn_rows,
                weather_rows,
                effects_applied,
                players,
            )
            continue

        _consume_card_from_hand(
            player_state,
            player_id,
            card_id,
        )
        consumed_cards[player_id].append(card_id)
        if card_type == "special":
            returned_before = len(returned_cards)
            scorch_before = len(scorch_pending)
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
            for scorch in scorch_pending[scorch_before:]:
                _apply_scorch(board, scorch, weather_rows, horn_rows, effects_applied)
            for returned in returned_cards[returned_before:]:
                if returned["player_id"] == player_id:
                    _remove_pending_discard(consumed_cards[player_id], str(returned["card_id"]))
                    _return_card_to_hand(player_state, str(returned["card_id"]))
            continue
        row_name = _row_for_card(card, str(play.get("row") or ""))
        board_player_id = _opponent_id(players, player_id) if "spy" in effects else player_id
        unit = _unit_from_card(
            card,
            player_id=board_player_id,
            played_by=player_id,
            row_name=row_name,
        )
        board[board_player_id][row_name].append(unit)
        if "commanders_horn" in effects:
            horn_rows[player_id].add(row_name)
            effects_applied.append(
                {
                    "card_id": card_id,
                    "effect": "commanders_horn",
                    "scope": "unit",
                    "row": row_name,
                }
            )
        if "spy" in effects:
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
        if "medic" in effects:
            revived = _apply_medic(
                play,
                player_id,
                player_state,
                cards,
                board,
                consumed_cards[player_id],
                effects_applied,
                weather_rows,
                horn_rows,
                players,
            )
            if revived is None:
                effects_applied.append({"card_id": card_id, "effect": "medic", "scope": "unit", "revived_card_id": None})
        if "muster" in effects:
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
        for card_effect in effects:
            if card_effect.startswith("scorch_"):
                _apply_scorch(
                    board,
                    {
                        "effect": card_effect,
                        "source_card_id": card_id,
                        "player_id": player_id,
                        "opponent_only": True,
                    },
                    weather_rows,
                    horn_rows,
                    effects_applied,
                )
            elif card_effect in {"morale", "bond", "tight_bond", "agile", "hero"}:
                effects_applied.append({"card_id": card_id, "effect": card_effect, "scope": "unit"})

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
        winner_id = _tie_winner_from_faction(players, deck_state, cards, effects_applied)
        tie = winner_id is None
    else:
        winner_id = players[0] if totals[players[0]] > totals[players[1]] else players[1]
        tie = False
    passed = round_state.get("passed") or round_state.get("passed_flags") or {}
    if not isinstance(passed, dict):
        passed = {}
    carryover_rows = (
        _apply_monsters_carryover(players, deck_state, cards, board, consumed_cards, effects_applied)
        if _round_end_abilities_should_apply(players, passed)
        else {player: {row: [] for row in GWENT_ROWS} for player in players}
    )
    for player_id in players:
        player_state = deck_state[player_id]
        player_state["graveyard"].extend(consumed_cards[player_id])
        player_state["rows"] = carryover_rows[player_id]
        player_state["passed"] = bool(passed.get(player_id, True))
        player_state["cards_burned"] = False
    if _round_end_abilities_should_apply(players, passed):
        _apply_round_end_faction_abilities(winner_id, deck_state, cards, effects_applied)
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


def _round_end_abilities_should_apply(players: list[str], passed: dict[str, Any]) -> bool:
    return all(bool(passed.get(player_id, True)) for player_id in players)


def _tie_winner_from_faction(
    players: list[str],
    deck_state: dict[str, Any],
    cards: dict[str, sqlite3.Row],
    effects_applied: list[dict[str, Any]],
) -> str | None:
    nilfgaard_players = [
        player_id
        for player_id in players
        if _deck_faction(deck_state.get(player_id, {}), cards) == "nilfgaard"
    ]
    if len(nilfgaard_players) != 1:
        return None
    winner_id = nilfgaard_players[0]
    effects_applied.append(
        {
            "effect": "faction_nilfgaard_tie_win",
            "scope": "faction",
            "player_id": winner_id,
            "faction": "nilfgaard",
        }
    )
    return winner_id


def _apply_round_end_faction_abilities(
    winner_id: str | None,
    deck_state: dict[str, Any],
    cards: dict[str, sqlite3.Row],
    effects_applied: list[dict[str, Any]],
) -> None:
    if not winner_id or winner_id not in deck_state:
        return
    player_state = deck_state[winner_id]
    faction = _deck_faction(player_state, cards)
    if faction != "northern":
        return
    drawn = _draw_cards(player_state, 1)
    effects_applied.append(
        {
            "effect": "faction_northern_realms_draw",
            "scope": "faction",
            "player_id": winner_id,
            "faction": faction,
            "drawn_count": len(drawn),
            "drawn_card_ids": drawn,
        }
    )


def _apply_monsters_carryover(
    players: list[str],
    deck_state: dict[str, Any],
    cards: dict[str, sqlite3.Row],
    board: dict[str, dict[str, list[dict[str, Any]]]],
    consumed_cards: dict[str, list[str]],
    effects_applied: list[dict[str, Any]],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    carryover_rows = {player_id: {row: [] for row in GWENT_ROWS} for player_id in players}
    for player_id in players:
        player_state = deck_state.get(player_id, {})
        if _deck_faction(player_state, cards) != "monsters":
            continue
        candidates = [
            unit
            for row_name in GWENT_ROWS
            for unit in board[player_id][row_name]
            if not unit.get("removed") and not _unit_has_effect(unit, "hero")
        ]
        if not candidates:
            effects_applied.append(
                {
                    "effect": "faction_monsters_keep_unit",
                    "scope": "faction",
                    "player_id": player_id,
                    "faction": "monsters",
                    "kept_card_id": None,
                }
            )
            continue
        seed = f"{player_state.get('shuffle_seed')}:monsters:{len(player_state.get('graveyard') or [])}:{len(consumed_cards[player_id])}"
        kept = random.Random(seed).choice(candidates)
        kept_card_id = str(kept["card_id"])
        _remove_pending_discard(consumed_cards[player_id], kept_card_id)
        carryover_rows[player_id][str(kept["row"])].append(dict(kept, carried_by_faction=True))
        effects_applied.append(
            {
                "effect": "faction_monsters_keep_unit",
                "scope": "faction",
                "player_id": player_id,
                "faction": "monsters",
                "kept_card_id": kept_card_id,
                "row": kept["row"],
            }
        )
    return carryover_rows


def _apply_skellige_round_three_restore(
    deck_state: dict[str, Any],
    players: list[str],
    cards: dict[str, sqlite3.Row],
    effects_applied: list[dict[str, Any]],
) -> None:
    for player_id in players:
        player_state = deck_state.get(player_id, {})
        if _deck_faction(player_state, cards) != "skellige":
            continue
        candidates = [
            card_id
            for card_id in player_state.get("graveyard", [])
            if (card := cards.get(str(card_id))) is not None
            and str(card["type"]) == "unit"
            and not _card_has_effect(card, "hero")
        ]
        seed = f"{player_state.get('shuffle_seed')}:skellige_round_three:{len(candidates)}"
        restored = _shuffle_card_ids([str(card_id) for card_id in candidates], seed)[:2]
        for card_id in restored:
            card = cards[card_id]
            player_state["graveyard"].remove(card_id)
            row_name = _row_for_card(card, "")
            player_state.setdefault("rows", {row: [] for row in GWENT_ROWS})
            player_state["rows"].setdefault(row_name, []).append(
                _unit_from_card(
                    card,
                    player_id=player_id,
                    played_by=player_id,
                    row_name=row_name,
                    restored_by_faction=True,
                )
            )
        effects_applied.append(
            {
                "effect": "faction_skellige_round_three_restore",
                "scope": "faction",
                "player_id": player_id,
                "faction": "skellige",
                "restored_card_ids": restored,
            }
        )


def _deck_faction(player_state: dict[str, Any], cards: dict[str, sqlite3.Row]) -> str:
    faction = str(player_state.get("faction") or "").strip().lower()
    if faction:
        return faction
    leader = cards.get(str(player_state.get("leader_card_id") or ""))
    if leader is None:
        return ""
    return str(leader["faction"] or "").strip().lower()


def _deck_faction_from_deck(deck: sqlite3.Row, cards: dict[str, sqlite3.Row]) -> str:
    leader = cards.get(str(deck["leader_card_id"]))
    if leader is None:
        return ""
    return str(leader["faction"] or "").strip().lower()


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
    effects = _card_effects(card)
    effect = effects[0]
    if effect in GWENT_WEATHER_BY_EFFECT:
        weather_rows.add(GWENT_WEATHER_BY_EFFECT[effect])
    elif effect == "clear_weather":
        weather_rows.clear()
    elif effect == "commanders_horn":
        horn_rows[player_id].add(_row_name(str(play.get("row") or "melee")))
    elif effect == "decoy":
        target_card_id = str(play.get("target_card_id") or "")
        if not target_card_id:
            raise PvpError("Gwent decoy requires target_card_id.")
        returned = _remove_card_from_board(board[player_id], target_card_id)
        if returned is None:
            raise PvpError(f"Gwent decoy target is not a non-hero unit on board: {target_card_id}")
        returned_cards.append({"player_id": player_id, "card_id": target_card_id})
    elif effect == "scorch":
        scorch_pending.append({"effect": "scorch", "source_card_id": card_id, "player_id": player_id})
    effects_applied.append({"card_id": card_id, "effect": effect, "scope": "special"})


def _apply_leader_play(
    play: dict[str, Any],
    card: sqlite3.Row,
    player_state: dict[str, Any],
    deck_state: dict[str, Any],
    cards: dict[str, sqlite3.Row],
    board: dict[str, dict[str, list[dict[str, Any]]]],
    horn_rows: dict[str, set[str]],
    weather_rows: set[str],
    effects_applied: list[dict[str, Any]],
    players: list[str],
) -> None:
    player_id = str(play.get("player_id"))
    card_id = str(card["card_id"])
    if str(player_state.get("leader_card_id")) != card_id:
        raise PvpError(f"Gwent leader is not assigned to player deck: {card_id}")
    if bool(player_state.get("leader_used")):
        raise PvpError(f"Gwent leader was already used by player: {player_id}")
    if bool(player_state.get("leader_disabled")):
        raise PvpError(f"Gwent leader is disabled for player: {player_id}")
    effect = _card_effects(card)[0]
    payload: dict[str, Any] = {"card_id": card_id, "effect": effect, "scope": "leader"}
    if effect == "leader_foltest_fog":
        weather_card_id, weather_effect = _play_weather_from_deck(player_state, cards, {"weather_ranged"})
        if weather_effect:
            weather_rows.add(GWENT_WEATHER_BY_EFFECT[weather_effect])
        payload["weather_card_id"] = weather_card_id
    elif effect == "leader_foltest_clear_weather":
        weather_rows.clear()
    elif effect == "leader_foltest_siege_horn":
        horn_rows[player_id].add("siege")
    elif effect == "leader_foltest_siege_scorch":
        _apply_scorch(
            board,
            {
                "effect": "scorch_siege",
                "source_card_id": card_id,
                "player_id": player_id,
                "opponent_only": True,
            },
            weather_rows,
            horn_rows,
            effects_applied,
        )
    elif effect == "leader_emhyr_spy_hand":
        opponent_id = _opponent_id(players, player_id)
        opponent_state = deck_state.get(opponent_id, {})
        opponent_hand = [str(card_id) for card_id in opponent_state.get("hand") or []]
        reveal_seed = (
            f"{player_state.get('shuffle_seed')}:leader_emhyr_spy_hand:"
            f"{opponent_id}:{len(player_state.get('private_reveals') or [])}"
        )
        revealed = random.Random(reveal_seed).sample(opponent_hand, min(3, len(opponent_hand)))
        player_state.setdefault("private_reveals", []).append(
            {
                "effect": effect,
                "opponent_player_id": opponent_id,
                "card_ids": revealed,
                "reveal_seed": reveal_seed,
            }
        )
        payload["opponent_player_id"] = opponent_id
        payload["revealed_count"] = len(revealed)
        payload["reveal_seed"] = reveal_seed
    elif effect == "leader_emhyr_rain":
        weather_card_id, weather_effect = _play_weather_from_deck(player_state, cards, {"weather_siege"})
        if weather_effect:
            weather_rows.add(GWENT_WEATHER_BY_EFFECT[weather_effect])
        payload["weather_card_id"] = weather_card_id
    elif effect == "leader_francesca_ranged_horn":
        horn_rows[player_id].add("ranged")
    elif effect == "leader_emhyr_cancel_leader":
        opponent_id = _opponent_id(players, player_id)
        deck_state.setdefault(opponent_id, {})["leader_disabled"] = True
        payload["disabled_player_id"] = opponent_id
    elif effect == "leader_francesca_draw":
        payload["drawn_card_ids"] = _draw_cards(player_state, 1)
    elif effect == "leader_francesca_frost":
        weather_card_id, weather_effect = _play_weather_from_deck(player_state, cards, {"weather_melee"})
        if weather_effect:
            weather_rows.add(GWENT_WEATHER_BY_EFFECT[weather_effect])
        payload["weather_card_id"] = weather_card_id
    elif effect == "leader_francesca_melee_scorch":
        _apply_scorch(
            board,
            {
                "effect": "scorch_melee",
                "source_card_id": card_id,
                "player_id": player_id,
                "opponent_only": True,
            },
            weather_rows,
            horn_rows,
            effects_applied,
        )
    elif effect == "leader_eredin_melee_horn":
        horn_rows[player_id].add("melee")
    elif effect == "leader_emhyr_graveyard_theft":
        opponent_id = _opponent_id(players, player_id)
        opponent_state = deck_state.get(opponent_id, {})
        target_card_id = str(play.get("target_card_id") or "")
        if not target_card_id:
            raise PvpError("Gwent leader graveyard theft requires target_card_id.")
        if target_card_id not in opponent_state.get("graveyard", []):
            raise PvpError(f"Gwent leader target is not in opponent graveyard: {target_card_id}")
        target = cards.get(target_card_id)
        if target is None or str(target["type"]) != "unit" or _card_has_effect(target, "hero"):
            raise PvpError(f"Gwent leader target is not a revivable non-hero unit: {target_card_id}")
        if target_card_id:
            opponent_state["graveyard"].remove(target_card_id)
            player_state["hand"].append(target_card_id)
        payload["drawn_from_opponent_graveyard"] = target_card_id or None
    elif effect == "leader_eredin_graveyard_return":
        target_card_id = str(play.get("target_card_id") or "")
        if not target_card_id:
            raise PvpError("Gwent leader graveyard return requires target_card_id.")
        if target_card_id not in player_state.get("graveyard", []):
            raise PvpError(f"Gwent leader target is not in own graveyard: {target_card_id}")
        target = cards.get(target_card_id)
        if target is None or str(target["type"]) != "unit" or _card_has_effect(target, "hero"):
            raise PvpError(f"Gwent leader target is not a revivable non-hero unit: {target_card_id}")
        if target_card_id:
            player_state["graveyard"].remove(target_card_id)
            player_state["hand"].append(target_card_id)
        payload["returned_from_graveyard"] = target_card_id or None
    elif effect == "leader_eredin_discard_draw":
        target_card_id = str(play.get("target_card_id") or "")
        draw_pile = player_state.get("draw_pile") or []
        discard_card_ids = [
            str(discard_card_id).strip()
            for discard_card_id in (play.get("discard_card_ids") or [])
            if str(discard_card_id).strip()
        ]
        if len(discard_card_ids) != 2 or len(set(discard_card_ids)) != 2:
            raise PvpError("Gwent leader discard draw requires exactly two distinct discard_card_ids.")
        hand = list(player_state.get("hand") or [])
        missing_discards = [discard_id for discard_id in discard_card_ids if discard_id not in hand]
        if missing_discards:
            raise PvpError(f"Gwent leader discard cards are not in current hand: {', '.join(missing_discards)}")
        if not target_card_id:
            raise PvpError("Gwent leader discard draw requires target_card_id from draw pile.")
        if target_card_id not in draw_pile:
            raise PvpError(f"Gwent leader target is not in draw pile: {target_card_id}")
        discarded: list[str] = []
        for discard_id in discard_card_ids:
            player_state["hand"].remove(discard_id)
            player_state.setdefault("graveyard", []).append(discard_id)
            discarded.append(str(discard_id))
        player_state["draw_pile"].remove(target_card_id)
        player_state["hand"].append(target_card_id)
        payload["discarded_card_ids"] = discarded
        payload["drawn_card_id"] = target_card_id
    elif effect == "leader_eredin_weather":
        weather_card_id, weather_effect = _play_weather_from_deck(
            player_state,
            cards,
            {"weather_melee", "weather_ranged", "weather_siege"},
        )
        if weather_effect:
            weather_rows.add(GWENT_WEATHER_BY_EFFECT[weather_effect])
        payload["weather_card_id"] = weather_card_id
    elif effect == "leader_crach_graveyard_shuffle":
        shuffled_by_player: dict[str, list[str]] = {}
        for candidate_id in players:
            candidate_state = deck_state.get(candidate_id, {})
            graveyard = [str(card_id) for card_id in candidate_state.get("graveyard") or []]
            if not graveyard:
                shuffled_by_player[candidate_id] = []
                continue
            seed = f"{candidate_state.get('shuffle_seed')}:leader_crach:{card_id}:{len(candidate_state.get('draw_pile') or [])}"
            shuffled = _shuffle_card_ids(graveyard, seed)
            candidate_state["draw_pile"].extend(shuffled)
            candidate_state["graveyard"] = []
            shuffled_by_player[candidate_id] = shuffled
        payload["shuffled_graveyards"] = shuffled_by_player
    player_state["leader_used"] = True
    effects_applied.append(payload)


def _play_weather_from_deck(
    player_state: dict[str, Any],
    cards: dict[str, sqlite3.Row],
    effects: set[str],
) -> tuple[str | None, str | None]:
    for card_id in list(player_state.get("draw_pile") or []):
        card = cards.get(str(card_id))
        if card is None or str(card["type"]) != "special":
            continue
        for effect in _card_effects(card):
            if effect not in effects:
                continue
            player_state["draw_pile"].remove(str(card_id))
            player_state.setdefault("graveyard", []).append(str(card_id))
            return str(card_id), effect
    return None, None


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
    weather_rows: set[str],
    horn_rows: dict[str, set[str]],
    players: list[str],
    *,
    chain_depth: int = 0,
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
    if target is None or str(target["type"]) != "unit" or _card_has_effect(target, "hero"):
        raise PvpError(f"Gwent medic target is not a revivable unit: {target_card_id}")
    graveyard.remove(target_card_id)
    row_name = _row_for_card(target, str(play.get("revive_row") or ""))
    target_effects = _card_effects(target)
    board_player_id = _opponent_id(players, player_id) if "spy" in target_effects else player_id
    board[board_player_id][row_name].append(
        _unit_from_card(
            target,
            player_id=board_player_id,
            played_by=player_id,
            row_name=row_name,
            revived_by_medic=True,
        )
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
    if "commanders_horn" in target_effects:
        horn_rows[player_id].add(row_name)
        effects_applied.append(
            {
                "card_id": target_card_id,
                "effect": "commanders_horn",
                "scope": "unit",
                "row": row_name,
                "triggered_by": "medic",
            }
        )
    if "spy" in target_effects:
        drawn = _draw_cards(player_state, 2)
        effects_applied.append(
            {
                "card_id": target_card_id,
                "effect": "spy",
                "scope": "unit",
                "placed_for_player_id": board_player_id,
                "drawn_card_ids": drawn,
                "triggered_by": "medic",
            }
        )
    if "muster" in target_effects:
        mustered = _apply_muster(player_id, target_card_id, target, player_state, cards, board, consumed)
        effects_applied.append(
            {
                "card_id": target_card_id,
                "effect": "muster",
                "scope": "unit",
                "mustered_card_ids": mustered,
                "triggered_by": "medic",
            }
        )
    if "medic" in target_effects and chain_depth < 4:
        _apply_medic(
            {"card_id": target_card_id},
            player_id,
            player_state,
            cards,
            board,
            consumed,
            effects_applied,
            weather_rows,
            horn_rows,
            players,
            chain_depth=chain_depth + 1,
        )
    for effect in target_effects:
        if effect.startswith("scorch_"):
            _apply_scorch(
                board,
                {
                    "effect": effect,
                    "source_card_id": target_card_id,
                    "player_id": player_id,
                    "opponent_only": True,
                },
                weather_rows,
                horn_rows,
                effects_applied,
            )
        elif effect in {"morale", "bond", "tight_bond", "agile", "hero"}:
            effects_applied.append(
                {
                    "card_id": target_card_id,
                    "effect": effect,
                    "scope": "unit",
                    "triggered_by": "medic",
                }
            )
    return target_card_id


def _first_medic_target(graveyard: list[str], cards: dict[str, sqlite3.Row]) -> str:
    for card_id in graveyard:
        card = cards.get(card_id)
        if card is not None and str(card["type"]) == "unit" and not _card_has_effect(card, "hero"):
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
    source_group = _card_group(
        source_card,
        "muster_group",
        _card_group(source_card, "name_group", source_card_id),
    )
    candidates = list(player_state["hand"]) + list(player_state["draw_pile"])
    for card_id in candidates:
        if card_id == source_card_id:
            continue
        card = cards.get(card_id)
        if (
            card is None
            or str(card["type"]) != "unit"
            or not _card_has_effect(card, "muster")
            or _card_group(card, "muster_group", _card_group(card, "name_group", card_id)) != source_group
        ):
            continue
        if card_id in player_state["hand"]:
            player_state["hand"].remove(card_id)
        elif card_id in player_state["draw_pile"]:
            player_state["draw_pile"].remove(card_id)
        row_name = _row_for_card(card, "")
        board[player_id][row_name].append(
            _unit_from_card(
                card,
                player_id=player_id,
                played_by=player_id,
                row_name=row_name,
                mustered=True,
            )
        )
        consumed.append(card_id)
        mustered.append(card_id)
    return mustered


def _apply_scorch(
    board: dict[str, dict[str, list[dict[str, Any]]]],
    scorch: dict[str, Any],
    weather_rows: set[str],
    horn_rows: dict[str, set[str]],
    effects_applied: list[dict[str, Any]],
) -> None:
    effect = str(scorch["effect"])
    row_filter = effect.removeprefix("scorch_") if effect.startswith("scorch_") else None
    source_player_id = str(scorch.get("player_id") or "")
    opponent_only = bool(scorch.get("opponent_only"))
    candidates: list[tuple[dict[str, Any], int]] = []
    row_totals: dict[tuple[str, str], int] = {}
    for board_player_id, rows in board.items():
        if opponent_only and source_player_id and board_player_id == source_player_id:
            continue
        for row_name, units in rows.items():
            if row_filter and row_filter != row_name:
                continue
            active_units = [unit for unit in units if not unit["removed"]]
            bond_counts, morale_count = _active_unit_rows(active_units, row_name)
            row_total = 0
            for unit in units:
                if unit["removed"] or _unit_has_effect(unit, "hero"):
                    continue
                strength = _effective_unit_strength(
                    unit,
                    row_name=row_name,
                    weather_rows=weather_rows,
                    horn_active=row_name in horn_rows.get(board_player_id, set()),
                    bond_counts=bond_counts,
                    morale_count=morale_count,
                )
                row_total += strength
                candidates.append((unit, strength))
            row_totals[(board_player_id, row_name)] = row_total
    if not candidates:
        return
    if row_filter and opponent_only:
        candidates = [
            (unit, strength)
            for unit, strength in candidates
            if row_totals.get((str(unit.get("player_id") or ""), row_filter), 0) >= 10
        ]
        if not candidates:
            return
    max_strength = max(strength for _, strength in candidates)
    if max_strength < 10 and not (row_filter and opponent_only):
        return
    removed_ids = []
    for unit, strength in candidates:
        if strength == max_strength:
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
    bond_counts, morale_count = _active_unit_rows(active_units, row_name)
    return sum(
        _effective_unit_strength(
            unit,
            row_name=row_name,
            weather_rows=weather_rows,
            horn_active=horn_active,
            bond_counts=bond_counts,
            morale_count=morale_count,
        )
        for unit in active_units
    )


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
    payload["prep"] = _challenge_prep(row)
    payload["duplicate"] = duplicate
    return payload


def _challenge_prep(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    raw = row["prep_json"] if "prep_json" in row.keys() else "{}"  # type: ignore[union-attr]
    prep = _json_loads(str(raw or "{}"), {})
    if not isinstance(prep, dict):
        prep = {}
    ready_players = [str(value) for value in prep.get("ready_players") or []]
    players = [str(row["challenger_id"]), str(row["target_id"])]
    mulligans_by_player = prep.get("mulligans_by_player") if isinstance(prep.get("mulligans_by_player"), dict) else {}
    deck_ids_by_player = prep.get("deck_ids_by_player") if isinstance(prep.get("deck_ids_by_player"), dict) else {}
    preferred_starting_player_ids = (
        prep.get("preferred_starting_player_ids_by_player")
        if isinstance(prep.get("preferred_starting_player_ids_by_player"), dict)
        else {}
    )
    updated_at_by_player = prep.get("updated_at_by_player") if isinstance(prep.get("updated_at_by_player"), dict) else {}
    return {
        "ready_players": ready_players,
        "missing_players": [player_id for player_id in players if player_id not in ready_players],
        "mulligans_by_player": {
            str(player_id): [str(card_id) for card_id in cards]
            for player_id, cards in mulligans_by_player.items()
            if isinstance(cards, list)
        },
        "deck_ids_by_player": {
            str(player_id): str(deck_id)
            for player_id, deck_id in deck_ids_by_player.items()
        },
        "preferred_starting_player_ids_by_player": {
            str(player_id): str(preferred_player_id)
            for player_id, preferred_player_id in preferred_starting_player_ids.items()
        },
        "updated_at_by_player": {
            str(player_id): str(updated_at)
            for player_id, updated_at in updated_at_by_player.items()
        },
        "updated_at": prep.get("updated_at"),
        "all_ready": all(player_id in ready_players for player_id in players),
    }


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
        "stake": _stake_payload(connection, str(row["challenge_id"])),
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
            if unit["card_id"] == target_card_id and not unit["removed"] and not _unit_has_effect(unit, "hero"):
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


def _deck_for_player(
    connection: sqlite3.Connection,
    player_id: str,
    *,
    deck_id: str | None = None,
) -> sqlite3.Row:
    if not _table_exists(connection, "gwent_decks"):
        raise PvpError("No imported Gwent decks are available.")
    normalized_deck_id = str(deck_id or "").strip()
    if normalized_deck_id:
        if _table_exists(connection, "gwent_deck_runtime"):
            runtime_row = connection.execute(
                """
                SELECT deck_id, player_id, leader_card_id, card_ids
                FROM gwent_deck_runtime
                WHERE player_id = ?
                  AND deck_id = ?
                  AND status = 'active'
                LIMIT 1
                """,
                (player_id, normalized_deck_id),
            ).fetchone()
            if runtime_row is not None:
                return runtime_row
        row = connection.execute(
            """
            SELECT *
            FROM gwent_decks
            WHERE player_id = ?
              AND deck_id = ?
            ORDER BY _row_number
            LIMIT 1
            """,
            (player_id, normalized_deck_id),
        ).fetchone()
        if row is None:
            raise PvpError(f"Gwent deck is not available for player {player_id}: {normalized_deck_id}")
        return row

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


def _player_available_gwent_card_ids(connection: sqlite3.Connection, player_id: str) -> set[str]:
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
    return available


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
