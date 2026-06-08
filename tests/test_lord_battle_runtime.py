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


FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"
TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
MASTER_HEADERS = {"X-Role-Token": "MASTER-KING-4QZ8"}
UNIT_CLASSES = {
    "infantry",
    "guard",
    "ranged",
    "cavalry",
    "heavy_siege",
    "specialist",
}


@unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
class LordBattleRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_neutral_ai_master_takeover_capture_handoff_and_persistence(self) -> None:
        settings = self._settings("lord_battle_neutral")
        self._import_seed(settings)
        client = TestClient(create_app(settings))
        self._set_reserve_count(settings, "reserve_north_infantry", 4)

        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 3,
            },
        )
        self.assertEqual(active.status_code, 200)
        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={"to_node_id": "node_field_oats"},
        )
        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.json()["status"], "pending_move")
        completed = self._complete_pending_moves(settings)
        self.assertIn(completed[0]["claim"]["status"], {"in_battle", "contested_pending_tick"})

        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_neutral_field",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_field_oats",
                "seed": "neutral-field-seed",
            },
        )
        self.assertEqual(created.status_code, 200)
        battle = created.json()
        self.assertEqual(battle["battle_type"], "neutral")
        self.assertEqual(battle["defender_control"], "neutral_ai")
        self.assertEqual(battle["board"]["width"], 5)
        self.assertEqual(battle["board"]["height"], 6)
        self.assertIn("deployment_recorded", [entry["entry_type"] for entry in battle["battle_log"]])
        self.assertEqual(battle["deployment"]["hand"]["attacker"][0]["card_id"], "unit_infantry_t1")

        invalid_deploy = client.post(
            "/api/lord-battles/battle_neutral_field/actions",
            headers=self._headers("north"),
            json={
                "action_id": "invalid-deploy",
                "action_type": "deploy",
                "actor_side": "attacker",
                "payload": {"card_id": "unit_heavy_siege_t3"},
            },
        )
        self.assertEqual(invalid_deploy.status_code, 400)
        self.assertEqual(invalid_deploy.json()["detail"]["code"], "deployment_card_not_in_hand")

        defended = client.post(
            "/api/lord-battles/battle_neutral_field/actions",
            headers=self._headers("north"),
            json={
                "action_id": "attacker-defend",
                "action_type": "defend",
                "actor_side": "attacker",
            },
        )
        self.assertEqual(defended.status_code, 200)
        duplicate_defended = client.post(
            "/api/lord-battles/battle_neutral_field/actions",
            headers=self._headers("north"),
            json={
                "action_id": "attacker-defend",
                "action_type": "defend",
                "actor_side": "attacker",
            },
        )
        self.assertEqual(duplicate_defended.status_code, 200)
        self.assertFalse(defended.json()["duplicate"])
        self.assertTrue(duplicate_defended.json()["duplicate"])
        self.assertEqual(duplicate_defended.json()["status"], defended.json()["status"])
        ai_turn = client.post(
            "/api/lord-battles/battle_neutral_field/actions",
            headers=MASTER_HEADERS,
            json={
                "action_id": "neutral-ai-turn",
                "action_type": "ai_turn",
                "actor_side": "defender",
            },
        )
        self.assertEqual(ai_turn.status_code, 200)
        takeover = client.post(
            "/api/lord-battles/battle_neutral_field/actions",
            headers=MASTER_HEADERS,
            json={
                "action_id": "master-takeover",
                "action_type": "master_takeover",
                "actor_side": "defender",
            },
        )
        self.assertEqual(takeover.status_code, 200)
        self.assertEqual(takeover.json()["defender_control"], "master")

        resolved = client.post(
            "/api/lord-battles/battle_neutral_field/actions",
            headers=self._headers("north"),
            json={
                "action_id": "resolve-neutral",
                "action_type": "auto_resolve",
                "actor_side": "attacker",
            },
        )
        self.assertEqual(resolved.status_code, 200)
        result = resolved.json()["battle"]["result"]
        self.assertEqual(result["winner_side"], "attacker")
        self.assertEqual(result["capture"]["status"], "capture_pending_garrison")
        self.assertTrue(result["capture"]["garrison_required"])

        captured = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "territory_id": "territory_field_oats",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(captured.status_code, 200)
        self.assertEqual(captured.json()["status"], "captured")

        restarted = TestClient(create_app(settings))
        persisted = restarted.get(
            "/api/lord-battles/battle_neutral_field",
            headers=self._headers("north"),
        )
        self.assertEqual(persisted.status_code, 200)
        payload = persisted.json()
        self.assertEqual(payload["status"], "finished")
        self.assertTrue(payload["burned_cards"])
        self.assertIn(
            "lord_battle_finished",
            [entry["entry_type"] for entry in payload["battle_log"]],
        )

    def test_lord_vs_lord_garrison_active_defense_and_repeated_timeout_auto_resolve(self) -> None:
        settings = self._settings("lord_battle_timeout")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_cavalry", "domain_north", "unit_cavalry_t2", 2, "node_res_river"),
                ("army_river_ranged", "domain_river", "unit_ranged_t1", 1, "node_res_river"),
            ],
        )
        client = TestClient(create_app(settings))

        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_river_timeout",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "river-timeout-seed",
            },
        )
        self.assertEqual(created.status_code, 200)
        battle = created.json()
        self.assertEqual(battle["battle_type"], "lord_vs_lord")
        defender_sources = {item["source_type"] for item in battle["deployment"]["hand"]["defender"]}
        self.assertIn("garrison", defender_sources)
        self.assertIn("active_army", defender_sources)

        last_payload = battle
        for index in range(4):
            side = last_payload["active_side"]
            response = client.post(
                "/api/lord-battles/battle_river_timeout/actions",
                headers=self._headers("north" if side == "attacker" else "river"),
                json={
                    "action_id": f"timeout-{index}",
                    "action_type": "timeout",
                    "actor_side": side,
                },
            )
            self.assertEqual(response.status_code, 200)
            last_payload = response.json()["battle"]
            if last_payload["status"] == "finished":
                break

        self.assertEqual(last_payload["status"], "finished")
        self.assertEqual(last_payload["result"]["outcome"], "auto_resolve")
        self.assertEqual(last_payload["result"]["reason"], "repeated_timeout")
        self.assertGreaterEqual(
            max(last_payload["timeout_counts"].values()),
            2,
        )
        self.assertIn(
            "lord_battle_turn_timeout",
            [entry["entry_type"] for entry in last_payload["battle_log"]],
        )

        persisted = TestClient(create_app(settings)).get(
            "/api/lord-battles/battle_river_timeout",
            headers=MASTER_HEADERS,
        )
        self.assertEqual(persisted.status_code, 200)
        self.assertEqual(persisted.json()["status"], "finished")
        self.assertTrue(persisted.json()["burned_cards"])

    def test_unit_class_fixtures_damage_los_and_retaliation(self) -> None:
        for unit_class, card_id in {
            "infantry": "unit_infantry_t1",
            "guard": "unit_guard_t1",
            "ranged": "unit_ranged_t1",
            "cavalry": "unit_cavalry_t2",
            "heavy_siege": "unit_heavy_siege_t3",
            "specialist": "unit_specialist_t3",
        }.items():
            with self.subTest(unit_class=unit_class):
                settings = self._settings(f"lord_battle_{unit_class}")
                self._import_seed(settings)
                self._set_active_armies(
                    settings,
                    current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
                    rows=[
                        (f"army_north_{unit_class}", "domain_north", card_id, 1, "node_res_river"),
                    ],
                    clear_existing=True,
                )
                client = TestClient(create_app(settings))
                created = client.post(
                    "/api/lord-battles",
                    headers=self._headers("north"),
                    json={
                        "battle_id": f"battle_fixture_{unit_class}",
                        "attacker_domain_id": "domain_north",
                        "defender_domain_id": "domain_river",
                        "territory_id": "territory_res_river",
                        "seed": f"class-{unit_class}",
                    },
                )
                self.assertEqual(created.status_code, 200)
                attacker_classes = {
                    item["unit_class"] for item in created.json()["deployment"]["hand"]["attacker"]
                }
                self.assertIn(unit_class, attacker_classes)

        settings = self._settings("lord_battle_los")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_ranged", "domain_north", "unit_ranged_t1", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        client = TestClient(create_app(settings))
        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_los_damage",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "los-damage",
            },
        )
        self.assertEqual(created.status_code, 200)
        attack = client.post(
            "/api/lord-battles/battle_los_damage/actions",
            headers=self._headers("north"),
            json={
                "action_id": "ranged-los-attack",
                "action_type": "attack",
                "actor_side": "attacker",
                "payload": {"target_stack_id": "D1"},
            },
        )
        self.assertEqual(attack.status_code, 200)
        self.assertEqual(attack.json()["damage"], 1)
        self.assertIsNone(attack.json()["retaliation"])

        settings = self._settings("lord_battle_retaliation")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_cavalry", "domain_north", "unit_cavalry_t2", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        client = TestClient(create_app(settings))
        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_retaliation",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "retaliation",
            },
        )
        self.assertEqual(created.status_code, 200)
        move = client.post(
            "/api/lord-battles/battle_retaliation/actions",
            headers=self._headers("north"),
            json={
                "action_id": "cavalry-close",
                "action_type": "move",
                "actor_side": "attacker",
                "payload": {"to": {"x": 0, "y": 3}},
            },
        )
        self.assertEqual(move.status_code, 200)
        melee = client.post(
            "/api/lord-battles/battle_retaliation/actions",
            headers=self._headers("river"),
            json={
                "action_id": "guard-melee",
                "action_type": "attack",
                "actor_side": "defender",
                "payload": {"target_stack_id": "A1"},
            },
        )
        self.assertEqual(melee.status_code, 200)
        self.assertEqual(melee.json()["damage"], 1)
        self.assertIsNotNone(melee.json()["retaliation"])
        self.assertEqual(melee.json()["retaliation"]["damage"], 2)

    def test_lord_battle_api_requires_owner_or_master_token(self) -> None:
        settings = self._settings("lord_battle_auth")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_auth", "domain_north", "unit_infantry_t1", 1, "node_res_river"),
                ("army_river_auth", "domain_river", "unit_guard_t1", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        client = TestClient(create_app(settings))
        create_payload = {
            "battle_id": "battle_auth_check",
            "attacker_domain_id": "domain_north",
            "defender_domain_id": "domain_river",
            "territory_id": "territory_res_river",
            "seed": "auth-check",
        }

        missing = client.post("/api/lord-battles", json=create_payload)
        self.assertEqual(missing.status_code, 401)

        wrong_lord = client.post(
            "/api/lord-battles",
            headers=self._headers("river"),
            json=create_payload,
        )
        self.assertEqual(wrong_lord.status_code, 403)
        self.assertEqual(wrong_lord.json()["detail"]["code"], "wrong_actor_domain")

        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json=create_payload,
        )
        self.assertEqual(created.status_code, 200, created.text)

        missing_action = client.post(
            "/api/lord-battles/battle_auth_check/actions",
            json={"action_id": "missing-action", "action_type": "defend", "actor_side": "attacker"},
        )
        self.assertEqual(missing_action.status_code, 401)

        wrong_action = client.post(
            "/api/lord-battles/battle_auth_check/actions",
            headers=self._headers("river"),
            json={"action_id": "wrong-action", "action_type": "defend", "actor_side": "attacker"},
        )
        self.assertEqual(wrong_action.status_code, 403)
        self.assertEqual(wrong_action.json()["detail"]["code"], "wrong_actor_domain")

        master_created = client.post(
            "/api/lord-battles",
            headers=MASTER_HEADERS,
            json={
                **create_payload,
                "battle_id": "battle_master_created",
                "seed": "master-auth-check",
            },
        )
        self.assertEqual(master_created.status_code, 200, master_created.text)

    def test_lord_battle_list_and_get_are_scoped_to_participant_lord_or_master(self) -> None:
        settings = self._settings("lord_battle_visibility")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_visibility", "domain_north", "unit_infantry_t1", 1, "node_res_river"),
                ("army_river_visibility", "domain_river", "unit_guard_t1", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        client = TestClient(create_app(settings))

        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_visibility_check",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "visibility-check",
            },
        )
        missing_list_auth = client.get("/api/lord-battles")
        north_list = client.get("/api/lord-battles", headers=self._headers("north"))
        river_get = client.get(
            "/api/lord-battles/battle_visibility_check",
            headers=self._headers("river"),
        )
        forest_get = client.get(
            "/api/lord-battles/battle_visibility_check",
            headers=self._headers("forest"),
        )
        forest_cross_domain_list = client.get(
            "/api/lord-battles",
            headers=self._headers("forest"),
            params={"domain_id": "domain_north"},
        )
        master_list = client.get("/api/lord-battles", headers=MASTER_HEADERS)

        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(missing_list_auth.status_code, 401)
        self.assertEqual(north_list.status_code, 200)
        self.assertEqual(
            [item["battle_id"] for item in north_list.json()["items"]],
            ["battle_visibility_check"],
        )
        self.assertEqual(river_get.status_code, 200)
        self.assertEqual(river_get.json()["battle_id"], "battle_visibility_check")
        self.assertEqual(forest_get.status_code, 403)
        self.assertEqual(forest_get.json()["detail"], "Token cannot access this lord battle.")
        self.assertEqual(forest_cross_domain_list.status_code, 403)
        self.assertEqual(
            forest_cross_domain_list.json()["detail"],
            "Token cannot list this lord battle domain.",
        )
        self.assertEqual(master_list.status_code, 200)
        self.assertEqual(
            [item["battle_id"] for item in master_list.json()["items"]],
            ["battle_visibility_check"],
        )

    def test_lord_battle_rejects_illegal_turn_move_and_friendly_fire(self) -> None:
        settings = self._settings("lord_battle_illegal_actions")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_illegal_1", "domain_north", "unit_infantry_t1", 1, "node_res_river"),
                ("army_north_illegal_2", "domain_north", "unit_ranged_t1", 1, "node_res_river"),
                ("army_river_illegal", "domain_river", "unit_guard_t1", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        client = TestClient(create_app(settings))
        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_illegal_actions",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "illegal-actions",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        battle = created.json()
        active_side = battle["active_side"]
        inactive_side = "defender" if active_side == "attacker" else "attacker"
        active_lord = "north" if active_side == "attacker" else "river"
        inactive_lord = "river" if inactive_side == "defender" else "north"
        active_stack_id = battle["active_stack_id"]
        occupied = next(
            stack
            for stack in battle["board"]["stacks"]
            if stack["stack_id"] != active_stack_id and stack["count_alive"] > 0
        )

        inactive_defend = client.post(
            "/api/lord-battles/battle_illegal_actions/actions",
            headers=self._headers(inactive_lord),
            json={
                "action_id": "inactive-defend",
                "action_type": "defend",
                "actor_side": inactive_side,
            },
        )
        wrong_stack = client.post(
            "/api/lord-battles/battle_illegal_actions/actions",
            headers=self._headers(active_lord),
            json={
                "action_id": "wrong-stack",
                "action_type": "move",
                "actor_side": active_side,
                "payload": {"stack_id": "not-the-active-stack", "to": {"x": 1, "y": 2}},
            },
        )
        hero_cell = client.post(
            "/api/lord-battles/battle_illegal_actions/actions",
            headers=self._headers(active_lord),
            json={
                "action_id": "hero-cell",
                "action_type": "move",
                "actor_side": active_side,
                "payload": {"to": battle["board"]["hero_cells"][active_side]},
            },
        )
        occupied_cell = client.post(
            "/api/lord-battles/battle_illegal_actions/actions",
            headers=self._headers(active_lord),
            json={
                "action_id": "occupied-cell",
                "action_type": "move",
                "actor_side": active_side,
                "payload": {"to": {"x": occupied["x"], "y": occupied["y"]}},
            },
        )
        friendly_fire = client.post(
            "/api/lord-battles/battle_illegal_actions/actions",
            headers=self._headers(active_lord),
            json={
                "action_id": "friendly-fire",
                "action_type": "attack",
                "actor_side": active_side,
                "payload": {"target_stack_id": active_stack_id},
            },
        )

        self.assertEqual(inactive_defend.status_code, 400)
        self.assertEqual(inactive_defend.json()["detail"]["code"], "not_active_side")
        self.assertEqual(wrong_stack.status_code, 400)
        self.assertEqual(wrong_stack.json()["detail"]["code"], "not_active_stack")
        self.assertEqual(hero_cell.status_code, 400)
        self.assertEqual(hero_cell.json()["detail"]["code"], "move_to_hero_cell")
        self.assertEqual(occupied_cell.status_code, 400)
        self.assertEqual(occupied_cell.json()["detail"]["code"], "move_to_occupied_cell")
        self.assertEqual(friendly_fire.status_code, 400)
        self.assertEqual(friendly_fire.json()["detail"]["code"], "friendly_fire")

    def test_lord_battle_create_rejects_impossible_domain_and_army_states(self) -> None:
        settings = self._settings("lord_battle_create_rejects")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        same_domain = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_same_domain",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_north",
                "seed": "same-domain",
            },
        )

        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_north"},
            rows=[("army_north_wrong_place", "domain_north", "unit_infantry_t1", 1, "node_res_north")],
            clear_existing=True,
        )
        wrong_place = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_wrong_place",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "wrong-place",
            },
        )

        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute("DELETE FROM active_army_runtime WHERE domain_id = 'domain_north'")
        missing_attacker = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_missing_attacker",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "seed": "missing-attacker",
            },
        )

        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_north"},
            rows=[("army_north_missing_defender", "domain_north", "unit_infantry_t1", 1, "node_res_north")],
            clear_existing=True,
        )
        missing_defender = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_missing_defender",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "seed": "missing-defender",
            },
        )

        self.assertEqual(same_domain.status_code, 400)
        self.assertEqual(same_domain.json()["detail"]["code"], "same_domain")
        self.assertEqual(wrong_place.status_code, 400)
        self.assertEqual(wrong_place.json()["detail"]["code"], "attacker_not_at_territory")
        self.assertEqual(missing_attacker.status_code, 400)
        self.assertEqual(missing_attacker.json()["detail"]["code"], "missing_attacker_army")
        self.assertEqual(missing_defender.status_code, 400)
        self.assertEqual(missing_defender.json()["detail"]["code"], "missing_defender_army")

    def test_lord_battle_surrender_finishes_for_enemy_side_and_persists_result(self) -> None:
        settings = self._settings("lord_battle_surrender")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_surrender", "domain_north", "unit_infantry_t1", 1, "node_res_river"),
                ("army_river_surrender", "domain_river", "unit_guard_t1", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        client = TestClient(create_app(settings))
        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_surrender",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "surrender-seed",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        active_side = created.json()["active_side"]
        active_lord = "north" if active_side == "attacker" else "river"
        expected_winner = "defender" if active_side == "attacker" else "attacker"

        surrendered = client.post(
            "/api/lord-battles/battle_surrender/actions",
            headers=self._headers(active_lord),
            json={
                "action_id": "surrender-now",
                "action_type": "surrender",
                "actor_side": active_side,
            },
        )
        persisted = client.get("/api/lord-battles/battle_surrender", headers=MASTER_HEADERS)

        self.assertEqual(surrendered.status_code, 200, surrendered.text)
        self.assertEqual(surrendered.json()["status"], "finished")
        self.assertEqual(surrendered.json()["outcome"], "surrender")
        self.assertEqual(surrendered.json()["winner_side"], expected_winner)
        self.assertEqual(persisted.status_code, 200)
        self.assertEqual(persisted.json()["status"], "finished")
        self.assertEqual(persisted.json()["result"]["outcome"], "surrender")
        self.assertEqual(persisted.json()["result"]["winner_side"], expected_winner)

    def test_lord_battle_hero_attack_uses_range_los_and_rejects_own_hero(self) -> None:
        settings = self._settings("lord_battle_hero_attack")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_hero", "domain_north", "unit_ranged_t1", 1, "node_res_river"),
                ("army_river_hero", "domain_river", "unit_guard_t1", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        client = TestClient(create_app(settings))
        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_hero_attack",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "hero-attack-seed",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        active_side = created.json()["active_side"]
        active_lord = "north" if active_side == "attacker" else "river"
        enemy_side = "defender" if active_side == "attacker" else "attacker"

        own_hero = client.post(
            "/api/lord-battles/battle_hero_attack/actions",
            headers=self._headers(active_lord),
            json={
                "action_id": "own-hero",
                "action_type": "attack",
                "actor_side": active_side,
                "payload": {"target_type": "hero", "target_side": active_side},
            },
        )

        with connect(settings) as connection:
            row = connection.execute(
                """
                SELECT board_json, active_stack_id
                FROM lord_battles
                WHERE battle_id = 'battle_hero_attack'
                """
            ).fetchone()
            board = json.loads(row["board_json"])
            hero_cell = board["hero_cells"][enemy_side]
            for stack in board["stacks"]:
                if stack["stack_id"] == row["active_stack_id"]:
                    stack["x"] = hero_cell["x"]
                    stack["y"] = hero_cell["y"] - 1 if enemy_side == "defender" else hero_cell["y"] + 1
                    break
            connection.execute(
                """
                UPDATE lord_battles
                SET board_json = ?
                WHERE battle_id = 'battle_hero_attack'
                """,
                (json.dumps(board, ensure_ascii=False, sort_keys=True),),
            )

        hero_attack = client.post(
            "/api/lord-battles/battle_hero_attack/actions",
            headers=self._headers(active_lord),
            json={
                "action_id": "enemy-hero",
                "action_type": "attack",
                "actor_side": active_side,
                "payload": {"target_type": "hero", "target_side": enemy_side},
            },
        )

        self.assertEqual(own_hero.status_code, 400)
        self.assertEqual(own_hero.json()["detail"]["code"], "friendly_fire")
        self.assertEqual(hero_attack.status_code, 200, hero_attack.text)
        self.assertEqual(hero_attack.json()["status"], "hero_attacked")
        self.assertEqual(hero_attack.json()["target_side"], enemy_side)
        self.assertLess(
            hero_attack.json()["hero_hp"],
            created.json()["hero_hp"][enemy_side]["current"],
        )

    def test_lord_battle_rejects_missing_attack_target_and_corrupted_active_stack_state(self) -> None:
        settings = self._settings("lord_battle_state_corruption")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_corruption", "domain_north", "unit_infantry_t1", 1, "node_res_river"),
                ("army_river_corruption", "domain_river", "unit_guard_t1", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        client = TestClient(create_app(settings))
        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_state_corruption",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "state-corruption",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        active_side = created.json()["active_side"]
        active_lord = "north" if active_side == "attacker" else "river"

        missing_target = client.post(
            "/api/lord-battles/battle_state_corruption/actions",
            headers=self._headers(active_lord),
            json={
                "action_id": "missing-target",
                "action_type": "attack",
                "actor_side": active_side,
                "payload": {},
            },
        )
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE lord_battles
                SET active_stack_id = NULL
                WHERE battle_id = 'battle_state_corruption'
                """
            )
        no_active_stack = client.post(
            "/api/lord-battles/battle_state_corruption/actions",
            headers=self._headers(active_lord),
            json={
                "action_id": "no-active-stack",
                "action_type": "defend",
                "actor_side": active_side,
            },
        )
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE lord_battles
                SET active_stack_id = 'missing-stack'
                WHERE battle_id = 'battle_state_corruption'
                """
            )
        stack_not_found = client.post(
            "/api/lord-battles/battle_state_corruption/actions",
            headers=self._headers(active_lord),
            json={
                "action_id": "stack-not-found",
                "action_type": "defend",
                "actor_side": active_side,
            },
        )

        self.assertEqual(missing_target.status_code, 400)
        self.assertEqual(missing_target.json()["detail"]["code"], "missing_target")
        self.assertEqual(no_active_stack.status_code, 400)
        self.assertEqual(no_active_stack.json()["detail"]["code"], "no_active_stack")
        self.assertEqual(stack_not_found.status_code, 404)
        self.assertEqual(stack_not_found.json()["detail"]["code"], "stack_not_found")

    def test_lord_battle_auto_resolve_tie_uses_deterministic_seed_winner(self) -> None:
        settings = self._settings("lord_battle_auto_resolve_tie")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_tie", "domain_north", "unit_infantry_t1", 1, "node_res_river"),
                ("army_river_tie", "domain_river", "unit_infantry_t1", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        client = TestClient(create_app(settings))
        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_auto_tie",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "seed": "equal-power-seed",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(
            self._battle_score(created.json(), "attacker"),
            self._battle_score(created.json(), "defender"),
        )

        resolved = client.post(
            "/api/lord-battles/battle_auto_tie/actions",
            headers=self._headers("north"),
            json={
                "action_id": "manual-auto-tie",
                "action_type": "auto_resolve",
                "actor_side": "attacker",
            },
        )
        payload = resolved.json()
        result = payload["battle"]["result"]

        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(payload["status"], "finished")
        self.assertEqual(payload["outcome"], "auto_resolve")
        self.assertEqual(payload["reason"], "manual_auto_resolve")
        self.assertIn(payload["winner_side"], {"attacker", "defender"})
        self.assertEqual(result["winner_side"], payload["winner_side"])
        self.assertEqual(result["outcome"], "auto_resolve")
        self.assertIsNone(result["capture"])

    def test_lord_battle_surrender_records_no_retreat_node_when_domain_has_no_safe_node(self) -> None:
        settings = self._settings("lord_battle_no_retreat_node")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_no_retreat", "domain_north", "unit_infantry_t1", 1, "node_res_river"),
                ("army_river_no_retreat", "domain_river", "unit_guard_t1", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        client = TestClient(create_app(settings))
        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_no_retreat_node",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "seed": "no-retreat-seed",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        losing_side = created.json()["active_side"]
        losing_lord = "north" if losing_side == "attacker" else "river"
        losing_domain = "domain_north" if losing_side == "attacker" else "domain_river"

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE territories
                SET owner_domain_id = ''
                WHERE owner_domain_id = ?
                """,
                (losing_domain,),
            )
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = NULL
                WHERE owner_domain_id = ?
                """,
                (losing_domain,),
            )

        surrendered = client.post(
            "/api/lord-battles/battle_no_retreat_node/actions",
            headers=self._headers(losing_lord),
            json={
                "action_id": "surrender-without-safe-node",
                "action_type": "surrender",
                "actor_side": losing_side,
            },
        )
        result = surrendered.json()["battle"]["result"]

        self.assertEqual(surrendered.status_code, 200, surrendered.text)
        self.assertEqual(result["outcome"], "surrender")
        self.assertEqual(result["loser_domain_id"], losing_domain)
        self.assertEqual(
            result["retreat"],
            {"domain_id": losing_domain, "status": "no_retreat_node"},
        )

    def test_neutral_ai_moves_toward_target_when_attack_is_not_available(self) -> None:
        settings = self._settings("lord_battle_ai_move")
        self._import_seed(settings)
        self._set_reserve_count(settings, "reserve_north_infantry", 4)
        client = TestClient(create_app(settings))

        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(active.status_code, 200)
        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={"to_node_id": "node_field_oats"},
        )
        self.assertEqual(moved.status_code, 200)
        self._complete_pending_moves(settings)
        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_ai_move",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_field_oats",
                "seed": "ai-move-seed",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)

        with connect(settings) as connection:
            row = connection.execute(
                """
                SELECT board_json
                FROM lord_battles
                WHERE battle_id = 'battle_ai_move'
                """
            ).fetchone()
            board = json.loads(row["board_json"])
            attacker = next(stack for stack in board["stacks"] if stack["side"] == "attacker")
            defender = next(stack for stack in board["stacks"] if stack["side"] == "defender")
            attacker["x"], attacker["y"] = 0, 0
            defender["x"], defender["y"] = 4, 5
            connection.execute(
                """
                UPDATE lord_battles
                SET active_side = 'defender',
                    active_stack_id = ?,
                    board_json = ?
                WHERE battle_id = 'battle_ai_move'
                """,
                (
                    defender["stack_id"],
                    json.dumps(board, ensure_ascii=False, sort_keys=True),
                ),
            )

        ai_turn = client.post(
            "/api/lord-battles/battle_ai_move/actions",
            headers=MASTER_HEADERS,
            json={
                "action_id": "ai-move-toward-target",
                "action_type": "ai_turn",
                "actor_side": "defender",
            },
        )
        battle = ai_turn.json()["battle"]
        moved_stack = next(stack for stack in battle["board"]["stacks"] if stack["side"] == "defender")

        self.assertEqual(ai_turn.status_code, 200, ai_turn.text)
        self.assertEqual(ai_turn.json()["status"], "ai_moved")
        self.assertLess(abs(moved_stack["x"] - 0) + abs(moved_stack["y"] - 0), 9)

    def test_pending_tick_rewards_settle_on_defender_and_neutral_victory(self) -> None:
        settings = self._settings("lord_battle_pending_defender")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_pending_loss", "domain_north", "unit_infantry_t1", 1, "node_res_river"),
                ("army_river_pending_win", "domain_river", "unit_heavy_siege_t3", 5, "node_res_river"),
            ],
            clear_existing=True,
        )
        with connect(settings) as connection:
            connection.execute(
                """
                INSERT INTO pending_tick_reward_runtime (
                    pending_reward_id, domain_id, territory_id, reward_gold, status, due_at
                )
                VALUES (
                    'pending_river_defense',
                    'domain_river',
                    'territory_res_river',
                    14,
                    'pending',
                    '2026-06-02T11:00:00+00:00'
                )
                """
            )
        client = TestClient(create_app(settings))
        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_pending_defender",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "pending-defender-win",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        resolved = client.post(
            "/api/lord-battles/battle_pending_defender/actions",
            headers=self._headers("north"),
            json={
                "action_id": "auto-defender-win",
                "action_type": "auto_resolve",
                "actor_side": "attacker",
            },
        )
        capture = resolved.json()["battle"]["result"]["capture"]

        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()["battle"]["result"]["winner_side"], "defender")
        self.assertEqual(capture["status"], "defense_held")
        self.assertEqual(capture["pending_tick_awards"][0]["status"], "awarded")
        self.assertEqual(capture["pending_tick_awards"][0]["awarded_to_domain_id"], "domain_river")
        with connect(settings) as connection:
            pending = connection.execute(
                """
                SELECT status, awarded_to_domain_id
                FROM pending_tick_reward_runtime
                WHERE pending_reward_id = 'pending_river_defense'
                """
            ).fetchone()
            river_gold = connection.execute(
                "SELECT gold FROM domain_runtime_state WHERE domain_id = 'domain_river'"
            ).fetchone()["gold"]
        self.assertEqual(dict(pending), {"status": "awarded", "awarded_to_domain_id": "domain_river"})
        self.assertEqual(river_gold, 94)

        neutral_settings = self._settings("lord_battle_pending_neutral")
        self._import_seed(neutral_settings)
        self._set_active_armies(
            neutral_settings,
            current_nodes={"domain_north": "node_field_oats"},
            rows=[
                ("army_north_neutral_loss", "domain_north", "unit_infantry_t1", 1, "node_field_oats"),
            ],
            clear_existing=True,
        )
        with connect(neutral_settings) as connection:
            connection.execute(
                """
                INSERT INTO pending_tick_reward_runtime (
                    pending_reward_id, domain_id, territory_id, reward_gold, status, due_at
                )
                VALUES (
                    'pending_neutral_defense',
                    NULL,
                    'territory_field_oats',
                    8,
                    'pending',
                    '2026-06-02T11:00:00+00:00'
                )
                """
            )
        neutral_client = TestClient(create_app(neutral_settings))
        neutral_created = neutral_client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_pending_neutral",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_field_oats",
                "seed": "pending-neutral-defense",
            },
        )
        self.assertEqual(neutral_created.status_code, 200, neutral_created.text)
        neutral_resolved = neutral_client.post(
            "/api/lord-battles/battle_pending_neutral/actions",
            headers=self._headers("north"),
            json={
                "action_id": "auto-neutral-win",
                "action_type": "auto_resolve",
                "actor_side": "attacker",
            },
        )
        neutral_capture = neutral_resolved.json()["battle"]["result"]["capture"]

        self.assertEqual(neutral_resolved.status_code, 200, neutral_resolved.text)
        self.assertEqual(neutral_resolved.json()["battle"]["result"]["winner_side"], "defender")
        self.assertEqual(neutral_capture["pending_tick_awards"][0]["status"], "voided")
        with connect(neutral_settings) as connection:
            neutral_pending = connection.execute(
                """
                SELECT status, awarded_to_domain_id
                FROM pending_tick_reward_runtime
                WHERE pending_reward_id = 'pending_neutral_defense'
                """
            ).fetchone()
        self.assertEqual(dict(neutral_pending), {"status": "voided", "awarded_to_domain_id": None})

    def test_expired_turn_timer_is_applied_before_ordinary_action(self) -> None:
        settings = self._settings("lord_battle_proactive_timeout")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_timeout_guard", "domain_north", "unit_infantry_t1", 1, "node_res_river"),
                ("army_river_timeout_guard", "domain_river", "unit_guard_t1", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        client = TestClient(create_app(settings))
        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_proactive_timeout",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "proactive-timeout",
            },
        )
        self.assertEqual(created.status_code, 200, created.text)
        active_side = created.json()["active_side"]
        active_lord = "north" if active_side == "attacker" else "river"
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE lord_battles
                SET timeout_at = ?
                WHERE battle_id = 'battle_proactive_timeout'
                """,
                (datetime(2026, 6, 2, 10, 0, tzinfo=UTC).isoformat(timespec="seconds"),),
            )

        action = client.post(
            "/api/lord-battles/battle_proactive_timeout/actions",
            headers=self._headers(active_lord),
            json={
                "action_id": "attack-after-expired-timeout",
                "action_type": "attack",
                "actor_side": active_side,
                "payload": {},
            },
        )

        self.assertEqual(action.status_code, 200, action.text)
        self.assertTrue(action.json()["timed_out_before_action"])
        self.assertEqual(action.json()["requested_action_type"], "attack")
        self.assertEqual(action.json()["battle"]["timeout_counts"][active_side], 1)
        self.assertIn(
            "lord_battle_turn_timeout",
            [entry["entry_type"] for entry in action.json()["battle"]["battle_log"]],
        )

    def test_lord_battle_hp_uses_v0_deployed_army_power_formula(self) -> None:
        cases = [
            ("hp_low", "unit_infantry_t1", 1, 10, 35),
            ("hp_mid", "unit_infantry_t1", 10, 100, 40),
            ("hp_high", "unit_heavy_siege_t3", 25, 500, 70),
        ]
        for name, card_id, count, expected_power, expected_hp in cases:
            with self.subTest(name=name):
                settings = self._settings(f"lord_battle_{name}")
                self._import_seed(settings)
                self._set_active_armies(
                    settings,
                    current_nodes={
                        "domain_north": "node_res_river",
                        "domain_river": "node_res_river",
                    },
                    rows=[
                        (f"army_north_{name}", "domain_north", card_id, count, "node_res_river"),
                    ],
                    clear_existing=True,
                )
                client = TestClient(create_app(settings))
                created = client.post(
                    "/api/lord-battles",
                    headers=self._headers("north"),
                    json={
                        "battle_id": f"battle_{name}",
                        "attacker_domain_id": "domain_north",
                        "defender_domain_id": "domain_river",
                        "territory_id": "territory_res_river",
                        "seed": name,
                    },
                )
                self.assertEqual(created.status_code, 200, created.text)
                hero_hp = created.json()["hero_hp"]

                self.assertEqual(hero_hp["attacker"]["deployed_army_power"], expected_power)
                self.assertEqual(hero_hp["attacker"]["max"], expected_hp)
                self.assertEqual(hero_hp["attacker"]["current"], expected_hp)
                self.assertEqual(hero_hp["formula_inputs"]["base"], 30)
                self.assertEqual(hero_hp["formula_inputs"]["power_divisor"], 10)
                self.assertEqual(hero_hp["formula_inputs"]["min"], 35)
                self.assertEqual(hero_hp["formula_inputs"]["max"], 70)

    def test_lord_battle_rejects_invalid_runtime_unit_stats(self) -> None:
        settings = self._settings("lord_battle_bad_unit_stats")
        self._import_seed(settings)
        self._set_active_armies(
            settings,
            current_nodes={"domain_north": "node_res_river", "domain_river": "node_res_river"},
            rows=[
                ("army_north_bad_hp", "domain_north", "unit_infantry_t1", 1, "node_res_river"),
                ("army_river_guard", "domain_river", "unit_guard_t1", 1, "node_res_river"),
            ],
            clear_existing=True,
        )
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE army_unit_cards
                SET hp = 0
                WHERE card_id = 'unit_infantry_t1'
                """
            )
        client = TestClient(create_app(settings))

        created = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_bad_runtime_unit_stats",
                "attacker_domain_id": "domain_north",
                "defender_domain_id": "domain_river",
                "territory_id": "territory_res_river",
                "seed": "bad-runtime-unit-stats",
            },
        )

        self.assertEqual(created.status_code, 400)
        self.assertEqual(created.json()["detail"]["code"], "invalid_unit_stat")

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def _import_seed(self, settings: Settings) -> None:
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")

    def _set_reserve_count(self, settings: Settings, reserve_id: str, count: int) -> None:
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                "UPDATE army_reserve_runtime SET count = ? WHERE reserve_id = ?",
                (count, reserve_id),
            )

    def _set_active_armies(
        self,
        settings: Settings,
        *,
        current_nodes: dict[str, str],
        rows: list[tuple[str, str, str, int, str]],
        clear_existing: bool = False,
    ) -> None:
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            if clear_existing:
                connection.execute("DELETE FROM active_army_runtime")
            for domain_id, node_id in current_nodes.items():
                connection.execute(
                    """
                    UPDATE domain_runtime_state
                    SET current_node_id = ?, updated_at = '2026-06-02T10:00:00+00:00'
                    WHERE domain_id = ?
                    """,
                    (node_id, domain_id),
                )
            for army_id, domain_id, card_id, count, node_id in rows:
                connection.execute(
                    """
                    INSERT INTO active_army_runtime (
                        army_id, domain_id, card_id, count, location_node_id, status, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 'active', '2026-06-02T10:00:00+00:00')
                    ON CONFLICT(army_id) DO UPDATE SET
                        card_id = excluded.card_id,
                        count = excluded.count,
                        location_node_id = excluded.location_node_id,
                        status = 'active',
                        updated_at = excluded.updated_at
                    """,
                    (army_id, domain_id, card_id, count, node_id),
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
    def _battle_score(battle: dict[str, object], side: str) -> int:
        board = battle["board"]
        assert isinstance(board, dict)
        hero_hp = battle["hero_hp"]
        assert isinstance(hero_hp, dict)
        stacks = board["stacks"]
        assert isinstance(stacks, list)
        stack_score = 0
        for stack in stacks:
            assert isinstance(stack, dict)
            if stack["side"] != side or int(stack["count_alive"]) <= 0:
                continue
            stack_score += (
                int(stack["attack"])
                + int(stack["defense"])
                + int(stack["hp"])
                + int(stack["tier"])
            ) * int(stack["count_alive"])
        side_hp = hero_hp[side]
        assert isinstance(side_hp, dict)
        return stack_score + int(side_hp["current"])


if __name__ == "__main__":
    unittest.main()
