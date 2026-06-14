from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import unittest
from uuid import uuid4

from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.lord_runtime import ensure_lord_runtime_state
from backend.witcher_larp.lord_runtime import reconcile_pending_lord_moves

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


@unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
class LordPanelContractTests(unittest.TestCase):
    def setUp(self) -> None:
        (PROJECT_ROOT / ".test-data").mkdir(exist_ok=True)

    def test_legacy_lord_static_panel_is_removed(self) -> None:
        client = TestClient(create_app(self._settings("lord_static")))

        page = client.get("/lord")
        script = client.get("/static/lord/lord.js")
        styles = client.get("/static/lord/lord.css")
        layout = client.get("/static/lord/assets/lord_map_layout.json")
        map_art = client.get("/static/lord/assets/lord_map_playable_v1_display.webp")

        self.assertEqual(page.status_code, 404)
        self.assertEqual(script.status_code, 404)
        self.assertEqual(styles.status_code, 404)
        self.assertEqual(layout.status_code, 404)
        self.assertEqual(map_art.status_code, 404)
        self.assertFalse((PROJECT_ROOT / "backend" / "witcher_larp" / "web" / "lord").exists())
        self.assertFalse(
            (PROJECT_ROOT / "backend" / "witcher_larp" / "web" / "package.json").exists()
        )

    def test_lord_panel_action_controls_execute_role_scoped_apis(self) -> None:
        settings = self._settings("lord_action_behavior")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        self.assertEqual(client.get("/lord").status_code, 404)

        start = client.post(
            "/api/master/acts/act1/start",
            headers={"X-Role-Token": "MASTER-KING-4QZ8"},
            json={"operator": "gm_lord_panel", "physical_announcement_state": "announced"},
        )
        self.assertEqual(start.status_code, 200, start.text)

        missing_token = client.post(
            "/api/lords/p_lord_1/move",
            json={"to_node_id": "node_fort_east"},
        )
        wrong_lord = client.post(
            "/api/lords/p_lord_1/move",
            headers={"X-Role-Token": "LORD-RIVER-M2J9"},
            json={"to_node_id": "node_fort_east"},
        )
        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "to_node_id": "node_fort_east",
                "route_node_ids": ["node_res_north", "node_fort_east"],
            },
        )

        self.assertEqual(missing_token.status_code, 401)
        self.assertEqual(wrong_lord.status_code, 403)
        self.assertEqual(active.status_code, 200, active.text)
        self.assertEqual(moved.status_code, 200, moved.text)
        moved_payload = moved.json()
        self.assertEqual(moved_payload["status"], "pending_move")
        self.assertEqual(moved_payload["mp_spent"], 2)
        self.assertEqual(moved_payload["route"], ["node_res_north", "node_fort_east"])
        self.assertIsNone(moved_payload["claim"])
        completed = self._complete_pending_moves(settings)
        self.assertEqual(completed[0]["claim"]["territory_id"], "territory_fort_east")

        claim_state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        self.assertEqual(claim_state.status_code, 200, claim_state.text)
        claim_payload = claim_state.json()
        self.assertGreaterEqual(claim_payload["summary"]["active_claims"], 1)
        claim = self._claim(claim_payload["claims"], "territory_fort_east")
        self.assertEqual(claim["territory_id"], "territory_fort_east")
        self.assertEqual(claim["claimant_domain_id"], "domain_north")
        self.assertEqual(claim["status"], "in_battle")

        battle = client.post(
            "/api/lord-battles",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "battle_id": "lord_panel_battle_contract",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_fort_east",
                "claim_id": claim["claim_id"],
                "seed": "lord-panel-contract",
            },
        )
        wrong_battle = client.post(
            "/api/lord-battles",
            headers={"X-Role-Token": "LORD-RIVER-M2J9"},
            json={
                "battle_id": "lord_panel_wrong_actor_contract",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_fort_east",
                "seed": "lord-panel-wrong-actor",
            },
        )

        self.assertEqual(battle.status_code, 200, battle.text)
        battle_payload = battle.json()
        self.assertEqual(battle_payload["board"]["width"], 5)
        self.assertEqual(battle_payload["board"]["height"], 6)
        self.assertEqual(battle_payload["attacker_domain_id"], "domain_north")
        self.assertIn("hero_hp", battle_payload)
        self.assertEqual(wrong_battle.status_code, 403)
        self.assertEqual(wrong_battle.json()["detail"]["code"], "wrong_actor_domain")
        self._start_battle_after_deployment(client, "lord_panel_battle_contract")

        battle_state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        self.assertEqual(battle_state.status_code, 200, battle_state.text)
        battle_state_payload = battle_state.json()
        panel_battle = next(
            item
            for item in battle_state_payload["active_battles"]
            if item["battle_id"] == "lord_panel_battle_contract"
        )
        self.assertEqual(panel_battle["territory_id"], "territory_fort_east")
        self.assertEqual(panel_battle["claim_id"], claim["claim_id"])
        self.assertEqual(panel_battle["cta"]["action"], "open_battle")
        self.assertTrue(
            any(
                alert["battle_id"] == "lord_panel_battle_contract"
                and alert["type"] == "active_battle"
                for alert in battle_state_payload["battle_alerts"]
            )
        )
        battle_claim = self._claim(
            battle_state_payload["claims"], "territory_fort_east"
        )
        self.assertIn("cta", battle_claim)
        self.assertIn("alert_level", battle_claim)

        battle_action = client.post(
            "/api/lord-battles/lord_panel_battle_contract/actions",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "action_id": "lord-panel-auto-resolve",
                "action_type": "auto_resolve",
                "actor_side": "attacker",
            },
        )
        self.assertEqual(battle_action.status_code, 200, battle_action.text)
        self.assertEqual(battle_action.json()["battle"]["status"], "finished")

        state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        self.assertEqual(state.status_code, 200, state.text)
        state_payload = state.json()
        self.assertIn("map_nodes", state_payload)
        self.assertEqual(len(state_payload["map_nodes"]), 25)
        self.assertIn("map_edges", state_payload)
        self.assertTrue(state_payload["map_edges"])
        self.assertEqual(
            state_payload["lord_map_layout"]["layout_id"],
            "venue_map_v3_strict_v6",
        )
        self.assertTrue(state_payload["lord_map_layout"]["visibility"]["graph_visible"])
        self.assertIn("lord_map_intel", state_payload)
        self.assertIn("enemy_armies", state_payload["lord_map_intel"])
        self.assertIn("pending_move", state_payload)
        self.assertEqual(
            state_payload["route_options"]["current_node_id"],
            state_payload["movement"]["current_node_id"],
        )
        self.assertEqual(state_payload["route_options"]["mp_available"], 4)
        self.assertIn("claims", state_payload)
        self.assertIn("active_claims", state_payload["summary"])
        self.assertIn("fort", state_payload["neutral_territories"][0])
        self.assertIn(
            "move",
            {surface["id"] for surface in state_payload["action_surfaces"]},
        )
        self.assertIn(
            "lord_battles",
            {surface["id"] for surface in state_payload["action_surfaces"]},
        )
        self.assertIn("battles", state_payload)

        scoped_endpoints = (
            (
                "/api/lords/p_lord_2/buildings",
                {"building_id": "b_market"},
            ),
            (
                "/api/lords/p_lord_2/recruit",
                {"action": "refresh"},
            ),
            (
                "/api/lords/p_lord_2/raids",
                {"target_territory_id": "territory_res_north"},
            ),
            (
                "/api/lords/p_lord_2/orders",
                {
                    "action": "create",
                    "order_id": "lord_panel_cross_scope",
                    "object_id": "territory_fort_east",
                    "visibility": "public",
                    "target_player_id": "p_witcher_1",
                    "escrow_reward_id": "reward_order_success",
                },
            ),
        )
        for url, body in scoped_endpoints:
            with self.subTest(url=url):
                cross_scope = client.post(
                    url,
                    headers={"X-Role-Token": "LORD-NORTH-R8K4"},
                    json=body,
                )
                self.assertEqual(cross_scope.status_code, 403, cross_scope.text)

    def test_lord_panel_queues_simultaneous_attacks_against_same_lord(self) -> None:
        settings = self._settings("lord_battle_queue")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))
        now = datetime.now(UTC)
        board = {
            "width": 5,
            "height": 6,
            "rules": {"turn_timer_seconds": 60},
            "stacks": [],
            "hero_cells": {
                "attacker": {"x": 2, "y": 0},
                "defender": {"x": 2, "y": 5},
            },
        }
        deployment = {
            "deployment_cap": 5,
            "hand": {"attacker": [], "defender": []},
            "deployed": {"attacker": [], "defender": []},
            "undeployed": {"attacker": [], "defender": []},
            "ready": {"attacker": True, "defender": True},
            "phase": "complete",
        }
        hero_hp = {
            "attacker": {"current": 40, "max": 40},
            "defender": {"current": 40, "max": 40},
        }
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            for index, (battle_id, attacker_domain_id, territory_id) in enumerate(
                [
                    ("lord_panel_queue_first", "domain_river", "territory_fort_east"),
                    ("lord_panel_queue_second", "domain_forest", "territory_black_mire"),
                ]
            ):
                created_at = now + timedelta(seconds=index)
                connection.execute(
                    """
                    INSERT INTO lord_battles (
                        battle_id, battle_type, territory_id, claim_id,
                        attacker_domain_id, defender_domain_id, defender_control,
                        status, seed, round_number, active_side, active_stack_id,
                        turn_started_at, timeout_at, timeout_counts_json, board_json,
                        hero_hp_json, deployment_json, initiative_json,
                        burned_cards_json, result_json, created_at, updated_at,
                        target_duration_seconds, auto_resolve_after_seconds,
                        master_takeover_enabled
                    )
                    VALUES (?, 'lord_vs_lord', ?, NULL, ?, 'domain_north', 'lord',
                            'active', ?, 1, 'defender', NULL, ?, ?, '{}', ?, ?, ?,
                            '[]', '[]', '{}', ?, ?, 1200, 1500, 0)
                    """,
                    (
                        battle_id,
                        territory_id,
                        attacker_domain_id,
                        f"seed-{battle_id}",
                        created_at.isoformat(),
                        (created_at + timedelta(seconds=60)).isoformat(),
                        json.dumps(board),
                        json.dumps(hero_hp),
                        json.dumps(deployment),
                        created_at.isoformat(),
                        created_at.isoformat(),
                    ),
                )

        defender_state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        self.assertEqual(defender_state.status_code, 200, defender_state.text)
        defender_payload = defender_state.json()
        first = next(
            battle
            for battle in defender_payload["active_battles"]
            if battle["battle_id"] == "lord_panel_queue_first"
        )
        second = next(
            battle
            for battle in defender_payload["active_battles"]
            if battle["battle_id"] == "lord_panel_queue_second"
        )
        self.assertEqual(first["queue_state"], "ready")
        self.assertEqual(first["queue_position"], 1)
        self.assertEqual(first["cta"]["action"], "open_battle")
        self.assertTrue(first["can_act"])
        self.assertEqual(second["queue_state"], "waiting")
        self.assertEqual(second["queue_position"], 2)
        self.assertEqual(second["blocking_battle_ids"], ["lord_panel_queue_first"])
        self.assertEqual(second["cta"]["action"], "wait_for_battle")
        self.assertFalse(second["can_act"])
        self.assertEqual(
            [
                alert["battle_id"]
                for alert in defender_payload["battle_alerts"]
                if alert["type"] == "active_battle"
            ],
            ["lord_panel_queue_first"],
        )

        waiting_attacker = client.get(
            "/api/lords/p_lord_3/state",
            headers={"X-Role-Token": "LORD-FOREST-P6W3"},
        )
        self.assertEqual(waiting_attacker.status_code, 200, waiting_attacker.text)
        waiting_battle = next(
            battle
            for battle in waiting_attacker.json()["active_battles"]
            if battle["battle_id"] == "lord_panel_queue_second"
        )
        self.assertEqual(waiting_battle["queue_state"], "waiting")
        self.assertEqual(waiting_battle["cta"]["action"], "wait_for_battle")
        blocked_action = client.post(
            "/api/lord-battles/lord_panel_queue_second/actions",
            headers={"X-Role-Token": "LORD-FOREST-P6W3"},
            json={
                "action_id": "queued-battle-action",
                "action_type": "auto_resolve",
                "actor_side": "attacker",
            },
        )
        self.assertEqual(blocked_action.status_code, 409, blocked_action.text)
        self.assertEqual(
            blocked_action.json()["detail"]["code"],
            "battle_waiting_for_previous",
        )

        with connect(settings) as connection:
            finished_at = (now + timedelta(minutes=2)).isoformat()
            connection.execute(
                """
                UPDATE lord_battles
                SET status = 'finished', finished_at = ?, updated_at = ?
                WHERE battle_id = 'lord_panel_queue_first'
                """,
                (finished_at, finished_at),
            )

        released_state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        self.assertEqual(released_state.status_code, 200, released_state.text)
        released_payload = released_state.json()
        released_battle = next(
            battle
            for battle in released_payload["active_battles"]
            if battle["battle_id"] == "lord_panel_queue_second"
        )
        self.assertEqual(released_battle["queue_state"], "ready")
        self.assertEqual(released_battle["queue_position"], 1)
        self.assertEqual(released_battle["cta"]["action"], "open_battle")
        self.assertTrue(released_battle["can_act"])

    def test_capture_pending_foreign_territory_is_garrison_target_from_panel(self) -> None:
        settings = self._settings("lord_capture_pending_panel")
        self._import_valid_seed(settings)
        self._set_reserve_count(settings, "reserve_north_infantry", 6)
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_river',
                    status = 'controlled',
                    contested_by_domain_id = NULL
                WHERE territory_id = 'territory_fort_east'
                """
            )
            connection.execute(
                """
                INSERT INTO garrison_runtime_state (
                    garrison_id, territory_id, domain_id, card_id,
                    count, status, updated_at
                )
                VALUES (
                    'garrison_river_fort_east',
                    'territory_fort_east',
                    'domain_river',
                    'unit_guard_t1',
                    1,
                    'active',
                    CURRENT_TIMESTAMP
                )
                """
            )
        client = TestClient(create_app(settings))

        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 4,
            },
        )
        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "to_node_id": "node_fort_east",
                "route_node_ids": ["node_res_north", "node_fort_east"],
            },
        )
        completed = self._complete_pending_moves(settings)
        battle = client.post(
            "/api/lord-battles",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "battle_id": "lord_panel_foreign_capture",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_fort_east",
                "seed": "lord-panel-foreign-capture",
            },
        )
        self.assertEqual(active.status_code, 200, active.text)
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(completed[0]["claim"]["territory_id"], "territory_fort_east")
        self.assertEqual(battle.status_code, 200, battle.text)
        self._start_battle_after_deployment(client, "lord_panel_foreign_capture")
        first_vote = client.post(
            "/api/lord-battles/lord_panel_foreign_capture/actions",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "action_id": "resolve-foreign-capture-attacker",
                "action_type": "auto_resolve",
                "actor_side": "attacker",
            },
        )
        self.assertEqual(first_vote.status_code, 200, first_vote.text)
        resolved = first_vote
        if first_vote.json()["status"] == "auto_resolve_vote_pending":
            resolved = client.post(
                "/api/lord-battles/lord_panel_foreign_capture/actions",
                headers={"X-Role-Token": "LORD-RIVER-M2J9"},
                json={
                    "action_id": "resolve-foreign-capture-defender",
                    "action_type": "auto_resolve",
                    "actor_side": "defender",
                },
            )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()["battle"]["result"]["winner_side"], "attacker")
        self.assertEqual(
            resolved.json()["battle"]["result"]["capture"]["status"],
            "capture_pending_garrison",
        )

        pending_state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        self.assertEqual(pending_state.status_code, 200, pending_state.text)
        payload = pending_state.json()
        target = self._territory(payload["garrison_targets"], "territory_fort_east")
        self.assertEqual(target["owner_domain_id"], "domain_river")
        self.assertEqual(target["status"], "capture_pending_garrison")
        self.assertEqual(target["contested_by_domain_id"], "domain_north")
        self.assertEqual(target["garrison_target_reason"], "capture_pending_garrison")
        self.assertEqual(payload["summary"]["garrison_targets"], 2)
        pending_claim = self._claim(payload["claims"], "territory_fort_east")
        self.assertEqual(pending_claim["status"], "awaiting_garrison")
        self.assertFalse(pending_claim["battle_required"])
        self.assertEqual(pending_claim["cta"]["action"], "open_garrison")
        self.assertFalse(
            any(
                battle["battle_id"] == "lord_panel_foreign_capture"
                for battle in payload["active_battles"]
            )
        )
        self.assertFalse(
            any(
                alert.get("type") == "active_battle"
                and alert.get("battle_id") == "lord_panel_foreign_capture"
                for alert in payload["battle_alerts"]
            )
        )
        garrison_alert = next(
            alert
            for alert in payload["battle_alerts"]
            if alert.get("claim_id") == pending_claim["claim_id"]
        )
        self.assertEqual(garrison_alert["cta"]["action"], "open_garrison")

        repeated_battle = client.post(
            "/api/lord-battles",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "battle_id": "lord_panel_foreign_capture_repeat",
                "claim_id": pending_claim["claim_id"],
                "territory_id": "territory_fort_east",
                "seed": "lord-panel-foreign-capture-repeat",
            },
        )
        self.assertEqual(repeated_battle.status_code, 409, repeated_battle.text)
        self.assertEqual(
            repeated_battle.json()["detail"]["code"],
            "claim_awaiting_garrison",
        )

        captured = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "operation": "active_to_fort",
                "territory_id": "territory_fort_east",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )

        self.assertEqual(captured.status_code, 200, captured.text)
        self.assertEqual(captured.json()["status"], "captured")
        captured_state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        ).json()
        river_fort = self._territory(
            captured_state["territories"],
            "territory_fort_east",
        )
        self.assertEqual(river_fort["owner_domain_id"], "domain_north")
        self.assertEqual(river_fort["status"], "controlled")

    def test_registration_summary_marks_lord_panel_for_clean_full_refresh(self) -> None:
        settings = self._settings("lord_registration_summary_refresh")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        start = client.post(
            "/api/master/acts/act1/start",
            headers={"X-Role-Token": "MASTER-KING-4QZ8"},
            json={"operator": "gm_dirty", "physical_announcement_state": "announced"},
        )
        self.assertEqual(start.status_code, 200, start.text)

        dirty_at = datetime(2026, 6, 2, 10, 0, tzinfo=UTC).isoformat(timespec="seconds")
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                INSERT INTO domain_buildings (
                    domain_id, territory_id, building_id, purchased_at, source
                )
                VALUES ('domain_north', 'territory_res_north', 'b_barracks', ?, 'test')
                """,
                (dirty_at,),
            )
            connection.execute(
                """
                INSERT INTO army_reserve_runtime (
                    reserve_id, domain_id, card_id, count, status, updated_at
                )
                VALUES ('reserve_dirty_panel', 'domain_north', 'unit_infantry_t1', 9, 'available', ?)
                """,
                (dirty_at,),
            )
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count, location_node_id, status, updated_at
                )
                VALUES ('army_dirty_panel', 'domain_north', 'unit_infantry_t1', 3, 'node_res_north', 'active', ?)
                """,
                (dirty_at,),
            )
            connection.execute(
                """
                INSERT INTO garrison_runtime_state (
                    garrison_id, territory_id, domain_id, card_id, count, status, updated_at
                )
                VALUES ('garrison_dirty_panel', 'territory_res_north', 'domain_north', 'unit_guard_t1', 2, 'active', ?)
                """,
                (dirty_at,),
            )

        reset = client.post(
            "/api/master/acts/registration/start",
            headers={"X-Role-Token": "MASTER-KING-4QZ8"},
            json={"operator": "gm_reset", "physical_announcement_state": "announced"},
        )
        self.assertEqual(reset.status_code, 200, reset.text)

        summary = client.get(
            "/api/lords/p_lord_1/summary",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        self.assertEqual(summary.status_code, 200, summary.text)
        summary_payload = summary.json()
        self.assertEqual(summary_payload["timer_summary"]["current_act_id"], "registration")
        self.assertTrue(summary_payload["timer_summary"]["updated_at"])

        state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        self.assertEqual(state.status_code, 200, state.text)
        state_payload = state.json()
        self.assertEqual(state_payload["timer_summary"]["current_act_id"], "registration")
        self.assertEqual(state_payload["owned_buildings"], [])
        self.assertEqual(state_payload["army_reserve"], [])
        self.assertEqual(state_payload["active_army"], [])
        self.assertFalse(
            any(territory["garrisons"] for territory in state_payload["territory_views"])
        )

    def test_lord_battle_panel_uses_board_controls_without_raw_json_acceptance(self) -> None:
        settings = self._settings("lord_battle_board_contract")
        self._import_valid_seed(settings)
        self._set_reserve_count(settings, "reserve_north_infantry", 4)
        client = TestClient(create_app(settings))

        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 3,
            },
        )
        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "to_node_id": "node_fort_east",
                "route_node_ids": ["node_res_north", "node_fort_east"],
            },
        )
        self.assertEqual(active.status_code, 200, active.text)
        self.assertEqual(moved.status_code, 200, moved.text)
        self._complete_pending_moves(settings)
        battle = client.post(
            "/api/lord-battles",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "battle_id": "lord_panel_board_contract",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_fort_east",
                "seed": "lord-panel-board-contract",
            },
        )
        state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )

        self.assertEqual(battle.status_code, 200, battle.text)
        self.assertEqual(state.status_code, 200, state.text)
        panel_battle = state.json()["battles"][0]
        self.assertEqual(panel_battle["battle_id"], "lord_panel_board_contract")
        self.assertEqual(panel_battle["board"]["width"], 5)
        self.assertEqual(panel_battle["board"]["height"], 6)
        self.assertIn("active_stack_id", panel_battle)
        self.assertIn("hero_cells", panel_battle["board"])
        self.assertEqual(client.get("/lord").status_code, 404)
        self.assertEqual(client.get("/static/lord/lord.js").status_code, 404)

    def test_role_token_auth_returns_lord_identity(self) -> None:
        settings = self._settings("lord_auth")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        response = client.post(
            "/api/auth/role-token",
            json={"token": "LORD-NORTH-R8K4"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role_type"], "lord")
        self.assertEqual(payload["owner_id"], "p_lord_1")
        self.assertEqual(payload["lord_id"], "p_lord_1")
        self.assertEqual(payload["domain_id"], "domain_north")
        self.assertIn("lord_panel:read", payload["permissions"])

    def test_lord_player_code_auth_returns_lord_identity(self) -> None:
        settings = self._settings("lord_player_code_auth")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        response = client.post(
            "/api/auth/role-token",
            json={"token": "LC-NORTH-7QK2"},
        )
        witcher = client.post(
            "/api/auth/role-token",
            json={"token": "WC-WOLF-6GF4"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["token_id"], "code_lord_1")
        self.assertEqual(payload["role_type"], "lord")
        self.assertEqual(payload["owner_id"], "p_lord_1")
        self.assertEqual(payload["lord_id"], "p_lord_1")
        self.assertEqual(payload["domain_id"], "domain_north")
        self.assertIn("lord_panel:read", payload["permissions"])
        self.assertEqual(witcher.status_code, 401)

    def test_role_token_auth_returns_master_identity(self) -> None:
        settings = self._settings("master_auth")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        response = client.post(
            "/api/auth/role-token",
            json={"token": "MASTER-KING-4QZ8"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["role_type"], "npc_master")
        self.assertEqual(payload["owner_id"], "npc_king")
        self.assertIn("master:read", payload["permissions"])
        self.assertIn("master:write", payload["permissions"])

    def test_lord_state_is_visible_only_to_matching_lord_token(self) -> None:
        settings = self._settings("lord_state")
        report = self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        accepted = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        accepted_summary = client.get(
            "/api/lords/p_lord_1/summary",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        accepted_player_code = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LC-NORTH-7QK2"},
        )
        mismatched = client.get(
            "/api/lords/p_lord_2/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        invalid = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "NOT-A-TOKEN"},
        )
        missing = client.get("/api/lords/p_lord_1/state")
        master = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "MASTER-KING-4QZ8"},
        )

        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted_summary.status_code, 200)
        summary_payload = accepted_summary.json()
        self.assertEqual(summary_payload["lord"]["lord_id"], "p_lord_1")
        self.assertIn("current_mp", summary_payload["movement"])
        self.assertNotIn("territories", summary_payload)
        self.assertNotIn("territory_views", summary_payload)
        self.assertEqual(accepted_player_code.status_code, 200)
        self.assertEqual(accepted_player_code.json()["lord"]["lord_id"], "p_lord_1")
        payload = accepted.json()
        self.assertEqual(payload["snapshot_version"], report.snapshot_version)
        self.assertEqual(payload["lord"]["lord_id"], "p_lord_1")
        self.assertEqual(payload["domain"]["domain_id"], "domain_north")
        self.assertIn("income_per_hour", payload["domain"])
        self.assertIn("active_army_slots_used", payload["domain"])
        self.assertIn("raid_tokens", payload)
        self.assertTrue(payload["raid_rules"])
        self.assertTrue(payload["raid_targets"])
        self.assertIn("active_raid_effects", payload)
        self.assertIn("raid_history", payload)
        self.assertIn("locked_reason", payload["raid_rules"][0])
        self.assertIn("timer_summary", payload)
        self.assertIn("server_time", payload["timer_summary"])
        self.assertNotIn("challenge_tokens", payload["lord"])
        self.assertNotIn("challenge_tokens", payload["domain"])
        self.assertEqual(payload["summary"]["owned_territories"], 1)
        self.assertEqual(payload["summary"]["active_orders"], 3)
        self.assertEqual(payload["order_cap"]["public_active"], 2)
        self.assertEqual(payload["order_cap"]["public_limit"], 0)
        self.assertFalse(payload["order_cap"]["public_unlocked"])
        self.assertEqual(payload["order_cap"]["addressed_active"], 1)
        self.assertEqual(payload["order_cap"]["addressed_limit"], 0)
        self.assertFalse(payload["order_cap"]["addressed_unlocked"])
        self.assertEqual(payload["order_cap"]["raid_public_penalty"], 0)
        self.assertEqual(payload["escrow"]["locked_gold"], 45)
        self.assertEqual(payload["escrow"]["available_gold"], 80)
        self.assertGreaterEqual(payload["escrow"]["locked_asset_count"], 3)
        self.assertTrue(payload["visible_targets"])
        self.assertTrue(
            any(
                target["source"] == "order_interest_objects"
                for target in payload["visible_targets"]
            )
        )
        self.assertTrue(
            any(target["target_type"] == "card" for target in payload["visible_targets"])
        )
        self.assertTrue(
            any(target["target_type"] == "artifact" for target in payload["visible_targets"])
        )
        self.assertTrue(
            any(target["target_type"] == "treasure" for target in payload["visible_targets"])
        )
        self.assertTrue(payload["eligible_recipients"])
        self.assertEqual(
            {"witcher"},
            {recipient["role_type"] for recipient in payload["eligible_recipients"]},
        )
        self.assertTrue(payload["order_reward_options"])
        self.assertIn("order_conflicts", payload)
        first_order = payload["orders"][0]
        self.assertIn("object_label", first_order)
        self.assertIn("visible_hook", first_order)
        self.assertIn("reward_label", first_order)
        self.assertIn("escrow_label", first_order)
        self.assertTrue(payload["territories"])
        self.assertIn("income_per_hour", payload["territories"][0])
        self.assertIn("garrison_slots_used", payload["territories"][0]["fort"])
        self.assertIn("garrison_slots_free", payload["territories"][0]["fort"])
        self.assertTrue(payload["recruit_market"])
        self.assertEqual(
            len(payload["recruit_market"]),
            len({offer["card_id"] for offer in payload["recruit_market"]}),
        )
        self.assertTrue(
            all(
                offer["status"] in {"available", "held"}
                for offer in payload["recruit_market"]
            )
        )
        infantry_offer = next(
            offer
            for offer in payload["recruit_market"]
            if offer["card_id"] == "unit_infantry_t1"
        )
        self.assertEqual(infantry_offer["current_stock"], 24)
        self.assertEqual(infantry_offer["rate_per_hour"], 24)
        self.assertEqual(infantry_offer["unit"]["attack_range"], 1)
        self.assertEqual(infantry_offer["unit"]["initiative"], 3)
        signals = {item["domain_id"]: item for item in payload["diplomacy_signals"]}
        self.assertEqual(signals["domain_north"]["active_orders"], 3)
        self.assertEqual(signals["domain_north"]["active_order_visibility"], "own_exact")
        self.assertNotIn("active_orders", signals["domain_river"])
        self.assertIn(
            signals["domain_river"]["active_order_pressure"],
            {"none", "low", "medium", "high"},
        )
        self.assertEqual(signals["domain_river"]["active_order_visibility"], "foreign_coarse")
        self.assertEqual(
            {surface["status"] for surface in payload["action_surfaces"]},
            {"ready"},
        )
        self.assertEqual(mismatched.status_code, 403)
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(master.status_code, 403)

    def test_territory_views_scope_owned_fort_without_moving_active_army(self) -> None:
        settings = self._settings("lord_territory_views")
        self._import_valid_seed(settings)
        self._set_reserve_count(settings, "reserve_north_infantry", 4)
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_north',
                    status = 'controlled',
                    contested_by_domain_id = NULL
                WHERE territory_id = 'territory_fort_east'
                """
            )
        client = TestClient(create_app(settings))

        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )

        self.assertEqual(active.status_code, 200, active.text)
        self.assertEqual(state.status_code, 200, state.text)
        payload = state.json()
        castle_view = self._territory(payload["territory_views"], "territory_res_north")
        fort_view = self._territory(payload["territory_views"], "territory_fort_east")
        stored_fort = self._territory(payload["territories"], "territory_fort_east")

        self.assertTrue(castle_view["active_army_present"])
        self.assertEqual(castle_view["active_army_lock_reason"], "")
        self.assertTrue(fort_view["is_owned"])
        self.assertTrue(fort_view["is_selectable"])
        self.assertFalse(fort_view["active_army_present"])
        self.assertTrue(fort_view["active_army_lock_reason"])
        self.assertIn(
            "active_army_not_here",
            {reason["code"] for reason in fort_view["lock_reasons"]},
        )
        self.assertEqual(fort_view["owner_domain_id"], "domain_north")
        self.assertEqual(stored_fort["owner_domain_id"], "domain_north")
        self.assertEqual(
            fort_view["bonuses"][0]["effect_type"],
            "raid_defense_flat",
        )
        self.assertTrue(fort_view["bonuses"][0]["public_label"])
        self.assertTrue(fort_view["recruit_stock"])
        self.assertEqual(fort_view["building_tree"]["node_ids"], [])
        self.assertEqual(fort_view["building_tree"]["nodes"], [])
        self.assertEqual(fort_view["building_tree"]["status"], "locked")
        self.assertEqual(fort_view["building_tree"]["scope"], "residence_only")
        self.assertEqual(
            fort_view["building_tree_lock_reason"],
            "Здания строятся в главном замке",
        )

    def test_empty_active_army_keeps_current_residence_usable_for_transfer(self) -> None:
        settings = self._settings("lord_empty_active_army_home")
        self._import_valid_seed(settings)
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                "DELETE FROM active_army_runtime WHERE domain_id = 'domain_north'"
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET current_node_id = 'node_res_north'
                WHERE domain_id = 'domain_north'
                """
            )
        client = TestClient(create_app(settings))

        state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )

        self.assertEqual(state.status_code, 200, state.text)
        payload = state.json()
        residence = self._territory(payload["territory_views"], "territory_res_north")
        self.assertTrue(residence["hero_here"])
        self.assertFalse(residence["active_army_present"])
        self.assertEqual(residence["active_army_lock_reason"], "")
        self.assertNotIn(
            "active_army_not_here",
            {reason["reason_code"] for reason in residence["lock_reasons"]},
        )

    def test_all_four_lord_panels_can_load_their_own_state(self) -> None:
        settings = self._settings("lord_four_panels")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))
        expected = {
            "p_lord_1": ("LORD-NORTH-R8K4", "domain_north"),
            "p_lord_2": ("LORD-RIVER-M2J9", "domain_river"),
            "p_lord_3": ("LORD-FOREST-P6W3", "domain_forest"),
            "p_lord_4": ("LORD-HILL-T5C7", "domain_hill"),
        }

        for lord_id, (token, domain_id) in expected.items():
            with self.subTest(lord_id=lord_id):
                response = client.get(
                    f"/api/lords/{lord_id}/state",
                    headers={"X-Role-Token": token},
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["lord"]["lord_id"], lord_id)
        self.assertEqual(payload["domain"]["domain_id"], domain_id)
        self.assertEqual(payload["summary"]["owned_territories"], 1)

    def test_lord_state_exposes_ui_ready_territory_views_and_building_effects(self) -> None:
        settings = self._settings("lord_state_contract")
        self._import_valid_seed(settings)
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_north',
                    status = 'controlled',
                    contested_by_domain_id = NULL
                WHERE territory_id = 'territory_fort_east'
                """
            )
        client = TestClient(create_app(settings))

        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )

        self.assertEqual(active.status_code, 200, active.text)
        self.assertEqual(state.status_code, 200, state.text)
        payload = state.json()
        self.assertEqual(payload["resources"]["gold"], payload["domain"]["gold"])
        self.assertEqual(payload["resources"]["current_mp"], payload["domain"]["current_mp"])
        self.assertEqual(payload["resources"]["raid_tokens"], payload["domain"]["raid_tokens"])
        self.assertIn("territory_views", payload)
        self.assertIn("active_army_location", payload)
        self.assertEqual(
            payload["active_army_location"]["territory_id"], "territory_res_north"
        )
        residence = self._territory(payload["territory_views"], "territory_res_north")
        self.assertEqual(residence["owner"]["relation"], "self")
        self.assertEqual(residence["status"], "controlled")
        self.assertGreater(residence["income_per_hour"], 0)
        self.assertTrue(residence["hero_here"])
        self.assertIn("garrison_capacity", residence["fort"])
        self.assertIn("garrison_stacks", residence)
        self.assertTrue(residence["recruit_stock"])
        infantry_stock = next(
            stock
            for stock in residence["recruit_stock"]
            if stock["card_id"] == "unit_infantry_t1"
        )
        self.assertGreater(infantry_stock["current_stock"], 0)
        self.assertGreater(infantry_stock["rate_per_hour"], 0)
        self.assertGreaterEqual(infantry_stock["max_purchasable"], 1)
        self.assertEqual(infantry_stock["gold_cost"], infantry_stock["cost"])
        self.assertEqual(
            infantry_stock["garrison_capacity"],
            residence["fort"]["garrison_capacity"],
        )
        self.assertEqual(
            infantry_stock["garrison_slots_used"],
            residence["fort"]["garrison_slots_used"],
        )
        self.assertEqual(infantry_stock["purchase_payload"]["territory_id"], "territory_res_north")
        self.assertEqual(infantry_stock["purchase_payload"]["action"], "purchase_stock")
        self.assertEqual(infantry_stock["purchase_payload"]["card_id"], "unit_infantry_t1")
        self.assertNotIn("offer_id", infantry_stock["purchase_payload"])
        self.assertIn("can_recruit", infantry_stock)
        self.assertEqual(residence["building_tree_status"], "available")
        building_nodes_by_id = {
            node["building_id"]: node for node in residence["building_tree"]["nodes"]
        }
        mage_study = building_nodes_by_id["b_mage_study"]
        training_yard = building_nodes_by_id["b_training_yard"]
        raid_office = building_nodes_by_id["b_raid_office"]
        self.assertTrue(
            all(node["effect_labels"] for node in residence["building_tree"]["nodes"])
        )
        self.assertIn("effect_labels", mage_study)
        self.assertTrue(mage_study["effect_labels"])
        self.assertIn("Защита резиденции от рейдов +1", mage_study["effect_labels"])
        self.assertNotIn(
            "Магическая ветка: открывает лабораторию и комнату видений",
            mage_study["effect_labels"],
        )
        self.assertIn("Максимум активной армии +1", training_yard["effect_labels"])
        self.assertIn("Открывает найм мечников", training_yard["effect_labels"])
        self.assertIn("Кап рейдовых жетонов +2", raid_office["effect_labels"])
        self.assertIn("Открывает территориальные рейды", raid_office["effect_labels"])
        forbidden_military_words = ("запас", "прирост", "/час", "HP", "атака", "дальность")
        for node in residence["building_tree"]["nodes"]:
            if node["branch"] != "military":
                continue
            joined_labels = " ".join(node["effect_labels"])
            self.assertFalse(
                any(word in joined_labels for word in forbidden_military_words),
                joined_labels,
            )
        for node in residence["building_tree"]["nodes"]:
            self.assertFalse(
                any(str(label).startswith("Unlocks buildings") for label in node["effect_labels"])
            )
        self.assertIn("properties", mage_study["effects"])
        self.assertTrue(mage_study["effects"]["properties"])
        self.assertIn(
            "Магическая ветка: защита и разведка владения",
            mage_study["effects"]["properties"],
        )
        self.assertEqual(mage_study["purchase_payload"]["territory_id"], "territory_res_north")
        self.assertEqual(
            {item["building_id"] for item in mage_study["effects"]["unlocks"]},
            {"b_alchemy_lab", "b_scrying_room"},
        )
        self.assertIn("capacity_delta", mage_study["effects"])
        self.assertIn("raid_unlock", mage_study["effects"])
        self.assertIn("recruit_unlocks", mage_study["effects"])

        remote_owned = self._territory(payload["territory_views"], "territory_fort_east")
        self.assertFalse(remote_owned["hero_here"])
        self.assertIn(
            "active_army_not_here",
            {reason["reason_code"] for reason in remote_owned["lock_reasons"]},
        )

    def test_lord_action_errors_return_stable_reason_code(self) -> None:
        settings = self._settings("lord_action_reason_codes")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))
        cases = (
            (
                "/api/lords/p_lord_1/move",
                {},
                "missing_route",
            ),
            (
                "/api/lords/p_lord_1/buildings",
                {"building_id": "b_barracks"},
                "missing_prerequisites",
            ),
            (
                "/api/lords/p_lord_1/recruit",
                {"action": "purchase"},
                "missing_offer",
            ),
            (
                "/api/lords/p_lord_1/raids",
                {"target_territory_id": "territory_res_north"},
                "invalid_target",
            ),
        )

        for url, body, expected_reason_code in cases:
            with self.subTest(url=url):
                response = client.post(
                    url,
                    headers={"X-Role-Token": "LORD-NORTH-R8K4"},
                    json=body,
                )

                self.assertGreaterEqual(response.status_code, 400, response.text)
                self.assertEqual(response.json()["detail"]["code"], expected_reason_code)
                self.assertEqual(
                    response.json()["detail"]["reason_code"], expected_reason_code
                )

    def test_recruit_stock_read_model_explains_empty_stock_and_contested_lock(self) -> None:
        settings = self._settings("lord_recruit_stock_read_model_locks")
        self._import_valid_seed(settings)
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE army_reserve_runtime
                SET count = 0,
                    status = 'available'
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                """
            )
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_north',
                    status = 'contested',
                    contested_by_domain_id = 'domain_river'
                WHERE territory_id = 'territory_fort_east'
                """
            )
        client = TestClient(create_app(settings))

        state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )

        self.assertEqual(state.status_code, 200, state.text)
        payload = state.json()
        residence = self._territory(payload["territory_views"], "territory_res_north")
        empty_stock = next(
            stock
            for stock in residence["recruit_stock"]
            if stock["card_id"] == "unit_infantry_t1"
        )
        self.assertEqual(empty_stock["current_stock"], 0)
        self.assertEqual(empty_stock["max_purchasable"], 0)
        empty_reasons = {reason["reason_code"]: reason for reason in empty_stock["lock_reasons"]}
        self.assertIn("insufficient_stock", empty_reasons)
        self.assertIn("Нет накопленного найма", empty_reasons["insufficient_stock"]["message"])

        contested = self._territory(payload["territory_views"], "territory_fort_east")
        contested_reasons = {
            reason["reason_code"]: reason for reason in contested["lock_reasons"]
        }
        self.assertIn("territory_contested", contested_reasons)
        self.assertIn("Спорная территория", contested_reasons["territory_contested"]["message"])
        contested_stock = next(
            stock
            for stock in contested["recruit_stock"]
            if stock["card_id"] == "unit_infantry_t1"
        )
        self.assertFalse(contested_stock["can_recruit"])
        self.assertEqual(contested_stock["max_purchasable"], 0)

    def _settings(self, name: str) -> Settings:
        return Settings(
            database_path=PROJECT_ROOT / ".test-data" / f"{name}_{uuid4().hex}.db"
        )

    def _import_valid_seed(self, settings: Settings):
        report = import_seed_pack(
            settings,
            manifest_path=PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "seed_valid"
            / "fixture_manifest.csv",
            snapshot_dir=None,
        )
        self.assertEqual(report.status, "success")
        return report

    def _set_reserve_count(self, settings: Settings, reserve_id: str, count: int) -> None:
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                "UPDATE army_reserve_runtime SET count = ? WHERE reserve_id = ?",
                (count, reserve_id),
            )

    def _complete_pending_moves(
        self, settings: Settings, domain_id: str = "domain_north"
    ) -> list[dict[str, object]]:
        with connect(settings) as connection:
            return reconcile_pending_lord_moves(
                connection,
                domain_id=domain_id,
                now=datetime.now(UTC) + timedelta(minutes=1),
            )

    def _start_battle_after_deployment(
        self,
        client: TestClient,
        battle_id: str,
        *,
        attacker_lord: str = "north",
        defender_lord: str = "river",
    ) -> dict[str, object]:
        battle = client.get(
            f"/api/lord-battles/{battle_id}",
            headers={"X-Role-Token": "MASTER-KING-4QZ8"},
        ).json()
        board = battle["board"]
        deployment = battle["deployment"]
        for side, lord in (("attacker", attacker_lord), ("defender", defender_lord)):
            if side == "defender" and battle["battle_type"] == "neutral":
                continue
            headers = self._lord_headers(lord)
            for index, item in enumerate(deployment["hand"][side][: int(deployment["deployment_cap"])]):
                x, y = self._deployment_cell(board, side, index)
                deployed = client.post(
                    f"/api/lord-battles/{battle_id}/actions",
                    headers=headers,
                    json={
                        "action_id": f"deploy-{battle_id}-{side}-{index}",
                        "action_type": "deploy",
                        "actor_side": side,
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
                headers=headers,
                json={
                    "action_id": f"ready-{battle_id}-{side}",
                    "action_type": "ready",
                    "actor_side": side,
                },
            )
            self.assertEqual(ready.status_code, 200, ready.text)
            if isinstance(ready.json().get("battle"), dict):
                battle = ready.json()["battle"]
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

    @staticmethod
    def _lord_headers(lord: str) -> dict[str, str]:
        tokens = {
            "north": "LORD-NORTH-R8K4",
            "river": "LORD-RIVER-M2J9",
            "forest": "LORD-FOREST-P6W3",
            "hill": "LORD-HILL-T5C7",
        }
        return {"X-Role-Token": tokens[lord]}

    @staticmethod
    def _territory(
        territories: list[dict[str, object]],
        territory_id: str,
    ) -> dict[str, object]:
        for territory in territories:
            if territory["territory_id"] == territory_id:
                return territory
        raise AssertionError(f"Missing territory {territory_id}")

    @staticmethod
    def _claim(
        claims: list[dict[str, object]],
        territory_id: str,
    ) -> dict[str, object]:
        for claim in claims:
            if claim["territory_id"] == territory_id:
                return claim
        raise AssertionError(f"Missing claim for {territory_id}")


if __name__ == "__main__":
    unittest.main()
