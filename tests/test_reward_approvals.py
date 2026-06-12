from __future__ import annotations

from datetime import UTC, datetime
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.event_models import EventSyncEvent, EventSyncRequest
from backend.witcher_larp.event_service import sync_events
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.pvp_service import ChallengeCreateInput, create_pvp_challenge
from backend.witcher_larp.sorceress_service import SorceressError, create_trade_transfer

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"
MASTER_HEADERS = {"X-Role-Token": "MASTER-KING-4QZ8"}


class RewardApprovalContractTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_master_approval_api_approve_correct_reject_and_invalid_id(self) -> None:
        settings = self.prepare_seed("reward_approval_api")
        with connect(settings) as connection:
            self.request_reward_approval(connection, "evt_approve", "reward_pve_t3")
            self.request_reward_approval(connection, "evt_correct", "reward_artifact_pending")
            self.request_reward_approval(connection, "evt_reject", "reward_final_evidence")

        client = TestClient(create_app(settings))
        approved = client.post(
            "/api/master/reward-approvals/approval_event_1",
            headers=MASTER_HEADERS,
            json={
                "action": "approve",
                "operator": "gm_rewards",
                "reason": "roll log checked",
            },
        )
        duplicate_approved = client.post(
            "/api/master/reward-approvals/approval_event_1",
            headers=MASTER_HEADERS,
            json={
                "action": "approve",
                "operator": "gm_rewards",
                "reason": "double-clicked after checking roll log",
            },
        )
        conflicting_after_final = client.post(
            "/api/master/reward-approvals/approval_event_1",
            headers=MASTER_HEADERS,
            json={
                "action": "reject",
                "operator": "gm_rewards",
                "reason": "changed mind after final decision",
            },
        )
        missing_reason = client.post(
            "/api/master/reward-approvals/approval_event_2",
            headers=MASTER_HEADERS,
            json={
                "action": "correct",
                "operator": "gm_rewards",
                "reason": "   ",
                "correction": {
                    "xp": 1,
                    "gold": 2,
                    "item_ids": "item_final_token",
                    "card_ids": "",
                    "artifact_ids": "",
                },
            },
        )
        corrected = client.post(
            "/api/master/reward-approvals/approval_event_2",
            headers=MASTER_HEADERS,
            json={
                "action": "correct",
                "operator": "gm_rewards",
                "reason": "wrong prop was scanned",
                "correction": {
                    "xp": 1,
                    "gold": 2,
                    "item_ids": "item_final_token",
                    "card_ids": "",
                    "artifact_ids": "",
                },
            },
        )
        rejected = client.post(
            "/api/master/reward-approvals/approval_event_3",
            headers=MASTER_HEADERS,
            json={
                "action": "reject",
                "operator": "gm_rewards",
                "reason": "duplicate paper claim",
            },
        )
        invalid = client.post(
            "/api/master/reward-approvals/missing_approval",
            headers=MASTER_HEADERS,
            json={"action": "approve", "operator": "gm", "reason": "not found"},
        )

        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["status"], "approved")
        self.assertEqual(approved.json()["decision"]["reward_update"]["status"], "applied")
        self.assertEqual(duplicate_approved.status_code, 200)
        self.assertTrue(duplicate_approved.json()["duplicate"])
        self.assertEqual(duplicate_approved.json()["decision"]["status"], "duplicate")
        self.assertEqual(conflicting_after_final.status_code, 409)
        self.assertEqual(
            conflicting_after_final.json()["detail"]["code"],
            "approval_already_decided",
        )
        self.assertEqual(missing_reason.status_code, 400)
        self.assertEqual(missing_reason.json()["detail"]["code"], "missing_audit_reason")
        self.assertEqual(corrected.status_code, 200)
        self.assertEqual(corrected.json()["status"], "corrected")
        self.assertEqual(
            corrected.json()["decision"]["reward_update"]["granted_assets"][0]["asset_id"],
            "item_final_token",
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()["status"], "rejected")
        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(invalid.json()["detail"]["code"], "unknown_reward_approval")

        with connect(settings) as connection:
            ownership = self.asset_quantity(
                connection,
                "p_witcher_1",
                "item",
                "item_monster_trophy",
            )
            corrected_item = self.asset_quantity(
                connection,
                "p_witcher_1",
                "item",
                "item_final_token",
            )
            rejected_artifact = self.asset_quantity(
                connection,
                "p_witcher_1",
                "artifact",
                "artifact_oath_stone",
            )
            audit_count = connection.execute(
                "SELECT COUNT(*) FROM reward_approval_audit"
            ).fetchone()[0]
            active_locks = connection.execute(
                "SELECT COUNT(*) FROM asset_locks WHERE status = 'active'"
            ).fetchone()[0]

        self.assertEqual(ownership, 1)
        self.assertEqual(corrected_item, 1)
        self.assertEqual(rejected_artifact, 0)
        self.assertEqual(audit_count, 3)
        self.assertEqual(active_locks, 0)

    def test_pending_reward_assets_are_blocked_from_pvp_stake_and_trade(self) -> None:
        settings = self.prepare_seed("reward_lock_negatives")
        with connect(settings) as connection:
            start_act(
                connection,
                settings,
                "act1",
                operator="gm_rewards",
                physical_announcement_state="announced",
                now=datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
            )
            self.request_reward_approval(connection, "evt_pending_lock", "reward_pve_t3")

            with self.assertRaisesRegex(Exception, "locked"):
                create_pvp_challenge(
                    connection,
                    ChallengeCreateInput(
                        challenge_id="challenge_pending_reward_stake",
                        challenger_id="p_witcher_1",
                        target_id="p_witcher_2",
                        stake={
                            "asset_type": "item",
                            "asset_id": "item_monster_trophy",
                        },
                    ),
                )
            with self.assertRaisesRegex(SorceressError, "locked"):
                create_trade_transfer(
                    connection,
                    transfer_id="trade_pending_reward_asset",
                    from_player_id="p_witcher_1",
                    to_player_id="p_witcher_2",
                    asset_type="item",
                    asset_id="item_monster_trophy",
                )

            summary = client_summary_payload(connection=None, settings=settings)

        self.assertIn(
            "item_monster_trophy",
            {item["asset_id"] for item in summary["asset_locks"]},
        )
        self.assertIn(
            "reward_approval_lock",
            {item["source_type"] for item in summary["evidence_by_role"]["disputed_objects"]},
        )

    def test_second_pending_reward_for_same_asset_routes_to_review_without_double_lock(self) -> None:
        settings = self.prepare_seed("reward_double_lock_review")
        with connect(settings) as connection:
            self.request_reward_approval(connection, "evt_first_pending_lock", "reward_pve_t3")
            response = sync_events(
                connection,
                EventSyncRequest(
                    device_id=f"phone_{uuid4().hex}",
                    actor_id="p_witcher_2",
                    actor_type="player",
                    events=[
                        EventSyncEvent(
                            event_id="evt_second_pending_lock",
                            client_sequence=1,
                            created_at="2026-06-02T09:05:00+00:00",
                            event_type="reward_approval_requested",
                            payload={"reward_id": "reward_pve_t3"},
                        )
                    ],
                ),
            )
            active_locks = connection.execute(
                """
                SELECT COUNT(*)
                FROM asset_locks
                WHERE asset_type = 'item'
                  AND asset_id = 'item_monster_trophy'
                  AND status = 'active'
                """
            ).fetchone()[0]
            review = connection.execute(
                """
                SELECT reason
                FROM event_reviews
                WHERE event_id = 'evt_second_pending_lock'
                """
            ).fetchone()

        self.assertEqual(response.results[0].status, "needs_master_review")
        self.assertIn("locked", response.results[0].reason)
        self.assertEqual(active_locks, 1)
        self.assertIsNotNone(review)
        self.assertIn("locked", review["reason"])

    def prepare_seed(self, name: str) -> Settings:
        settings = Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")
        return settings

    def request_reward_approval(
        self,
        connection,
        event_id: str,
        reward_id: str,
    ) -> None:
        response = sync_events(
            connection,
            EventSyncRequest(
                device_id=f"phone_{uuid4().hex}",
                actor_id="p_witcher_1",
                actor_type="player",
                events=[
                    EventSyncEvent(
                        event_id=event_id,
                        client_sequence=1,
                        created_at="2026-06-02T09:00:00+00:00",
                        event_type="reward_approval_requested",
                        payload={"reward_id": reward_id},
                    )
                ],
            ),
        )
        self.assertEqual(response.results[0].status, "pending_master_approval")

    @staticmethod
    def asset_quantity(connection, owner: str, asset_type: str, asset_id: str) -> int:
        row = connection.execute(
            """
            SELECT quantity
            FROM asset_ownership
            WHERE owner_player_id = ?
              AND asset_type = ?
              AND asset_id = ?
              AND status = 'active'
            """,
            (owner, asset_type, asset_id),
        ).fetchone()
        return int(row["quantity"]) if row is not None else 0


def client_summary_payload(*, connection, settings: Settings) -> dict[str, object]:
    from backend.witcher_larp.final_summary_service import build_final_summary

    if connection is not None:
        return build_final_summary(connection)
    with connect(settings) as reopened:
        return build_final_summary(reopened)


if __name__ == "__main__":
    unittest.main()
