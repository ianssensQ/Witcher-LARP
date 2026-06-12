from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.app import create_app
from backend.witcher_larp.asset_service import grant_asset_ownership
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.lord_runtime import anti_snowball_cut_for_domain
from backend.witcher_larp.lord_runtime import ensure_lord_runtime_state
from backend.witcher_larp.lord_runtime import reconcile_pending_lord_moves
from backend.witcher_larp.pve_runtime import resolve_pve_scene
from backend.witcher_larp.timer_service import apply_due_timers

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"
MASTER_HEADERS = {"X-Role-Token": "MASTER-KING-4QZ8"}


@unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
class Stage1GateRoleFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_stage1_p0_p1_regressions_fail_through_client_facing_apis(self) -> None:
        suffix = uuid4().hex
        settings = Settings(
            database_path=TEST_TMP_ROOT / f"stage1_negatives_{suffix}.db",
            backup_dir=TEST_TMP_ROOT / f"stage1_negatives_backups_{suffix}",
        )
        report = import_seed_pack(
            settings,
            manifest_path=FIXTURE_MANIFEST,
            snapshot_dir=None,
        )
        self.assertEqual(report.status, "success")
        self._grant_stage1_stake_assets(settings)
        client = TestClient(create_app(settings))

        start_act1 = self._post_ok(
            client,
            "/api/master/acts/act1/start",
            headers=MASTER_HEADERS,
            json={"operator": "gm_stage1", "physical_announcement_state": "announced"},
        )
        self.assertEqual(start_act1["state"]["current_act_id"], "act1")

        snapshot = client.get(
            "/api/content/snapshot",
            params={"player_code": "WC-WOLF-6GF4"},
        )
        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        snapshot_payload = snapshot.json()
        self.assertEqual(snapshot_payload["snapshot_version"], report.snapshot_version)
        self.assertEqual(snapshot_payload["visibility"]["scope"], "player")
        self.assertEqual(snapshot_payload["player"]["player_id"], "p_witcher_1")
        self.assertNotIn("player_codes", snapshot_payload)
        self.assertNotIn("role_tokens", snapshot_payload)
        self.assertTrue(all(row["code"] is None for row in snapshot_payload["act_unlock_codes"]))
        for secret in (
            "WC-CAT-1HN8",
            "SC-MOON-4AD8",
            "LORD-NORTH-R8K4",
            "MASTER-KING-4QZ8",
            "UNLOCK-A2-7GQ4",
        ):
            self.assertNotIn(secret, snapshot.text)

        early_unlock = self._sync_event(
            client,
            device_id="phone_wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            event_type="act_unlocked_offline",
            payload={"act_id": "act2", "code": "UNLOCK-A2-7GQ4"},
            sequence=1,
        )
        self.assertEqual(early_unlock["results"][0]["status"], "rejected")
        self.assertEqual(
            early_unlock["results"][0]["reason"],
            "act unlock code has not been revealed by masters",
        )

        forged_pve = self._sync_event(
            client,
            device_id="phone_wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            event_type="pve_completed",
            payload={
                "scenario_id": "scn_a1_001",
                "qr_id": "qr_a1_001",
                "act_id": "act1",
                "unlock_source": "act1_default",
                "result": "success",
                "reward_id": "reward_pve_t1",
                "physical_presence_confirmed": True,
            },
            sequence=2,
        )
        self.assertEqual(forged_pve["results"][0]["status"], "needs_master_review")
        self.assertEqual(
            forged_pve["results"][0]["reason"],
            "pve completion must include exactly one replayable d20 roll_log entry",
        )

        with connect(settings) as connection:
            missing_presence_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 10, 5, tzinfo=UTC),
            )
            missing_presence_payload["physical_presence_confirmed"] = False
            unique_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_006",
                roll=20,
                now=datetime(2026, 6, 2, 10, 10, tzinfo=UTC),
            )
            pending_reward_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_007",
                roll=20,
                now=datetime(2026, 6, 2, 10, 15, tzinfo=UTC),
            )

        missing_presence = self._sync_event(
            client,
            device_id="phone_wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            event_type="pve_completed",
            payload=missing_presence_payload,
            sequence=3,
        )
        self.assertEqual(missing_presence["results"][0]["status"], "needs_master_review")
        self.assertEqual(
            missing_presence["results"][0]["reason"],
            "physical presence confirmation required for physical QR scene",
        )

        first_unique = self._sync_event(
            client,
            device_id="phone_wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            event_type="pve_completed",
            payload=unique_payload,
            sequence=4,
        )
        duplicate_unique = self._sync_event(
            client,
            device_id="phone_wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            event_type="pve_completed",
            payload=unique_payload,
            sequence=5,
        )
        self.assertEqual(first_unique["results"][0]["status"], "pending_master_approval")
        self.assertEqual(duplicate_unique["results"][0]["status"], "needs_master_review")
        self.assertEqual(
            duplicate_unique["results"][0]["reason"],
            "unique QR object already consumed",
        )

        pending_reward = self._sync_event(
            client,
            device_id="phone_wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            event_type="pve_completed",
            payload=pending_reward_payload,
            sequence=6,
        )
        self.assertEqual(pending_reward["results"][0]["status"], "pending_master_approval")

        pending_stake = client.post(
            "/api/pvp/challenges",
            headers=self._player_headers("p_witcher_1"),
            json={
                "challenge_id": "stage1_pending_reward_stake",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {
                    "asset_type": "artifact",
                    "asset_id": "artifact_mirror_shard",
                },
            },
        )
        pending_trade = client.post(
            "/api/trade-transfers",
            headers=self._player_headers("p_witcher_1"),
            json={
                "transfer_id": "stage1_pending_reward_trade",
                "from_player_id": "p_witcher_1",
                "to_player_id": "p_witcher_2",
                "asset_type": "artifact",
                "asset_id": "artifact_mirror_shard",
            },
        )
        self.assertEqual(pending_stake.status_code, 400, pending_stake.text)
        self.assertIn("locked", pending_stake.text)
        self.assertIn(pending_trade.status_code, {400, 409}, pending_trade.text)
        self.assertIn("locked", pending_trade.text)

        challenge = self._post_ok(
            client,
            "/api/pvp/challenges",
            headers=self._player_headers("p_witcher_1"),
            json={
                "challenge_id": "stage1_invalid_gwent_card",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {
                    "asset_type": "item",
                    "asset_id": "stage1_invalid_gwent_marker",
                },
            },
        )
        started = self._post_ok(
            client,
            f"/api/pvp/challenges/{challenge['challenge_id']}/start",
            headers=self._player_headers("p_witcher_1"),
            json={},
        )
        invalid_card = client.post(
            f"/api/pvp/matches/{started['match']['match_id']}/rounds",
            headers=self._player_headers("p_witcher_1"),
            json={
                "round_number": 1,
                "plays": [
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_11"},
                ],
            },
        )
        self.assertEqual(invalid_card.status_code, 400)
        self.assertIn("not in current hand", invalid_card.text)

        battle_payload = {
            "battle_id": "stage1_unauthorized_battle",
            "attacker_domain_id": "domain_north",
            "territory_id": "territory_res_north",
            "seed": "stage1-auth-negative",
        }
        missing_battle_token = client.post("/api/lord-battles", json=battle_payload)
        wrong_battle_token = client.post(
            "/api/lord-battles",
            headers=self._headers("river"),
            json=battle_payload,
        )
        self.assertEqual(missing_battle_token.status_code, 401)
        self.assertEqual(wrong_battle_token.status_code, 403)

        paper_payload = {
            "paper_form_id": "stage1-paper-pve-duplicate",
            "source_form_type": "paper_pve_result",
            "operator": "gm_stage1",
            "timestamp": "2026-06-02T10:30:00+00:00",
            "reason": "paper fallback drill",
            "player_id": "p_witcher_1",
            "qr_id": "qr_a1_001",
            "result": "success",
            "roll": 8,
            "conflict_status": "clean",
        }
        clean_paper = self._sync_event(
            client,
            device_id="paper_terminal",
            actor_id="gm_stage1",
            actor_type="master",
            event_type="paper_recovered",
            payload=paper_payload,
            sequence=1,
        )
        duplicate_paper = self._sync_event(
            client,
            device_id="paper_terminal",
            actor_id="gm_stage1",
            actor_type="master",
            event_type="paper_recovered",
            payload=paper_payload,
            sequence=2,
        )
        self.assertEqual(clean_paper["results"][0]["status"], "accepted")
        self.assertEqual(duplicate_paper["results"][0]["status"], "needs_master_review")
        self.assertIn("duplicate paper_form_id", duplicate_paper["results"][0]["reason"])

    def test_seed_scripted_role_flow_covers_stage1_gate(self) -> None:
        suffix = uuid4().hex
        settings = Settings(
            database_path=TEST_TMP_ROOT / f"stage1_gate_{suffix}.db",
            backup_dir=TEST_TMP_ROOT / f"stage1_gate_backups_{suffix}",
        )
        snapshot_dir = TEST_TMP_ROOT / f"stage1_gate_snapshots_{suffix}"
        report = import_seed_pack(
            settings,
            manifest_path=FIXTURE_MANIFEST,
            snapshot_dir=snapshot_dir,
        )
        self.assertEqual(report.status, "success")
        self._grant_stage1_stake_assets(settings)

        client = TestClient(create_app(settings))
        self._assert_stack_contract(client, report.snapshot_version, snapshot_dir)

        started_at = datetime.now(UTC).replace(microsecond=0)
        with connect(settings) as connection:
            act1 = start_act(
                connection,
                settings,
                "act1",
                operator="gm_stage1",
                physical_announcement_state="announced",
                now=started_at,
            )
        self.assertEqual(act1["start_effects"]["challenge_tokens"]["tokens_per_player"], 3)

        active = self._post_ok(
            client,
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 8,
            },
        )
        self.assertEqual(active["status"], "active_army_updated")

        # Route guard tests cover neutral-front stopping; this broad stage gate
        # keeps its downstream battle/timer flow by pre-owning the corridor.
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_north',
                    status = 'controlled',
                    contested_by_domain_id = NULL
                WHERE territory_id IN ('territory_fort_east', 'territory_well_city')
                """
            )

        moved = self._post_ok(
            client,
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={
                "route_node_ids": [
                    "node_res_north",
                    "node_fort_east",
                    "node_well_city",
                    "node_village_east_shed",
                ],
            },
        )
        self.assertEqual(moved["status"], "pending_move")
        self.assertIsNone(moved["claim"])
        move_arrived_at = datetime.fromisoformat(moved["pending_move"]["arrival_at"])
        with connect(settings) as connection:
            completed = reconcile_pending_lord_moves(
                connection,
                domain_id="domain_north",
                now=move_arrived_at + timedelta(seconds=1),
            )
        self.assertEqual(completed[0]["claim"]["territory_id"], "territory_village_east_shed")
        self.assertIn(completed[0]["claim"]["status"], {"in_battle", "contested_pending_tick"})

        with connect(settings) as connection:
            first_tick = apply_due_timers(
                connection,
                settings,
                now=move_arrived_at + timedelta(minutes=31),
            )
        self.assertEqual(first_tick[0]["effect_type"], "lord_income_and_mana")
        self.assertEqual(
            first_tick[0]["pending_tick_rewards"][0]["territory_id"],
            "territory_village_east_shed",
        )

        battle = self._post_ok(
            client,
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "stage1_neutral_field",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_village_east_shed",
                "seed": "stage1-gate-neutral",
            },
        )
        self.assertEqual(battle["board"]["width"], 5)
        self.assertEqual(battle["board"]["height"], 6)
        self.assertEqual(battle["defender_control"], "neutral_ai")
        battle = self._start_battle_after_deployment(client, "stage1_neutral_field")

        takeover = self._post_ok(
            client,
            "/api/lord-battles/stage1_neutral_field/actions",
            headers=MASTER_HEADERS,
            json={
                "action_id": "stage1-master-takeover",
                "action_type": "master_takeover",
                "actor_side": "defender",
            },
        )
        self.assertEqual(takeover["defender_control"], "master")
        resolved = self._post_ok(
            client,
            "/api/lord-battles/stage1_neutral_field/actions",
            headers=self._headers("north"),
            json={
                "action_id": "stage1-auto-resolve",
                "action_type": "auto_resolve",
                "actor_side": "attacker",
            },
        )
        self.assertEqual(resolved["battle"]["result"]["winner_side"], "attacker")

        with connect(settings) as connection:
            second_tick = apply_due_timers(
                connection,
                settings,
                now=move_arrived_at + timedelta(minutes=91),
            )
            act2 = start_act(
                connection,
                settings,
                "act2",
                operator="gm_stage1",
                physical_announcement_state="announced",
                now=move_arrived_at + timedelta(hours=2, minutes=30),
            )
            act2_tick = apply_due_timers(
                connection,
                settings,
                now=move_arrived_at + timedelta(hours=3, minutes=1),
            )
        self.assertEqual(second_tick[0]["effect_type"], "lord_income_and_mana")
        self.assertTrue(act2["unlock_code"]["available"])
        self.assertEqual(act2_tick[0]["effect_type"], "lord_income_and_mana")

        self._assert_lord_strategy_flow(client, settings)
        self._assert_mobile_pve_and_recovery_flow(client, settings)
        self._assert_pvp_trade_order_flow(client, settings)
        self._assert_sorceress_and_npc_flow(client)

        with connect(settings) as connection:
            start_act(
                connection,
                settings,
                "act3",
                operator="gm_stage1",
                physical_announcement_state="announced",
                now=move_arrived_at + timedelta(hours=5),
            )
            start_act(
                connection,
                settings,
                "final_lock",
                operator="gm_stage1",
                physical_announcement_state="announced",
                now=move_arrived_at + timedelta(hours=7, minutes=15),
            )
            start_act(
                connection,
                settings,
                "final_act",
                operator="gm_stage1",
                physical_announcement_state="announced",
                now=move_arrived_at + timedelta(hours=7, minutes=30),
            )

        restarted_client = TestClient(create_app(settings))
        persisted_battle = restarted_client.get(
            "/api/lord-battles/stage1_neutral_field",
            headers=MASTER_HEADERS,
        )
        self.assertEqual(persisted_battle.status_code, 200, persisted_battle.text)
        self.assertEqual(persisted_battle.json()["status"], "finished")

        summary = restarted_client.get("/api/master/final-summary", headers=MASTER_HEADERS)
        self.assertEqual(summary.status_code, 200, summary.text)
        payload = summary.json()
        self.assertFalse(payload["decision_policy"]["automatic_winner_calculation"])
        self.assertTrue(payload["final_lock_state"]["locked"])
        self.assertEqual(len(payload["evidence_by_role"]["lords"]), 4)
        self.assertEqual(len(payload["evidence_by_role"]["sorceresses"]), 4)
        self.assertEqual(len(payload["evidence_by_role"]["witchers"]), 5)
        self.assertTrue(payload["paper_recovery"])
        self.assertTrue(payload["npc_prices"])
        self.assertTrue(payload["locked_magical_intent"])
        intent_statuses = {
            item["sorceress_id"]: item["status"]
            for item in payload["locked_magical_intent"]
        }
        self.assertEqual(
            set(intent_statuses),
            {"p_sorc_1", "p_sorc_2", "p_sorc_3", "p_sorc_4"},
        )
        self.assertEqual(intent_statuses["p_sorc_1"], "locked")
        unresolved_intents = {
            sorceress_id
            for sorceress_id, status in intent_statuses.items()
            if status != "locked"
        }
        self.assertEqual(unresolved_intents, {"p_sorc_2", "p_sorc_3", "p_sorc_4"})
        missing_intent_locks = {
            item["sorceress_id"]
            for item in payload["missing_locks"]
            if item["evidence_category"] == "locked_magical_intent"
        }
        self.assertTrue(unresolved_intents.issubset(missing_intent_locks))
        self.assertNotIn("p_sorc_1", missing_intent_locks)
        self.assertEqual(payload["staffing"]["total_station_count"], 6)
        self.assertEqual(payload["export"]["snapshot_version"], report.snapshot_version)
        self.assertNotIn("winner_id", payload)

    def _assert_stack_contract(
        self,
        client: TestClient,
        snapshot_version: str,
        snapshot_dir,
    ) -> None:
        health = client.get("/health")
        self.assertEqual(health.status_code, 200, health.text)
        self.assertEqual(health.json()["database"]["schema_version"], 1)

        snapshot = client.get(
            "/api/content/snapshot",
            params={"player_code": "WC-WOLF-6GF4"},
        )
        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        self.assertEqual(snapshot.json()["snapshot_version"], snapshot_version)
        self.assertEqual(snapshot.json()["player"]["player_id"], "p_witcher_1")
        self.assertTrue(any(snapshot_dir.glob("*.json")))

        old_lord_panel = client.get("/lord")
        self.assertEqual(old_lord_panel.status_code, 404, old_lord_panel.text)
        self.assertTrue((PROJECT_ROOT / "mobile" / "project.godot").exists())
        self.assertTrue((PROJECT_ROOT / "mobile" / "scripts" / "main.gd").exists())

    def _assert_lord_strategy_flow(self, client: TestClient, settings: Settings) -> None:
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            for building_id in ("b_map_room", "b_stables", "b_raid_office"):
                connection.execute(
                    """
                    INSERT INTO domain_buildings (
                        domain_id, territory_id, building_id, purchased_at, source
                    )
                    VALUES (
                        'domain_north', 'territory_res_north', ?,
                        '2026-06-02T12:00:00+00:00', 'stage1_test'
                    )
                    ON CONFLICT(domain_id, territory_id, building_id) DO NOTHING
                    """,
                    (building_id,),
                )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET raid_tokens = 1, raid_token_cap = 3
                WHERE domain_id = 'domain_north'
                """
            )
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_river',
                    status = 'controlled',
                    contested_by_domain_id = NULL
                WHERE territory_id = 'territory_field_oats'
                """
            )
        raid = self._post_ok(
            client,
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_field_oats",
                "rule_id": "raid_income_sabotage",
                "expected_gold_cost": 0,
            },
        )
        self.assertEqual(raid["status"], "active")
        self.assertEqual(raid["token_spent"], 1)

        for lord_id, token_name, building_id in (
            ("p_lord_1", "north", "b_training_yard"),
            ("p_lord_2", "river", "b_market"),
            ("p_lord_3", "forest", "b_notice_board"),
            ("p_lord_4", "hill", "b_mage_study"),
        ):
            bought = self._post_ok(
                client,
                f"/api/lords/{lord_id}/buildings",
                headers=self._headers(token_name),
                json={"building_id": building_id},
            )
            self.assertEqual(bought["status"], "purchased")

        archery = self._post_ok(
            client,
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_archery_range"},
        )
        self.assertIn(
            "unit_ranged_t1",
            {offer["card_id"] for offer in archery["unlocked_recruit_offers"]},
        )
        refresh = self._post_ok(
            client,
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "refresh"},
        )
        recruit_offer = next(
            offer for offer in refresh["offers"] if offer["card_id"] == "unit_ranged_t1"
        )
        recruited = self._post_ok(
            client,
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "purchase", "offer_id": recruit_offer["offer_id"]},
        )
        self.assertEqual(recruited["reserve"]["card_id"], "unit_ranged_t1")

        captured = self._post_ok(
            client,
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "territory_id": "territory_village_east_shed",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(captured["status"], "captured")
        self.assertEqual(captured["pending_tick_awards"][0]["reward_gold"], 8)

        with connect(settings) as connection:
            anti_snowball = anti_snowball_cut_for_domain(connection, "domain_north")
        self.assertIn("army_power_ratio", anti_snowball)
        self.assertIn(anti_snowball["income_cut_percent"], {0, 30, 50})

    def _assert_mobile_pve_and_recovery_flow(
        self,
        client: TestClient,
        settings: Settings,
    ) -> None:
        act2_start = self._post_ok(
            client,
            "/api/master/acts/act2/start",
            headers=MASTER_HEADERS,
            json={"operator": "gm_stage1", "physical_announcement_state": "announced"},
        )
        self.assertEqual(act2_start["state"]["current_act_id"], "act2")
        act2_code = client.get(
            "/api/master/acts/act2/unlock-code",
            headers=MASTER_HEADERS,
            params={"operator": "gm_stage1"},
        )
        self.assertEqual(act2_code.status_code, 200, act2_code.text)
        offline_unlock = self._sync_event(
            client,
            device_id="phone_wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            event_type="act_unlocked_offline",
            payload={"act_id": "act2", "code": "UNLOCK-A2-7GQ4"},
            sequence=1,
        )
        self.assertEqual(offline_unlock["results"][0]["status"], "accepted")

        qr_lookup = self._post_ok(
            client,
            "/api/qr/lookup",
            headers=self._event_auth_headers("p_witcher_1", "player"),
            json={
                "code": "QR-A1-TRV-001-K7Q2",
                "device_id": "phone_wolf",
                "source": "manual_id",
                "physical_presence_confirmed": True,
            },
        )
        self.assertEqual(qr_lookup["event_context"]["qr_mode"], "repeatable_scene")
        honesty_review = self._post_ok(
            client,
            "/api/qr/lookup",
            headers=self._event_auth_headers("p_witcher_1", "player"),
            json={
                "code": "witcher-larp://qr?code=QR-A1-EAZ-006-X3L5",
                "device_id": "phone_wolf",
                "source": "qr_scan",
                "physical_presence_confirmed": False,
            },
        )
        self.assertEqual(honesty_review["status"], "needs_master_review")
        self.assertEqual(honesty_review["reason"], "honesty_violation_suspected")

        with connect(settings) as connection:
            pve_success = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 13, 10, tzinfo=UTC),
            )
            pve_failure = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_002",
                roll=1,
                now=datetime(2026, 6, 2, 13, 15, tzinfo=UTC),
            )
            pending_reward = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_007",
                roll=20,
                now=datetime(2026, 6, 2, 13, 20, tzinfo=UTC),
            )

        pve_sync = self._sync_events(
            client,
            device_id="phone_wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            events=[
                ("pve_completed", pve_success),
                ("pve_completed", pve_failure),
                ("pve_completed", pending_reward),
            ],
            first_sequence=2,
        )
        self.assertEqual(pve_sync["results"][0]["status"], "accepted")
        self.assertEqual(pve_sync["results"][1]["status"], "accepted")
        self.assertEqual(pve_sync["results"][2]["status"], "pending_master_approval")

        paper = self._sync_event(
            client,
            device_id="paper_terminal",
            actor_id="gm_stage1",
            actor_type="master",
            event_type="paper_recovered",
            payload={
                "paper_form_id": "stage1-paper-battle-1",
                "source_form_type": "paper_lord_battle",
                "operator": "gm_stage1",
                "timestamp": "2026-06-02T13:30:00+00:00",
                "reason": "lord battle continued on paper during network loss",
                "battle_id": "stage1_neutral_field",
                "result": "attacker_won",
                "losses": {"attacker": 0, "defender": 1},
                "conflict_status": "duplicate_conflict_needs_review",
            },
            sequence=1,
        )
        self.assertEqual(paper["results"][0]["status"], "needs_master_review")

        with connect(settings) as connection:
            cooldown = connection.execute(
                """
                SELECT cooldown_until
                FROM pve_cooldowns
                WHERE player_id = 'p_witcher_1' AND qr_id = 'qr_a1_002'
                """
            ).fetchone()
            approvals = connection.execute(
                """
                SELECT COUNT(*)
                FROM reward_approvals
                WHERE status = 'pending_master_approval'
                """
            ).fetchone()[0]
            paper_review = connection.execute(
                """
                SELECT reason
                FROM event_reviews
                WHERE event_id = ?
                """,
                (paper["results"][0]["event_id"],),
            ).fetchone()
        self.assertIsNotNone(cooldown["cooldown_until"])
        self.assertGreaterEqual(approvals, 1)
        self.assertIn("paper during network loss", paper_review["reason"])

    def _assert_pvp_trade_order_flow(self, client: TestClient, settings: Settings) -> None:
        challenge = self._post_ok(
            client,
            "/api/pvp/challenges",
            headers=self._player_headers("p_witcher_1"),
            json={
                "challenge_id": "stage1_gwent_challenge",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {
                    "asset_type": "item",
                    "asset_id": "stage1_gwent_marker",
                    "transfer_on_finish": True,
                },
            },
        )
        self.assertEqual(challenge["status"], "assigned")
        self.assertEqual(challenge["assigned_zone"], "main_house_table")
        self.assertIn("start_window_deadline", challenge)

        started = self._post_ok(
            client,
            "/api/pvp/challenges/stage1_gwent_challenge/start",
            headers=self._player_headers("p_witcher_1"),
            json={},
        )
        match_id = started["match"]["match_id"]
        hands = {
            player_id: list(state["hand"])
            for player_id, state in started["match"]["deck_state"].items()
            if player_id in {"p_witcher_1", "p_witcher_2"}
        }
        round_specs = (
            (
                1,
                "p_witcher_1",
                "p_witcher_2",
                [{"player_id": "p_witcher_1", "card_id": hands["p_witcher_1"][0]}],
            ),
            (
                2,
                "p_witcher_2",
                "p_witcher_1",
                [{"player_id": "p_witcher_2", "card_id": hands["p_witcher_2"][0]}],
            ),
            (
                3,
                "p_witcher_1",
                "p_witcher_2",
                [{"player_id": "p_witcher_1", "card_id": hands["p_witcher_1"][1]}],
            ),
        )
        for round_number, winner, loser, plays in round_specs:
            pending_round = self._post_ok(
                client,
                f"/api/pvp/matches/{match_id}/rounds",
                headers=self._player_headers(winner),
                json={
                    "round_number": round_number,
                    "plays": plays,
                    "passed": {winner: True},
                },
            )
            self.assertIsNone(pending_round["round"]["winner_id"])
            round_payload = self._post_ok(
                client,
                f"/api/pvp/matches/{match_id}/rounds",
                headers=self._player_headers(loser),
                json={
                    "round_number": round_number,
                    "passed": {loser: True},
                },
            )
            self.assertEqual(round_payload["round"]["winner_id"], winner)
        finished = self._post_ok(
            client,
            f"/api/pvp/matches/{match_id}/finish",
            headers=self._player_headers("p_witcher_1"),
            json={"winner_id": "p_witcher_1"},
        )
        self.assertEqual(finished["stake_transfer"]["status"], "applied")
        self.assertFalse(finished["duplicate"])

        refusal_challenge = self._post_ok(
            client,
            "/api/pvp/challenges",
            headers=self._player_headers("p_witcher_3"),
            json={
                "challenge_id": "stage1_refusal_challenge",
                "challenger_id": "p_witcher_3",
                "target_id": "p_sorc_1",
                "stake": {"asset_type": "item", "asset_id": "stage1_refusal_marker"},
            },
        )
        self.assertEqual(refusal_challenge["status"], "assigned")
        refusal = self._post_ok(
            client,
            "/api/pvp/challenges/stage1_refusal_challenge/refusal",
            headers=self._player_headers("p_sorc_1"),
            json={"reason": "safety_stop", "actor_id": "p_sorc_1"},
        )
        self.assertEqual(refusal["status"], "needs_master_review")
        self.assertEqual(refusal["review_reason"], "refusal:safety_stop")
        with connect(settings) as connection:
            refusal_review = connection.execute(
                """
                SELECT severity
                FROM pvp_reviews
                WHERE challenge_id = 'stage1_refusal_challenge'
                """
            ).fetchone()
        self.assertEqual(refusal_review["severity"], "P0")

        trade_created = self._post_ok(
            client,
            "/api/trade-transfers",
            headers=self._player_headers("p_witcher_1"),
            json={
                "transfer_id": "stage1_auto_reward_trade",
                "from_player_id": "p_witcher_1",
                "to_player_id": "p_lord_1",
                "asset_type": "item",
                "asset_id": "item_herb_bundle",
            },
        )
        self.assertEqual(trade_created["status"], "pending_locked")
        trade = self._post_ok(
            client,
            "/api/trade-transfers/stage1_auto_reward_trade/accept",
            headers=self._player_headers("p_lord_1"),
            json={"accepted_by_player_id": "p_lord_1"},
        )
        self.assertEqual(trade["status"], "accepted")

        first = self._post_ok(
            client,
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={
                "action": "create",
                "order_id": "stage1_order_first",
                "object_id": "territory_well_city",
                "visibility": "public",
                "target_player_id": "p_witcher_2",
                "escrow_reward_id": "reward_order_success",
            },
        )
        second = self._post_ok(
            client,
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={
                "action": "create",
                "order_id": "stage1_order_second",
                "object_id": "territory_well_city",
                "visibility": "public",
                "target_player_id": "p_witcher_3",
                "escrow_reward_id": "reward_order_success",
            },
        )
        self.assertEqual(first["status"], "created")
        self.assertEqual(second["status"], "created")
        accepted = self._post_ok(
            client,
            "/api/lords/p_lord_3/orders",
            headers=self._player_headers("p_witcher_2"),
            json={
                "action": "accept",
                "order_id": "stage1_order_first",
            },
        )
        self.assertEqual(accepted["status"], "accepted")
        conflict = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._player_headers("p_witcher_2"),
            json={
                "action": "accept",
                "order_id": "stage1_order_second",
            },
        )
        self.assertEqual(conflict.status_code, 400, conflict.text)
        self.assertEqual(conflict.json()["detail"]["code"], "order_object_conflict")
        submitted = self._post_ok(
            client,
            "/api/lords/p_lord_3/orders",
            headers=self._player_headers("p_witcher_2"),
            json={
                "action": "submit_success",
                "order_id": "stage1_order_first",
                "result_event_id": "stage1_order_event",
            },
        )
        self.assertEqual(submitted["status"], "pending_master_approval")
        self.assertEqual(submitted["closed_competing_orders"], ["stage1_order_second"])

    def _assert_sorceress_and_npc_flow(self, client: TestClient) -> None:
        potion = self._post_ok(
            client,
            "/api/sorceresses/p_sorc_1/potions/buy",
            headers=self._player_headers("p_sorc_1"),
            json={"potion_id": "potion_common_swallow", "quantity": 2},
        )
        self.assertEqual(potion["inventory"]["quantity"], 2)
        transfer = self._post_ok(
            client,
            "/api/sorceresses/p_sorc_1/potions/transfer",
            headers=MASTER_HEADERS,
            json={
                "to_player_id": "p_witcher_1",
                "potion_id": "potion_common_swallow",
                "quantity": 1,
                "mode": "gift",
                "auto_accept": True,
            },
        )
        self.assertEqual(transfer["status"], "accepted")
        potion_use = self._post_ok(
            client,
            "/api/players/p_witcher_1/potions/use",
            headers=self._player_headers("p_witcher_1"),
            json={"potion_id": "potion_common_swallow", "scene_id": "scn_a1_001"},
        )
        self.assertEqual(potion_use["max_potions_per_scene"], 1)

        favorite = self._post_ok(
            client,
            "/api/favorites",
            headers=self._player_headers("p_sorc_3"),
            json={
                "favorite_id": "stage1_favorite",
                "sorceress_id": "p_sorc_3",
                "favored_player_id": "p_witcher_2",
                "slot": "primary",
            },
        )
        self.assertEqual(favorite["status"], "pending")
        accepted = self._post_ok(
            client,
            "/api/favorites/stage1_favorite/accept",
            headers=self._player_headers("p_witcher_2"),
            json={"accepted_by_player_id": "p_witcher_2"},
        )
        self.assertEqual(accepted["status"], "accepted")

        ritual = self._post_ok(
            client,
            "/api/sorceresses/p_sorc_1/spells/cast",
            headers=self._player_headers("p_sorc_1"),
            json={
                "spell_id": "spell_ritual_t4",
                "target_type": "final_hook",
                "target_id": "hook_sorc_intent",
            },
        )
        self.assertEqual(ritual["status"], "accepted")
        sorceress_state = client.get(
            "/api/sorceresses/p_sorc_1/state",
            headers=self._player_headers("p_sorc_1"),
        )
        self.assertEqual(sorceress_state.status_code, 200, sorceress_state.text)
        self.assertEqual(
            sorceress_state.json()["locked_magical_intent"][0]["status"],
            "locked",
        )

        evidence = self._post_ok(
            client,
            "/api/sorceresses/p_sorc_3/alignment-evidence",
            headers=self._player_headers("p_sorc_3"),
            json={
                "alignment_state": "double_game",
                "evidence_type": "two_sided_evidence",
                "payload": {"lords": ["p_lord_1", "p_lord_3"]},
                "final_flag": True,
            },
        )
        self.assertTrue(evidence["final_flag"])

        king = self._post_ok(
            client,
            "/api/master/npc/events",
            headers=MASTER_HEADERS,
            json={"seed_event_id": "npc_king_ruling"},
        )
        self.assertEqual(king["review_route"], "before_next_act_or_final")
        wanderer = self._post_ok(
            client,
            "/api/master/npc/events",
            headers=MASTER_HEADERS,
            json={"seed_event_id": "npc_wanderer_deal"},
        )
        self.assertTrue(wanderer["deal"]["hidden_price"])

    def _sync_event(
        self,
        client: TestClient,
        *,
        device_id: str,
        actor_id: str,
        actor_type: str,
        event_type: str,
        payload: dict[str, object],
        sequence: int,
    ) -> dict[str, object]:
        return self._sync_events(
            client,
            device_id=device_id,
            actor_id=actor_id,
            actor_type=actor_type,
            events=[(event_type, payload)],
            first_sequence=sequence,
        )

    def _sync_events(
        self,
        client: TestClient,
        *,
        device_id: str,
        actor_id: str,
        actor_type: str,
        events: list[tuple[str, dict[str, object]]],
        first_sequence: int,
    ) -> dict[str, object]:
        response = client.post(
            "/api/events/sync",
            headers=self._event_auth_headers(actor_id, actor_type),
            json={
                "device_id": device_id,
                "actor_id": actor_id,
                "actor_type": actor_type,
                "events": [
                    {
                        "event_id": f"stage1_{uuid4().hex}",
                        "client_sequence": first_sequence + index,
                        "created_at": "2026-06-02T13:00:00+00:00",
                        "event_type": event_type,
                        "payload": payload,
                    }
                    for index, (event_type, payload) in enumerate(events)
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _event_auth_headers(self, actor_id: str, actor_type: str) -> dict[str, str]:
        if actor_type in {"master", "npc_master"}:
            return MASTER_HEADERS
        player_codes = {
            "p_witcher_1": "WC-WOLF-6GF4",
            "p_witcher_2": "WC-CAT-1HN8",
            "p_sorc_1": "SC-MOON-4AD8",
            "p_lord_1": "LC-NORTH-7QK2",
        }
        return {"X-Player-Code": player_codes.get(actor_id, "WC-WOLF-6GF4")}

    def _post_ok(self, client: TestClient, url: str, **kwargs) -> dict[str, object]:
        response = client.post(url, **kwargs)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _start_battle_after_deployment(
        self,
        client: TestClient,
        battle_id: str,
        *,
        attacker_lord: str = "north",
    ) -> dict[str, object]:
        battle = client.get(
            f"/api/lord-battles/{battle_id}",
            headers=MASTER_HEADERS,
        ).json()
        board = battle["board"]
        deployment = battle["deployment"]
        for index, item in enumerate(deployment["hand"]["attacker"][: int(deployment["deployment_cap"])]):
            x, y = self._deployment_cell(board, "attacker", index)
            deployed = client.post(
                f"/api/lord-battles/{battle_id}/actions",
                headers=self._headers(attacker_lord),
                json={
                    "action_id": f"deploy-{battle_id}-attacker-{index}",
                    "action_type": "deploy",
                    "actor_side": "attacker",
                    "payload": {
                        "source_id": item["source_id"],
                        "card_id": item["card_id"],
                        "to": {"x": x, "y": y},
                    },
                },
            )
            self.assertEqual(deployed.status_code, 200, deployed.text)
        ready = client.post(
            f"/api/lord-battles/{battle_id}/actions",
            headers=self._headers(attacker_lord),
            json={
                "action_id": f"ready-{battle_id}-attacker",
                "action_type": "ready",
                "actor_side": "attacker",
            },
        )
        self.assertEqual(ready.status_code, 200, ready.text)
        if isinstance(ready.json().get("battle"), dict):
            return ready.json()["battle"]
        return battle

    @staticmethod
    def _deployment_cell(board: dict[str, object], side: str, index: int) -> tuple[int, int]:
        x_order = [0, 1, 3, 4, 2]
        start_lines = board["start_lines"]
        start = int(start_lines[side])
        if side == "attacker":
            y_order = [start, start, start, start, min(int(board["height"]) - 1, start + 1)]
        else:
            y_order = [start, start, start, start, max(0, start - 1)]
        return x_order[index], y_order[index]

    def _grant_stage1_stake_assets(self, settings: Settings) -> None:
        with connect(settings) as connection:
            for player_id, asset_id in (
                ("p_witcher_1", "stage1_invalid_gwent_marker"),
                ("p_witcher_1", "stage1_gwent_marker"),
                ("p_witcher_3", "stage1_refusal_marker"),
            ):
                self._ensure_stage1_item_asset(connection, asset_id)
                grant_asset_ownership(
                    connection,
                    owner_player_id=player_id,
                    asset_type="item",
                    asset_id=asset_id,
                    source="test_stage1_stake_seed",
                    source_ref_id=asset_id,
                )

    @staticmethod
    def _ensure_stage1_item_asset(connection, asset_id: str) -> None:
        connection.execute(
            """
            INSERT INTO items (
                _import_run_id, _row_number, item_id, item_type, tier,
                stat_requirement_json, effect_json
            )
            SELECT
                COALESCE((SELECT _import_run_id FROM items LIMIT 1), 'test_stage1'),
                COALESCE((SELECT MAX(_row_number) FROM items), 0) + 1,
                ?,
                'pvp_stake',
                1,
                '{}',
                '{"use":"gwent_stake"}'
            WHERE NOT EXISTS (
                SELECT 1 FROM items WHERE item_id = ?
            )
            """,
            (asset_id, asset_id),
        )

    @staticmethod
    def _headers(lord: str) -> dict[str, str]:
        tokens = {
            "north": "LORD-NORTH-R8K4",
            "river": "LORD-RIVER-M2J9",
            "forest": "LORD-FOREST-P6W3",
            "hill": "LORD-HILL-T5C7",
        }
        return {"X-Role-Token": tokens[lord]}

    @staticmethod
    def _player_headers(player_id: str) -> dict[str, str]:
        codes = {
            "p_witcher_1": "WC-WOLF-6GF4",
            "p_witcher_2": "WC-CAT-1HN8",
            "p_witcher_3": "WC-GRIFFIN-7LX2",
            "p_lord_1": "LC-NORTH-7QK2",
            "p_sorc_1": "SC-MOON-4AD8",
            "p_sorc_3": "SC-OWL-2RW7",
        }
        return {"X-Player-Code": codes[player_id]}


if __name__ == "__main__":
    unittest.main()
