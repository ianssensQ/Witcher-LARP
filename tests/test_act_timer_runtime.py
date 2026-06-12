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
from backend.witcher_larp.lord_runtime import ensure_lord_runtime_state
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
            north_update = next(
                update
                for update in applied[0]["domain_updates"]
                if update["domain_id"] == "domain_north"
            )
            north_growth = next(
                growth
                for growth in applied[0]["recruit_growth"]
                if growth["domain_id"] == "domain_north"
                and growth["card_id"] == "unit_infantry_t1"
            )
            north = connection.execute(
                "SELECT gold, current_mp, influence FROM domain_runtime_state WHERE domain_id = 'domain_north'"
            ).fetchone()
            north_reserve = connection.execute(
                """
                SELECT count
                FROM army_reserve_runtime
                WHERE reserve_id = 'reserve_north_infantry'
                """
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

        self.assertEqual(north_update["territory_income"], 8)
        self.assertEqual(north_update["raw_income"], 8)
        self.assertEqual(north_growth["cap"], 48)
        self.assertEqual(
            dict(north),
            {"gold": 80 + north_update["income"], "current_mp": 6, "influence": 4},
        )
        self.assertEqual(north_growth["growth"], 24)
        self.assertEqual(north_reserve["count"], north_growth["after"])
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

        second_due = started_at + timedelta(minutes=61)
        with connect(settings) as connection:
            second_applied = apply_due_timers(connection, settings, now=second_due)
            self.assertEqual([tick["effect_type"] for tick in second_applied], ["lord_income_and_mana"])
            second_north_update = next(
                update
                for update in second_applied[0]["domain_updates"]
                if update["domain_id"] == "domain_north"
            )
            north_gold = connection.execute(
                "SELECT gold, influence FROM domain_runtime_state WHERE domain_id = 'domain_north'"
            ).fetchone()
            sorceress_mana = connection.execute(
                "SELECT mana FROM player_runtime_state WHERE player_id = 'p_sorc_1'"
            ).fetchone()["mana"]

        self.assertEqual(
            north_gold["gold"],
            80 + north_update["income"] + second_north_update["income"],
        )
        self.assertEqual(north_gold["influence"], 5)
        self.assertEqual(sorceress_mana, 4)

        third_due = started_at + timedelta(minutes=91)
        with connect(settings) as connection:
            third_applied = apply_due_timers(connection, settings, now=third_due)
            self.assertEqual([tick["effect_type"] for tick in third_applied], ["lord_income_and_mana"])
            third_north_update = next(
                update
                for update in third_applied[0]["domain_updates"]
                if update["domain_id"] == "domain_north"
            )
            third_north = connection.execute(
                """
                SELECT gold, influence
                FROM domain_runtime_state
                WHERE domain_id = 'domain_north'
                """
            ).fetchone()
            third_sorceress_mana = connection.execute(
                "SELECT mana FROM player_runtime_state WHERE player_id = 'p_sorc_1'"
            ).fetchone()["mana"]

        self.assertEqual(
            third_north["gold"],
            80
            + north_update["income"]
            + second_north_update["income"]
            + third_north_update["income"],
        )
        self.assertEqual(third_north["influence"], 6)
        self.assertEqual(third_sorceress_mana, 6)

    def test_lord_income_uses_controlled_territories_without_hidden_domain_base(self) -> None:
        settings = self.make_settings("lord_income_territories")
        self.import_seed(settings)
        started_at = datetime.now(UTC)
        with connect(settings) as connection:
            start_act(
                connection,
                settings,
                "act1",
                operator="gm_income",
                physical_announcement_state="announced",
                now=started_at,
            )
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_north',
                    status = 'controlled',
                    contested_by_domain_id = NULL
                WHERE territory_id IN ('territory_fort_east', 'territory_well_city')
                """
            )
            connection.execute(
                """
                UPDATE anti_snowball_rules
                SET army_power_ratio_threshold = 9999
                """
            )

            applied = apply_due_timers(connection, settings, now=started_at + timedelta(minutes=31))

        north_update = next(
            update
            for update in applied[0]["domain_updates"]
            if update["domain_id"] == "domain_north"
        )
        self.assertEqual(north_update["configured_base_income"], 0)
        self.assertEqual(north_update["base_income"], 0)
        self.assertEqual(north_update["territory_income"], 43)
        self.assertEqual(north_update["raw_income"], 43)
        self.assertEqual(north_update["income"], 43)

    def test_starting_registration_resets_game_to_clean_initial_state(self) -> None:
        settings = self.make_settings("registration_reset")
        self.import_seed(settings)
        act_started_at = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
        reset_at = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)

        with connect(settings) as connection:
            start_act(
                connection,
                settings,
                "act1",
                operator="gm_dirty",
                physical_announcement_state="announced",
                now=act_started_at,
            )
            ensure_lord_runtime_state(connection)
            connection.execute(
                "UPDATE domain_runtime_state SET gold = 999, current_mp = 0 WHERE domain_id = 'domain_north'"
            )
            connection.execute(
                """
                INSERT INTO domain_buildings (
                    domain_id, territory_id, building_id, purchased_at, source
                )
                VALUES ('domain_north', 'territory_res_north', 'b_training_yard', ?, 'test')
                """,
                (act_started_at.isoformat(timespec="seconds"),),
            )
            connection.execute(
                """
                INSERT INTO army_reserve_runtime (
                    reserve_id, domain_id, card_id, count, status, updated_at
                )
                VALUES ('reserve_dirty', 'domain_north', 'unit_infantry_t1', 9, 'available', ?)
                """,
                (act_started_at.isoformat(timespec="seconds"),),
            )
            connection.execute(
                """
                INSERT INTO active_army_runtime (
                    army_id, domain_id, card_id, count, location_node_id, status, updated_at
                )
                VALUES ('army_dirty', 'domain_north', 'unit_infantry_t1', 3, 'node_res_north', 'active', ?)
                """,
                (act_started_at.isoformat(timespec="seconds"),),
            )
            connection.execute(
                """
                INSERT INTO garrison_runtime_state (
                    garrison_id, territory_id, domain_id, card_id, count, status, updated_at
                )
                VALUES ('garrison_dirty', 'territory_res_north', 'domain_north', 'unit_guard_t1', 2, 'active', ?)
                """,
                (act_started_at.isoformat(timespec="seconds"),),
            )
            connection.execute(
                """
                INSERT INTO order_runtime_state (
                    order_id, lord_id, target_player_id, object_id, visibility,
                    status, escrow_reward_id, created_at, updated_at
                )
                VALUES (
                    'order_dirty', 'p_lord_1', 'p_witcher_1', 'qr_a1_006', 'public',
                    'published', NULL, ?, ?
                )
                """,
                (
                    act_started_at.isoformat(timespec="seconds"),
                    act_started_at.isoformat(timespec="seconds"),
                ),
            )
            connection.execute(
                """
                INSERT INTO applied_timer_ticks (
                    timer_id, due_at, act_id, effect_type, applied_at, source, payload_json
                )
                VALUES ('timer_dirty', ?, 'act1', 'lord_income_and_mana', ?, 'test', '{}')
                """,
                (
                    act_started_at.isoformat(timespec="seconds"),
                    act_started_at.isoformat(timespec="seconds"),
                ),
            )
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_north', status = 'controlled'
                WHERE territory_id = 'territory_field_oats'
                """
            )

            result = start_act(
                connection,
                settings,
                "registration",
                operator="gm_reset",
                physical_announcement_state="announced",
                now=reset_at,
            )
            ensure_lord_runtime_state(connection)

            domain_gold_values = {
                row["gold"]
                for row in connection.execute(
                    "SELECT gold FROM domain_runtime_state ORDER BY domain_id"
                ).fetchall()
            }
            dirty_counts = {
                table_name: connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                for table_name in [
                    "domain_buildings",
                    "army_reserve_runtime",
                    "active_army_runtime",
                    "garrison_runtime_state",
                    "order_runtime_state",
                    "territory_claim_runtime",
                    "applied_timer_ticks",
                    "army_windows",
                ]
            }
            act_history = [
                dict(row)
                for row in connection.execute(
                    "SELECT act_id, status, started_at FROM act_history ORDER BY started_at"
                ).fetchall()
            ]
            field_oats = connection.execute(
                """
                SELECT owner_domain_id, status
                FROM territory_runtime_state
                WHERE territory_id = 'territory_field_oats'
                """
            ).fetchone()
            river_node = connection.execute(
                """
                SELECT current_node_id
                FROM domain_runtime_state
                WHERE domain_id = 'domain_river'
                """
            ).fetchone()["current_node_id"]
            witcher = connection.execute(
                """
                SELECT gold, challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()
            controlled_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM territory_runtime_state
                WHERE owner_domain_id IS NOT NULL
                """
            ).fetchone()[0]

        self.assertEqual(result["state"]["current_act_id"], "registration")
        self.assertEqual(
            result["start_effects"]["registration_reset"]["initial_domain_gold"],
            [80],
        )
        self.assertEqual(domain_gold_values, {80})
        self.assertEqual(dirty_counts, {table_name: 0 for table_name in dirty_counts})
        self.assertEqual(
            act_history,
            [
                {
                    "act_id": "registration",
                    "status": "active",
                    "started_at": reset_at.isoformat(timespec="seconds"),
                }
            ],
        )
        self.assertEqual(dict(field_oats), {"owner_domain_id": None, "status": "neutral"})
        self.assertEqual(controlled_count, 4)
        self.assertEqual(river_node, "node_res_river")
        self.assertEqual(dict(witcher), {"gold": 20, "challenge_tokens": 0})

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

    def test_direct_final_act_start_applies_final_lock_side_effects(self) -> None:
        settings = self.make_settings("direct_final_act")
        self.import_seed(settings)
        final_act_at = datetime(2026, 6, 2, 17, 30, tzinfo=UTC)

        with connect(settings) as connection:
            result = start_act(
                connection,
                settings,
                "final_act",
                operator="gm_final",
                physical_announcement_state="announced",
                now=final_act_at,
            )
            lock = connection.execute(
                "SELECT locked_at, operator, source FROM final_lock_state WHERE id = 1"
            ).fetchone()
            pre_final = connection.execute(
                """
                SELECT status, artifact_path
                FROM backup_runs
                WHERE trigger_type = 'pre_final_lock'
                ORDER BY started_at DESC
                LIMIT 1
                """
            ).fetchone()

        self.assertEqual(result["state"]["current_act_id"], "final_act")
        self.assertEqual(result["start_effects"]["final_lock"]["status"], "locked")
        self.assertEqual(lock["operator"], "gm_final")
        self.assertEqual(lock["source"], "direct_final_act_start")
        self.assertIsNotNone(lock["locked_at"])
        self.assertEqual(pre_final["status"], "success")
        self.assertTrue(Path(pre_final["artifact_path"]).exists())

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_role_state_endpoint_reconciles_due_timers_after_restart(self) -> None:
        settings = self.make_settings("role_endpoint_timer")
        self.import_seed(settings)
        started_at = datetime.now(UTC) - timedelta(minutes=31)

        with connect(settings) as connection:
            start_act(
                connection,
                settings,
                "act1",
                operator="gm_timer",
                physical_announcement_state="announced",
                now=started_at,
            )

        client = TestClient(create_app(settings))
        state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )

        self.assertEqual(state.status_code, 200, state.text)
        with connect(settings) as connection:
            tick_payload = json.loads(
                connection.execute(
                    """
                    SELECT payload_json
                    FROM applied_timer_ticks
                    WHERE effect_type = 'lord_income_and_mana'
                    """
                ).fetchone()["payload_json"]
            )
        north_update = next(
            update
            for update in tick_payload["domain_updates"]
            if update["domain_id"] == "domain_north"
        )
        self.assertEqual(state.json()["domain"]["gold"], 80 + north_update["income"])
        self.assertEqual(
            state.json()["domain"]["territory_income_per_hour"],
            north_update["territory_income"],
        )
        self.assertEqual(state.json()["domain"]["current_mp"], 6)
        with connect(settings) as connection:
            tick_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM applied_timer_ticks
                WHERE effect_type = 'lord_income_and_mana'
                """
            ).fetchone()[0]
        self.assertEqual(tick_count, 1)

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
