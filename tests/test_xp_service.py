from __future__ import annotations

from contextlib import closing
import sqlite3
import unittest

from backend.witcher_larp.xp_service import next_level_cost, spend_xp_for_levels


class XpServiceTests(unittest.TestCase):
    def test_spends_level_costs_and_keeps_remaining_current_level_xp(self) -> None:
        with closing(self._connection("0;10;25;45;70")) as connection:
            xp_after, level_after = spend_xp_for_levels(
                connection,
                level_before=1,
                xp_available=50,
            )

        self.assertEqual(level_after, 3)
        self.assertEqual(xp_after, 15)

    def test_next_level_cost_uses_current_level_when_rule_starts_with_zero(self) -> None:
        self.assertEqual(next_level_cost([0, 10, 25, 45], 1), 10)
        self.assertEqual(next_level_cost([0, 10, 25, 45], 3), 45)

    def test_does_not_level_up_until_current_bucket_is_full(self) -> None:
        with closing(self._connection("0;10;25;45;70")) as connection:
            xp_after, level_after = spend_xp_for_levels(
                connection,
                level_before=2,
                xp_available=24,
            )

        self.assertEqual(level_after, 2)
        self.assertEqual(xp_after, 24)

    def _connection(self, level_thresholds: str) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            CREATE TABLE xp_rules (
                _row_number INTEGER NOT NULL,
                level_thresholds TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO xp_rules (_row_number, level_thresholds) VALUES (1, ?)",
            (level_thresholds,),
        )
        return connection


if __name__ == "__main__":
    unittest.main()
