from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import reveal_unlock_code, start_act
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.event_models import EventSyncEvent, EventSyncRequest
from backend.witcher_larp.event_service import sync_events
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.pve_runtime import resolve_pve_scene


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"


class EventSyncIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_offline_act_unlock_rejects_valid_code_before_master_reveal(self) -> None:
        settings = self._settings("early_unlock")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            response = self._sync_one(
                connection,
                event_type="act_unlocked_offline",
                payload={"act_id": "act2", "code": "UNLOCK-A2-7GQ4"},
            )

        result = response.results[0]
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason, "act unlock code has not been revealed by masters")

    def test_offline_act_unlock_accepts_code_after_start_announcement_and_reveal(self) -> None:
        settings = self._settings("revealed_unlock")
        self._import_valid_seed(settings)
        started_at = datetime(2026, 6, 2, 12, 30, tzinfo=UTC)

        with connect(settings) as connection:
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
            response = self._sync_one(
                connection,
                event_type="act_unlocked_offline",
                payload={"act_id": "act2", "code": "UNLOCK-A2-7GQ4"},
            )

        result = response.results[0]
        self.assertEqual(result.status, "accepted")
        self.assertIsNone(result.reason)

    def test_offline_act_unlock_accepts_hash_verifier_after_reveal(self) -> None:
        settings = self._settings("revealed_unlock_hash")
        self._import_valid_seed(settings)
        started_at = datetime(2026, 6, 2, 12, 30, tzinfo=UTC)
        code_hash = hashlib.sha256("UNLOCK-A2-7GQ4".encode("utf-8")).hexdigest()

        with connect(settings) as connection:
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
            response = self._sync_one(
                connection,
                event_type="act_unlocked_offline",
                payload={"act_id": "act2", "code_sha256": code_hash},
            )

        result = response.results[0]
        self.assertEqual(result.status, "accepted")
        self.assertIsNone(result.reason)

    def test_offline_act_unlock_rejects_invalid_code_and_reviews_unknown_target(self) -> None:
        settings = self._settings("bad_unlock_inputs")
        self._import_valid_seed(settings)
        started_at = datetime(2026, 6, 2, 12, 30, tzinfo=UTC)

        with connect(settings) as connection:
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
            invalid_code = self._sync_one(
                connection,
                event_type="act_unlocked_offline",
                payload={"act_id": "act2", "code": "WRONG-CODE"},
            )
            unknown_target = self._sync_one(
                connection,
                event_type="act_unlocked_offline",
                payload={"act_id": "secret_act", "code": "UNLOCK-SECRET"},
            )
            missing_fields = self._sync_one(
                connection,
                event_type="act_unlocked_offline",
                payload={"act_id": "act2"},
            )

        self.assertEqual(invalid_code.results[0].status, "rejected")
        self.assertEqual(invalid_code.results[0].reason, "invalid act unlock code")
        self.assertEqual(unknown_target.results[0].status, "needs_master_review")
        self.assertEqual(unknown_target.results[0].reason, "unknown act unlock target: secret_act")
        self.assertEqual(missing_fields.results[0].status, "rejected")
        self.assertEqual(missing_fields.results[0].reason, "missing act unlock act_id or code")

    def test_pve_sync_rejects_missing_fields_unknown_qr_scenario_mismatch_and_bad_result(self) -> None:
        settings = self._settings("pve_event_rejects")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            response = self._sync_request(
                connection,
                actor_id="p_witcher_1",
                actor_type="player",
                events=[
                    EventSyncEvent(
                        event_id="evt_missing_pve_qr",
                        client_sequence=1,
                        created_at="2026-06-02T09:00:00+00:00",
                        event_type="pve_completed",
                        payload={"scenario_id": "scn_a1_001", "result": "success"},
                    ),
                    EventSyncEvent(
                        event_id="evt_bad_pve_result",
                        client_sequence=2,
                        created_at="2026-06-02T09:01:00+00:00",
                        event_type="pve_completed",
                        payload={"qr_id": "qr_a1_001", "scenario_id": "scn_a1_001", "result": "critical"},
                    ),
                    EventSyncEvent(
                        event_id="evt_unknown_qr",
                        client_sequence=3,
                        created_at="2026-06-02T09:02:00+00:00",
                        event_type="pve_completed",
                        payload={"qr_id": "qr_missing", "scenario_id": "scn_a1_001", "result": "success"},
                    ),
                    EventSyncEvent(
                        event_id="evt_qr_scenario_mismatch",
                        client_sequence=4,
                        created_at="2026-06-02T09:03:00+00:00",
                        event_type="pve_completed",
                        payload={"qr_id": "qr_a1_001", "scenario_id": "scn_a1_002", "result": "success"},
                    ),
                ],
            )
            reviews = {
                row["event_id"]: row["reason"]
                for row in connection.execute(
                    """
                    SELECT event_id, reason
                    FROM event_reviews
                    ORDER BY review_id
                    """
                ).fetchall()
            }
            attempt_count = self._count(connection, "pve_attempts")

        self.assertEqual(
            [result.status for result in response.results],
            ["rejected", "rejected", "needs_master_review", "needs_master_review"],
        )
        self.assertEqual(response.results[0].reason, "missing pve field: qr_id")
        self.assertEqual(response.results[1].reason, "unsupported pve result: critical")
        self.assertEqual(reviews["evt_unknown_qr"], "unknown qr_id: qr_missing")
        self.assertEqual(reviews["evt_qr_scenario_mismatch"], "qr scenario mismatch: qr_a1_001")
        self.assertEqual(attempt_count, 0)

    def test_future_act_pve_with_forged_master_unlock_source_needs_review(self) -> None:
        settings = self._settings("future_pve")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a2_013",
                roll=12,
                unlock_source="master_unlock_code",
                now=datetime(2026, 6, 2, 12, 0, tzinfo=UTC),
            )
            response = self._sync_one(connection, event_type="pve_completed", payload=payload)

        result = response.results[0]
        self.assertEqual(result.status, "needs_master_review")
        self.assertEqual(result.reason, "master unlock code is not revealed for this act")

    def test_pve_completion_without_replayable_roll_log_needs_review(self) -> None:
        settings = self._settings("missing_roll")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            response = self._sync_one(
                connection,
                event_type="pve_completed",
                payload={
                    "qr_id": "qr_a1_001",
                    "scenario_id": "scn_a1_001",
                    "result": "success",
                    "reward_id": "reward_pve_t1",
                    "physical_presence_confirmed": True,
                },
            )
            attempt_count = self._count(connection, "pve_attempts")

        result = response.results[0]
        self.assertEqual(result.status, "needs_master_review")
        self.assertEqual(
            result.reason,
            "pve completion must include exactly one replayable d20 roll_log entry",
        )
        self.assertEqual(attempt_count, 0)

    def test_pve_completion_without_physical_presence_needs_review(self) -> None:
        settings = self._settings("missing_presence")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            payload["physical_presence_confirmed"] = False
            response = self._sync_one(connection, event_type="pve_completed", payload=payload)
            attempt_count = self._count(connection, "pve_attempts")

        result = response.results[0]
        self.assertEqual(result.status, "needs_master_review")
        self.assertEqual(
            result.reason,
            "physical presence confirmation required for physical QR scene",
        )
        self.assertEqual(attempt_count, 0)

    def test_pve_active_cooldown_rejects_new_success_before_reward(self) -> None:
        settings = self._settings("cooldown_reject")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            connection.execute(
                """
                INSERT INTO pve_cooldowns (
                    player_id, qr_id, cooldown_until, reason, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "p_witcher_1",
                    "qr_a1_001",
                    (datetime.now(UTC) + timedelta(hours=1)).isoformat(timespec="seconds"),
                    "pve_failure",
                    datetime.now(UTC).isoformat(timespec="seconds"),
                ),
            )
            response = self._sync_one(connection, event_type="pve_completed", payload=payload)
            attempt_count = self._count(connection, "pve_attempts")

        result = response.results[0]
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason, "pve cooldown active")
        self.assertEqual(attempt_count, 0)

    def test_unique_object_consumption_blocks_duplicate_new_event_ids(self) -> None:
        settings = self._settings("unique_consumption")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            first_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_006",
                roll=9,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            first = self._sync_one(connection, event_type="pve_completed", payload=first_payload)
            second_payload = dict(first_payload)
            second_payload["completed_at"] = "2026-06-02T09:05:00+00:00"
            second = self._sync_one(connection, event_type="pve_completed", payload=second_payload)
            consumed_count = self._count(connection, "pve_consumed_objects")
            approval_count = self._count(connection, "reward_approvals")

        self.assertEqual(first.results[0].status, "pending_master_approval")
        self.assertEqual(second.results[0].status, "needs_master_review")
        self.assertEqual(second.results[0].reason, "unique QR object already consumed")
        self.assertEqual(consumed_count, 1)
        self.assertEqual(approval_count, 1)

    def test_qr_honesty_and_manual_rate_limit_sync_events_enter_master_review(self) -> None:
        settings = self._settings("qr_review_sync")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            response = sync_events(
                connection,
                EventSyncRequest(
                    device_id="phone_wolf",
                    actor_id="p_witcher_1",
                    actor_type="player",
                    events=[
                        EventSyncEvent(
                            event_id=f"evt_{uuid4().hex}",
                            client_sequence=1,
                            created_at="2026-06-02T09:00:00+00:00",
                            event_type="qr_attempt",
                            payload={
                                "local_status": "needs_master_review",
                                "review_reason": "honesty_violation_suspected",
                                "source": "qr_scan",
                                "qr_id": "qr_a1_006",
                                "physical_presence_confirmed": False,
                            },
                        ),
                        EventSyncEvent(
                            event_id=f"evt_{uuid4().hex}",
                            client_sequence=2,
                            created_at="2026-06-02T09:01:00+00:00",
                            event_type="qr_attempt",
                            payload={
                                "local_status": "needs_master_review",
                                "review_reason": "manual_rate_limit",
                                "source": "manual_id",
                                "normalized_code": "NO-SUCH-QR",
                            },
                        ),
                    ],
                ),
            )
            reviews = [
                row["reason"]
                for row in connection.execute(
                    """
                    SELECT reason
                    FROM event_reviews
                    ORDER BY review_id
                    """
                ).fetchall()
            ]
            log_sources = {
                row["source"]
                for row in connection.execute(
                    """
                    SELECT source
                    FROM event_log
                    WHERE event_type = 'qr_attempt'
                    """
                ).fetchall()
            }

        self.assertEqual([result.status for result in response.results], ["needs_master_review", "needs_master_review"])
        self.assertEqual(reviews, ["honesty_violation_suspected", "manual_rate_limit"])
        self.assertEqual(log_sources, {"mobile_qr"})

    def test_event_sync_rejects_invalid_actor_and_is_idempotent_by_event_id(self) -> None:
        settings = self._settings("actor_and_duplicate")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            unknown = self._sync_request(
                connection,
                actor_id="p_missing",
                actor_type="player",
                events=[
                    EventSyncEvent(
                        event_id="evt_unknown_actor",
                        client_sequence=1,
                        created_at="2026-06-02T09:00:00+00:00",
                        event_type="qr_scene_started",
                        payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
                    )
                ],
            )
            mismatch = self._sync_request(
                connection,
                actor_id="p_witcher_1",
                actor_type="lord",
                events=[
                    EventSyncEvent(
                        event_id="evt_actor_mismatch",
                        client_sequence=1,
                        created_at="2026-06-02T09:01:00+00:00",
                        event_type="qr_scene_started",
                        payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
                    )
                ],
            )
            unsupported_actor_type = self._sync_request(
                connection,
                actor_id="p_witcher_1",
                actor_type="merchant",
                events=[
                    EventSyncEvent(
                        event_id="evt_unsupported_actor_type",
                        client_sequence=1,
                        created_at="2026-06-02T09:02:00+00:00",
                        event_type="qr_scene_started",
                        payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
                    )
                ],
            )
            event_id = "evt_idempotent_qr"
            first = self._sync_request(
                connection,
                actor_id="p_witcher_1",
                actor_type="player",
                events=[
                    EventSyncEvent(
                        event_id=event_id,
                        client_sequence=1,
                        created_at="2026-06-02T09:03:00+00:00",
                        event_type="qr_scene_started",
                        payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
                    )
                ],
            )
            duplicate = self._sync_request(
                connection,
                actor_id="p_witcher_1",
                actor_type="player",
                events=[
                    EventSyncEvent(
                        event_id=event_id,
                        client_sequence=2,
                        created_at="2026-06-02T09:04:00+00:00",
                        event_type="qr_scene_started",
                        payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
                    )
                ],
            )
            stored_count = connection.execute(
                "SELECT COUNT(*) FROM events WHERE event_id = ?",
                (event_id,),
            ).fetchone()[0]

        self.assertEqual(unknown.results[0].status, "rejected")
        self.assertEqual(unknown.results[0].reason, "unknown actor_id: p_missing")
        self.assertEqual(mismatch.results[0].status, "rejected")
        self.assertEqual(mismatch.results[0].reason, "actor_type mismatch: lord")
        self.assertEqual(unsupported_actor_type.results[0].status, "rejected")
        self.assertEqual(
            unsupported_actor_type.results[0].reason,
            "unsupported actor_type: merchant",
        )
        self.assertEqual(first.results[0].status, "accepted")
        self.assertEqual(duplicate.results[0].status, "duplicate")
        self.assertEqual(duplicate.results[0].reason, "event_id already processed")
        self.assertEqual(duplicate.results[0].server_event_id, first.results[0].server_event_id)
        self.assertEqual(stored_count, 1)

    def test_event_sync_routes_client_review_unsupported_event_and_unknown_reward_to_review(self) -> None:
        settings = self._settings("event_review_routes")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            response = self._sync_request(
                connection,
                actor_id="p_witcher_1",
                actor_type="player",
                events=[
                    EventSyncEvent(
                        event_id="evt_client_review",
                        client_sequence=1,
                        created_at="2026-06-02T09:00:00+00:00",
                        event_type="qr_scene_started",
                        payload={
                            "requires_master_review": True,
                            "reason": "player reports impossible QR placement",
                            "qr_id": "qr_a1_001",
                        },
                    ),
                    EventSyncEvent(
                        event_id="evt_unsupported_event",
                        client_sequence=2,
                        created_at="2026-06-02T09:01:00+00:00",
                        event_type="unexpected_runtime_event",
                        payload={"some": "payload"},
                    ),
                    EventSyncEvent(
                        event_id="evt_unknown_reward",
                        client_sequence=3,
                        created_at="2026-06-02T09:02:00+00:00",
                        event_type="reward_approval_requested",
                        payload={"reward_id": "reward_missing"},
                    ),
                    EventSyncEvent(
                        event_id="evt_missing_reward",
                        client_sequence=4,
                        created_at="2026-06-02T09:03:00+00:00",
                        event_type="reward_approval_requested",
                        payload={},
                    ),
                ],
            )
            reviews = {
                row["event_id"]: row["reason"]
                for row in connection.execute(
                    """
                    SELECT event_id, reason
                    FROM event_reviews
                    ORDER BY review_id
                    """
                ).fetchall()
            }

        self.assertEqual(
            [result.status for result in response.results],
            ["needs_master_review", "needs_master_review", "needs_master_review", "rejected"],
        )
        self.assertEqual(reviews["evt_client_review"], "player reports impossible QR placement")
        self.assertEqual(
            reviews["evt_unsupported_event"],
            "unsupported event_type: unexpected_runtime_event",
        )
        self.assertEqual(reviews["evt_unknown_reward"], "unknown reward_id: reward_missing")
        self.assertEqual(response.results[3].reason, "missing reward_id")

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def _import_valid_seed(self, settings: Settings) -> None:
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")

    def _sync_one(
        self,
        connection,
        *,
        event_type: str,
        payload: dict[str, object],
    ):
        return sync_events(
            connection,
            EventSyncRequest(
                device_id=f"phone_{uuid4().hex}",
                actor_id="p_witcher_1",
                actor_type="player",
                events=[
                    EventSyncEvent(
                        event_id=f"evt_{uuid4().hex}",
                        client_sequence=1,
                        created_at="2026-06-02T09:00:00+00:00",
                        event_type=event_type,
                        payload=payload,
                    )
                ],
            ),
        )

    def _sync_request(
        self,
        connection,
        *,
        actor_id: str,
        actor_type: str,
        events: list[EventSyncEvent],
    ):
        return sync_events(
            connection,
            EventSyncRequest(
                device_id=f"phone_{uuid4().hex}",
                actor_id=actor_id,
                actor_type=actor_type,
                events=events,
            ),
        )

    def _count(self, connection, table_name: str) -> int:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
