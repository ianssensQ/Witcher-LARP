from __future__ import annotations

import sqlite3
import unittest
from uuid import uuid4

from backend.witcher_larp.config import Settings
from backend.witcher_larp.config import PROJECT_ROOT
from backend.witcher_larp.database import connect, healthcheck_database, init_database


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"


class DatabaseRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def make_settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def test_init_database_creates_schema_and_health_status(self) -> None:
        settings = self.make_settings("schema")

        health = init_database(settings)

        self.assertEqual(health.status, "ok")
        self.assertEqual(health.schema_version, 1)
        self.assertTrue(settings.database_path.exists())

        with connect(settings) as connection:
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

        self.assertIn("schema_version", tables)
        self.assertIn("event_log", tables)
        self.assertIn("events", tables)
        self.assertIn("event_reviews", tables)
        self.assertIn("master_corrections", tables)

    def test_init_database_is_idempotent(self) -> None:
        settings = self.make_settings("idempotent")

        first = init_database(settings)
        second = init_database(settings)

        self.assertEqual(first.as_dict(), second.as_dict())

    def test_connect_rolls_back_failed_transaction(self) -> None:
        settings = self.make_settings("rollback")
        init_database(settings)

        with self.assertRaises(sqlite3.IntegrityError):
            with connect(settings) as connection:
                connection.execute(
                    "INSERT INTO event_log (event_type, payload_json) VALUES (?, ?)",
                    ("test_event", "{}"),
                )
                connection.execute(
                    "INSERT INTO schema_version (id, version) VALUES (1, 999)"
                )

        with connect(settings) as connection:
            count = connection.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]

        self.assertEqual(count, 0)

    def test_healthcheck_reports_missing_schema_before_init(self) -> None:
        settings = self.make_settings("missing")

        health = healthcheck_database(settings)

        self.assertEqual(health.status, "missing_schema")
        self.assertEqual(health.schema_version, 0)


if __name__ == "__main__":
    unittest.main()
