from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.lord_runtime import BUILDING_RECRUIT_GROWTH_PER_HOUR_BY_CLASS
from backend.witcher_larp.lord_runtime import BUILDING_RECRUIT_INITIAL_STOCK_BY_CLASS
from backend.witcher_larp.lord_runtime import anti_snowball_cut_for_domain
from backend.witcher_larp.lord_runtime import ensure_lord_runtime_state
from backend.witcher_larp.lord_runtime import raid_income_multiplier_for_territory
from backend.witcher_larp.lord_runtime import raid_token_surcharge_for_domain
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

    def test_building_recruit_initial_stock_matches_one_growth_tick(self) -> None:
        self.assertEqual(
            BUILDING_RECRUIT_INITIAL_STOCK_BY_CLASS,
            BUILDING_RECRUIT_GROWTH_PER_HOUR_BY_CLASS,
        )

    def test_recruit_refresh_clamps_existing_stock_to_two_tick_cap(self) -> None:
        settings = self._settings("lord_recruit_cap_clamp")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        built = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_training_yard"},
        )
        self.assertEqual(built.status_code, 200, built.text)
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE army_reserve_runtime
                SET count = 240,
                    updated_at = ?
                WHERE reserve_id = 'reserve_north_infantry'
                """,
                (datetime.now(UTC).isoformat(),),
            )

        refresh = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "refresh"},
        )

        self.assertEqual(refresh.status_code, 200, refresh.text)
        self.assertEqual(
            {"unit_infantry_t1": 48},
            {
                reserve["card_id"]: reserve["count"]
                for reserve in refresh.json()["spawned_reserves"]
            },
        )

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
                "UPDATE army_reserve_runtime SET count = 8 WHERE reserve_id = 'reserve_north_infantry'"
            )
        client = TestClient(create_app(settings))

        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 8,
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

        with connect(settings) as connection:
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count, location_node_id, status, updated_at
                )
                VALUES (
                    'army_north_prepared_guard',
                    'domain_north',
                    'unit_guard_t1',
                    20,
                    'node_fort_east',
                    'active',
                    '2026-06-02T10:00:00+00:00'
                )
                """
            )

        battle = client.post(
            "/api/lord-battles",
            headers=self._headers("north"),
            json={
                "battle_id": "battle_fort_east_capture",
                "attacker_domain_id": "domain_north",
                "territory_id": "territory_fort_east",
                "seed": "north-fort-prepared-win",
            },
        )
        self.assertEqual(battle.status_code, 200, battle.text)
        self._start_battle_after_deployment(client, "battle_fort_east_capture")
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
        self.assertEqual(capture_payload["pending_tick_awards"][0]["reward_gold"], 15)
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

    def test_captured_territory_keeps_one_garrison_unit_until_replaced(self) -> None:
        settings = self._settings("lord_captured_min_garrison")
        self._import_seed(settings)
        client = TestClient(create_app(settings))
        now = "2026-06-02T10:00:00+00:00"
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_river',
                    status = 'capture_pending_garrison',
                    contested_by_domain_id = 'domain_north',
                    updated_at = ?
                WHERE territory_id = 'territory_fort_east'
                """,
                (now,),
            )
            connection.execute(
                """
                INSERT INTO territory_claim_runtime (
                    claim_id, territory_id, claimant_domain_id, defender_domain_id,
                    status, source, created_at, resolved_at, battle_required
                )
                VALUES (
                    'claim_north_fort_min_garrison',
                    'territory_fort_east',
                    'domain_north',
                    'domain_river',
                    'awaiting_garrison',
                    'test',
                    ?,
                    ?,
                    0
                )
                """,
                (now, now),
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET current_node_id = 'node_fort_east',
                    updated_at = ?
                WHERE domain_id = 'domain_north'
                """,
                (now,),
            )
            connection.execute("DELETE FROM active_army_runtime WHERE domain_id = 'domain_north'")
            connection.executemany(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count, location_node_id, status, updated_at
                )
                VALUES (?, 'domain_north', ?, ?, 'node_fort_east', 'active', ?)
                """,
                [
                    ("army_north_capture_infantry", "unit_infantry_t1", 1, now),
                    ("army_north_capture_guard", "unit_guard_t1", 1, now),
                ],
            )

        captured = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "active_to_fort",
                "territory_id": "territory_fort_east",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(captured.status_code, 200, captured.text)
        self.assertEqual(captured.json()["status"], "captured")

        last_unit = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "fort_to_active",
                "territory_id": "territory_fort_east",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(last_unit.status_code, 400, last_unit.text)
        self.assertEqual(last_unit.json()["detail"]["code"], "minimum_garrison_required")

        replacement = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "active_to_fort",
                "territory_id": "territory_fort_east",
                "card_id": "unit_guard_t1",
                "count": 1,
            },
        )
        self.assertEqual(replacement.status_code, 200, replacement.text)
        self.assertEqual(replacement.json()["status"], "reinforced")

        swapped = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "fort_to_active",
                "territory_id": "territory_fort_east",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(swapped.status_code, 200, swapped.text)
        self.assertEqual(swapped.json()["status"], "active_army_updated")
        with connect(settings) as connection:
            garrison_total = connection.execute(
                """
                SELECT COALESCE(SUM(count), 0)
                FROM garrison_runtime_state
                WHERE territory_id = 'territory_fort_east'
                  AND domain_id = 'domain_north'
                  AND status = 'active'
                """
            ).fetchone()[0]
        self.assertEqual(garrison_total, 1)

    def test_reserve_to_active_spends_gold_and_rejects_insufficient_gold(self) -> None:
        settings = self._settings("lord_reserve_to_active_cost")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET gold = 3
                WHERE domain_id = 'domain_north'
                """
            )

        blocked = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 4,
            },
        )
        self.assertEqual(blocked.status_code, 400, blocked.text)
        self.assertEqual(blocked.json()["detail"]["code"], "insufficient_gold")

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET gold = 10
                WHERE domain_id = 'domain_north'
                """
            )

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
        self.assertEqual(active.status_code, 200, active.text)
        self.assertEqual(active.json()["gold_spent"], 8)

        with connect(settings) as connection:
            domain = connection.execute(
                "SELECT gold FROM domain_runtime_state WHERE domain_id = 'domain_north'"
            ).fetchone()
            reserve = connection.execute(
                """
                SELECT count
                FROM army_reserve_runtime
                WHERE reserve_id = 'reserve_north_infantry'
                """
            ).fetchone()
            army = connection.execute(
                """
                SELECT count
                FROM active_army_runtime
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                """
            ).fetchone()
        self.assertEqual(domain["gold"], 2)
        self.assertEqual(reserve["count"], 20)
        self.assertEqual(army["count"], 4)

    def test_reserve_and_garrison_to_active_allow_large_one_card_stacks(self) -> None:
        settings = self._settings("lord_reserve_to_active_large_stacks")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 9,
            },
        )
        self.assertEqual(active.status_code, 200, active.text)
        self.assertNotIn("field_count_cap", active.json())

        extra = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 1,
            },
        )
        self.assertEqual(extra.status_code, 200, extra.text)

        with connect(settings) as connection:
            connection.execute(
                """
                INSERT INTO garrison_runtime_state (
                    garrison_id, territory_id, domain_id, card_id, count, status, updated_at
                )
                VALUES (
                    'garrison_north_extra_infantry',
                    'territory_res_north',
                    'domain_north',
                    'unit_infantry_t1',
                    40,
                    'active',
                    '2026-06-02T10:00:00+00:00'
                )
                """
            )

        from_garrison = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "fort_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "stack_id": "garrison_north_extra_infantry",
                "count": 40,
            },
        )
        self.assertEqual(from_garrison.status_code, 200, from_garrison.text)

        with connect(settings) as connection:
            army_total = connection.execute(
                """
                SELECT SUM(count) AS count
                FROM active_army_runtime
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                  AND status = 'active'
                """
            ).fetchone()
            garrison_stack = connection.execute(
                """
                SELECT count, status
                FROM garrison_runtime_state
                WHERE garrison_id = 'garrison_north_extra_infantry'
                """
            ).fetchone()
        self.assertEqual(army_total["count"], 50)
        self.assertEqual(garrison_stack["count"], 0)
        self.assertEqual(garrison_stack["status"], "empty")

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
            "unit_infantry_t1",
            {offer["card_id"] for offer in training.json()["unlocked_recruit_offers"]},
        )
        self.assertEqual(training.json()["spawned_reserves"], [])

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
        self.assertEqual(
            {"unit_guard_t1": 12},
            {
                reserve["card_id"]: reserve["count"]
                for reserve in barracks.json()["spawned_reserves"]
            },
        )
        blocked_siege = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_siege_yard"},
        )
        self.assertEqual(blocked_siege.status_code, 400)
        self.assertIn("b_archery_range", blocked_siege.json()["detail"]["message"])

        with connect(settings) as connection:
            connection.execute(
                """
                INSERT INTO army_reserve_runtime (
                    reserve_id, domain_id, card_id, count, status, updated_at
                )
                VALUES (
                    'reserve_zero_ranged_before_archery',
                    'domain_north',
                    'unit_ranged_t1',
                    0,
                    'available',
                    '2026-01-01T00:00:00+00:00'
                )
                """
            )

        archery = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_archery_range"},
        )
        self.assertEqual(archery.status_code, 200)
        self.assertEqual(
            {"unit_ranged_t1": 12},
            {
                reserve["card_id"]: reserve["count"]
                for reserve in archery.json()["spawned_reserves"]
            },
        )
        with connect(settings) as connection:
            connection.execute(
                """
                DELETE FROM army_reserve_runtime
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_ranged_t1'
                """
            )
        siege = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_siege_yard"},
        )
        self.assertEqual(siege.status_code, 200)
        self.assertEqual(siege.json()["raid_token_delta"], 0)
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
        self.assertIn(
            "unit_ranged_t1",
            {reserve["card_id"] for reserve in refresh.json()["spawned_reserves"]},
        )
        self.assertNotIn(
            "unit_specialist_t3",
            {offer["card_id"] for offer in refresh.json()["offers"]},
        )
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
                SELECT COALESCE(SUM(count), 0) AS count
                FROM army_reserve_runtime
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_heavy_siege_t3'
                """
            ).fetchone()["count"]
        self.assertEqual(reserve_count, 3)

    def test_building_purchase_is_scoped_to_residence(self) -> None:
        settings = self._settings("lord_building_scope")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET gold = 1000
                WHERE domain_id = 'domain_north'
                """
            )
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_north', status = 'controlled'
                WHERE territory_id = 'territory_fort_east'
                """
            )

        residence_training = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={
                "building_id": "b_training_yard",
                "territory_id": "territory_res_north",
            },
        )
        self.assertEqual(residence_training.status_code, 200, residence_training.text)
        self.assertEqual(residence_training.json()["territory_id"], "territory_res_north")

        default_barracks = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_barracks"},
        )
        self.assertEqual(default_barracks.status_code, 200, default_barracks.text)
        self.assertEqual(default_barracks.json()["territory_id"], "territory_res_north")

        non_residence_barracks = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={
                "building_id": "b_barracks",
                "territory_id": "territory_fort_east",
            },
        )
        self.assertEqual(non_residence_barracks.status_code, 400, non_residence_barracks.text)
        self.assertEqual(
            non_residence_barracks.json()["detail"]["code"],
            "building_tree_residence_only",
        )

        fort_training = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={
                "building_id": "b_training_yard",
                "territory_id": "territory_fort_east",
            },
        )
        self.assertEqual(fort_training.status_code, 400, fort_training.text)
        self.assertEqual(
            fort_training.json()["detail"]["code"],
            "building_tree_residence_only",
        )

        wrong_tree = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={"building_id": "b_bank", "territory_id": "territory_fort_east"},
        )
        self.assertEqual(wrong_tree.status_code, 400, wrong_tree.text)
        self.assertEqual(
            wrong_tree.json()["detail"]["code"],
            "building_tree_residence_only",
        )

        not_owned = client.post(
            "/api/lords/p_lord_1/buildings",
            headers=self._headers("north"),
            json={
                "building_id": "b_training_yard",
                "territory_id": "territory_fort_west",
            },
        )
        self.assertEqual(not_owned.status_code, 403, not_owned.text)
        self.assertEqual(not_owned.json()["detail"]["code"], "territory_not_owned")

        state = client.get(
            "/api/lords/p_lord_1/state",
            headers=self._headers("north"),
        )
        self.assertEqual(state.status_code, 200, state.text)
        payload = state.json()
        residence = self._territory(payload["territory_views"], "territory_res_north")
        fort = self._territory(payload["territory_views"], "territory_fort_east")
        residence_nodes = {
            node["building_id"]: node for node in residence["building_tree"]["nodes"]
        }

        self.assertEqual(residence_nodes["b_training_yard"]["status"], "built")
        self.assertEqual(residence_nodes["b_barracks"]["status"], "built")
        self.assertEqual(fort["building_tree"]["scope"], "residence_only")
        self.assertEqual(fort["building_tree"]["node_ids"], [])
        self.assertEqual(
            fort["building_tree_lock_reason"],
            "Здания строятся в главном замке",
        )

    def test_recruit_purchase_quantity_to_owned_garrison(self) -> None:
        settings = self._settings("lord_recruit_garrison")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        refresh = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "refresh"},
        )
        self.assertEqual(refresh.status_code, 200)
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE army_reserve_runtime
                SET count = 3
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                """
            )
            connection.execute(
                """
                INSERT INTO army_reserve_runtime (
                    reserve_id, domain_id, card_id, count, status, updated_at
                )
                VALUES (
                    'reserve_north_infantry_extra',
                    'domain_north',
                    'unit_infantry_t1',
                    21,
                    'available',
                    '2026-01-01T00:00:00+00:00'
                )
                """
            )

        hired = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={
                "action": "purchase_stock",
                "card_id": "unit_infantry_t1",
                "quantity": 20,
                "territory_id": "territory_res_north",
            },
        )

        self.assertEqual(hired.status_code, 200, hired.text)
        payload = hired.json()
        self.assertEqual(payload["status"], "hired")
        self.assertEqual(payload["count"], 20)
        self.assertEqual(payload["gold_spent"], 40)
        self.assertEqual(payload["garrison"]["territory_id"], "territory_res_north")

        with connect(settings) as connection:
            gold = connection.execute(
                "SELECT gold FROM domain_runtime_state WHERE domain_id = 'domain_north'"
            ).fetchone()["gold"]
            reserve_count = connection.execute(
                """
                SELECT COALESCE(SUM(count), 0) AS count
                FROM army_reserve_runtime
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                  AND status = 'available'
                """
            ).fetchone()["count"]
            garrison_count = connection.execute(
                """
                SELECT count
                FROM garrison_runtime_state
                WHERE territory_id = 'territory_res_north'
                  AND domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                """
            ).fetchone()["count"]
        self.assertEqual(gold, 40)
        self.assertEqual(reserve_count, 4)
        self.assertEqual(garrison_count, 20)

    def test_recruit_purchase_payload_with_offer_id_still_hires(self) -> None:
        settings = self._settings("lord_recruit_legacy_payload")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        refresh = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "refresh"},
        )
        self.assertEqual(refresh.status_code, 200, refresh.text)
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE army_reserve_runtime
                SET count = 8
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                """
            )

        hired = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={
                "action": "purchase",
                "offer_id": "offer_north_infantry",
                "quantity": 6,
                "territory_id": "territory_res_north",
            },
        )

        self.assertEqual(hired.status_code, 200, hired.text)
        payload = hired.json()
        self.assertEqual(payload["status"], "hired")
        self.assertEqual(payload["count"], 6)
        self.assertEqual(payload["gold_spent"], 12)
        self.assertEqual(payload["garrison"]["territory_id"], "territory_res_north")

    def test_recruit_purchase_stock_rejects_empty_stock_contested_and_capacity(self) -> None:
        settings = self._settings("lord_recruit_stock_guards")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        refresh = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={"action": "refresh"},
        )
        self.assertEqual(refresh.status_code, 200, refresh.text)

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE army_reserve_runtime
                SET count = 0,
                    status = 'empty'
                WHERE domain_id = 'domain_north'
                  AND card_id = 'unit_infantry_t1'
                """
            )
        empty_stock = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={
                "action": "purchase_stock",
                "card_id": "unit_infantry_t1",
                "quantity": 1,
                "territory_id": "territory_res_north",
            },
        )
        self.assertEqual(empty_stock.status_code, 400, empty_stock.text)
        self.assertEqual(empty_stock.json()["detail"]["code"], "insufficient_stock")

        with connect(settings) as connection:
            connection.execute(
                """
                INSERT INTO army_reserve_runtime (
                    reserve_id, domain_id, card_id, count, status, updated_at
                )
                VALUES (
                    'reserve_test_infantry_stock',
                    'domain_north',
                    'unit_infantry_t1',
                    5,
                    'available',
                    '2026-01-01T00:00:00+00:00'
                )
                ON CONFLICT(reserve_id) DO UPDATE SET
                    count = excluded.count,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """
            )
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET status = 'contested',
                    contested_by_domain_id = 'domain_river'
                WHERE territory_id = 'territory_res_north'
                """
            )
        contested = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={
                "action": "purchase_stock",
                "card_id": "unit_infantry_t1",
                "quantity": 1,
                "territory_id": "territory_res_north",
            },
        )
        self.assertEqual(contested.status_code, 400, contested.text)
        self.assertEqual(contested.json()["detail"]["code"], "territory_contested")

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET status = 'controlled',
                    contested_by_domain_id = NULL
                WHERE territory_id = 'territory_res_north'
                """
            )
            connection.execute(
                """
                UPDATE territory_forts
                SET garrison_capacity = 0
                WHERE territory_id = 'territory_res_north'
                """
            )
            connection.execute(
                """
                DELETE FROM garrison_runtime_state
                WHERE territory_id = 'territory_res_north'
                  AND card_id = 'unit_infantry_t1'
                """
            )
        capacity = client.post(
            "/api/lords/p_lord_1/recruit",
            headers=self._headers("north"),
            json={
                "action": "purchase_stock",
                "card_id": "unit_infantry_t1",
                "quantity": 1,
                "territory_id": "territory_res_north",
            },
        )
        self.assertEqual(capacity.status_code, 400, capacity.text)
        self.assertEqual(capacity.json()["detail"]["code"], "fort_capacity_exceeded")

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

    def test_existing_front_claim_attaches_second_lord_army_as_defender(self) -> None:
        settings = self._settings("lord_claim_collision_defender")
        self._import_seed(settings)
        self._set_reserve_count(settings, "reserve_north_infantry", 4)
        client = TestClient(create_app(settings))

        north_active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 2,
            },
        )
        self.assertEqual(north_active.status_code, 200, north_active.text)
        north_move = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={"to_node_id": "node_fort_east"},
        )
        self.assertEqual(north_move.status_code, 200, north_move.text)
        north_completed = self._complete_pending_moves(settings)
        north_claim = north_completed[0]["claim"]
        self.assertEqual(north_claim["territory_id"], "territory_fort_east")
        self.assertIsNone(north_claim.get("defender_domain_id"))

        now = "2026-06-02T10:00:00+00:00"
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_river',
                    status = 'controlled',
                    contested_by_domain_id = NULL,
                    controlled_since = ?,
                    updated_at = ?
                WHERE territory_id = 'territory_well_city'
                """,
                (now, now),
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET current_node_id = 'node_well_city',
                    current_mp = 6,
                    updated_at = ?
                WHERE domain_id = 'domain_river'
                """,
                (now,),
            )
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count, location_node_id, status, updated_at
                )
                VALUES (
                    'army_river_collision',
                    'domain_river',
                    'unit_guard_t1',
                    3,
                    'node_well_city',
                    'active',
                    ?
                )
                """,
                (now,),
            )

        river_move = client.post(
            "/api/lords/p_lord_2/move",
            headers=self._headers("river"),
            json={
                "to_node_id": "node_fort_east",
                "route_node_ids": ["node_well_city", "node_fort_east"],
            },
        )
        self.assertEqual(river_move.status_code, 200, river_move.text)
        river_completed = self._complete_pending_moves(settings, domain_id="domain_river")
        collision_claim = river_completed[0]["claim"]
        self.assertEqual(collision_claim["claim_id"], north_claim["claim_id"])
        self.assertEqual(collision_claim["claimant_domain_id"], "domain_north")
        self.assertEqual(collision_claim["defender_domain_id"], "domain_river")

        battle = client.post(
            "/api/lord-battles",
            headers=self._headers("river"),
            json={
                "claim_id": north_claim["claim_id"],
                "territory_id": "territory_fort_east",
                "seed": "collision-lords",
            },
        )
        self.assertEqual(battle.status_code, 200, battle.text)
        self.assertEqual(battle.json()["battle_type"], "lord_vs_lord")
        self.assertEqual(battle.json()["attacker_domain_id"], "domain_north")
        self.assertEqual(battle.json()["defender_domain_id"], "domain_river")

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
        automatic_preview = client.post(
            "/api/lords/p_lord_1/route-preview",
            headers=self._headers("north"),
            json={"to_node_id": "node_mountain_north_alpine"},
        )
        self.assertEqual(automatic_preview.status_code, 200, automatic_preview.text)
        automatic_payload = automatic_preview.json()
        self.assertEqual(automatic_payload["status"], "stopped")
        self.assertEqual(automatic_payload["reason_code"], "route_stopped_at_front")
        self.assertEqual(automatic_payload["requested_to_node_id"], "node_mountain_north_alpine")
        self.assertEqual(automatic_payload["to_node_id"], "node_fort_east")
        self.assertEqual(automatic_payload["route"], ["node_res_north", "node_fort_east"])
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

    def test_movement_from_neutral_front_cannot_advance_to_another_neutral(self) -> None:
        settings = self._settings("lord_map_neutral_front_lock")
        self._import_seed(settings)
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute("DELETE FROM active_army_runtime")
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET current_node_id = 'node_forest_dark',
                    current_mp = 3,
                    updated_at = '2026-06-02T10:00:00+00:00'
                WHERE domain_id = 'domain_north'
                """
            )
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count,
                    location_node_id, status, updated_at
                )
                VALUES (
                    'army_north_front_lock',
                    'domain_north',
                    'unit_infantry_t1',
                    3,
                    'node_forest_dark',
                    'active',
                    '2026-06-02T10:00:00+00:00'
                )
                """
            )
        client = TestClient(create_app(settings))

        direct_preview = client.post(
            "/api/lords/p_lord_1/route-preview",
            headers=self._headers("north"),
            json={"to_node_id": "node_swamp_black"},
        )
        self.assertEqual(direct_preview.status_code, 200, direct_preview.text)
        direct_payload = direct_preview.json()
        self.assertEqual(direct_payload["status"], "blocked")
        self.assertFalse(direct_payload["can_move"])
        self.assertEqual(direct_payload["reason_code"], "front_locked")
        self.assertEqual(direct_payload["route"], ["node_forest_dark", "node_swamp_black"])

        stopped_preview = client.post(
            "/api/lords/p_lord_1/route-preview",
            headers=self._headers("north"),
            json={
                "to_node_id": "node_fort_west",
                "route_node_ids": [
                    "node_forest_dark",
                    "node_field_west_large",
                    "node_fort_west",
                ],
            },
        )
        self.assertEqual(stopped_preview.status_code, 200, stopped_preview.text)
        stopped_payload = stopped_preview.json()
        self.assertEqual(stopped_payload["status"], "blocked")
        self.assertFalse(stopped_payload["can_move"])
        self.assertEqual(stopped_payload["reason_code"], "front_locked")
        self.assertEqual(stopped_payload["requested_to_node_id"], "node_fort_west")
        self.assertEqual(stopped_payload["to_node_id"], "node_field_west_large")
        self.assertEqual(stopped_payload["route"], ["node_forest_dark", "node_field_west_large"])

        moved = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={"to_node_id": "node_swamp_black"},
        )
        self.assertEqual(moved.status_code, 400, moved.text)
        self.assertEqual(moved.json()["detail"]["code"], "front_locked")
        with connect(settings) as connection:
            domain = connection.execute(
                """
                SELECT current_node_id, current_mp
                FROM domain_runtime_state
                WHERE domain_id = 'domain_north'
                """
            ).fetchone()
            pending_moves = connection.execute(
                """
                SELECT COUNT(*)
                FROM pending_lord_moves
                WHERE domain_id = 'domain_north'
                """
            ).fetchone()[0]
        self.assertEqual(domain["current_node_id"], "node_forest_dark")
        self.assertEqual(domain["current_mp"], 3)
        self.assertEqual(pending_moves, 0)

    def test_lord_map_intel_redacts_adjacent_enemy_army_until_revealed(self) -> None:
        settings = self._settings("lord_map_enemy_intel")
        self._import_seed(settings)
        client = TestClient(create_app(settings))
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET current_node_id = 'node_fort_east'
                WHERE domain_id = 'domain_river'
                """
            )
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count,
                    location_node_id, status, updated_at
                )
                VALUES (
                    'army_north_intel_probe',
                    'domain_north',
                    'unit_infantry_t1',
                    3,
                    'node_res_north',
                    'active',
                    CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count,
                    location_node_id, status, updated_at
                )
                VALUES (
                    'army_river_near_north',
                    'domain_river',
                    'unit_guard_t1',
                    5,
                    'node_fort_east',
                    'active',
                    CURRENT_TIMESTAMP
                )
                """
            )

        state = client.get(
            "/api/lords/p_lord_1/state",
            headers=self._headers("north"),
        )
        self.assertEqual(state.status_code, 200, state.text)
        intel = state.json()["lord_map_intel"]["enemy_armies"]
        self.assertEqual(len(intel), 1)
        self.assertEqual(intel[0]["node_id"], "node_fort_east")
        self.assertEqual(intel[0]["territory_id"], "territory_fort_east")
        self.assertEqual(intel[0]["intel_level"], "presence")
        self.assertTrue(intel[0]["presence"])
        self.assertTrue(intel[0]["detail_redacted"])
        self.assertNotIn("owner_domain_id", intel[0])
        self.assertNotIn("rough_strength", intel[0])
        self.assertNotIn("composition", intel[0])

        with connect(settings) as connection:
            connection.execute(
                """
                INSERT INTO lord_map_intel (
                    domain_id, target_type, target_id,
                    intel_level, revealed_at, source
                )
                VALUES (
                    'domain_north',
                    'enemy_army',
                    'domain_river:node_fort_east',
                    'composition',
                    CURRENT_TIMESTAMP,
                    'test_reveal'
                )
                """
            )

        revealed_state = client.get(
            "/api/lords/p_lord_1/state",
            headers=self._headers("north"),
        )
        self.assertEqual(revealed_state.status_code, 200, revealed_state.text)
        revealed = revealed_state.json()["lord_map_intel"]["enemy_armies"][0]
        self.assertEqual(revealed["intel_level"], "composition")
        self.assertEqual(revealed["owner_domain_id"], "domain_river")
        self.assertEqual(revealed["rough_strength"], "medium")
        self.assertEqual(revealed["total_count"], 5)
        self.assertEqual(
            revealed["composition"],
            [
                {
                    "army_id": "army_river_near_north",
                    "card_id": "unit_guard_t1",
                    "count": 5,
                }
            ],
        )

    def test_lord_map_intel_uses_current_domain_node_for_one_road_visibility(self) -> None:
        settings = self._settings("lord_map_enemy_intel_current_node")
        self._import_seed(settings)
        client = TestClient(create_app(settings))
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute("DELETE FROM active_army_runtime")
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET current_node_id = 'node_fort_east'
                WHERE domain_id = 'domain_north'
                """
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET current_node_id = 'node_well_city'
                WHERE domain_id = 'domain_river'
                """
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET current_node_id = 'node_fort_east'
                WHERE domain_id = 'domain_forest'
                """
            )
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count,
                    location_node_id, status, updated_at
                )
                VALUES (
                    'army_north_stale_location',
                    'domain_north',
                    'unit_infantry_t1',
                    3,
                    'node_res_north',
                    'active',
                    CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count,
                    location_node_id, status, updated_at
                )
                VALUES (
                    'army_forest_same_node',
                    'domain_forest',
                    'unit_ranged_t1',
                    2,
                    'node_res_forest',
                    'active',
                    CURRENT_TIMESTAMP
                )
                """
            )

        state = client.get(
            "/api/lords/p_lord_1/state",
            headers=self._headers("north"),
        )

        self.assertEqual(state.status_code, 200, state.text)
        intel = state.json()["lord_map_intel"]["enemy_armies"]
        visible_nodes = {item["node_id"] for item in intel}
        self.assertIn("node_well_city", visible_nodes)
        self.assertIn("node_fort_east", visible_nodes)

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
        self.assertEqual(reserve_count, 24)
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

    def test_stack_split_and_id_based_partial_transfer_keep_duplicate_cards_separate(self) -> None:
        settings = self._settings("lord_stack_split_transfer")
        self._import_seed(settings)
        self._set_reserve_count(settings, "reserve_north_infantry", 12)
        client = TestClient(create_app(settings))

        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                INSERT INTO garrison_runtime_state (
                    garrison_id, territory_id, domain_id, card_id, count, status, updated_at
                )
                VALUES (
                    'garrison_north_ranged_14',
                    'territory_res_north',
                    'domain_north',
                    'unit_ranged_t1',
                    14,
                    'active',
                    '2026-01-01T00:00:00+00:00'
                )
                """
            )

        split_garrison = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "split_garrison",
                "territory_id": "territory_res_north",
                "stack_id": "garrison_north_ranged_14",
                "count": 5,
            },
        )
        self.assertEqual(split_garrison.status_code, 200, split_garrison.text)
        self.assertEqual(split_garrison.json()["status"], "garrison_stack_split")
        self.assertEqual(split_garrison.json()["source_remaining"], 9)
        with connect(settings) as connection:
            garrison_counts = [
                row["count"]
                for row in connection.execute(
                    """
                    SELECT count
                    FROM garrison_runtime_state
                    WHERE territory_id = 'territory_res_north'
                      AND domain_id = 'domain_north'
                      AND card_id = 'unit_ranged_t1'
                      AND status = 'active'
                    ORDER BY count
                    """
                ).fetchall()
            ]
        self.assertEqual(garrison_counts, [5, 9])

        active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "reserve_to_active",
                "territory_id": "territory_res_north",
                "card_id": "unit_infantry_t1",
                "count": 8,
            },
        )
        self.assertEqual(active.status_code, 200, active.text)
        active_stack_id = "army_domain_north_unit_infantry_t1"
        split_active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "split_active",
                "territory_id": "territory_res_north",
                "army_id": active_stack_id,
                "count": 5,
            },
        )
        self.assertEqual(split_active.status_code, 200, split_active.text)
        self.assertEqual(split_active.json()["status"], "active_stack_split")
        self.assertEqual(split_active.json()["source_remaining"], 3)
        with connect(settings) as connection:
            active_counts_after_split = [
                row["count"]
                for row in connection.execute(
                    """
                    SELECT count
                    FROM active_army_runtime
                    WHERE domain_id = 'domain_north'
                      AND card_id = 'unit_infantry_t1'
                      AND status = 'active'
                    ORDER BY count
                    """
                ).fetchall()
            ]
        self.assertEqual(active_counts_after_split, [3, 5])

        pulled = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "fort_to_active",
                "territory_id": "territory_res_north",
                "garrison_id": "garrison_north_ranged_14",
                "count": 5,
            },
        )
        self.assertEqual(pulled.status_code, 200, pulled.text)
        self.assertEqual(pulled.json()["status"], "active_army_updated")
        with connect(settings) as connection:
            ranged_active_counts = [
                row["count"]
                for row in connection.execute(
                    """
                    SELECT count
                    FROM active_army_runtime
                    WHERE domain_id = 'domain_north'
                      AND card_id = 'unit_ranged_t1'
                      AND status = 'active'
                    ORDER BY count
                    """
                ).fetchall()
            ]
            ranged_garrison_counts = [
                row["count"]
                for row in connection.execute(
                    """
                    SELECT count
                    FROM garrison_runtime_state
                    WHERE territory_id = 'territory_res_north'
                      AND domain_id = 'domain_north'
                      AND card_id = 'unit_ranged_t1'
                      AND status = 'active'
                    ORDER BY count
                    """
                ).fetchall()
            ]
        self.assertEqual(ranged_active_counts, [5])
        self.assertEqual(ranged_garrison_counts, [4, 5])

        state = client.get(
            "/api/lords/p_lord_1/state",
            headers=self._headers("north"),
        )
        self.assertEqual(state.status_code, 200, state.text)
        home = self._territory(state.json()["territories"], "territory_res_north")
        visible_ranged = [
            stack
            for stack in home["garrisons"]
            if stack.get("card_id") == "unit_ranged_t1"
        ]
        self.assertEqual(len(visible_ranged), 2)

    def test_same_lane_same_card_stacks_can_merge_back_by_id(self) -> None:
        settings = self._settings("lord_stack_merge")
        self._import_seed(settings)
        client = TestClient(create_app(settings))
        now = "2026-01-01T00:00:00+00:00"

        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                "DELETE FROM active_army_runtime WHERE domain_id = 'domain_north'"
            )
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count, location_node_id, status, updated_at
                )
                VALUES
                    ('army_merge_source', 'domain_north', 'unit_infantry_t1', 3, 'node_res_north', 'active', ?),
                    ('army_merge_target', 'domain_north', 'unit_infantry_t1', 5, 'node_res_north', 'active', ?)
                """,
                (now, now),
            )
            connection.execute(
                """
                INSERT INTO garrison_runtime_state (
                    garrison_id, territory_id, domain_id, card_id, count, status, updated_at
                )
                VALUES
                    ('garrison_merge_source', 'territory_res_north', 'domain_north', 'unit_ranged_t1', 5, 'active', ?),
                    ('garrison_merge_target', 'territory_res_north', 'domain_north', 'unit_ranged_t1', 9, 'active', ?),
                    ('garrison_merge_guard', 'territory_res_north', 'domain_north', 'unit_guard_t1', 1, 'active', ?)
                """,
                (now, now, now),
            )

        active_merge = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "merge_active",
                "territory_id": "territory_res_north",
                "stack_id": "army_merge_source",
                "target_stack_id": "army_merge_target",
            },
        )
        self.assertEqual(active_merge.status_code, 200, active_merge.text)
        self.assertEqual(active_merge.json()["status"], "active_stack_merged")
        self.assertEqual(active_merge.json()["count"], 8)

        garrison_merge = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "merge_garrison",
                "territory_id": "territory_res_north",
                "stack_id": "garrison_merge_source",
                "target_stack_id": "garrison_merge_target",
            },
        )
        self.assertEqual(garrison_merge.status_code, 200, garrison_merge.text)
        self.assertEqual(garrison_merge.json()["status"], "garrison_stack_merged")
        self.assertEqual(garrison_merge.json()["count"], 14)

        mismatch = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "merge_garrison",
                "territory_id": "territory_res_north",
                "stack_id": "garrison_merge_target",
                "target_stack_id": "garrison_merge_guard",
            },
        )
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(mismatch.json()["detail"]["code"], "merge_unit_mismatch")

        with connect(settings) as connection:
            active_rows = connection.execute(
                """
                SELECT army_id, count, status
                FROM active_army_runtime
                WHERE army_id IN ('army_merge_source', 'army_merge_target')
                ORDER BY army_id
                """
            ).fetchall()
            garrison_rows = connection.execute(
                """
                SELECT garrison_id, count, status
                FROM garrison_runtime_state
                WHERE garrison_id IN ('garrison_merge_source', 'garrison_merge_target')
                ORDER BY garrison_id
                """
            ).fetchall()
        self.assertEqual(
            [(row["army_id"], row["count"], row["status"]) for row in active_rows],
            [
                ("army_merge_source", 0, "empty"),
                ("army_merge_target", 8, "active"),
            ],
        )
        self.assertEqual(
            [
                (row["garrison_id"], row["count"], row["status"])
                for row in garrison_rows
            ],
            [
                ("garrison_merge_source", 0, "empty"),
                ("garrison_merge_target", 14, "active"),
            ],
        )

    def test_cross_lane_same_card_stack_drop_merges_into_target_by_id(self) -> None:
        settings = self._settings("lord_cross_lane_stack_merge")
        self._import_seed(settings)
        client = TestClient(create_app(settings))
        now = "2026-01-01T00:00:00+00:00"

        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                "DELETE FROM active_army_runtime WHERE domain_id = 'domain_north'"
            )
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count, location_node_id, status, updated_at
                )
                VALUES
                    ('army_to_fort_source', 'domain_north', 'unit_infantry_t1', 4, 'node_res_north', 'active', ?),
                    ('army_cross_target', 'domain_north', 'unit_ranged_t1', 3, 'node_res_north', 'active', ?),
                    ('army_cross_guard', 'domain_north', 'unit_guard_t1', 1, 'node_res_north', 'active', ?)
                """,
                (now, now, now),
            )
            connection.execute(
                """
                INSERT INTO garrison_runtime_state (
                    garrison_id, territory_id, domain_id, card_id, count, status, updated_at
                )
                VALUES
                    ('garrison_cross_target', 'territory_res_north', 'domain_north', 'unit_infantry_t1', 6, 'active', ?),
                    ('garrison_to_active_source', 'territory_res_north', 'domain_north', 'unit_ranged_t1', 5, 'active', ?)
                """,
                (now, now),
            )

        to_garrison = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "active_to_fort",
                "territory_id": "territory_res_north",
                "stack_id": "army_to_fort_source",
                "target_stack_id": "garrison_cross_target",
                "count": 4,
            },
        )
        self.assertEqual(to_garrison.status_code, 200, to_garrison.text)
        self.assertEqual(to_garrison.json()["status"], "reinforced")
        self.assertEqual(to_garrison.json()["target_stack"]["count"], 10)

        to_active = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "fort_to_active",
                "territory_id": "territory_res_north",
                "stack_id": "garrison_to_active_source",
                "target_stack_id": "army_cross_target",
                "count": 5,
            },
        )
        self.assertEqual(to_active.status_code, 200, to_active.text)
        self.assertEqual(to_active.json()["status"], "active_army_updated")
        self.assertEqual(to_active.json()["target_stack"]["count"], 8)

        mismatch = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "active_to_fort",
                "territory_id": "territory_res_north",
                "stack_id": "army_cross_guard",
                "target_stack_id": "garrison_cross_target",
                "count": 1,
            },
        )
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(mismatch.json()["detail"]["code"], "merge_unit_mismatch")

        with connect(settings) as connection:
            rows = {
                row["id"]: (row["count"], row["status"])
                for row in connection.execute(
                    """
                    SELECT army_id AS id, count, status
                    FROM active_army_runtime
                    WHERE army_id IN ('army_to_fort_source', 'army_cross_target')
                    UNION ALL
                    SELECT garrison_id AS id, count, status
                    FROM garrison_runtime_state
                    WHERE garrison_id IN ('garrison_cross_target', 'garrison_to_active_source')
                    """
                ).fetchall()
            }
        self.assertEqual(rows["army_to_fort_source"], (0, "empty"))
        self.assertEqual(rows["garrison_cross_target"], (10, "active"))
        self.assertEqual(rows["garrison_to_active_source"], (0, "empty"))
        self.assertEqual(rows["army_cross_target"], (8, "active"))

    def test_stack_split_and_transfer_reject_capacity_and_unsplittable_sources(self) -> None:
        settings = self._settings("lord_stack_capacity_guards")
        self._import_seed(settings)
        client = TestClient(create_app(settings))
        now = "2026-01-01T00:00:00+00:00"

        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count, location_node_id, status, updated_at
                )
                VALUES (
                    'army_north_singleton',
                    'domain_north',
                    'unit_guard_t1',
                    1,
                    'node_res_north',
                    'active',
                    ?
                )
                """,
                (now,),
            )
        singleton_split = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "split_active",
                "territory_id": "territory_res_north",
                "stack_id": "army_north_singleton",
                "count": 1,
            },
        )
        self.assertEqual(singleton_split.status_code, 400)
        self.assertEqual(singleton_split.json()["detail"]["code"], "stack_cannot_split")

        with connect(settings) as connection:
            connection.execute(
                "DELETE FROM active_army_runtime WHERE domain_id = 'domain_north'"
            )
            connection.execute(
                "DELETE FROM garrison_runtime_state WHERE territory_id = 'territory_res_north'"
            )
            for index in range(7):
                connection.execute(
                    """
                    INSERT INTO garrison_runtime_state (
                        garrison_id, territory_id, domain_id, card_id, count, status, updated_at
                    )
                    VALUES (?, 'territory_res_north', 'domain_north', ?, ?, 'active', ?)
                    """,
                    (
                        f"garrison_capacity_{index}",
                        "unit_infantry_t1" if index == 0 else "unit_guard_t1",
                        8 if index == 0 else 1,
                        now,
                    ),
                )
        full_garrison_split = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "split_garrison",
                "territory_id": "territory_res_north",
                "stack_id": "garrison_capacity_0",
                "count": 3,
            },
        )
        self.assertEqual(full_garrison_split.status_code, 400)
        self.assertEqual(
            full_garrison_split.json()["detail"]["code"],
            "fort_capacity_exceeded",
        )

        with connect(settings) as connection:
            connection.execute(
                "DELETE FROM active_army_runtime WHERE domain_id = 'domain_north'"
            )
            connection.execute(
                "DELETE FROM garrison_runtime_state WHERE territory_id = 'territory_res_north'"
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET active_army_capacity = 5
                WHERE domain_id = 'domain_north'
                """
            )
            for index in range(5):
                connection.execute(
                    """
                    INSERT INTO active_army_runtime (
                        army_id, domain_id, card_id, count, location_node_id, status, updated_at
                    )
                    VALUES (?, 'domain_north', ?, 1, 'node_res_north', 'active', ?)
                    """,
                    (
                        f"army_capacity_{index}",
                        "unit_infantry_t1" if index == 0 else "unit_guard_t1",
                        now,
                    ),
                )
            connection.execute(
                """
                INSERT INTO garrison_runtime_state (
                    garrison_id, territory_id, domain_id, card_id, count, status, updated_at
                )
                VALUES (
                    'garrison_transfer_blocked',
                    'territory_res_north',
                    'domain_north',
                    'unit_ranged_t1',
                    14,
                    'active',
                    ?
                )
                """,
                (now,),
            )
        full_army_transfer = client.post(
            "/api/lords/p_lord_1/garrisons/transfer",
            headers=self._headers("north"),
            json={
                "operation": "fort_to_active",
                "territory_id": "territory_res_north",
                "stack_id": "garrison_transfer_blocked",
                "count": 5,
            },
        )
        self.assertEqual(full_army_transfer.status_code, 400)
        self.assertEqual(full_army_transfer.json()["detail"]["code"], "army_capacity_exceeded")

    def test_raid_engine_and_anti_snowball_report(self) -> None:
        settings = self._settings("lord_raid")
        self._import_seed(settings)
        self._unlock_raid_rules(settings)
        client = TestClient(create_app(settings))

        raid = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_fort_east",
                "rule_id": "raid_loot_run",
                "expected_token_cost": 2,
                "expected_gold_cost": 0,
            },
        )
        self.assertEqual(raid.status_code, 200)
        payload = raid.json()
        self.assertEqual(payload["status"], "resolved")
        self.assertEqual(payload["token_spent"], 2)
        self.assertEqual(payload["gold_spent"], 0)
        self.assertTrue(payload["started"])
        self.assertTrue(payload["resisted"])
        self.assertEqual(payload["resistance_outcome"], "weakened")
        self.assertEqual(payload["effect_multiplier"], 50)
        self.assertEqual(payload["loot_formula"]["policy"], "static_plus_percent_current_gold")
        self.assertEqual(payload["loot_formula"]["territory_tier"], 2)
        self.assertEqual(payload["loot_formula"]["static_amount"], 8)
        self.assertEqual(payload["loot_formula"]["percent_current_gold"], 10)
        self.assertEqual(payload["loot_formula"]["resistance_multiplier_percent"], 50)
        self.assertEqual(payload["loot_gold"], payload["loot_formula"]["loot_gold"])
        self.assertTrue(payload["loot_applied"])
        self.assertEqual(payload["raid_tokens"], 1)
        self.assertEqual(payload["gold"], 500 + payload["loot_gold"])
        self.assertEqual(payload["active_raid_effects"][0]["rule_id"], "raid_loot_run")
        self.assertIsNotNone(payload["audit_event_id"])
        self.assertIsNotNone(payload["expires_at"])

        duplicate = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_fort_east",
                "rule_id": "raid_loot_run",
                "expected_token_cost": 2,
                "expected_gold_cost": 0,
            },
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["detail"]["code"], "insufficient_raid_tokens")

        stale_cost = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_fort_east",
                "rule_id": "raid_income_sabotage",
                "expected_token_cost": 9,
                "expected_gold_cost": 9,
            },
        )
        self.assertEqual(stale_cost.status_code, 409)
        self.assertEqual(stale_cost.json()["detail"]["code"], "stale_expected_cost")

        with connect(settings) as connection:
            connection.execute(
                "UPDATE domain_runtime_state SET raid_tokens = 4 WHERE domain_id = 'domain_north'"
            )
        expiring_raid = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_fort_east",
                "rule_id": "raid_income_sabotage",
                "expected_token_cost": 1,
                "expected_gold_cost": 0,
            },
        )
        self.assertEqual(expiring_raid.status_code, 200)
        self.assertEqual(expiring_raid.json()["status"], "active")
        residence_raid = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_res_river",
                "rule_id": "raid_residence_mark",
                "expected_token_cost": 2,
                "expected_gold_cost": 0,
            },
        )
        self.assertEqual(residence_raid.status_code, 200)
        self.assertEqual(residence_raid.json()["status"], "active")
        self.assertTrue(residence_raid.json()["resisted"])
        self.assertFalse(residence_raid.json()["loot_applied"])

        expired_at = datetime.now(UTC) - timedelta(minutes=1)
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE raid_effects
                SET expires_at = ?
                WHERE raid_effect_id = ?
                """,
                (
                    expired_at.isoformat(timespec="seconds"),
                    expiring_raid.json()["raid_effect_id"],
                ),
            )
        expired_state = client.get(
            "/api/lords/p_lord_1/state",
            headers=self._headers("north"),
        )
        self.assertEqual(expired_state.status_code, 200)
        expired_raid = next(
            raid
            for raid in expired_state.json()["raid_effects"]
            if raid["raid_effect_id"] == expiring_raid.json()["raid_effect_id"]
        )
        self.assertEqual(expired_raid["status"], "expired")
        self.assertTrue(expired_state.json()["raid_rules"])
        self.assertTrue(expired_state.json()["raid_targets"])
        self.assertTrue(expired_state.json()["raid_history"])
        self.assertEqual(expired_state.json()["active_raid_effects"][0]["rule_id"], "raid_residence_mark")
        self.assertEqual(expired_state.json()["summary"]["active_raids"], 1)

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

    def test_raid_income_debuff_affects_timer_and_refills_tokens(self) -> None:
        settings = self._settings("lord_raid_income_effect")
        self._import_seed(settings)
        self._unlock_raid_rules(settings)
        client = TestClient(create_app(settings))

        raid = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_fort_east",
                "rule_id": "raid_income_sabotage",
                "expected_token_cost": 1,
                "expected_gold_cost": 0,
            },
        )
        self.assertEqual(raid.status_code, 200, raid.text)
        self.assertEqual(raid.json()["status"], "active")
        self.assertEqual(raid.json()["raid_tokens"], 2)

        tick = client.post(
            "/api/master/timers/lord-income-tick",
            headers=self._master_headers(),
            json={"operator": "gm_test", "source": "raid_income_test"},
        )
        self.assertEqual(tick.status_code, 200, tick.text)
        applied = tick.json()["applied_now"][0]
        river_update = next(
            item for item in applied["domain_updates"] if item["domain_id"] == "domain_river"
        )
        self.assertEqual(river_update["territory_income"], 15)
        self.assertEqual(river_update["raw_income"], 15)
        north_refill = next(
            item for item in applied["raid_token_refill"] if item["domain_id"] == "domain_north"
        )
        self.assertEqual(north_refill["before"], 2)
        self.assertEqual(north_refill["after"], 3)
        self.assertEqual(north_refill["cap"], 4)

    def test_full_income_sabotage_zeroes_target_income_multiplier(self) -> None:
        settings = self._settings("lord_raid_income_full_effect")
        self._import_seed(settings)
        self._unlock_raid_rules(settings)
        client = TestClient(create_app(settings))
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                "DELETE FROM garrison_runtime_state WHERE territory_id = 'territory_well_city'"
            )
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_river',
                    status = 'controlled',
                    contested_by_domain_id = NULL
                WHERE territory_id = 'territory_well_city'
                """
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET raid_tokens = 3
                WHERE domain_id = 'domain_north'
                """
            )

        raid = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_well_city",
                "rule_id": "raid_income_sabotage",
                "expected_token_cost": 1,
                "expected_gold_cost": 0,
            },
        )
        self.assertEqual(raid.status_code, 200, raid.text)
        self.assertEqual(raid.json()["status"], "active")
        self.assertEqual(raid.json()["resistance_outcome"], "full")
        with connect(settings) as connection:
            self.assertEqual(
                raid_income_multiplier_for_territory(
                    connection, "territory_well_city"
                ),
                0,
            )

    def test_residence_raid_applies_surcharge_and_token_loss_when_weakened(self) -> None:
        settings = self._settings("lord_raid_residence_weakened")
        self._import_seed(settings)
        self._unlock_raid_rules(settings)
        self._grant_residence_buildings(settings, "domain_river", ("b_raid_office",))
        client = TestClient(create_app(settings))
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET raid_tokens = 4
                WHERE domain_id = 'domain_north'
                """
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET raid_tokens = 2, raid_token_cap = 5
                WHERE domain_id = 'domain_river'
                """
            )

        raid = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_res_river",
                "rule_id": "raid_residence_mark",
                "expected_token_cost": 2,
                "expected_gold_cost": 0,
            },
        )
        self.assertEqual(raid.status_code, 200, raid.text)
        self.assertEqual(raid.json()["status"], "active")
        self.assertEqual(raid.json()["resistance_outcome"], "weakened")
        self.assertEqual(raid.json()["target_raid_tokens_lost"], 1)
        with connect(settings) as connection:
            river = connection.execute(
                """
                SELECT raid_tokens
                FROM domain_runtime_state
                WHERE domain_id = 'domain_river'
                """
            ).fetchone()
            self.assertEqual(river["raid_tokens"], 1)
            self.assertEqual(raid_token_surcharge_for_domain(connection, "domain_river"), 1)

    def test_building_effects_drive_income_stock_raids_and_ritual_cleanse(self) -> None:
        settings = self._settings("lord_building_effects")
        self._import_seed(settings)
        self._unlock_raid_rules(settings)
        self._grant_residence_buildings(
            settings,
            "domain_north",
            (
                "b_training_yard",
                "b_market",
                "b_tax_office",
                "b_storehouse",
                "b_bank",
                "b_treasury_hall",
            ),
        )
        self._grant_residence_buildings(
            settings,
            "domain_river",
            ("b_bank", "b_mage_study", "b_alchemy_lab", "b_ritual_chamber"),
        )
        client = TestClient(create_app(settings))
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_north', status = 'controlled'
                WHERE territory_id IN ('territory_field_oats', 'territory_well_city')
                """
            )
            connection.execute(
                """
                UPDATE army_reserve_runtime
                SET count = 299,
                    updated_at = '2026-01-01T00:00:00+00:00'
                WHERE reserve_id = 'reserve_north_infantry'
                """
            )
            connection.execute(
                """
                UPDATE anti_snowball_rules
                SET army_power_ratio_threshold = 0,
                    income_cut_percent = 80
                WHERE rule_id = 'anti_snowball_soft'
                """
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET gold = 0
                WHERE domain_id = 'domain_north'
                """
            )

        tick = client.post(
            "/api/master/timers/lord-income-tick",
            headers=self._master_headers(),
            json={"operator": "gm_test", "source": "building_effects_test"},
        )
        self.assertEqual(tick.status_code, 200, tick.text)
        applied = tick.json()["applied_now"][0]
        north_update = next(
            item for item in applied["domain_updates"] if item["domain_id"] == "domain_north"
        )
        self.assertEqual(north_update["flat_building_income"], 48)
        self.assertEqual(north_update["territory_income_bonus_percent"], 50)
        self.assertEqual(north_update["territory_income_before_penalties"], 58)
        self.assertEqual(north_update["raw_income"], 106)
        self.assertEqual(north_update["treasury_income_floor"], 53)
        self.assertEqual(north_update["income"], 53)
        infantry_growth = next(
            item for item in applied["recruit_growth"] if item["card_id"] == "unit_infantry_t1"
        )
        self.assertEqual(infantry_growth["cap"], 96)
        self.assertEqual(infantry_growth["after"], 96)
        river_ritual = next(
            item for item in applied["ritual_cleanse_refill"] if item["domain_id"] == "domain_river"
        )
        self.assertEqual(river_ritual["after"], 1)

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET raid_tokens = 5, raid_token_cap = 5
                WHERE domain_id = 'domain_north'
                """
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET gold = 500
                WHERE domain_id = 'domain_river'
                """
            )

        loot = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={"target_territory_id": "territory_fort_east", "rule_id": "raid_loot_run"},
        )
        self.assertEqual(loot.status_code, 200, loot.text)
        loot_payload = loot.json()
        self.assertEqual(loot_payload["loot_gold"], 14)
        self.assertEqual(loot_payload["loot_formula"]["target_current_gold"], 500)
        self.assertEqual(loot_payload["loot_formula"]["percent_amount"], 50)
        self.assertEqual(loot_payload["loot_formula"]["after_resistance"], 29)
        self.assertEqual(loot_payload["loot_formula"]["bank_reduction_percent"], 50)
        self.assertEqual(loot_payload["loot_formula"]["after_bank"], 14)
        self.assertFalse(loot_payload["loot_formula"]["capped_by_target_gold"])

        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET raid_tokens = 5, raid_token_cap = 5
                WHERE domain_id = 'domain_north'
                """
            )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET gold = 1
                WHERE domain_id = 'domain_river'
                """
            )
        capped_loot = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={"target_territory_id": "territory_fort_east", "rule_id": "raid_loot_run"},
        )
        self.assertEqual(capped_loot.status_code, 200, capped_loot.text)
        capped_payload = capped_loot.json()
        self.assertEqual(capped_payload["loot_gold"], 1)
        self.assertTrue(capped_payload["loot_formula"]["capped_by_target_gold"])
        self.assertEqual(capped_payload["loot_formula"]["target_current_gold"], 1)

        sabotage = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_fort_east",
                "rule_id": "raid_income_sabotage",
            },
        )
        self.assertEqual(sabotage.status_code, 200, sabotage.text)
        self.assertEqual(sabotage.json()["status"], "active")
        self.assertEqual(sabotage.json()["duration_min"], 1)
        self.assertEqual(sabotage.json()["alchemy_duration_reduction"], 14)

        cleanse = client.post(
            "/api/lords/p_lord_2/raids/cleanse",
            headers=self._headers("river"),
            json={"raid_effect_id": sabotage.json()["raid_effect_id"]},
        )
        self.assertEqual(cleanse.status_code, 200, cleanse.text)
        self.assertEqual(cleanse.json()["status"], "cleansed")
        self.assertEqual(cleanse.json()["ritual_cleanse_charges"], 0)
        with connect(settings) as connection:
            status = connection.execute(
                "SELECT status FROM raid_effects WHERE raid_effect_id = ?",
                (sabotage.json()["raid_effect_id"],),
            ).fetchone()["status"]
        self.assertEqual(status, "cleansed")

        self._grant_residence_buildings(settings, "domain_river", ("b_wards",))
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET raid_tokens = 4
                WHERE domain_id = 'domain_north'
                """
            )
        residence_raid = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_res_river",
                "rule_id": "raid_residence_mark",
            },
        )
        self.assertEqual(residence_raid.status_code, 200, residence_raid.text)
        self.assertTrue(residence_raid.json()["blocked"])
        self.assertEqual(residence_raid.json()["status"], "blocked")

    def test_order_caps_object_conflict_success_race_and_escrow_release(self) -> None:
        settings = self._settings("lord_orders")
        self._import_seed(settings)
        self._grant_residence_buildings(settings, "domain_north", ("b_notice_board",))
        self._grant_residence_buildings(settings, "domain_forest", ("b_notice_board",))
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
        self.assertIn(first_id, {order["order_id"] for order in first.json()["orders"]})

        third_public = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={
                "action": "create",
                "object_id": "territory_magic_corner",
                "visibility": "public",
                "target_player_id": "p_witcher_4",
                "escrow_reward_id": "reward_order_success",
            },
        )
        self.assertEqual(third_public.status_code, 400)
        self.assertEqual(third_public.json()["detail"]["code"], "order_cap_exceeded")

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

        started = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={"action": "start", "order_id": first_id},
        )
        self.assertEqual(started.status_code, 200)
        cancel_started = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={
                "action": "cancel",
                "order_id": first_id,
                "reason": "too late to withdraw",
            },
        )
        self.assertEqual(cancel_started.status_code, 409)
        self.assertEqual(cancel_started.json()["detail"]["code"], "order_already_in_progress")

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

    def test_order_creation_requires_notice_board_and_envoy_hall(self) -> None:
        settings = self._settings("lord_order_building_gates")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        public_locked = client.post(
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
        self.assertEqual(public_locked.status_code, 400)
        self.assertEqual(public_locked.json()["detail"]["code"], "public_orders_locked")

        addressed_locked = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={
                "action": "create",
                "object_id": "territory_well_city",
                "visibility": "addressed",
                "target_player_id": "p_witcher_2",
                "escrow_reward_id": "reward_order_success",
            },
        )
        self.assertEqual(addressed_locked.status_code, 400)
        self.assertEqual(
            addressed_locked.json()["detail"]["code"],
            "addressed_orders_locked",
        )

        self._grant_residence_buildings(settings, "domain_forest", ("b_notice_board",))
        public_created = client.post(
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
        self.assertEqual(public_created.status_code, 200, public_created.text)
        self.assertEqual(public_created.json()["order_cap"]["public_limit"], 2)

        self._grant_residence_buildings(settings, "domain_forest", ("b_envoy_hall",))
        addressed_created = client.post(
            "/api/lords/p_lord_3/orders",
            headers=self._headers("forest"),
            json={
                "action": "create",
                "object_id": "territory_magic_corner",
                "visibility": "addressed",
                "target_player_id": "p_witcher_3",
                "escrow_reward_id": "reward_order_success",
            },
        )
        self.assertEqual(addressed_created.status_code, 200, addressed_created.text)
        self.assertEqual(addressed_created.json()["order_cap"]["addressed_limit"], 1)

    def test_cross_lord_order_race_closes_competitors_and_refunds_escrow(self) -> None:
        settings = self._settings("lord_cross_lord_orders")
        self._import_seed(settings)
        self._grant_residence_buildings(settings, "domain_forest", ("b_notice_board",))
        self._grant_residence_buildings(
            settings,
            "domain_hill",
            ("b_notice_board", "b_envoy_hall"),
        )
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
        preview = client.post(
            "/api/lords/p_lord_1/route-preview",
            headers=self._headers("north"),
            json={"to_node_id": "node_well_city"},
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["status"], "stopped")
        self.assertEqual(preview.json()["reason_code"], "route_stopped_at_front")
        self.assertEqual(preview.json()["requested_to_node_id"], "node_well_city")
        self.assertEqual(preview.json()["to_node_id"], "node_fort_east")
        self.assertEqual(preview.json()["route"], ["node_res_north", "node_fort_east"])
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
        self.assertEqual(moved.json()["requested_to_node_id"], "node_well_city")
        self.assertEqual(moved.json()["to_node_id"], "node_fort_east")
        self.assertEqual(moved.json()["mp_spent"], 2)
        self.assertEqual(moved.json()["current_mp"], 4)
        self.assertEqual(
            moved.json()["route"],
            ["node_res_north", "node_fort_east"],
        )
        self._complete_pending_moves(settings)
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET current_mp = 1
                WHERE domain_id = 'domain_north'
                """
            )

        too_expensive = client.post(
            "/api/lords/p_lord_1/move",
            headers=self._headers("north"),
            json={
                "to_node_id": "node_well_city",
                "route_node_ids": [
                    "node_fort_east",
                    "node_well_city",
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
        self._unlock_raid_rules(settings)
        self._grant_residence_buildings(
            settings,
            "domain_hill",
            ("b_notice_board", "b_envoy_hall"),
        )
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
        self.assertEqual(neutral_raid.json()["detail"]["code"], "invalid_target")
        self.assertEqual(own_raid.status_code, 400)
        self.assertEqual(own_raid.json()["detail"]["code"], "invalid_target")

        with connect(settings) as connection:
            connection.execute(
                "UPDATE domain_runtime_state SET raid_tokens = 0, gold = 80 WHERE domain_id = 'domain_north'"
            )
        no_raid_token = client.post(
            "/api/lords/p_lord_1/raids",
            headers=self._headers("north"),
            json={
                "target_territory_id": "territory_fort_east",
                "rule_id": "raid_income_sabotage",
            },
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
            json={
                "target_territory_id": "territory_fort_east",
                "rule_id": "raid_income_sabotage",
                "expected_gold_cost": 0,
            },
        )
        self.assertEqual(no_raid_gold.status_code, 200)
        self.assertEqual(no_raid_gold.json()["gold_spent"], 0)

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

        sorceress_addressed_target = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={
                "action": "create",
                "object_id": "territory_magic_corner",
                "visibility": "addressed",
                "target_player_id": "p_sorc_1",
                "escrow_reward_id": "reward_order_success",
            },
        )
        self.assertEqual(sorceress_addressed_target.status_code, 400)
        self.assertEqual(
            sorceress_addressed_target.json()["detail"]["code"],
            "invalid_addressed_target",
        )

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
                "visible_hook": "Najti sled u zerkalnogo pruda",
                "reward": {"reward_id": "reward_order_success"},
            },
        )
        self.assertEqual(public_order.status_code, 200, public_order.text)
        self.assertEqual(public_order.json()["order_cap"]["public_active"], 1)
        self.assertEqual(public_order.json()["order_cap"]["public_limit"], 2)
        self.assertEqual(public_order.json()["escrow"]["locked_gold"], 15)
        self.assertTrue(
            any(
                order["order_id"] == public_order.json()["order"]["order_id"]
                for order in public_order.json()["orders"]
            )
        )
        self.assertEqual(
            public_order.json()["order"]["visible_hook"],
            "Najti sled u zerkalnogo pruda",
        )
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

        cancelled = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={
                "action": "cancel",
                "order_id": order_id,
                "reason": "lord changed the contract",
            },
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["status"], "cancelled_by_lord")
        self.assertEqual(cancelled.json()["order_cap"]["public_active"], 0)
        self.assertEqual(cancelled.json()["escrow"]["locked_gold"], 0)
        self.assertEqual(
            next(
                order for order in cancelled.json()["orders"] if order["order_id"] == order_id
            )["status"],
            "cancelled_by_lord",
        )

        recreated = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={
                "action": "create",
                "object_id": "territory_lake_mist",
                "visibility": "public",
                "reward": {"reward_id": "reward_order_success"},
            },
        )
        self.assertEqual(recreated.status_code, 200, recreated.text)
        self.assertEqual(recreated.json()["order_cap"]["public_active"], 1)

        card_object_order = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={
                "action": "create",
                "object_id": "pc_infantry_t1",
                "visibility": "public",
                "visible_hook": "Вернуть лорду карту: Infantry Favor",
                "reward": {"gold": 23},
            },
        )
        self.assertEqual(card_object_order.status_code, 200, card_object_order.text)
        self.assertEqual(card_object_order.json()["order"]["object_id"], "pc_infantry_t1")
        self.assertEqual(card_object_order.json()["order_cap"]["public_active"], 2)
        self.assertEqual(card_object_order.json()["escrow"]["locked_gold"], 38)
        self.assertEqual(card_object_order.json()["order"]["escrow_reward_id"], "order_gold_23")

        invalid_addressed_target = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={
                "action": "create",
                "object_id": "territory_magic_corner",
                "visibility": "addressed",
                "target_player_id": "p_lord_1",
                "reward": {"reward_id": "reward_order_success"},
            },
        )
        self.assertEqual(invalid_addressed_target.status_code, 400)
        self.assertEqual(
            invalid_addressed_target.json()["detail"]["code"],
            "invalid_addressed_target",
        )

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
            headers=self._master_headers(),
        ).json()
        board = battle["board"]
        deployment = battle["deployment"]
        for side, lord in (("attacker", attacker_lord), ("defender", defender_lord)):
            if side == "defender" and battle["battle_type"] == "neutral":
                continue
            for index, item in enumerate(deployment["hand"][side][: int(deployment["deployment_cap"])]):
                x, y = self._deployment_cell(board, side, index)
                deployed = client.post(
                    f"/api/lord-battles/{battle_id}/actions",
                    headers=self._headers(lord),
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
                headers=self._headers(lord),
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

    def _set_reserve_count(self, settings: Settings, reserve_id: str, count: int) -> None:
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            connection.execute(
                "UPDATE army_reserve_runtime SET count = ? WHERE reserve_id = ?",
                (count, reserve_id),
            )

    def _unlock_raid_rules(self, settings: Settings) -> None:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            for building_id in (
                "b_raid_office",
                "b_war_council",
                "b_scrying_room",
            ):
                connection.execute(
                    """
                    INSERT INTO domain_buildings (
                        domain_id, territory_id, building_id, purchased_at, source
                    )
                    VALUES ('domain_north', 'territory_res_north', ?, ?, 'test')
                    ON CONFLICT(domain_id, territory_id, building_id) DO NOTHING
                    """,
                    (building_id, now),
                )
            connection.execute(
                """
                UPDATE domain_runtime_state
                SET raid_tokens = 3, gold = 500
                WHERE domain_id = 'domain_north'
                """
            )
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_river', status = 'controlled', updated_at = ?
                WHERE territory_id = 'territory_fort_east'
                """,
                (now,),
            )

    def _grant_residence_buildings(
        self,
        settings: Settings,
        domain_id: str,
        building_ids: tuple[str, ...],
    ) -> None:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with connect(settings) as connection:
            ensure_lord_runtime_state(connection)
            row = connection.execute(
                """
                SELECT territory_id
                FROM territories
                WHERE owner_domain_id = ? AND bonus_type = 'residence'
                ORDER BY _row_number
                LIMIT 1
                """,
                (domain_id,),
            ).fetchone()
            self.assertIsNotNone(row)
            for building_id in building_ids:
                connection.execute(
                    """
                    INSERT INTO domain_buildings (
                        domain_id, territory_id, building_id, purchased_at, source
                    )
                    VALUES (?, ?, ?, ?, 'test')
                    ON CONFLICT(domain_id, territory_id, building_id) DO NOTHING
                    """,
                    (domain_id, row["territory_id"], building_id, now),
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
