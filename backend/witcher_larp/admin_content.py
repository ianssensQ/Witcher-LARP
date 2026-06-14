"""Master-facing content import state and checklist helpers."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
import sqlite3

from .config import PROJECT_ROOT
from .content_schema import REQUIRED_FILES, split_ids
from .repository import (
    ensure_import_schema,
    fetch_latest_snapshot,
    fetch_table,
    latest_snapshot_version,
    quote_identifier,
)
from .snapshot_exporter import export_snapshot_file


DEFAULT_PACK_ID = "data_seed"
REQUIRED_HANDOUT_TOPICS = {
    "common_rules",
    "qr_honesty",
    "single_d20",
    "pvp_refusal_safety",
    "npc_scene_book",
}


def list_content_packs() -> dict[str, object]:
    packs: list[dict[str, object]] = [
        {
            "id": DEFAULT_PACK_ID,
            "label": "Runtime seed pack",
            "kind": "seed_root",
            "source_path": _relative_path(PROJECT_ROOT / "data" / "seed"),
            "manifest_path": None,
            "expected_result": "success",
        }
    ]

    fixtures_root = PROJECT_ROOT / "tests" / "fixtures"
    if fixtures_root.exists():
        for manifest_path in sorted(fixtures_root.glob("seed_*/fixture_manifest.csv")):
            packs.append(_manifest_pack_option(manifest_path))

    return {
        "default_pack_id": DEFAULT_PACK_ID,
        "packs": packs,
    }


def resolve_manifest_path(manifest_path: str | None) -> Path | None:
    if not manifest_path or not manifest_path.strip():
        return None
    resolved = _resolve_project_path(manifest_path.strip())
    if not resolved.exists():
        raise FileNotFoundError(f"Manifest path does not exist: {_relative_path(resolved)}")
    if resolved.suffix.lower() != ".csv":
        raise ValueError("Manifest path must point to a CSV fixture manifest.")
    _validate_manifest_boundaries(resolved)
    return resolved


def resolve_snapshot_dir(snapshot_dir: str | None, default_dir: Path) -> Path:
    if not snapshot_dir or not snapshot_dir.strip():
        return default_dir
    return _resolve_project_path(snapshot_dir.strip())


def latest_import_report(connection: sqlite3.Connection) -> dict[str, object]:
    ensure_import_schema(connection)
    row = connection.execute(
        """
        SELECT run_id, source_path, status, started_at, finished_at,
               files_json, error_count, snapshot_version
        FROM import_runs
        ORDER BY started_at DESC, rowid DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return {
            "status": "not_imported",
            "run_id": None,
            "files": [],
            "errors": [],
            "error_count": 0,
            "snapshot_version": latest_snapshot_version(connection),
        }

    errors = connection.execute(
        """
        SELECT code, file, row_number, record_id, message
        FROM import_errors
        WHERE run_id = ?
        ORDER BY error_id
        """,
        (row["run_id"],),
    ).fetchall()
    return {
        "run_id": row["run_id"],
        "source_path": row["source_path"],
        "status": row["status"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "files": json.loads(row["files_json"] or "[]"),
        "error_count": int(row["error_count"]),
        "snapshot_version": row["snapshot_version"],
        "errors": [
            {
                "code": error["code"],
                "file": error["file"],
                "row": error["row_number"],
                "record_id": error["record_id"],
                "message": error["message"],
            }
            for error in errors
        ],
    }


def export_latest_snapshot(
    connection: sqlite3.Connection, snapshot_dir: Path
) -> dict[str, object]:
    snapshot = fetch_latest_snapshot(connection)
    if snapshot is None:
        return {
            "status": "not_imported",
            "snapshot_version": None,
            "path": None,
        }
    path = export_snapshot_file(snapshot, snapshot_dir)
    return {
        "status": "success",
        "snapshot_version": snapshot["snapshot_version"],
        "path": _relative_path(path),
    }


def build_qr_checklist(connection: sqlite3.Connection) -> dict[str, object]:
    snapshot_version = latest_snapshot_version(connection)
    qr_rows = _safe_fetch_table(connection, "qr_objects")
    scenario_rows = {
        row.get("scenario_id"): row
        for row in _safe_fetch_table(connection, "pve_scenarios")
    }
    modes = Counter(str(row.get("qr_mode", "")) for row in qr_rows)
    items = []
    for row in qr_rows:
        scenario = scenario_rows.get(row.get("scenario_id"), {})
        items.append(
            {
                "qr_id": row.get("qr_id", ""),
                "manual_code": row.get("manual_code", ""),
                "mode": row.get("qr_mode", ""),
                "act_id": row.get("act_id", ""),
                "location_node_id": row.get("location_node_id", ""),
                "scenario_id": row.get("scenario_id", ""),
                "scene_type": scenario.get("scene_type", ""),
                "physical_presence_required": _truthy(row.get("physical_presence_required")),
                "print_ready": bool(row.get("manual_code"))
                and _truthy(row.get("physical_presence_required")),
            }
        )

    policy = _qr_policy_state(connection)
    return {
        "status": "ready" if qr_rows and policy["ready"] else "not_imported",
        "snapshot_version": snapshot_version,
        "total": len(qr_rows),
        "by_mode": dict(modes),
        "policy": policy,
        "items": items,
    }


def build_pve_authoring_summary() -> dict[str, object]:
    authoring_dir = PROJECT_ROOT / "data" / "authoring"
    registry_path = authoring_dir / "pve_qr_registry.csv"
    matrix_path = authoring_dir / "pve_authoring_matrix.csv"
    freeze_path = authoring_dir / "freezes" / "pve72_v1.json"
    print_path = PROJECT_ROOT / "reports" / "pve-qr-print" / "pve72_v1.html"
    if not registry_path.exists() or not matrix_path.exists():
        return {
            "status": "missing",
            "total": 0,
            "scenarios": 0,
            "by_act": {},
            "by_mode": {},
            "statuses": {},
            "print_sheet": None,
            "freeze": None,
            "items": [],
        }

    registry = _read_csv_rows(registry_path)
    matrix = _read_csv_rows(matrix_path)
    matrix_by_quest = {row.get("quest_id", ""): row for row in matrix}
    by_act = Counter(str(row.get("act_id", "")) for row in registry)
    by_mode = Counter(str(row.get("qr_mode", "")) for row in registry)
    statuses = Counter(str(row.get("status", "")) for row in registry)
    items = []
    for row in registry[:12]:
        scene = matrix_by_quest.get(row.get("quest_id", ""), {})
        items.append(
            {
                "qr_id": row.get("qr_id", ""),
                "manual_code": row.get("manual_code", ""),
                "quest_id": row.get("quest_id", ""),
                "scenario_id": scene.get("scenario_id", ""),
                "act_id": row.get("act_id", ""),
                "loc_code": row.get("loc_code", ""),
                "location_node_id": row.get("location_node_id", ""),
                "qr_mode": row.get("qr_mode", ""),
                "status": row.get("status", ""),
            }
        )

    ready = (
        len(registry) == 72
        and len(matrix) == 72
        and print_path.exists()
        and freeze_path.exists()
    )
    return {
        "status": "ready" if ready else "draft",
        "total": len(registry),
        "scenarios": len(matrix),
        "by_act": dict(by_act),
        "by_mode": dict(by_mode),
        "statuses": dict(statuses),
        "print_sheet": _relative_path(print_path) if print_path.exists() else None,
        "freeze": _relative_path(freeze_path) if freeze_path.exists() else None,
        "items": items,
    }


def build_handout_checklist(connection: sqlite3.Connection) -> dict[str, object]:
    snapshot_version = latest_snapshot_version(connection)
    handout_rows = _safe_fetch_table(connection, "player_handouts")
    ops_rows = _safe_fetch_table(connection, "ops_checklists")
    items = []
    all_topics: set[str] = set()
    for row in handout_rows:
        topics = split_ids(str(row.get("required_topics", "")))
        all_topics.update(topics)
        missing_topics = (
            sorted(REQUIRED_HANDOUT_TOPICS - set(topics))
            if row.get("audience") == "all"
            else []
        )
        items.append(
            {
                "handout_id": row.get("handout_id", ""),
                "audience": row.get("audience", ""),
                "topics": topics,
                "missing_topics": missing_topics,
                "ready": not missing_topics,
            }
        )

    policy_checks = [
        {
            "id": topic,
            "label": topic.replace("_", " "),
            "ready": topic in all_topics,
        }
        for topic in sorted(REQUIRED_HANDOUT_TOPICS)
    ]
    ops_required = [
        row
        for row in ops_rows
        if _truthy(row.get("required"))
        and row.get("item_id")
        in {"ops_player_handouts", "ops_qr_manual_ids", "ops_safety_zones", "ops_pvp_tables"}
    ]
    ready = bool(handout_rows) and all(check["ready"] for check in policy_checks)
    return {
        "status": "ready" if ready else "not_imported",
        "snapshot_version": snapshot_version,
        "items": items,
        "policy_checks": policy_checks,
        "ops_items": [
            {
                "item_id": row.get("item_id", ""),
                "phase": row.get("phase", ""),
                "owner_role": row.get("owner_role", ""),
                "required": _truthy(row.get("required")),
            }
            for row in ops_required
        ],
    }


def _manifest_pack_option(manifest_path: Path) -> dict[str, object]:
    row = _read_manifest_row(manifest_path)
    fixture_id = row.get("fixture_id") or manifest_path.parent.name
    fixture_type = row.get("fixture_type") or "fixture_manifest"
    return {
        "id": fixture_id,
        "label": fixture_id.replace("_", " "),
        "kind": fixture_type,
        "source_path": _relative_path(manifest_path.parent),
        "manifest_path": _relative_path(manifest_path),
        "expected_result": row.get("expected_result") or "",
    }


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_manifest_row(manifest_path: Path) -> dict[str, str]:
    try:
        with manifest_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return {}
    return rows[0] if rows else {}


def _validate_manifest_boundaries(manifest_path: Path) -> None:
    row = _read_manifest_row(manifest_path)
    if not row:
        return
    base_path = (manifest_path.parent / row.get("base_path", "")).resolve()
    _ensure_inside_project(base_path)
    for file_name in split_ids(row.get("override_files", "")):
        override_path = Path(file_name)
        if override_path.name != file_name or override_path.suffix.lower() != ".csv":
            raise ValueError(f"Manifest override file must be a CSV file name: {file_name}")


def _resolve_project_path(value: str) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved = candidate.resolve()
    _ensure_inside_project(resolved)
    return resolved


def _ensure_inside_project(path: Path) -> None:
    project_root = PROJECT_ROOT.resolve()
    if path != project_root and project_root not in path.parents:
        raise ValueError("Content paths must stay inside the project root.")


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _safe_fetch_table(
    connection: sqlite3.Connection, table_name: str
) -> list[dict[str, str]]:
    if not _table_exists(connection, table_name):
        return []
    return fetch_table(connection, table_name)


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


def _qr_policy_state(connection: sqlite3.Connection) -> dict[str, object]:
    policies = _safe_fetch_table(connection, "qr_policies")
    check_policies = _safe_fetch_table(connection, "check_policies")
    qr_policy_ready = any(
        _truthy(row.get("physical_presence_required"))
        and _truthy(row.get("manual_entry_allowed"))
        for row in policies
    )
    single_d20_ready = any(
        row.get("die_policy") == "single_d20" and _truthy(row.get("no_rerolls"))
        for row in check_policies
    )
    return {
        "ready": qr_policy_ready and single_d20_ready,
        "qr_honesty": qr_policy_ready,
        "single_d20_no_reroll": single_d20_ready,
    }


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() == "true"


def table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for file_name in REQUIRED_FILES:
        table_name = file_name[:-4]
        if not _table_exists(connection, table_name):
            continue
        row = connection.execute(
            f"SELECT COUNT(*) FROM {quote_identifier(table_name)}"
        ).fetchone()
        counts[table_name] = int(row[0]) if row is not None else 0
    return counts
