"""Master game-ops state and audited correction helpers."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import sqlite3
from typing import Any
from uuid import uuid4

from .act_service import get_act_state
from .asset_service import active_reward_approvals, ensure_asset_contract_schema
from .config import Settings
from .event_schema import ensure_event_schema
from .lord_runtime import (
    ACTIVE_ORDER_STATUSES,
    anti_snowball_cut_for_domain,
    ensure_lord_runtime_state,
)
from .pvp_service import get_pvp_tables
from .repository import fetch_table, latest_snapshot_version, quote_identifier
from .runtime_schema import ensure_runtime_schema, log_event
from .sorceress_service import ensure_sorceress_runtime_state


FINAL_REVIEW_STATUSES = {"approved", "rejected", "corrected"}
FINAL_REWARD_STATUSES = {"approved", "rejected", "corrected"}

DISPLAY_NAME_OVERRIDES = {
    "North Watch": "Северный Дозор",
    "River Gate": "Речные Врата",
    "Forest March": "Лесной Марш",
    "Hill Crown": "Холмовая Корона",
    "Lord Aedirn": "Лорд Аэдирна",
    "Lord Temeria": "Лорд Темерии",
    "Lord Redania": "Лорд Редании",
    "Lord Skellige": "Лорд Скеллиге",
    "Yennefer Circle": "Чародейка Йеннифэр",
    "Triss Circle": "Чародейка Трисс",
    "Philippa Circle": "Чародейка Филиппа",
    "Fringilla Circle": "Чародейка Фрингилья",
    "Witcher Wolf": "Ведьмак Волк",
    "Witcher Cat": "Ведьмак Кот",
    "Witcher Griffin": "Ведьмак Грифон",
    "Witcher Bear": "Ведьмак Медведь",
    "Witcher Viper": "Ведьмак Змея",
}


class GameOpsCorrectionError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        code: str = "game_ops_correction_error",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


CORRECTION_TARGETS: dict[str, dict[str, object]] = {
    "territory": {
        "table": "territory_runtime_state",
        "pk": "territory_id",
        "allowed": {"owner_domain_id", "status", "contested_by_domain_id"},
    },
    "domain": {
        "table": "domain_runtime_state",
        "pk": "domain_id",
        "allowed": {
            "gold",
            "current_mp",
            "mp_cap",
            "active_army_capacity",
            "raid_tokens",
            "influence",
            "current_node_id",
        },
        "ints": {
            "gold",
            "current_mp",
            "mp_cap",
            "active_army_capacity",
            "raid_tokens",
            "influence",
        },
    },
    "player": {
        "table": "player_runtime_state",
        "pk": "player_id",
        "allowed": {
            "level",
            "xp",
            "gold",
            "stats_json",
            "unspent_stat_points",
            "mana",
            "max_mana",
            "challenge_tokens",
        },
        "ints": {"level", "xp", "gold", "unspent_stat_points", "mana", "max_mana", "challenge_tokens"},
        "json": {"stats_json"},
    },
    "personal_goal": {
        "table": "personal_goals",
        "pk": "goal_id",
        "allowed": {"public_text"},
    },
    "garrison": {
        "table": "garrison_runtime_state",
        "pk": "garrison_id",
        "allowed": {"territory_id", "domain_id", "card_id", "count", "status"},
        "ints": {"count"},
    },
    "pending_reward": {
        "table": "pending_tick_reward_runtime",
        "pk": "pending_reward_id",
        "allowed": {"domain_id", "reward_gold", "status", "awarded_to_domain_id"},
        "ints": {"reward_gold"},
    },
    "recruit_offer": {
        "table": "recruit_offer_runtime",
        "pk": "offer_id",
        "allowed": {"domain_id", "card_id", "cost", "status", "held_by_domain_id"},
        "ints": {"cost"},
    },
    "reserve": {
        "table": "army_reserve_runtime",
        "pk": "reserve_id",
        "allowed": {"domain_id", "card_id", "count", "status"},
        "ints": {"count"},
    },
    "raid": {
        "table": "raid_effects",
        "pk": "raid_effect_id",
        "allowed": {
            "rule_id",
            "source_domain_id",
            "target_domain_id",
            "target_territory_id",
            "status",
            "starts_at_offset_min",
            "ends_at_offset_min",
            "payload_json",
        },
        "ints": {"starts_at_offset_min", "ends_at_offset_min"},
        "json": {"payload_json"},
    },
    "pvp_challenge": {
        "table": "pvp_challenges",
        "pk": "challenge_id",
        "allowed": {"status", "table_id", "assigned_zone", "refusal_reason", "review_reason"},
    },
    "pvp_match": {
        "table": "gwent_runtime_matches",
        "pk": "match_id",
        "allowed": {"status", "winner_id", "review_reason", "duration_seconds"},
        "ints": {"duration_seconds"},
    },
    "pvp_review": {
        "table": "pvp_reviews",
        "pk": "review_id",
        "allowed": {"status", "severity", "reason"},
    },
    "potion_market": {
        "table": "potion_market_runtime",
        "pk": "market_id",
        "allowed": {"stock", "refresh_rule"},
        "ints": {"stock"},
    },
    "potion_inventory": {
        "table": "potion_inventory",
        "pk": "inventory_id",
        "allowed": {"player_id", "potion_id", "quantity"},
        "ints": {"quantity"},
    },
    "trade_transfer": {
        "table": "trade_transfer_runtime",
        "pk": "transfer_id",
        "allowed": {
            "from_player_id",
            "to_player_id",
            "asset_type",
            "asset_id",
            "quantity",
            "price_gold",
            "mode",
            "status",
            "accepted_at",
        },
        "ints": {"quantity", "price_gold"},
    },
}


def build_master_state(
    connection: sqlite3.Connection, settings: Settings
) -> dict[str, Any]:
    """Return the single read payload used by the browser game-ops dashboard."""

    _ensure_game_ops_schema(connection)
    ensure_event_schema(connection)
    ensure_asset_contract_schema(connection)
    ensure_lord_runtime_state(connection)
    ensure_sorceress_runtime_state(connection)
    acts = get_act_state(connection, settings)
    pvp = get_pvp_tables(connection)
    review = _review_state(connection)
    rewards = _reward_approval_state(connection)
    backups = backup_status(connection)
    return {
        "snapshot_version": latest_snapshot_version(connection),
        "acts": acts,
        "timers": acts.get("timers", {}),
        "events": {
            "review": review,
            "recent": _recent_events(connection),
            "sync_statuses": _sync_statuses(connection),
        },
        "reward_approvals": rewards,
        "lord_map": _lord_map_state(connection),
        "visibility_audit": build_visibility_audit(connection),
        "pvp": {
            **pvp,
            "reviews": _pvp_reviews(connection),
        },
        "economy": _economy_recovery_state(connection),
        "backups": backups,
        "corrections": _recent_game_ops_corrections(connection),
        "blocking_alerts": [
            *review["blocking_alerts"],
            *rewards["blocking_alerts"],
            *backups["blocking_alerts"],
        ],
    }


def list_master_player_codes(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = _rows(
        connection,
        """
        SELECT
            pc.code_id,
            pc.player_id,
            pc.code,
            pc.enabled,
            p.role_type,
            p.display_name
        FROM player_codes pc
        JOIN players p ON p.player_id = pc.player_id
        ORDER BY
            CASE p.role_type
                WHEN 'lord' THEN 1
                WHEN 'sorceress' THEN 2
                WHEN 'witcher' THEN 3
                ELSE 4
            END,
            pc.player_id
        """,
        table_name="player_codes",
    )
    items = [
        {
            **row,
            "display_name": _display_name(row.get("display_name"), fallback=row.get("player_id")),
            "enabled": _to_bool(row.get("enabled")),
        }
        for row in rows
    ]
    return {
        "items": items,
        "total": len(items),
        "enabled_count": sum(1 for item in items if item["enabled"]),
    }


def backup_status(connection: sqlite3.Connection) -> dict[str, Any]:
    _ensure_game_ops_schema(connection)
    rows = _rows(
        connection,
        """
        SELECT *
        FROM backup_runs
        ORDER BY started_at DESC, backup_id DESC
        LIMIT 12
        """,
        table_name="backup_runs",
    )
    failed = [row for row in rows if row.get("status") == "failed"]
    needs_review = [row for row in rows if _to_bool(row.get("needs_master_review"))]
    return {
        "configured_jobs": _count(connection, "backup_jobs"),
        "run_count": _count(connection, "backup_runs"),
        "last_run": rows[0] if rows else None,
        "runs": rows,
        "blocking_alerts": [
            {
                "source": "backup",
                "severity": "P1",
                "message": f"Backup failed: {row.get('backup_id')}",
                "record_id": row.get("backup_id"),
            }
            for row in failed
        ]
        + [
            {
                "source": "backup",
                "severity": "P1",
                "message": f"Backup needs master review: {row.get('backup_id')}",
                "record_id": row.get("backup_id"),
            }
            for row in needs_review
            if row not in failed
        ],
    }


def build_visibility_audit(connection: sqlite3.Connection) -> dict[str, Any]:
    """Return the master-only visibility audit used by Admin Studio."""

    _ensure_game_ops_schema(connection)
    ensure_asset_contract_schema(connection)
    ensure_lord_runtime_state(connection)
    domain_ids = _domain_ids(connection)
    hidden_garrisons = _hidden_garrison_audit(connection, domain_ids)
    raid_effects = _raid_effect_visibility_audit(connection, domain_ids)
    artifacts = _artifact_visibility_audit(connection)
    return {
        "scope": "master",
        "policy": {
            "master_exact_values": True,
            "lord_garrisons_redacted_to_foreign_presence": True,
            "raid_effects_visible_to_source_target_and_masters": True,
            "artifact_visibility_uses_seed_policy_and_reveal_events": True,
        },
        "summary": {
            "hidden_garrisons": len(hidden_garrisons),
            "raid_effects": len(raid_effects),
            "artifacts": len(artifacts),
            "master_only_artifacts": sum(
                1 for item in artifacts if item.get("player_visibility") == "hidden_from_players"
            ),
            "revealed_artifacts": sum(1 for item in artifacts if item.get("revealed")),
        },
        "hidden_garrisons": hidden_garrisons,
        "raid_effects": raid_effects,
        "artifacts": artifacts,
        "lord_view_boundaries": [
            {
                "domain_id": domain_id,
                "exact_own_garrisons": True,
                "foreign_garrisons": "hidden_foreign_garrison",
                "raid_effects": "source_target_only",
                "artifact_numbers": "not_in_lord_panel",
            }
            for domain_id in domain_ids
        ],
    }


def apply_game_ops_correction(
    connection: sqlite3.Connection,
    *,
    target_type: str,
    target_id: str,
    patch: dict[str, Any],
    operator: str,
    reason: str,
    source: str = "master_api",
) -> dict[str, Any]:
    _ensure_game_ops_schema(connection)
    ensure_lord_runtime_state(connection)
    ensure_sorceress_runtime_state(connection)
    target_type = _normalize_target_type(target_type)
    target_id = str(target_id or "").strip()
    operator = str(operator or "").strip()
    reason = str(reason or "").strip()
    source = str(source or "").strip() or "master_api"
    if not target_id:
        raise GameOpsCorrectionError("Correction target_id is required.", code="missing_target_id")
    if not operator:
        raise GameOpsCorrectionError("Correction operator is required.", code="missing_operator")
    if not reason:
        raise GameOpsCorrectionError("Correction reason is required.", code="missing_reason")
    if not isinstance(patch, dict) or not patch:
        raise GameOpsCorrectionError("Correction patch must be a non-empty object.", code="missing_patch")

    if target_type == "domain_building":
        return _apply_building_correction(
            connection,
            target_id=target_id,
            patch=patch,
            operator=operator,
            reason=reason,
            source=source,
        )
    return _apply_table_correction(
        connection,
        target_type=target_type,
        target_id=target_id,
        patch=patch,
        operator=operator,
        reason=reason,
        source=source,
    )


def _apply_table_correction(
    connection: sqlite3.Connection,
    *,
    target_type: str,
    target_id: str,
    patch: dict[str, Any],
    operator: str,
    reason: str,
    source: str,
) -> dict[str, Any]:
    spec = CORRECTION_TARGETS.get(target_type)
    if spec is None:
        raise GameOpsCorrectionError(
            f"Unsupported correction target_type: {target_type}.",
            code="unsupported_target_type",
        )
    table_name = str(spec["table"])
    pk = str(spec["pk"])
    allowed = set(spec.get("allowed", set()))
    int_fields = set(spec.get("ints", set()))
    json_fields = set(spec.get("json", set()))
    existing_columns = _table_columns(connection, table_name)
    effective_allowed = allowed & existing_columns
    rejected = sorted(set(patch) - effective_allowed)
    if rejected:
        raise GameOpsCorrectionError(
            f"Unsupported correction field(s): {', '.join(rejected)}.",
            code="unsupported_patch_field",
        )

    before = _fetch_by_pk(connection, table_name, pk, target_id)
    if before is None:
        raise GameOpsCorrectionError(
            f"Unknown {target_type} correction target: {target_id}.",
            status_code=404,
            code="correction_target_not_found",
        )

    normalized_patch = {
        field: _normalize_patch_value(field, value, int_fields, json_fields)
        for field, value in patch.items()
    }
    if not normalized_patch:
        raise GameOpsCorrectionError("Correction patch changed no fields.", code="empty_patch")

    now = _iso()
    assignments = ", ".join(f"{quote_identifier(field)} = ?" for field in normalized_patch)
    if "updated_at" in existing_columns:
        assignments = f"{assignments}, updated_at = ?"
    params: list[Any] = list(normalized_patch.values())
    if "updated_at" in existing_columns:
        params.append(now)
    params.append(target_id)
    connection.execute(
        f"""
        UPDATE {quote_identifier(table_name)}
        SET {assignments}
        WHERE {quote_identifier(pk)} = ?
        """,
        tuple(params),
    )
    after = _fetch_by_pk(connection, table_name, pk, target_id) or {}
    return _record_correction(
        connection,
        target_type=target_type,
        target_id=target_id,
        operator=operator,
        reason=reason,
        patch=normalized_patch,
        before=before,
        after=after,
        source=source,
        created_at=now,
    )


def _apply_building_correction(
    connection: sqlite3.Connection,
    *,
    target_id: str,
    patch: dict[str, Any],
    operator: str,
    reason: str,
    source: str,
) -> dict[str, Any]:
    domain_id = str(patch.get("domain_id") or "").strip()
    territory_id = str(patch.get("territory_id") or "").strip()
    building_id = str(patch.get("building_id") or "").strip()
    if not domain_id or not building_id:
        if ":" in target_id:
            parts = [part.strip() for part in target_id.split(":")]
            if len(parts) >= 3:
                domain_id, territory_id, building_id = parts[:3]
            elif len(parts) == 2:
                domain_id, building_id = parts
    action = str(patch.get("action") or "grant").strip().lower()
    if not domain_id or not building_id:
        raise GameOpsCorrectionError(
            "Domain building correction requires domain_id and building_id.",
            code="missing_building_target",
        )
    if action not in {"grant", "remove"}:
        raise GameOpsCorrectionError(
            "Domain building correction action must be grant or remove.",
            code="unsupported_building_action",
        )

    territory_id = territory_id or _domain_residence_territory(connection, domain_id) or ""
    before = _fetch_domain_building(connection, domain_id, building_id, territory_id)
    now = _iso()
    if action == "grant":
        connection.execute(
            """
            INSERT INTO domain_buildings (
                domain_id, territory_id, building_id, purchased_at, source
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(domain_id, territory_id, building_id) DO UPDATE SET
                purchased_at = excluded.purchased_at,
                source = excluded.source
            """,
            (domain_id, territory_id, building_id, now, source),
        )
    else:
        connection.execute(
            """
            DELETE FROM domain_buildings
            WHERE domain_id = ? AND territory_id = ? AND building_id = ?
            """,
            (domain_id, territory_id, building_id),
        )
    after = _fetch_domain_building(connection, domain_id, building_id, territory_id)
    return _record_correction(
        connection,
        target_type="domain_building",
        target_id=f"{domain_id}:{territory_id}:{building_id}",
        operator=operator,
        reason=reason,
        patch={
            "action": action,
            "domain_id": domain_id,
            "territory_id": territory_id,
            "building_id": building_id,
        },
        before=before or {},
        after=after or {},
        source=source,
        created_at=now,
    )


def _review_state(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = _rows(
        connection,
        """
        SELECT er.review_id, er.server_event_id, er.event_id, er.status,
               er.reason, er.severity, er.created_at, er.decision,
               er.decision_reason, er.decided_by, er.decided_at,
               er.correction_id, e.event_type, e.actor_id, e.actor_type
        FROM event_reviews er
        LEFT JOIN events e ON e.server_event_id = er.server_event_id
        ORDER BY
            CASE er.severity
                WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3
            END,
            er.created_at,
            er.review_id
        """,
        table_name="event_reviews",
    )
    open_items = [row for row in rows if str(row.get("status")) not in FINAL_REVIEW_STATUSES]
    critical = [
        row for row in open_items if str(row.get("severity", "")).upper() in {"P0", "P1"}
    ]
    return {
        "items": rows,
        "open_items": open_items,
        "open_count": len(open_items),
        "critical_open_count": len(critical),
        "blocking_alerts": [
            {
                "source": "review",
                "severity": row.get("severity") or "P1",
                "message": f"Open {row.get('severity')} review: {row.get('event_id')}",
                "record_id": row.get("event_id"),
            }
            for row in critical
        ],
    }


def _reward_approval_state(connection: sqlite3.Connection) -> dict[str, Any]:
    active = [_decorate_reward_approval(row) for row in active_reward_approvals(connection)]
    recent = [
        _decorate_reward_approval(row)
        for row in _rows(
            connection,
            """
            SELECT *
            FROM reward_approvals
            ORDER BY created_at DESC, approval_id
            LIMIT 20
            """,
            table_name="reward_approvals",
        )
    ]
    pending = [row for row in recent if str(row.get("status")) not in FINAL_REWARD_STATUSES]
    return {
        "pending": active,
        "recent": recent,
        "pending_count": len(active),
        "blocking_alerts": [
            {
                "source": "reward_approval",
                "severity": row["severity"],
                "message": f"Pending reward approval: {row.get('approval_id')}",
                "record_id": row.get("approval_id"),
            }
            for row in pending
            if row["severity"] in {"P0", "P1"}
        ],
    }


def _decorate_reward_approval(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("status") or "")
    severity = "P1" if status == "pending_master_approval" else "P3"
    return {**row, "severity": severity}


def _lord_map_state(connection: sqlite3.Connection) -> dict[str, Any]:
    domains = []
    domain_rows = _table(connection, "domains")
    runtime_domains = {
        row["domain_id"]: row
        for row in _rows(
            connection,
            "SELECT * FROM domain_runtime_state ORDER BY domain_id",
            table_name="domain_runtime_state",
        )
    }
    map_node_rows = _table(connection, "map_nodes")
    map_nodes_by_id = _group_first(map_node_rows, "node_id")
    map_nodes_by_territory = _group_first(map_node_rows, "territory_id")
    garrison_rows = _rows(
        connection,
        "SELECT * FROM garrison_runtime_state ORDER BY territory_id, domain_id, garrison_id",
        table_name="garrison_runtime_state",
    )
    garrisons_by_domain = _group_by(garrison_rows, "domain_id")
    garrisons_by_territory = _group_by(garrison_rows, "territory_id")
    orders_by_domain = _group_by(_lord_order_rows(connection), "domain_id")
    pending_moves_by_domain = _group_by(
        _rows(
            connection,
            """
            SELECT *
            FROM pending_lord_moves
            WHERE status NOT IN ('completed', 'cancelled', 'failed')
            ORDER BY started_at, move_id
            """,
            table_name="pending_lord_moves",
        ),
        "domain_id",
    )
    for domain in domain_rows:
        domain_id = str(domain.get("domain_id") or "")
        payload = {**domain, **runtime_domains.get(domain_id, {})}
        current_node_id = str(payload.get("current_node_id") or "")
        orders = orders_by_domain.get(domain_id, [])
        payload["display_name"] = _display_name(payload.get("name"), fallback=domain_id)
        payload["current_node"] = map_nodes_by_id.get(current_node_id)
        payload["buildings"] = _buildings_for_domain(connection, domain_id)
        payload["garrisons"] = garrisons_by_domain.get(domain_id, [])
        payload["recruit_offers"] = _rows(
            connection,
            """
            SELECT *
            FROM recruit_offer_runtime
            WHERE domain_id = ?
            ORDER BY offer_id
            """,
            (domain_id,),
            table_name="recruit_offer_runtime",
        )
        payload["reserve"] = _rows(
            connection,
            """
            SELECT *
            FROM army_reserve_runtime
            WHERE domain_id = ?
            ORDER BY reserve_id
            """,
            (domain_id,),
            table_name="army_reserve_runtime",
        )
        payload["active_army"] = _rows(
            connection,
            """
            SELECT *
            FROM active_army_runtime
            WHERE domain_id = ?
            ORDER BY army_id
            """,
            (domain_id,),
            table_name="active_army_runtime",
        )
        payload["orders"] = orders
        payload["active_order_count"] = sum(
            1 for row in orders if str(row.get("status") or "") in ACTIVE_ORDER_STATUSES
        )
        payload["pending_moves"] = pending_moves_by_domain.get(domain_id, [])
        payload["anti_snowball"] = anti_snowball_cut_for_domain(connection, domain_id)
        domains.append(payload)

    territory_rows = _table(connection, "territories")
    runtime_territories = {
        row["territory_id"]: row
        for row in _rows(
            connection,
            "SELECT * FROM territory_runtime_state ORDER BY territory_id",
            table_name="territory_runtime_state",
        )
    }
    pending_rewards = _group_by(
        _rows(
            connection,
            """
            SELECT *
            FROM pending_tick_reward_runtime
            ORDER BY due_at, pending_reward_id
            """,
            table_name="pending_tick_reward_runtime",
        ),
        "territory_id",
    )
    territories = []
    for territory in territory_rows:
        territory_id = str(territory.get("territory_id") or "")
        runtime = runtime_territories.get(territory_id, {})
        node = map_nodes_by_territory.get(territory_id, {})
        territories.append(
            {
                **territory,
                **runtime,
                "node_id": node.get("node_id"),
                "node_name": node.get("name"),
                "node_type": node.get("node_type"),
                "garrisons": garrisons_by_territory.get(territory_id, []),
                "pending_rewards": pending_rewards.get(territory_id, []),
            }
        )

    return {
        "domains": domains,
        "territories": territories,
        "contested_claims": _rows(
            connection,
            """
            SELECT *
            FROM territory_claim_runtime
            WHERE status NOT IN ('controlled', 'resolved', 'cancelled')
            ORDER BY created_at, claim_id
            """,
            table_name="territory_claim_runtime",
        ),
        "raid_effects": _rows(
            connection,
            "SELECT * FROM raid_effects ORDER BY raid_effect_id",
            table_name="raid_effects",
        ),
    }


def _lord_order_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = _rows(
        connection,
        """
        SELECT o.*, d.domain_id
        FROM order_runtime_state o
        LEFT JOIN domains d ON d.lord_player_id = o.lord_id
        ORDER BY o.updated_at DESC, o.order_id
        """,
        table_name="order_runtime_state",
    )
    return [row for row in rows if row.get("domain_id")]


def _economy_recovery_state(connection: sqlite3.Connection) -> dict[str, Any]:
    markets = _rows(
        connection,
        """
        SELECT market_id, seller_role, potion_id, stock, refresh_rule, updated_at
        FROM potion_market_runtime
        ORDER BY market_id
        """,
        table_name="potion_market_runtime",
    )
    inventory = _rows(
        connection,
        """
        SELECT inventory_id, player_id, potion_id, quantity, updated_at
        FROM potion_inventory
        ORDER BY player_id, potion_id
        LIMIT 40
        """,
        table_name="potion_inventory",
    )
    transfers = _rows(
        connection,
        """
        SELECT transfer_id, from_player_id, to_player_id, asset_type, asset_id,
               quantity, price_gold, mode, status, accepted_at, source,
               created_at, updated_at
        FROM trade_transfer_runtime
        ORDER BY updated_at DESC, transfer_id
        LIMIT 40
        """,
        table_name="trade_transfer_runtime",
    )
    players = _rows(
        connection,
        """
        SELECT runtime.player_id, players.display_name, runtime.role_type,
               runtime.level, runtime.gold, runtime.xp, runtime.mana,
               runtime.max_mana, runtime.challenge_tokens, runtime.updated_at
        FROM player_runtime_state runtime
        LEFT JOIN players ON players.player_id = runtime.player_id
        ORDER BY runtime.player_id
        """,
        table_name="player_runtime_state",
    )
    personal_goals = _rows(
        connection,
        """
        SELECT goals.goal_id, goals.player_id, goals.act_id, goals.public_text,
               goals.progress_type, goals.final_hook_id,
               tracks.track_id, tracks.state AS track_state,
               tracks.current_value, tracks.target_value, tracks.visibility
        FROM personal_goals goals
        LEFT JOIN goal_tracks tracks ON tracks.goal_id = goals.goal_id
        ORDER BY goals.player_id, goals.act_id, goals.goal_id
        """,
        table_name="personal_goals",
    )
    for player in players:
        player["display_name"] = _display_name(
            player.get("display_name"),
            fallback=player.get("player_id"),
        )
    return {
        "potion_markets": markets,
        "potion_inventory": inventory,
        "trade_transfers": transfers,
        "player_economy": players,
        "personal_goals": personal_goals,
        "summary": {
            "potion_markets": len(markets),
            "potion_inventory_rows": len(inventory),
            "trade_transfers": len(transfers),
            "pending_trade_transfers": sum(
                1 for row in transfers if str(row.get("status")) == "pending_locked"
            ),
            "player_rows": len(players),
        },
    }


def _domain_ids(connection: sqlite3.Connection) -> list[str]:
    ids = {
        str(row.get("domain_id") or "")
        for row in _table(connection, "domains")
        if row.get("domain_id")
    }
    ids.update(
        str(row.get("domain_id") or "")
        for row in _rows(
            connection,
            "SELECT domain_id FROM domain_runtime_state ORDER BY domain_id",
            table_name="domain_runtime_state",
        )
        if row.get("domain_id")
    )
    return sorted(ids)


def _display_name(value: object, *, fallback: object = "") -> str:
    name = str(value or "").strip()
    if not name:
        name = str(fallback or "").strip()
    return DISPLAY_NAME_OVERRIDES.get(name, name)


def _hidden_garrison_audit(
    connection: sqlite3.Connection, domain_ids: list[str]
) -> list[dict[str, Any]]:
    rows = _rows(
        connection,
        """
        SELECT garrison_id, territory_id, domain_id, card_id, count, status, updated_at
        FROM garrison_runtime_state
        WHERE status = 'active' AND count > 0
        ORDER BY territory_id, domain_id, garrison_id
        """,
        table_name="garrison_runtime_state",
    )
    return [
        {
            **row,
            "count": _to_int(row.get("count")),
            "master_exact": True,
            "lord_exact_domain_ids": [row["domain_id"]],
            "redacted_for_domain_ids": [
                domain_id for domain_id in domain_ids if domain_id != row.get("domain_id")
            ],
            "lord_redaction": "hidden_foreign_garrison",
        }
        for row in rows
    ]


def _raid_effect_visibility_audit(
    connection: sqlite3.Connection, domain_ids: list[str]
) -> list[dict[str, Any]]:
    rows = _rows(
        connection,
        """
        SELECT *
        FROM raid_effects
        ORDER BY raid_effect_id
        """,
        table_name="raid_effects",
    )
    result = []
    for row in rows:
        visible_to = sorted(
            {
                str(row.get("source_domain_id") or ""),
                str(row.get("target_domain_id") or ""),
            }
            - {""}
        )
        result.append(
            {
                **row,
                "payload": _json_loads(row.get("payload_json"), {}),
                "visible_to_domain_ids": visible_to,
                "hidden_from_domain_ids": [
                    domain_id for domain_id in domain_ids if domain_id not in visible_to
                ],
                "master_exact": True,
            }
        )
    return result


def _artifact_visibility_audit(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    owners_by_artifact = _group_by(
        _rows(
            connection,
            """
            SELECT owner_player_id, asset_id, quantity, status, source, source_ref_id, updated_at
            FROM asset_ownership
            WHERE asset_type = 'artifact'
            ORDER BY asset_id, owner_player_id
            """,
            table_name="asset_ownership",
        ),
        "asset_id",
    )
    locks_by_artifact = _group_by(
        _rows(
            connection,
            """
            SELECT lock_id, owner_player_id, asset_id, quantity, lock_type,
                   source_ref_id, status, locked_at, released_at, reason, metadata_json
            FROM asset_locks
            WHERE asset_type = 'artifact'
            ORDER BY asset_id, locked_at, lock_id
            """,
            table_name="asset_locks",
        ),
        "asset_id",
    )
    reveals_by_artifact = _artifact_reveal_events(connection)
    artifacts = []
    for row in _table(connection, "artifacts"):
        artifact_id = str(row.get("artifact_id") or "")
        if not artifact_id:
            continue
        reveal_events = reveals_by_artifact.get(artifact_id, [])
        artifacts.append(
            {
                **row,
                "owners": owners_by_artifact.get(artifact_id, []),
                "locks": [
                    {
                        **lock,
                        "metadata": _json_loads(lock.get("metadata_json"), {}),
                    }
                    for lock in locks_by_artifact.get(artifact_id, [])
                ],
                "reveal_events": reveal_events,
                "revealed": bool(reveal_events),
                "player_visibility": _artifact_player_visibility(str(row.get("visibility") or "")),
                "master_exact": True,
            }
        )
    return artifacts


def _artifact_reveal_events(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    events = _rows(
        connection,
        """
        SELECT effect_id, cast_id, sorceress_id, spell_id, target_type, target_id,
               effect_json, counterplay, visibility, status, created_at
        FROM magic_effects
        WHERE target_type IN ('object', 'visibility')
        ORDER BY created_at, effect_id
        """,
        table_name="magic_effects",
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    artifact_ids = {str(row.get("artifact_id") or "") for row in _table(connection, "artifacts")}
    for row in events:
        effect = _json_loads(row.get("effect_json"), {})
        targets = [str(row.get("target_id") or "")]
        artifact_id = effect.get("artifact_id") if isinstance(effect, dict) else None
        if artifact_id:
            targets.append(str(artifact_id))
        for target_id in sorted(set(targets)):
            if target_id not in artifact_ids:
                continue
            grouped.setdefault(target_id, []).append({**row, "effect": effect})
    return grouped


def _artifact_player_visibility(seed_visibility: str) -> str:
    visibility = seed_visibility.strip().lower()
    if visibility == "master_only":
        return "hidden_from_players"
    if visibility == "hidden_until_used":
        return "hidden_until_revealed"
    if visibility in {"master_and_owner", "owner_visible", "owner_or_master"}:
        return "owner_visible"
    return visibility or "unspecified"


def _buildings_for_domain(connection: sqlite3.Connection, domain_id: str) -> dict[str, Any]:
    owned_rows = _rows(
        connection,
        """
        SELECT *
        FROM domain_buildings
        WHERE domain_id = ?
        ORDER BY building_id
        """,
        (domain_id,),
        table_name="domain_buildings",
    )
    owned_ids = {row["building_id"] for row in owned_rows}
    catalog = []
    for row in _table(connection, "buildings"):
        prerequisites = _split_ids(row.get("prerequisite_ids"))
        missing = [item for item in prerequisites if item not in owned_ids]
        status = "owned" if row.get("building_id") in owned_ids else "available"
        if missing:
            status = "locked_prerequisites"
        catalog.append({**row, "status": status, "missing_prerequisites": missing})
    return {
        "owned": owned_rows,
        "available": [row for row in catalog if row["status"] == "available"],
        "catalog": catalog,
    }


def _pvp_reviews(connection: sqlite3.Connection) -> dict[str, Any]:
    rows = _rows(
        connection,
        """
        SELECT *
        FROM pvp_reviews
        ORDER BY
            CASE severity
                WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3
            END,
            created_at,
            review_id
        """,
        table_name="pvp_reviews",
    )
    open_items = [row for row in rows if row.get("status") == "needs_master_review"]
    return {"items": rows, "open_items": open_items, "open_count": len(open_items)}


def _recent_events(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        {**row, "payload": _json_loads(row.get("payload_json"), {})}
        for row in _rows(
            connection,
            """
            SELECT id, event_type, payload_json, source, created_at
            FROM event_log
            ORDER BY id DESC
            LIMIT 25
            """,
            table_name="event_log",
        )
    ]


def _sync_statuses(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(
        connection,
        """
        SELECT client_id, player_id, snapshot_version, last_seen_at, last_event_sequence
        FROM client_sync_state
        ORDER BY last_seen_at DESC
        LIMIT 20
        """,
        table_name="client_sync_state",
    )


def _recent_game_ops_corrections(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        {
            **row,
            "patch": _json_loads(row.get("patch_json"), {}),
            "before": _json_loads(row.get("before_json"), {}),
            "after": _json_loads(row.get("after_json"), {}),
        }
        for row in _rows(
            connection,
            """
            SELECT *
            FROM game_ops_corrections
            ORDER BY created_at DESC, correction_id DESC
            LIMIT 20
            """,
            table_name="game_ops_corrections",
        )
    ]


def _record_correction(
    connection: sqlite3.Connection,
    *,
    target_type: str,
    target_id: str,
    operator: str,
    reason: str,
    patch: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    source: str,
    created_at: str,
) -> dict[str, Any]:
    correction_id = f"ops_corr_{uuid4().hex}"
    payload = {
        "correction_id": correction_id,
        "target_type": target_type,
        "target_id": target_id,
        "operator": operator,
        "reason": reason,
        "patch": patch,
        "before": before,
        "after": after,
        "source": source,
        "created_at": created_at,
    }
    connection.execute(
        """
        INSERT INTO game_ops_corrections (
            correction_id, target_type, target_id, operator, reason,
            patch_json, before_json, after_json, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            correction_id,
            target_type,
            target_id,
            operator,
            reason,
            _json_dumps(patch),
            _json_dumps(before),
            _json_dumps(after),
            source,
            created_at,
        ),
    )
    log_event(connection, "master_game_ops_correction", payload, source=source)
    return payload


def _ensure_game_ops_schema(connection: sqlite3.Connection) -> None:
    ensure_runtime_schema(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS game_ops_corrections (
            correction_id TEXT PRIMARY KEY,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            operator TEXT NOT NULL,
            reason TEXT NOT NULL,
            patch_json TEXT NOT NULL DEFAULT '{}',
            before_json TEXT NOT NULL DEFAULT '{}',
            after_json TEXT NOT NULL DEFAULT '{}',
            source TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _normalize_target_type(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "owner": "territory",
        "mp": "domain",
        "building": "domain_building",
        "purchased_building": "domain_building",
        "reward": "pending_reward",
        "pending_tick_reward": "pending_reward",
        "pvp_timeout": "pvp_review",
        "potion": "potion_market",
        "potion_stock": "potion_market",
        "potion_market_stock": "potion_market",
        "inventory": "potion_inventory",
        "potion_bag": "potion_inventory",
        "trade": "trade_transfer",
        "trade_transfer_runtime": "trade_transfer",
        "economy_player": "player",
        "goal": "personal_goal",
        "player_goal": "personal_goal",
    }
    return aliases.get(normalized, normalized)


def _normalize_patch_value(
    field: str,
    value: Any,
    int_fields: set[str],
    json_fields: set[str],
) -> Any:
    if field in int_fields:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise GameOpsCorrectionError(
                f"Correction field {field} must be an integer.",
                code="invalid_integer_field",
            ) from exc
    if field in json_fields and not isinstance(value, str):
        return _json_dumps(value)
    if value is None:
        return None
    return str(value)


def _fetch_by_pk(
    connection: sqlite3.Connection,
    table_name: str,
    pk: str,
    target_id: str,
) -> dict[str, Any] | None:
    if not _table_exists(connection, table_name):
        return None
    row = connection.execute(
        f"""
        SELECT *
        FROM {quote_identifier(table_name)}
        WHERE {quote_identifier(pk)} = ?
        """,
        (target_id,),
    ).fetchone()
    return _clean_row(row) if row is not None else None


def _fetch_domain_building(
    connection: sqlite3.Connection,
    domain_id: str,
    building_id: str,
    territory_id: str | None = None,
) -> dict[str, Any] | None:
    if not _table_exists(connection, "domain_buildings"):
        return None
    scoped_territory_id = str(territory_id or "")
    territory_clause = "AND territory_id = ?" if scoped_territory_id else ""
    params: tuple[object, ...] = (
        (domain_id, building_id, scoped_territory_id)
        if scoped_territory_id
        else (domain_id, building_id)
    )
    row = connection.execute(
        f"""
        SELECT *
        FROM domain_buildings
        WHERE domain_id = ? AND building_id = ?
          {territory_clause}
        ORDER BY territory_id
        LIMIT 1
        """,
        params,
    ).fetchone()
    return _clean_row(row) if row is not None else None


def _domain_residence_territory(connection: sqlite3.Connection, domain_id: str) -> str | None:
    if not _table_exists(connection, "territories"):
        return None
    row = connection.execute(
        """
        SELECT territory_id
        FROM territories
        WHERE owner_domain_id = ?
          AND bonus_type = 'residence'
        ORDER BY _row_number
        LIMIT 1
        """,
        (domain_id,),
    ).fetchone()
    return str(row["territory_id"] or "") if row is not None else None


def _table(connection: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    try:
        return [dict(row) for row in fetch_table(connection, table_name)]
    except sqlite3.OperationalError:
        return []


def _rows(
    connection: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
    *,
    table_name: str,
) -> list[dict[str, Any]]:
    if not _table_exists(connection, table_name):
        return []
    return [_clean_row(row) for row in connection.execute(sql, params).fetchall()]


def _count(connection: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(connection, table_name):
        return 0
    row = connection.execute(
        f"SELECT COUNT(*) FROM {quote_identifier(table_name)}"
    ).fetchone()
    return int(row[0]) if row else 0


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    if not _table_exists(connection, table_name):
        return set()
    return {
        str(row["name"])
        for row in connection.execute(
            f"PRAGMA table_info({quote_identifier(table_name)})"
        ).fetchall()
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


def _group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(key) or ""), []).append(row)
    return grouped


def _group_first(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_key = str(row.get(key) or "")
        if row_key and row_key not in grouped:
            grouped[row_key] = row
    return grouped


def _split_ids(value: object) -> list[str]:
    return [part.strip() for part in str(value or "").replace(",", ";").split(";") if part.strip()]


def _clean_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def _json_loads(value: object, fallback: Any) -> Any:
    try:
        if value in (None, ""):
            return fallback
        return json.loads(str(value))
    except json.JSONDecodeError:
        return fallback


def _json_dumps(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _to_int(value: object) -> int:
    if value in (None, ""):
        return 0
    return int(value)


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(UTC)).isoformat(timespec="seconds")
