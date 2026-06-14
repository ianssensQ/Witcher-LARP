#!/usr/bin/env python
"""Validate, compile and print PvE QR authoring assets."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
import hashlib
import html
import json
from pathlib import Path
import sys
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTHORING_DIR = PROJECT_ROOT / "data" / "authoring"
DEFAULT_PRINT_PATH = PROJECT_ROOT / "reports" / "pve-qr-print" / "pve72_v1.html"
DEFAULT_FREEZE_PATH = AUTHORING_DIR / "freezes" / "pve72_v1.json"

EXPECTED_ACT_COUNTS = {"act1": 20, "act2": 22, "act3": 22, "final_act": 8}
EXPECTED_QR_MODE_COUNTS = {
    "repeatable_scene": 15,
    "always_available_scene": 9,
    "unique_object": 48,
}
EXPECTED_CONTENT_LANE_COUNTS = {"anti_idle": 24, "story_quest": 48}
MAX_SCENARIO_THEME_REUSE = 2
QR_CONSUMPTION_RULE_BY_MODE = {
    "unique_object": "consume_once",
    "repeatable_scene": "repeatable",
    "always_available_scene": "always_available",
}
CONTENT_LANE_BY_QR_MODE = {
    "unique_object": "story_quest",
    "repeatable_scene": "anti_idle",
    "always_available_scene": "anti_idle",
}
VALID_TRIAL_TYPES = {"combat", "choice", "ritual_check"}
SCENE_TYPES = {"monster_hunt", "moral_choice", "puzzle_check"}
STORY_FLOW_FIELDS = [
    "quest_flow_version",
    "board_description",
    "scan_reveal",
    "choice_prompt",
    "choice_options_json",
    "encounter_steps_json",
    "victory_rule",
    "branch_reward_policy",
    "reputation_hint",
]
HIDDEN_STORY_FIELDS = ["choice_morality_json"]
QUEST_BIBLE_AUTHORING_FIELDS = [
    "scenario_title",
    "visible_hook",
    "player_brief",
    "story_summary",
    "visual_asset_id",
    "visual_prompt",
    "icon_key",
    "content_lane",
    "estimated_minutes",
    "trial_type",
    "trial_prompt",
    "stat_check_label",
    "gear_tags",
    "monster_tags",
    "success_consequence",
    "partial_consequence",
    "failure_consequence",
    "reward_summary",
    "world_effect",
    *STORY_FLOW_FIELDS,
    *HIDDEN_STORY_FIELDS,
    "hidden_truth_tag",
    "gm_notes",
    "balance_notes",
]
QUEST_BIBLE_REQUIRED_FIELDS = [
    "scenario_title",
    "visible_hook",
    "player_brief",
    "story_summary",
    "visual_asset_id",
    "visual_prompt",
    "icon_key",
    "content_lane",
    "estimated_minutes",
    "trial_type",
    "trial_prompt",
    "stat_check_label",
    "gear_tags",
    "monster_tags",
    "success_text",
    "failure_text",
    "success_consequence",
    "partial_consequence",
    "failure_consequence",
    "reward_summary",
    "world_effect",
    *STORY_FLOW_FIELDS,
    *HIDDEN_STORY_FIELDS,
    "gm_notes",
    "balance_notes",
]
PVE_RUNTIME_CARD_FIELDS = [
    "scenario_title",
    "visible_hook",
    "player_brief",
    "story_summary",
    "visual_asset_id",
    "visual_prompt",
    "icon_key",
    "content_lane",
    "estimated_minutes",
    "trial_type",
    "trial_prompt",
    "stat_check_label",
    "gear_tags",
    "monster_tags",
    "success_consequence",
    "partial_consequence",
    "failure_consequence",
    "reward_summary",
    "world_effect",
    *STORY_FLOW_FIELDS,
]
PVE_HIDDEN_RUNTIME_FIELDS = [*HIDDEN_STORY_FIELDS]
STABLE_QR_FIELDS = [
    "qr_id",
    "manual_code",
    "quest_id",
    "act_id",
    "loc_code",
    "location_node_id",
    "qr_mode",
    "consumption_rule",
]
QR_SEED_FIELDS = [
    "qr_id",
    "manual_code",
    "scenario_id",
    "qr_mode",
    "act_id",
    "location_node_id",
    "physical_presence_required",
    "rate_limit",
    "consumption_rule",
]
PVE_SEED_FIELDS = [
    "scenario_id",
    "act_id",
    "tier",
    "scene_type",
    "primary_stat",
    "dc",
    "check_policy",
    "combat_profile_id",
    "reward_id",
    *PVE_RUNTIME_CARD_FIELDS,
    *PVE_HIDDEN_RUNTIME_FIELDS,
    "success_text",
    "failure_text",
    "timeout_outcome",
]
QR_ALPHANUMERIC = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"
QR_SIZE = 21
QR_DATA_CODEWORDS = 19
QR_ECC_CODEWORDS = 7


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _count_by(rows: Iterable[dict[str, str]], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(field_name, "")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _scenario_theme(row: dict[str, str]) -> str:
    return row.get("scenario_title", "").split(":", 1)[0].strip()


def _count_scenario_themes(rows: Iterable[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        theme = _scenario_theme(row)
        if not theme:
            continue
        counts[theme] = counts.get(theme, 0) + 1
    return dict(sorted(counts.items()))


def _find_duplicates(rows: Iterable[dict[str, str]], field_name: str) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for row in rows:
        value = row.get(field_name, "")
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return sorted(dupes)


def _require_columns(
    report: ValidationReport, path: Path, rows: list[dict[str, str]], columns: list[str]
) -> None:
    if not rows:
        report.errors.append(f"{path.name}: file is empty")
        return
    missing = [column for column in columns if column not in rows[0]]
    if missing:
        report.errors.append(f"{path.name}: missing columns {', '.join(missing)}")


def _validate_json_array(
    report: ValidationReport,
    quest_id: str,
    row: dict[str, str],
    field_name: str,
    *,
    min_items: int,
    required_keys: set[str],
) -> None:
    raw_value = row.get(field_name, "").strip()
    if not raw_value:
        report.errors.append(f"{quest_id}: {field_name} required")
        return
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        report.errors.append(f"{quest_id}: {field_name} invalid JSON: {exc.msg}")
        return
    if not isinstance(payload, list) or len(payload) < min_items:
        report.errors.append(f"{quest_id}: {field_name} must contain at least {min_items} items")
        return
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            report.errors.append(f"{quest_id}: {field_name}[{index}] must be an object")
            continue
        missing = sorted(required_keys - set(item))
        if missing:
            report.errors.append(
                f"{quest_id}: {field_name}[{index}] missing keys {', '.join(missing)}"
            )


def _validate_choice_morality(report: ValidationReport, quest_id: str, row: dict[str, str]) -> None:
    try:
        choices = json.loads(row.get("choice_options_json", ""))
        morality = json.loads(row.get("choice_morality_json", ""))
    except json.JSONDecodeError as exc:
        report.errors.append(f"{quest_id}: choice morality/option JSON invalid: {exc.msg}")
        return
    if not isinstance(choices, list) or not isinstance(morality, list):
        report.errors.append(f"{quest_id}: choice morality and options must be JSON arrays")
        return
    choice_ids = [str(choice.get("id", "")) for choice in choices if isinstance(choice, dict)]
    morality_ids = [
        str(entry.get("option_id", "")) for entry in morality if isinstance(entry, dict)
    ]
    if sorted(choice_ids) != sorted(morality_ids):
        report.errors.append(
            f"{quest_id}: choice_morality_json option_id values must match choice_options_json ids"
        )
    for index, entry in enumerate(morality, start=1):
        if not isinstance(entry, dict):
            report.errors.append(f"{quest_id}: choice_morality_json[{index}] must be an object")
            continue
        missing = {
            "option_id",
            "alignment",
            "good_evil_delta",
            "moral_axis",
            "hidden_moral",
            "reputation_reason",
            "visibility",
            "apply_on",
        } - set(entry)
        if missing:
            report.errors.append(
                f"{quest_id}: choice_morality_json[{index}] missing keys {', '.join(sorted(missing))}"
            )
        try:
            delta = int(entry.get("good_evil_delta", 0))
        except (TypeError, ValueError):
            report.errors.append(f"{quest_id}: choice_morality_json[{index}] delta must be integer")
            continue
        if delta < -2 or delta > 2:
            report.errors.append(
                f"{quest_id}: choice_morality_json[{index}] delta must be between -2 and 2"
            )
        if entry.get("visibility") != "master_only":
            report.errors.append(
                f"{quest_id}: choice_morality_json[{index}] visibility must be master_only"
            )


def validate_authoring(root: Path = PROJECT_ROOT) -> ValidationReport:
    authoring_dir = root / "data" / "authoring"
    locations_path = authoring_dir / "location_codes.csv"
    registry_path = authoring_dir / "pve_qr_registry.csv"
    matrix_path = authoring_dir / "pve_authoring_matrix.csv"
    report = ValidationReport()

    for path in [locations_path, registry_path, matrix_path]:
        if not path.exists():
            report.errors.append(f"missing {path}")
            return report

    locations = _read_csv(locations_path)
    registry = _read_csv(registry_path)
    matrix = _read_csv(matrix_path)

    _require_columns(
        report,
        locations_path,
        locations,
        ["loc_code", "location_node_id", "print_label", "qr_allowed"],
    )
    _require_columns(
        report,
        registry_path,
        registry,
        [
            *STABLE_QR_FIELDS,
            "physical_presence_required",
            "print_label",
            "placement_note",
            "take_policy",
            "print_batch",
            "status",
        ],
    )
    _require_columns(
        report,
        matrix_path,
        matrix,
        [
            "quest_id",
            "scenario_id",
            "act_id",
            "loc_code",
            "location_node_id",
            "tier",
            "scene_type",
            "qr_mode",
            "primary_stat",
            "secondary_stat",
            "dc",
            "combat_profile_id",
            "reward_id",
            *QUEST_BIBLE_AUTHORING_FIELDS,
            "success_text",
            "failure_text",
            "reward_approval_policy",
            "act_unlock_policy",
            "role_load_tag",
            "ops_checklist_tag",
            "test_status",
        ],
    )
    if report.errors:
        return report

    loc_map = {row["loc_code"]: row["location_node_id"] for row in locations}
    matrix_by_quest = {row["quest_id"]: row for row in matrix}

    for field_name in ["loc_code", "location_node_id"]:
        duplicates = _find_duplicates(locations, field_name)
        for value in duplicates:
            report.errors.append(f"location_codes.csv: duplicate {field_name} {value}")

    for field_name in ["qr_id", "manual_code", "quest_id"]:
        duplicates = _find_duplicates(registry, field_name)
        for value in duplicates:
            report.errors.append(f"pve_qr_registry.csv: duplicate {field_name} {value}")

    for field_name in ["quest_id", "scenario_id"]:
        duplicates = _find_duplicates(matrix, field_name)
        for value in duplicates:
            report.errors.append(f"pve_authoring_matrix.csv: duplicate {field_name} {value}")
    for field_name in ["visual_asset_id"]:
        duplicates = _find_duplicates(matrix, field_name)
        for value in duplicates:
            report.errors.append(f"pve_authoring_matrix.csv: duplicate {field_name} {value}")
    scenario_theme_counts = _count_scenario_themes(matrix)
    for theme, count in scenario_theme_counts.items():
        if count > MAX_SCENARIO_THEME_REUSE:
            report.errors.append(
                "pve_authoring_matrix.csv: scenario theme "
                f"{theme!r} reused {count} times; max is {MAX_SCENARIO_THEME_REUSE}"
            )

    for row in registry:
        qr_id = row["qr_id"]
        loc_code = row["loc_code"]
        manual_code = row["manual_code"]
        if loc_code not in loc_map:
            report.errors.append(f"{qr_id}: unknown loc_code {loc_code}")
        elif loc_map[loc_code] != row["location_node_id"]:
            report.errors.append(
                f"{qr_id}: loc_code {loc_code} points to {loc_map[loc_code]}, "
                f"not {row['location_node_id']}"
            )
        if row["physical_presence_required"].lower() != "true":
            report.errors.append(f"{qr_id}: physical_presence_required must be true")
        if row["qr_mode"] not in EXPECTED_QR_MODE_COUNTS:
            report.errors.append(f"{qr_id}: invalid qr_mode {row['qr_mode']}")
        expected_consumption = QR_CONSUMPTION_RULE_BY_MODE.get(row["qr_mode"])
        if expected_consumption and row["consumption_rule"] != expected_consumption:
            report.errors.append(
                f"{qr_id}: consumption_rule {row['consumption_rule']} does not match "
                f"{row['qr_mode']} ({expected_consumption})"
            )
        if any(char not in QR_ALPHANUMERIC for char in manual_code):
            report.errors.append(f"{qr_id}: manual_code contains non-QR alphanumeric char")
        if len(manual_code) > 25:
            report.errors.append(f"{qr_id}: manual_code too long for version 1-L QR")
        if row["quest_id"] not in matrix_by_quest:
            report.errors.append(f"{qr_id}: missing authoring matrix row {row['quest_id']}")
            continue
        matrix_row = matrix_by_quest[row["quest_id"]]
        for field_name in ["act_id", "loc_code", "location_node_id", "qr_mode"]:
            if row[field_name] != matrix_row[field_name]:
                report.errors.append(
                    f"{qr_id}: registry {field_name}={row[field_name]} does not match "
                    f"matrix {matrix_row[field_name]}"
                )

    registry_quest_ids = {row["quest_id"] for row in registry}
    for row in matrix:
        quest_id = row["quest_id"]
        if quest_id not in registry_quest_ids:
            report.errors.append(f"{quest_id}: missing QR registry row")
        if row["scene_type"] not in SCENE_TYPES:
            report.errors.append(f"{quest_id}: invalid scene_type {row['scene_type']}")
        if row["tier"] not in {"1", "2", "3", "4"}:
            report.errors.append(f"{quest_id}: invalid tier {row['tier']}")
        if not row["dc"].isdigit():
            report.errors.append(f"{quest_id}: dc must be numeric")
        if not row["success_text"] or not row["failure_text"]:
            report.errors.append(f"{quest_id}: success_text/failure_text required")
        for field_name in QUEST_BIBLE_REQUIRED_FIELDS:
            value = row.get(field_name, "").strip()
            if not value:
                report.errors.append(f"{quest_id}: {field_name} required")
            elif "????" in value:
                report.errors.append(f"{quest_id}: {field_name} contains mojibake placeholder")
        expected_lane = CONTENT_LANE_BY_QR_MODE.get(row["qr_mode"])
        if row["content_lane"] not in EXPECTED_CONTENT_LANE_COUNTS:
            report.errors.append(f"{quest_id}: invalid content_lane {row['content_lane']}")
        elif expected_lane and row["content_lane"] != expected_lane:
            report.errors.append(
                f"{quest_id}: content_lane {row['content_lane']} does not match "
                f"{row['qr_mode']} ({expected_lane})"
            )
        if row["trial_type"] not in VALID_TRIAL_TYPES:
            report.errors.append(f"{quest_id}: invalid trial_type {row['trial_type']}")
        _validate_json_array(
            report,
            quest_id,
            row,
            "choice_options_json",
            min_items=2,
            required_keys={"id", "label", "description", "modifier", "stakes"},
        )
        _validate_json_array(
            report,
            quest_id,
            row,
            "encounter_steps_json",
            min_items=3,
            required_keys={"step", "title", "stat", "dc", "text", "success", "failure"},
        )
        _validate_choice_morality(report, quest_id, row)
        if "2" not in row.get("victory_rule", "") or "3" not in row.get("victory_rule", ""):
            report.errors.append(f"{quest_id}: victory_rule must describe the 2-of-3 outcome")
        if not row["estimated_minutes"].isdigit():
            report.errors.append(f"{quest_id}: estimated_minutes must be numeric")
        else:
            estimated_minutes = int(row["estimated_minutes"])
            if estimated_minutes <= 0 or estimated_minutes > 15:
                report.errors.append(
                    f"{quest_id}: estimated_minutes must fit the 10h field cadence"
                )
            if row["content_lane"] == "anti_idle" and estimated_minutes > 8:
                report.errors.append(f"{quest_id}: anti_idle scenes must stay under 8 minutes")
            if row["content_lane"] == "story_quest" and estimated_minutes < 10:
                report.errors.append(f"{quest_id}: story_quest scenes must be at least 10 minutes")
        if row["loc_code"] not in loc_map:
            report.errors.append(f"{quest_id}: unknown loc_code {row['loc_code']}")
        elif loc_map[row["loc_code"]] != row["location_node_id"]:
            report.errors.append(f"{quest_id}: loc_code/location_node_id mismatch")

    act_counts = _count_by(registry, "act_id")
    mode_counts = _count_by(registry, "qr_mode")
    content_lane_counts = _count_by(matrix, "content_lane")
    if act_counts != EXPECTED_ACT_COUNTS:
        report.errors.append(f"act coverage mismatch: {act_counts} != {EXPECTED_ACT_COUNTS}")
    if mode_counts != EXPECTED_QR_MODE_COUNTS:
        report.errors.append(
            f"qr_mode coverage mismatch: {mode_counts} != {EXPECTED_QR_MODE_COUNTS}"
        )
    if content_lane_counts != EXPECTED_CONTENT_LANE_COUNTS:
        report.errors.append(
            f"content lane coverage mismatch: "
            f"{content_lane_counts} != {EXPECTED_CONTENT_LANE_COUNTS}"
        )

    report.summary = {
        "locations": len(locations),
        "qr_slots": len(registry),
        "scenarios": len(matrix),
        "act_counts": act_counts,
        "qr_mode_counts": mode_counts,
        "content_lane_counts": content_lane_counts,
        "trial_type_counts": _count_by(matrix, "trial_type"),
        "scene_type_counts": _count_by(matrix, "scene_type"),
        "scenario_theme_reuse_max": max(scenario_theme_counts.values(), default=0),
    }
    return report


def compile_seed_pack(
    root: Path = PROJECT_ROOT,
    output_dir: Path | None = None,
) -> dict[str, object]:
    """Compile authoring CSV into runtime seed CSV files."""

    report = validate_authoring(root)
    if not report.ok:
        raise ValueError("\n".join(report.errors))

    if output_dir is None:
        output_dir = root / "data" / "seed"
    registry = _read_csv(root / "data" / "authoring" / "pve_qr_registry.csv")
    matrix = _read_csv(root / "data" / "authoring" / "pve_authoring_matrix.csv")
    matrix_by_quest = {row["quest_id"]: row for row in matrix}

    qr_rows = []
    for row in registry:
        scenario = matrix_by_quest[row["quest_id"]]
        qr_rows.append(
            {
                "qr_id": row["qr_id"],
                "manual_code": row["manual_code"],
                "scenario_id": scenario["scenario_id"],
                "qr_mode": row["qr_mode"],
                "act_id": row["act_id"],
                "location_node_id": row["location_node_id"],
                "physical_presence_required": row["physical_presence_required"],
                "rate_limit": "5_per_minute",
                "consumption_rule": row["consumption_rule"],
            }
        )

    pve_rows = []
    for row in matrix:
        pve_row = {
            "scenario_id": row["scenario_id"],
            "act_id": row["act_id"],
            "tier": row["tier"],
            "scene_type": row["scene_type"],
            "primary_stat": row["primary_stat"],
            "dc": row["dc"],
            "check_policy": "single_d20",
            "combat_profile_id": row["combat_profile_id"],
            "reward_id": row["reward_id"],
        }
        for field_name in PVE_RUNTIME_CARD_FIELDS:
            pve_row[field_name] = row[field_name]
        for field_name in PVE_HIDDEN_RUNTIME_FIELDS:
            pve_row[field_name] = row[field_name]
        pve_row["success_text"] = row["success_text"]
        pve_row["failure_text"] = row["failure_text"]
        pve_row["timeout_outcome"] = "fail_and_cooldown"
        pve_rows.append(pve_row)

    _write_csv(output_dir / "qr_objects.csv", QR_SEED_FIELDS, qr_rows)
    _write_csv(output_dir / "pve_scenarios.csv", PVE_SEED_FIELDS, pve_rows)
    return {
        "output_dir": str(output_dir),
        "qr_objects": len(qr_rows),
        "pve_scenarios": len(pve_rows),
        "act_counts": _count_by(qr_rows, "act_id"),
        "qr_mode_counts": _count_by(qr_rows, "qr_mode"),
        "content_lane_counts": _count_by(pve_rows, "content_lane"),
        "trial_type_counts": _count_by(pve_rows, "trial_type"),
    }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _gf_tables() -> tuple[list[int], list[int]]:
    exp = [0] * 512
    log = [0] * 256
    value = 1
    for index in range(255):
        exp[index] = value
        log[value] = index
        value <<= 1
        if value & 0x100:
            value ^= 0x11D
    for index in range(255, 512):
        exp[index] = exp[index - 255]
    return exp, log


GF_EXP, GF_LOG = _gf_tables()


def _gf_multiply(left: int, right: int) -> int:
    if left == 0 or right == 0:
        return 0
    return GF_EXP[GF_LOG[left] + GF_LOG[right]]


def _reed_solomon_remainder(data: list[int], degree: int) -> list[int]:
    divisor = [0] * degree
    divisor[-1] = 1
    root = 1
    for _ in range(degree):
        for index in range(degree):
            divisor[index] = _gf_multiply(divisor[index], root)
            if index + 1 < degree:
                divisor[index] ^= divisor[index + 1]
        root = _gf_multiply(root, 2)

    result = [0] * degree
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for index, coefficient in enumerate(divisor):
            result[index] ^= _gf_multiply(coefficient, factor)
    return result


class _BitBuffer:
    def __init__(self) -> None:
        self.bits: list[int] = []

    def append(self, value: int, bit_count: int) -> None:
        for shift in reversed(range(bit_count)):
            self.bits.append((value >> shift) & 1)

    def to_codewords(self) -> list[int]:
        return [
            int("".join(str(bit) for bit in self.bits[index : index + 8]), 2)
            for index in range(0, len(self.bits), 8)
        ]


def _encode_alphanumeric_payload(payload: str) -> list[int]:
    payload = payload.upper()
    buffer = _BitBuffer()
    buffer.append(0b0010, 4)
    buffer.append(len(payload), 9)
    index = 0
    while index + 1 < len(payload):
        value = QR_ALPHANUMERIC.index(payload[index]) * 45
        value += QR_ALPHANUMERIC.index(payload[index + 1])
        buffer.append(value, 11)
        index += 2
    if index < len(payload):
        buffer.append(QR_ALPHANUMERIC.index(payload[index]), 6)

    capacity_bits = QR_DATA_CODEWORDS * 8
    terminator = min(4, capacity_bits - len(buffer.bits))
    buffer.append(0, terminator)
    while len(buffer.bits) % 8:
        buffer.append(0, 1)
    codewords = buffer.to_codewords()
    for pad_byte in [0xEC, 0x11] * QR_DATA_CODEWORDS:
        if len(codewords) >= QR_DATA_CODEWORDS:
            break
        codewords.append(pad_byte)
    return codewords


def _empty_qr_matrix() -> tuple[list[list[bool]], list[list[bool]]]:
    matrix = [[False for _ in range(QR_SIZE)] for _ in range(QR_SIZE)]
    reserved = [[False for _ in range(QR_SIZE)] for _ in range(QR_SIZE)]

    def set_function(row: int, col: int, black: bool) -> None:
        if 0 <= row < QR_SIZE and 0 <= col < QR_SIZE:
            matrix[row][col] = black
            reserved[row][col] = True

    def add_finder(row: int, col: int) -> None:
        for dy in range(-1, 8):
            for dx in range(-1, 8):
                rr = row + dy
                cc = col + dx
                if not (0 <= rr < QR_SIZE and 0 <= cc < QR_SIZE):
                    continue
                black = (
                    0 <= dx <= 6
                    and 0 <= dy <= 6
                    and (
                        dx in {0, 6}
                        or dy in {0, 6}
                        or (2 <= dx <= 4 and 2 <= dy <= 4)
                    )
                )
                set_function(rr, cc, black)

    add_finder(0, 0)
    add_finder(0, QR_SIZE - 7)
    add_finder(QR_SIZE - 7, 0)

    for index in range(8, QR_SIZE - 8):
        set_function(6, index, index % 2 == 0)
        set_function(index, 6, index % 2 == 0)

    set_function(13, 8, True)
    for index in range(15):
        if index < 6:
            set_function(8, index, False)
        elif index < 8:
            set_function(8, index + 1, False)
        else:
            set_function(8, 14 - index, False)
        if index < 8:
            set_function(QR_SIZE - 1 - index, 8, False)
        else:
            set_function(8, QR_SIZE - 15 + index, False)
    return matrix, reserved


def _mask_bit(mask: int, row: int, col: int) -> bool:
    if mask == 0:
        return (row + col) % 2 == 0
    if mask == 1:
        return row % 2 == 0
    if mask == 2:
        return col % 3 == 0
    if mask == 3:
        return (row + col) % 3 == 0
    if mask == 4:
        return (row // 2 + col // 3) % 2 == 0
    if mask == 5:
        return (row * col) % 2 + (row * col) % 3 == 0
    if mask == 6:
        return ((row * col) % 2 + (row * col) % 3) % 2 == 0
    return ((row + col) % 2 + (row * col) % 3) % 2 == 0


def _format_bits(mask: int) -> int:
    data = (0b01 << 3) | mask
    value = data << 10
    generator = 0x537
    for shift in reversed(range(10)):
        if (value >> (shift + 10)) & 1:
            value ^= generator << shift
    return ((data << 10) | (value & 0x3FF)) ^ 0x5412


def _draw_format_bits(matrix: list[list[bool]], mask: int) -> None:
    bits = _format_bits(mask)
    for index in range(15):
        black = ((bits >> index) & 1) == 1
        if index < 6:
            matrix[8][index] = black
        elif index < 8:
            matrix[8][index + 1] = black
        else:
            matrix[8][14 - index] = black
        if index < 8:
            matrix[QR_SIZE - 1 - index][8] = black
        else:
            matrix[8][QR_SIZE - 15 + index] = black
    matrix[13][8] = True


def _place_data_bits(
    matrix: list[list[bool]],
    reserved: list[list[bool]],
    bits: list[int],
    mask: int,
) -> None:
    bit_index = 0
    direction = -1
    col = QR_SIZE - 1
    while col > 0:
        if col == 6:
            col -= 1
        for row_step in range(QR_SIZE):
            row = QR_SIZE - 1 - row_step if direction == -1 else row_step
            for current_col in [col, col - 1]:
                if reserved[row][current_col]:
                    continue
                black = bit_index < len(bits) and bits[bit_index] == 1
                if _mask_bit(mask, row, current_col):
                    black = not black
                matrix[row][current_col] = black
                bit_index += 1
        direction *= -1
        col -= 2


def _penalty_score(matrix: list[list[bool]]) -> int:
    score = 0
    for row in matrix:
        run_color = row[0]
        run_len = 1
        for color in row[1:]:
            if color == run_color:
                run_len += 1
            else:
                if run_len >= 5:
                    score += 3 + run_len - 5
                run_color = color
                run_len = 1
        if run_len >= 5:
            score += 3 + run_len - 5
    for col in range(QR_SIZE):
        run_color = matrix[0][col]
        run_len = 1
        for row in range(1, QR_SIZE):
            if matrix[row][col] == run_color:
                run_len += 1
            else:
                if run_len >= 5:
                    score += 3 + run_len - 5
                run_color = matrix[row][col]
                run_len = 1
        if run_len >= 5:
            score += 3 + run_len - 5
    for row in range(QR_SIZE - 1):
        for col in range(QR_SIZE - 1):
            color = matrix[row][col]
            if (
                matrix[row][col + 1] == color
                and matrix[row + 1][col] == color
                and matrix[row + 1][col + 1] == color
            ):
                score += 3
    return score


def make_qr_matrix(payload: str) -> list[list[bool]]:
    data = _encode_alphanumeric_payload(payload)
    ecc = _reed_solomon_remainder(data, QR_ECC_CODEWORDS)
    bits: list[int] = []
    for codeword in [*data, *ecc]:
        bits.extend((codeword >> shift) & 1 for shift in reversed(range(8)))

    best_matrix: list[list[bool]] | None = None
    best_score: int | None = None
    for mask in range(8):
        matrix, reserved = _empty_qr_matrix()
        _place_data_bits(matrix, reserved, bits, mask)
        _draw_format_bits(matrix, mask)
        score = _penalty_score(matrix)
        if best_score is None or score < best_score:
            best_score = score
            best_matrix = matrix
    if best_matrix is None:
        raise RuntimeError("QR matrix generation failed")
    return best_matrix


def make_qr_svg(payload: str) -> str:
    matrix = make_qr_matrix(payload)
    quiet = 4
    size = QR_SIZE + quiet * 2
    path_parts = []
    for row, modules in enumerate(matrix):
        for col, black in enumerate(modules):
            if black:
                path_parts.append(f"M{col + quiet},{row + quiet}h1v1h-1z")
    path_data = " ".join(path_parts)
    return (
        f'<svg class="qr" viewBox="0 0 {size} {size}" role="img" '
        f'aria-label="{html.escape(payload)}">'
        f'<rect width="{size}" height="{size}" fill="#fff"/>'
        f'<path fill="#000" d="{path_data}"/></svg>'
    )


def _act_sort_key(act_id: str) -> tuple[int, str]:
    order = {"act1": 1, "act2": 2, "act3": 3, "final_act": 4}
    return (order.get(act_id, 99), act_id)


def render_print_html(root: Path = PROJECT_ROOT) -> str:
    report = validate_authoring(root)
    if not report.ok:
        raise ValueError("\n".join(report.errors))

    registry = sorted(
        _read_csv(root / "data" / "authoring" / "pve_qr_registry.csv"),
        key=lambda row: (_act_sort_key(row["act_id"]), row["loc_code"], row["manual_code"]),
    )
    matrix_by_quest = {
        row["quest_id"]: row
        for row in _read_csv(root / "data" / "authoring" / "pve_authoring_matrix.csv")
    }
    cards = []
    for row in registry:
        scene = matrix_by_quest[row["quest_id"]]
        cards.append(
            "\n".join(
                [
                    '<article class="card">',
                    f'<div class="qrbox">{make_qr_svg(row["manual_code"])}</div>',
                    f'<h2>{html.escape(row["manual_code"])}</h2>',
                    f'<p class="label">{html.escape(row["print_label"])}</p>',
                    f'<p>QR: <strong>{html.escape(row["qr_id"])}</strong></p>',
                    f'<p>Quest: <strong>{html.escape(row["quest_id"])}</strong></p>',
                    f'<p>Scene: {html.escape(scene["scenario_title"])}</p>',
                    f'<p>Mode: {html.escape(row["qr_mode"])}</p>',
                    f'<p>Take policy: {html.escape(row["take_policy"])}</p>',
                    "</article>",
                ]
            )
        )

    style = """
    @page { size: A4; margin: 10mm; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      color: #111;
      background: #fff;
    }
    header { margin: 0 0 8mm; }
    h1 { font-size: 18pt; margin: 0 0 2mm; }
    .summary { font-size: 9pt; margin: 0; }
    .sheet {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 5mm;
    }
    .card {
      break-inside: avoid;
      border: 0.35mm solid #111;
      min-height: 84mm;
      padding: 4mm;
      display: grid;
      grid-template-rows: auto auto auto 1fr;
      align-content: start;
    }
    .qrbox { display: flex; justify-content: center; }
    .qr { width: 38mm; height: 38mm; image-rendering: pixelated; }
    h2 { font-size: 12pt; margin: 2mm 0 1mm; text-align: center; letter-spacing: 0; }
    p { font-size: 7.5pt; line-height: 1.25; margin: 1mm 0; }
    .label { font-size: 8.5pt; font-weight: 700; text-align: center; }
    """
    summary = report.summary
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="ru">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>PvE QR print sheet pve72_v1</title>",
            f"<style>{style}</style>",
            "</head>",
            "<body>",
            "<header>",
            "<h1>PvE QR print sheet: pve72_v1</h1>",
            (
                '<p class="summary">'
                f"QR slots: {summary['qr_slots']}; "
                f"acts: {html.escape(json.dumps(summary['act_counts'], ensure_ascii=False))}; "
                f"modes: {html.escape(json.dumps(summary['qr_mode_counts'], ensure_ascii=False))}"
                "</p>"
            ),
            "</header>",
            '<main class="sheet">',
            *cards,
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def write_print_html(output_path: Path, root: Path = PROJECT_ROOT) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_print_html(root), encoding="utf-8")
    return output_path


def _stable_payload(row: dict[str, str]) -> dict[str, str]:
    return {field_name: row[field_name] for field_name in STABLE_QR_FIELDS}


def _stable_hash(payload: dict[str, str]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_freeze(root: Path = PROJECT_ROOT, batch: str = "pve72_v1") -> dict[str, object]:
    report = validate_authoring(root)
    if not report.ok:
        raise ValueError("\n".join(report.errors))
    registry = _read_csv(root / "data" / "authoring" / "pve_qr_registry.csv")
    rows = []
    for row in sorted(registry, key=lambda item: item["qr_id"]):
        payload = _stable_payload(row)
        rows.append({**payload, "stable_hash": _stable_hash(payload)})
    return {
        "schema": "pve_qr_freeze_v1",
        "batch": batch,
        "stable_fields": STABLE_QR_FIELDS,
        "row_count": len(rows),
        "rows": rows,
    }


def write_freeze(output_path: Path, root: Path = PROJECT_ROOT, batch: str = "pve72_v1") -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_freeze(root, batch), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def check_freeze(freeze_path: Path, root: Path = PROJECT_ROOT) -> list[str]:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    frozen_rows = {row["qr_id"]: row for row in freeze.get("rows", [])}
    current_rows = {
        row["qr_id"]: _stable_payload(row)
        for row in _read_csv(root / "data" / "authoring" / "pve_qr_registry.csv")
    }
    errors: list[str] = []
    for qr_id, frozen in frozen_rows.items():
        if qr_id not in current_rows:
            errors.append(f"{qr_id}: frozen row missing from current registry")
            continue
        current_hash = _stable_hash(current_rows[qr_id])
        if current_hash != frozen["stable_hash"]:
            errors.append(f"{qr_id}: stable fields changed after freeze")
    for qr_id in sorted(set(current_rows) - set(frozen_rows)):
        errors.append(f"{qr_id}: current registry row missing from freeze")
    return errors


def _print_report(report: ValidationReport) -> None:
    print(json.dumps(report.summary, ensure_ascii=False, indent=2))
    for warning in report.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in report.errors:
        print(f"ERROR: {error}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="Validate data/authoring CSV files")

    compile_parser = subparsers.add_parser(
        "compile-seed",
        help="Compile authoring QR/PvE rows into data/seed runtime CSV files",
    )
    compile_parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "data" / "seed")

    print_parser = subparsers.add_parser("print-html", help="Generate printable QR HTML")
    print_parser.add_argument("--output", type=Path, default=DEFAULT_PRINT_PATH)

    freeze_parser = subparsers.add_parser("freeze", help="Write QR stable-field freeze JSON")
    freeze_parser.add_argument("--output", type=Path, default=DEFAULT_FREEZE_PATH)
    freeze_parser.add_argument("--batch", default="pve72_v1")

    check_parser = subparsers.add_parser("check-freeze", help="Compare registry to freeze JSON")
    check_parser.add_argument("--freeze", type=Path, default=DEFAULT_FREEZE_PATH)

    args = parser.parse_args(argv)

    if args.command == "validate":
        report = validate_authoring()
        _print_report(report)
        return 0 if report.ok else 1
    if args.command == "compile-seed":
        summary = compile_seed_pack(output_dir=args.output_dir)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "print-html":
        output_path = write_print_html(args.output)
        print(output_path)
        return 0
    if args.command == "freeze":
        output_path = write_freeze(args.output, batch=args.batch)
        print(output_path)
        return 0
    if args.command == "check-freeze":
        errors = check_freeze(args.freeze)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"freeze_errors={len(errors)}")
        return 0 if not errors else 1
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
