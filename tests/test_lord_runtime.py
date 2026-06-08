from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.lord_runtime import anti_snowball_cut_for_domain
from backend.witcher_larp.lord_runtime import ensure_lord_runtime_state
from backend.witcher_larp.lord_runtime import reconcile_pending_lord_moves
from backend.witcher_larp.timer_service import apply_due_timers

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"
TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"


@unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
class LordRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_movement_contested_capture_pending_tick_and_hidden_garrisons(self) -> None:
        settings = self._settings("lord_move")
        self._import_seed(settings)
        started_at = datetime.now(UTC)
        with connect(settings) as connection:
            start_act(
                connection,
                settings,
                "act1",
                operator="gm_lord",
                physical_announcement_state="announced",
                now=started_at,
            )
            ensure_lord_runtime_state(connection)
            connection.execute(
                "UPDATE army_reserve_runtime SET count = 5 WHERE reserve_id = 'reserve_north_infantry'"
            )
        client = TestClient(create_app(settings))

        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 4,
            },
        )
        self.assertEqual(active.status_code, 200)

        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={"to_node_id": "node_fort_east"},
        )
        self.assertEqual(moved.status_code, 200)
        move_payload = moved.json()
        self.assertEqual(move_payload["status"], "pending_move")
        self.assertEqual(move_payload["mp_spent"], 2)
        self.assertEqual(move_payload["current_mp"], 4)
        self.assertEqual(move_payload["battle_spent_mp"], 0)
        self.assertIsNone(move_payload["claim"])
        completed = self._complete_pending_moves(settings)
        self.assertEqual(completed[0]["claim"]["status"], "in_battle")
        self.assertTrue(completed[0]["claim"]["visible_to_lords"])

        with connect(settings) as connection:
            ticks = apply_due_timers(connection, settings, now=started_at + timedelta(minutes=31))
        self.assertEqual(ticks[0]["pending_tick_rewards"][0]["territory_id"], "territory_fort_east")

        shortcut = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "territory_id": "territory_fort_east",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(shortcut.status_code, 400)
        self.assertEqual(shortcut.json()["detail"]["code"], "capture_not_resolved")

        battle = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_fort_east_capture",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_fort_east",
                "seed": "north-fort-easy-win",
            },
        )
        self.assertEqual(battle.status_code, 200, battle.text)
        resolved = client.post(
            "/api/lord-battles/battle_fort_east_capture/actions",
            headers=self._headers("north"),
            json={
                "action_id": "resolve-fort-east",
                "action_type": "auto_resolve",
                "actor_side": "attacker",
            },
        )
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()["battle"]["result"]["winner_side"], "attacker")
        self.assertEqual(
            resolved.json()["battle"]["result"]["capture"]["status"],
            "capture_pending_garrison",
        )
        with connect(settings) as connection:
            active_before_capture = connection.execute(
                """
                SELECT count
                FROM active_army_runtime
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                  AND status = 'active'
                """
            ).fetchone()["count"]
            reserve_before_capture = connection.execute(
                """
                SELECT count
                FROM army_reserve_runtime
                WHERE reserve_id = 'reserve_north_infantry'
                """
            ).fetchone()["count"]
        self.assertGreaterEqual(active_before_capture, 1)

        captured = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "territory_id": "territory_fort_east",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(captured.status_code, 200)
        capture_payload = captured.json()
        self.assertEqual(capture_payload["status"], "captured")
        self.assertEqual(capture_payload["pending_tick_awards"][0]["reward_gold"], 14)
        with connect(settings) as connection:
            active_after_capture = connection.execute(
                """
                SELECT count
                FROM active_army_runtime
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                  AND status = 'active'
                """
            ).fetchone()["count"]
            reserve_after_capture = connection.execute(
                """
                SELECT count
                FROM army_reserve_runtime
                WHERE reserve_id = 'reserve_north_infantry'
                """
            ).fetchone()["count"]
        self.assertEqual(active_after_capture, active_before_capture - 1)
        self.assertEqual(reserve_after_capture, reserve_before_capture)

        restarted_client = TestClient(create_app(settings))
        north_state = restarted_client.get(
            "/api/lords/p_lord_1/state",
            headers=self._headers("north"),
        )
        river_state = restarted_client.get(
            "/api/lords/p_lord_2/state",
            headers=self._headers("river"),
        )

        self.assertEqual(north_state.status_code, 200)
        fort = self._territory(north_state.json()["territories"], "territory_fort_east")
        self.assertEqual(fort["owner_domain_id"], "domain_north")
        self.assertEqual(fort["status"], "controlled")
        self.assertEqual(fort["garrisons"][0]["card_id"], "unit_infantry_t1")

        self.assertEqual(river_state.status_code, 200)
        river_fort_view = self._territory(
            river_state.json()["other_territories"], "territory_fort_east"
        )
        self.assertEqual(river_fort_view["owner_domain_id"], "domain_north")
        self.assertEqual(river_fort_view["bonus_type"], "defense")
        self.assertEqual(river_fort_view["garrisons"][0]["status"], "hidden_foreign_garrison")

    def test_building_prerequisites_cross_deps_recruit_hold_and_reserve_spawn(self) -> None:
        settings = self._settings("lord_buildings")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        missing = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_barracks"},
        )
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(missing.json()["detail"]["code"], "missing_prerequisites")

        training = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_training_yard"},
        )
        self.assertEqual(training.status_code, 200)
        self.assertEqual(training.json()["gold_spent"], 40)
        self.assertIn(
            "unit_guard_t1",
            {offer["card_id"] for offer in training.json()["unlocked_recruit_offers"]},
        )

        market = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_market"},
        )
        self.assertEqual(market.status_code, 200)

        with connect(settings) as connection:
            connection.execute(
                "UPDATE domain_runtime_state SET gold = 1000 WHERE domain_id = 'domain_north'"
            )

        barracks = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_barracks"},
        )
        self.assertEqual(barracks.status_code, 200)
        blocked_siege = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_siege_yard"},
        )
        self.assertEqual(blocked_siege.status_code, 400)
        self.assertIn("b_archery_range", blocked_siege.json()["detail"]["message"])

        archery = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_archery_range"},
        )
        self.assertEqual(archery.status_code, 200)
        siege = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_siege_yard"},
        )
        self.assertEqual(siege.status_code, 200)
        self.assertIn(
            "unit_heavy_siege_t3",
            {offer["card_id"] for offer in siege.json()["unlocked_recruit_offers"]},
        )

        refresh = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "refresh"},
        )
        self.assertEqual(refresh.status_code, 200)
        heavy_offer = next(
            offer
            for offer in refresh.json()["offers"]
            if offer["card_id"] == "unit_heavy_siege_t3"
        )
        held = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "hold", "offer_id": heavy_offer["offer_id"]},
        )
        self.assertEqual(held.status_code, 200)
        purchased = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "purchase", "offer_id": heavy_offer["offer_id"]},
        )
        self.assertEqual(purchased.status_code, 200)
        self.assertEqual(purchased.json()["reserve"]["card_id"], "unit_heavy_siege_t3")
        after_purchase_refresh = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "refresh"},
        )
        self.assertEqual(after_purchase_refresh.status_code, 200)
        replacement_heavy = next(
            offer
            for offer in after_purchase_refresh.json()["offers"]
            if offer["card_id"] == "unit_heavy_siege_t3" and offer["status"] == "available"
        )
        self.assertNotEqual(replacement_heavy["offer_id"], heavy_offer["offer_id"])

        guard_offer = next(
            offer
            for offer in after_purchase_refresh.json()["offers"]
            if offer["card_id"] == "unit_guard_t1"
        )
        held_guard = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "hold", "offer_id": guard_offer["offer_id"]},
        )
        held_refresh = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "refresh"},
        )
        self.assertEqual(held_guard.status_code, 200)
        self.assertIn(
            guard_offer["offer_id"],
            {
                offer["offer_id"]
                for offer in held_refresh.json()["offers"]
                if offer["card_id"] == "unit_guard_t1" and offer["status"] == "held"
            },
        )

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
        self.assertEqual(active.status_code, 200, active.text)
        moved_away = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={"to_node_id": "node_fort_east"},
        )
        self.assertEqual(moved_away.status_code, 200)
        self._complete_pending_moves(settings)
        blocked_active_army = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_heavy_siege_t3",
                "count": 1,
            },
        )
        self.assertEqual(blocked_active_army.status_code, 400)
        self.assertEqual(blocked_active_army.json()["detail"]["code"], "not_at_residence")

        with connect(settings) as connection:
            reserve_count = connection.execute(
                """
                SELECT count
                FROM army_reserve_runtime
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_heavy_siege_t3'
                """
            ).fetchone()["count"]
        self.assertEqual(reserve_count, 1)

    def test_movement_without_active_army_cannot_create_contested_claim(self) -> None:
        settings = self._settings("lord_move_requires_active")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={"to_node_id": "node_fort_east"},
        )
        self.assertEqual(moved.status_code, 400, moved.text)
        self.assertEqual(moved.json()["detail"]["code"], "missing_active_army")

        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            domain = connection.execute(
                """
                SELECT current_node_id, current_mp
                FROM domain_runtime_state
                WHERE domain_id = 'domain_north'
                """
            ).fetchone()
            fort = connection.execute(
                """
                SELECT owner_domain_id, status, contested_by_domain_id
                FROM territory_runtime_state
                WHERE territory_id = 'territory_fort_east'
                """
            ).fetchone()
            claims = connection.execute(
                """
                SELECT COUNT(*)
                FROM territory_claim_runtime
                WHERE territory_id = 'territory_fort_east'
                  AND claimant_domain_id = 'domain_north'
                """
            ).fetchone()[0]

        self.assertEqual(domain["current_node_id"], "node_res_north")
        self.assertEqual(domain["current_mp"], 6)
        self.assertIsNone(fort["owner_domain_id"])
        self.assertEqual(fort["status"], "neutral")
        self.assertIsNone(fort["contested_by_domain_id"])
        self.assertEqual(claims, 0)

    def test_movement_rejects_foreign_residence_and_stops_at_blocking_territory(self) -> None:
        settings = self._settings("lord_map_route_guards")
        self._import_seed(settings)
        self._set_reserve_count(settings, "reserve_north_infantry", 4)
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
        self.assertEqual(active.status_code, 200, active.text)

        residence_preview = client.post(
            "/api/lords/p_lord_1/route-preview",
            headers=self._headers("north"),
            json={"to_node_id": "node_res_river"},
        )
        self.assertEqual(residence_preview.status_code, 400)
        self.assertEqual(
            residence_preview.json()["detail"]["code"],
            "forbidden_residence_target",
        )

        preview = client.post(
            "/api/lords/p_lord_1/route-preview",
            headers=self._headers("north"),
            json={
                "to_node_id": "node_mountain_north_alpine",
                "route_node_ids": [
                    "node_res_north",
                    "node_fort_east",
                    "node_mountain_north_alpine",
                ],
            },
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        preview_payload = preview.json()
        self.assertEqual(preview_payload["status"], "stopped")
        self.assertTrue(preview_payload["can_move"])
        self.assertEqual(preview_payload["reason_code"], "route_stopped_at_front")
        self.assertEqual(preview_payload["requested_to_node_id"], "node_mountain_north_alpine")
        self.assertEqual(preview_payload["to_node_id"], "node_fort_east")
        self.assertEqual(preview_payload["route"], ["node_res_north", "node_fort_east"])
        self.assertEqual(preview_payload["mp_cost"], 2)
        self.assertEqual(preview_payload["outcome"]["kind"], "will_create_claim")
        with connect(settings) as connection:
            self.assertEqual(
                connection.execute(
                    """
                    SELECT current_mp
                    FROM domain_runtime_state
                    WHERE domain_id = 'domain_north'
                    """
                ).fetchone()["current_mp"],
                6,
            )

        residence_attack = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={
                "to_node_id": "node_res_river",
                "route_node_ids": [
                    "node_res_north",
                    "node_fort_east",
                    "node_well_city",
                    "node_res_river",
                ],
            },
        )
        self.assertEqual(residence_attack.status_code, 400)
        self.assertEqual(
            residence_attack.json()["detail"]["code"],
            "forbidden_residence_target",
        )

        stopped = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={
                "to_node_id": "node_mountain_north_alpine",
                "route_node_ids": [
                    "node_res_north",
                    "node_fort_east",
                    "node_mountain_north_alpine",
                ],
            },
        )
        self.assertEqual(stopped.status_code, 200, stopped.text)
        payload = stopped.json()
        self.assertEqual(payload["status"], "pending_move")
        self.assertEqual(payload["requested_to_node_id"], "node_mountain_north_alpine")
        self.assertEqual(payload["to_node_id"], "node_fort_east")
        self.assertEqual(payload["route"], ["node_res_north", "node_fort_east"])
        self.assertEqual(payload["mp_spent"], 2)
        pending_preview = client.post(
            "/api/lords/p_lord_1/route-preview",
            headers=self._headers("north"),
            json={"to_node_id": "node_mountain_north_alpine"},
        )
        self.assertEqual(pending_preview.status_code, 200, pending_preview.text)
        self.assertEqual(pending_preview.json()["status"], "blocked")
        self.assertEqual(pending_preview.json()["reason_code"], "pending_move_active")
        completed = self._complete_pending_moves(settings)
        self.assertEqual(completed[0]["claim"]["territory_id"], "territory_fort_east")

    def test_local_active_army_fort_transfers_reject_remote_reserve_and_contested_state(self) -> None:
        settings = self._settings("lord_local_fort_transfers")
        self._import_seed(settings)
        client = TestClient(create_app(settings))
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

        remote_reinforce = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "active_to_fort",
                "territory_id": "territory_fort_east",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(remote_reinforce.status_code, 400, remote_reinforce.text)
        self.assertEqual(remote_reinforce.json()["detail"]["code"], "army_not_at_territory")
        with connect(settings) as connection:
            reserve_count = connection.execute(
                "SELECT count FROM army_reserve_runtime WHERE reserve_id = 'reserve_north_infantry'"
            ).fetchone()["count"]
            remote_garrison = connection.execute(
                """
                SELECT COUNT(*)
                FROM garrison_runtime_state
                WHERE territory_id = 'territory_fort_east'
                  AND domain_id = 'domain_north'
                """
            ).fetchone()[0]
        self.assertEqual(reserve_count, 3)
        self.assertEqual(remote_garrison, 0)

        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 2,
            },
        )
        self.assertEqual(active.status_code, 200, active.text)
        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={"to_node_id": "node_fort_east"},
        )
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertIsNone(moved.json()["claim"])
        self.assertEqual(moved.json()["status"], "pending_move")
        completed = self._complete_pending_moves(settings)
        self.assertIsNone(completed[0]["claim"])

        placed = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "active_to_fort",
                "territory_id": "territory_fort_east",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(placed.status_code, 200, placed.text)
        self.assertEqual(placed.json()["status"], "reinforced")

        pulled = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "fort_to_active",
                "territory_id": "territory_fort_east",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(pulled.status_code, 200, pulled.text)
        self.assertEqual(pulled.json()["status"], "active_army_updated")
        with connect(settings) as connection:
            active_count = connection.execute(
                """
                SELECT count
                FROM active_army_runtime
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                """
            ).fetchone()["count"]
            garrison_count = connection.execute(
                """
                SELECT count
                FROM garrison_runtime_state
                WHERE territory_id = 'territory_fort_east'
                  AND domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                """
            ).fetchone()["count"]
        self.assertEqual(active_count, 2)
        self.assertEqual(garrison_count, 0)

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET status = 'in_battle',
                    contested_by_domain_id = 'domain_river'
                WHERE territory_id = 'territory_fort_east'
                """
            )
        contested = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "active_to_fort",
                "territory_id": "territory_fort_east",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(contested.status_code, 400, contested.text)
        self.assertEqual(contested.json()["detail"]["code"], "territory_contested")

    def test_raid_engine_and_anti_snowball_report(self) -> None:
        settings = self._settings("lord_raid")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        raid = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={"target_territory_id": "territory_res_river"},
        )
        self.assertEqual(raid.status_code, 200)
        payload = raid.json()
        self.assertEqual(payload["status"], "active")
        self.assertEqual(payload["token_spent"], 1)
        self.assertEqual(payload["gold_spent"], 15)
        self.assertGreaterEqual(payload["resistance"], 1)
        self.assertIsNotNone(payload["expires_at"])

        expired_at = datetime.now(UTC) - timedelta(minutes=1)
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE raid_effects
                SET expires_at = ?
                WHERE raid_effect_id = ?
                """,
                (expired_at.isoformat(timespec="seconds"), payload["raid_effect_id"]),
            )
        expired_state = client.get(
            "/api/lords/p_lord_1/state",
            headers=self._headers("north"),
        )
        self.assertEqual(expired_state.status_code, 200)
        expired_raid = next(
            raid
            for raid in expired_state.json()["raid_effects"]
            if raid["raid_effect_id"] == payload["raid_effect_id"]
        )
        self.assertEqual(expired_raid["status"], "expired")
        self.assertEqual(expired_state.json()["summary"]["active_raids"], 0)

        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                INSERT INTO army_reserve_runtime (
                    reserve_id, domain_id, card_id, count, status, updated_at
                )
                VALUES (
                    'reserve_north_balance_spike',
                    'domain_north',
                    'unit_heavy_siege_t3',
                    20,
                    'available',
                    '2026-06-02T10:00:00+00:00'
                )
                """
            )
            report = anti_snowball_cut_for_domain(connection, "domain_north")

        self.assertGreaterEqual(report["army_power_ratio"], 170)
        self.assertEqual(report["income_cut_percent"], 50)

    def test_order_caps_object_conflict_success_race_and_escrow_release(self) -> None:
        settings = self._settings("lord_orders")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        north_over_cap = client.post(
            "/api/lords/p_lord_1/orders",
            headers=self._headers("north"),
            json={
                "action": "create",
                "object_id": "territory_fort_east",
                "visibility": "public",
                "target_player_id": "p_witcher_4",
                "escrow_reward_id": "reward_order_success",
            },
        )
        self.assertEqual(north_over_cap.status_code, 400)
        self.assertEqual(north_over_cap.json()["detail"]["code"], "order_cap_exceeded")

        first = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={
                "action": "create",
                "object_id": "territory_well_city",
                "visibility": "public",
                "target_player_id": "p_witcher_2",
                "escrow_reward_id": "reward_order_success",
            },
        )
        second = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={
                "action": "create",
                "object_id": "territory_well_city",
                "visibility": "public",
                "target_player_id": "p_witcher_3",
                "escrow_reward_id": "reward_order_success",
            },
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_id = first.json()["order"]["order_id"]
        second_id = second.json()["order"]["order_id"]

        with connect(settings) as connection:
            forest_gold_after_reserve = connection.execute(
                "SELECT gold FROM domain_runtime_state WHERE domain_id = 'domain_forest'"
            ).fetchone()["gold"]
            first_escrow = connection.execute(
                "SELECT reserved_gold, reserved_xp, reserved_assets_json FROM escrow_ledger WHERE order_id = ?",
                (first_id,),
            ).fetchone()
        self.assertEqual(forest_gold_after_reserve, 50)
        self.assertEqual(first_escrow["reserved_gold"], 15)
        self.assertEqual(first_escrow["reserved_xp"], 6)
        self.assertIn("item_order_seal", first_escrow["reserved_assets_json"])

        lord_impersonation_accept = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={"action": "accept", "order_id": first_id, "player_id": "p_witcher_2"},
        )
        self.assertEqual(lord_impersonation_accept.status_code, 403)

        accepted = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._player_headers("p_witcher_2"),
            json={"action": "accept", "order_id": first_id},
        )
        self.assertEqual(accepted.status_code, 200)

        conflict = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._player_headers("p_witcher_2"),
            json={"action": "accept", "order_id": second_id},
        )
        self.assertEqual(conflict.status_code, 400)
        self.assertEqual(conflict.json()["detail"]["code"], "order_object_conflict")

        wrong_player = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._player_headers("p_witcher_3"),
            json={"action": "submit_success", "order_id": first_id, "result_event_id": "evt_wrong_actor"},
        )
        self.assertEqual(wrong_player.status_code, 400)
        self.assertEqual(wrong_player.json()["detail"]["code"], "order_actor_mismatch")

        lord_impersonation_submit = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={
                "action": "submit_success",
                "order_id": first_id,
                "player_id": "p_witcher_2",
                "result_event_id": "evt_lord_impersonation",
            },
        )
        self.assertEqual(lord_impersonation_submit.status_code, 403)

        submitted = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._player_headers("p_witcher_2"),
            json={
                "action": "submit_success",
                "order_id": first_id,
                "result_event_id": "evt_order_success",
            },
        )
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.json()["status"], "pending_master_approval")
        self.assertEqual(submitted.json()["closed_competing_orders"], [second_id])

        lord_impersonation_complete = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={"action": "complete", "order_id": first_id, "player_id": "p_witcher_2"},
        )
        self.assertEqual(lord_impersonation_complete.status_code, 403)

        completed = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._master_headers(),
            json={
                "action": "complete",
                "order_id": first_id,
                "reason": "reviewed submitted order proof",
            },
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["order"]["escrow"][0]["status"], "awarded")
        self.assertEqual(completed.json()["reward_update"]["status"], "applied")
        self.assertEqual(completed.json()["reward_update"]["rewards"][0]["gold_gain"], 15)

        duplicate_complete = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._master_headers(),
            json={
                "action": "complete",
                "order_id": first_id,
                "reason": "duplicate approval retry",
            },
        )
        self.assertEqual(duplicate_complete.status_code, 200)
        self.assertEqual(duplicate_complete.json()["reward_update"]["status"], "already_settled")

        with connect(settings) as connection:
            second_status = connection.execute(
                "SELECT status FROM order_runtime_state WHERE order_id = ?",
                (second_id,),
            ).fetchone()["status"]
            second_escrow = connection.execute(
                "SELECT status FROM escrow_ledger WHERE order_id = ?",
                (second_id,),
            ).fetchone()["status"]
            forest_gold_after_settlement = connection.execute(
                "SELECT gold FROM domain_runtime_state WHERE domain_id = 'domain_forest'"
            ).fetchone()["gold"]
            witcher_reward = connection.execute(
                "SELECT xp, gold FROM player_runtime_state WHERE player_id = 'p_witcher_2'"
            ).fetchone()
            order_seal = connection.execute(
                """
                SELECT quantity
                FROM asset_ownership
                WHERE owner_player_id = 'p_witcher_2'
                  AND asset_type = 'item'
                  AND asset_id = 'item_order_seal'
                  AND status = 'active'
                """
            ).fetchone()

        self.assertEqual(second_status, "failed_closed")
        self.assertEqual(second_escrow, "released")
        self.assertEqual(forest_gold_after_settlement, 65)
        self.assertEqual(dict(witcher_reward), {"xp": 6, "gold": 35})
        self.assertEqual(order_seal["quantity"], 1)

    def test_cross_lord_order_race_closes_competitors_and_refunds_escrow(self) -> None:
        settings = self._settings("lord_cross_lord_orders")
        self._import_seed(settings)
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            initial_hill_gold = connection.execute(
                "SELECT gold FROM domain_runtime_state WHERE domain_id = 'domain_hill'",
            ).fetchone()["gold"]
        client = TestClient(create_app(settings))

        forest = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={
                "action": "create",
                "object_id": "territory_well_city",
                "visibility": "public",
                "target_player_id": "p_witcher_2",
                "escrow_reward_id": "reward_order_success",
            },
        )
        hill = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={
                "action": "create",
                "object_id": "territory_well_city",
                "visibility": "public",
                "target_player_id": "p_witcher_3",
                "escrow_reward_id": "reward_order_success",
            },
        )
        self.assertEqual(forest.status_code, 200, forest.text)
        self.assertEqual(hill.status_code, 200, hill.text)
        forest_id = forest.json()["order"]["order_id"]
        hill_id = hill.json()["order"]["order_id"]

        accepted = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._player_headers("p_witcher_2"),
            json={"action": "accept", "order_id": forest_id},
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        submitted = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._player_headers("p_witcher_2"),
            json={
                "action": "submit_success",
                "order_id": forest_id,
                "result_event_id": "evt_cross_lord_order_success",
            },
        )
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()["closed_competing_orders"], [hill_id])

        completed = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._master_headers(),
            json={
                "action": "complete",
                "order_id": forest_id,
                "reason": "cross-lord race proof accepted",
            },
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        duplicate_complete = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._master_headers(),
            json={
                "action": "complete",
                "order_id": forest_id,
                "reason": "duplicate cross-lord completion retry",
            },
        )
        self.assertEqual(duplicate_complete.status_code, 200, duplicate_complete.text)
        self.assertEqual(duplicate_complete.json()["reward_update"]["status"], "already_settled")

        with connect(settings) as connection:
            loser = connection.execute(
                "SELECT status FROM order_runtime_state WHERE order_id = ?",
                (hill_id,),
            ).fetchone()
            loser_escrow = connection.execute(
                "SELECT status FROM escrow_ledger WHERE order_id = ?",
                (hill_id,),
            ).fetchone()
            hill_gold = connection.execute(
                "SELECT gold FROM domain_runtime_state WHERE domain_id = 'domain_hill'",
            ).fetchone()["gold"]
            winner_escrow_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM escrow_ledger
                WHERE order_id = ? AND status = 'awarded'
                """,
                (forest_id,),
            ).fetchone()[0]

        self.assertEqual(loser["status"], "failed_closed")
        self.assertEqual(loser_escrow["status"], "released")
        self.assertEqual(hill_gold, initial_hill_gold)
        self.assertEqual(winner_escrow_count, 1)

    def test_weighted_route_movement_validates_route_and_mp(self) -> None:
        settings = self._settings("lord_weighted_route")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        impossible_route = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={
                "to_node_id": "node_well_city",
                "route_node_ids": ["node_res_north", "node_well_city"],
            },
        )
        self.assertEqual(impossible_route.status_code, 400)
        self.assertEqual(impossible_route.json()["detail"]["code"], "invalid_route")

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
        self.assertEqual(active.status_code, 200, active.text)
        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={
                "to_node_id": "node_well_city",
                "route_node_ids": [
                    "node_res_north",
                    "node_fort_east",
                    "node_well_city",
                ],
            },
        )
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(moved.json()["mp_spent"], 4)
        self.assertEqual(moved.json()["current_mp"], 2)
        self.assertEqual(
            moved.json()["route"],
            ["node_res_north", "node_fort_east", "node_well_city"],
        )
        self._complete_pending_moves(settings)

        too_expensive = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={
                "to_node_id": "node_lake_south_pond",
                "route_node_ids": [
                    "node_well_city",
                    "node_village_east_shed",
                    "node_lake_mist",
                    "node_field_east_large",
                    "node_science_barn",
                    "node_forest_south_garden",
                    "node_lake_south_pond",
                ],
            },
        )
        self.assertEqual(too_expensive.status_code, 400)
        self.assertEqual(too_expensive.json()["detail"]["code"], "insufficient_mp")

    def test_movement_rejects_non_positive_runtime_route_cost(self) -> None:
        settings = self._settings("lord_bad_route_cost")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE map_edges
                SET mp_cost = -2
                WHERE edge_id = 'edge_north_fort_east'
                """
            )

        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={"to_node_id": "node_fort_east"},
        )

        self.assertEqual(moved.status_code, 400)
        self.assertEqual(moved.json()["detail"]["code"], "invalid_route_cost")

    def test_lord_actions_reject_invalid_movement_garrison_raid_recruit_and_order_edges(self) -> None:
        settings = self._settings("lord_guardrails")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        missing_route = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={},
        )
        self.assertEqual(missing_route.status_code, 400)
        self.assertEqual(missing_route.json()["detail"]["code"], "missing_route")

        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                "UPDATE domain_runtime_state SET current_mp = 0 WHERE domain_id = 'domain_north'"
            )
        no_mp = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={"to_node_id": "node_fort_east"},
        )
        self.assertEqual(no_mp.status_code, 400)
        self.assertEqual(no_mp.json()["detail"]["code"], "insufficient_mp")

        invalid_count = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 0,
            },
        )
        self.assertEqual(invalid_count.status_code, 400)
        self.assertEqual(invalid_count.json()["detail"]["code"], "invalid_count")

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_north',
                    status = 'contested',
                    contested_by_domain_id = 'domain_river'
                WHERE territory_id = 'territory_res_north'
                """
            )
        contested_transfer = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(contested_transfer.status_code, 400)
        self.assertEqual(contested_transfer.json()["detail"]["code"], "territory_contested")

        neutral_raid = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={"target_territory_id": "territory_field_oats"},
        )
        own_raid = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={"target_territory_id": "territory_res_north"},
        )
        self.assertEqual(neutral_raid.status_code, 400)
        self.assertEqual(neutral_raid.json()["detail"]["code"], "raid_target_neutral")
        self.assertEqual(own_raid.status_code, 400)
        self.assertEqual(own_raid.json()["detail"]["code"], "raid_target_own")

        with connect(settings) as connection:
            connection.execute(
                "UPDATE domain_runtime_state SET raid_tokens = 0, gold = 80 WHERE domain_id = 'domain_north'"
            )
        no_raid_token = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={"target_territory_id": "territory_res_river"},
        )
        self.assertEqual(no_raid_token.status_code, 400)
        self.assertEqual(no_raid_token.json()["detail"]["code"], "insufficient_raid_tokens")

        with connect(settings) as connection:
            connection.execute(
                "UPDATE domain_runtime_state SET raid_tokens = 1, gold = 0 WHERE domain_id = 'domain_north'"
            )
        no_raid_gold = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={"target_territory_id": "territory_res_river"},
        )
        self.assertEqual(no_raid_gold.status_code, 400)
        self.assertEqual(no_raid_gold.json()["detail"]["code"], "insufficient_gold")

        missing_offer = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "hold"},
        )
        self.assertEqual(missing_offer.status_code, 400)
        self.assertEqual(missing_offer.json()["detail"]["code"], "missing_offer")

        refresh = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "refresh"},
        )
        self.assertEqual(refresh.status_code, 200)
        offer_id = refresh.json()["offers"][0]["offer_id"]
        unknown_recruit_action = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "reserve", "offer_id": offer_id},
        )
        self.assertEqual(unknown_recruit_action.status_code, 400)
        self.assertEqual(unknown_recruit_action.json()["detail"]["code"], "unknown_recruit_action")

        missing_addressed_target = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={
                "action": "create",
                "object_id": "territory_magic_corner",
                "visibility": "addressed",
            },
        )
        self.assertEqual(missing_addressed_target.status_code, 400)
        self.assertEqual(missing_addressed_target.json()["detail"]["code"], "missing_target")

        missing_escrow = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={
                "action": "create",
                "object_id": "territory_lake_mist",
                "visibility": "public",
            },
        )
        self.assertEqual(missing_escrow.status_code, 400)
        self.assertEqual(missing_escrow.json()["detail"]["code"], "missing_escrow_reward")

        public_order = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={
                "action": "create",
                "object_id": "territory_lake_mist",
                "visibility": "public",
                "escrow_reward_id": "reward_order_success",
            },
        )
        self.assertEqual(public_order.status_code, 200, public_order.text)
        order_id = public_order.json()["order"]["order_id"]
        missing_player = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={"action": "accept", "order_id": order_id},
        )
        unknown_order_action = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={"action": "archive", "order_id": order_id, "player_id": "p_witcher_5"},
        )
        self.assertEqual(missing_player.status_code, 403)
        self.assertEqual(unknown_order_action.status_code, 400)
        self.assertEqual(unknown_order_action.json()["detail"]["code"], "unknown_order_action")

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def _import_seed(self, settings: Settings) -> None:
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")

    def _complete_pending_moves(
        self, settings: Settings, domain_id: str = "domain_north"
    ) -> list[dict[str, object]]:
        with connect(settings) as connection:
            return reconcile_pending_lord_moves(
                connection,
                domain_id=domain_id,
                now=datetime.now(UTC) + timedelta(minutes=1),
            )

    def _set_reserve_count(self, settings: Settings, reserve_id: str, count: int) -> None:
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                "UPDATE army_reserve_runtime SET count = ? WHERE reserve_id = ?",
                (count, reserve_id),
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
            "p_witcher_4": "WC-BEAR-3SC5",
            "p_witcher_5": "WC-VIPER-9BZ1",
        }
        return {"X-Player-Code": codes[player_id]}

    @staticmethod
    def _master_headers() -> dict[str, str]:
        return {"X-Role-Token": "MASTER-KING-4QZ8"}

    @staticmethod
    def _territory(items: list[dict[str, object]], territory_id: str) -> dict[str, object]:
        return next(item for item in items if item["territory_id"] == territory_id)


if __name__ == "__main__":
    unittest.main()
