from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.app import create_app
from backend.witcher_larp.backup_service import run_backup
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.runtime_schema import log_event
from backend.witcher_larp.timer_service import apply_due_timers

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"
MASTER_HEADERS = {"X-Role-Token": "MASTER-KING-4QZ8"}


class ActTimerRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def make_settings(self, name: str) -> Settings:
        suffix = uuid4().hex
        return Settings(
            database_path=TEST_TMP_ROOT / f"{name}_{suffix}.db",
            backup_dir=TEST_TMP_ROOT / f"{name}_backups_{suffix}",
        )

    def import_seed(self, settings: Settings) -> None:
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_start_act_unlock_gating_and_manual_backup(self) -> None:
        settings = self.make_settings("api_act")
        self.import_seed(settings)
        client = TestClient(create_app(settings))

        hidden = client.get("/api/master/acts/act2/unlock-code", headers=MASTER_HEADERS)
        self.assertEqual(hidden.status_code, 403)

        start = client.post(
            "/api/master/acts/act2/start",
            headers=MASTER_HEADERS,
            json={
                "operator": "gm_king",
                "physical_announcement_state": "pending",
            },
        )
        self.assertEqual(start.status_code, 200)
        payload = start.json()
        self.assertEqual(payload["state"]["current_act_id"], "act2")
        self.assertEqual(payload["start_effects"]["challenge_tokens"]["tokens_per_player"], 3)
        self.assertFalse(payload["unlock_code"]["available"])
        self.assertIsNone(payload["unlock_code"]["code"])

        still_hidden = client.get("/api/master/acts/act2/unlock-code", headers=MASTER_HEADERS)
        self.assertEqual(still_hidden.status_code, 403)

        announcement = client.post(
            "/api/master/acts/act2/physical-announcement",
            headers=MASTER_HEADERS,
            json={"operator": "gm_king", "state": "announced"},
        )
        self.assertEqual(announcement.status_code, 200)
        self.assertTrue(announcement.json()["available"])

        revealed = client.get(
            "/api/master/acts/act2/unlock-code",
            headers=MASTER_HEADERS,
            params={"operator": "gm_king"},
        )
        self.assertEqual(revealed.status_code, 200)
        self.assertEqual(revealed.json()["code"], "UNLOCK-A2-7GQ4")

        backup = client.post(
            "/api/backups/run",
            headers=MASTER_HEADERS,
            json={"operator": "gm_king"},
        )
        self.assertEqual(backup.status_code, 200)
        backup_payload = backup.json()
        self.assertEqual(backup_payload["status"], "success")
        self.assertTrue(Path(backup_payload["artifact_path"]).exists())

    def test_due_timers_apply_income_mana_tokens_and_are_idempotent_after_restart(self) -> None:
        settings = self.make_settings("timers")
        self.import_seed(settings)
        started_at = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)

        with connect(settings) as connection:
            start_act(
                connection,
                settings,
                "act1",
                operator="gm_timer",
                physical_announcement_state="announced",
                now=started_at,
            )

        first_due = started_at + timedelta(minutes=31)
        with connect(settings) as connection:
            applied = apply_due_timers(connection, settings, now=first_due)
            self.assertEqual([tick["effect_type"] for tick in applied], ["lord_income_and_mana"])
            north = connection.execute(
                "SELECT gold, current_mp, influence FROM domain_runtime_state WHERE domain_id = 'domain_north'"
            ).fetchone()
            sorceress = connection.execute(
                "SELECT mana, max_mana FROM player_runtime_state WHERE player_id = 'p_sorc_1'"
            ).fetchone()
            witcher = connection.execute(
                "SELECT challenge_tokens FROM player_runtime_state WHERE player_id = 'p_witcher_1'"
            ).fetchone()
            lord = connection.execute(
                "SELECT challenge_tokens FROM player_runtime_state WHERE player_id = 'p_lord_1'"
            ).fetchone()
            window_count = connection.execute(
                "SELECT COUNT(*) FROM army_windows WHERE act_id = 'act1' AND status = 'open'"
            ).fetchone()[0]

        self.assertEqual(dict(north), {"gold": 105, "current_mp": 6, "influence": 4})
        self.assertEqual(dict(sorceress), {"mana": 2, "max_mana": 7})
        self.assertEqual(witcher["challenge_tokens"], 3)
        self.assertEqual(lord["challenge_tokens"], 0)
        self.assertEqual(window_count, 4)

        with connect(settings) as restarted_connection:
            self.assertEqual(apply_due_timers(restarted_connection, settings, now=first_due), [])
            tick_count = restarted_connection.execute(
                "SELECT COUNT(*) FROM applied_timer_ticks"
            ).fetchone()[0]
        self.assertEqual(tick_count, 1)

        second_due = started_at + timedelta(minutes=91)
        with connect(settings) as connection:
            second_applied = apply_due_timers(connection, settings, now=second_due)
            self.assertEqual([tick["effect_type"] for tick in second_applied], ["lord_income_and_mana"])
            north_gold = connection.execute(
                "SELECT gold, influence FROM domain_runtime_state WHERE domain_id = 'domain_north'"
            ).fetchone()
            sorceress_mana = connection.execute(
                "SELECT mana FROM player_runtime_state WHERE player_id = 'p_sorc_1'"
            ).fetchone()["mana"]

        self.assertEqual(north_gold["gold"], 130)
        self.assertEqual(north_gold["influence"], 5)
        self.assertEqual(sorceress_mana, 4)

    def test_final_lock_and_pre_final_backup_timer(self) -> None:
        settings = self.make_settings("final_lock")
        self.import_seed(settings)
        final_lock_at = datetime(2026, 6, 2, 17, 15, tzinfo=UTC)
        final_act_at = datetime(2026, 6, 2, 17, 30, tzinfo=UTC)

        with connect(settings) as connection:
            start_act(
                connection,
                settings,
                "final_lock",
                operator="gm_final",
                physical_announcement_state="announced",
                now=final_lock_at,
            )
            locked = connection.execute("SELECT locked_at FROM final_lock_state WHERE id = 1").fetchone()
            self.assertIsNotNone(locked["locked_at"])

        with connect(settings) as connection:
            result = start_act(
                connection,
                settings,
                "final_act",
                operator="gm_final",
                physical_announcement_state="announced",
                now=final_act_at,
            )
            self.assertEqual(result["backup"]["status"], "success")
            pre_final = connection.execute(
                """
                SELECT status, artifact_path
                FROM backup_runs
                WHERE trigger_type = 'pre_final_lock'
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()

        self.assertEqual(pre_final["status"], "success")
        self.assertTrue(Path(pre_final["artifact_path"]).exists())

    def test_backup_fallback_and_missing_job_review_are_recorded(self) -> None:
        settings = self.make_settings("backup_resilience")
        self.import_seed(settings)
        backup_at = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)

        with connect(settings) as connection:
            log_event(
                connection,
                "manual_recovery_marker",
                {"operator": "gm_ops", "reason": "before_act_transition"},
                source="test_backup",
                created_at=backup_at,
            )
            fallback = run_backup(
                connection,
                settings,
                trigger_type="unexpected_transition",
                operator="gm_ops",
                source="test_backup",
                affects_transition=True,
                now=backup_at,
            )

            self.assertEqual(fallback.status, "success")
            self.assertEqual(fallback.job_id, "backup_manual")
            self.assertEqual(fallback.trigger_type, "unexpected_transition")
            self.assertFalse(fallback.needs_master_review)
            self.assertIsNotNone(fallback.artifact_path)

            manifest_path = Path(str(fallback.artifact_path))
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["backup_id"], fallback.backup_id)
            self.assertEqual(manifest["job_id"], "backup_manual")
            self.assertEqual(manifest["trigger_type"], "unexpected_transition")
            self.assertEqual(manifest["operator"], "gm_ops")
            self.assertTrue(Path(str(manifest["sqlite_path"])).exists())
            self.assertIn(
                "manual_recovery_marker",
                [event["event_type"] for event in manifest["event_log"]],
            )

            fallback_record = connection.execute(
                """
                SELECT job_id, trigger_type, status, needs_master_review,
                       artifact_path, include_sqlite, include_event_log, error
                FROM backup_runs
                WHERE backup_id = ?
                """,
                (fallback.backup_id,),
            ).fetchone()
            self.assertEqual(fallback_record["job_id"], "backup_manual")
            self.assertEqual(fallback_record["trigger_type"], "unexpected_transition")
            self.assertEqual(fallback_record["status"], "success")
            self.assertEqual(fallback_record["needs_master_review"], 0)
            self.assertEqual(fallback_record["artifact_path"], str(manifest_path))
            self.assertEqual(fallback_record["include_sqlite"], 1)
            self.assertEqual(fallback_record["include_event_log"], 1)
            self.assertIsNone(fallback_record["error"])

            connection.execute("DELETE FROM backup_jobs WHERE trigger_type = 'manual'")
            missing = run_backup(
                connection,
                settings,
                trigger_type="manual",
                operator="gm_ops",
                source="test_backup",
                affects_transition=True,
                now=backup_at + timedelta(minutes=1),
            )

            self.assertEqual(missing.status, "failed")
            self.assertEqual(missing.job_id, "missing_manual")
            self.assertTrue(missing.needs_master_review)
            self.assertIsNone(missing.artifact_path)
            self.assertIn("No backup job configured", str(missing.error))

            missing_record = connection.execute(
                """
                SELECT job_id, trigger_type, status, needs_master_review,
                       artifact_path, include_sqlite, include_event_log, error
                FROM backup_runs
                WHERE backup_id = ?
                """,
                (missing.backup_id,),
            ).fetchone()
            self.assertEqual(missing_record["job_id"], "missing_manual")
            self.assertEqual(missing_record["trigger_type"], "manual")
            self.assertEqual(missing_record["status"], "failed")
            self.assertEqual(missing_record["needs_master_review"], 1)
            self.assertIsNone(missing_record["artifact_path"])
            self.assertEqual(missing_record["include_sqlite"], 1)
            self.assertEqual(missing_record["include_event_log"], 1)
            self.assertIn("No backup job configured", missing_record["error"])

            backup_events = connection.execute(
                """
                SELECT payload_json
                FROM event_log
                WHERE event_type = 'backup_run' AND source = 'test_backup'
                ORDER BY id
                """
            ).fetchall()
            self.assertEqual(len(backup_events), 2)
            last_payload = json.loads(backup_events[-1]["payload_json"])
            self.assertEqual(last_payload["backup_id"], missing.backup_id)
            self.assertEqual(last_payload["status"], "failed")
            self.assertTrue(last_payload["needs_master_review"])


if __name__ == "__main__":
    unittest.main()
