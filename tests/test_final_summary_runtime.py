from __future__ import annotations

from datetime import UTC, datetime
import json
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.event_models import EventSyncEvent, EventSyncRequest
from backend.witcher_larp.event_service import sync_events
from backend.witcher_larp.final_summary_service import build_final_summary
from backend.witcher_larp.final_summary_service import record_final_master_note
from backend.witcher_larp.import_models import ImportReport
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.npc_service import NpcEventInput, record_npc_event
from backend.witcher_larp.sorceress_service import cast_spell
from backend.witcher_larp.sorceress_service import ensure_sorceress_runtime_state
from backend.witcher_larp.sorceress_service import record_alignment_evidence

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"
MASTER_HEADERS = {"X-Role-Token": "MASTER-KING-4QZ8"}


class FinalSummaryRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_final_summary_aggregates_master_evidence_without_winner(self) -> None:
        settings, report = self.prepare_seed("final_summary")
        now = datetime(2026, 6, 2, 17, 0, tzinfo=UTC)

        with connect(settings) as connection:
            ensure_sorceress_runtime_state(connection)
            connection.execute(
                "UPDATE player_runtime_state SET mana = 4 WHERE player_id = 'p_sorc_1'"
            )
            cast_spell(
                connection,
                sorceress_id="p_sorc_1",
                spell_id="spell_ritual_t4",
                target_type="final_hook",
                target_id="hook_sorc_intent",
                now=now,
            )
            record_alignment_evidence(
                connection,
                sorceress_id="p_sorc_3",
                alignment_state="double_game",
                evidence_type="two_sided_evidence",
                payload={"lords": ["p_lord_1", "p_lord_3"]},
                final_flag=True,
                now=now,
            )
            record_npc_event(
                connection,
                NpcEventInput(
                    npc_role="npc_wanderer",
                    event_type="stranger_deal",
                    target_ids=["p_witcher_4"],
                    price={"hidden_price": "owed_at_final"},
                    condition={"must_bring": "artifact"},
                    consequence={"effect": "alternate_victory_hook"},
                    reputation_delta=-4,
                    severity="P0",
                    final_flag=True,
                ),
            )
            connection.execute(
                """
                INSERT INTO pve_attempts (
                    player_id, qr_id, scenario_id, act_id, result,
                    outcome, roll_log_json, reward_id, reward_status,
                    payload_json, created_at
                )
                VALUES (?, ?, ?, ?, 'success', 'success', ?, ?, 'auto', ?, ?)
                """,
                (
                    "p_witcher_1",
                    "qr_a1_001",
                    "scn_a1_001",
                    "act1",
                    json.dumps([{"die": "d20", "roll": 18}], sort_keys=True),
                    "reward_pve_common",
                    json.dumps({"summary": "monster contract"}, sort_keys=True),
                    now.isoformat(timespec="seconds"),
                ),
            )
            sync_events(
                connection,
                EventSyncRequest(
                    device_id="paper-terminal",
                    actor_id="gm_final",
                    actor_type="master",
                    events=[
                        EventSyncEvent(
                            event_id="paper-final-evidence-1",
                            client_sequence=1,
                            created_at=now.isoformat(timespec="seconds"),
                            event_type="paper_recovered",
                            payload={
                                "paper_form_id": "paper_final_1",
                                "source_form_type": "paper_final_evidence",
                                "operator": "gm_final",
                                "timestamp": now.isoformat(timespec="seconds"),
                                "reason": "offline final station",
                                "evidence_category": "final_scene",
                                "target_id": "p_witcher_5",
                                "summary_text": "final scene evidence captured on paper",
                                "conflict_status": "needs_review",
                            },
                        )
                    ],
                ),
            )
            record_final_master_note(
                connection,
                note_id="final_note_epilogue",
                category="epilogue",
                target_id="p_witcher_5",
                note_text="Use this as tone input only.",
                operator="gm_final",
                now=now,
            )
            start_act(
                connection,
                settings,
                "final_lock",
                operator="gm_final",
                physical_announcement_state="announced",
                now=datetime(2026, 6, 2, 17, 15, tzinfo=UTC),
            )
            summary = build_final_summary(
                connection,
                now=datetime(2026, 6, 2, 17, 30, tzinfo=UTC),
            )

        self.assertEqual(summary["snapshot_version"], report.snapshot_version)
        self.assertTrue(summary["final_lock_state"]["locked"])
        self.assertTrue(summary["final_lock_state"]["blocks_new_orders"])
        self.assertFalse(summary["decision_policy"]["automatic_winner_calculation"])
        self.assertTrue(summary["decision_policy"]["masters_must_decide"])
        self.assertNotIn("winner_id", summary)
        self.assertEqual(summary["staffing"]["unmanned_station_count"], 0)
        self.assertEqual(summary["staffing"]["total_station_count"], 6)

        self.assertEqual(len(summary["evidence_by_role"]["lords"]), 4)
        self.assertEqual(
            self._role_item(summary["evidence_by_role"]["lords"], "p_lord_1")["domain"]["influence"],
            3,
        )
        self.assertEqual(len(summary["evidence_by_role"]["witchers"]), 5)
        self.assertEqual(len(summary["evidence_by_role"]["sorceresses"]), 4)
        witcher_one = self._role_item(summary["evidence_by_role"]["witchers"], "p_witcher_1")
        self.assertEqual(witcher_one["pve_attempts"][0]["result"], "success")

        sorceress_one = self._role_item(summary["evidence_by_role"]["sorceresses"], "p_sorc_1")
        self.assertEqual(sorceress_one["locked_magical_intent"][0]["status"], "locked")
        self.assertEqual(
            sorceress_one["personal_hooks"][0]["flags_master_only"][0]["flag_key"],
            "locked_magical_intent",
        )
        self.assertFalse(
            any("flag_sorc_intent" in str(item) for item in summary["player_visible_categories"])
        )

        self.assertEqual(summary["npc_prices"][0]["price"]["hidden_price"], "owed_at_final")
        self.assertEqual(summary["paper_recovery"][0]["source_form_type"], "paper_final_evidence")
        self.assertIn(
            "unresolved_review",
            {item["evidence_category"] for item in summary["missing_locks"]},
        )
        self.assertIn(
            "battle",
            {item["evidence_category"] for item in summary["missing_locks"]},
        )
        self.assertEqual(summary["master_final_notes"][0]["note_id"], "final_note_epilogue")
        self.assertEqual(summary["export"]["snapshot_version"], report.snapshot_version)

        with connect(settings) as restarted_connection:
            restarted = build_final_summary(restarted_connection)
        self.assertEqual(restarted["master_final_notes"][0]["note_text"], "Use this as tone input only.")
        self.assertTrue(restarted["final_lock_state"]["locked"])

    def test_final_summary_requires_locked_intent_per_sorceress(self) -> None:
        settings, _ = self.prepare_seed("final_summary_sorceress_locks")
        before_final = datetime(2026, 6, 2, 17, 0, tzinfo=UTC)
        final_time = datetime(2026, 6, 2, 17, 20, tzinfo=UTC)

        with connect(settings) as connection:
            ensure_sorceress_runtime_state(connection)
            connection.execute(
                """
                UPDATE player_runtime_state
                SET mana = 4
                WHERE player_id IN ('p_sorc_1', 'p_sorc_2')
                """
            )
            cast_spell(
                connection,
                sorceress_id="p_sorc_1",
                spell_id="spell_ritual_t4",
                target_type="final_hook",
                target_id="hook_sorc_intent",
                now=before_final,
            )
            start_act(
                connection,
                settings,
                "final_lock",
                operator="gm_final",
                physical_announcement_state="announced",
                now=datetime(2026, 6, 2, 17, 15, tzinfo=UTC),
            )
            cast_spell(
                connection,
                sorceress_id="p_sorc_2",
                spell_id="spell_ritual_t4",
                target_type="final_hook",
                target_id="hook_sorc_intent",
                now=final_time,
            )
            connection.execute(
                """
                INSERT INTO locked_magical_intent (
                    intent_id, sorceress_id, cast_id, target_id, intent_json,
                    status, review_reason, locked_at, created_at
                )
                VALUES (
                    'intent_sorc_3_disputed', 'p_sorc_3', NULL, 'hook_sorc_intent',
                    ?, 'contested_review', 'masters received conflicting magical intent notes',
                    NULL, ?
                )
                """,
                (
                    json.dumps({"effect": "locked_magical_intent"}, sort_keys=True),
                    final_time.isoformat(timespec="seconds"),
                ),
            )
            summary = build_final_summary(connection, now=final_time)

        intent_states = {item["sorceress_id"]: item for item in summary["locked_magical_intent"]}
        self.assertEqual(
            {sorceress_id: item["status"] for sorceress_id, item in intent_states.items()},
            {
                "p_sorc_1": "locked",
                "p_sorc_2": "review_pending",
                "p_sorc_3": "disputed",
                "p_sorc_4": "missing",
            },
        )
        self.assertEqual(intent_states["p_sorc_2"]["runtime_status"], "needs_master_review")
        self.assertEqual(intent_states["p_sorc_3"]["runtime_status"], "contested_review")

        sorceress_two = self._role_item(summary["evidence_by_role"]["sorceresses"], "p_sorc_2")
        sorceress_four = self._role_item(summary["evidence_by_role"]["sorceresses"], "p_sorc_4")
        self.assertEqual(sorceress_two["locked_magical_intent"][0]["status"], "review_pending")
        self.assertEqual(sorceress_four["locked_magical_intent"][0]["status"], "missing")

        magic_missing = [
            item
            for item in summary["missing_locks"]
            if item["evidence_category"] == "locked_magical_intent"
        ]
        self.assertEqual(
            {item["sorceress_id"]: item["status"] for item in magic_missing},
            {
                "p_sorc_2": "review_pending",
                "p_sorc_3": "disputed",
                "p_sorc_4": "missing",
            },
        )
        self.assertNotIn("p_sorc_1", {item["sorceress_id"] for item in magic_missing})

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_fastapi_final_summary_and_final_lock_order_policy(self) -> None:
        settings, _ = self.prepare_seed("final_summary_api")
        with connect(settings) as connection:
            start_act(
                connection,
                settings,
                "final_lock",
                operator="gm_final",
                physical_announcement_state="announced",
                now=datetime(2026, 6, 2, 17, 15, tzinfo=UTC),
            )
        client = TestClient(create_app(settings))

        summary = client.get("/api/master/final-summary", headers=MASTER_HEADERS)
        note = client.post(
            "/api/master/final-summary/notes",
            headers=MASTER_HEADERS,
            json={
                "note_id": "api_final_note",
                "category": "ruling",
                "target_id": "p_lord_4",
                "note_text": "Manual ruling input.",
            },
        )
        blank_note = client.post(
            "/api/master/final-summary/notes",
            headers=MASTER_HEADERS,
            json={
                "note_id": "api_blank_note",
                "category": "ruling",
                "target_id": "p_lord_4",
                "note_text": "   ",
            },
        )
        blocked_order = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={
                "action": "create",
                "object_id": "territory_magic_corner",
                "visibility": "public",
                "target_player_id": "p_witcher_5",
                "escrow_reward_id": "reward_order_success",
            },
        )
        paper_order = client.post(
            "/api/lords/p_lord_4/orders",
            headers=self._headers("hill"),
            json={
                "action": "create",
                "order_id": "paper_final_order",
                "object_id": "territory_magic_corner",
                "visibility": "public",
                "target_player_id": "p_witcher_5",
                "escrow_reward_id": "reward_order_success",
                "source": "paper_final_evidence",
            },
        )

        self.assertEqual(summary.status_code, 200)
        self.assertFalse(summary.json()["final_summary_config"]["automatic_winner_calculation"])
        self.assertEqual(note.status_code, 200)
        self.assertEqual(note.json()["note_id"], "api_final_note")
        self.assertEqual(blank_note.status_code, 400)
        self.assertIn("Final master note text is required", blank_note.json()["detail"])
        self.assertEqual(blocked_order.status_code, 409)
        self.assertEqual(blocked_order.json()["detail"]["code"], "final_lock_orders_closed")
        self.assertEqual(paper_order.status_code, 200)
        self.assertEqual(paper_order.json()["order"]["order_id"], "paper_final_order")

    def prepare_seed(self, name: str) -> tuple[Settings, ImportReport]:
        settings = Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")
        return settings, report

    @staticmethod
    def _role_item(items: list[dict[str, object]], player_id: str) -> dict[str, object]:
        return next(item for item in items if item["player"]["player_id"] == player_id)

    @staticmethod
    def _headers(lord: str) -> dict[str, str]:
        tokens = {
            "north": "LORD-NORTH-R8K4",
            "river": "LORD-RIVER-M2J9",
            "forest": "LORD-FOREST-P6W3",
            "hill": "LORD-HILL-T5C7",
        }
        return {"X-Role-Token": tokens[lord]}


if __name__ == "__main__":
    unittest.main()
