from __future__ import annotations

import json
import unittest
from uuid import uuid4

from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.event_models import EventSyncEvent, EventSyncRequest
from backend.witcher_larp.event_service import sync_events
from backend.witcher_larp.import_service import import_seed_pack


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"


class PaperRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_clean_paper_recovery_auto_applies_as_audited_paper_source(self) -> None:
        settings = self._settings("paper_clean")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            response = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-pve-clean-1",
                    "source_form_type": "paper_pve_result",
                    "operator": "gm_king",
                    "timestamp": "2026-06-02T13:30:00+00:00",
                    "reason": "phone battery died after QR scene",
                    "player_id": "p_witcher_1",
                    "qr_id": "qr_a1_001",
                    "result": "success",
                    "conflict_status": "clean",
                },
            )
            result = response.results[0]
            stored = connection.execute(
                """
                SELECT source, metadata_json
                FROM events
                WHERE server_event_id = ?
                """,
                (result.server_event_id,),
            ).fetchone()
            log = connection.execute(
                """
                SELECT source
                FROM event_log
                WHERE payload_json LIKE ?
                """,
                ("%paper-pve-clean-1%",),
            ).fetchone()
            review_count = connection.execute(
                "SELECT COUNT(*) FROM event_reviews WHERE event_id = ?",
                (result.event_id,),
            ).fetchone()[0]

        self.assertEqual(result.status, "accepted")
        self.assertEqual(stored["source"], "paper_recovered")
        self.assertEqual(log["source"], "paper_recovered")
        self.assertTrue(json.loads(stored["metadata_json"])["paper_auto_applied"])
        self.assertEqual(review_count, 0)

    def test_missing_paper_audit_fields_are_rejected_readably(self) -> None:
        settings = self._settings("paper_missing")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            response = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-pvp-missing-1",
                    "source_form_type": "paper_pvp_stake",
                    "timestamp": "2026-06-02T13:40:00+00:00",
                    "reason": "stake result captured on paper",
                    "match_id": "match-paper-1",
                    "stake_json": {"asset_id": "item_order_seal"},
                    "conflict_status": "clean",
                },
            )

        result = response.results[0]
        self.assertEqual(result.status, "rejected")
        self.assertIn("operator", result.reason)

    def test_paper_recovery_diagnostics_for_unknown_timestamp_and_corrupt_form_config(self) -> None:
        settings = self._settings("paper_diagnostics")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            missing_source = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-missing-source-1",
                    "operator": "gm_king",
                    "timestamp": "2026-06-02T14:05:00+00:00",
                    "reason": "paper fallback sheet did not name the form type",
                    "conflict_status": "clean",
                },
            )
            unknown_source = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-unknown-source-1",
                    "source_form_type": "paper_unknown_contract",
                    "operator": "gm_king",
                    "timestamp": "2026-06-02T14:10:00+00:00",
                    "reason": "legacy form name from a printed packet",
                    "conflict_status": "clean",
                },
            )
            invalid_timestamp = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-bad-timestamp-1",
                    "source_form_type": "paper_pve_result",
                    "operator": "gm_king",
                    "timestamp": "not-a-clock",
                    "reason": "QR scene was recovered after Wi-Fi returned",
                    "player_id": "p_witcher_1",
                    "qr_id": "qr_a1_001",
                    "result": "success",
                    "conflict_status": "clean",
                },
            )
            connection.execute(
                """
                UPDATE paper_forms
                SET required_fields_json = ?
                WHERE form_type = 'paper_npc_deal'
                """,
                ("{broken-json",),
            )
            corrupt_form = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-corrupt-form-1",
                    "source_form_type": "paper_npc_deal",
                    "operator": "gm_stranger",
                    "timestamp": "2026-06-02T14:20:00+00:00",
                    "reason": "NPC bargain captured during server outage",
                    "npc_role": "stranger",
                    "target_id": "p_sorc_1",
                    "price_json": {"gold": 2},
                    "conflict_status": "clean",
                },
            )
            review_reasons = [
                row["reason"]
                for row in connection.execute(
                    """
                    SELECT reason
                    FROM event_reviews
                    ORDER BY review_id
                    """
                ).fetchall()
            ]

        self.assertEqual(missing_source.results[0].status, "rejected")
        self.assertIn("source_form_type", missing_source.results[0].reason)
        self.assertEqual(unknown_source.results[0].status, "needs_master_review")
        self.assertIn("unknown paper source_form_type", unknown_source.results[0].reason)
        self.assertEqual(invalid_timestamp.results[0].status, "rejected")
        self.assertEqual(
            invalid_timestamp.results[0].reason,
            "paper recovery timestamp must be ISO-8601",
        )
        self.assertEqual(corrupt_form.results[0].status, "needs_master_review")
        self.assertIn("paper form definition is invalid", corrupt_form.results[0].reason)
        self.assertTrue(
            any("unknown paper source_form_type" in reason for reason in review_reasons)
        )
        self.assertTrue(
            any("paper form definition is invalid" in reason for reason in review_reasons)
        )

    def test_duplicate_or_conflicting_paper_recovery_routes_to_review(self) -> None:
        settings = self._settings("paper_conflict")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            first = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-order-dup-1",
                    "source_form_type": "paper_order_resolution",
                    "operator": "gm_king",
                    "timestamp": "2026-06-02T13:50:00+00:00",
                    "reason": "order resolved while lord panel was offline",
                    "order_id": "order_river_review",
                    "result": "completed",
                    "conflict_status": "clean",
                },
            )
            duplicate = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-order-dup-1",
                    "source_form_type": "paper_order_resolution",
                    "operator": "gm_king",
                    "timestamp": "2026-06-02T13:55:00+00:00",
                    "reason": "second copy of the same paper form",
                    "order_id": "order_river_review",
                    "result": "completed",
                    "conflict_status": "clean",
                },
            )
            conflict = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-battle-conflict-1",
                    "source_form_type": "paper_lord_battle",
                    "operator": "gm_king",
                    "timestamp": "2026-06-02T14:00:00+00:00",
                    "reason": "paper battle result conflicts with digital state",
                    "battle_id": "battle-paper-1",
                    "result": "attacker_won",
                    "losses": {"attacker": 1, "defender": 2},
                    "conflict_status": "duplicate_conflict_needs_review",
                },
            )
            review_reasons = [
                row["reason"]
                for row in connection.execute(
                    """
                    SELECT reason
                    FROM event_reviews
                    ORDER BY review_id
                    """
                ).fetchall()
            ]

        self.assertEqual(first.results[0].status, "accepted")
        self.assertEqual(duplicate.results[0].status, "needs_master_review")
        self.assertEqual(conflict.results[0].status, "needs_master_review")
        self.assertTrue(any("duplicate paper_form_id" in reason for reason in review_reasons))
        self.assertTrue(any("paper battle result conflicts" in reason for reason in review_reasons))

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def _import_valid_seed(self, settings: Settings) -> None:
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")

    def _sync_one(self, connection, *, payload: dict[str, object]):
        return sync_events(
            connection,
            EventSyncRequest(
                device_id="paper_terminal",
                actor_id="gm_king",
                actor_type="master",
                events=[
                    EventSyncEvent(
                        event_id=f"paper_{uuid4().hex}",
                        client_sequence=1,
                        created_at="2026-06-02T13:30:00+00:00",
                        event_type="paper_recovered",
                        payload=payload,
                    )
                ],
            ),
        )


if __name__ == "__main__":
    unittest.main()
