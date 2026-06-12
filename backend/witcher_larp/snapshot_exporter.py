"""Build and export compact mobile content snapshots."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
import sqlite3

from .csv_loader import SeedPack
from .repository import fetch_table
from .reputation_service import ReputationError, get_reputation_view


SNAPSHOT_TABLES = (
    "profiles",
    "acts",
    "act_unlock_codes",
    "players",
    "player_codes",
    "role_tokens",
    "orders",
    "qr_objects",
    "pve_scenarios",
    "pve_combat_rules",
    "mobs",
    "check_policies",
    "xp_rules",
    "balance_defaults",
    "items",
    "cards",
    "gwent_cards",
    "gwent_decks",
    "potions",
    "spells",
    "artifacts",
    "rewards",
    "personal_goals",
    "goal_tracks",
    "goal_flags",
    "final_hooks",
    "final_summary",
    "final_summary_fields",
    "map_nodes",
    "territories",
    "territory_bonuses",
    "reputation_rules",
    "favorite_rules",
    "ops_checklists",
    "player_handouts",
)

SECRET_SNAPSHOT_KEYS = {"player_codes", "role_tokens"}
PRIVATE_PLAYER_KEYS = {"player_code_id", "reputation"}
HIDDEN_PVE_PLAYER_FIELDS = {"choice_morality_json"}
PLAYER_SAFE_QR_MODES = {"repeatable_scene", "always_available_scene"}
PLAYER_PUBLIC_ARTIFACT_VISIBILITIES = {"public", "player_visible", "always_visible"}
PLAYER_VISIBLE_ORDER_STATUSES = {
    "published",
    "addressed_pending",
    "accepted",
    "in_progress",
    "claimed_at_prop",
    "submitted_pending_sync",
    "pending_master_approval",
    "failed_retryable",
    "contested_review",
    "completed",
}
PLAYER_PUBLIC_ORDER_STATUSES = {
    "published",
    "addressed_pending",
}


def build_snapshot_from_pack(pack: SeedPack) -> tuple[str, str, dict[str, object]]:
    tables = {
        table.name: [record.values for record in table.rows]
        for table in pack.tables.values()
    }
    return _build_snapshot(tables)


def build_snapshot_from_database(
    connection: sqlite3.Connection, *, player_code: str | None = None
) -> dict[str, object] | None:
    version_row = connection.execute(
        """
        SELECT snapshot_version, created_at
        FROM snapshot_versions
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    if version_row is None:
        return None
    tables = {name: fetch_table(connection, name) for name in SNAPSHOT_TABLES}
    tables["players"] = _merge_runtime_player_rows(connection, tables["players"])
    player_scope = None
    if player_code:
        player_scope = _player_scope_from_code(
            tables["player_codes"],
            tables["players"],
            player_code,
        )
        if player_scope is None:
            return None

    tables["orders"] = _fetch_order_snapshot_rows(connection, tables["orders"])
    act_unlocks = _act_unlock_snapshot_rows(
        tables["act_unlock_codes"],
        _fetch_act_history(connection),
    )
    snapshot = _payload_from_tables(
        tables,
        snapshot_version=version_row["snapshot_version"],
        generated_at=version_row["created_at"],
        act_unlocks=act_unlocks,
    )
    if player_scope is not None:
        reputation_view = _player_reputation_view(
            connection,
            str(player_scope["player_id"]),
        )
        return _scope_snapshot_to_player_id(
            snapshot,
            player_scope,
            reputation_view=reputation_view,
        )
    return snapshot


def scope_snapshot_to_player(
    snapshot: dict[str, object], player_code: str
) -> dict[str, object] | None:
    codes = snapshot.get("player_codes", [])
    if not isinstance(codes, list):
        return None
    code_row = next(
        (
            row
            for row in codes
            if isinstance(row, dict)
            and str(row.get("code", "")).strip().upper() == player_code.strip().upper()
            and _truthy(row.get("enabled"))
        ),
        None,
    )
    if code_row is None:
        return None
    return _scope_snapshot_to_player_id(snapshot, code_row)


def _scope_snapshot_to_player_id(
    snapshot: dict[str, object],
    player_scope: dict[str, str],
    *,
    reputation_view: dict[str, object] | None = None,
) -> dict[str, object] | None:
    player_id = str(player_scope["player_id"])
    players = snapshot.get("players", [])
    if not isinstance(players, list):
        return None
    player = next(
        (row for row in players if isinstance(row, dict) and row.get("player_id") == player_id),
        None,
    )
    if player is None:
        return None

    scoped = {
        key: value
        for key, value in snapshot.items()
        if key not in SECRET_SNAPSHOT_KEYS
    }
    public_player = _public_player_payload(
        player,
        descriptors=snapshot.get("descriptors"),
        reputation_view=reputation_view,
    )
    scoped["auth"] = {
        "scope": "player_code",
        "player_id": player_id,
        "player_code_id": str(player_scope.get("code_id", "")),
    }
    scoped["player"] = public_player
    scoped["players"] = [public_player]
    scoped["goals"] = _scope_goals(snapshot.get("goals"), player_id)
    scoped["orders"] = _scope_orders(snapshot.get("orders"), player_id)
    _redact_player_content(scoped)
    scoped["visibility"] = {
        "scope": "player",
        "player_id": player_id,
        "secret_tables": "server_only",
        "hidden_goal_flags": "master_only",
        "future_acts": "requires_sync_or_act_unlock_code",
    }
    return scoped


def export_snapshot_file(snapshot: dict[str, object], snapshot_dir: Path) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    version = str(snapshot["snapshot_version"])
    path = snapshot_dir / f"{version}.json"
    export_payload = _mobile_export_payload(snapshot)
    path.write_text(
        json.dumps(export_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _build_snapshot(tables: dict[str, list[dict[str, str]]]) -> tuple[str, str, dict[str, object]]:
    canonical = json.dumps(tables, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    snapshot_version = f"seed-v1-{content_hash[:12]}"
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    payload = _payload_from_tables(
        tables,
        snapshot_version=snapshot_version,
        generated_at=generated_at,
    )
    return snapshot_version, content_hash, payload


def _payload_from_tables(
    tables: dict[str, list[dict[str, str]]],
    *,
    snapshot_version: str,
    generated_at: str,
    act_unlocks: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    safe_act_unlocks = (
        act_unlocks
        if act_unlocks is not None
        else _act_unlock_snapshot_rows(tables["act_unlock_codes"], {})
    )
    return {
        "snapshot_version": snapshot_version,
        "generated_at": generated_at,
        "profile": tables["profiles"][0],
        "player": None,
        "players": tables["players"],
        "acts": tables["acts"],
        "act_unlock_codes": safe_act_unlocks,
        "act_unlock_state": _act_unlock_state(tables["acts"], safe_act_unlocks),
        "orders": _order_snapshot_rows(
            tables["orders"],
            qr_objects=tables["qr_objects"],
            map_nodes=tables["map_nodes"],
            territories=tables["territories"],
        ),
        "qr_objects": tables["qr_objects"],
        "pve_scenarios": tables["pve_scenarios"],
        "mobs": tables["mobs"],
        "checks": {
            "policies": tables["check_policies"],
            "combat_rules": tables["pve_combat_rules"],
            "xp_rules": tables["xp_rules"],
            "balance_defaults": tables["balance_defaults"],
        },
        "items": tables["items"],
        "cards": tables["cards"],
        "gwent_cards": tables["gwent_cards"],
        "gwent_decks": tables["gwent_decks"],
        "potions": tables["potions"],
        "spells": tables["spells"],
        "artifacts": tables["artifacts"],
        "rewards": tables["rewards"],
        "goals": {
            "personal_goals": tables["personal_goals"],
            "goal_tracks": tables["goal_tracks"],
            "goal_flags": tables["goal_flags"],
            "final_hooks": tables["final_hooks"],
        },
        "map": {
            "nodes": tables["map_nodes"],
            "territories": tables["territories"],
            "territory_bonuses": tables["territory_bonuses"],
        },
        "descriptors": {
            "reputation_rules": tables["reputation_rules"],
            "favorite_rules": tables["favorite_rules"],
            "final_summary": tables["final_summary"],
            "final_summary_fields": tables["final_summary_fields"],
            "ops_checklists": tables["ops_checklists"],
            "player_handouts": tables["player_handouts"],
        },
        "visibility": {
            "scope": "full",
            "secret_tables": "server_only",
            "hidden_goal_flags": "master_only",
            "future_acts": "requires_sync_or_act_unlock_code",
        },
    }


def _fetch_act_history(connection: sqlite3.Connection) -> dict[str, dict[str, str]]:
    if not _table_exists(connection, "act_history"):
        return {}
    rows = connection.execute(
        """
        SELECT act_id, status, physical_announcement_state,
               physical_announcement_at, unlock_revealed_at, unlock_revealed_by
        FROM act_history
        """
    ).fetchall()
    return {
        str(row["act_id"]): {key: row[key] for key in row.keys()}
        for row in rows
    }


def _act_unlock_snapshot_rows(
    rows: list[dict[str, str]],
    history_by_act: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    safe_rows: list[dict[str, object]] = []
    for row in rows:
        act_id = str(row.get("act_id", ""))
        history = history_by_act.get(act_id, {})
        server_unlocked = _is_announced(history.get("physical_announcement_state"))
        revealed = server_unlocked and bool(history.get("unlock_revealed_at"))
        code = str(row.get("code", "")).strip().upper()
        safe_rows.append(
            {
                "unlock_id": row.get("unlock_id", ""),
                "act_id": act_id,
                "revealed_after_start": row.get("revealed_after_start", ""),
                "server_unlocked": server_unlocked,
                "revealed": revealed,
                "code": code if revealed else None,
                "code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest()
                if code and revealed
                else None,
                "physical_announcement_state": history.get("physical_announcement_state"),
                "physical_announcement_at": history.get("physical_announcement_at"),
                "unlock_revealed_at": history.get("unlock_revealed_at"),
                "unlock_revealed_by": history.get("unlock_revealed_by"),
            }
        )
    return safe_rows


def _act_unlock_state(
    acts: list[dict[str, str]],
    act_unlocks: list[dict[str, object]],
) -> dict[str, object]:
    unlocked = {"act1"}
    revealed = set()
    for act in acts:
        act_id = str(act.get("act_id", ""))
        if act_id == "act1" or not _truthy(act.get("unlock_required")):
            unlocked.add(act_id)
    for row in act_unlocks:
        act_id = str(row.get("act_id", ""))
        if row.get("server_unlocked"):
            unlocked.add(act_id)
        if row.get("revealed"):
            revealed.add(act_id)
    return {
        "unlocked_act_ids": sorted(unlocked),
        "revealed_act_ids": sorted(revealed),
        "policy": "server_sync_or_revealed_master_code",
    }


def _player_scope_from_code(
    codes: list[dict[str, str]],
    players: list[dict[str, str]],
    player_code: str,
) -> dict[str, str] | None:
    normalized = player_code.strip().upper()
    if not normalized:
        return None
    code_row = next(
        (
            row
            for row in codes
            if str(row.get("code", "")).strip().upper() == normalized
            and _truthy(row.get("enabled"))
        ),
        None,
    )
    if code_row is None:
        return None
    player_id = str(code_row.get("player_id", ""))
    if not any(row.get("player_id") == player_id for row in players):
        return None
    return {
        "code_id": str(code_row.get("code_id", "")),
        "player_id": player_id,
        "enabled": str(code_row.get("enabled", "")),
    }


def _player_reputation_view(
    connection: sqlite3.Connection,
    player_id: str,
) -> dict[str, object] | None:
    try:
        return get_reputation_view(connection, player_id, visibility="player")
    except (ReputationError, sqlite3.OperationalError):
        return None


def _public_player_payload(
    player: dict[str, object],
    *,
    descriptors: object = None,
    reputation_view: dict[str, object] | None = None,
) -> dict[str, object]:
    public_player: dict[str, object] = {
        key: value
        for key, value in player.items()
        if key not in PRIVATE_PLAYER_KEYS
    }
    reputation_state = _public_reputation_payload(
        player,
        descriptors=descriptors,
        reputation_view=reputation_view,
    )
    if reputation_state:
        public_player["reputation_state"] = reputation_state
    return public_player


def _public_reputation_payload(
    player: dict[str, object],
    *,
    descriptors: object,
    reputation_view: dict[str, object] | None,
) -> dict[str, object]:
    if reputation_view:
        return _redact_reputation_view(reputation_view)

    if str(player.get("role_type", "")) not in {"witcher", "sorceress"}:
        return {}

    rules = []
    if isinstance(descriptors, dict):
        candidate = descriptors.get("reputation_rules", [])
        if isinstance(candidate, list):
            rules = candidate
    value = _to_int(player.get("reputation"))
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        min_value = _to_int(rule.get("min_value"))
        max_value = _to_int(rule.get("max_value"))
        if min_value <= value <= max_value:
            return {
                "state_label": str(rule.get("label", "")),
                "canonical_label": str(rule.get("label", "")),
                "player_descriptor": str(rule.get("player_descriptor", "")),
                "value_visibility": "hidden_from_player",
            }
    return {"value_visibility": "hidden_from_player"}


def _redact_reputation_view(view: dict[str, object]) -> dict[str, object]:
    return {
        key: view[key]
        for key in (
            "state_label",
            "canonical_label",
            "player_descriptor",
            "value_visibility",
        )
        if key in view
    }


def _redact_player_content(payload: dict[str, object]) -> None:
    qr_objects = _player_visible_qr_objects(
        payload.get("qr_objects"),
        payload.get("act_unlock_state"),
    )
    scenario_ids = {
        str(row.get("scenario_id", ""))
        for row in qr_objects
        if str(row.get("scenario_id", ""))
    }
    scenarios = _filter_dict_rows_by_ids(
        payload.get("pve_scenarios"),
        "scenario_id",
        scenario_ids,
    )
    scenarios = [_player_safe_pve_scenario(row) for row in scenarios]
    reward_ids = {
        str(row.get("reward_id", ""))
        for row in scenarios
        if str(row.get("reward_id", ""))
    }
    reward_ids.update(
        str(row.get("escrow_reward_id", ""))
        for row in _dict_rows(payload.get("orders"))
        if str(row.get("escrow_reward_id", ""))
    )
    mob_ids = {
        str(row.get("combat_profile_id", ""))
        for row in scenarios
        if str(row.get("combat_profile_id", ""))
    }

    payload["qr_objects"] = qr_objects
    payload["pve_scenarios"] = scenarios
    payload["rewards"] = _filter_dict_rows_by_ids(payload.get("rewards"), "reward_id", reward_ids)
    payload["mobs"] = _filter_dict_rows_by_ids(payload.get("mobs"), "mob_id", mob_ids)
    payload["artifacts"] = _player_visible_artifacts(payload.get("artifacts"))
    payload["descriptors"] = _player_visible_descriptors(payload.get("descriptors"))


def _player_visible_qr_objects(
    rows: object,
    act_unlock_state: object,
) -> list[dict[str, object]]:
    unlocked_act_ids = {"act1"}
    if isinstance(act_unlock_state, dict):
        unlocked = act_unlock_state.get("unlocked_act_ids", [])
        if isinstance(unlocked, list):
            unlocked_act_ids.update(str(act_id) for act_id in unlocked)

    visible = []
    for row in _dict_rows(rows):
        qr_mode = str(row.get("qr_mode", "")).strip().lower()
        consumption_rule = str(row.get("consumption_rule", "")).strip().lower()
        act_id = str(row.get("act_id", ""))
        if act_id not in unlocked_act_ids:
            continue
        if qr_mode not in PLAYER_SAFE_QR_MODES:
            continue
        if consumption_rule == "consume_once":
            continue
        visible.append(dict(row))
    return visible


def _player_visible_artifacts(rows: object) -> list[dict[str, object]]:
    visible = []
    for row in _dict_rows(rows):
        visibility = str(row.get("visibility", "")).strip().lower()
        if visibility not in PLAYER_PUBLIC_ARTIFACT_VISIBILITIES:
            continue
        visible.append(dict(row))
    return visible


def _player_visible_descriptors(descriptors: object) -> object:
    if not isinstance(descriptors, dict):
        return descriptors
    safe = json.loads(json.dumps(descriptors, ensure_ascii=False, default=str))
    rules = safe.get("reputation_rules")
    if isinstance(rules, list):
        safe["reputation_rules"] = [
            {
                key: rule[key]
                for key in ("rule_id", "label", "player_descriptor")
                if isinstance(rule, dict) and key in rule
            }
            for rule in rules
            if isinstance(rule, dict)
        ]
    return safe


def _filter_dict_rows_by_ids(
    rows: object,
    id_key: str,
    allowed_ids: set[str],
) -> list[dict[str, object]]:
    if not allowed_ids:
        return []
    return [
        dict(row)
        for row in _dict_rows(rows)
        if str(row.get(id_key, "")) in allowed_ids
    ]


def _player_safe_pve_scenario(row: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in row.items() if key not in HIDDEN_PVE_PLAYER_FIELDS}


def _dict_rows(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _mobile_export_payload(snapshot: dict[str, object]) -> dict[str, object]:
    payload = json.loads(json.dumps(snapshot, ensure_ascii=False, default=str))
    visibility = payload.get("visibility", {})
    scope = visibility.get("scope") if isinstance(visibility, dict) else None
    for key in SECRET_SNAPSHOT_KEYS:
        payload.pop(key, None)
    payload["pve_scenarios"] = [
        _player_safe_pve_scenario(row) for row in _dict_rows(payload.get("pve_scenarios"))
    ]
    if scope == "player":
        return payload

    payload["player"] = None
    payload["players"] = []
    goals = payload.get("goals")
    if isinstance(goals, dict):
        goals["personal_goals"] = []
        goals["goal_tracks"] = []
        goals["goal_flags"] = []
        goals["final_hooks"] = []
    payload["orders"] = []
    payload["visibility"] = {
        **(visibility if isinstance(visibility, dict) else {}),
        "scope": "mobile_public_artifact",
        "players": "server_scoped_only",
        "secret_tables": "server_only",
        "hidden_goal_flags": "master_only",
    }
    return payload


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _to_int(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(value)


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


def _scope_goals(goals: object, player_id: str) -> dict[str, list[dict[str, str]]]:
    if not isinstance(goals, dict):
        return {"personal_goals": [], "goal_tracks": [], "goal_flags": [], "final_hooks": []}
    personal_goals = [
        goal
        for goal in goals.get("personal_goals", [])
        if isinstance(goal, dict) and goal.get("player_id") == player_id
    ]
    goal_ids = {str(goal["goal_id"]) for goal in personal_goals}
    public_tracks = [
        track
        for track in goals.get("goal_tracks", [])
        if isinstance(track, dict)
        and track.get("goal_id") in goal_ids
        and track.get("visibility") != "master_only"
    ]
    public_flags = [
        flag
        for flag in goals.get("goal_flags", [])
        if isinstance(flag, dict)
        and flag.get("goal_id") in goal_ids
        and flag.get("visibility") != "master_only"
    ]
    hook_ids = {str(goal["final_hook_id"]) for goal in personal_goals if goal.get("final_hook_id")}
    final_hooks = [
        hook
        for hook in goals.get("final_hooks", [])
        if isinstance(hook, dict) and hook.get("final_hook_id") in hook_ids
    ]
    return {
        "personal_goals": personal_goals,
        "goal_tracks": public_tracks,
        "goal_flags": public_flags,
        "final_hooks": final_hooks,
    }


def _fetch_order_snapshot_rows(
    connection: sqlite3.Connection,
    fallback_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    if not _table_exists(connection, "order_runtime_state"):
        return list(fallback_rows)
    rows = connection.execute(
        """
        SELECT order_id, lord_id, target_player_id, object_id, visibility, status,
               escrow_reward_id, accepted_by_player_id, submitted_by_player_id,
               result_event_id, reason, created_at, updated_at
        FROM order_runtime_state
        ORDER BY created_at, order_id
        """
    ).fetchall()
    if not rows:
        return list(fallback_rows)
    return [{key: row[key] for key in row.keys()} for row in rows]


def _merge_runtime_player_rows(
    connection: sqlite3.Connection,
    players: list[dict[str, str]],
) -> list[dict[str, object]]:
    if not _table_exists(connection, "player_runtime_state"):
        return list(players)
    rows = connection.execute(
        """
        SELECT player_id, level, xp, gold, stats_json, mana, max_mana,
               challenge_tokens, updated_at
        FROM player_runtime_state
        """
    ).fetchall()
    runtime_by_player_id = {
        str(row["player_id"]): {key: row[key] for key in row.keys() if key != "player_id"}
        for row in rows
    }
    result: list[dict[str, object]] = []
    for player in players:
        payload = dict(player)
        runtime = runtime_by_player_id.get(str(player.get("player_id", "")))
        if runtime is not None:
            payload.update(runtime)
        result.append(payload)
    return result


def _order_snapshot_rows(
    rows: object,
    *,
    qr_objects: object,
    map_nodes: object,
    territories: object,
) -> list[dict[str, object]]:
    qr_by_id = {str(row.get("qr_id", "")): row for row in _dict_rows(qr_objects)}
    map_node_by_id = {str(row.get("node_id", "")): row for row in _dict_rows(map_nodes)}
    territory_by_id = {
        str(row.get("territory_id", "")): row for row in _dict_rows(territories)
    }
    result: list[dict[str, object]] = []
    for row in _dict_rows(rows):
        order = dict(row)
        object_id = str(order.get("object_id") or "")
        object_label, object_type = _order_object_metadata(
            object_id,
            qr_by_id=qr_by_id,
            map_node_by_id=map_node_by_id,
            territory_by_id=territory_by_id,
        )
        order["object_label"] = object_label
        order["object_type"] = object_type
        result.append(order)
    return result


def _order_object_metadata(
    object_id: str,
    *,
    qr_by_id: dict[str, dict[str, object]],
    map_node_by_id: dict[str, dict[str, object]],
    territory_by_id: dict[str, dict[str, object]],
) -> tuple[str, str]:
    territory = territory_by_id.get(object_id)
    if territory is not None:
        return str(territory.get("name", object_id)), "territory"

    qr_object = qr_by_id.get(object_id)
    if qr_object is not None:
        node_id = str(qr_object.get("location_node_id", ""))
        node = map_node_by_id.get(node_id)
        if node is not None:
            return str(node.get("name", object_id)), "qr_object"
        return object_id, "qr_object"

    return object_id, "unknown"


def _scope_orders(orders: object, player_id: str) -> list[dict[str, object]]:
    scoped: list[dict[str, object]] = []
    for row in _dict_rows(orders):
        status = str(row.get("status") or "").strip().lower()
        if status and status not in PLAYER_VISIBLE_ORDER_STATUSES:
            continue
        target_player_id = str(row.get("target_player_id") or "")
        accepted_by_player_id = str(row.get("accepted_by_player_id") or "")
        submitted_by_player_id = str(row.get("submitted_by_player_id") or "")
        visibility = str(row.get("visibility") or "").strip().lower()
        belongs_to_player = player_id in {
            target_player_id,
            accepted_by_player_id,
            submitted_by_player_id,
        }
        is_open_public_order = (
            visibility == "public"
            and not target_player_id
            and status in PLAYER_PUBLIC_ORDER_STATUSES
        )
        if belongs_to_player or is_open_public_order:
            scoped.append(dict(row))
    return scoped
