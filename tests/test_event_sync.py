from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import reveal_unlock_code, start_act
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.event_models import EventSyncEvent, EventSyncRequest
from backend.witcher_larp.event_service import sync_events
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.pve_runtime import (
    PveSideEffectConflictError,
    apply_pve_completion_side_effects,
    resolve_pve_scene,
)


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

    def test_future_act_pve_created_before_reveal_still_needs_review_after_late_sync(self) -> None:
        settings = self._settings("future_pve_late_sync")
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
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a2_013",
                roll=12,
                unlock_source="master_unlock_code",
                now=started_at + timedelta(minutes=2),
            )
            response = sync_events(
                connection,
                EventSyncRequest(
                    device_id="phone_late_future_act",
                    actor_id="p_witcher_1",
                    actor_type="player",
                    events=[
                        EventSyncEvent(
                            event_id="evt_late_future_act",
                            client_sequence=1,
                            created_at="2026-06-02T12:00:00+00:00",
                            event_type="pve_completed",
                            payload=payload,
                        )
                    ],
                ),
            )
            attempt_count = self._count(connection, "pve_attempts")

        result = response.results[0]
        self.assertEqual(result.status, "needs_master_review")
        self.assertEqual(
            result.reason,
            "pve event was created before act unlock was authoritative",
        )
        self.assertEqual(attempt_count, 0)

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

    def test_pve_completion_rejects_forged_reward_id_without_applying_reward(self) -> None:
        settings = self._settings("forged_pve_reward")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            payload["reward_id"] = "reward_pve_t2"
            response = self._sync_one(connection, event_type="pve_completed", payload=payload)
            state = connection.execute(
                """
                SELECT xp, gold
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()
            attempt_count = self._count(connection, "pve_attempts")

        result = response.results[0]
        self.assertEqual(result.status, "needs_master_review")
        self.assertEqual(result.reason, "pve reward_id mismatch for scenario scn_a1_001")
        self.assertEqual(state["xp"], 0)
        self.assertEqual(state["gold"], 20)
        self.assertEqual(attempt_count, 0)

    def test_pve_completion_blank_or_unknown_client_reward_id_routes_to_review(self) -> None:
        for supplied_reward_id in ("", "reward_missing"):
            with self.subTest(supplied_reward_id=supplied_reward_id):
                settings = self._settings("bad_pve_reward")
                self._import_valid_seed(settings)

                with connect(settings) as connection:
                    payload = resolve_pve_scene(
                        connection,
                        player_id="p_witcher_1",
                        qr_id="qr_a1_001",
                        roll=8,
                        now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
                    )
                    payload["reward_id"] = supplied_reward_id
                    response = self._sync_one(
                        connection,
                        event_type="pve_completed",
                        payload=payload,
                    )
                    attempt_count = self._count(connection, "pve_attempts")

                result = response.results[0]
                self.assertEqual(result.status, "needs_master_review")
                self.assertEqual(
                    result.reason,
                    "pve reward_id mismatch for scenario scn_a1_001",
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

    def test_pve_reward_approval_policy_controls_auto_and_pending_outcomes(self) -> None:
        settings = self._settings("pve_reward_policy")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            auto_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            order_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_006",
                roll=20,
                now=datetime(2026, 6, 2, 9, 5, tzinfo=UTC),
            )
            artifact_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_007",
                roll=20,
                now=datetime(2026, 6, 2, 9, 10, tzinfo=UTC),
            )

            auto = self._sync_one(connection, event_type="pve_completed", payload=auto_payload)
            order = self._sync_one(connection, event_type="pve_completed", payload=order_payload)
            artifact = self._sync_one(connection, event_type="pve_completed", payload=artifact_payload)
            attempts = {
                row["qr_id"]: dict(row)
                for row in connection.execute(
                    """
                    SELECT qr_id, reward_id, reward_status
                    FROM pve_attempts
                    ORDER BY server_event_id
                    """
                ).fetchall()
            }
            approvals = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT reward_id, status
                    FROM reward_approvals
                    ORDER BY approval_id
                    """
                ).fetchall()
            ]
            player_state = connection.execute(
                """
                SELECT xp, gold
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()

        self.assertEqual(auto.results[0].status, "accepted")
        self.assertIsNone(auto.results[0].reason)
        self.assertEqual(order.results[0].status, "pending_master_approval")
        self.assertEqual(order.results[0].reason, "reward requires master approval")
        self.assertEqual(artifact.results[0].status, "pending_master_approval")
        self.assertEqual(artifact.results[0].reason, "reward requires master approval")
        self.assertEqual(
            attempts["qr_a1_001"],
            {
                "qr_id": "qr_a1_001",
                "reward_id": "reward_pve_t1",
                "reward_status": "auto",
            },
        )
        self.assertEqual(
            attempts["qr_a1_006"],
            {
                "qr_id": "qr_a1_006",
                "reward_id": "reward_order_success",
                "reward_status": "pending_master_approval",
            },
        )
        self.assertEqual(
            attempts["qr_a1_007"],
            {
                "qr_id": "qr_a1_007",
                "reward_id": "reward_artifact_pending",
                "reward_status": "pending_master_approval",
            },
        )
        self.assertEqual(
            approvals,
            [
                {"reward_id": "reward_order_success", "status": "pending_master_approval"},
                {"reward_id": "reward_artifact_pending", "status": "pending_master_approval"},
            ],
        )
        self.assertEqual(dict(player_state), {"xp": 4, "gold": 30})

    def test_unique_object_side_effect_conflict_does_not_apply_losing_attempt(self) -> None:
        settings = self._settings("unique_side_effect_conflict")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_006",
                roll=9,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            connection.execute(
                """
                INSERT INTO pve_consumed_objects (
                    qr_id, scenario_id, act_id, player_id, source_event_id,
                    consumed_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "qr_a1_006",
                    "scn_a1_006",
                    "act1",
                    "p_witcher_2",
                    None,
                    "2026-06-02T09:00:00+00:00",
                    "{}",
                ),
            )

            with self.assertRaisesRegex(
                PveSideEffectConflictError,
                "unique QR object already consumed",
            ):
                apply_pve_completion_side_effects(
                    connection,
                    player_id="p_witcher_1",
                    payload=payload,
                    metadata={
                        "qr_id": "qr_a1_006",
                        "scenario_id": "scn_a1_006",
                        "act_id": "act1",
                        "qr_mode": "unique_object",
                        "consumption_rule": "consume_once",
                        "reward_id": payload["reward_id"],
                        "reward_status": payload["reward_status"],
                    },
                    status="pending_master_approval",
                    server_event_id=42,
                    now=datetime(2026, 6, 2, 9, 1, tzinfo=UTC),
                )
            attempt_count = self._count(connection, "pve_attempts")
            consumed_count = self._count(connection, "pve_consumed_objects")

        self.assertEqual(attempt_count, 0)
        self.assertEqual(consumed_count, 1)

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

    def test_duplicate_retry_preserves_original_review_rejected_and_pending_status(self) -> None:
        settings = self._settings("duplicate_visible_status")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            review_event = EventSyncEvent(
                event_id="evt_duplicate_review_status",
                client_sequence=1,
                created_at="2026-06-02T09:00:00+00:00",
                event_type="pve_completed",
                payload={
                    "qr_id": "qr_a1_001",
                    "scenario_id": "scn_a1_001",
                    "result": "success",
                    "reward_id": "reward_pve_t1",
                    "physical_presence_confirmed": True,
                },
            )
            rejected_event = EventSyncEvent(
                event_id="evt_duplicate_rejected_status",
                client_sequence=2,
                created_at="2026-06-02T09:01:00+00:00",
                event_type="reward_approval_requested",
                payload={},
            )
            pending_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_006",
                roll=9,
                now=datetime(2026, 6, 2, 9, 2, tzinfo=UTC),
            )
            pending_event = EventSyncEvent(
                event_id="evt_duplicate_pending_status",
                client_sequence=3,
                created_at="2026-06-02T09:02:00+00:00",
                event_type="pve_completed",
                payload=pending_payload,
            )
            first = self._sync_request(
                connection,
                actor_id="p_witcher_1",
                actor_type="player",
                events=[review_event, rejected_event, pending_event],
            )
            retry = self._sync_request(
                connection,
                actor_id="p_witcher_1",
                actor_type="player",
                events=[review_event, rejected_event, pending_event],
            )

        self.assertEqual(
            [result.status for result in first.results],
            ["needs_master_review", "rejected", "pending_master_approval"],
        )
        self.assertEqual(
            [result.status for result in retry.results],
            ["needs_master_review", "rejected", "pending_master_approval"],
        )
        self.assertEqual(
            [result.reason for result in retry.results],
            [result.reason for result in first.results],
        )
        self.assertEqual(
            [result.server_event_id for result in retry.results],
            [result.server_event_id for result in first.results],
        )

    def test_client_sequence_gaps_duplicates_and_out_of_order_batches_are_detected(self) -> None:
        settings = self._settings("sequence_authority")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            first_batch = sync_events(
                connection,
                EventSyncRequest(
                    device_id="phone_sequence_guard",
                    actor_id="p_witcher_1",
                    actor_type="player",
                    events=[
                        EventSyncEvent(
                            event_id="evt_sequence_one",
                            client_sequence=1,
                            created_at="2026-06-02T09:00:00+00:00",
                            event_type="qr_scene_started",
                            payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
                        ),
                        EventSyncEvent(
                            event_id="evt_sequence_gap",
                            client_sequence=3,
                            created_at="2026-06-02T09:01:00+00:00",
                            event_type="qr_scene_started",
                            payload={"qr_id": "qr_a1_002", "local_status": "accepted"},
                        ),
                    ],
                ),
            )
            duplicate_sequence = sync_events(
                connection,
                EventSyncRequest(
                    device_id="phone_sequence_dup",
                    actor_id="p_witcher_1",
                    actor_type="player",
                    events=[
                        EventSyncEvent(
                            event_id="evt_sequence_dup_first",
                            client_sequence=1,
                            created_at="2026-06-02T09:02:00+00:00",
                            event_type="qr_scene_started",
                            payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
                        ),
                        EventSyncEvent(
                            event_id="evt_sequence_dup_second",
                            client_sequence=1,
                            created_at="2026-06-02T09:03:00+00:00",
                            event_type="qr_scene_started",
                            payload={"qr_id": "qr_a1_002", "local_status": "accepted"},
                        ),
                    ],
                ),
            )
            out_of_order = sync_events(
                connection,
                EventSyncRequest(
                    device_id="phone_sequence_guard",
                    actor_id="p_witcher_1",
                    actor_type="player",
                    events=[
                        EventSyncEvent(
                            event_id="evt_sequence_old_new_id",
                            client_sequence=1,
                            created_at="2026-06-02T09:04:00+00:00",
                            event_type="qr_scene_started",
                            payload={"qr_id": "qr_a1_003", "local_status": "accepted"},
                        )
                    ],
                ),
            )
            sync_state = connection.execute(
                """
                SELECT last_event_sequence
                FROM client_sync_state
                WHERE client_id = 'phone_sequence_guard'
                """
            ).fetchone()

        self.assertEqual(
            [result.status for result in first_batch.results],
            ["accepted", "needs_master_review"],
        )
        self.assertEqual(
            first_batch.results[1].reason,
            "client_sequence gap detected: expected 2, got 3",
        )
        self.assertEqual(
            [result.status for result in duplicate_sequence.results],
            ["accepted", "rejected"],
        )
        self.assertEqual(
            duplicate_sequence.results[1].reason,
            "duplicate client_sequence in sync batch: 1",
        )
        self.assertEqual(out_of_order.results[0].status, "rejected")
        self.assertEqual(
            out_of_order.results[0].reason,
            "client_sequence already processed or out of order: 1 < 2",
        )
        self.assertEqual(sync_state["last_event_sequence"], 1)

    def test_player_only_sync_rejects_payload_bound_to_another_player(self) -> None:
        settings = self._settings("wrong_actor_payload")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            response = self._sync_request(
                connection,
                actor_id="p_witcher_1",
                actor_type="player",
                events=[
                    EventSyncEvent(
                        event_id="evt_wrong_payload_player",
                        client_sequence=1,
                        created_at="2026-06-02T09:00:00+00:00",
                        event_type="qr_scene_started",
                        payload={
                            "player_id": "p_witcher_2",
                            "qr_id": "qr_a1_001",
                            "local_status": "accepted",
                        },
                    )
                ],
            )
            review = connection.execute(
                """
                SELECT reason, severity
                FROM event_reviews
                WHERE event_id = 'evt_wrong_payload_player'
                """
            ).fetchone()

        self.assertEqual(response.results[0].status, "rejected")
        self.assertEqual(
            response.results[0].reason,
            "event payload player_id does not match authenticated actor",
        )
        self.assertEqual(review["severity"], "P0")

    def test_player_only_sync_events_use_canonical_role_scope(self) -> None:
        settings = self._settings("player_only_scope")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            lord_attempts = self._sync_request(
                connection,
                actor_id="p_lord_1",
                actor_type="player",
                events=[
                    EventSyncEvent(
                        event_id="evt_lord_pve_as_player",
                        client_sequence=1,
                        created_at="2026-06-02T09:00:00+00:00",
                        event_type="pve_completed",
                        payload={
                            "qr_id": "qr_a1_001",
                            "scenario_id": "scn_a1_001",
                            "result": "success",
                        },
                    ),
                    EventSyncEvent(
                        event_id="evt_lord_qr_as_player",
                        client_sequence=2,
                        created_at="2026-06-02T09:01:00+00:00",
                        event_type="qr_attempt",
                        payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
                    ),
                    EventSyncEvent(
                        event_id="evt_lord_reward_as_player",
                        client_sequence=3,
                        created_at="2026-06-02T09:02:00+00:00",
                        event_type="reward_approval_requested",
                        payload={"reward_id": "reward_pve_t1"},
                    ),
                ],
            )
            npc_attempt = self._sync_request(
                connection,
                actor_id="npc_king",
                actor_type="master",
                events=[
                    EventSyncEvent(
                        event_id="evt_npc_qr_as_player",
                        client_sequence=1,
                        created_at="2026-06-02T09:03:00+00:00",
                        event_type="qr_scene_started",
                        payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
                    )
                ],
            )
            sorceress_qr = self._sync_request(
                connection,
                actor_id="p_sorc_1",
                actor_type="player",
                events=[
                    EventSyncEvent(
                        event_id="evt_sorc_qr_allowed",
                        client_sequence=1,
                        created_at="2026-06-02T09:04:00+00:00",
                        event_type="qr_scene_started",
                        payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
                    )
                ],
            )
            rejected_metadata = [
                json.loads(row["metadata_json"])
                for row in connection.execute(
                    """
                    SELECT metadata_json
                    FROM events
                    WHERE event_id LIKE 'evt_lord_%'
                    ORDER BY server_event_id
                    """
                ).fetchall()
            ]
            review_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM event_reviews
                WHERE event_id IN (
                    'evt_lord_pve_as_player',
                    'evt_lord_qr_as_player',
                    'evt_lord_reward_as_player',
                    'evt_npc_qr_as_player'
                )
                """
            ).fetchone()[0]

        self.assertEqual([result.status for result in lord_attempts.results], ["rejected"] * 3)
        self.assertTrue(
            all(
                "requires witcher or sorceress player actor" in str(result.reason)
                for result in lord_attempts.results
            )
        )
        self.assertEqual(npc_attempt.results[0].status, "rejected")
        self.assertIn(
            "requires witcher or sorceress player actor",
            str(npc_attempt.results[0].reason),
        )
        self.assertEqual(sorceress_qr.results[0].status, "accepted")
        self.assertEqual(
            {metadata["canonical_actor_role_type"] for metadata in rejected_metadata},
            {"lord"},
        )
        self.assertEqual(
            {metadata["auth_boundary"] for metadata in rejected_metadata},
            {"player_only_mobile_event"},
        )
        self.assertEqual(review_count, 4)

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
