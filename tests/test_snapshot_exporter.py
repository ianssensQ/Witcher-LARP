from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import reveal_unlock_code, start_act
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.reputation_service import apply_reputation_change
from backend.witcher_larp.reputation_service import get_reputation_view
from backend.witcher_larp.snapshot_exporter import build_snapshot_from_database


FIXTURE_MANIFEST = (
    PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"
)
SECRET_VALUES = (
    "LC-NORTH-7QK2",
    "LC-RIVER-8YM4",
    "LC-FOREST-3FD9",
    "LC-HILL-6VN1",
    "SC-MOON-4AD8",
    "SC-EMBER-9JP3",
    "SC-OWL-2RW7",
    "SC-STAR-5TN6",
    "WC-WOLF-6GF4",
    "WC-CAT-1HN8",
    "WC-GRIFFIN-7LX2",
    "WC-BEAR-3SC5",
    "WC-VIPER-9BZ1",
    "LORD-NORTH-R8K4",
    "LORD-RIVER-M2J9",
    "LORD-FOREST-P6W3",
    "LORD-HILL-T5C7",
    "MASTER-KING-4QZ8",
    "MASTER-WANDERER-2LF6",
    "UNLOCK-A2-7GQ4",
    "UNLOCK-A3-2KVM",
    "UNLOCK-FINAL-9XCE",
)


class SnapshotExporterSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        (PROJECT_ROOT / ".test-data").mkdir(exist_ok=True)

    def test_scoped_snapshots_hide_secret_tables_for_all_player_roles(self) -> None:
        settings = self._settings("scoped_snapshot")
        self._import_valid_seed(settings)
        cases = (
            ("WC-WOLF-6GF4", "p_witcher_1", "witcher"),
            ("SC-MOON-4AD8", "p_sorc_1", "sorceress"),
            ("LC-NORTH-7QK2", "p_lord_1", "lord"),
        )

        with connect(settings) as connection:
            for player_code, player_id, role_type in cases:
                with self.subTest(role_type=role_type):
                    snapshot = build_snapshot_from_database(
                        connection,
                        player_code=player_code,
                    )

                    self.assertIsNotNone(snapshot)
                    assert snapshot is not None
                    self.assertEqual(snapshot["visibility"]["scope"], "player")
                    self.assertEqual(snapshot["auth"]["player_id"], player_id)
                    self.assertEqual(snapshot["player"]["player_id"], player_id)
                    self.assertEqual(snapshot["player"]["role_type"], role_type)
                    self.assertEqual(snapshot["players"], [snapshot["player"]])
                    self.assertNotIn("player_code_id", snapshot["player"])
                    self.assert_secret_tables_absent(snapshot)

    def test_player_scoped_snapshot_hides_exact_reputation_value(self) -> None:
        settings = self._settings("scoped_reputation")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            apply_reputation_change(
                connection,
                "p_witcher_1",
                3,
                reason="public contract accepted",
            )
            snapshot = build_snapshot_from_database(
                connection,
                player_code="WC-WOLF-6GF4",
            )
            master_view = get_reputation_view(
                connection,
                "p_witcher_1",
                visibility="master",
            )

        assert snapshot is not None
        player = snapshot["player"]
        assert isinstance(player, dict)
        reputation = player["reputation_state"]
        assert isinstance(reputation, dict)

        self.assertEqual(master_view["value"], 3)
        self.assertNotIn("reputation", player)
        self.assertNotIn("value", reputation)
        self.assertNotIn("change_log", reputation)
        self.assertNotIn("threshold_range", reputation)
        self.assertEqual(reputation["state_label"], "Good")
        self.assertEqual(reputation["player_descriptor"], "trusted")
        self.assertEqual(reputation["value_visibility"], "hidden_from_player")
        self.assertEqual(snapshot["players"], [player])
        reputation_rules = snapshot["descriptors"]["reputation_rules"]
        self.assertTrue(reputation_rules)
        self.assertTrue(all("min_value" not in rule for rule in reputation_rules))
        self.assertTrue(all("max_value" not in rule for rule in reputation_rules))

    def test_player_scoped_snapshot_redacts_future_unique_qr_and_artifacts(self) -> None:
        settings = self._settings("scoped_qr_artifacts")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            snapshot = build_snapshot_from_database(
                connection,
                player_code="WC-WOLF-6GF4",
            )

        assert snapshot is not None
        qr_rows = snapshot["qr_objects"]
        scenario_rows = snapshot["pve_scenarios"]
        artifact_rows = snapshot["artifacts"]
        assert isinstance(qr_rows, list)
        assert isinstance(scenario_rows, list)
        assert isinstance(artifact_rows, list)

        qr_ids = {row["qr_id"] for row in qr_rows}
        scenario_ids = {row["scenario_id"] for row in scenario_rows}
        self.assertIn("qr_a1_001", qr_ids)
        self.assertNotIn("qr_a1_006", qr_ids)
        self.assertNotIn("qr_a2_013", qr_ids)
        self.assertTrue(all(row["act_id"] == "act1" for row in qr_rows))
        self.assertTrue(
            all(row["qr_mode"] in {"repeatable_scene", "always_available_scene"} for row in qr_rows)
        )
        self.assertIn("scn_a1_001", scenario_ids)
        self.assertNotIn("scn_a1_006", scenario_ids)
        self.assertNotIn("scn_a2_013", scenario_ids)
        self.assertEqual(artifact_rows, [])

        dumped = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("QR-A1-X3L5", dumped)
        self.assertNotIn("QR-A2-B4K8", dumped)
        self.assertNotIn("Fang secured", dumped)
        self.assertNotIn("artifact_black_seal", dumped)
        self.assertNotIn("artifact_crow_feather", dumped)

    def test_exported_full_snapshot_file_does_not_contain_role_or_player_codes(self) -> None:
        settings = self._settings("exported_snapshot")
        snapshot_dir = PROJECT_ROOT / ".test-data" / f"snapshots_{uuid4().hex}"
        report = import_seed_pack(
            settings,
            manifest_path=FIXTURE_MANIFEST,
            snapshot_dir=snapshot_dir,
        )
        self.assertEqual(report.status, "success")

        snapshot_path = snapshot_dir / f"{report.snapshot_version}.json"
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["visibility"]["secret_tables"], "server_only")
        self.assert_secret_tables_absent(payload)

    def test_unknown_player_code_cannot_build_scoped_snapshot(self) -> None:
        settings = self._settings("bad_player_code")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            snapshot = build_snapshot_from_database(
                connection,
                player_code="WC-NOT-A-CODE",
            )

        self.assertIsNone(snapshot)

    def test_revealed_act_unlock_code_is_included_in_scoped_snapshot(self) -> None:
        settings = self._settings("revealed_unlock_snapshot")
        self._import_valid_seed(settings)
        started_at = datetime(2026, 6, 2, 12, 30, tzinfo=UTC)

        with connect(settings) as connection:
            hidden_snapshot = build_snapshot_from_database(
                connection,
                player_code="WC-WOLF-6GF4",
            )
            start_act(
                connection,
                settings,
                "act2",
                operator="gm_king",
                physical_announcement_state="announced",
                now=started_at,
            )
            reveal_unlock_code(
                connection,
                "act2",
                operator="gm_king",
                now=started_at + timedelta(minutes=1),
            )
            revealed_snapshot = build_snapshot_from_database(
                connection,
                player_code="WC-WOLF-6GF4",
            )

        assert hidden_snapshot is not None
        assert revealed_snapshot is not None
        hidden_act2 = self.act_unlock_row(hidden_snapshot, "act2")
        revealed_act2 = self.act_unlock_row(revealed_snapshot, "act2")

        self.assertIsNone(hidden_act2["code"])
        self.assertIsNone(hidden_act2["code_sha256"])
        self.assertFalse(hidden_act2["revealed"])
        self.assertEqual(hidden_snapshot["act_unlock_state"]["revealed_act_ids"], [])
        self.assertNotIn(
            hashlib.sha256("UNLOCK-A2-7GQ4".encode("utf-8")).hexdigest(),
            json.dumps(hidden_snapshot, ensure_ascii=False, sort_keys=True),
        )
        self.assertEqual(revealed_act2["code"], "UNLOCK-A2-7GQ4")
        self.assertTrue(revealed_act2["revealed"])
        self.assertTrue(revealed_act2["server_unlocked"])
        self.assertIsNotNone(revealed_act2["code_sha256"])
        self.assertEqual(revealed_act2["unlock_revealed_by"], "gm_king")
        self.assertIn("act2", revealed_snapshot["act_unlock_state"]["unlocked_act_ids"])
        self.assertIn("act2", revealed_snapshot["act_unlock_state"]["revealed_act_ids"])
        self.assertNotIn("player_codes", revealed_snapshot)
        self.assertNotIn("role_tokens", revealed_snapshot)

    def assert_secret_tables_absent(self, payload: dict[str, object]) -> None:
        self.assertNotIn("player_codes", payload)
        self.assertNotIn("role_tokens", payload)
        dumped = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        for secret in SECRET_VALUES:
            self.assertNotIn(secret, dumped)

    @staticmethod
    def act_unlock_row(payload: dict[str, object], act_id: str) -> dict[str, object]:
        rows = payload["act_unlock_codes"]
        assert isinstance(rows, list)
        return next(row for row in rows if isinstance(row, dict) and row["act_id"] == act_id)

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=PROJECT_ROOT / ".test-data" / f"{name}_{uuid4().hex}.db")

    def _import_valid_seed(self, settings: Settings):
        report = import_seed_pack(
            settings,
            manifest_path=FIXTURE_MANIFEST,
            snapshot_dir=None,
        )
        self.assertEqual(report.status, "success")
        return report


if __name__ == "__main__":
    unittest.main()
