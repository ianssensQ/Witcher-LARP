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
        started_at = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
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
        self.assertEqual(move_payload["mp_spent"], 2)
        self.assertEqual(move_payload["current_mp"], 4)
        self.assertEqual(move_payload["battle_spent_mp"], 0)
        self.assertEqual(move_payload["claim"]["status"], "in_battle")
        self.assertTrue(move_payload["claim"]["visible_to_lords"])

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
        self.assertIn("b_storehouse", blocked_siege.json()["detail"]["message"])

        storehouse = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_storehouse"},
        )
        self.assertEqual(storehouse.status_code, 200)
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

        moved_away = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={"to_node_id": "node_fort_east"},
        )
        self.assertEqual(moved_away.status_code, 200)
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

        accepted = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={"action": "accept", "order_id": first_id, "player_id": "p_witcher_2"},
        )
        self.assertEqual(accepted.status_code, 200)

        conflict = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={"action": "accept", "order_id": second_id, "player_id": "p_witcher_2"},
        )
        self.assertEqual(conflict.status_code, 400)
        self.assertEqual(conflict.json()["detail"]["code"], "order_object_conflict")

        submitted = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={
                "action": "submit_success",
                "order_id": first_id,
                "player_id": "p_witcher_2",
                "result_event_id": "evt_order_success",
            },
        )
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.json()["status"], "pending_master_approval")
        self.assertEqual(submitted.json()["closed_competing_orders"], [second_id])

        completed = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={"action": "complete", "order_id": first_id},
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["order"]["escrow"][0]["status"], "awarded")
        self.assertEqual(completed.json()["reward_update"]["status"], "applied")
        self.assertEqual(completed.json()["reward_update"]["rewards"][0]["gold_gain"], 15)

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

        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={
                "to_node_id": "node_well_city",
                "route_node_ids": [
                    "node_res_north",
                    "node_fort_east",
                    "node_village_barn",
                    "node_well_city",
                ],
            },
        )
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(moved.json()["mp_spent"], 5)
        self.assertEqual(moved.json()["current_mp"], 1)
        self.assertEqual(
            moved.json()["route"],
            ["node_res_north", "node_fort_east", "node_village_barn", "node_well_city"],
        )

        too_expensive = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={
                "to_node_id": "node_lake_mist",
                "route_node_ids": ["node_res_river", "node_lake_mist"],
            },
        )
        self.assertEqual(too_expensive.status_code, 400)
        self.assertEqual(too_expensive.json()["detail"]["code"], "insufficient_mp")

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
        self.assertEqual(missing_player.status_code, 400)
        self.assertEqual(missing_player.json()["detail"]["code"], "missing_player")
        self.assertEqual(unknown_order_action.status_code, 400)
        self.assertEqual(unknown_order_action.json()["detail"]["code"], "unknown_order_action")

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def _import_seed(self, settings: Settings) -> None:
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")

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
    def _territory(items: list[dict[str, object]], territory_id: str) -> dict[str, object]:
        return next(item for item in items if item["territory_id"] == territory_id)


if __name__ == "__main__":
    unittest.main()
