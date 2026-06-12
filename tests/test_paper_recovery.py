from __future__ import annotations

import json
import unittest
from uuid import uuid4

from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.event_models import EventSyncEvent, EventSyncRequest
from backend.witcher_larp.event_service import sync_events
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.review_service import decide_event_review


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"


class PaperRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)
        self._paper_sequence = 0

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
                    "roll": 8,
                    "conflict_status": "clean",
                },
            )
            duplicate = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-pve-clean-1",
                    "source_form_type": "paper_pve_result",
                    "operator": "gm_king",
                    "timestamp": "2026-06-02T13:35:00+00:00",
                    "reason": "duplicate copy from the same recovered sheet",
                    "player_id": "p_witcher_1",
                    "qr_id": "qr_a1_001",
                    "result": "success",
                    "roll": 8,
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
            runtime_state = connection.execute(
                """
                SELECT xp, gold
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()
            pve_attempt = connection.execute(
                """
                SELECT player_id, qr_id, result, reward_id, reward_status
                FROM pve_attempts
                WHERE server_event_id = ?
                """,
                (result.server_event_id,),
            ).fetchone()
            review_count = connection.execute(
                "SELECT COUNT(*) FROM event_reviews WHERE event_id = ?",
                (result.event_id,),
            ).fetchone()[0]
            duplicate_reviews = connection.execute(
                "SELECT COUNT(*) FROM event_reviews WHERE event_id = ?",
                (duplicate.results[0].event_id,),
            ).fetchone()[0]

        self.assertEqual(result.status, "accepted")
        self.assertEqual(duplicate.results[0].status, "needs_master_review")
        self.assertIn("duplicate paper_form_id", duplicate.results[0].reason)
        self.assertEqual(stored["source"], "paper_recovered")
        self.assertEqual(log["source"], "paper_recovered")
        metadata = json.loads(stored["metadata_json"])
        self.assertTrue(metadata["paper_auto_applied"])
        self.assertEqual(metadata["recovered_event_type"], "pve_completed")
        self.assertEqual(metadata["pve_side_effects"]["reward_update"]["status"], "applied")
        self.assertEqual(runtime_state["xp"], 4)
        self.assertEqual(runtime_state["gold"], 30)
        self.assertEqual(pve_attempt["player_id"], "p_witcher_1")
        self.assertEqual(pve_attempt["qr_id"], "qr_a1_001")
        self.assertEqual(pve_attempt["result"], "success")
        self.assertEqual(pve_attempt["reward_id"], "reward_pve_t1")
        self.assertEqual(pve_attempt["reward_status"], "auto")
        self.assertEqual(review_count, 0)
        self.assertEqual(duplicate_reviews, 1)

    def test_clean_paper_pve_without_roll_evidence_requires_review_and_no_side_effects(self) -> None:
        settings = self._settings("paper_missing_roll")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            response = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-pve-missing-roll",
                    "source_form_type": "paper_pve_result",
                    "operator": "gm_king",
                    "timestamp": "2026-06-02T13:30:00+00:00",
                    "reason": "paper sheet omitted the d20 proof",
                    "player_id": "p_witcher_1",
                    "qr_id": "qr_a1_001",
                    "result": "success",
                    "conflict_status": "clean",
                },
            )
            runtime_row = connection.execute(
                """
                SELECT xp, gold
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()
            attempt_count = self._count(connection, "pve_attempts")

        result = response.results[0]
        self.assertEqual(result.status, "needs_master_review")
        self.assertEqual(
            result.reason,
            "paper pve recovery requires roll or roll_log evidence, or explicit master override review",
        )
        self.assertIsNone(runtime_row)
        self.assertEqual(attempt_count, 0)

    def test_conflicted_paper_pve_approval_applies_recovered_side_effects(self) -> None:
        settings = self._settings("paper_conflicted_pve_approve")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            response = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-pve-conflict-approve",
                    "source_form_type": "paper_pve_result",
                    "operator": "gm_king",
                    "timestamp": "2026-06-02T13:30:00+00:00",
                    "reason": "paper result conflicted with stale phone queue",
                    "player_id": "p_witcher_1",
                    "qr_id": "qr_a1_001",
                    "result": "success",
                    "roll": 8,
                    "conflict_status": "duplicate_conflict_needs_review",
                },
            )
            before_attempts = self._count(connection, "pve_attempts")
            decision = decide_event_review(
                connection,
                response.results[0].event_id,
                action="approve",
                operator="gm_king",
                reason="paper d20 evidence accepted after conflict review",
                severity="P1",
                source="paper_recovery_review",
            )
            runtime_state = connection.execute(
                """
                SELECT xp, gold
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()
            pve_attempt = connection.execute(
                """
                SELECT player_id, qr_id, result, reward_id, reward_status
                FROM pve_attempts
                WHERE server_event_id = ?
                """,
                (response.results[0].server_event_id,),
            ).fetchone()

        self.assertEqual(response.results[0].status, "needs_master_review")
        self.assertEqual(before_attempts, 0)
        self.assertEqual(decision["decision"]["status"], "applied")
        self.assertEqual(runtime_state["xp"], 4)
        self.assertEqual(runtime_state["gold"], 30)
        self.assertEqual(pve_attempt["player_id"], "p_witcher_1")
        self.assertEqual(pve_attempt["qr_id"], "qr_a1_001")
        self.assertEqual(pve_attempt["result"], "success")
        self.assertEqual(pve_attempt["reward_id"], "reward_pve_t1")
        self.assertEqual(pve_attempt["reward_status"], "auto")

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

    def test_rejected_malformed_paper_form_does_not_poison_corrected_same_form_id(self) -> None:
        settings = self._settings("paper_correction_after_reject")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            malformed = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-corrected-after-reject",
                    "source_form_type": "paper_pve_result",
                    "operator": "gm_king",
                    "timestamp": "bad-clock",
                    "reason": "operator mistyped timestamp",
                    "player_id": "p_witcher_1",
                    "qr_id": "qr_a1_001",
                    "result": "success",
                    "roll": 8,
                    "conflict_status": "clean",
                },
            )
            corrected = self._sync_one(
                connection,
                payload={
                    "paper_form_id": "paper-corrected-after-reject",
                    "source_form_type": "paper_pve_result",
                    "operator": "gm_king",
                    "timestamp": "2026-06-02T13:30:00+00:00",
                    "reason": "corrected timestamp for same paper sheet",
                    "player_id": "p_witcher_1",
                    "qr_id": "qr_a1_001",
                    "result": "success",
                    "roll": 8,
                    "conflict_status": "clean",
                },
            )
            pve_attempt = connection.execute(
                """
                SELECT player_id, qr_id
                FROM pve_attempts
                WHERE server_event_id = ?
                """,
                (corrected.results[0].server_event_id,),
            ).fetchone()

        self.assertEqual(malformed.results[0].status, "rejected")
        self.assertEqual(corrected.results[0].status, "accepted")
        self.assertEqual(pve_attempt["player_id"], "p_witcher_1")
        self.assertEqual(pve_attempt["qr_id"], "qr_a1_001")

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

        self.assertEqual(first.results[0].status, "needs_master_review")
        self.assertIn("domain-specific master review", first.results[0].reason)
        self.assertEqual(duplicate.results[0].status, "needs_master_review")
        self.assertEqual(conflict.results[0].status, "needs_master_review")
        self.assertTrue(
            any("domain-specific master review" in reason for reason in review_reasons)
        )
        self.assertTrue(any("duplicate paper_form_id" in reason for reason in review_reasons))
        self.assertTrue(any("paper battle result conflicts" in reason for reason in review_reasons))

    def test_clean_non_pve_paper_forms_require_explicit_domain_review(self) -> None:
        settings = self._settings("paper_domain_review")
        self._import_valid_seed(settings)
        cases = [
            {
                "paper_form_id": "paper-lord-action-review",
                "source_form_type": "paper_lord_action",
                "lord_id": "p_lord_1",
                "territory_id": "territory_north_keep",
                "action": "garrison",
            },
            {
                "paper_form_id": "paper-lord-battle-review",
                "source_form_type": "paper_lord_battle",
                "battle_id": "battle-paper-1",
                "result": "attacker_won",
                "losses": {"attacker": 1, "defender": 2},
            },
            {
                "paper_form_id": "paper-order-review",
                "source_form_type": "paper_order_resolution",
                "order_id": "order_river_review",
                "result": "completed",
            },
            {
                "paper_form_id": "paper-npc-review",
                "source_form_type": "paper_npc_deal",
                "npc_role": "wanderer",
                "target_id": "p_sorc_1",
                "price_json": {"gold": 2},
            },
            {
                "paper_form_id": "paper-final-review",
                "source_form_type": "paper_final_evidence",
                "evidence_category": "artifact",
                "target_id": "p_witcher_1",
                "summary_text": "Recovered final evidence from a paper fallback.",
            },
        ]

        with connect(settings) as connection:
            results = [
                self._sync_one(
                    connection,
                    payload={
                        **case,
                        "operator": "gm_king",
                        "timestamp": "2026-06-02T14:30:00+00:00",
                        "reason": "clean sheet still needs a domain handler",
                        "conflict_status": "clean",
                    },
                ).results[0]
                for case in cases
            ]
            review_count = connection.execute(
                "SELECT COUNT(*) FROM event_reviews"
            ).fetchone()[0]

        self.assertEqual([result.status for result in results], ["needs_master_review"] * len(cases))
        self.assertTrue(
            all("domain-specific master review" in str(result.reason) for result in results)
        )
        self.assertEqual(review_count, len(cases))

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def _import_valid_seed(self, settings: Settings) -> None:
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")

    def _sync_one(self, connection, *, payload: dict[str, object]):
        self._paper_sequence += 1
        return sync_events(
            connection,
            EventSyncRequest(
                device_id="paper_terminal",
                actor_id="gm_king",
                actor_type="master",
                events=[
                    EventSyncEvent(
                        event_id=f"paper_{uuid4().hex}",
                        client_sequence=self._paper_sequence,
                        created_at="2026-06-02T13:30:00+00:00",
                        event_type="paper_recovered",
                        payload=payload,
                    )
                ],
            ),
        )

    def _count(self, connection, table_name: str) -> int:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
