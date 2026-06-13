from __future__ import annotations

from uuid import uuid4
import unittest

from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.material_market_service import (
    apply_material_drop_for_pve,
    ensure_material_market_runtime_state,
    material_market_rows,
    sell_material_to_market,
)


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"


class MaterialMarketServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def make_settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def import_seed(self, name: str) -> Settings:
        settings = self.make_settings(name)
        report = import_seed_pack(settings, snapshot_dir=None)
        self.assertEqual(report.status, "success", report.errors)
        return settings

    def test_material_price_falls_when_player_stock_is_abundant(self) -> None:
        settings = self.import_seed("material_price")
        with connect(settings) as connection:
            ensure_material_market_runtime_state(connection)
            empty_market = self.market_by_material(connection, "mat_herbs")
            self.assertEqual(empty_market["current_price"], empty_market["max_price"])

            connection.execute(
                """
                INSERT INTO material_inventory (
                    inventory_id, player_id, material_id, quantity, updated_at
                )
                VALUES ('test_herbs_stock', 'p_witcher_1', 'mat_herbs', 40, CURRENT_TIMESTAMP)
                """
            )
            abundant_market = self.market_by_material(connection, "mat_herbs")

        self.assertLess(abundant_market["current_price"], empty_market["base_price"])
        self.assertEqual(abundant_market["current_price"], abundant_market["min_price"])

    def test_sell_material_debits_inventory_and_credits_gold(self) -> None:
        settings = self.import_seed("material_sell")
        with connect(settings) as connection:
            ensure_material_market_runtime_state(connection)
            connection.execute(
                """
                INSERT INTO material_inventory (
                    inventory_id, player_id, material_id, quantity, updated_at
                )
                VALUES ('test_silver_stock', 'p_witcher_1', 'mat_silver_dust', 5, CURRENT_TIMESTAMP)
                """
            )
            player_before = connection.execute(
                "SELECT gold FROM players WHERE player_id = 'p_witcher_1'"
            ).fetchone()
            sale = sell_material_to_market(
                connection,
                player_id="p_witcher_1",
                material_id="mat_silver_dust",
                quantity=2,
                sale_id="test_sale_silver",
                source="test",
            )
            inventory_after = connection.execute(
                """
                SELECT quantity
                FROM material_inventory
                WHERE player_id = 'p_witcher_1' AND material_id = 'mat_silver_dust'
                """
            ).fetchone()
            runtime_after = connection.execute(
                "SELECT gold FROM player_runtime_state WHERE player_id = 'p_witcher_1'"
            ).fetchone()

        self.assertEqual(sale["quantity"], 2)
        self.assertEqual(sale["total_gold"], sale["unit_price"] * 2)
        self.assertEqual(inventory_after["quantity"], 3)
        self.assertEqual(runtime_after["gold"], int(player_before["gold"]) + sale["total_gold"])

    def test_pve_material_drop_is_idempotent_per_source_event(self) -> None:
        settings = self.import_seed("material_drop")
        with connect(settings) as connection:
            scenario = connection.execute(
                """
                SELECT scenario_id
                FROM pve_scenarios
                ORDER BY _row_number
                LIMIT 1
                """
            ).fetchone()
            first = apply_material_drop_for_pve(
                connection,
                player_id="p_witcher_1",
                scenario_id=scenario["scenario_id"],
                result="success",
                source_event_id=12345,
            )
            duplicate = apply_material_drop_for_pve(
                connection,
                player_id="p_witcher_1",
                scenario_id=scenario["scenario_id"],
                result="success",
                source_event_id=12345,
            )
            drop_count = connection.execute(
                "SELECT COUNT(*) AS count FROM material_drop_log WHERE source_event_id = 12345"
            ).fetchone()["count"]

        self.assertEqual(first["status"], "applied")
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(drop_count, 1)

    def market_by_material(self, connection, material_id: str) -> dict[str, object]:
        return next(row for row in material_market_rows(connection) if row["material_id"] == material_id)
