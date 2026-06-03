"""Final master summary read model and post-game export payload."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from typing import Any
from uuid import uuid4

from .asset_service import active_asset_locks, active_reward_approvals
from .lord_runtime import ensure_lord_runtime_state
from .npc_service import list_npc_deals, list_npc_events, review_queue
from .pvp_service import ensure_pvp_runtime_state
from .reputation_service import ReputationError, get_reputation_view
from .repository import latest_snapshot_version
from .runtime_schema import ensure_runtime_schema, log_event
from .sorceress_service import ensure_sorceress_runtime_state
from .timer_service import ensure_runtime_content_state


LOCKED_INTENT_LOCKED_STATUSES = {"locked"}
LOCKED_INTENT_REVIEW_STATUSES = {
    "needs_master_review",
    "pending_master_review",
    "review_pending",
    "pending_review",
    "pending",
}
LOCKED_INTENT_DISPUTED_STATUSES = {
    "contested_review",
    "disputed",
    "conflict",
    "review_disputed",
}


def build_final_summary(
    connection: sqlite3.Connection,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the master-only final evidence bundle without scoring winners."""

    ensure_final_summary_runtime_state(connection)
    generated_at = _iso(now)
    fields = _final_summary_fields(connection)
    config = _final_summary_config(connection)
    evidence_by_role = {
        "lords": _lord_evidence(connection),
        "witchers": _witcher_evidence(connection),
        "sorceresses": _sorceress_evidence(connection),
        "npc_story": _npc_story_evidence(connection),
        "disputed_objects": _disputed_object_evidence(connection),
    }
    pending_disputes = _pending_disputes(connection)
    pending_rewards = active_reward_approvals(connection)
    asset_locks = active_asset_locks(connection)
    paper_recovery = _paper_recovery(connection)
    locked_intents = _locked_magical_intent(connection)
    personal_hooks = _personal_hooks(connection)
    missing_locks = _missing_locks(
        connection,
        fields,
        evidence_by_role=evidence_by_role,
        pending_disputes=pending_disputes,
        paper_recovery=paper_recovery,
        locked_intents=locked_intents,
        personal_hooks=personal_hooks,
    )

    automatic_winner = bool(config.get("automatic_winner_calculation", False))
    snapshot_version = latest_snapshot_version(connection)
    return {
        "snapshot_version": snapshot_version,
        "final_lock_state": _final_lock_state(connection),
        "final_summary_config": config,
        "evidence_fields": fields,
        "evidence_by_role": evidence_by_role,
        "missing_locks": missing_locks,
        "pending_disputes": pending_disputes,
        "pending_rewards": pending_rewards,
        "asset_locks": asset_locks,
        "npc_prices": list_npc_deals(connection, visibility="master"),
        "locked_magical_intent": locked_intents,
        "personal_hooks": personal_hooks,
        "paper_recovery": paper_recovery,
        "final_procedures": _final_procedures(connection),
        "staffing": _staffing(connection),
        "master_final_notes": _master_final_notes(connection),
        "player_visible_categories": _player_visible_categories(fields),
        "decision_policy": {
            "automatic_winner_calculation": automatic_winner,
            "winner_policy": config.get("winner_policy", "masters_decide_from_evidence"),
            "masters_must_decide": not automatic_winner,
            "personal_hooks_are_tone_and_edge_case_inputs": True,
            "visible_play_cannot_be_silently_erased": True,
        },
        "export": {
            "json_ready": True,
            "formats": ["json"],
            "post_game_review": True,
            "snapshot_version": snapshot_version,
            "generated_at": generated_at,
            "automatic_winner_calculation": automatic_winner,
        },
        "export_generated_at": generated_at,
    }


def record_final_master_note(
    connection: sqlite3.Connection,
    *,
    note_text: str,
    category: str = "ruling",
    target_id: str | None = None,
    visibility: str = "masters",
    operator: str = "master",
    source: str = "master_api",
    note_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_runtime_schema(connection)
    text = note_text.strip()
    if not text:
        raise ValueError("Final master note text is required.")
    new_note_id = note_id or f"final_note_{uuid4().hex}"
    timestamp = _iso(now)
    connection.execute(
        """
        INSERT INTO final_master_notes (
            note_id, category, target_id, note_text, visibility,
            operator, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(note_id) DO UPDATE SET
            category = excluded.category,
            target_id = excluded.target_id,
            note_text = excluded.note_text,
            visibility = excluded.visibility,
            operator = excluded.operator,
            source = excluded.source,
            created_at = excluded.created_at
        """,
        (
            new_note_id,
            category,
            target_id,
            text,
            visibility,
            operator,
            source,
            timestamp,
        ),
    )
    note = _master_note_by_id(connection, new_note_id)
    log_event(connection, "final_master_note_recorded", note, source=source, created_at=now)
    return note


def ensure_final_summary_runtime_state(connection: sqlite3.Connection) -> None:
    ensure_runtime_schema(connection)
    ensure_runtime_content_state(connection)
    ensure_lord_runtime_state(connection)
    ensure_pvp_runtime_state(connection)
    ensure_sorceress_runtime_state(connection)


def _final_summary_config(connection: sqlite3.Connection) -> dict[str, Any]:
    row = _first_row(connection, "final_summary", "SELECT * FROM final_summary ORDER BY _row_number")
    if row is None:
        return {
            "summary_id": None,
            "tournament_mode": "npc_led_tournament",
            "winner_policy": "masters_decide_from_evidence",
            "includes_missing_locks": True,
            "includes_pending_disputes": True,
            "includes_npc_prices": True,
            "includes_locked_magical_intent": True,
            "export_snapshot_required": True,
            "automatic_winner_calculation": False,
        }
    return {
        "summary_id": row["summary_id"],
        "final_act_id": row["final_act_id"],
        "tournament_mode": row["tournament_mode"],
        "winner_policy": row["winner_policy"],
        "includes_missing_locks": _truthy(row["includes_missing_locks"]),
        "includes_pending_disputes": _truthy(row["includes_pending_disputes"]),
        "includes_npc_prices": _truthy(row["includes_npc_prices"]),
        "includes_locked_magical_intent": _truthy(row["includes_locked_magical_intent"]),
        "export_snapshot_required": _truthy(row["export_snapshot_required"]),
        "automatic_winner_calculation": _truthy(row["automatic_winner_calculation"]),
    }


def _final_summary_fields(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = _rows(
        connection,
        "final_summary_fields",
        """
        SELECT field_id, source_type, evidence_category, visibility, required_for_export
        FROM final_summary_fields
        ORDER BY _row_number
        """,
    )
    return [
        {
            "field_id": row["field_id"],
            "source_type": row["source_type"],
            "evidence_category": row["evidence_category"],
            "visibility": row["visibility"],
            "required_for_export": _truthy(row["required_for_export"]),
        }
        for row in rows
    ]


def _final_lock_state(connection: sqlite3.Connection) -> dict[str, Any]:
    lock = connection.execute(
        "SELECT locked_at, operator, source FROM final_lock_state WHERE id = 1"
    ).fetchone()
    act = connection.execute(
        """
        SELECT current_act_id, status, active_started_at, updated_at
        FROM act_state
        WHERE id = 1
        """
    ).fetchone()
    throttle = connection.execute(
        """
        SELECT mode, final_lock_behavior, max_tables, max_started_per_player_per_act
        FROM pvp_throttle_state
        WHERE id = 1
        """
    ).fetchone()
    locked_at = lock["locked_at"] if lock is not None else None
    return {
        "locked": bool(locked_at),
        "locked_at": locked_at,
        "operator": lock["operator"] if lock is not None else None,
        "source": lock["source"] if lock is not None else None,
        "current_act_id": act["current_act_id"] if act is not None else None,
        "act_status": act["status"] if act is not None else "not_started",
        "active_started_at": act["active_started_at"] if act is not None else None,
        "blocks_new_orders": bool(locked_at),
        "blocks_new_challenges": bool(locked_at),
        "allowed_after_lock": ["master_override", "paper_recovered", "paper_final_evidence"],
        "pvp_throttle": _clean_row(throttle) if throttle is not None else {},
    }


def _lord_evidence(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    result = []
    for lord in _players(connection, "lord"):
        lord_id = str(lord["player_id"])
        domain = _first_row(
            connection,
            "domain_runtime_state",
            "SELECT * FROM domain_runtime_state WHERE lord_player_id = ?",
            (lord_id,),
        )
        domain_id = str(domain["domain_id"]) if domain is not None else None
        result.append(
            {
                "player": _player_payload(connection, lord),
                "domain": _clean_row(domain) if domain is not None else None,
                "territories": _territories_for_domain(connection, domain_id),
                "claims": _rows_as_dicts(
                    connection,
                    "territory_claim_runtime",
                    """
                    SELECT *
                    FROM territory_claim_runtime
                    WHERE claimant_domain_id = ? OR defender_domain_id = ?
                    ORDER BY created_at, claim_id
                    """,
                    (domain_id, domain_id),
                )
                if domain_id
                else [],
                "garrisons": _rows_as_dicts(
                    connection,
                    "garrison_runtime_state",
                    "SELECT * FROM garrison_runtime_state WHERE domain_id = ? ORDER BY territory_id, card_id",
                    (domain_id,),
                )
                if domain_id
                else [],
                "army_reserve": _rows_as_dicts(
                    connection,
                    "army_reserve_runtime",
                    "SELECT * FROM army_reserve_runtime WHERE domain_id = ? ORDER BY card_id, reserve_id",
                    (domain_id,),
                )
                if domain_id
                else [],
                "active_army": _rows_as_dicts(
                    connection,
                    "active_army_runtime",
                    "SELECT * FROM active_army_runtime WHERE domain_id = ? ORDER BY card_id, army_id",
                    (domain_id,),
                )
                if domain_id
                else [],
                "buildings": _rows_as_dicts(
                    connection,
                    "domain_buildings",
                    "SELECT * FROM domain_buildings WHERE domain_id = ? ORDER BY purchased_at, building_id",
                    (domain_id,),
                )
                if domain_id
                else [],
                "orders": _orders_for_lord(connection, lord_id),
                "lord_battles": _lord_battles_for_domain(connection, domain_id),
                "raids": _raid_effects_for_domain(connection, domain_id),
                "evidence_categories": ["territory", "battle", "economy", "order", "raid"],
            }
        )
    return result


def _witcher_evidence(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    result = []
    for witcher in _players(connection, "witcher"):
        player_id = str(witcher["player_id"])
        result.append(
            {
                "player": _player_payload(connection, witcher),
                "reputation": _reputation(connection, player_id),
                "pve_attempts": _pve_attempts_for_player(connection, player_id),
                "orders": _orders_for_player(connection, player_id),
                "pvp": _pvp_for_player(connection, player_id),
                "trade_transfers": _trade_transfers_for_player(connection, player_id),
                "npc_prices": _npc_deals_for_target(connection, player_id),
                "personal_hooks": _personal_hooks_for_player(connection, player_id),
                "evidence_categories": [
                    "pve_contract",
                    "pvp_gwent",
                    "order",
                    "npc_price",
                    "personal_hooks",
                ],
            }
        )
    return result


def _sorceress_evidence(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    result = []
    locked_intents = _locked_magical_intent(connection)
    for sorceress in _players(connection, "sorceress"):
        player_id = str(sorceress["player_id"])
        result.append(
            {
                "player": _player_payload(connection, sorceress),
                "reputation": _reputation(connection, player_id),
                "spell_casts": _spell_casts_for_sorceress(connection, player_id),
                "locked_magical_intent": [
                    item for item in locked_intents if item["sorceress_id"] == player_id
                ],
                "potions": {
                    "inventory": _rows_as_dicts(
                        connection,
                        "potion_inventory",
                        "SELECT * FROM potion_inventory WHERE player_id = ? ORDER BY potion_id",
                        (player_id,),
                    ),
                    "scene_usage": _rows_as_dicts(
                        connection,
                        "potion_scene_usage",
                        "SELECT * FROM potion_scene_usage WHERE player_id = ? ORDER BY created_at",
                        (player_id,),
                    ),
                    "transfers": _trade_transfers_for_player(connection, player_id),
                },
                "favorites": _favorites_for_sorceress(connection, player_id),
                "favorite_history": _favorite_history_for_sorceress(connection, player_id),
                "alignment_evidence": _alignment_evidence_for_sorceress(connection, player_id),
                "npc_prices": _npc_deals_for_target(connection, player_id),
                "personal_hooks": _personal_hooks_for_player(connection, player_id),
                "evidence_categories": [
                    "locked_magical_intent",
                    "potion_economy",
                    "favorite",
                    "alignment",
                    "npc_price",
                    "personal_hooks",
                ],
            }
        )
    return result


def _npc_story_evidence(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        "events": list_npc_events(connection, visibility="master"),
        "deals": list_npc_deals(connection, visibility="master"),
        "reputation_changes": _rows_as_dicts(
            connection,
            "reputation_changes",
            """
            SELECT *
            FROM reputation_changes
            ORDER BY created_at, change_id
            """,
        ),
        "final_hooks": _rows_as_dicts(
            connection,
            "final_hooks",
            "SELECT * FROM final_hooks ORDER BY role_category, evidence_category, final_hook_id",
        ),
    }


def _disputed_object_evidence(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    disputed = []
    disputed.extend(
        {
            "source_type": "order",
            "object_id": row["object_id"],
            "status": row["status"],
            "reason": row["reason"],
            "owner_id": row["lord_id"],
            "record_id": row["order_id"],
        }
        for row in _rows(
            connection,
            "order_runtime_state",
            """
            SELECT order_id, lord_id, object_id, status, reason
            FROM order_runtime_state
            WHERE status IN ('pending_master_approval', 'contested_review')
            ORDER BY updated_at, order_id
            """,
        )
    )
    disputed.extend(
        {
            "source_type": "pvp",
            "object_id": row["asset_id"],
            "status": row["status"],
            "reason": "stake not applied",
            "owner_id": row["owner_player_id"],
            "record_id": row["stake_ledger_id"],
        }
        for row in _rows(
            connection,
            "pvp_stake_ledger",
            """
            SELECT stake_ledger_id, asset_id, owner_player_id, status
            FROM pvp_stake_ledger
            WHERE status = 'locked'
            ORDER BY created_at, stake_ledger_id
            """,
        )
    )
    disputed.extend(
        {
            "source_type": "trade_transfer",
            "object_id": row["asset_id"],
            "status": row["status"],
            "reason": "pending transfer lock",
            "owner_id": row["from_player_id"],
            "record_id": row["transfer_id"],
        }
        for row in _rows(
            connection,
            "trade_transfer_runtime",
            """
            SELECT transfer_id, from_player_id, asset_id, status
            FROM trade_transfer_runtime
            WHERE status = 'pending_locked'
            ORDER BY created_at, transfer_id
            """,
        )
    )
    disputed.extend(
        {
            "source_type": "reward_approval_lock",
            "object_id": row["asset_id"],
            "asset_type": row["asset_type"],
            "status": row["status"],
            "reason": row["reason"] or "reward asset pending master approval",
            "owner_id": row["owner_player_id"],
            "record_id": row["source_ref_id"],
        }
        for row in _rows(
            connection,
            "asset_locks",
            """
            SELECT source_ref_id, owner_player_id, asset_type, asset_id, status, reason
            FROM asset_locks
            WHERE lock_type = 'reward_approval' AND status = 'active'
            ORDER BY locked_at, lock_id
            """,
        )
    )
    disputed.extend(
        {
            "source_type": "paper_recovered",
            "object_id": item.get("payload", {}).get("target_id")
            or item.get("payload", {}).get("order_id")
            or item.get("payload", {}).get("battle_id")
            or item.get("event_id"),
            "status": item["status"],
            "reason": item["reason"],
            "owner_id": item["actor_id"],
            "record_id": item["event_id"],
        }
        for item in _paper_recovery(connection)
    )
    return disputed


def _pending_disputes(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    disputes: list[dict[str, Any]] = []
    for item in review_queue(connection)["items"]:
        disputes.append({"source_type": "review_queue", **item})
    disputes.extend(
        {"source_type": "pvp_review", **_clean_row(row)}
        for row in _rows(
            connection,
            "pvp_reviews",
            """
            SELECT *
            FROM pvp_reviews
            WHERE status = 'needs_master_review'
            ORDER BY created_at, review_id
            """,
        )
    )
    disputes.extend(
        {
            "source_type": "reward_approval",
            "record_id": row["approval_id"],
            "reward_id": row["reward_id"],
            "player_id": row["player_id"],
            "status": row["status"],
            "reason": "reward requires master approval",
            "severity": "P2",
            "created_at": row["created_at"],
        }
        for row in _rows(
            connection,
            "reward_approvals",
            """
            SELECT approval_id, reward_id, player_id, status, created_at
            FROM reward_approvals
            WHERE status = 'pending_master_approval'
            ORDER BY created_at, approval_id
            """,
        )
    )
    disputes.extend(
        {
            "source_type": "order",
            "record_id": row["order_id"],
            "object_id": row["object_id"],
            "lord_id": row["lord_id"],
            "status": row["status"],
            "reason": row["reason"] or "order awaits master ruling",
            "severity": "P1" if row["status"] == "pending_master_approval" else "P2",
            "created_at": row["created_at"],
        }
        for row in _rows(
            connection,
            "order_runtime_state",
            """
            SELECT order_id, object_id, lord_id, status, reason, created_at
            FROM order_runtime_state
            WHERE status IN ('pending_master_approval', 'contested_review')
            ORDER BY created_at, order_id
            """,
        )
    )
    disputes.sort(
        key=lambda item: (
            _severity_rank(str(item.get("severity", "P3"))),
            str(item.get("created_at", "")),
        )
    )
    return disputes


def _paper_recovery(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = _rows(
        connection,
        "events",
        """
        SELECT server_event_id, event_id, actor_id, actor_type, status, reason,
               payload_json, metadata_json, source, received_at
        FROM events
        WHERE event_type = 'paper_recovered'
        ORDER BY received_at, server_event_id
        """,
    )
    items = []
    for row in rows:
        payload = _json_loads(row["payload_json"], {})
        metadata = _json_loads(row["metadata_json"], {})
        review = _first_row(
            connection,
            "event_reviews",
            """
            SELECT review_id, status, reason, severity, created_at
            FROM event_reviews
            WHERE server_event_id = ?
            ORDER BY review_id DESC
            """,
            (row["server_event_id"],),
        )
        items.append(
            {
                "server_event_id": int(row["server_event_id"]),
                "event_id": row["event_id"],
                "actor_id": row["actor_id"],
                "actor_type": row["actor_type"],
                "status": row["status"],
                "reason": row["reason"],
                "payload": payload,
                "metadata": metadata,
                "conflict_status": payload.get("conflict_status"),
                "source_form_type": payload.get("source_form_type"),
                "review": _clean_row(review) if review is not None else None,
                "source": row["source"],
                "received_at": row["received_at"],
            }
        )
    return items


def _locked_magical_intent(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    records = _locked_magical_intent_records(connection)
    records_by_sorceress: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        records_by_sorceress.setdefault(str(record["sorceress_id"]), []).append(record)

    result = []
    for sorceress in _players(connection, "sorceress"):
        player_id = str(sorceress["player_id"])
        result.append(
            _locked_magical_intent_state(
                player_id,
                str(sorceress["display_name"]),
                records_by_sorceress.get(player_id, []),
            )
        )
    return result


def _locked_magical_intent_records(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        {**_clean_row(row), "intent": _json_loads(row["intent_json"], {})}
        for row in _rows(
            connection,
            "locked_magical_intent",
            """
            SELECT *
            FROM locked_magical_intent
            ORDER BY created_at, intent_id
            """,
        )
    ]


def _locked_magical_intent_state(
    sorceress_id: str, display_name: str, records: list[dict[str, Any]]
) -> dict[str, Any]:
    if not records:
        return {
            "intent_id": None,
            "sorceress_id": sorceress_id,
            "sorceress_display_name": display_name,
            "cast_id": None,
            "target_id": None,
            "intent": {},
            "status": "missing",
            "runtime_status": None,
            "review_reason": "required magical intent lock is missing",
            "locked_at": None,
            "created_at": None,
            "required_for_export": True,
            "state_source": "required_missing",
            "records": [],
        }

    latest = records[-1]
    runtime_status = str(latest["status"])
    status = _normalize_locked_intent_status(runtime_status)
    review_reason = latest.get("review_reason")
    if status == "review_pending" and not review_reason:
        review_reason = "magical intent is pending master review"
    elif status == "disputed" and not review_reason:
        review_reason = "magical intent is disputed"
    return {
        **latest,
        "sorceress_display_name": display_name,
        "status": status,
        "runtime_status": runtime_status,
        "review_reason": review_reason,
        "required_for_export": True,
        "state_source": "runtime",
        "records": records,
    }


def _normalize_locked_intent_status(status: str) -> str:
    if status in LOCKED_INTENT_LOCKED_STATUSES:
        return "locked"
    if status in LOCKED_INTENT_DISPUTED_STATUSES:
        return "disputed"
    if status in LOCKED_INTENT_REVIEW_STATUSES:
        return "review_pending"
    return "review_pending"


def _personal_hooks(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = _rows(
        connection,
        "personal_goals",
        """
        SELECT g.goal_id, g.player_id, g.act_id, g.public_text, g.progress_type,
               g.final_hook_id, h.role_category, h.evidence_category, h.summary_text
        FROM personal_goals g
        LEFT JOIN final_hooks h ON h.final_hook_id = g.final_hook_id
        ORDER BY g.player_id, g.goal_id
        """,
    )
    return [_personal_hook_payload(connection, row) for row in rows]


def _personal_hooks_for_player(
    connection: sqlite3.Connection, player_id: str
) -> list[dict[str, Any]]:
    return [hook for hook in _personal_hooks(connection) if hook["player_id"] == player_id]


def _personal_hook_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    tracks = [
        {
            **_clean_row(track),
            "current_value": _to_int(track["current_value"]),
            "target_value": _to_int(track["target_value"]),
        }
        for track in _rows(
            connection,
            "goal_tracks",
            """
            SELECT track_id, goal_id, state, current_value, target_value, visibility
            FROM goal_tracks
            WHERE goal_id = ?
            ORDER BY track_id
            """,
            (row["goal_id"],),
        )
    ]
    flags = [
        {
            "flag_id": flag["flag_id"],
            "goal_id": flag["goal_id"],
            "flag_key": flag["flag_key"],
            "value": flag["value"],
            "visibility": flag["visibility"],
        }
        for flag in _rows(
            connection,
            "goal_flags",
            """
            SELECT flag_id, goal_id, flag_key, value, visibility
            FROM goal_flags
            WHERE goal_id = ?
            ORDER BY flag_id
            """,
            (row["goal_id"],),
        )
    ]
    return {
        "goal_id": row["goal_id"],
        "player_id": row["player_id"],
        "act_id": row["act_id"],
        "public_text": row["public_text"],
        "progress_type": row["progress_type"],
        "final_hook_id": row["final_hook_id"],
        "role_category": row["role_category"],
        "evidence_category": row["evidence_category"],
        "summary_text": row["summary_text"],
        "tracks": tracks,
        "flags_master_only": [flag for flag in flags if flag["visibility"] == "master_only"],
        "public_flag_count": len([flag for flag in flags if flag["visibility"] != "master_only"]),
        "summary_policy": "evidence_only_no_auto_winner",
    }


def _final_procedures(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        {
            **_clean_row(row),
            "start_offset_min": _to_int(row["start_offset_min"]),
            "end_offset_min": _to_int(row["end_offset_min"]),
            "station_count": _to_int(row["station_count"]),
        }
        for row in _rows(
            connection,
            "final_procedures",
            """
            SELECT procedure_id, final_act_window, start_offset_min, end_offset_min,
                   station_count, master_role
            FROM final_procedures
            ORDER BY start_offset_min, procedure_id
            """,
        )
    ]


def _staffing(connection: sqlite3.Connection) -> dict[str, Any]:
    procedures = _final_procedures(connection)
    stations = [
        {
            "procedure_id": procedure["procedure_id"],
            "owner_role": procedure["master_role"],
            "station_count": procedure["station_count"],
            "covered": bool(procedure["master_role"]) and int(procedure["station_count"]) > 0,
        }
        for procedure in procedures
    ]
    return {
        "stations": stations,
        "total_station_count": sum(int(item["station_count"]) for item in stations),
        "unmanned_station_count": sum(1 for item in stations if not item["covered"]),
        "owner_roles": sorted({str(item["owner_role"]) for item in stations if item["owner_role"]}),
    }


def _master_final_notes(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows_as_dicts(
        connection,
        "final_master_notes",
        """
        SELECT note_id, category, target_id, note_text, visibility,
               operator, source, created_at
        FROM final_master_notes
        ORDER BY created_at, note_id
        """,
    )


def _master_note_by_id(connection: sqlite3.Connection, note_id: str) -> dict[str, Any]:
    row = _first_row(
        connection,
        "final_master_notes",
        """
        SELECT note_id, category, target_id, note_text, visibility,
               operator, source, created_at
        FROM final_master_notes
        WHERE note_id = ?
        """,
        (note_id,),
    )
    if row is None:
        raise ValueError(f"Missing final master note: {note_id}")
    return _clean_row(row)


def _missing_locks(
    connection: sqlite3.Connection,
    fields: list[dict[str, Any]],
    *,
    evidence_by_role: dict[str, Any],
    pending_disputes: list[dict[str, Any]],
    paper_recovery: list[dict[str, Any]],
    locked_intents: list[dict[str, Any]],
    personal_hooks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    present = {
        "territory": any(lord["territories"] for lord in evidence_by_role["lords"]),
        "battle": _table_count(connection, "lord_battles") > 0,
        "order": _table_count(connection, "order_runtime_state") > 0,
        "pve_contract": _table_count(connection, "pve_attempts") > 0,
        "pvp_gwent": _table_count(connection, "gwent_runtime_matches") > 0
        or _table_count(connection, "gwent_matches") > 0,
        "trade_locks": _table_count(connection, "trade_transfer_runtime") > 0,
        "favorite": _table_count(connection, "favorite_runtime") > 0,
        "locked_magical_intent": bool(locked_intents)
        and all(item["status"] == "locked" for item in locked_intents),
        "npc_price": _table_count(connection, "npc_deals") > 0,
        "paper_recovered": bool(paper_recovery),
        "personal_hooks": bool(personal_hooks),
    }
    missing = []
    for field in fields:
        category = str(field["evidence_category"])
        if not field["required_for_export"]:
            continue
        if category == "locked_magical_intent":
            missing.extend(_missing_magical_intent_locks(field, locked_intents))
            continue
        if present.get(category, False):
            continue
        missing.append(
            {
                "field_id": field["field_id"],
                "evidence_category": category,
                "source_type": field["source_type"],
                "reason": "required final evidence is not locked or captured",
                "required_for_export": True,
            }
        )
    for dispute in pending_disputes:
        if str(dispute.get("severity", "P3")) in {"P0", "P1"}:
            missing.append(
                {
                    "field_id": None,
                    "evidence_category": "unresolved_review",
                    "source_type": dispute.get("source_type"),
                    "reason": dispute.get("reason") or "unresolved P0/P1 final dispute",
                    "required_for_export": True,
                    "record_id": dispute.get("record_id") or dispute.get("event_id"),
                    "severity": dispute.get("severity"),
                }
            )
    return missing


def _missing_magical_intent_locks(
    field: dict[str, Any], locked_intents: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    missing = []
    for item in locked_intents:
        if item["status"] == "locked":
            continue
        status = str(item["status"])
        reason = {
            "missing": "required magical intent lock is missing",
            "review_pending": "magical intent lock is pending master review",
            "disputed": "magical intent lock is disputed",
        }.get(status, "magical intent lock is not finalized")
        missing.append(
            {
                "field_id": field["field_id"],
                "evidence_category": "locked_magical_intent",
                "source_type": field["source_type"],
                "reason": reason,
                "required_for_export": True,
                "sorceress_id": item["sorceress_id"],
                "sorceress_display_name": item.get("sorceress_display_name"),
                "status": status,
                "record_id": item.get("intent_id"),
                "runtime_status": item.get("runtime_status"),
            }
        )
    return missing


def _player_visible_categories(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    categories = sorted({str(field["evidence_category"]) for field in fields})
    return [
        {
            "evidence_category": category,
            "visibility": "category_only",
            "hidden_goal_flags": "master_only",
        }
        for category in categories
    ]


def _players(connection: sqlite3.Connection, role_type: str) -> list[sqlite3.Row]:
    if not _table_exists(connection, "players"):
        return []
    return connection.execute(
        """
        SELECT p.player_id, p.role_type, p.display_name, p.lord_id,
               p.sorceress_start_lord_id, p.level, p.xp, p.gold,
               p.reputation, p.stats_json,
               r.level AS runtime_level, r.xp AS runtime_xp,
               r.gold AS runtime_gold, r.stats_json AS runtime_stats_json,
               r.mana, r.max_mana, r.challenge_tokens
        FROM players p
        LEFT JOIN player_runtime_state r ON r.player_id = p.player_id
        WHERE p.role_type = ?
        ORDER BY p.player_id
        """,
        (role_type,),
    ).fetchall()


def _player_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    runtime_stats = row["runtime_stats_json"] if "runtime_stats_json" in row.keys() else None
    return {
        "player_id": row["player_id"],
        "role_type": row["role_type"],
        "display_name": row["display_name"],
        "lord_id": row["lord_id"],
        "sorceress_start_lord_id": row["sorceress_start_lord_id"],
        "level": _to_int(row["runtime_level"] or row["level"]),
        "xp": _to_int(row["runtime_xp"] or row["xp"]),
        "gold": _to_int(row["runtime_gold"] or row["gold"]),
        "stats": _json_loads(runtime_stats or row["stats_json"], {}),
        "mana": _to_int(row["mana"]) if "mana" in row.keys() else 0,
        "max_mana": _to_int(row["max_mana"]) if "max_mana" in row.keys() else 0,
        "challenge_tokens": _to_int(row["challenge_tokens"]) if "challenge_tokens" in row.keys() else 0,
        "reputation": _reputation(connection, str(row["player_id"]))
        if str(row["role_type"]) in {"witcher", "sorceress"}
        else None,
    }


def _reputation(connection: sqlite3.Connection, player_id: str) -> dict[str, Any] | None:
    try:
        return get_reputation_view(connection, player_id, visibility="master")
    except (ReputationError, sqlite3.OperationalError):
        return None


def _territories_for_domain(
    connection: sqlite3.Connection, domain_id: str | None
) -> list[dict[str, Any]]:
    if not domain_id:
        return []
    return _rows_as_dicts(
        connection,
        "territory_runtime_state",
        """
        SELECT t.territory_id, t.owner_domain_id, t.status, t.contested_by_domain_id,
               t.controlled_since, t.updated_at,
               seed.name, seed.bonus_type, seed.tier
        FROM territory_runtime_state t
        LEFT JOIN territories seed ON seed.territory_id = t.territory_id
        WHERE t.owner_domain_id = ? OR t.contested_by_domain_id = ?
        ORDER BY t.territory_id
        """,
        (domain_id, domain_id),
    )


def _orders_for_lord(connection: sqlite3.Connection, lord_id: str) -> list[dict[str, Any]]:
    return _rows_as_dicts(
        connection,
        "order_runtime_state",
        """
        SELECT *
        FROM order_runtime_state
        WHERE lord_id = ?
        ORDER BY created_at, order_id
        """,
        (lord_id,),
    )


def _orders_for_player(connection: sqlite3.Connection, player_id: str) -> list[dict[str, Any]]:
    return _rows_as_dicts(
        connection,
        "order_runtime_state",
        """
        SELECT *
        FROM order_runtime_state
        WHERE target_player_id = ?
           OR accepted_by_player_id = ?
           OR submitted_by_player_id = ?
        ORDER BY created_at, order_id
        """,
        (player_id, player_id, player_id),
    )


def _lord_battles_for_domain(
    connection: sqlite3.Connection, domain_id: str | None
) -> list[dict[str, Any]]:
    if not domain_id:
        return []
    rows = _rows(
        connection,
        "lord_battles",
        """
        SELECT *
        FROM lord_battles
        WHERE attacker_domain_id = ? OR defender_domain_id = ?
        ORDER BY created_at, battle_id
        """,
        (domain_id, domain_id),
    )
    return [_battle_payload(row) for row in rows]


def _battle_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = _clean_row(row)
    for key in (
        "timeout_counts_json",
        "board_json",
        "hero_hp_json",
        "deployment_json",
        "initiative_json",
        "burned_cards_json",
        "result_json",
    ):
        fallback: Any = [] if key in {"initiative_json", "burned_cards_json"} else {}
        payload[key.removesuffix("_json")] = _json_loads(str(payload.pop(key, "")), fallback)
    return payload


def _raid_effects_for_domain(
    connection: sqlite3.Connection, domain_id: str | None
) -> list[dict[str, Any]]:
    if not domain_id:
        return []
    return [
        {**_clean_row(row), "payload": _json_loads(row["payload_json"], {})}
        for row in _rows(
            connection,
            "raid_effects",
            """
            SELECT *
            FROM raid_effects
            WHERE source_domain_id = ? OR target_domain_id = ?
            ORDER BY starts_at_offset_min, raid_effect_id
            """,
            (domain_id, domain_id),
        )
    ]


def _pve_attempts_for_player(
    connection: sqlite3.Connection, player_id: str
) -> list[dict[str, Any]]:
    return [
        {
            **_clean_row(row),
            "roll_log": _json_loads(row["roll_log_json"], []),
            "payload": _json_loads(row["payload_json"], {}),
        }
        for row in _rows(
            connection,
            "pve_attempts",
            """
            SELECT *
            FROM pve_attempts
            WHERE player_id = ?
            ORDER BY created_at, pve_attempt_id
            """,
            (player_id,),
        )
    ]


def _pvp_for_player(connection: sqlite3.Connection, player_id: str) -> dict[str, Any]:
    challenges = _rows_as_dicts(
        connection,
        "pvp_challenges",
        """
        SELECT *
        FROM pvp_challenges
        WHERE challenger_id = ? OR target_id = ?
        ORDER BY created_at, challenge_id
        """,
        (player_id, player_id),
    )
    matches = [
        {
            **_clean_row(row),
            "deck_state": _json_loads(row["deck_state_json"], {}),
            "round_losses": _json_loads(row["round_losses_json"], {}),
            "balance_report": _json_loads(row["balance_report_json"], {}),
        }
        for row in _rows(
            connection,
            "gwent_runtime_matches",
            """
            SELECT *
            FROM gwent_runtime_matches
            WHERE challenger_id = ? OR target_id = ?
            ORDER BY created_at, match_id
            """,
            (player_id, player_id),
        )
    ]
    seed_matches = [
        {**_clean_row(row), "stake": _json_loads(row["stake_json"], {})}
        for row in _rows(
            connection,
            "gwent_matches",
            """
            SELECT *
            FROM gwent_matches
            WHERE challenger_id = ? OR target_id = ?
            ORDER BY _row_number
            """,
            (player_id, player_id),
        )
    ]
    stakes = _rows_as_dicts(
        connection,
        "pvp_stake_ledger",
        """
        SELECT *
        FROM pvp_stake_ledger
        WHERE owner_player_id = ?
           OR pending_target_player_id = ?
           OR winner_id = ?
           OR loser_id = ?
        ORDER BY created_at, stake_ledger_id
        """,
        (player_id, player_id, player_id, player_id),
    )
    return {"challenges": challenges, "matches": matches, "seed_matches": seed_matches, "stakes": stakes}


def _trade_transfers_for_player(
    connection: sqlite3.Connection, player_id: str
) -> list[dict[str, Any]]:
    return _rows_as_dicts(
        connection,
        "trade_transfer_runtime",
        """
        SELECT *
        FROM trade_transfer_runtime
        WHERE from_player_id = ? OR to_player_id = ?
        ORDER BY created_at, transfer_id
        """,
        (player_id, player_id),
    )


def _npc_deals_for_target(connection: sqlite3.Connection, target_id: str) -> list[dict[str, Any]]:
    return [
        deal
        for deal in list_npc_deals(connection, visibility="master")
        if target_id in deal.get("target_ids", [])
    ]


def _spell_casts_for_sorceress(
    connection: sqlite3.Connection, sorceress_id: str
) -> list[dict[str, Any]]:
    return [
        {**_clean_row(row), "effect": _json_loads(row["effect_json"], {})}
        for row in _rows(
            connection,
            "sorceress_spell_casts",
            """
            SELECT *
            FROM sorceress_spell_casts
            WHERE sorceress_id = ?
            ORDER BY created_at, cast_id
            """,
            (sorceress_id,),
        )
    ]


def _favorites_for_sorceress(
    connection: sqlite3.Connection, sorceress_id: str
) -> list[dict[str, Any]]:
    return _rows_as_dicts(
        connection,
        "favorite_runtime",
        """
        SELECT *
        FROM favorite_runtime
        WHERE sorceress_id = ?
        ORDER BY created_at, favorite_id
        """,
        (sorceress_id,),
    )


def _favorite_history_for_sorceress(
    connection: sqlite3.Connection, sorceress_id: str
) -> list[dict[str, Any]]:
    return _rows_as_dicts(
        connection,
        "favorite_history",
        """
        SELECT *
        FROM favorite_history
        WHERE sorceress_id = ?
        ORDER BY created_at, history_id
        """,
        (sorceress_id,),
    )


def _alignment_evidence_for_sorceress(
    connection: sqlite3.Connection, sorceress_id: str
) -> list[dict[str, Any]]:
    return [
        {
            **_clean_row(row),
            "payload": _json_loads(row["payload_json"], {}),
            "final_flag": bool(row["final_flag"]),
        }
        for row in _rows(
            connection,
            "sorceress_alignment_evidence",
            """
            SELECT *
            FROM sorceress_alignment_evidence
            WHERE sorceress_id = ?
            ORDER BY created_at, evidence_id
            """,
            (sorceress_id,),
        )
    ]


def _table_count(connection: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(connection, table_name):
        return 0
    row = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(row[0])


def _rows_as_dicts(
    connection: sqlite3.Connection,
    table_name: str,
    sql: str,
    params: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    return [_clean_row(row) for row in _rows(connection, table_name, sql, params)]


def _rows(
    connection: sqlite3.Connection,
    table_name: str,
    sql: str,
    params: tuple[Any, ...] = (),
) -> list[sqlite3.Row]:
    if not _table_exists(connection, table_name):
        return []
    return connection.execute(sql, params).fetchall()


def _first_row(
    connection: sqlite3.Connection,
    table_name: str,
    sql: str,
    params: tuple[Any, ...] = (),
) -> sqlite3.Row | None:
    rows = _rows(connection, table_name, sql, params)
    return rows[0] if rows else None


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


def _clean_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def _json_loads(value: object, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback


def _truthy(value: object) -> bool:
    return str(value).strip().lower() == "true"


def _to_int(value: object) -> int:
    if value in (None, ""):
        return 0
    return int(value)


def _severity_rank(severity: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(severity, 99)


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")
