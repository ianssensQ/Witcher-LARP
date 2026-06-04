"""Validation rules for runtime CSV imports."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json

from .content_schema import REQUIRED_FILES, TABLE_ID_COLUMNS, split_ids
from .csv_loader import CsvRecord, CsvTable, SeedPack
from .gwent_effects import is_gwent_effect_supported
from .import_models import ImportErrorDetail
from .stats import (
    CANONICAL_STAT_SET,
    CANONICAL_STATS,
    RUNTIME_STAT_MAX,
    START_STAT_BUDGET,
    START_STAT_MAX,
)


VALID_QR_MODES = {"unique_object", "repeatable_scene", "always_available_scene"}
QR_CONSUMPTION_RULE_BY_MODE = {
    "unique_object": "consume_once",
    "repeatable_scene": "repeatable",
    "always_available_scene": "always_available",
}
VALID_BUILDING_BRANCHES = {"military", "economy", "order", "magic"}
VALID_UNIT_CLASSES = {"infantry", "guard", "ranged", "cavalry", "heavy_siege", "specialist"}
VALID_PVP_THROTTLE_MODES = {"normal", "limited", "paused"}
VALID_REWARD_POLICIES = {"auto", "pending_master_approval"}
VALID_ORDER_VISIBILITY = {"public", "addressed", "private"}
VALID_FAVORITE_SLOTS = {"primary", "secondary"}
REQUIRED_NPC_MASTER_TOKEN_OWNERS = {"npc_king", "npc_wanderer"}
CANONICAL_LORD_BATTLE_RULES = {
    "grid_width": "5",
    "grid_height": "6",
    "turn_timer_seconds": "60",
    "damage_formula": "max(1 attack-defense+modifiers)",
    "initiative_tiebreaker": "initiative_desc_tier_desc_seed",
    "timeout_policy": "auto_defend_then_skip",
    "auto_resolve_policy": "repeated_timeout_master_takeover_or_auto_resolve",
}
CASCADE_PVE_SCENE_TYPES = {
    "artifact",
    "final_scene",
    "lord_hook",
    "npc_deal",
    "order_object",
    "reputation",
    "reputation_impact",
}
CASCADE_ITEM_TYPES = {
    "final_evidence",
    "order_token",
    "plot_key",
    "pvp_stake",
    "trophy",
}
CASCADE_EFFECT_MARKERS = {
    "domain",
    "final",
    "final_evidence",
    "final_summary",
    "gwent_stake",
    "influence",
    "lord",
    "npc",
    "order",
    "pvp",
    "reputation",
    "stake",
}
REQUIRED_HANDOUT_AUDIENCES = {"all", "witcher", "sorceress", "lord", "npc_master"}
REQUIRED_COMMON_HANDOUT_TOPICS = {
    "common_rules",
    "qr_honesty",
    "single_d20",
    "pvp_refusal_safety",
    "npc_scene_book",
}


def _csv_bool(value: object) -> bool:
    return str(value or "").strip().lower() == "true"


def validate_seed_pack(pack: SeedPack) -> list[ImportErrorDetail]:
    errors = list(pack.load_errors)
    tables = pack.tables

    for file_name in REQUIRED_FILES:
        if file_name not in tables:
            errors.append(
                ImportErrorDetail(
                    code="missing_file",
                    file=file_name,
                    message=f"Required CSV file is missing from loaded seed pack: {file_name}",
                )
            )
            continue
        table = tables[file_name]
        if TABLE_ID_COLUMNS[file_name] not in table.headers:
            errors.append(
                ImportErrorDetail(
                    code="missing_id_column",
                    file=file_name,
                    message=(
                        f"CSV file {file_name} must include id column "
                        f"{TABLE_ID_COLUMNS[file_name]}."
                    ),
                )
            )
        if not table.rows:
            errors.append(
                ImportErrorDetail(
                    code="empty_file",
                    file=file_name,
                    message=f"CSV file must contain at least one row: {file_name}",
                )
            )

    errors.extend(_validate_missing_headers(pack))
    if errors:
        return errors

    errors.extend(_validate_duplicate_ids(tables))
    ids = _id_index(tables)
    errors.extend(_validate_references(tables, ids))
    errors.extend(_validate_production_profile(tables))
    errors.extend(_validate_role_ownership_and_tokens(tables))
    errors.extend(_validate_stat_model(tables))
    errors.extend(_validate_acts_and_unlocks(tables, ids))
    errors.extend(_validate_qr_and_pve(tables, ids))
    errors.extend(_validate_buildings_and_units(tables, ids))
    errors.extend(_validate_orders(tables, ids))
    errors.extend(_validate_gwent(tables, ids))
    errors.extend(_validate_trade_transfers(tables, ids))
    errors.extend(_validate_lord_battle_rules(tables))
    errors.extend(_validate_rules_and_final(tables, ids))
    errors.extend(_validate_master_ops_readiness(tables))
    errors.extend(_validate_paper_forms(tables))
    return errors


def _validate_missing_headers(pack: SeedPack) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    for file_name, table in pack.tables.items():
        reference_headers = _reference_headers(pack, file_name)
        if not reference_headers:
            continue
        missing_headers = [
            header for header in reference_headers if header not in set(table.headers)
        ]
        if not missing_headers:
            continue
        errors.append(
            ImportErrorDetail(
                code="missing_header",
                file=file_name,
                message=(
                    f"CSV file {file_name} is missing required header(s): "
                    f"{', '.join(missing_headers)}."
                ),
            )
        )
    return errors


def _reference_headers(pack: SeedPack, file_name: str) -> tuple[str, ...]:
    reference_path = pack.source_path / file_name
    if not reference_path.exists():
        return ()
    try:
        with reference_path.open(newline="", encoding="utf-8") as handle:
            fieldnames = csv.DictReader(handle).fieldnames
    except OSError:
        return ()
    return tuple(fieldnames or ())


def _validate_duplicate_ids(tables: dict[str, CsvTable]) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    for file_name, table in tables.items():
        id_column = TABLE_ID_COLUMNS[file_name]
        seen: dict[str, CsvRecord] = {}
        for record in table.rows:
            value = record.values.get(id_column, "")
            if not value:
                errors.append(
                    ImportErrorDetail(
                        code="missing_id",
                        file=file_name,
                        row=record.row_number,
                        message=f"Missing required id value in {id_column}.",
                    )
                )
                continue
            if value in seen:
                errors.append(
                    ImportErrorDetail(
                        code="duplicate_id",
                        file=file_name,
                        row=record.row_number,
                        record_id=value,
                        message=f"Duplicate id {value} in {file_name}.",
                    )
                )
            seen[value] = record
    return errors


def _id_index(tables: dict[str, CsvTable]) -> dict[str, set[str]]:
    return {
        file_name: {
            record.values[TABLE_ID_COLUMNS[file_name]]
            for record in table.rows
            if record.values.get(TABLE_ID_COLUMNS[file_name])
        }
        for file_name, table in tables.items()
    }


def _validate_references(
    tables: dict[str, CsvTable], ids: dict[str, set[str]]
) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []

    reference_checks = [
        ("player_codes.csv", "player_id", "players.csv", True),
        ("players.csv", "player_code_id", "player_codes.csv", True),
        ("domains.csv", "lord_player_id", "players.csv", True),
        ("auto_timers.csv", "act_id", "acts.csv", True),
        ("physical_announcements.csv", "act_id", "acts.csv", True),
        ("map_nodes.csv", "territory_id", "territories.csv", False),
        ("territories.csv", "owner_domain_id", "domains.csv", False),
        ("territories.csv", "neutral_defense_profile_id", "mobs.csv", False),
        ("movement_pools.csv", "domain_id", "domains.csv", True),
        ("movement_pools.csv", "act_id", "acts.csv", True),
        ("territory_claims.csv", "territory_id", "territories.csv", True),
        ("territory_claims.csv", "claimant_domain_id", "domains.csv", True),
        ("pending_tick_rewards.csv", "domain_id", "domains.csv", True),
        ("pending_tick_rewards.csv", "territory_id", "territories.csv", True),
        ("pending_tick_rewards.csv", "reward_id", "rewards.csv", True),
        ("army_reserves.csv", "domain_id", "domains.csv", True),
        ("army_reserves.csv", "card_id", "army_unit_cards.csv", True),
        ("garrisons.csv", "territory_id", "territories.csv", True),
        ("garrisons.csv", "domain_id", "domains.csv", True),
        ("garrisons.csv", "card_id", "army_unit_cards.csv", True),
        ("army_unit_cards.csv", "source_id", "buildings.csv", True),
        ("recruit_markets.csv", "domain_id", "domains.csv", True),
        ("recruit_markets.csv", "card_id", "army_unit_cards.csv", True),
        ("cards.csv", "army_unit_card_id", "army_unit_cards.csv", True),
        ("pve_scenarios.csv", "act_id", "acts.csv", True),
        ("pve_scenarios.csv", "check_policy", "check_policies.csv", True),
        ("pve_scenarios.csv", "combat_profile_id", "mobs.csv", True),
        ("pve_scenarios.csv", "reward_id", "rewards.csv", True),
        ("qr_objects.csv", "scenario_id", "pve_scenarios.csv", True),
        ("qr_objects.csv", "act_id", "acts.csv", True),
        ("qr_objects.csv", "location_node_id", "map_nodes.csv", True),
        ("gwent_decks.csv", "player_id", "players.csv", True),
        ("gwent_decks.csv", "leader_card_id", "gwent_cards.csv", True),
        ("gwent_matches.csv", "challenger_id", "players.csv", True),
        ("gwent_matches.csv", "target_id", "players.csv", True),
        ("orders.csv", "lord_id", "players.csv", True),
        ("orders.csv", "target_player_id", "players.csv", True),
        ("orders.csv", "escrow_reward_id", "rewards.csv", False),
        ("potion_markets.csv", "potion_id", "potions.csv", True),
        ("personal_goals.csv", "player_id", "players.csv", True),
        ("personal_goals.csv", "act_id", "acts.csv", True),
        ("personal_goals.csv", "final_hook_id", "final_hooks.csv", True),
        ("goal_tracks.csv", "goal_id", "personal_goals.csv", True),
        ("goal_flags.csv", "goal_id", "personal_goals.csv", True),
        ("favorites.csv", "sorceress_id", "players.csv", True),
        ("favorites.csv", "favored_player_id", "players.csv", True),
        ("final_summary.csv", "final_act_id", "acts.csv", True),
        ("challenge_tokens.csv", "act_id", "acts.csv", True),
    ]
    for file_name, column, target_file, required in reference_checks:
        errors.extend(
            _reference_errors(
                tables[file_name],
                column,
                ids[target_file],
                required=required,
            )
        )

    errors.extend(_list_reference_errors(tables["buildings.csv"], "prerequisite_ids", ids["buildings.csv"]))
    errors.extend(
        _list_reference_errors(tables["buildings.csv"], "recruit_unlock_ids", ids["army_unit_cards.csv"])
    )
    errors.extend(_list_reference_errors(tables["rewards.csv"], "item_ids", ids["items.csv"]))
    errors.extend(_list_reference_errors(tables["rewards.csv"], "card_ids", ids["cards.csv"] | ids["gwent_cards.csv"]))
    errors.extend(_list_reference_errors(tables["rewards.csv"], "artifact_ids", ids["artifacts.csv"]))
    errors.extend(_list_reference_errors(tables["gwent_decks.csv"], "card_ids", ids["gwent_cards.csv"]))

    order_object_ids = ids["qr_objects.csv"] | ids["territories.csv"] | ids["items.csv"] | ids["artifacts.csv"]
    for record in tables["orders.csv"].rows:
        object_id = record.values["object_id"]
        if object_id not in order_object_ids:
            errors.append(
                ImportErrorDetail(
                    code="missing_reference",
                    file="orders.csv",
                    row=record.row_number,
                    record_id=record.values["order_id"],
                    message=f"orders.csv object_id references unknown order object {object_id}.",
                )
            )

    node_ids = ids["map_nodes.csv"]
    excluded_nodes = {
        record.values["node_id"]
        for record in tables["map_nodes.csv"].rows
        if record.values["zone_status"] == "no_play_excluded"
    }
    for record in tables["map_edges.csv"].rows:
        for column in ("from_node_id", "to_node_id"):
            node_id = record.values[column]
            if node_id not in node_ids:
                errors.append(
                    ImportErrorDetail(
                        code="missing_reference",
                        file="map_edges.csv",
                        row=record.row_number,
                        record_id=record.values["edge_id"],
                        message=f"map_edges.csv {column} references unknown map node {node_id}.",
                    )
                )
            if node_id in excluded_nodes:
                errors.append(
                    ImportErrorDetail(
                        code="venue_exclusion_violation",
                        file="map_edges.csv",
                        row=record.row_number,
                        record_id=record.values["edge_id"],
                        message=f"Map edge references excluded venue node {node_id}.",
                    )
                )

    return errors


def _reference_errors(
    table: CsvTable, column: str, valid_ids: set[str], *, required: bool = False
) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    id_column = TABLE_ID_COLUMNS[table.file_name]
    for record in table.rows:
        value = record.values.get(column, "")
        if not value:
            if required:
                errors.append(
                    ImportErrorDetail(
                        code="missing_required_reference",
                        file=table.file_name,
                        row=record.row_number,
                        record_id=record.values.get(id_column),
                        message=(
                            f"{table.file_name} {column} is a required reference "
                            "and must not be empty."
                        ),
                    )
                )
            continue
        if value not in valid_ids:
            errors.append(
                ImportErrorDetail(
                    code="missing_reference",
                    file=table.file_name,
                    row=record.row_number,
                    record_id=record.values.get(id_column),
                    message=f"{table.file_name} {column} references unknown id {value}.",
                )
            )
    return errors


def _list_reference_errors(
    table: CsvTable, column: str, valid_ids: set[str]
) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    id_column = TABLE_ID_COLUMNS[table.file_name]
    for record in table.rows:
        for value in split_ids(record.values.get(column, "")):
            if value not in valid_ids:
                errors.append(
                    ImportErrorDetail(
                        code="missing_reference",
                        file=table.file_name,
                        row=record.row_number,
                        record_id=record.values.get(id_column),
                        message=f"{table.file_name} {column} references unknown id {value}.",
                    )
                )
    return errors


def _validate_production_profile(tables: dict[str, CsvTable]) -> list[ImportErrorDetail]:
    profile = tables["profiles.csv"].rows[0].values
    errors: list[ImportErrorDetail] = []
    expected = {
        "total_people": 15,
        "player_count": 13,
        "npc_master_count": 2,
        "lord_count": 4,
        "sorceress_count": 4,
        "witcher_count": 5,
    }
    for column, value in expected.items():
        if _to_int(profile.get(column, ""), default=-1) != value:
            errors.append(
                ImportErrorDetail(
                    code="bad_profile_counts",
                    file="profiles.csv",
                    row=2,
                    record_id=profile.get("profile_id"),
                    message=f"Production profile {column} must be {value}.",
                )
            )

    role_counts = Counter(record.values["role_type"] for record in tables["players.csv"].rows)
    if role_counts != {"lord": 4, "sorceress": 4, "witcher": 5}:
        errors.append(
            ImportErrorDetail(
                code="bad_profile_counts",
                file="players.csv",
                message=f"Player role profile must be 4 lords, 4 sorceresses, 5 witchers: {dict(role_counts)}.",
            )
        )
    return errors


def _validate_role_ownership_and_tokens(tables: dict[str, CsvTable]) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    players = {
        record.values["player_id"]: record
        for record in tables["players.csv"].rows
        if record.values.get("player_id")
    }
    player_roles = {
        player_id: record.values["role_type"]
        for player_id, record in players.items()
    }
    lord_player_ids = {
        player_id for player_id, role_type in player_roles.items() if role_type == "lord"
    }
    domains = {
        record.values["domain_id"]: record
        for record in tables["domains.csv"].rows
        if record.values.get("domain_id")
    }
    domain_ids_by_lord = {
        record.values["lord_player_id"]: domain_id
        for domain_id, record in domains.items()
        if record.values.get("lord_player_id")
    }

    for domain_id, record in domains.items():
        lord_player_id = record.values["lord_player_id"]
        if lord_player_id and player_roles.get(lord_player_id) != "lord":
            errors.append(
                ImportErrorDetail(
                    code="domain_lord_owner",
                    file="domains.csv",
                    row=record.row_number,
                    record_id=domain_id,
                    message=(
                        "domains.csv lord_player_id must reference a player "
                        f"with role_type=lord, got {lord_player_id}."
                    ),
                )
            )

    for player_id, record in players.items():
        role_type = record.values["role_type"]
        lord_id = record.values.get("lord_id", "")
        start_lord_id = record.values.get("sorceress_start_lord_id", "")
        if role_type == "lord":
            domain = domains.get(lord_id)
            if domain is None:
                errors.append(
                    ImportErrorDetail(
                        code="invalid_player_lord_binding",
                        file="players.csv",
                        row=record.row_number,
                        record_id=player_id,
                        message="Lord players must bind lord_id to an existing domain.",
                    )
                )
            elif domain.values["lord_player_id"] != player_id:
                errors.append(
                    ImportErrorDetail(
                        code="invalid_player_lord_binding",
                        file="players.csv",
                        row=record.row_number,
                        record_id=player_id,
                        message=(
                            "Lord player lord_id must point to a domain owned "
                            f"by that player, got {lord_id}."
                        ),
                    )
                )
            if start_lord_id:
                errors.append(
                    ImportErrorDetail(
                        code="invalid_sorceress_lord_binding",
                        file="players.csv",
                        row=record.row_number,
                        record_id=player_id,
                        message="Lord players must not set sorceress_start_lord_id.",
                    )
                )
        else:
            if lord_id:
                errors.append(
                    ImportErrorDetail(
                        code="invalid_player_lord_binding",
                        file="players.csv",
                        row=record.row_number,
                        record_id=player_id,
                        message="Only lord players may bind lord_id to a domain.",
                    )
                )
            if role_type == "sorceress":
                if start_lord_id not in lord_player_ids or start_lord_id not in domain_ids_by_lord:
                    errors.append(
                        ImportErrorDetail(
                            code="invalid_sorceress_lord_binding",
                            file="players.csv",
                            row=record.row_number,
                            record_id=player_id,
                            message=(
                                "Sorceress start lord must reference a lord player "
                                "who owns a domain."
                            ),
                        )
                    )
            elif start_lord_id:
                errors.append(
                    ImportErrorDetail(
                        code="invalid_sorceress_lord_binding",
                        file="players.csv",
                        row=record.row_number,
                        record_id=player_id,
                        message="Only sorceresses may set sorceress_start_lord_id.",
                    )
                )

    token_values: dict[str, CsvRecord] = {}
    enabled_lord_owner_count = 0
    enabled_lord_owners: set[str] = set()
    enabled_npc_owner_count = 0
    enabled_npc_owners: set[str] = set()
    for record in tables["role_tokens.csv"].rows:
        token_id = record.values["token_id"]
        role_type = record.values["role_type"]
        owner_id = record.values["owner_id"]
        token = record.values["token"]
        enabled = _csv_bool(record.values["enabled"])
        if not token:
            errors.append(
                ImportErrorDetail(
                    code="role_token_value",
                    file="role_tokens.csv",
                    row=record.row_number,
                    record_id=token_id,
                    message="Role token value must not be empty.",
                )
            )
        elif token in token_values:
            errors.append(
                ImportErrorDetail(
                    code="role_token_value",
                    file="role_tokens.csv",
                    row=record.row_number,
                    record_id=token_id,
                    message=f"Duplicate role token value also used by {token_values[token].values['token_id']}.",
                )
            )
        token_values[token] = record

        if role_type == "lord":
            if owner_id not in lord_player_ids:
                errors.append(
                    ImportErrorDetail(
                        code="role_token_owner",
                        file="role_tokens.csv",
                        row=record.row_number,
                        record_id=token_id,
                        message="Lord role tokens must be owned by lord players.",
                    )
                )
            if enabled:
                enabled_lord_owner_count += 1
                enabled_lord_owners.add(owner_id)
        elif role_type == "npc_master":
            if owner_id not in REQUIRED_NPC_MASTER_TOKEN_OWNERS:
                errors.append(
                    ImportErrorDetail(
                        code="role_token_owner",
                        file="role_tokens.csv",
                        row=record.row_number,
                        record_id=token_id,
                        message=(
                            "NPC-master role tokens must be owned by npc_king "
                            "or npc_wanderer."
                        ),
                    )
                )
            if enabled:
                enabled_npc_owner_count += 1
                enabled_npc_owners.add(owner_id)
        else:
            errors.append(
                ImportErrorDetail(
                    code="role_token_owner",
                    file="role_tokens.csv",
                    row=record.row_number,
                    record_id=token_id,
                    message="Role tokens are only valid for lord or npc_master roles.",
                )
            )

    if enabled_lord_owners != lord_player_ids or enabled_lord_owner_count != len(lord_player_ids):
        errors.append(
            ImportErrorDetail(
                code="role_token_coverage",
                file="role_tokens.csv",
                message="Enabled lord role tokens must cover each of the 4 lord players exactly once.",
            )
        )
    if (
        enabled_npc_owners != REQUIRED_NPC_MASTER_TOKEN_OWNERS
        or enabled_npc_owner_count != len(REQUIRED_NPC_MASTER_TOKEN_OWNERS)
    ):
        errors.append(
            ImportErrorDetail(
                code="role_token_coverage",
                file="role_tokens.csv",
                message="Enabled npc_master role tokens must cover npc_king and npc_wanderer exactly once.",
            )
        )

    return errors


def _validate_stat_model(tables: dict[str, CsvTable]) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    for record in tables["players.csv"].rows:
        player_id = record.values["player_id"]
        try:
            parsed = json.loads(record.values["stats_json"])
        except json.JSONDecodeError as exc:
            errors.append(
                ImportErrorDetail(
                    code="invalid_stat_schema",
                    file="players.csv",
                    row=record.row_number,
                    record_id=player_id,
                    message=f"Player stats_json must be valid JSON: {exc.msg}.",
                )
            )
            continue
        if not isinstance(parsed, dict):
            errors.append(
                ImportErrorDetail(
                    code="invalid_stat_schema",
                    file="players.csv",
                    row=record.row_number,
                    record_id=player_id,
                    message="Player stats_json must be an object with canonical stat IDs.",
                )
            )
            continue

        stats = {str(key): _to_int(value, default=-1) for key, value in parsed.items()}
        keys = set(stats)
        if keys != CANONICAL_STAT_SET:
            missing = sorted(CANONICAL_STAT_SET - keys)
            unknown = sorted(keys - CANONICAL_STAT_SET)
            errors.append(
                ImportErrorDetail(
                    code="invalid_stat_schema",
                    file="players.csv",
                    row=record.row_number,
                    record_id=player_id,
                    message=(
                        "Player stats must use exactly canonical stats "
                        f"{', '.join(CANONICAL_STATS)}; "
                        f"missing={missing}, unknown={unknown}."
                    ),
                )
            )
            continue
        if any(value < 0 for value in stats.values()):
            errors.append(
                ImportErrorDetail(
                    code="invalid_stat_schema",
                    file="players.csv",
                    row=record.row_number,
                    record_id=player_id,
                    message="Player stat values must be non-negative integers.",
                )
            )
        if sum(stats.values()) != START_STAT_BUDGET:
            errors.append(
                ImportErrorDetail(
                    code="invalid_stat_schema",
                    file="players.csv",
                    row=record.row_number,
                    record_id=player_id,
                    message=f"Starting player stats must spend exactly {START_STAT_BUDGET} points.",
                )
            )
        if max(stats.values()) > START_STAT_MAX:
            errors.append(
                ImportErrorDetail(
                    code="invalid_stat_schema",
                    file="players.csv",
                    row=record.row_number,
                    record_id=player_id,
                    message=f"Starting player stats cannot exceed {START_STAT_MAX} in one stat.",
                )
            )

    for record in tables["items.csv"].rows:
        try:
            requirements = json.loads(record.values["stat_requirement_json"] or "{}")
        except json.JSONDecodeError as exc:
            errors.append(
                ImportErrorDetail(
                    code="invalid_item_stat_requirement",
                    file="items.csv",
                    row=record.row_number,
                    record_id=record.values["item_id"],
                    message=f"Item stat_requirement_json must be valid JSON: {exc.msg}.",
                )
            )
            continue
        if not isinstance(requirements, dict):
            errors.append(
                ImportErrorDetail(
                    code="invalid_item_stat_requirement",
                    file="items.csv",
                    row=record.row_number,
                    record_id=record.values["item_id"],
                    message="Item stat_requirement_json must be an object.",
                )
            )
            continue
        for stat_id, value in requirements.items():
            if str(stat_id) not in CANONICAL_STAT_SET:
                errors.append(
                    ImportErrorDetail(
                        code="invalid_item_stat_requirement",
                        file="items.csv",
                        row=record.row_number,
                        record_id=record.values["item_id"],
                        message=f"Item references non-canonical stat {stat_id}.",
                    )
                )
            if _to_int(value, default=-1) < 0 or _to_int(value) > RUNTIME_STAT_MAX:
                errors.append(
                    ImportErrorDetail(
                        code="invalid_item_stat_requirement",
                        file="items.csv",
                        row=record.row_number,
                        record_id=record.values["item_id"],
                        message=f"Item stat requirement for {stat_id} must be 0..{RUNTIME_STAT_MAX}.",
                    )
                )
    return errors


def _validate_acts_and_unlocks(
    tables: dict[str, CsvTable], ids: dict[str, set[str]]
) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    acts = tables["acts.csv"].rows
    sequence = [(record.values["act_id"], _to_int(record.values["start_offset_min"])) for record in acts]
    expected_sequence = [
        ("registration", 0),
        ("act1", 30),
        ("act2", 150),
        ("act3", 300),
        ("final_lock", 435),
        ("final_act", 450),
        ("debrief", 570),
    ]
    if sequence != expected_sequence:
        errors.append(
            ImportErrorDetail(
                code="invalid_act_structure",
                file="acts.csv",
                message="Acts must follow the fixed 10-hour schedule with registration, 3 story acts, final lock, final act and debrief.",
            )
        )
    if _to_int(acts[-1].values["end_offset_min"]) != 600:
        errors.append(
            ImportErrorDetail(
                code="invalid_act_structure",
                file="acts.csv",
                record_id=acts[-1].values["act_id"],
                message="Fixed schedule must end at 600 minutes.",
            )
        )

    unlock_rows = tables["act_unlock_codes.csv"].rows
    unlock_act_ids = {record.values["act_id"] for record in unlock_rows}
    required_unlocks = {
        record.values["act_id"]
        for record in acts
        if record.values["act_type"] in {"story", "final"}
    }
    missing_unlocks = required_unlocks - unlock_act_ids
    for act_id in sorted(missing_unlocks):
        errors.append(
            ImportErrorDetail(
                code="act_unlock_coverage",
                file="act_unlock_codes.csv",
                record_id=act_id,
                message=f"Missing act unlock code for {act_id}.",
            )
        )
    for record in unlock_rows:
        if record.values["act_id"] not in ids["acts.csv"]:
            errors.append(
                ImportErrorDetail(
                    code="missing_reference",
                    file="act_unlock_codes.csv",
                    row=record.row_number,
                    record_id=record.values["unlock_id"],
                    message=f"Act unlock references unknown act {record.values['act_id']}.",
                )
            )
        if record.values["revealed_after_start"] != "true":
            errors.append(
                ImportErrorDetail(
                    code="future_act_unlock_revealed",
                    file="act_unlock_codes.csv",
                    row=record.row_number,
                    record_id=record.values["unlock_id"],
                    message="Act unlock codes must stay hidden until the physical act start.",
                )
            )
    return errors


def _validate_qr_and_pve(
    tables: dict[str, CsvTable], ids: dict[str, set[str]]
) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    qr_rows = tables["qr_objects.csv"].rows
    scenarios = {
        record.values["scenario_id"]: record
        for record in tables["pve_scenarios.csv"].rows
        if record.values.get("scenario_id")
    }
    for record in qr_rows:
        mode = record.values["qr_mode"]
        if mode not in VALID_QR_MODES:
            errors.append(
                ImportErrorDetail(
                    code="bad_qr_mode",
                    file="qr_objects.csv",
                    row=record.row_number,
                    record_id=record.values["qr_id"],
                    message=f"Invalid qr_mode {mode}.",
                )
            )
        if record.values["physical_presence_required"] != "true":
            errors.append(
                ImportErrorDetail(
                    code="qr_honesty_policy",
                    file="qr_objects.csv",
                    row=record.row_number,
                    record_id=record.values["qr_id"],
                    message="QR objects must require physical presence.",
                )
            )
        scenario = scenarios.get(record.values["scenario_id"])
        if scenario is not None and scenario.values["act_id"] != record.values["act_id"]:
            errors.append(
                ImportErrorDetail(
                    code="qr_scenario_act_mismatch",
                    file="qr_objects.csv",
                    row=record.row_number,
                    record_id=record.values["qr_id"],
                    message=(
                        "QR object act_id must match linked PvE scenario act_id: "
                        f"{record.values['act_id']} != {scenario.values['act_id']}."
                    ),
                )
            )
        expected_consumption_rule = QR_CONSUMPTION_RULE_BY_MODE.get(mode)
        if (
            expected_consumption_rule is not None
            and record.values["consumption_rule"] != expected_consumption_rule
        ):
            errors.append(
                ImportErrorDetail(
                    code="qr_consumption_rule_mismatch",
                    file="qr_objects.csv",
                    row=record.row_number,
                    record_id=record.values["qr_id"],
                    message=(
                        f"QR mode {mode} must use consumption_rule "
                        f"{expected_consumption_rule}."
                    ),
                )
            )

    mode_counts = Counter(record.values["qr_mode"] for record in qr_rows)
    if mode_counts["repeatable_scene"] + mode_counts["always_available_scene"] < 15:
        errors.append(
            ImportErrorDetail(
                code="qr_content_mix",
                file="qr_objects.csv",
                message="Seed must include at least 15 repeatable or always-available QR scenes.",
            )
        )
    if mode_counts["unique_object"] < 25:
        errors.append(
            ImportErrorDetail(
                code="qr_content_mix",
                file="qr_objects.csv",
                message="Seed must include at least 25 unique QR objects.",
            )
        )

    for record in tables["pve_scenarios.csv"].rows:
        if record.values["primary_stat"] not in CANONICAL_STAT_SET:
            errors.append(
                ImportErrorDetail(
                    code="invalid_pve_stat",
                    file="pve_scenarios.csv",
                    row=record.row_number,
                    record_id=record.values["scenario_id"],
                    message=(
                        "PvE primary_stat must use canonical mobile stats: "
                        f"{', '.join(CANONICAL_STATS)}."
                    ),
                )
            )
        if record.values["timeout_outcome"] != "fail_and_cooldown":
            errors.append(
                ImportErrorDetail(
                    code="pve_timeout_policy",
                    file="pve_scenarios.csv",
                    row=record.row_number,
                    record_id=record.values["scenario_id"],
                    message="PvE timeout must be fail_and_cooldown.",
                )
            )
    for record in tables["pve_combat_rules.csv"].rows:
        if _to_int(record.values["failure_cooldown_min"]) != 30:
            errors.append(
                ImportErrorDetail(
                    code="invalid_cooldown_window",
                    file="pve_combat_rules.csv",
                    row=record.row_number,
                    record_id=record.values["rule_id"],
                    message="PvE failure cooldown must be 30 minutes.",
                )
            )
    for record in tables["check_policies.csv"].rows:
        if record.values["die_policy"] != "single_d20" or record.values["no_rerolls"] != "true":
            errors.append(
                ImportErrorDetail(
                    code="invalid_check_policy",
                    file="check_policies.csv",
                    row=record.row_number,
                    record_id=record.values["policy_id"],
                    message="Check policy must use single_d20 and no rerolls.",
                )
            )
    return errors


def _validate_buildings_and_units(
    tables: dict[str, CsvTable], ids: dict[str, set[str]]
) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    graph: dict[str, list[str]] = {}
    for record in tables["buildings.csv"].rows:
        building_id = record.values["building_id"]
        graph[building_id] = split_ids(record.values["prerequisite_ids"])
        if record.values["branch"] not in VALID_BUILDING_BRANCHES:
            errors.append(
                ImportErrorDetail(
                    code="invalid_building_branch",
                    file="buildings.csv",
                    row=record.row_number,
                    record_id=building_id,
                    message=f"Unknown building branch {record.values['branch']}.",
                )
            )
        if _to_int(record.values["tier"]) not in {1, 2, 3, 4}:
            errors.append(
                ImportErrorDetail(
                    code="invalid_building_tier",
                    file="buildings.csv",
                    row=record.row_number,
                    record_id=building_id,
                    message="Building tier must be 1..4.",
                )
            )
        if _to_int(record.values["gold_cost"], default=-1) <= 0:
            errors.append(
                ImportErrorDetail(
                    code="invalid_gold_cost",
                    file="buildings.csv",
                    row=record.row_number,
                    record_id=building_id,
                    message="Building gold_cost must be positive.",
                )
            )

    errors.extend(_cycle_errors(graph, "buildings.csv", "building_cycle"))

    for record in tables["army_unit_cards.csv"].rows:
        card_id = record.values["card_id"]
        if record.values["unit_class"] not in VALID_UNIT_CLASSES:
            errors.append(
                ImportErrorDetail(
                    code="invalid_unit_class",
                    file="army_unit_cards.csv",
                    row=record.row_number,
                    record_id=card_id,
                    message=f"Invalid unit_class {record.values['unit_class']}.",
                )
            )
        for column in ("tier", "attack", "defense", "hp", "initiative", "move_range", "attack_range", "cost"):
            if _to_int(record.values[column], default=-1) < 0:
                errors.append(
                    ImportErrorDetail(
                        code="invalid_unit_value",
                        file="army_unit_cards.csv",
                        row=record.row_number,
                        record_id=card_id,
                        message=f"Unit {column} must be a non-negative integer.",
                    )
                )
    return errors


def _validate_orders(
    tables: dict[str, CsvTable], ids: dict[str, set[str]]
) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    status_rows = tables["order_status_rules.csv"].rows
    lock_statuses = {
        record.values["status_id"]
        for record in status_rows
        if _csv_bool(record.values.get("locks_object"))
    }
    cap_statuses = {
        record.values["status_id"]
        for record in status_rows
        if _csv_bool(record.values.get("counts_against_cap"))
    }
    object_locks: dict[tuple[str, str], str] = {}
    counts_by_lord_visibility: dict[tuple[str, str], int] = defaultdict(int)

    for record in tables["orders.csv"].rows:
        order_id = record.values["order_id"]
        visibility = record.values["visibility"]
        status = record.values["status"]
        if visibility not in VALID_ORDER_VISIBILITY:
            errors.append(
                ImportErrorDetail(
                    code="invalid_order_visibility",
                    file="orders.csv",
                    row=record.row_number,
                    record_id=order_id,
                    message=f"Invalid order visibility {visibility}.",
                )
            )
        if status not in ids["order_status_rules.csv"]:
            errors.append(
                ImportErrorDetail(
                    code="invalid_order_status",
                    file="orders.csv",
                    row=record.row_number,
                    record_id=order_id,
                    message=f"Unknown order status {status}.",
                )
            )
            continue
        if status in lock_statuses:
            key = (record.values["target_player_id"], record.values["object_id"])
            if key in object_locks:
                errors.append(
                    ImportErrorDetail(
                        code="order_object_conflict",
                        file="orders.csv",
                        row=record.row_number,
                        record_id=order_id,
                        message=(
                            "Duplicate active order object lock for "
                            f"{key[0]} / {key[1]} already held by {object_locks[key]}."
                        ),
                    )
                )
            object_locks[key] = order_id
        if status in cap_statuses:
            counts_by_lord_visibility[(record.values["lord_id"], visibility)] += 1

    for (lord_id, visibility), count in counts_by_lord_visibility.items():
        cap = 2 if visibility == "public" else 1 if visibility == "addressed" else 99
        if count > cap:
            errors.append(
                ImportErrorDetail(
                    code="order_cap",
                    file="orders.csv",
                    record_id=lord_id,
                    message=f"Lord {lord_id} has {count} active {visibility} orders; cap is {cap}.",
                )
            )
    return errors


def _validate_gwent(
    tables: dict[str, CsvTable], ids: dict[str, set[str]]
) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    rule = tables["gwent_rules.csv"].rows[0].values
    min_units = _to_int(rule["deck_min_unit_cards"])
    max_specials = _to_int(rule["max_special_cards"])
    cards = {record.values["card_id"]: record.values for record in tables["gwent_cards.csv"].rows}

    for record in tables["gwent_cards.csv"].rows:
        row = record.values["row"]
        card_type = record.values["type"]
        effect = record.values["effect"] or "none"
        if card_type == "leader" and row != "leader":
            errors.append(
                ImportErrorDetail(
                    code="gwent_card_invalid",
                    file="gwent_cards.csv",
                    row=record.row_number,
                    record_id=record.values["card_id"],
                    message="Leader cards must use leader row.",
                )
            )
        if card_type == "unit" and row not in {"melee", "ranged", "siege"}:
            errors.append(
                ImportErrorDetail(
                    code="gwent_card_invalid",
                    file="gwent_cards.csv",
                    row=record.row_number,
                    record_id=record.values["card_id"],
                    message="Unit cards must use a combat row.",
                )
            )
        if card_type not in {"unit", "special", "leader"}:
            errors.append(
                ImportErrorDetail(
                    code="gwent_card_invalid",
                    file="gwent_cards.csv",
                    row=record.row_number,
                    record_id=record.values["card_id"],
                    message=f"Unsupported Gwent card type {card_type}.",
                )
            )
        elif not is_gwent_effect_supported(card_type, effect):
            errors.append(
                ImportErrorDetail(
                    code="gwent_effect_unsupported",
                    file="gwent_cards.csv",
                    row=record.row_number,
                    record_id=record.values["card_id"],
                    message=(
                        f"Gwent effect {effect} on {card_type} card is not supported "
                        "by the Stage 1 runtime."
                    ),
                )
            )

    for record in tables["gwent_decks.csv"].rows:
        deck_id = record.values["deck_id"]
        leader = cards.get(record.values["leader_card_id"])
        deck_cards = [cards[card_id] for card_id in split_ids(record.values["card_ids"]) if card_id in cards]
        unit_count = sum(1 for card in deck_cards if card["type"] == "unit")
        special_count = sum(1 for card in deck_cards if card["type"] == "special")
        if not leader or leader["type"] != "leader":
            errors.append(
                ImportErrorDetail(
                    code="gwent_deck_invalid",
                    file="gwent_decks.csv",
                    row=record.row_number,
                    record_id=deck_id,
                    message="Gwent deck leader_card_id must reference a leader card.",
                )
            )
        if unit_count < min_units:
            errors.append(
                ImportErrorDetail(
                    code="gwent_deck_invalid",
                    file="gwent_decks.csv",
                    row=record.row_number,
                    record_id=deck_id,
                    message=f"Gwent deck has {unit_count} unit cards; minimum is {min_units}.",
                )
            )
        if special_count > max_specials:
            errors.append(
                ImportErrorDetail(
                    code="gwent_deck_invalid",
                    file="gwent_decks.csv",
                    row=record.row_number,
                    record_id=deck_id,
                    message=f"Gwent deck has {special_count} special cards; maximum is {max_specials}.",
                )
            )
    return errors


def _validate_trade_transfers(
    tables: dict[str, CsvTable], ids: dict[str, set[str]]
) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    asset_ids = (
        ids["items.csv"]
        | ids["cards.csv"]
        | ids["gwent_cards.csv"]
        | ids["artifacts.csv"]
        | ids["potions.csv"]
    )
    for record in tables["trade_transfers.csv"].rows:
        if record.values["from_player_id"] not in ids["players.csv"] or record.values["to_player_id"] not in ids["players.csv"]:
            errors.append(
                ImportErrorDetail(
                    code="trade_transfer_player",
                    file="trade_transfers.csv",
                    row=record.row_number,
                    record_id=record.values["transfer_id"],
                    message="Trade transfer players must exist.",
                )
            )
        if record.values["asset_id"] not in asset_ids:
            errors.append(
                ImportErrorDetail(
                    code="trade_transfer_asset",
                    file="trade_transfers.csv",
                    row=record.row_number,
                    record_id=record.values["transfer_id"],
                    message=f"Trade transfer references unknown asset {record.values['asset_id']}.",
                )
            )
        if record.values["status"] not in {"pending_locked", "accepted", "rejected", "cancelled"}:
            errors.append(
                ImportErrorDetail(
                    code="trade_transfer_lock_rule",
                    file="trade_transfers.csv",
                    row=record.row_number,
                    record_id=record.values["transfer_id"],
                    message="Trade transfer status must preserve two-confirmation lock semantics.",
                )
            )
    return errors


def _validate_lord_battle_rules(tables: dict[str, CsvTable]) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    default_rule_seen = False
    for record in tables["lord_battle_rules.csv"].rows:
        rule_id = record.values["rule_id"]
        if rule_id == "lord_battle_default":
            default_rule_seen = True
        for column, expected_value in CANONICAL_LORD_BATTLE_RULES.items():
            if record.values[column] != expected_value:
                errors.append(
                    ImportErrorDetail(
                        code="invalid_lord_battle_rule",
                        file="lord_battle_rules.csv",
                        row=record.row_number,
                        record_id=rule_id,
                        message=(
                            f"Lord battle {column} must be {expected_value}, "
                            f"got {record.values[column]}."
                        ),
                    )
                )
    if not default_rule_seen:
        errors.append(
            ImportErrorDetail(
                code="invalid_lord_battle_rule",
                file="lord_battle_rules.csv",
                message="lord_battle_default rule is required for runtime battle setup.",
            )
        )
    return errors


def _validate_rules_and_final(
    tables: dict[str, CsvTable], ids: dict[str, set[str]]
) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    cascade_reward_reasons = _cascade_reward_reasons(tables)
    for record in tables["rewards.csv"].rows:
        if record.values["approval_policy"] not in VALID_REWARD_POLICIES:
            errors.append(
                ImportErrorDetail(
                    code="reward_approval_policy",
                    file="rewards.csv",
                    row=record.row_number,
                    record_id=record.values["reward_id"],
                    message=f"Unknown reward approval policy {record.values['approval_policy']}.",
                )
            )
        reward_id = record.values["reward_id"]
        cascade_reasons = cascade_reward_reasons.get(reward_id, set())
        if (
            record.values["rarity"] in {"Rare", "Legendary"}
            or record.values["artifact_ids"]
            or cascade_reasons
        ) and record.values["approval_policy"] != "pending_master_approval":
            reason_text = (
                f" Cascade markers: {', '.join(sorted(cascade_reasons))}."
                if cascade_reasons
                else ""
            )
            errors.append(
                ImportErrorDetail(
                    code="reward_approval_policy",
                    file="rewards.csv",
                    row=record.row_number,
                    record_id=reward_id,
                    message=(
                        "Rare, legendary, artifact or cascade-prone rewards must require "
                        f"master approval.{reason_text}"
                    ),
                )
            )

    for record in tables["challenge_tokens.csv"].rows:
        if _to_int(record.values["tokens_per_player"]) != 3 or _to_int(record.values["start_window_min"]) != 30:
            errors.append(
                ImportErrorDetail(
                    code="invalid_token_window",
                    file="challenge_tokens.csv",
                    row=record.row_number,
                    record_id=record.values["token_rule_id"],
                    message="Challenge tokens must grant 3 tokens with a 30-minute start window.",
                )
            )

    for record in tables["pvp_throttle_rules.csv"].rows:
        if record.values["mode"] not in VALID_PVP_THROTTLE_MODES:
            errors.append(
                ImportErrorDetail(
                    code="invalid_pvp_throttle",
                    file="pvp_throttle_rules.csv",
                    row=record.row_number,
                    record_id=record.values["rule_id"],
                    message=f"Invalid PvP throttle mode {record.values['mode']}.",
                )
            )

    covered_reputation = {
        value
        for record in tables["reputation_rules.csv"].rows
        for value in range(_to_int(record.values["min_value"]), _to_int(record.values["max_value"]) + 1)
    }
    if covered_reputation != set(range(-5, 6)):
        errors.append(
            ImportErrorDetail(
                code="invalid_reputation_range",
                file="reputation_rules.csv",
                message="Reputation rules must cover exactly -5..+5.",
            )
        )

    for record in tables["xp_rules.csv"].rows:
        if record.values["stat_gain_rule"] != "+1_stat_per_level" or _to_int(record.values["max_stat"]) != 7:
            errors.append(
                ImportErrorDetail(
                    code="invalid_xp_rule",
                    file="xp_rules.csv",
                    row=record.row_number,
                    record_id=record.values["rule_id"],
                    message="XP rule must use +1_stat_per_level with max stat 7.",
                )
            )

    for record in tables["spells.csv"].rows:
        if not record.values["counterplay"]:
            errors.append(
                ImportErrorDetail(
                    code="invalid_spell_counterplay",
                    file="spells.csv",
                    row=record.row_number,
                    record_id=record.values["spell_id"],
                    message="Spells must define counterplay.",
                )
            )

    favorite_rule = tables["favorite_rules.csv"].rows[0].values
    if favorite_rule["passive_bonus_allowed"] != "false":
        errors.append(
            ImportErrorDetail(
                code="favorite_lifecycle",
                file="favorite_rules.csv",
                row=2,
                record_id=favorite_rule["rule_id"],
                message="Favorites must not grant passive bonuses.",
            )
        )
    for record in tables["favorites.csv"].rows:
        if record.values["slot"] not in VALID_FAVORITE_SLOTS:
            errors.append(
                ImportErrorDetail(
                    code="favorite_lifecycle",
                    file="favorites.csv",
                    row=record.row_number,
                    record_id=record.values["favorite_id"],
                    message=f"Invalid favorite slot {record.values['slot']}.",
                )
            )

    final_summary = tables["final_summary.csv"].rows[0].values
    if (
        final_summary["tournament_mode"] != "npc_led_tournament"
        or final_summary["automatic_winner_calculation"] != "false"
        or final_summary["export_snapshot_required"] != "true"
    ):
        errors.append(
            ImportErrorDetail(
                code="final_summary_fields",
                file="final_summary.csv",
                row=2,
                record_id=final_summary["summary_id"],
                message="Final summary must be NPC-led, exportable and must not auto-calculate a winner.",
            )
        )
    procedure = tables["final_procedures.csv"].rows[0].values
    if _to_int(procedure["start_offset_min"]) != 450 or _to_int(procedure["end_offset_min"]) != 570:
        errors.append(
            ImportErrorDetail(
                code="final_summary_fields",
                file="final_procedures.csv",
                row=2,
                record_id=procedure["procedure_id"],
                message="Final Act procedure must cover the 7:30-9:30 window.",
            )
        )
    if _to_int(procedure["station_count"], default=0) < 2 or procedure["master_role"] != "npc_master_pair":
        errors.append(
            ImportErrorDetail(
                code="final_summary_fields",
                file="final_procedures.csv",
                row=2,
                record_id=procedure["procedure_id"],
                message="Final Act procedure must include station staffing for the NPC master pair.",
            )
        )
    return errors


def _cascade_reward_reasons(tables: dict[str, CsvTable]) -> dict[str, set[str]]:
    reasons: dict[str, set[str]] = defaultdict(set)
    item_rows = {
        record.values["item_id"]: record
        for record in tables["items.csv"].rows
    }

    for record in tables["pve_scenarios.csv"].rows:
        scene_type = record.values["scene_type"]
        reward_id = record.values["reward_id"]
        if scene_type in CASCADE_PVE_SCENE_TYPES:
            reasons[reward_id].add(f"pve_scenarios.scene_type={scene_type}")

    for record in tables["orders.csv"].rows:
        reward_id = record.values["escrow_reward_id"]
        if reward_id:
            reasons[reward_id].add("orders.escrow_reward_id")

    for record in tables["pending_tick_rewards.csv"].rows:
        reward_id = record.values["reward_id"]
        if reward_id:
            reasons[reward_id].add("pending_tick_rewards.reward_id")

    for record in tables["rewards.csv"].rows:
        reward_id = record.values["reward_id"]
        for item_id in split_ids(record.values["item_ids"]):
            item = item_rows.get(item_id)
            if item is None:
                continue
            item_type = item.values["item_type"]
            if item_type in CASCADE_ITEM_TYPES:
                reasons[reward_id].add(f"items.item_type={item_type}")
            if _has_cascade_effect_marker(item.values["effect_json"]):
                reasons[reward_id].add(f"items.effect_json={item_id}")
    return reasons


def _has_cascade_effect_marker(raw_json: str) -> bool:
    try:
        parsed = json.loads(raw_json or "{}")
    except json.JSONDecodeError:
        parsed = raw_json
    return _value_has_cascade_marker(parsed)


def _value_has_cascade_marker(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            _value_has_cascade_marker(key) or _value_has_cascade_marker(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_value_has_cascade_marker(item) for item in value)
    if isinstance(value, str):
        normalized = value.lower()
        return any(marker in normalized for marker in CASCADE_EFFECT_MARKERS)
    return False


def _validate_master_ops_readiness(tables: dict[str, CsvTable]) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []

    announced_act_ids = {
        record.values["act_id"] for record in tables["physical_announcements.csv"].rows
    }
    for record in tables["acts.csv"].rows:
        act_id = record.values["act_id"]
        if record.values["act_type"] not in {"story", "final"}:
            continue
        if act_id not in announced_act_ids:
            errors.append(
                ImportErrorDetail(
                    code="physical_announcement_coverage",
                    file="physical_announcements.csv",
                    record_id=act_id,
                    message=f"Missing physical announcement plan for {act_id}.",
                )
            )

    qr_policy_ready = any(
        record.values["physical_presence_required"] == "true"
        and record.values["manual_entry_allowed"] == "true"
        and record.values["suspected_violation_outcome"] == "needs_master_review"
        for record in tables["qr_policies.csv"].rows
    )
    if not qr_policy_ready:
        errors.append(
            ImportErrorDetail(
                code="qr_honesty_policy",
                file="qr_policies.csv",
                message=(
                    "QR policy must require physical presence, allow manual fallback "
                    "and route suspected violations to master review."
                ),
            )
        )

    handout_audiences = {
        record.values["audience"] for record in tables["player_handouts.csv"].rows
    }
    missing_audiences = sorted(REQUIRED_HANDOUT_AUDIENCES - handout_audiences)
    if missing_audiences:
        errors.append(
            ImportErrorDetail(
                code="handout_readiness",
                file="player_handouts.csv",
                message=f"Missing player handout audience(s): {', '.join(missing_audiences)}.",
            )
        )
    common_handout = next(
        (
            record
            for record in tables["player_handouts.csv"].rows
            if record.values["audience"] == "all"
        ),
        None,
    )
    common_topics = (
        set(split_ids(common_handout.values["required_topics"])) if common_handout else set()
    )
    missing_common_topics = sorted(REQUIRED_COMMON_HANDOUT_TOPICS - common_topics)
    if missing_common_topics:
        errors.append(
            ImportErrorDetail(
                code="handout_readiness",
                file="player_handouts.csv",
                row=common_handout.row_number if common_handout else None,
                record_id=common_handout.values["handout_id"] if common_handout else None,
                message=(
                    "Common player handout must cover "
                    f"{', '.join(missing_common_topics)}."
                ),
            )
        )

    pvp_safety_ready = any(
        record.values["reason"] == "safety_stop"
        and record.values["severity"] == "P0"
        and record.values["default_outcome"] == "needs_master_review"
        for record in tables["pvp_refusal_rules.csv"].rows
    )
    if not pvp_safety_ready:
        errors.append(
            ImportErrorDetail(
                code="pvp_refusal_safety",
                file="pvp_refusal_rules.csv",
                message="PvP refusal/safety table must include a P0 safety_stop master review path.",
            )
        )

    potion_market_ready = any(
        record.values["seller_role"] == "sorceress" and _to_int(record.values["stock"], default=0) > 0
        for record in tables["potion_markets.csv"].rows
    )
    if not potion_market_ready:
        errors.append(
            ImportErrorDetail(
                code="potion_market_access",
                file="potion_markets.csv",
                message="Potion wholesale market must be accessible to sorceresses with positive stock.",
            )
        )

    anti_snowball_cuts = {
        _to_int(record.values["income_cut_percent"], default=-1)
        for record in tables["anti_snowball_rules.csv"].rows
        if _to_int(record.values["army_power_ratio_threshold"], default=0) > 0
    }
    if not {30, 50}.issubset(anti_snowball_cuts):
        errors.append(
            ImportErrorDetail(
                code="anti_snowball_threshold",
                file="anti_snowball_rules.csv",
                message="Anti-snowball rules must include 30 and 50 percent income cuts.",
            )
        )

    return errors


def _validate_paper_forms(tables: dict[str, CsvTable]) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    required_fields = {
        "paper_form_id",
        "source_form_type",
        "operator",
        "timestamp",
        "reason",
        "conflict_status",
    }
    for record in tables["paper_forms.csv"].rows:
        try:
            fields = set(json.loads(record.values["required_fields_json"]))
        except json.JSONDecodeError as exc:
            errors.append(
                ImportErrorDetail(
                    code="paper_conflict_policy",
                    file="paper_forms.csv",
                    row=record.row_number,
                    record_id=record.values["form_type"],
                    message=f"Paper form required_fields_json is invalid JSON: {exc.msg}.",
                )
            )
            continue
        if not required_fields.issubset(fields) or record.values["conflict_policy"] != "review_conflict_no_silent_overwrite":
            errors.append(
                ImportErrorDetail(
                    code="paper_conflict_policy",
                    file="paper_forms.csv",
                    row=record.row_number,
                    record_id=record.values["form_type"],
                    message="Paper recovery must include audit fields and conflict review, never silent overwrite.",
                )
            )
    return errors


def _cycle_errors(
    graph: dict[str, list[str]], file_name: str, code: str
) -> list[ImportErrorDetail]:
    errors: list[ImportErrorDetail] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            errors.append(
                ImportErrorDetail(
                    code=code,
                    file=file_name,
                    record_id=node,
                    message=f"Cycle detected: {' -> '.join(path + [node])}.",
                )
            )
            return
        visiting.add(node)
        for dependency in graph.get(node, []):
            visit(dependency, path + [node])
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node, [])
    return errors


def _to_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
