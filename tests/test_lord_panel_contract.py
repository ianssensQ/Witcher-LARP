from __future__ import annotations

import unittest
from uuid import uuid4

from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.lord_runtime import ensure_lord_runtime_state

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


@unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
class LordPanelContractTests(unittest.TestCase):
    def setUp(self) -> None:
        (PROJECT_ROOT / ".test-data").mkdir(exist_ok=True)

    def test_lord_static_panel_is_served_without_node_build(self) -> None:
        client = TestClient(create_app(self._settings("lord_static")))

        page = client.get("/lord")
        script = client.get("/static/lord/lord.js")
        styles = client.get("/static/lord/lord.css")

        self.assertEqual(page.status_code, 200)
        self.assertIn('data-app="lord-panel"', page.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("/api/auth/role-token", script.text)
        self.assertIn("route_node_ids", script.text)
        self.assertIn("buildRoute", script.text)
        self.assertIn("battlePayloadFor", script.text)
        self.assertIn("/api/lord-battles/", script.text)
        self.assertNotIn("payload_json", script.text)
        self.assertIn('id="battle-board"', page.text)
        self.assertIn('data-battle-command="move"', page.text)
        self.assertIn('data-battle-command="attack"', page.text)
        self.assertNotIn('data-action-form="battle-action"', page.text)
        self.assertNotIn("Payload JSON", page.text)
        self.assertEqual(styles.status_code, 200)
        self.assertIn("[hidden]", styles.text)
        self.assertIn(".battle-board", styles.text)
        self.assertFalse(
            (PROJECT_ROOT / "backend" / "witcher_larp" / "web" / "package.json").exists()
        )

    def test_lord_panel_action_controls_execute_role_scoped_apis(self) -> None:
        settings = self._settings("lord_action_behavior")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        page = client.get("/lord")
        self.assertEqual(page.status_code, 200)
        self.assertIn('data-action-form="move"', page.text)
        self.assertIn('id="move-route-preview"', page.text)
        self.assertIn('data-action-form="garrison"', page.text)
        self.assertIn('data-action-form="building"', page.text)
        self.assertIn('data-action-form="recruit"', page.text)
        self.assertIn('data-action-form="raid"', page.text)
        self.assertIn('data-action-form="order"', page.text)
        self.assertIn('data-action-form="battle-create"', page.text)
        self.assertNotIn('data-action-form="battle-action"', page.text)
        self.assertNotIn("read-only", page.text.lower())

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
        self.assertEqual(moved_payload["mp_spent"], 2)
        self.assertEqual(moved_payload["route"], ["node_res_north", "node_fort_east"])
        self.assertEqual(moved_payload["claim"]["territory_id"], "territory_fort_east")

        battle = client.post(
            "/api/lord-battles",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "battle_id": "lord_panel_battle_contract",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_fort_east",
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
        self.assertIn("map_edges", state.json())
        self.assertTrue(state.json()["map_edges"])
        self.assertIn(
            "move",
            {surface["id"] for surface in state.json()["action_surfaces"]},
        )
        self.assertIn(
            "lord_battles",
            {surface["id"] for surface in state.json()["action_surfaces"]},
        )
        self.assertIn("battles", state.json())

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

    def test_capture_pending_foreign_territory_is_garrison_target_from_panel(self) -> None:
        settings = self._settings("lord_capture_pending_panel")
        self._import_valid_seed(settings)
        self._set_reserve_count(settings, "reserve_north_infantry", 6)
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
                "to_node_id": "node_res_river",
                "route_node_ids": [
                    "node_res_north",
                    "node_fort_east",
                    "node_village_barn",
                    "node_well_city",
                    "node_res_river",
                ],
            },
        )
        battle = client.post(
            "/api/lord-battles",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "battle_id": "lord_panel_foreign_capture",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_res_river",
                "seed": "lord-panel-foreign-capture",
            },
        )
        resolved = client.post(
            "/api/lord-battles/lord_panel_foreign_capture/actions",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "action_id": "resolve-foreign-capture",
                "action_type": "auto_resolve",
                "actor_side": "attacker",
            },
        )

        self.assertEqual(active.status_code, 200, active.text)
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(battle.status_code, 200, battle.text)
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
        target = self._territory(payload["garrison_targets"], "territory_res_river")
        self.assertEqual(target["owner_domain_id"], "domain_river")
        self.assertEqual(target["status"], "capture_pending_garrison")
        self.assertEqual(target["contested_by_domain_id"], "domain_north")
        self.assertEqual(target["garrison_target_reason"], "capture_pending_garrison")
        self.assertEqual(payload["summary"]["garrison_targets"], 2)

        captured = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "operation": "active_to_fort",
                "territory_id": "territory_res_river",
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
        river_residence = self._territory(
            captured_state["territories"],
            "territory_res_river",
        )
        self.assertEqual(river_residence["owner_domain_id"], "domain_north")
        self.assertEqual(river_residence["status"], "controlled")

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
        page = client.get("/lord")
        script = client.get("/static/lord/lord.js")

        self.assertEqual(active.status_code, 200, active.text)
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(battle.status_code, 200, battle.text)
        self.assertEqual(state.status_code, 200, state.text)
        panel_battle = state.json()["battles"][0]
        self.assertEqual(panel_battle["battle_id"], "lord_panel_board_contract")
        self.assertEqual(panel_battle["board"]["width"], 5)
        self.assertEqual(panel_battle["board"]["height"], 6)
        self.assertIn("active_stack_id", panel_battle)
        self.assertIn("hero_cells", panel_battle["board"])
        self.assertIn('id="battle-board"', page.text)
        self.assertIn('data-battle-command="move"', page.text)
        self.assertIn('data-battle-command="attack"', page.text)
        self.assertIn('data-battle-command="surrender"', page.text)
        self.assertIn("battlePayloadFor", script.text)
        self.assertIn("selectedBattleTarget", script.text)
        self.assertNotIn('name="battle_id"', page.text)
        self.assertNotIn('name="actor_side"', page.text)
        self.assertNotIn("payload_json", script.text)

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
        payload = accepted.json()
        self.assertEqual(payload["snapshot_version"], report.snapshot_version)
        self.assertEqual(payload["lord"]["lord_id"], "p_lord_1")
        self.assertEqual(payload["domain"]["domain_id"], "domain_north")
        self.assertNotIn("challenge_tokens", payload["lord"])
        self.assertNotIn("challenge_tokens", payload["domain"])
        self.assertEqual(payload["summary"]["owned_territories"], 1)
        self.assertEqual(payload["summary"]["active_orders"], 3)
        self.assertTrue(payload["territories"])
        self.assertTrue(payload["recruit_market"])
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

    @staticmethod
    def _territory(
        territories: list[dict[str, object]],
        territory_id: str,
    ) -> dict[str, object]:
        for territory in territories:
            if territory["territory_id"] == territory_id:
                return territory
        raise AssertionError(f"Missing territory {territory_id}")


if __name__ == "__main__":
    unittest.main()
