from __future__ import annotations

import os
import sqlite3
import sys
import types
import unittest
from unittest.mock import patch
from uuid import uuid4

from backend.witcher_larp import __main__ as backend_main
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


class BackendEntrypointTests(unittest.TestCase):
    def run_main_with_env(self, env: dict[str, str]) -> dict[str, object]:
        captured: dict[str, object] = {}

        def fake_run(app_ref: str, **kwargs: object) -> None:
            captured["app_ref"] = app_ref
            captured.update(kwargs)

        fake_uvicorn = types.SimpleNamespace(run=fake_run)
        with patch.dict(sys.modules, {"uvicorn": fake_uvicorn}):
            with patch.dict(os.environ, env, clear=True):
                exit_code = backend_main.main()

        captured["exit_code"] = exit_code
        return captured

    def test_python_module_entrypoint_defaults_to_lan_production_server(self) -> None:
        captured = self.run_main_with_env({})

        self.assertEqual(captured["exit_code"], 0)
        self.assertEqual(captured["app_ref"], "backend.witcher_larp.app:create_app")
        self.assertEqual(captured["factory"], True)
        self.assertEqual(captured["host"], "0.0.0.0")
        self.assertEqual(captured["port"], 8002)

    def test_python_module_entrypoint_accepts_host_and_port_overrides(self) -> None:
        captured = self.run_main_with_env(
            {
                "WITCHER_LARP_HOST": "127.0.0.1",
                "WITCHER_LARP_PORT": "8794",
            }
        )

        self.assertEqual(captured["exit_code"], 0)
        self.assertEqual(captured["host"], "127.0.0.1")
        self.assertEqual(captured["port"], 8794)


if __name__ == "__main__":
    unittest.main()
