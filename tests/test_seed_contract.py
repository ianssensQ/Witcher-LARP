from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import unittest

from backend.witcher_larp.config import PROJECT_ROOT


SEED_ROOT = PROJECT_ROOT / "data" / "seed"
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures"
CANONICAL_STATS = {"Сила", "Ловкость", "Разум", "Харизма", "Воля"}


REQUIRED_HEADERS = {
    "profiles.csv": [
        "profile_id",
        "total_people",
        "player_count",
        "npc_master_count",
        "lord_count",
        "sorceress_count",
        "witcher_count",
    ],
    "players.csv": [
        "player_id",
        "role_type",
        "display_name",
        "lord_id",
        "sorceress_start_lord_id",
        "level",
        "xp",
        "gold",
        "reputation",
        "stats_json",
        "player_code_id",
    ],
    "player_codes.csv": ["code_id", "player_id", "code", "enabled"],
    "role_tokens.csv": ["token_id", "role_type", "owner_id", "token", "enabled"],
    "acts.csv": [
        "act_id",
        "sequence",
        "act_type",
        "name",
        "start_offset_min",
        "end_offset_min",
        "buffer_after_min",
        "unlock_required",
        "physical_announcement_required",
    ],
    "act_unlock_codes.csv": ["unlock_id", "act_id", "code", "revealed_after_start"],
    "physical_announcements.csv": [
        "announcement_id",
        "act_id",
        "required_signal",
        "operator_role",
    ],
    "auto_timers.csv": [
        "timer_id",
        "act_id",
        "timer_type",
        "offset_min",
        "interval_min",
        "effect_type",
    ],
    "domains.csv": [
        "domain_id",
        "lord_player_id",
        "name",
        "starting_gold",
        "base_income",
    ],
    "venue_map_profiles.csv": [
        "profile_id",
        "name",
        "active_house_status",
        "old_house_status",
        "adjacent_shed_status",
        "notes",
    ],
    "map_nodes.csv": ["node_id", "name", "node_type", "zone_status", "territory_id"],
    "map_edges.csv": [
        "edge_id",
        "from_node_id",
        "to_node_id",
        "mp_cost",
        "bidirectional",
    ],
    "territories.csv": [
        "territory_id",
        "name",
        "owner_domain_id",
        "bonus_type",
        "tier",
        "neutral_defense_profile_id",
    ],
    "territory_forts.csv": [
        "fort_id",
        "territory_id",
        "name",
        "theme",
        "garrison_capacity",
        "art_prompt_id",
        "background_asset_id",
        "card_asset_id",
    ],
    "movement_rules.csv": [
        "rule_id",
        "mp_cap",
        "refill_interval_min",
        "refill_amount",
    ],
    "movement_pools.csv": [
        "pool_id",
        "domain_id",
        "act_id",
        "current_mp",
        "mp_cap",
        "last_refill_offset_min",
    ],
    "territory_claims.csv": [
        "claim_id",
        "territory_id",
        "claimant_domain_id",
        "status",
        "claimed_at_offset_min",
        "source",
    ],
    "pending_tick_rewards.csv": [
        "pending_reward_id",
        "domain_id",
        "territory_id",
        "reward_id",
        "status",
        "unlock_offset_min",
    ],
    "army_reserves.csv": ["reserve_id", "domain_id", "card_id", "count", "status"],
    "garrisons.csv": [
        "garrison_id",
        "territory_id",
        "domain_id",
        "card_id",
        "count",
        "status",
    ],
    "buildings.csv": [
        "building_id",
        "branch",
        "name",
        "tier",
        "gold_cost",
        "prerequisite_ids",
        "recruit_unlock_ids",
        "capacity_delta",
        "raid_unlock",
    ],
    "army_unit_cards.csv": [
        "card_id",
        "unit_class",
        "tier",
        "attack",
        "defense",
        "hp",
        "initiative",
        "move_range",
        "attack_range",
        "cost",
        "source_id",
    ],
    "recruit_markets.csv": [
        "offer_id",
        "domain_id",
        "card_id",
        "cost",
        "status",
        "refresh_rule",
    ],
    "cards.csv": [
        "card_id",
        "card_type",
        "tier",
        "name",
        "army_unit_card_id",
        "conversion_rule",
    ],
    "mobs.csv": [
        "mob_id",
        "tier",
        "scene_hp",
        "combat_dc",
        "scene_damage",
        "round_limit",
        "special_rule",
    ],
    "rewards.csv": [
        "reward_id",
        "xp",
        "gold",
        "item_ids",
        "card_ids",
        "artifact_ids",
        "rarity",
        "approval_policy",
    ],
    "reward_approval_rules.csv": [
        "rule_id",
        "reward_type",
        "default_status",
        "locks_assets",
    ],
    "items.csv": [
        "item_id",
        "item_type",
        "tier",
        "stat_requirement_json",
        "effect_json",
    ],
    "qr_policies.csv": [
        "policy_id",
        "physical_presence_required",
        "manual_entry_allowed",
        "manual_rate_limit",
        "suspected_violation_outcome",
    ],
    "check_policies.csv": [
        "policy_id",
        "die_policy",
        "modifier_sources",
        "no_rerolls",
        "log_required",
    ],
    "pve_combat_rules.csv": [
        "rule_id",
        "player_scene_hp",
        "base_damage",
        "no_persistent_player_hp",
        "timeout_outcome",
        "failure_cooldown_min",
    ],
    "pve_scenarios.csv": [
        "scenario_id",
        "act_id",
        "tier",
        "scene_type",
        "primary_stat",
        "dc",
        "check_policy",
        "combat_profile_id",
        "reward_id",
        "success_text",
        "failure_text",
        "timeout_outcome",
    ],
    "qr_objects.csv": [
        "qr_id",
        "manual_code",
        "scenario_id",
        "qr_mode",
        "act_id",
        "location_node_id",
        "physical_presence_required",
        "rate_limit",
        "consumption_rule",
    ],
    "gwent_rules.csv": [
        "rule_id",
        "deck_min_unit_cards",
        "max_special_cards",
        "hand_size",
        "mulligans",
        "row_count",
        "tie_handling",
    ],
    "gwent_cards.csv": [
        "card_id",
        "faction",
        "row",
        "type",
        "strength",
        "effect",
        "rarity",
    ],
    "gwent_decks.csv": ["deck_id", "player_id", "leader_card_id", "card_ids"],
    "gwent_matches.csv": [
        "match_id",
        "challenger_id",
        "target_id",
        "status",
        "stake_json",
    ],
    "challenge_tokens.csv": [
        "token_rule_id",
        "act_id",
        "tokens_per_player",
        "start_window_min",
    ],
    "pvp_tables.csv": ["table_id", "status", "zone_name"],
    "pvp_throttle_rules.csv": [
        "rule_id",
        "mode",
        "max_tables",
        "max_started_per_player_per_act",
        "final_lock_behavior",
    ],
    "pvp_refusal_rules.csv": ["rule_id", "reason", "severity", "default_outcome"],
    "trade_transfers.csv": [
        "transfer_id",
        "from_player_id",
        "to_player_id",
        "asset_type",
        "asset_id",
        "status",
    ],
    "orders.csv": [
        "order_id",
        "lord_id",
        "target_player_id",
        "object_id",
        "visibility",
        "status",
        "escrow_reward_id",
    ],
    "order_status_rules.csv": [
        "status_id",
        "is_active",
        "locks_object",
        "counts_against_cap",
        "next_statuses",
    ],
    "potions.csv": [
        "potion_id",
        "rarity",
        "wholesale_cost",
        "resale_min",
        "resale_max",
        "effect_json",
    ],
    "potion_markets.csv": [
        "market_id",
        "seller_role",
        "potion_id",
        "stock",
        "refresh_rule",
    ],
    "spells.csv": [
        "spell_id",
        "tier",
        "role",
        "cost_mana",
        "target_type",
        "effect_json",
        "counterplay",
    ],
    "artifacts.csv": [
        "artifact_id",
        "rarity",
        "act_cap",
        "visibility",
        "power_budget",
        "counterplay",
    ],
    "rarity_rules.csv": [
        "rule_id",
        "asset_type",
        "rarity",
        "total_cap",
        "act_cap",
        "earliest_act",
        "visibility",
        "power_budget",
        "counterplay",
    ],
    "raid_rules.csv": [
        "rule_id",
        "name",
        "tier",
        "category",
        "description",
        "token_cost",
        "gold_cost",
        "duration_min",
        "resistance_check",
        "loot_policy",
        "effect_type",
        "allowed_target_types",
        "required_building_ids",
        "visibility",
        "counterplay",
    ],
    "anti_snowball_rules.csv": [
        "rule_id",
        "army_power_ratio_threshold",
        "income_cut_percent",
        "notes",
    ],
    "diplomacy_signals.csv": [
        "signal_id",
        "trigger_type",
        "visible_to",
        "effect",
        "notes",
    ],
    "xp_rules.csv": [
        "rule_id",
        "source",
        "xp_min",
        "xp_max",
        "stat_gain_rule",
        "max_stat",
        "level_thresholds",
    ],
    "balance_defaults.csv": [
        "rule_id",
        "xp_thresholds",
        "pve_dc_tiers",
        "reward_gold_tiers",
        "reward_xp_tiers",
        "lord_starting_gold",
        "lord_base_income",
        "lord_hp_formula",
        "mana_max_formula",
        "mana_regen_formula",
        "spell_costs",
    ],
    "lord_battle_rules.csv": [
        "rule_id",
        "grid_width",
        "grid_height",
        "turn_timer_seconds",
        "damage_formula",
        "initiative_tiebreaker",
        "timeout_policy",
        "auto_resolve_policy",
    ],
    "personal_goals.csv": [
        "goal_id",
        "player_id",
        "act_id",
        "public_text",
        "progress_type",
        "final_hook_id",
    ],
    "goal_tracks.csv": [
        "track_id",
        "goal_id",
        "state",
        "current_value",
        "target_value",
        "visibility",
    ],
    "goal_flags.csv": ["flag_id", "goal_id", "flag_key", "value", "visibility"],
    "final_hooks.csv": [
        "final_hook_id",
        "role_category",
        "evidence_category",
        "summary_text",
    ],
    "reputation_rules.csv": [
        "rule_id",
        "min_value",
        "max_value",
        "label",
        "player_descriptor",
        "master_visibility",
    ],
    "npc_events.csv": [
        "event_id",
        "npc_role",
        "event_type",
        "target_id",
        "price_json",
        "consequence_json",
        "severity",
    ],
    "review_severity_rules.csv": [
        "severity",
        "meaning",
        "response_window",
        "default_owner",
    ],
    "favorite_rules.csv": [
        "rule_id",
        "max_primary",
        "max_secondary",
        "max_sorceresses_per_favored",
        "change_limit_per_act",
        "passive_bonus_allowed",
    ],
    "favorites.csv": [
        "favorite_id",
        "sorceress_id",
        "favored_player_id",
        "slot",
        "status",
        "changed_in_act",
    ],
    "sorceress_alignment_rules.csv": ["rule_id", "alignment_state", "evidence_required"],
    "final_summary_fields.csv": [
        "field_id",
        "source_type",
        "evidence_category",
        "visibility",
        "required_for_export",
    ],
    "final_procedures.csv": [
        "procedure_id",
        "final_act_window",
        "start_offset_min",
        "end_offset_min",
        "station_count",
        "master_role",
    ],
    "final_summary.csv": [
        "summary_id",
        "final_act_id",
        "tournament_mode",
        "winner_policy",
        "includes_missing_locks",
        "includes_pending_disputes",
        "includes_npc_prices",
        "includes_locked_magical_intent",
        "export_snapshot_required",
        "automatic_winner_calculation",
    ],
    "paper_forms.csv": [
        "form_type",
        "required_fields_json",
        "recovery_event_type",
        "conflict_policy",
    ],
    "backup_jobs.csv": ["job_id", "trigger_type", "include_sqlite", "include_event_log"],
    "player_handouts.csv": ["handout_id", "audience", "required_topics"],
    "ops_checklists.csv": ["item_id", "phase", "owner_role", "required"],
}


def split_ids(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


class SeedContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = {name: cls.load_csv(name) for name in REQUIRED_HEADERS}

    @staticmethod
    def load_csv(name: str) -> list[dict[str, str]]:
        path = SEED_ROOT / name
        if not path.exists():
            raise AssertionError(f"Missing seed CSV: {path}")
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            expected = REQUIRED_HEADERS[name]
            if reader.fieldnames != expected:
                raise AssertionError(
                    f"{name} headers differ.\nExpected: {expected}\nActual: {reader.fieldnames}"
                )
            rows = list(reader)
        for index, row in enumerate(rows, start=2):
            if None in row:
                raise AssertionError(f"{name}:{index} has extra CSV columns: {row[None]}")
        return rows

    def ids(self, name: str, column: str) -> set[str]:
        return {row[column] for row in self.rows[name]}

    def test_required_csv_files_exist_and_have_rows(self) -> None:
        for name, rows in self.rows.items():
            with self.subTest(csv=name):
                self.assertGreater(len(rows), 0, f"{name} must not be empty")

        self.assertTrue((PROJECT_ROOT / "data" / "snapshots").exists())
        self.assertTrue((PROJECT_ROOT / "data" / "backups").exists())

    def test_production_profile_players_codes_and_tokens(self) -> None:
        profile = self.rows["profiles.csv"][0]
        self.assertEqual(profile["profile_id"], "production_15")
        self.assertEqual(int(profile["total_people"]), 15)
        self.assertEqual(int(profile["player_count"]), 13)
        self.assertEqual(int(profile["npc_master_count"]), 2)

        role_counts = Counter(row["role_type"] for row in self.rows["players.csv"])
        self.assertEqual(role_counts["lord"], 4)
        self.assertEqual(role_counts["sorceress"], 4)
        self.assertEqual(role_counts["witcher"], 5)

        player_ids = self.ids("players.csv", "player_id")
        code_player_ids = self.ids("player_codes.csv", "player_id")
        self.assertEqual(player_ids, code_player_ids)

        player_code_ids = self.ids("player_codes.csv", "code_id")
        for player in self.rows["players.csv"]:
            self.assertIn(player["player_code_id"], player_code_ids)
            stats = json.loads(player["stats_json"])
            self.assertEqual(set(stats), CANONICAL_STATS)
            self.assertEqual(sum(stats.values()), 7)
            self.assertLessEqual(max(stats.values()), 3)

        token_roles = Counter(row["role_type"] for row in self.rows["role_tokens.csv"])
        self.assertEqual(token_roles["lord"], 4)
        self.assertEqual(token_roles["npc_master"], 2)

    def test_qr_content_mix_and_pve_references(self) -> None:
        qr_rows = self.rows["qr_objects.csv"]
        mode_counts = Counter(row["qr_mode"] for row in qr_rows)
        act_counts = Counter(row["act_id"] for row in qr_rows)
        self.assertEqual(len(qr_rows), 40)
        self.assertGreaterEqual(
            mode_counts["repeatable_scene"] + mode_counts["always_available_scene"],
            15,
        )
        self.assertGreaterEqual(mode_counts["unique_object"], 25)
        self.assertEqual(act_counts, {"act1": 12, "act2": 14, "act3": 14})
        self.assertEqual(len({row["manual_code"] for row in qr_rows}), len(qr_rows))

        valid_modes = {"unique_object", "repeatable_scene", "always_available_scene"}
        scenario_ids = self.ids("pve_scenarios.csv", "scenario_id")
        node_ids = self.ids("map_nodes.csv", "node_id")
        excluded_nodes = {
            row["node_id"]
            for row in self.rows["map_nodes.csv"]
            if row["zone_status"] == "no_play_excluded"
        }
        for row in qr_rows:
            self.assertIn(row["qr_mode"], valid_modes)
            self.assertIn(row["scenario_id"], scenario_ids)
            self.assertIn(row["location_node_id"], node_ids)
            self.assertNotIn(row["location_node_id"], excluded_nodes)
            self.assertEqual(row["physical_presence_required"], "true")
            self.assertRegex(row["manual_code"], r"^QR-A[123]-[A-Z0-9]{4}$")

        reward_ids = self.ids("rewards.csv", "reward_id")
        mob_ids = self.ids("mobs.csv", "mob_id")
        check_policy_ids = self.ids("check_policies.csv", "policy_id")
        for scenario in self.rows["pve_scenarios.csv"]:
            self.assertIn(scenario["primary_stat"], CANONICAL_STATS)
            self.assertIn(scenario["reward_id"], reward_ids)
            self.assertIn(scenario["combat_profile_id"], mob_ids)
            self.assertIn(scenario["check_policy"], check_policy_ids)
            self.assertEqual(scenario["timeout_outcome"], "fail_and_cooldown")

    def test_lord_map_strategy_and_no_play_exclusions(self) -> None:
        domains = self.rows["domains.csv"]
        self.assertEqual(len(domains), 4)
        for domain in domains:
            self.assertEqual(int(domain["starting_gold"]), 80)
            self.assertEqual(int(domain["base_income"]), 25)

        excluded_nodes = {
            row["node_id"]
            for row in self.rows["map_nodes.csv"]
            if row["zone_status"] == "no_play_excluded"
        }
        edge_nodes = {
            node
            for edge in self.rows["map_edges.csv"]
            for node in (edge["from_node_id"], edge["to_node_id"])
        }
        self.assertTrue({"node_old_house", "node_adjacent_shed"}.issubset(excluded_nodes))
        self.assertTrue(excluded_nodes.isdisjoint(edge_nodes))

        owned = [row for row in self.rows["territories.csv"] if row["owner_domain_id"]]
        self.assertEqual(len(owned), 4)
        self.assertTrue(all(row["bonus_type"] == "residence" for row in owned))

        capturable = [
            row for row in self.rows["territories.csv"] if row["bonus_type"] != "residence"
        ]
        self.assertEqual(len(capturable), 19)
        capturable_ids = {row["territory_id"] for row in capturable}
        playable_ids = {row["territory_id"] for row in self.rows["territories.csv"]}
        fort_territory_ids = {
            row["territory_id"] for row in self.rows["territory_forts.csv"]
        }
        self.assertEqual(fort_territory_ids, playable_ids)
        self.assertEqual(
            Counter(row["node_type"] for row in self.rows["map_nodes.csv"])["mountain"],
            3,
        )
        self.assertTrue(
            {
                "territory_mountain_north_alpine",
                "territory_mountain_gray",
                "territory_mountain_west_alpine",
            }.issubset(capturable_ids)
        )
        forts_by_territory = {
            fort["territory_id"]: fort for fort in self.rows["territory_forts.csv"]
        }
        for territory in self.rows["territories.csv"]:
            fort = forts_by_territory[territory["territory_id"]]
            capacity = int(fort["garrison_capacity"])
            self.assertGreaterEqual(capacity, 5)
            self.assertLessEqual(capacity, 8)

        self.assertEqual(len(self.rows["movement_pools.csv"]), 4)
        self.assertTrue(self.rows["pending_tick_rewards.csv"])
        self.assertTrue(self.rows["army_reserves.csv"])
        self.assertTrue(self.rows["garrisons.csv"])
        self.assertEqual(
            {row["income_cut_percent"] for row in self.rows["anti_snowball_rules.csv"]},
            {"30", "50"},
        )
        self.assertTrue(self.rows["raid_rules.csv"])
        self.assertTrue(self.rows["diplomacy_signals.csv"])

    def test_buildings_units_and_card_conversion(self) -> None:
        required_buildings = {
            "Учебный двор",
            "Казармы",
            "Стрельбище",
            "Конюшни",
            "Осадный двор",
            "Военная академия",
            "Рынок",
            "Налоговая палата",
            "Склад",
            "Банк",
            "Казначейский зал",
            "Доска объявлений",
            "Посольский зал",
            "Картографическая",
            "Рейдовая ставка",
            "Военный совет",
            "Кабинет мага",
            "Алхимическая лаборатория",
            "Комната видений",
            "Обереги",
            "Ритуальная палата",
        }
        self.assertEqual({row["name"] for row in self.rows["buildings.csv"]}, required_buildings)

        graph = {
            row["building_id"]: split_ids(row["prerequisite_ids"])
            for row in self.rows["buildings.csv"]
        }
        self.assert_no_cycles(graph)
        self.assertEqual(
            {
                row["building_id"]: int(row["gold_cost"])
                for row in self.rows["buildings.csv"]
            },
            {
                row["building_id"]: {1: 40, 2: 75, 3: 120, 4: 180}[int(row["tier"])]
                for row in self.rows["buildings.csv"]
            },
        )

        unit_classes = {row["unit_class"] for row in self.rows["army_unit_cards.csv"]}
        self.assertEqual(
            unit_classes,
            {"infantry", "guard", "ranged", "cavalry", "heavy_siege", "specialist"},
        )
        unit_source_by_card = {
            row["card_id"]: row["source_id"] for row in self.rows["army_unit_cards.csv"]
        }
        recruit_sources = {
            card_id: row["building_id"]
            for row in self.rows["buildings.csv"]
            for card_id in split_ids(row["recruit_unlock_ids"])
        }
        self.assertEqual(recruit_sources, unit_source_by_card)

        unit_ids = self.ids("army_unit_cards.csv", "card_id")
        for card in self.rows["cards.csv"]:
            self.assertIn(card["army_unit_card_id"], unit_ids)

    def assert_no_cycles(self, graph: dict[str, list[str]]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                raise AssertionError(f"Building prerequisite cycle at {node}")
            visiting.add(node)
            for dependency in graph.get(node, []):
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)

    def test_gwent_pvp_trade_and_order_contracts(self) -> None:
        gwent_rules = self.rows["gwent_rules.csv"][0]
        self.assertEqual(int(gwent_rules["deck_min_unit_cards"]), 22)
        self.assertEqual(int(gwent_rules["max_special_cards"]), 10)
        self.assertEqual(int(gwent_rules["hand_size"]), 10)
        self.assertEqual(int(gwent_rules["mulligans"]), 2)
        self.assertEqual(int(gwent_rules["row_count"]), 3)

        cards = {row["card_id"]: row for row in self.rows["gwent_cards.csv"]}
        rare_cards = [row for row in cards.values() if row["rarity"] == "Rare"]
        self.assertEqual(len(rare_cards), 6)
        deck = self.rows["gwent_decks.csv"][0]
        deck_cards = [cards[card_id] for card_id in split_ids(deck["card_ids"])]
        self.assertGreaterEqual(
            sum(1 for card in deck_cards if card["type"] == "unit"),
            22,
        )
        self.assertLessEqual(
            sum(1 for card in deck_cards if card["type"] == "special"),
            10,
        )
        self.assertEqual(cards[deck["leader_card_id"]]["type"], "leader")
        pvp_player_ids = {
            row["player_id"]
            for row in self.rows["players.csv"]
            if row["role_type"] in {"witcher", "sorceress"}
        }
        deck_player_ids = {row["player_id"] for row in self.rows["gwent_decks.csv"]}
        self.assertEqual(pvp_player_ids, deck_player_ids)
        for deck in self.rows["gwent_decks.csv"]:
            with self.subTest(deck=deck["deck_id"]):
                deck_cards = [cards[card_id] for card_id in split_ids(deck["card_ids"])]
                self.assertGreaterEqual(
                    sum(1 for card in deck_cards if card["type"] == "unit"),
                    22,
                )
                self.assertLessEqual(
                    sum(1 for card in deck_cards if card["type"] == "special"),
                    10,
                )
                self.assertEqual(cards[deck["leader_card_id"]]["type"], "leader")

        self.assertEqual(len(self.rows["pvp_tables.csv"]), 2)
        self.assertEqual(
            {row["mode"] for row in self.rows["pvp_throttle_rules.csv"]},
            {"normal", "limited", "paused"},
        )
        for row in self.rows["challenge_tokens.csv"]:
            self.assertEqual(int(row["tokens_per_player"]), 3)
            self.assertEqual(int(row["start_window_min"]), 30)

        refusal_reasons = {row["reason"] for row in self.rows["pvp_refusal_rules.csv"]}
        self.assertTrue({"active_scene", "safety_stop", "force_majeure"}.issubset(refusal_reasons))
        trade_statuses = {row["status"] for row in self.rows["trade_transfers.csv"]}
        self.assertIn("contested_review", trade_statuses)
        self.assertTrue({"pending_locked", "accepted"}.isdisjoint(trade_statuses))

        active_statuses = {
            row["status_id"]
            for row in self.rows["order_status_rules.csv"]
            if row["is_active"] == "true"
        }
        active_orders_by_lord: dict[str, list[dict[str, str]]] = defaultdict(list)
        active_order_objects: set[tuple[str, str]] = set()
        for order in self.rows["orders.csv"]:
            if order["status"] not in active_statuses:
                continue
            active_orders_by_lord[order["lord_id"]].append(order)
            key = (order["target_player_id"], order["object_id"])
            self.assertNotIn(key, active_order_objects)
            active_order_objects.add(key)

        for orders in active_orders_by_lord.values():
            public_count = sum(1 for order in orders if order["visibility"] == "public")
            addressed_count = sum(1 for order in orders if order["visibility"] == "addressed")
            self.assertLessEqual(public_count, 2)
            self.assertLessEqual(addressed_count, 1)

    def test_progression_magic_reputation_final_and_paper_contracts(self) -> None:
        thresholds = split_ids(self.rows["balance_defaults.csv"][0]["xp_thresholds"])
        self.assertEqual(thresholds, ["0", "10", "25", "45", "70", "100", "135", "175", "220", "270"])

        for row in self.rows["xp_rules.csv"]:
            self.assertEqual(row["stat_gain_rule"], "+1_stat_per_level")
            self.assertEqual(int(row["max_stat"]), 7)

        potion_costs = {row["rarity"]: row for row in self.rows["potions.csv"]}
        self.assertEqual(int(potion_costs["Common"]["wholesale_cost"]), 8)
        self.assertEqual(int(potion_costs["Uncommon"]["wholesale_cost"]), 18)
        self.assertEqual(int(potion_costs["Rare"]["wholesale_cost"]), 40)
        self.assertEqual({row["seller_role"] for row in self.rows["potion_markets.csv"]}, {"sorceress"})

        spell_roles = {row["role"] for row in self.rows["spells.csv"]}
        self.assertTrue({"hint", "boost", "reveal", "ward", "curse", "ritual"}.issubset(spell_roles))
        self.assertEqual(self.rows["favorite_rules.csv"][0]["passive_bonus_allowed"], "false")
        self.assertEqual(
            {row["alignment_state"] for row in self.rows["sorceress_alignment_rules.csv"]},
            {
                "start_lord_support",
                "independent_intrigue",
                "double_game",
                "declared_new_patron",
                "open_betrayal",
            },
        )

        covered_reputation_values = {
            value
            for rule in self.rows["reputation_rules.csv"]
            for value in range(int(rule["min_value"]), int(rule["max_value"]) + 1)
        }
        self.assertEqual(covered_reputation_values, set(range(-5, 6)))

        rarity_rules = {row["rule_id"]: row for row in self.rows["rarity_rules.csv"]}
        self.assertEqual(rarity_rules["rare_gwent_cap"]["total_cap"], "6")
        self.assertEqual(rarity_rules["legendary_artifact_cap"]["earliest_act"], "act2")
        self.assertEqual(len(self.rows["artifacts.csv"]), 8)

        final_summary = self.rows["final_summary.csv"][0]
        self.assertEqual(final_summary["tournament_mode"], "npc_led_tournament")
        self.assertEqual(final_summary["automatic_winner_calculation"], "false")

        paper_forms = {row["form_type"]: row for row in self.rows["paper_forms.csv"]}
        self.assertEqual(
            set(paper_forms),
            {
                "paper_pve_result",
                "paper_pvp_stake",
                "paper_lord_action",
                "paper_lord_battle",
                "paper_order_resolution",
                "paper_npc_deal",
                "paper_final_evidence",
            },
        )
        for form in paper_forms.values():
            fields = set(json.loads(form["required_fields_json"]))
            self.assertTrue(
                {
                    "paper_form_id",
                    "source_form_type",
                    "operator",
                    "timestamp",
                    "reason",
                    "conflict_status",
                }.issubset(fields)
            )
            self.assertEqual(form["conflict_policy"], "review_conflict_no_silent_overwrite")

        self.assertTrue(self.rows["player_handouts.csv"])
        self.assertTrue(self.rows["ops_checklists.csv"])

    def test_fixture_layout_for_task004_importer(self) -> None:
        valid_manifest = self.load_fixture_csv(
            FIXTURE_ROOT / "seed_valid" / "fixture_manifest.csv"
        )[0]
        self.assertEqual(valid_manifest["base_path"], "../../../data/seed")
        self.assertEqual(valid_manifest["expected_result"], "success")

        expected_invalid = {
            "seed_invalid_duplicate_ids",
            "seed_invalid_missing_refs",
            "seed_invalid_bad_qr_mode",
            "seed_invalid_bad_profile_counts",
            "seed_invalid_future_act_unlock",
            "seed_invalid_reward_approval",
            "seed_invalid_order_conflict",
            "seed_invalid_gwent_deck",
            "seed_invalid_building_cycle",
            "seed_invalid_paper_conflict",
            "seed_invalid_empty_required_refs",
            "seed_invalid_qr_act_mismatch",
            "seed_invalid_qr_consumption_mismatch",
            "seed_invalid_domain_token_role_mismatch",
            "seed_invalid_lord_battle_rules",
        }
        actual_invalid = {
            path.name
            for path in FIXTURE_ROOT.iterdir()
            if path.is_dir() and path.name.startswith("seed_invalid_")
        }
        self.assertEqual(actual_invalid, expected_invalid)

        for fixture_name in expected_invalid:
            with self.subTest(fixture=fixture_name):
                fixture_dir = FIXTURE_ROOT / fixture_name
                manifest = self.load_fixture_csv(fixture_dir / "fixture_manifest.csv")[0]
                self.assertEqual(manifest["fixture_type"], "invalid_overlay")
                self.assertEqual(manifest["base_path"], "../../../data/seed")
                self.assertTrue(manifest["override_files"])
                self.assertTrue(manifest["expected_result"])
                for override in split_ids(manifest["override_files"]):
                    self.assertTrue((fixture_dir / override).exists())

    @staticmethod
    def load_fixture_csv(path: Path) -> list[dict[str, str]]:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
