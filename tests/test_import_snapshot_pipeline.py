from __future__ import annotations

from contextlib import redirect_stdout
import csv
import io
import json
from pathlib import Path
import unittest
from uuid import uuid4

from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.csv_loader import load_pack_from_manifest
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack, main as import_main
from backend.witcher_larp.snapshot_exporter import build_snapshot_from_database
from backend.witcher_larp.validation import validate_seed_pack


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures"


class ImportSnapshotPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def make_settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def test_valid_seed_imports_to_sqlite_and_exports_snapshot(self) -> None:
        settings = self.make_settings("import_valid")
        snapshot_dir = TEST_TMP_ROOT / f"snapshots_{uuid4().hex}"

        report = import_seed_pack(
            settings,
            manifest_path=FIXTURE_ROOT / "seed_valid" / "fixture_manifest.csv",
            snapshot_dir=snapshot_dir,
        )

        self.assertEqual(report.status, "success")
        self.assertIsNotNone(report.snapshot_version)
        self.assertFalse(report.errors)

        with connect(settings) as connection:
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            for table_name in {
                "players",
                "map_nodes",
                "map_edges",
                "movement_pools",
                "territory_claims",
                "pending_tick_rewards",
                "reward_approvals",
                "recruit_markets",
                "anti_snowball_rules",
                "act_unlock_codes",
                "challenge_tokens",
                "pvp_tables",
                "pvp_throttle_rules",
                "trade_transfers",
                "personal_goals",
                "goal_flags",
                "gwent_matches",
                "final_summary",
                "raid_effects",
                "snapshot_versions",
            }:
                self.assertIn(table_name, tables)

            player_count = connection.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            qr_count = connection.execute("SELECT COUNT(*) FROM qr_objects").fetchone()[0]
            snapshot_count = connection.execute(
                "SELECT COUNT(*) FROM snapshot_versions"
            ).fetchone()[0]

        self.assertEqual(player_count, 13)
        self.assertEqual(qr_count, 40)
        self.assertEqual(snapshot_count, 1)

        snapshot_path = snapshot_dir / f"{report.snapshot_version}.json"
        self.assertTrue(snapshot_path.exists())
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["snapshot_version"], report.snapshot_version)
        self.assertEqual(snapshot["profile"]["lord_count"], "4")
        self.assertEqual(snapshot["visibility"]["scope"], "mobile_public_artifact")
        self.assertEqual(snapshot["players"], [])
        self.assertNotIn("player_codes", snapshot)
        self.assertNotIn("role_tokens", snapshot)
        self.assertEqual(len(snapshot["qr_objects"]), 40)
        self.assertTrue(snapshot["pve_scenarios"])
        self.assertTrue(snapshot["mobs"])
        self.assertTrue(snapshot["checks"]["xp_rules"])
        self.assertTrue(snapshot["items"])
        self.assertTrue(snapshot["cards"])
        self.assertTrue(snapshot["gwent_cards"])
        self.assertTrue(snapshot["potions"])
        self.assertTrue(snapshot["spells"])
        self.assertEqual(snapshot["goals"]["personal_goals"], [])
        self.assertTrue(snapshot["descriptors"]["reputation_rules"])

    def test_import_cli_returns_process_code_and_json_report_for_success_and_failure(self) -> None:
        success_db = TEST_TMP_ROOT / f"cli_success_{uuid4().hex}.db"
        success_snapshot_dir = TEST_TMP_ROOT / f"cli_snapshots_{uuid4().hex}"
        success_stdout = io.StringIO()

        with redirect_stdout(success_stdout):
            success_code = import_main(
                [
                    "--manifest",
                    str(FIXTURE_ROOT / "seed_valid" / "fixture_manifest.csv"),
                    "--db",
                    str(success_db),
                    "--snapshot-dir",
                    str(success_snapshot_dir),
                ]
            )
        success_report = json.loads(success_stdout.getvalue())

        failure_db = TEST_TMP_ROOT / f"cli_failure_{uuid4().hex}.db"
        failure_snapshot_dir = TEST_TMP_ROOT / f"cli_failed_snapshots_{uuid4().hex}"
        failure_stdout = io.StringIO()
        with redirect_stdout(failure_stdout):
            failure_code = import_main(
                [
                    "--manifest",
                    str(FIXTURE_ROOT / "seed_invalid_duplicate_ids" / "fixture_manifest.csv"),
                    "--db",
                    str(failure_db),
                    "--snapshot-dir",
                    str(failure_snapshot_dir),
                ]
            )
        failure_report = json.loads(failure_stdout.getvalue())

        self.assertEqual(success_code, 0)
        self.assertEqual(success_report["status"], "success")
        self.assertTrue((success_snapshot_dir / f"{success_report['snapshot_version']}.json").exists())
        self.assertEqual(failure_code, 1)
        self.assertEqual(failure_report["status"], "failed")
        self.assertIn("duplicate_id", {error["code"] for error in failure_report["errors"]})
        self.assertFalse(failure_snapshot_dir.exists())

    def test_restart_can_read_snapshot_metadata_and_player_scoped_payload(self) -> None:
        settings = self.make_settings("restart")
        report = import_seed_pack(
            settings,
            manifest_path=FIXTURE_ROOT / "seed_valid" / "fixture_manifest.csv",
            snapshot_dir=None,
        )
        self.assertEqual(report.status, "success")

        with connect(settings) as restarted_connection:
            snapshot = build_snapshot_from_database(restarted_connection)
            scoped = build_snapshot_from_database(
                restarted_connection,
                player_code="WC-WOLF-6GF4",
            )

        self.assertIsNotNone(snapshot)
        self.assertIsNotNone(scoped)
        assert snapshot is not None
        assert scoped is not None
        self.assertEqual(snapshot["snapshot_version"], report.snapshot_version)
        self.assertEqual(scoped["visibility"]["scope"], "player")
        self.assertEqual(len(scoped["players"]), 1)
        self.assertEqual(scoped["player"]["player_id"], "p_witcher_1")
        hidden_flags = [
            flag
            for flag in scoped["goals"]["goal_flags"]
            if flag["visibility"] == "master_only"
        ]
        self.assertEqual(hidden_flags, [])

    def test_invalid_fixtures_fail_with_expected_codes(self) -> None:
        expected_codes = {
            "seed_invalid_duplicate_ids": "duplicate_id",
            "seed_invalid_missing_refs": "missing_reference",
            "seed_invalid_bad_qr_mode": "bad_qr_mode",
            "seed_invalid_bad_profile_counts": "bad_profile_counts",
            "seed_invalid_future_act_unlock": "future_act_unlock_revealed",
            "seed_invalid_reward_approval": "reward_approval_policy",
            "seed_invalid_order_conflict": "order_object_conflict",
            "seed_invalid_gwent_deck": "gwent_deck_invalid",
            "seed_invalid_building_cycle": "building_cycle",
            "seed_invalid_paper_conflict": "paper_conflict_policy",
            "seed_invalid_empty_required_refs": "missing_required_reference",
            "seed_invalid_qr_act_mismatch": "qr_scenario_act_mismatch",
            "seed_invalid_qr_consumption_mismatch": "qr_consumption_rule_mismatch",
            "seed_invalid_domain_token_role_mismatch": "role_token_owner",
            "seed_invalid_lord_battle_rules": "invalid_lord_battle_rule",
        }
        for fixture_name, expected_code in expected_codes.items():
            with self.subTest(fixture=fixture_name):
                settings = self.make_settings(fixture_name)
                report = import_seed_pack(
                    settings,
                    manifest_path=FIXTURE_ROOT / fixture_name / "fixture_manifest.csv",
                    snapshot_dir=None,
                )
                self.assertEqual(report.status, "failed")
                self.assertIn(expected_code, {error.code for error in report.errors})
                with connect(settings) as connection:
                    stored_errors = {
                        row["code"]
                        for row in connection.execute(
                            """
                            SELECT code
                            FROM import_errors
                            WHERE run_id = ?
                            """,
                            (report.run_id,),
                        )
                    }
                self.assertIn(expected_code, stored_errors)

    def test_failed_import_does_not_replace_previous_content(self) -> None:
        settings = self.make_settings("no_partial")
        valid_report = import_seed_pack(
            settings,
            manifest_path=FIXTURE_ROOT / "seed_valid" / "fixture_manifest.csv",
            snapshot_dir=None,
        )
        self.assertEqual(valid_report.status, "success")

        invalid_report = import_seed_pack(
            settings,
            manifest_path=FIXTURE_ROOT / "seed_invalid_duplicate_ids" / "fixture_manifest.csv",
            snapshot_dir=None,
        )
        self.assertEqual(invalid_report.status, "failed")

        with connect(settings) as connection:
            player_count = connection.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            latest_snapshot = connection.execute(
                """
                SELECT snapshot_version
                FROM snapshot_versions
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()["snapshot_version"]

        self.assertEqual(player_count, 13)
        self.assertEqual(latest_snapshot, valid_report.snapshot_version)

    def test_loader_validation_can_be_run_before_sqlite_write(self) -> None:
        pack = load_pack_from_manifest(FIXTURE_ROOT / "seed_valid" / "fixture_manifest.csv")
        errors = validate_seed_pack(pack)

        self.assertEqual(errors, [])


class ImportFixtureManifestTests(unittest.TestCase):
    def test_manifest_expected_results_match_runtime_import_codes(self) -> None:
        for manifest_path in sorted(FIXTURE_ROOT.glob("seed_invalid_*/fixture_manifest.csv")):
            with self.subTest(manifest=manifest_path.parent.name):
                expected_result = _manifest_expected_result(manifest_path)
                settings = Settings(
                    database_path=TEST_TMP_ROOT / f"manifest_{uuid4().hex}.db"
                )
                report = import_seed_pack(
                    settings,
                    manifest_path=manifest_path,
                    snapshot_dir=None,
                )
                self.assertEqual(report.status, "failed")
                self.assertIn(expected_result, {error.code for error in report.errors})


def _manifest_expected_result(manifest_path: Path) -> str:
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        return next(csv.DictReader(handle))["expected_result"]


if __name__ == "__main__":
    unittest.main()
