from __future__ import annotations

import unittest
from uuid import uuid4

from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.csv_loader import load_pack_from_manifest
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.validation import validate_seed_pack


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"


class SeedValidationDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_missing_non_id_header_reports_table_and_header_without_keyerror(self) -> None:
        fixture_dir = TEST_TMP_ROOT / f"seed_missing_header_{uuid4().hex}"
        fixture_dir.mkdir()
        manifest_path = fixture_dir / "fixture_manifest.csv"
        manifest_path.write_text(
            "\n".join(
                [
                    "fixture_id,fixture_type,base_path,override_files,expected_result",
                    f"seed_missing_header,invalid_overlay,{(PROJECT_ROOT / 'data' / 'seed').as_posix()},qr_objects.csv,missing_header",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (fixture_dir / "qr_objects.csv").write_text(
            "\n".join(
                [
                    "qr_id,manual_code,qr_mode,act_id,location_node_id,physical_presence_required,rate_limit,consumption_rule",
                    "qr_missing_header,QR-MISS-HDR,repeatable_scene,act1,node_forest_dark,true,5_per_minute,repeatable",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        pack = load_pack_from_manifest(manifest_path)
        errors = validate_seed_pack(pack)
        settings = Settings(database_path=TEST_TMP_ROOT / f"missing_header_{uuid4().hex}.db")
        report = import_seed_pack(settings, manifest_path=manifest_path, snapshot_dir=None)

        self.assertIn("missing_header", {error.code for error in errors})
        missing_header = next(error for error in errors if error.code == "missing_header")
        self.assertEqual(missing_header.file, "qr_objects.csv")
        self.assertIn("scenario_id", missing_header.message)
        self.assertEqual(report.status, "failed")
        self.assertIn("missing_header", {error.code for error in report.errors})

    def test_manifest_and_csv_shape_errors_are_reported_before_business_rules(self) -> None:
        empty_manifest = TEST_TMP_ROOT / f"seed_empty_manifest_{uuid4().hex}"
        empty_manifest.mkdir()
        empty_manifest_path = empty_manifest / "fixture_manifest.csv"
        empty_manifest_path.write_text(
            "fixture_id,fixture_type,base_path,override_files,expected_result\n",
            encoding="utf-8",
        )

        unknown_override = self._write_fixture(
            "seed_unknown_override",
            "unknown_seed.csv",
            "unknown_id\nunknown\n",
            override_files="unknown_seed.csv",
        )
        extra_columns = self._write_fixture(
            "seed_extra_columns",
            "profiles.csv",
            "profile_id,total_people,player_count,npc_master_count,lord_count,sorceress_count,witcher_count\n"
            "production_15,15,13,2,4,4,5,unexpected\n",
        )
        missing_id_column = self._write_fixture(
            "seed_missing_id_column",
            "profiles.csv",
            "total_people,player_count,npc_master_count,lord_count,sorceress_count,witcher_count\n"
            "15,13,2,4,4,5\n",
        )
        empty_file = self._write_fixture(
            "seed_empty_profiles",
            "profiles.csv",
            "profile_id,total_people,player_count,npc_master_count,lord_count,sorceress_count,witcher_count\n",
        )

        cases = [
            (empty_manifest_path, {"manifest_empty", "missing_file"}),
            (unknown_override, {"unknown_override_file"}),
            (extra_columns, {"extra_columns", "missing_file"}),
            (missing_id_column, {"missing_id_column", "missing_header"}),
            (empty_file, {"empty_file"}),
        ]
        for manifest_path, expected_codes in cases:
            with self.subTest(manifest_path=manifest_path.parent.name):
                pack = load_pack_from_manifest(manifest_path)
                errors = validate_seed_pack(pack)
                self.assertTrue(
                    expected_codes.issubset({error.code for error in errors}),
                    f"Expected {expected_codes}, got {[error.code for error in errors]}",
                )

    def test_id_integrity_errors_report_file_row_and_record_context(self) -> None:
        manifest_path = self._write_fixture(
            "seed_id_integrity",
            "qr_objects.csv",
            "qr_id,manual_code,scenario_id,qr_mode,act_id,location_node_id,physical_presence_required,rate_limit,consumption_rule\n"
            ",QR-MISSING-ID,scn_a1_001,repeatable_scene,act1,node_forest_dark,true,5_per_minute,repeatable\n"
            "qr_duplicate_id,QR-DUP-1,scn_a1_001,repeatable_scene,act1,node_forest_dark,true,5_per_minute,repeatable\n"
            "qr_duplicate_id,QR-DUP-2,scn_a1_001,repeatable_scene,act1,node_forest_dark,true,5_per_minute,repeatable\n",
        )

        errors = validate_seed_pack(load_pack_from_manifest(manifest_path))
        missing_id = next(error for error in errors if error.code == "missing_id")
        duplicate_id = next(error for error in errors if error.code == "duplicate_id")

        self.assertEqual(missing_id.file, "qr_objects.csv")
        self.assertEqual(missing_id.row, 2)
        self.assertIn("qr_id", missing_id.message)
        self.assertEqual(duplicate_id.file, "qr_objects.csv")
        self.assertEqual(duplicate_id.row, 4)
        self.assertEqual(duplicate_id.record_id, "qr_duplicate_id")

    def test_business_policy_overlays_report_specific_validation_codes(self) -> None:
        cases = [
            (
                "profiles.csv",
                "profile_id,total_people,player_count,npc_master_count,lord_count,sorceress_count,witcher_count\n"
                "production_15,14,12,2,4,4,4\n",
                {"bad_profile_counts"},
            ),
            (
                "qr_objects.csv",
                "qr_id,manual_code,scenario_id,qr_mode,act_id,location_node_id,physical_presence_required,rate_limit,consumption_rule\n"
                "qr_bad,QR-BAD-1,scn_a1_001,remote_scene,act1,node_forest_dark,false,5_per_minute,repeatable\n",
                {"bad_qr_mode", "qr_honesty_policy", "qr_content_mix"},
            ),
            (
                "pve_scenarios.csv",
                "scenario_id,act_id,tier,scene_type,primary_stat,dc,check_policy,combat_profile_id,reward_id,success_text,failure_text,timeout_outcome\n"
                "scn_a1_001,act1,1,monster_hunt,Сила,11,single_d20,mob_neutral_patrol_t1,reward_pve_t1,ok,fail,soft_timeout\n",
                {"pve_timeout_policy"},
            ),
            (
                "pve_scenarios.csv",
                "scenario_id,act_id,tier,scene_type,primary_stat,dc,check_policy,combat_profile_id,reward_id,success_text,failure_text,timeout_outcome\n"
                "scn_a1_001,act1,5,monster_hunt,combat,99,single_d20,mob_neutral_patrol_t1,reward_pve_t1,ok,fail,fail_and_cooldown\n"
                "scn_a1_002,act1,1,monster_hunt,combat,1,single_d20,mob_neutral_patrol_t1,reward_pve_t1,ok,fail,fail_and_cooldown\n",
                {"invalid_pve_tier", "invalid_pve_dc"},
            ),
            (
                "players.csv",
                "player_id,role_type,display_name,lord_id,sorceress_start_lord_id,level,xp,gold,reputation,stats_json,player_code_id\n"
                'p_bad,witcher,Bad Stats,,,1,0,20,0,"{""combat"":3,""lore"":2,""influence"":2}",code_witcher_1\n',
                {"invalid_stat_schema"},
            ),
            (
                "pve_scenarios.csv",
                "scenario_id,act_id,tier,scene_type,primary_stat,dc,check_policy,combat_profile_id,reward_id,success_text,failure_text,timeout_outcome\n"
                "scn_a1_001,act1,1,monster_hunt,combat,11,single_d20,mob_neutral_patrol_t1,reward_pve_t1,ok,fail,fail_and_cooldown\n",
                {"invalid_pve_stat"},
            ),
            (
                "items.csv",
                "item_id,item_type,tier,stat_requirement_json,effect_json\n"
                'item_bad,material,1,"{""alchemy"":1}","{""use"":""bad_old_stat""}"\n',
                {"invalid_item_stat_requirement"},
            ),
            (
                "pve_combat_rules.csv",
                "rule_id,player_scene_hp,base_damage,no_persistent_player_hp,timeout_outcome,failure_cooldown_min\n"
                "pve_combat_default,10,1,true,fail_and_cooldown,10\n",
                {"invalid_cooldown_window"},
            ),
            (
                "check_policies.csv",
                "policy_id,die_policy,modifier_sources,no_rerolls,log_required\n"
                "single_d20,d12,items,false,true\n",
                {"invalid_check_policy"},
            ),
            (
                "buildings.csv",
                "building_id,branch,name,tier,gold_cost,prerequisite_ids,recruit_unlock_ids,capacity_delta,raid_unlock\n"
                "b_bad,alchemy,Bad Building,5,0,b_bad,,0,false\n",
                {
                    "invalid_building_branch",
                    "invalid_building_tier",
                    "invalid_gold_cost",
                    "building_cycle",
                },
            ),
            (
                "army_unit_cards.csv",
                "card_id,unit_class,tier,attack,defense,hp,initiative,move_range,attack_range,cost,source_id\n"
                "unit_bad,dragon,1,-1,0,1,1,1,1,1,b_training_yard\n",
                {"invalid_unit_class", "invalid_unit_value"},
            ),
            (
                "army_unit_cards.csv",
                "card_id,unit_class,tier,attack,defense,hp,initiative,move_range,attack_range,cost,source_id\n"
                "unit_bad,infantry,0,1,1,0,1,6,6,1,b_training_yard\n",
                {"invalid_unit_value"},
            ),
            (
                "orders.csv",
                "order_id,lord_id,target_player_id,object_id,visibility,status,escrow_reward_id\n"
                "order_cap_1,p_lord_1,p_witcher_1,qr_a1_006,public,published,reward_order_success\n"
                "order_cap_2,p_lord_1,p_witcher_2,qr_a1_007,public,published,reward_order_success\n"
                "order_cap_3,p_lord_1,p_witcher_3,qr_a1_008,public,published,reward_order_success\n",
                {"order_cap"},
            ),
            (
                "gwent_cards.csv",
                "card_id,faction,row,type,strength,effect,rarity\n"
                "bad_leader,northern,melee,leader,0,leader_order_rally,Uncommon\n"
                "bad_unit,northern,special,unit,4,none,Common\n",
                {"gwent_card_invalid"},
            ),
            (
                "gwent_cards.csv",
                "card_id,faction,row,type,strength,effect,rarity\n"
                "bad_effect,northern,melee,unit,4,stage2_portal,Common\n",
                {"gwent_effect_unsupported"},
            ),
            (
                "trade_transfers.csv",
                "transfer_id,from_player_id,to_player_id,asset_type,asset_id,status\n"
                "trade_bad,p_missing,p_witcher_1,item,item_missing,teleported\n",
                {"trade_transfer_player", "trade_transfer_asset", "trade_transfer_lock_rule"},
            ),
            (
                "trade_transfers.csv",
                "transfer_id,from_player_id,to_player_id,asset_type,asset_id,status\n"
                "trade_seed_mint,p_witcher_1,p_lord_1,item,item_monster_trophy,pending_locked\n"
                "trade_seed_grant,p_sorc_1,p_witcher_1,potion,potion_common_swallow,accepted\n",
                {"trade_transfer_seed_provenance"},
            ),
            (
                "map_edges.csv",
                "edge_id,from_node_id,to_node_id,mp_cost,bidirectional\n"
                "edge_bad,node_res_north,node_fort_east,-1,maybe\n",
                {"invalid_map_edge_cost", "invalid_map_edge_bidirectional"},
            ),
            (
                "territory_forts.csv",
                "fort_id,territory_id,name,theme,garrison_capacity,art_prompt_id,background_asset_id,card_asset_id\n"
                "fort_bad,territory_fort_east,Bad Fort,bad_theme,99,prompt_bad,asset_bg_bad,asset_card_bad\n",
                {"invalid_garrison_capacity", "missing_territory_fort"},
            ),
            (
                "auto_timers.csv",
                "timer_id,act_id,timer_type,offset_min,interval_min,effect_type\n"
                "timer_bad,act1,typo_tick,10,0,unknown_noop\n",
                {"invalid_auto_timer", "invalid_auto_timer_effect", "missing_canonical_auto_timer"},
            ),
            (
                "movement_pools.csv",
                "pool_id,domain_id,act_id,current_mp,mp_cap,last_refill_offset_min\n"
                "mp_bad,domain_north,act1,7,6,-1\n",
                {"invalid_resource_value"},
            ),
            (
                "recruit_markets.csv",
                "offer_id,domain_id,card_id,cost,status,refresh_rule\n"
                "offer_bad,domain_north,unit_infantry_t1,-5,available,act_refresh\n",
                {"invalid_resource_value"},
            ),
            (
                "rewards.csv",
                "reward_id,xp,gold,item_ids,card_ids,artifact_ids,rarity,approval_policy\n"
                "reward_pve_t1,-1,-10,item_herb_bundle,pc_infantry_t1,,Common,auto\n",
                {"invalid_resource_value"},
            ),
            (
                "potions.csv",
                "potion_id,rarity,wholesale_cost,resale_min,resale_max,effect_json\n"
                'potion_common_swallow,Common,-1,15,12,"{""effect"":""minor_heal_scene_hp""}"\n',
                {"invalid_resource_value"},
            ),
            (
                "rewards.csv",
                "reward_id,xp,gold,item_ids,card_ids,artifact_ids,rarity,approval_policy\n"
                "reward_pve_t1,4,10,item_herb_bundle,pc_infantry_t1,,Common,auto\n"
                "reward_pve_t2,8,20,item_silver_dust,pc_guard_t1,,Uncommon,auto\n"
                "reward_pve_t3,12,35,item_monster_trophy,pc_cavalry_t2,,Rare,pending_master_approval\n"
                "reward_pve_t4,18,55,item_ancient_relic,pc_siege_t3,artifact_legend_crown,Legendary,pending_master_approval\n"
                "reward_artifact_pending,10,0,,rare_gwent_01,artifact_mirror_shard,Rare,pending_master_approval\n"
                "reward_lord_income_t1,0,8,,,,Common,auto\n"
                "reward_order_success,6,15,item_order_seal,pc_specialist_t3,,Uncommon,auto\n"
                "reward_gwent_stake,0,0,item_gwent_marker,gwent_larp_banner,,Uncommon,pending_master_approval\n"
                "reward_final_evidence,5,0,item_final_token,,artifact_oath_stone,Rare,pending_master_approval\n",
                {"reward_approval_policy"},
            ),
            (
                "pve_scenarios.csv",
                "scenario_id,act_id,tier,scene_type,primary_stat,dc,check_policy,combat_profile_id,reward_id,success_text,failure_text,timeout_outcome\n"
                "scn_a1_001,act1,1,npc_deal,РҐР°СЂРёР·РјР°,11,single_d20,mob_neutral_patrol_t1,reward_pve_t2,ok,fail,fail_and_cooldown\n"
                "scn_a1_002,act1,1,reputation_impact,РҐР°СЂРёР·РјР°,11,single_d20,mob_neutral_patrol_t1,reward_pve_t1,ok,fail,fail_and_cooldown\n",
                {"reward_approval_policy"},
            ),
            (
                "challenge_tokens.csv",
                "token_rule_id,act_id,tokens_per_player,start_window_min\n"
                "challenge_act1,act1,2,10\n",
                {"invalid_token_window"},
            ),
            (
                "physical_announcements.csv",
                "announcement_id,act_id,required_signal,operator_role\n"
                "ann_act1,act1,voice_or_bell,npc_master\n",
                {"physical_announcement_coverage"},
            ),
            (
                "qr_policies.csv",
                "policy_id,physical_presence_required,manual_entry_allowed,manual_rate_limit,suspected_violation_outcome\n"
                "qr_bad,false,false,none,ignore\n",
                {"qr_honesty_policy"},
            ),
            (
                "player_handouts.csv",
                "handout_id,audience,required_topics\n"
                "handout_common,all,common_rules;qr_honesty\n",
                {"handout_readiness"},
            ),
            (
                "pvp_refusal_rules.csv",
                "rule_id,reason,severity,default_outcome\n"
                "refusal_bad,active_scene,P2,deferred_window\n",
                {"pvp_refusal_safety"},
            ),
            (
                "potion_markets.csv",
                "market_id,seller_role,potion_id,stock,refresh_rule\n"
                "market_bad,lord,potion_common_swallow,0,never\n",
                {"potion_market_access"},
            ),
            (
                "anti_snowball_rules.csv",
                "rule_id,army_power_ratio_threshold,income_cut_percent,notes\n"
                "anti_bad,120,10,bad cut\n",
                {"anti_snowball_threshold"},
            ),
            (
                "pvp_throttle_rules.csv",
                "rule_id,mode,max_tables,max_started_per_player_per_act,final_lock_behavior\n"
                "throttle_bad,turbo,4,4,no_new_challenges_after_final_lock\n",
                {"invalid_pvp_throttle"},
            ),
            (
                "reputation_rules.csv",
                "rule_id,min_value,max_value,label,player_descriptor,master_visibility\n"
                "rep_short,-1,1,Neutral,uncertain,numeric_and_log\n",
                {"invalid_reputation_range"},
            ),
            (
                "xp_rules.csv",
                "rule_id,source,xp_min,xp_max,stat_gain_rule,max_stat,level_thresholds\n"
                "xp_bad,monster_hunt,3,20,no_stats,9,0;10\n",
                {"invalid_xp_rule"},
            ),
            (
                "spells.csv",
                "spell_id,tier,role,cost_mana,target_type,effect_json,counterplay\n"
                'spell_bad,1,hint,1,scene,"{}",\n',
                {"invalid_spell_counterplay"},
            ),
            (
                "favorite_rules.csv",
                "rule_id,max_primary,max_secondary,max_sorceresses_per_favored,change_limit_per_act,passive_bonus_allowed\n"
                "favorite_default,1,1,2,1,true\n",
                {"favorite_lifecycle"},
            ),
            (
                "final_summary.csv",
                "summary_id,final_act_id,tournament_mode,winner_policy,includes_missing_locks,includes_pending_disputes,includes_npc_prices,includes_locked_magical_intent,export_snapshot_required,automatic_winner_calculation\n"
                "final_summary_seed,final_act,auto_score,points,false,false,false,false,false,true\n",
                {"final_summary_fields"},
            ),
            (
                "final_procedures.csv",
                "procedure_id,final_act_window,start_offset_min,end_offset_min,station_count,master_role\n"
                "final_act_load_plan,7:30-9:30,450,570,1,npc_king\n",
                {"final_summary_fields"},
            ),
            (
                "paper_forms.csv",
                "form_type,description,required_fields_json,conflict_policy,recovery_event_type\n"
                'paper_bad,Bad form,"[""paper_form_id""]",silent_overwrite,paper_recovered\n',
                {"paper_conflict_policy"},
            ),
        ]

        for file_name, content, expected_codes in cases:
            with self.subTest(file_name=file_name):
                errors = self._validate_overlay(file_name, content)
                actual_codes = {error.code for error in errors}
                self.assertTrue(
                    expected_codes.issubset(actual_codes),
                    f"Expected {expected_codes}, got {actual_codes}",
                )

    def test_order_validation_uses_status_rule_flags_for_locks_and_canonical_caps(self) -> None:
        duplicate_published = (
            "order_id,lord_id,target_player_id,object_id,visibility,status,escrow_reward_id\n"
            "order_open_1,p_lord_3,p_witcher_2,territory_well_city,public,published,reward_order_success\n"
            "order_open_2,p_lord_3,p_witcher_2,territory_well_city,public,published,reward_order_success\n"
        )
        published_errors = self._validate_overlay("orders.csv", duplicate_published)
        published_codes = {error.code for error in published_errors}
        self.assertNotIn("order_object_conflict", published_codes)
        self.assertNotIn("order_cap", published_codes)

        duplicate_accepted = (
            "order_id,lord_id,target_player_id,object_id,visibility,status,escrow_reward_id\n"
            "order_lock_1,p_lord_3,p_witcher_2,territory_well_city,public,accepted,reward_order_success\n"
            "order_lock_2,p_lord_3,p_witcher_2,territory_well_city,public,accepted,reward_order_success\n"
        )
        accepted_errors = self._validate_overlay("orders.csv", duplicate_accepted)
        self.assertIn("order_object_conflict", {error.code for error in accepted_errors})

        status_rules_without_published_cap = (
            (PROJECT_ROOT / "data" / "seed" / "order_status_rules.csv")
            .read_text(encoding="utf-8")
            .replace("published,true,false,true", "published,true,false,false")
        )
        over_cap_published = (
            "order_id,lord_id,target_player_id,object_id,visibility,status,escrow_reward_id\n"
            "order_cap_1,p_lord_1,p_witcher_1,qr_a1_006,public,published,reward_order_success\n"
            "order_cap_2,p_lord_1,p_witcher_2,qr_a1_007,public,published,reward_order_success\n"
            "order_cap_3,p_lord_1,p_witcher_3,qr_a1_008,public,published,reward_order_success\n"
        )
        cap_errors = self._validate_overlay_files(
            {
                "order_status_rules.csv": status_rules_without_published_cap,
                "orders.csv": over_cap_published,
            }
        )
        cap_codes = {error.code for error in cap_errors}
        self.assertIn("order_status_cap_rule", cap_codes)
        self.assertIn("order_cap", cap_codes)

    def test_task073_business_validation_rejects_cross_row_seed_breaks(self) -> None:
        bad_empty_required_ref = self._seed_csv("qr_objects.csv").replace(
            "qr_a1_001,QR-A1-K7Q2,scn_a1_001,",
            "qr_a1_001,QR-A1-K7Q2,,",
        )
        bad_qr_act = self._seed_csv("qr_objects.csv").replace(
            "qr_a1_001,QR-A1-K7Q2,scn_a1_001,repeatable_scene,act1,",
            "qr_a1_001,QR-A1-K7Q2,scn_a1_001,repeatable_scene,act2,",
        )
        bad_qr_consumption = self._seed_csv("qr_objects.csv").replace(
            "qr_a1_001,QR-A1-K7Q2,scn_a1_001,repeatable_scene,act1,node_forest_dark,true,5_per_minute,repeatable",
            "qr_a1_001,QR-A1-K7Q2,scn_a1_001,repeatable_scene,act1,node_forest_dark,true,5_per_minute,consume_once",
        )
        bad_domains = self._seed_csv("domains.csv").replace(
            "domain_north,p_lord_1,North Watch",
            "domain_north,p_witcher_1,North Watch",
        )
        bad_role_tokens = self._seed_csv("role_tokens.csv").replace(
            "token_lord_1,lord,p_lord_1",
            "token_lord_1,lord,p_sorc_1",
        ).replace(
            "token_master_king,npc_master,npc_king",
            "token_master_king,npc_master,p_lord_1",
        )
        bad_sorceress_binding = self._seed_csv("players.csv").replace(
            "p_sorc_1,sorceress,Yennefer Circle,,p_lord_1",
            "p_sorc_1,sorceress,Yennefer Circle,,p_witcher_1",
        )
        bad_lord_battle = (
            "rule_id,grid_width,grid_height,turn_timer_seconds,damage_formula,initiative_tiebreaker,timeout_policy,auto_resolve_policy\n"
            "lord_battle_default,6,6,45,attack_minus_defense,initiative_asc,manual_skip,manual_only\n"
        )

        cases = [
            (
                {"qr_objects.csv": bad_empty_required_ref},
                {"missing_required_reference"},
            ),
            (
                {"qr_objects.csv": bad_qr_act},
                {"qr_scenario_act_mismatch"},
            ),
            (
                {"qr_objects.csv": bad_qr_consumption},
                {"qr_consumption_rule_mismatch"},
            ),
            (
                {"domains.csv": bad_domains, "role_tokens.csv": bad_role_tokens},
                {
                    "domain_lord_owner",
                    "invalid_player_lord_binding",
                    "role_token_owner",
                    "role_token_coverage",
                },
            ),
            (
                {"players.csv": bad_sorceress_binding},
                {"invalid_sorceress_lord_binding"},
            ),
            (
                {"lord_battle_rules.csv": bad_lord_battle},
                {"invalid_lord_battle_rule"},
            ),
        ]

        for files, expected_codes in cases:
            with self.subTest(files=sorted(files)):
                errors = self._validate_overlay_files(files)
                actual_codes = {error.code for error in errors}
                self.assertTrue(
                    expected_codes.issubset(actual_codes),
                    f"Expected {expected_codes}, got {actual_codes}",
                )

        missing_required = next(
            error
            for error in self._validate_overlay("qr_objects.csv", bad_empty_required_ref)
            if error.code == "missing_required_reference"
        )
        self.assertEqual(missing_required.file, "qr_objects.csv")
        self.assertEqual(missing_required.record_id, "qr_a1_001")
        self.assertIn("required reference", missing_required.message)

    def _validate_overlay(self, file_name: str, content: str):
        return self._validate_overlay_files({file_name: content})

    def _validate_overlay_files(self, files: dict[str, str]):
        file_names = sorted(files)
        fixture_label = "_".join(file_name.replace(".", "_") for file_name in file_names)
        fixture_dir = TEST_TMP_ROOT / f"seed_policy_{fixture_label}_{uuid4().hex}"
        fixture_dir.mkdir()
        manifest_path = fixture_dir / "fixture_manifest.csv"
        manifest_path.write_text(
            "\n".join(
                [
                    "fixture_id,fixture_type,base_path,override_files,expected_result",
                    (
                        "seed_policy,invalid_overlay,"
                        f"{(PROJECT_ROOT / 'data' / 'seed').as_posix()},"
                        f"{';'.join(file_names)},policy_error"
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        for file_name, content in files.items():
            (fixture_dir / file_name).write_text(content, encoding="utf-8")
        pack = load_pack_from_manifest(manifest_path)
        return validate_seed_pack(pack)

    def _write_fixture(
        self,
        name: str,
        file_name: str,
        content: str,
        *,
        override_files: str | None = None,
    ):
        fixture_dir = TEST_TMP_ROOT / f"{name}_{uuid4().hex}"
        fixture_dir.mkdir()
        manifest_path = fixture_dir / "fixture_manifest.csv"
        manifest_path.write_text(
            "\n".join(
                [
                    "fixture_id,fixture_type,base_path,override_files,expected_result",
                    (
                        f"{name},invalid_overlay,{(PROJECT_ROOT / 'data' / 'seed').as_posix()},"
                        f"{override_files or file_name},shape_error"
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (fixture_dir / file_name).write_text(content, encoding="utf-8")
        return manifest_path

    @staticmethod
    def _seed_csv(file_name: str) -> str:
        return (PROJECT_ROOT / "data" / "seed" / file_name).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
