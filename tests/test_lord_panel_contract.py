from __future__ import annotations

import unittest
from uuid import uuid4

from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.import_service import import_seed_pack

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
        self.assertEqual(styles.status_code, 200)
        self.assertIn("[hidden]", styles.text)
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
        self.assertIn('data-action-form="battle-action"', page.text)
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
        self.assertEqual(moved.status_code, 200, moved.text)
        moved_payload = moved.json()
        self.assertEqual(moved_payload["mp_spent"], 2)
        self.assertEqual(moved_payload["route"], ["node_res_north", "node_fort_east"])
        self.assertEqual(moved_payload["claim"]["territory_id"], "territory_fort_east")

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


if __name__ == "__main__":
    unittest.main()
