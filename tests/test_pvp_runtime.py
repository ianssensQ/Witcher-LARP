from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.app import create_app
from backend.witcher_larp.asset_service import grant_asset_ownership
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.pvp_service import ChallengeCreateInput, ChallengeStartInput, PvpError
from backend.witcher_larp.pvp_service import convert_personal_card_to_lord
from backend.witcher_larp.pvp_service import create_pvp_challenge, finish_gwent_match
from backend.witcher_larp.pvp_service import record_gwent_round, record_pvp_refusal
from backend.witcher_larp.pvp_service import set_pvp_throttle_mode, start_pvp_challenge
from backend.witcher_larp.reward_service import create_pending_reward_approval

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"
MASTER_HEADERS = {"X-Role-Token": "MASTER-KING-4QZ8"}
WITCHER_1_HEADERS = {"X-Player-Code": "WC-WOLF-6GF4"}
WITCHER_2_HEADERS = {"X-Player-Code": "WC-CAT-1HN8"}
WITCHER_3_HEADERS = {"X-Player-Code": "WC-GRIFFIN-7LX2"}
PVP_TEST_STAKE_PLAYERS = (
    "p_witcher_1",
    "p_witcher_2",
    "p_witcher_3",
    "p_witcher_4",
    "p_witcher_5",
    "p_sorc_1",
    "p_sorc_2",
    "p_sorc_3",
)
PVP_TEST_STAKE_ITEMS = (
    "item_gwent_marker",
    "another_marker",
    "stake_banner",
    "foreign_marker",
    "auth_scope_marker",
    "hand_reject_marker",
    "hand_consumption_marker",
    "special_cards_marker",
    "seed_core_effects_marker",
    "rare_specials_marker",
    "round_guardrails_marker",
    "self_rejected_marker",
    "lord_rejected_marker",
    "deck_contract_too_many_mulligans",
    "deck_contract_invalid_leader",
    "deck_contract_unknown_card",
    "deck_contract_special_cap",
    "preflight_invalid_marker",
    "corrupted_deck_marker",
    "stage2_effect_marker",
    "decoy_missing_marker",
    "decoy_hero_marker",
    "tie_marker",
    "partial_finish_marker",
    "in_match_refusal_marker",
    "shared_stake_marker",
    "limited_one",
    "limited_two",
    "paused_marker",
    "after_final_lock",
    "after_final_lock_override",
    "timeout_marker",
    "queue_first_marker",
    "queue_second_marker",
    "refusal_refund_marker",
    "cap_review_first_marker",
    "cap_review_second_marker",
    "invalid_finish_marker",
    "winner_override_marker",
)


class PvpRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def make_settings(self, name: str) -> Settings:
        suffix = uuid4().hex
        return Settings(
            database_path=TEST_TMP_ROOT / f"{name}_{suffix}.db",
            backup_dir=TEST_TMP_ROOT / f"{name}_backups_{suffix}",
        )

    def prepare_seed(
        self,
        name: str,
        *,
        extra_deck_players: tuple[str, ...] = ("p_witcher_2",),
        started_at: datetime | None = None,
    ) -> Settings:
        settings = self.make_settings(name)
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")
        with connect(settings) as connection:
            self.copy_gwent_deck(connection, *extra_deck_players)
            self.grant_pvp_test_stake_assets(connection)
            start_act(
                connection,
                settings,
                "act1",
                operator="gm_pvp",
                physical_announcement_state="announced",
                now=started_at or datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
            )
        return settings

    def grant_pvp_test_stake_assets(self, connection) -> None:
        for asset_id in PVP_TEST_STAKE_ITEMS:
            self.ensure_test_item_asset(connection, asset_id)
            for player_id in PVP_TEST_STAKE_PLAYERS:
                grant_asset_ownership(
                    connection,
                    owner_player_id=player_id,
                    asset_type="item",
                    asset_id=asset_id,
                    source="test_pvp_stake_seed",
                    source_ref_id=asset_id,
                )

    def ensure_test_item_asset(self, connection, asset_id: str) -> None:
        connection.execute(
            """
            INSERT INTO items (
                _import_run_id, _row_number, item_id, item_type, tier,
                stat_requirement_json, effect_json
            )
            SELECT
                COALESCE((SELECT _import_run_id FROM items LIMIT 1), 'test_pvp'),
                COALESCE((SELECT MAX(_row_number) FROM items), 0) + 1,
                ?,
                'pvp_stake',
                1,
                '{}',
                '{"use":"gwent_stake"}'
            WHERE NOT EXISTS (
                SELECT 1 FROM items WHERE item_id = ?
            )
            """,
            (asset_id, asset_id),
        )

    def copy_gwent_deck(self, connection, *player_ids: str) -> None:
        source = connection.execute(
            """
            SELECT *
            FROM gwent_decks
            WHERE player_id = 'p_witcher_1'
            LIMIT 1
            """
        ).fetchone()
        self.assertIsNotNone(source)
        for index, player_id in enumerate(player_ids, start=1):
            connection.execute(
                """
                INSERT INTO gwent_decks (
                    _import_run_id, _row_number, deck_id, player_id,
                    leader_card_id, card_ids
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source["_import_run_id"],
                    900 + index,
                    f"deck_{player_id}",
                    player_id,
                    source["leader_card_id"],
                    source["card_ids"],
                ),
            )

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_challenge_spends_token_assigns_table_and_blocks_second_active(self) -> None:
        settings = self.prepare_seed(
            "pvp_api_challenge",
            extra_deck_players=("p_witcher_2", "p_witcher_3"),
        )
        client = TestClient(create_app(settings))

        created = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenge_id": "challenge_token_demo",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {
                    "asset_type": "item",
                    "asset_id": "item_gwent_marker",
                    "transfer_on_finish": True,
                },
            },
        )

        self.assertEqual(created.status_code, 200)
        payload = created.json()
        self.assertEqual(payload["status"], "assigned")
        self.assertEqual(payload["table_id"], "pvp_table_1")
        self.assertEqual(payload["assigned_zone"], "main_house_table")
        self.assertEqual(payload["stake"]["status"], "locked")
        self.assertIn("start_window_deadline", payload)

        duplicate = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenge_id": "challenge_token_demo",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {"asset_type": "item", "asset_id": "item_gwent_marker"},
            },
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])

        second_active = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_3",
                "stake": {"asset_type": "item", "asset_id": "another_marker"},
            },
        )
        self.assertEqual(second_active.status_code, 400)
        self.assertIn("active PvP challenge", second_active.json()["detail"])

        with connect(settings) as connection:
            tokens = connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()["challenge_tokens"]
        self.assertEqual(tokens, 2)

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_full_gwent_rounds_finish_and_duplicate_result(self) -> None:
        settings = self.prepare_seed("pvp_api_match", extra_deck_players=("p_witcher_2",))
        client = TestClient(create_app(settings))
        challenge = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenge_id": "challenge_match_demo",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {"asset_type": "item", "asset_id": "stake_banner"},
            },
        ).json()
        started = client.post(
            f"/api/pvp/challenges/{challenge['challenge_id']}/start",
            headers=WITCHER_1_HEADERS,
            json={"mulligans_by_player": {"p_witcher_1": ["gwent_unit_01"]}},
        )

        self.assertEqual(started.status_code, 200)
        match = started.json()["match"]
        match_id = match["match_id"]
        self.assertEqual(match["status"], "active")
        self.assertEqual(len(match["deck_state"]["p_witcher_1"]["hand"]), 10)
        self.assertEqual(match["deck_state"]["p_witcher_1"]["mulligans"], ["gwent_unit_01"])
        self.assertFalse(match["deck_state"]["cards_burn_after_round"])

        first_round = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=MASTER_HEADERS,
            json={
                "round_number": 1,
                "plays": [
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_02"},
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_03"},
                    {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                ],
                "passed": {"p_witcher_1": True, "p_witcher_2": True},
            },
        )
        self.assertEqual(first_round.status_code, 200)
        round_payload = first_round.json()["round"]
        self.assertEqual(round_payload["winner_id"], "p_witcher_1")
        self.assertEqual(round_payload["row_scores"]["p_witcher_1"]["melee"], 9)
        self.assertEqual(round_payload["row_scores"]["p_witcher_2"]["melee"], 4)
        self.assertFalse(round_payload["round_state"]["cards_burned"])
        first_match = first_round.json()["match"]
        self.assertNotIn("gwent_unit_02", first_match["deck_state"]["p_witcher_1"]["hand"])
        self.assertIn("gwent_unit_02", first_match["deck_state"]["p_witcher_1"]["graveyard"])

        second_round = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=MASTER_HEADERS,
            json={
                "round_number": 2,
                "plays": [
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_07"},
                    {"player_id": "p_witcher_2", "card_id": "gwent_unit_02"},
                    {"player_id": "p_witcher_2", "card_id": "gwent_unit_03"},
                ],
            },
        )
        self.assertEqual(second_round.status_code, 200)
        self.assertEqual(second_round.json()["round"]["winner_id"], "p_witcher_2")

        third_round = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=MASTER_HEADERS,
            json={
                "round_number": 3,
                "plays": [
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_04"},
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_05"},
                    {"player_id": "p_witcher_2", "card_id": "gwent_unit_04"},
                ],
            },
        )
        self.assertEqual(third_round.status_code, 200)
        self.assertEqual(third_round.json()["match"]["status"], "awaiting_finish")
        self.assertEqual(third_round.json()["match"]["winner_id"], "p_witcher_1")

        finished = client.post(
            f"/api/pvp/matches/{match_id}/finish",
            headers=MASTER_HEADERS,
            json={"winner_id": "p_witcher_1"},
        )
        duplicate_finish = client.post(
            f"/api/pvp/matches/{match_id}/finish",
            headers=MASTER_HEADERS,
            json={"winner_id": "p_witcher_1"},
        )

        self.assertEqual(finished.status_code, 200)
        finish_payload = finished.json()
        self.assertEqual(finish_payload["match"]["status"], "finished")
        self.assertEqual(finish_payload["stake_transfer"]["status"], "applied")
        self.assertFalse(finish_payload["duplicate"])
        self.assertEqual(duplicate_finish.status_code, 200)
        self.assertTrue(duplicate_finish.json()["duplicate"])
        self.assertTrue(
            finish_payload["match"]["balance_report"]["no_match_time_limit_after_start"]
        )

        tables = client.get("/api/pvp/tables").json()
        self.assertEqual(tables["tables"][0]["status"], "open")
        with connect(settings) as connection:
            winner_quantity = connection.execute(
                """
                SELECT quantity
                FROM asset_ownership
                WHERE owner_player_id = 'p_witcher_1'
                  AND asset_type = 'item'
                  AND asset_id = 'stake_banner'
                  AND status = 'active'
                """
            ).fetchone()["quantity"]
            active_stake_locks = connection.execute(
                """
                SELECT COUNT(*)
                FROM asset_locks
                WHERE lock_type = 'pvp_stake'
                  AND source_ref_id = 'challenge_match_demo'
                  AND status = 'active'
                """
            ).fetchone()[0]
        self.assertEqual(winner_quantity, 1)
        self.assertEqual(active_stake_locks, 0)

    def test_gold_stakes_reserve_refund_settle_and_reject_insufficient_balance(self) -> None:
        settings = self.prepare_seed(
            "pvp_gold_stakes",
            extra_deck_players=(
                "p_witcher_2",
                "p_witcher_3",
                "p_witcher_4",
                "p_witcher_5",
                "p_sorc_1",
            ),
        )
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE player_runtime_state
                SET gold = CASE player_id
                    WHEN 'p_witcher_1' THEN 25
                    WHEN 'p_witcher_3' THEN 50
                    WHEN 'p_witcher_4' THEN 20
                    WHEN 'p_witcher_5' THEN 4
                    ELSE gold
                END
                WHERE player_id IN ('p_witcher_1', 'p_witcher_3', 'p_witcher_4', 'p_witcher_5')
                """
            )

            cancelled = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_gold_cancel",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "gold", "amount": 10},
                ),
            )
            reserved_gold = connection.execute(
                "SELECT gold FROM player_runtime_state WHERE player_id = 'p_witcher_1'"
            ).fetchone()["gold"]
            refused = record_pvp_refusal(
                connection,
                cancelled["challenge_id"],
                reason="safety_stop",
                actor_id="p_witcher_2",
            )
            refunded_gold = connection.execute(
                "SELECT gold FROM player_runtime_state WHERE player_id = 'p_witcher_1'"
            ).fetchone()["gold"]
            refunded_stake = connection.execute(
                """
                SELECT status, asset_type, asset_id, quantity
                FROM pvp_stake_ledger
                WHERE challenge_id = 'challenge_gold_cancel'
                """
            ).fetchone()

            self.assertEqual(cancelled["stake"]["asset_type"], "gold")
            self.assertEqual(cancelled["stake"]["quantity"], 10)
            self.assertEqual(reserved_gold, 15)
            self.assertEqual(refused["status"], "needs_master_review")
            self.assertEqual(refunded_gold, 25)
            self.assertEqual(
                dict(refunded_stake),
                {
                    "status": "refunded",
                    "asset_type": "gold",
                    "asset_id": "gold",
                    "quantity": 10,
                },
            )

            p5_tokens_before = connection.execute(
                "SELECT challenge_tokens FROM player_runtime_state WHERE player_id = 'p_witcher_5'"
            ).fetchone()["challenge_tokens"]
            with self.assertRaisesRegex(PvpError, "does not have enough gold"):
                create_pvp_challenge(
                    connection,
                    ChallengeCreateInput(
                        challenge_id="challenge_gold_insufficient",
                        challenger_id="p_witcher_5",
                        target_id="p_sorc_1",
                        stake={"asset_type": "gold", "amount": 6},
                    ),
                )
            p5_tokens_after = connection.execute(
                "SELECT challenge_tokens FROM player_runtime_state WHERE player_id = 'p_witcher_5'"
            ).fetchone()["challenge_tokens"]
            rejected_count = connection.execute(
                "SELECT COUNT(*) FROM pvp_challenges WHERE challenge_id = 'challenge_gold_insufficient'"
            ).fetchone()[0]

            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_gold_finish",
                    challenger_id="p_witcher_3",
                    target_id="p_witcher_4",
                    stake={"asset_type": "gold", "amount": 15},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            match_id = started["match"]["match_id"]
            record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_3", "card_id": "gwent_unit_01"},
                        {"player_id": "p_witcher_4", "card_id": "gwent_unit_02"},
                        {"player_id": "p_witcher_4", "card_id": "gwent_unit_03"},
                    ],
                    "passed": {"p_witcher_3": True, "p_witcher_4": True},
                },
                round_number=1,
            )
            second_round = record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_3", "card_id": "gwent_unit_04"},
                        {"player_id": "p_witcher_4", "card_id": "gwent_unit_04"},
                        {"player_id": "p_witcher_4", "card_id": "gwent_unit_05"},
                    ],
                    "passed": {"p_witcher_3": True, "p_witcher_4": True},
                },
                round_number=2,
            )
            finished = finish_gwent_match(connection, match_id, winner_id="p_witcher_4")
            duplicate_finish = finish_gwent_match(connection, match_id, winner_id="p_witcher_4")
            balances = {
                row["player_id"]: row["gold"]
                for row in connection.execute(
                    """
                    SELECT player_id, gold
                    FROM player_runtime_state
                    WHERE player_id IN ('p_witcher_3', 'p_witcher_4')
                    """
                ).fetchall()
            }
            settled_stake = connection.execute(
                """
                SELECT status, quantity, winner_id, loser_id
                FROM pvp_stake_ledger
                WHERE challenge_id = 'challenge_gold_finish'
                """
            ).fetchone()

        self.assertEqual(p5_tokens_after, p5_tokens_before)
        self.assertEqual(rejected_count, 0)
        self.assertEqual(second_round["match"]["status"], "awaiting_finish")
        self.assertEqual(second_round["match"]["winner_id"], "p_witcher_4")
        self.assertEqual(finished["stake_transfer"]["status"], "applied")
        self.assertFalse(finished["duplicate"])
        self.assertTrue(duplicate_finish["duplicate"])
        self.assertEqual(balances, {"p_witcher_3": 35, "p_witcher_4": 35})
        self.assertEqual(
            dict(settled_stake),
            {
                "status": "applied",
                "quantity": 15,
                "winner_id": "p_witcher_4",
                "loser_id": "p_witcher_3",
            },
        )

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_player_gwent_round_waits_for_opponent_submission(self) -> None:
        settings = self.prepare_seed("pvp_api_two_client_round", extra_deck_players=("p_witcher_2",))
        client = TestClient(create_app(settings))
        challenge = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenge_id": "challenge_two_client_round",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {"asset_type": "item", "asset_id": "round_guardrails_marker"},
            },
        ).json()
        started = client.post(
            f"/api/pvp/challenges/{challenge['challenge_id']}/start",
            headers=WITCHER_1_HEADERS,
            json={},
        )
        self.assertEqual(started.status_code, 200, started.text)
        match_id = started.json()["match"]["match_id"]

        first_submit = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=WITCHER_1_HEADERS,
            json={
                "round_number": 1,
                "plays": [
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_02"},
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_03"},
                ],
                "passed": {"p_witcher_1": True},
            },
        )
        self.assertEqual(first_submit.status_code, 200, first_submit.text)
        pending_payload = first_submit.json()
        self.assertIsNone(pending_payload["round"]["winner_id"])
        self.assertEqual(pending_payload["match"]["status"], "active")
        self.assertEqual(pending_payload["round"]["round_state"]["status"], "pending_player_submissions")
        self.assertEqual(pending_payload["round"]["round_state"]["ready_players"], ["p_witcher_1"])
        self.assertEqual(pending_payload["round"]["round_state"]["missing_players"], ["p_witcher_2"])
        self.assertIn(
            "gwent_unit_02",
            pending_payload["match"]["deck_state"]["p_witcher_1"]["hand"],
        )

        second_submit = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=WITCHER_2_HEADERS,
            json={
                "round_number": 1,
                "plays": [{"player_id": "p_witcher_2", "card_id": "gwent_unit_01"}],
                "passed": {"p_witcher_2": True},
            },
        )
        self.assertEqual(second_submit.status_code, 200, second_submit.text)
        resolved_payload = second_submit.json()
        self.assertFalse(resolved_payload["duplicate"])
        self.assertEqual(resolved_payload["round"]["winner_id"], "p_witcher_1")
        self.assertEqual(resolved_payload["round"]["row_scores"]["p_witcher_1"]["melee"], 9)
        self.assertEqual(resolved_payload["round"]["row_scores"]["p_witcher_2"]["melee"], 4)
        self.assertNotIn(
            "gwent_unit_02",
            resolved_payload["match"]["deck_state"]["p_witcher_1"]["hand"],
        )
        self.assertIn(
            "gwent_unit_02",
            resolved_payload["match"]["deck_state"]["p_witcher_1"]["graveyard"],
        )

        duplicate_submit = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=WITCHER_2_HEADERS,
            json={
                "round_number": 1,
                "plays": [{"player_id": "p_witcher_2", "card_id": "gwent_unit_01"}],
                "passed": {"p_witcher_2": True},
            },
        )
        self.assertEqual(duplicate_submit.status_code, 200, duplicate_submit.text)
        self.assertTrue(duplicate_submit.json()["duplicate"])

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_master_incomplete_gwent_round_goes_to_review_without_stake_transfer(self) -> None:
        settings = self.prepare_seed("pvp_api_master_incomplete_round", extra_deck_players=("p_witcher_2",))
        client = TestClient(create_app(settings))
        challenge = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenge_id": "challenge_master_incomplete_round",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {"asset_type": "item", "asset_id": "partial_finish_marker"},
            },
        ).json()
        started = client.post(
            f"/api/pvp/challenges/{challenge['challenge_id']}/start",
            headers=WITCHER_1_HEADERS,
            json={},
        )
        self.assertEqual(started.status_code, 200, started.text)
        match_id = started.json()["match"]["match_id"]

        incomplete_round = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=MASTER_HEADERS,
            json={
                "round_number": 1,
                "plays": [{"player_id": "p_witcher_1", "card_id": "gwent_unit_02"}],
                "passed": {"p_witcher_1": True},
            },
        )
        self.assertEqual(incomplete_round.status_code, 200, incomplete_round.text)
        round_payload = incomplete_round.json()["round"]
        match_payload = incomplete_round.json()["match"]
        self.assertTrue(round_payload["review_required"])
        self.assertEqual(round_payload["round_state"]["status"], "needs_master_review")
        self.assertEqual(
            round_payload["round_state"]["review_reason"],
            "incomplete_round_requires_master_review",
        )
        self.assertEqual(match_payload["status"], "needs_master_review")
        self.assertEqual(match_payload["review_reason"], "incomplete_round_requires_master_review")

        finish = client.post(
            f"/api/pvp/matches/{match_id}/finish",
            headers=MASTER_HEADERS,
            json={"winner_id": "p_witcher_1"},
        )
        self.assertEqual(finish.status_code, 200, finish.text)
        self.assertEqual(finish.json()["stake_transfer"]["status"], "not_applied")
        with connect(settings) as connection:
            review_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM pvp_reviews
                WHERE match_id = ?
                  AND reason = 'incomplete_round_requires_master_review'
                """,
                (match_id,),
            ).fetchone()[0]
            stake = connection.execute(
                """
                SELECT status, winner_id
                FROM pvp_stake_ledger
                WHERE challenge_id = 'challenge_master_incomplete_round'
                """
            ).fetchone()
        self.assertEqual(review_count, 1)
        self.assertEqual(stake["status"], "locked")
        self.assertIsNone(stake["winner_id"])

    def test_challenge_rejects_non_owned_and_missing_stake_without_token_table_or_lock(self) -> None:
        settings = self.prepare_seed("pvp_stake_ownership_negative", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            self.ensure_test_item_asset(connection, "stake_owned_by_other")
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_2",
                asset_type="item",
                asset_id="stake_owned_by_other",
                source="test_pvp_negative",
                source_ref_id="stake_owned_by_other",
            )
            tokens_before = connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()["challenge_tokens"]

            with self.assertRaisesRegex(PvpError, "does not own PvP stake asset"):
                create_pvp_challenge(
                    connection,
                    ChallengeCreateInput(
                        challenge_id="challenge_non_owned_stake",
                        challenger_id="p_witcher_1",
                        target_id="p_witcher_2",
                        stake={"asset_type": "item", "asset_id": "stake_owned_by_other"},
                    ),
                )
            with self.assertRaisesRegex(PvpError, "Unknown PvP stake asset"):
                create_pvp_challenge(
                    connection,
                    ChallengeCreateInput(
                        challenge_id="challenge_missing_stake",
                        challenger_id="p_witcher_1",
                        target_id="p_witcher_2",
                        stake={"asset_type": "item", "asset_id": "stake_missing_marker"},
                    ),
                )

            tokens_after = connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()["challenge_tokens"]
            challenge_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM pvp_challenges
                WHERE challenge_id IN ('challenge_non_owned_stake', 'challenge_missing_stake')
                """
            ).fetchone()[0]
            stake_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM pvp_stake_ledger
                WHERE challenge_id IN ('challenge_non_owned_stake', 'challenge_missing_stake')
                """
            ).fetchone()[0]
            active_stake_locks = connection.execute(
                """
                SELECT COUNT(*)
                FROM asset_locks
                WHERE lock_type = 'pvp_stake'
                  AND source_ref_id IN ('challenge_non_owned_stake', 'challenge_missing_stake')
                """
            ).fetchone()[0]
            occupied_tables = connection.execute(
                """
                SELECT COUNT(*)
                FROM pvp_table_runtime
                WHERE status = 'occupied'
                """
            ).fetchone()[0]

        self.assertEqual(tokens_after, tokens_before)
        self.assertEqual(challenge_count, 0)
        self.assertEqual(stake_count, 0)
        self.assertEqual(active_stake_locks, 0)
        self.assertEqual(occupied_tables, 0)

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_losing_participant_cannot_override_authoritative_winner(self) -> None:
        settings = self.prepare_seed("pvp_api_winner_override", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            self.ensure_test_item_asset(connection, "winner_override_private_marker")
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="winner_override_private_marker",
                source="test_pvp_winner_override",
                source_ref_id="winner_override_private_marker",
            )
        client = TestClient(create_app(settings))
        challenge = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenge_id": "challenge_winner_override",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {"asset_type": "item", "asset_id": "winner_override_private_marker"},
            },
        ).json()
        started = client.post(
            f"/api/pvp/challenges/{challenge['challenge_id']}/start",
            headers=WITCHER_1_HEADERS,
            json={},
        ).json()
        match_id = started["match"]["match_id"]
        first_round = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=MASTER_HEADERS,
            json={
                "round_number": 1,
                "plays": [
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_02"},
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_03"},
                    {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                ],
            },
        )
        second_round = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=MASTER_HEADERS,
            json={
                "round_number": 2,
                "plays": [
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_04"},
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_05"},
                    {"player_id": "p_witcher_2", "card_id": "gwent_unit_02"},
                ],
            },
        )
        loser_finish = client.post(
            f"/api/pvp/matches/{match_id}/finish",
            headers=WITCHER_2_HEADERS,
            json={"winner_id": "p_witcher_2"},
        )

        self.assertEqual(first_round.status_code, 200, first_round.text)
        self.assertEqual(second_round.status_code, 200, second_round.text)
        self.assertEqual(second_round.json()["match"]["winner_id"], "p_witcher_1")
        self.assertEqual(loser_finish.status_code, 200, loser_finish.text)
        finish_payload = loser_finish.json()
        self.assertEqual(finish_payload["match"]["status"], "needs_master_review")
        self.assertEqual(finish_payload["match"]["winner_id"], "p_witcher_1")
        self.assertEqual(finish_payload["match"]["review_reason"], "winner_override_requires_master_review")
        self.assertEqual(finish_payload["stake_transfer"]["status"], "not_applied")
        with connect(settings) as connection:
            stake = connection.execute(
                """
                SELECT status, winner_id
                FROM pvp_stake_ledger
                WHERE challenge_id = 'challenge_winner_override'
                """
            ).fetchone()
            loser_quantity = connection.execute(
                """
                SELECT COUNT(*)
                FROM asset_ownership
                WHERE owner_player_id = 'p_witcher_2'
                  AND asset_type = 'item'
                  AND asset_id = 'winner_override_private_marker'
                  AND status = 'active'
                """
            ).fetchone()[0]
        self.assertEqual(stake["status"], "locked")
        self.assertIsNone(stake["winner_id"])
        self.assertEqual(loser_quantity, 0)

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_pvp_error_and_master_throttle_contracts_are_explicit(self) -> None:
        settings = self.prepare_seed("pvp_api_errors", extra_deck_players=("p_witcher_2",))
        client = TestClient(create_app(settings))

        missing_start = client.post(
            "/api/pvp/challenges/no_such_challenge/start",
            headers=WITCHER_1_HEADERS,
            json={},
        )
        missing_round = client.post(
            "/api/pvp/matches/no_such_match/rounds",
            headers=WITCHER_1_HEADERS,
            json={"plays": []},
        )
        missing_finish = client.post(
            "/api/pvp/matches/no_such_match/finish",
            headers=WITCHER_1_HEADERS,
            json={},
        )
        missing_refusal = client.post(
            "/api/pvp/challenges/no_such_challenge/refusal",
            headers=WITCHER_2_HEADERS,
            json={"reason": "active_scene", "actor_id": "p_witcher_2"},
        )
        invalid_conversion = client.post(
            "/api/pvp/card-conversions",
            headers=WITCHER_1_HEADERS,
            json={
                "player_id": "p_witcher_1",
                "lord_id": "p_witcher_2",
                "personal_card_id": "pc_infantry_t1",
            },
        )
        missing_master = client.post("/api/master/pvp-throttle", json={"mode": "paused"})
        accepted_throttle = client.post(
            "/api/master/pvp-throttle",
            headers={"X-Role-Token": "MASTER-KING-4QZ8"},
            json={"mode": "limited", "operator": "gm_pvp"},
        )
        invalid_throttle = client.post(
            "/api/master/pvp-throttle",
            headers={"X-Role-Token": "MASTER-KING-4QZ8"},
            json={"mode": "storm", "operator": "gm_pvp"},
        )

        self.assertEqual(missing_start.status_code, 400)
        self.assertIn("Unknown PvP challenge", missing_start.json()["detail"])
        self.assertEqual(missing_round.status_code, 400)
        self.assertIn("Unknown Gwent match", missing_round.json()["detail"])
        self.assertEqual(missing_finish.status_code, 400)
        self.assertIn("Unknown Gwent match", missing_finish.json()["detail"])
        self.assertEqual(missing_refusal.status_code, 400)
        self.assertIn("Unknown PvP challenge", missing_refusal.json()["detail"])
        self.assertEqual(invalid_conversion.status_code, 400)
        self.assertIn("Unknown lord player", invalid_conversion.json()["detail"])
        self.assertEqual(missing_master.status_code, 401)
        self.assertEqual(accepted_throttle.status_code, 200)
        self.assertEqual(accepted_throttle.json()["throttle"]["mode"], "limited")
        self.assertEqual(invalid_throttle.status_code, 400)
        self.assertIn("Unsupported PvP throttle mode", invalid_throttle.json()["detail"])

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_pvp_mutations_reject_foreign_auth_payload_ids(self) -> None:
        settings = self.prepare_seed(
            "pvp_api_auth_scope",
            extra_deck_players=("p_witcher_2", "p_witcher_3"),
        )
        client = TestClient(create_app(settings))

        foreign_create = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_2_HEADERS,
            json={
                "challenge_id": "challenge_foreign_create",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {"asset_type": "item", "asset_id": "foreign_marker"},
            },
        )
        created = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenge_id": "challenge_auth_scope",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {"asset_type": "item", "asset_id": "auth_scope_marker"},
            },
        )
        foreign_start = client.post(
            "/api/pvp/challenges/challenge_auth_scope/start",
            headers=WITCHER_3_HEADERS,
            json={},
        )
        started = client.post(
            "/api/pvp/challenges/challenge_auth_scope/start",
            headers=WITCHER_1_HEADERS,
            json={},
        )
        match_id = started.json()["match"]["match_id"]
        foreign_round_payload = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=WITCHER_1_HEADERS,
            json={
                "round_number": 1,
                "plays": [{"player_id": "p_witcher_2", "card_id": "gwent_unit_01"}],
            },
        )
        foreign_finish_winner = client.post(
            f"/api/pvp/matches/{match_id}/finish",
            headers=WITCHER_2_HEADERS,
            json={"winner_id": "p_witcher_1"},
        )
        foreign_refusal_actor = client.post(
            "/api/pvp/challenges/challenge_auth_scope/refusal",
            headers=WITCHER_2_HEADERS,
            json={"actor_id": "p_witcher_1", "reason": "active_scene"},
        )
        foreign_conversion = client.post(
            "/api/pvp/card-conversions",
            headers=WITCHER_2_HEADERS,
            json={
                "player_id": "p_witcher_1",
                "lord_id": "p_lord_1",
                "personal_card_id": "pc_infantry_t1",
            },
        )

        self.assertEqual(foreign_create.status_code, 403)
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(foreign_start.status_code, 403)
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(foreign_round_payload.status_code, 403)
        self.assertEqual(foreign_finish_winner.status_code, 403)
        self.assertEqual(foreign_refusal_actor.status_code, 403)
        self.assertEqual(foreign_conversion.status_code, 403)

    def test_gwent_rejects_card_not_in_current_hand_and_replayed_card(self) -> None:
        settings = self.prepare_seed("pvp_hand_rejects", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_hand_rejects",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "hand_reject_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            match_id = started["match"]["match_id"]

            with self.assertRaisesRegex(PvpError, "not in current hand"):
                record_gwent_round(
                    connection,
                    match_id,
                    {"plays": [{"player_id": "p_witcher_1", "card_id": "gwent_unit_11"}]},
                    round_number=1,
                )

            record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_01"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_02"},
                    ]
                },
                round_number=1,
            )
            with self.assertRaisesRegex(PvpError, "not in current hand"):
                record_gwent_round(
                    connection,
                    match_id,
                    {"plays": [{"player_id": "p_witcher_1", "card_id": "gwent_unit_01"}]},
                    round_number=2,
                )

    def test_gwent_legal_hand_consumption_across_rounds(self) -> None:
        settings = self.prepare_seed("pvp_hand_consumption", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_hand_consumption",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "hand_consumption_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            match_id = started["match"]["match_id"]

            first = record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_01"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                    ]
                },
                round_number=1,
            )
            self.assertNotIn("gwent_unit_01", first["match"]["deck_state"]["p_witcher_1"]["hand"])
            self.assertIn("gwent_unit_01", first["match"]["deck_state"]["p_witcher_1"]["graveyard"])

            second = record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_02"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_02"},
                    ]
                },
                round_number=2,
            )
            self.assertNotIn("gwent_unit_02", second["match"]["deck_state"]["p_witcher_2"]["hand"])
            self.assertIn("gwent_unit_02", second["match"]["deck_state"]["p_witcher_2"]["graveyard"])

    def test_gwent_special_cards_apply_weather_horn_scorch_and_decoy_rules(self) -> None:
        settings = self.prepare_seed("pvp_special_cards", extra_deck_players=("p_witcher_2",))
        units = [f"gwent_unit_{index:02d}" for index in range(1, 23)]
        p1_cards = [
            "gwent_unit_01",
            "gwent_unit_02",
            "gwent_decoy",
            "gwent_horn",
            "gwent_weather_frost",
            "gwent_scorch",
            *[card_id for card_id in units if card_id not in {"gwent_unit_01", "gwent_unit_02"}],
        ]
        p2_cards = [
            "gwent_unit_11",
            "rare_gwent_01",
            *[card_id for card_id in units if card_id != "gwent_unit_11"],
        ]
        with connect(settings) as connection:
            connection.execute(
                "UPDATE gwent_cards SET strength = 10 WHERE card_id = 'gwent_unit_11'"
            )
            connection.execute(
                "UPDATE gwent_decks SET card_ids = ? WHERE player_id = 'p_witcher_1'",
                (";".join(p1_cards),),
            )
            connection.execute(
                "UPDATE gwent_decks SET card_ids = ? WHERE player_id = 'p_witcher_2'",
                (";".join(p2_cards),),
            )
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_special_cards",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "special_cards_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            match_id = started["match"]["match_id"]

            result = record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_01"},
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_02"},
                        {
                            "player_id": "p_witcher_1",
                            "card_id": "gwent_decoy",
                            "target_card_id": "gwent_unit_01",
                        },
                        {"player_id": "p_witcher_1", "card_id": "gwent_horn", "row": "melee"},
                        {"player_id": "p_witcher_1", "card_id": "gwent_weather_frost"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_11"},
                        {"player_id": "p_witcher_2", "card_id": "rare_gwent_01"},
                        {"player_id": "p_witcher_1", "card_id": "gwent_scorch"},
                    ]
                },
                round_number=1,
            )

        round_state = result["round"]["round_state"]
        effects = round_state["effects_applied"]
        scorch = next(item for item in effects if item["scope"] == "scorch")
        self.assertIn(
            {"card_id": "gwent_weather_frost", "effect": "weather_melee", "scope": "special"},
            effects,
        )
        self.assertIn(
            {"card_id": "gwent_horn", "effect": "commanders_horn", "scope": "special"},
            effects,
        )
        self.assertIn(
            {"card_id": "gwent_decoy", "effect": "decoy", "scope": "special"},
            effects,
        )
        self.assertEqual(scorch["removed_card_ids"], ["gwent_unit_11"])
        self.assertEqual(round_state["weather_rows"], ["melee"])
        self.assertEqual(round_state["horn_rows"]["p_witcher_1"], ["melee"])
        self.assertEqual(round_state["returned_cards"], [{"player_id": "p_witcher_1", "card_id": "gwent_unit_01"}])
        self.assertEqual(result["round"]["row_scores"]["p_witcher_1"]["melee"], 2)
        self.assertEqual(result["round"]["row_scores"]["p_witcher_2"]["melee"], 10)
        self.assertEqual(result["round"]["winner_id"], "p_witcher_2")
        self.assertIn("gwent_unit_01", result["match"]["deck_state"]["p_witcher_1"]["hand"])
        self.assertNotIn("gwent_unit_01", result["match"]["deck_state"]["p_witcher_1"]["graveyard"])
        self.assertIn("gwent_decoy", result["match"]["deck_state"]["p_witcher_1"]["graveyard"])

    def test_gwent_seed_core_effects_spy_medic_muster_and_leader_apply(self) -> None:
        settings = self.prepare_seed("pvp_seed_core_effects", extra_deck_players=("p_witcher_2",))
        units = [f"gwent_unit_{index:02d}" for index in range(1, 23)]
        priority_cards = [
            "gwent_unit_01",
            "gwent_unit_06",
            "gwent_unit_09",
            "gwent_unit_19",
            "gwent_unit_20",
            "gwent_unit_02",
            "gwent_unit_03",
            "gwent_unit_04",
            "gwent_unit_05",
            "gwent_unit_07",
        ]
        p1_cards = [*priority_cards, *[card_id for card_id in units if card_id not in priority_cards]]
        with connect(settings) as connection:
            connection.execute(
                "UPDATE gwent_decks SET card_ids = ? WHERE player_id = 'p_witcher_1'",
                (";".join(p1_cards),),
            )
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_seed_core_effects",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "seed_core_effects_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            match_id = started["match"]["match_id"]

            record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_01"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                    ]
                },
                round_number=1,
            )
            result = record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_leader_wolf", "row": "melee"},
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_06"},
                        {
                            "player_id": "p_witcher_1",
                            "card_id": "gwent_unit_09",
                            "revive_card_id": "gwent_unit_01",
                        },
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_19"},
                    ],
                    "passed": {"p_witcher_1": True, "p_witcher_2": True},
                },
                round_number=2,
            )

        round_state = result["round"]["round_state"]
        effects = round_state["effects_applied"]
        spy = next(item for item in effects if item["effect"] == "spy")
        medic = next(item for item in effects if item["effect"] == "medic")
        muster = next(item for item in effects if item["effect"] == "muster")
        leader = next(item for item in effects if item["scope"] == "leader")
        self.assertEqual(spy["placed_for_player_id"], "p_witcher_2")
        self.assertEqual(len(spy["drawn_card_ids"]), 2)
        self.assertEqual(medic["revived_card_id"], "gwent_unit_01")
        self.assertEqual(muster["mustered_card_ids"], ["gwent_unit_20"])
        self.assertEqual(leader["effect"], "leader_order_rally")
        self.assertTrue(result["match"]["deck_state"]["p_witcher_1"]["leader_used"])
        self.assertIn("gwent_unit_20", round_state["consumed_cards"]["p_witcher_1"])
        self.assertIn("gwent_unit_06", [unit["card_id"] for unit in round_state["board"]["p_witcher_2"]["melee"]])

    def test_gwent_rare_stage1_specials_clear_weather_and_last_stand_apply(self) -> None:
        settings = self.prepare_seed("pvp_rare_stage1_specials", extra_deck_players=("p_witcher_2",))
        units = [f"gwent_unit_{index:02d}" for index in range(1, 23)]
        p1_cards = [
            "gwent_weather_frost",
            "gwent_weather_fog",
            "rare_gwent_04",
            "rare_gwent_06",
            *units,
        ]
        with connect(settings) as connection:
            connection.execute(
                "UPDATE gwent_cards SET effect = 'clear_weather' WHERE card_id = 'gwent_weather_fog'"
            )
            connection.execute(
                "UPDATE gwent_decks SET card_ids = ? WHERE player_id = 'p_witcher_1'",
                (";".join(p1_cards),),
            )
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_rare_stage1_specials",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "rare_specials_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            result = record_gwent_round(
                connection,
                started["match"]["match_id"],
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_weather_frost"},
                        {"player_id": "p_witcher_1", "card_id": "gwent_weather_fog"},
                        {"player_id": "p_witcher_1", "card_id": "rare_gwent_04"},
                        {"player_id": "p_witcher_1", "card_id": "rare_gwent_06"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                    ]
                },
                round_number=1,
            )

        round_state = result["round"]["round_state"]
        effects = round_state["effects_applied"]
        spyglass = next(item for item in effects if item["card_id"] == "rare_gwent_04")
        last_stand = next(item for item in effects if item["card_id"] == "rare_gwent_06")

        self.assertEqual(round_state["weather_rows"], [])
        self.assertEqual(round_state["horn_rows"]["p_witcher_1"], ["melee", "ranged", "siege"])
        self.assertEqual(spyglass["drawn_card_ids"], ["gwent_unit_07"])
        self.assertEqual(last_stand["effect"], "custom_larp_last_stand")
        self.assertIn("gwent_unit_07", result["match"]["deck_state"]["p_witcher_1"]["hand"])
        self.assertIn(
            {"card_id": "gwent_weather_fog", "effect": "clear_weather", "scope": "special"},
            effects,
        )

    def test_gwent_rejects_leader_reuse_nonparticipant_and_unknown_round_cards(self) -> None:
        settings = self.prepare_seed("pvp_round_guardrails", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_round_guardrails",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "round_guardrails_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            match_id = started["match"]["match_id"]

            record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_leader_wolf"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                    ]
                },
                round_number=1,
            )
            with self.assertRaisesRegex(PvpError, "leader was already used"):
                record_gwent_round(
                    connection,
                    match_id,
                    {"plays": [{"player_id": "p_witcher_1", "card_id": "gwent_leader_wolf"}]},
                    round_number=2,
                )
            with self.assertRaisesRegex(PvpError, "non-participant"):
                record_gwent_round(
                    connection,
                    match_id,
                    {"plays": [{"player_id": "p_witcher_3", "card_id": "gwent_unit_01"}]},
                    round_number=2,
                )
            with self.assertRaisesRegex(PvpError, "unknown Gwent card"):
                record_gwent_round(
                    connection,
                    match_id,
                    {"plays": [{"player_id": "p_witcher_1", "card_id": "gwent_missing_card"}]},
                    round_number=2,
                )

    def test_pvp_challenge_rejects_self_challenge_and_non_pvp_roles_without_side_effects(self) -> None:
        settings = self.prepare_seed("pvp_challenge_guardrails", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            tokens_before = connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()["challenge_tokens"]

            with self.assertRaisesRegex(PvpError, "two different players"):
                create_pvp_challenge(
                    connection,
                    ChallengeCreateInput(
                        challenge_id="challenge_self_rejected",
                        challenger_id="p_witcher_1",
                        target_id="p_witcher_1",
                        stake={"asset_type": "item", "asset_id": "self_rejected_marker"},
                    ),
                )
            with self.assertRaisesRegex(PvpError, "cannot join personal PvP"):
                create_pvp_challenge(
                    connection,
                    ChallengeCreateInput(
                        challenge_id="challenge_lord_rejected",
                        challenger_id="p_witcher_1",
                        target_id="p_lord_1",
                        stake={"asset_type": "item", "asset_id": "lord_rejected_marker"},
                    ),
                )
            tokens_after = connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()["challenge_tokens"]
            challenge_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM pvp_challenges
                WHERE challenge_id IN ('challenge_self_rejected', 'challenge_lord_rejected')
                """
            ).fetchone()[0]
            stake_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM pvp_stake_ledger
                WHERE challenge_id IN ('challenge_self_rejected', 'challenge_lord_rejected')
                """
            ).fetchone()[0]

        self.assertEqual(tokens_after, tokens_before)
        self.assertEqual(challenge_count, 0)
        self.assertEqual(stake_count, 0)

    def test_gwent_deck_contract_rejects_bad_mulligans_leader_unknown_cards_and_special_cap(self) -> None:
        units = [f"gwent_unit_{index:02d}" for index in range(1, 23)]
        cases = [
            (
                "too_many_mulligans",
                None,
                {"p_witcher_1": ["gwent_unit_01", "gwent_unit_02", "gwent_unit_03"]},
                "mulligan count exceeds",
            ),
            (
                "invalid_leader",
                {"leader_card_id": "gwent_unit_01"},
                {},
                "deck leader is invalid",
            ),
            (
                "unknown_card",
                {"card_ids": ";".join([*units, "gwent_missing_card"])},
                {},
                "unknown cards",
            ),
            (
                "special_cap",
                {"card_ids": ";".join([*units, *["gwent_horn"] * 11])},
                {},
                "exceeds the special card cap",
            ),
        ]

        for name, deck_patch, mulligans, expected in cases:
            with self.subTest(name=name):
                settings = self.prepare_seed(f"pvp_deck_contract_{name}", extra_deck_players=("p_witcher_2",))
                with connect(settings) as connection:
                    if deck_patch:
                        assignments = ", ".join(f"{column} = ?" for column in deck_patch)
                        connection.execute(
                            f"UPDATE gwent_decks SET {assignments} WHERE player_id = 'p_witcher_1'",
                            tuple(deck_patch.values()),
                        )
                        with self.assertRaisesRegex(PvpError, expected):
                            create_pvp_challenge(
                                connection,
                                ChallengeCreateInput(
                                    challenge_id=f"challenge_deck_contract_{name}",
                                    challenger_id="p_witcher_1",
                                    target_id="p_witcher_2",
                                    stake={"asset_type": "item", "asset_id": f"deck_contract_{name}"},
                                ),
                            )
                        continue
                    challenge = create_pvp_challenge(
                        connection,
                        ChallengeCreateInput(
                            challenge_id=f"challenge_deck_contract_{name}",
                            challenger_id="p_witcher_1",
                            target_id="p_witcher_2",
                            stake={"asset_type": "item", "asset_id": f"deck_contract_{name}"},
                        ),
                    )
                    with self.assertRaisesRegex(PvpError, expected):
                        start_pvp_challenge(
                            connection,
                            ChallengeStartInput(
                                challenge_id=challenge["challenge_id"],
                                mulligans_by_player=mulligans,
                            ),
                        )

    def test_challenge_preflight_rejects_invalid_deck_before_token_stake_and_table(self) -> None:
        settings = self.prepare_seed("pvp_preflight_side_effects", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            connection.execute(
                """
                UPDATE gwent_decks
                SET card_ids = 'gwent_unit_01;gwent_unit_02'
                WHERE player_id = 'p_witcher_2'
                """
            )
            tokens_before = connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()["challenge_tokens"]

            with self.assertRaisesRegex(PvpError, "fewer than 22 unit cards"):
                create_pvp_challenge(
                    connection,
                    ChallengeCreateInput(
                        challenge_id="challenge_preflight_invalid_deck",
                        challenger_id="p_witcher_1",
                        target_id="p_witcher_2",
                        stake={"asset_type": "item", "asset_id": "preflight_invalid_marker"},
                    ),
                )

            tokens_after = connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()["challenge_tokens"]
            stake_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM pvp_stake_ledger
                WHERE challenge_id = 'challenge_preflight_invalid_deck'
                """
            ).fetchone()[0]
            occupied_tables = connection.execute(
                """
                SELECT COUNT(*)
                FROM pvp_table_runtime
                WHERE status = 'occupied'
                """
            ).fetchone()[0]

        self.assertEqual(tokens_after, tokens_before)
        self.assertEqual(stake_count, 0)
        self.assertEqual(occupied_tables, 0)

    def test_gwent_runtime_rejects_corrupted_deck_state_and_stage2_effect_cards(self) -> None:
        settings = self.prepare_seed(
            "pvp_deck_state_resilience",
            extra_deck_players=("p_witcher_2", "p_witcher_3", "p_witcher_4"),
        )
        units = [f"gwent_unit_{index:02d}" for index in range(1, 23)]
        with connect(settings) as connection:
            corrupted_challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_corrupted_deck_state",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "corrupted_deck_marker"},
                ),
            )
            corrupted_started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=corrupted_challenge["challenge_id"]),
            )
            corrupted_match_id = corrupted_started["match"]["match_id"]
            connection.execute(
                """
                UPDATE gwent_runtime_matches
                SET deck_state_json = ?
                WHERE match_id = ?
                """,
                (json.dumps(["not", "a", "deck-state"]), corrupted_match_id),
            )

            with self.assertRaisesRegex(PvpError, "invalid deck state"):
                record_gwent_round(
                    connection,
                    corrupted_match_id,
                    {"plays": [{"player_id": "p_witcher_1", "card_id": "gwent_unit_01"}]},
                    round_number=1,
                )

            connection.execute(
                """
                UPDATE gwent_cards
                SET effect = 'stage2_portal'
                WHERE card_id = 'gwent_unit_03'
                """
            )
            connection.execute(
                """
                UPDATE gwent_decks
                SET card_ids = ?
                WHERE player_id = 'p_witcher_3'
                """,
                (";".join(["gwent_unit_03", *[card_id for card_id in units if card_id != "gwent_unit_03"]]),),
            )
            with self.assertRaisesRegex(PvpError, "not implemented in Stage 1"):
                create_pvp_challenge(
                    connection,
                    ChallengeCreateInput(
                        challenge_id="challenge_stage2_effect_card",
                        challenger_id="p_witcher_3",
                        target_id="p_witcher_4",
                        stake={"asset_type": "item", "asset_id": "stage2_effect_marker"},
                    ),
                )

    def test_gwent_decoy_requires_target_and_cannot_return_hero_units(self) -> None:
        settings = self.prepare_seed("pvp_decoy_rejects", extra_deck_players=("p_witcher_2",))
        units = [f"gwent_unit_{index:02d}" for index in range(1, 23)]
        p1_cards = [
            "rare_gwent_01",
            "gwent_decoy",
            *units,
            "gwent_weather_frost",
            "gwent_horn",
        ]
        with connect(settings) as connection:
            connection.execute(
                "UPDATE gwent_decks SET card_ids = ? WHERE player_id = 'p_witcher_1'",
                (";".join(p1_cards),),
            )
            missing_target_challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_decoy_missing_target",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "decoy_missing_marker"},
                ),
            )
            missing_started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=missing_target_challenge["challenge_id"]),
            )
            with self.assertRaisesRegex(PvpError, "decoy requires target_card_id"):
                record_gwent_round(
                    connection,
                    missing_started["match"]["match_id"],
                    {"plays": [{"player_id": "p_witcher_1", "card_id": "gwent_decoy"}]},
                    round_number=1,
                )

            connection.execute(
                """
                UPDATE pvp_challenges
                SET status = 'resolved'
                WHERE challenge_id = 'challenge_decoy_missing_target'
                """
            )
            connection.execute(
                """
                UPDATE pvp_table_runtime
                SET status = 'open', current_challenge_id = NULL, current_match_id = NULL
                WHERE table_id = 'pvp_table_1'
                """
            )
            hero_target_challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_decoy_hero_target",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "decoy_hero_marker"},
                ),
            )
            hero_started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=hero_target_challenge["challenge_id"]),
            )
            with self.assertRaisesRegex(PvpError, "decoy target is not a non-hero unit"):
                record_gwent_round(
                    connection,
                    hero_started["match"]["match_id"],
                    {
                        "plays": [
                            {"player_id": "p_witcher_1", "card_id": "rare_gwent_01"},
                            {
                                "player_id": "p_witcher_1",
                                "card_id": "gwent_decoy",
                                "target_card_id": "rare_gwent_01",
                            },
                        ]
                    },
                    round_number=1,
                )

    def test_double_tie_match_moves_to_master_review_without_stake_transfer(self) -> None:
        settings = self.prepare_seed("pvp_tie_review", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_tie_review",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "tie_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            match_id = started["match"]["match_id"]
            for round_number, card_id in ((1, "gwent_unit_01"), (2, "gwent_unit_02")):
                result = record_gwent_round(
                    connection,
                    match_id,
                    {
                        "plays": [
                            {"player_id": "p_witcher_1", "card_id": card_id},
                            {"player_id": "p_witcher_2", "card_id": card_id},
                        ]
                    },
                    round_number=round_number,
                )

            self.assertEqual(result["match"]["status"], "needs_master_review")
            self.assertEqual(
                result["match"]["review_reason"],
                "double_loss_tie_requires_master_review",
            )
            finished = finish_gwent_match(connection, match_id, outcome="tie")
            stake = connection.execute(
                """
                SELECT status
                FROM pvp_stake_ledger
                WHERE challenge_id = 'challenge_tie_review'
                """
            ).fetchone()
            review_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM pvp_reviews
                WHERE match_id = ?
                """,
                (match_id,),
            ).fetchone()[0]

        self.assertEqual(finished["stake_transfer"]["status"], "not_applied")
        self.assertEqual(stake["status"], "locked")
        self.assertEqual(review_count, 1)

    def test_partial_finish_moves_to_review_without_stake_transfer(self) -> None:
        settings = self.prepare_seed("pvp_partial_finish_review", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_partial_finish",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "partial_finish_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            match_id = started["match"]["match_id"]
            record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_02"},
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_03"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                    ]
                },
                round_number=1,
            )
            finished = finish_gwent_match(connection, match_id, winner_id="p_witcher_1")
            challenge_row = connection.execute(
                """
                SELECT status, review_reason
                FROM pvp_challenges
                WHERE challenge_id = 'challenge_partial_finish'
                """
            ).fetchone()
            stake = connection.execute(
                """
                SELECT status
                FROM pvp_stake_ledger
                WHERE challenge_id = 'challenge_partial_finish'
                """
            ).fetchone()
            table = connection.execute(
                """
                SELECT status, current_challenge_id, current_match_id
                FROM pvp_table_runtime
                WHERE table_id = 'pvp_table_1'
                """
            ).fetchone()

        self.assertEqual(finished["match"]["status"], "needs_master_review")
        self.assertEqual(
            finished["match"]["review_reason"],
            "finish_before_match_winner_requires_master_review",
        )
        self.assertEqual(finished["stake_transfer"]["status"], "not_applied")
        self.assertEqual(challenge_row["status"], "needs_master_review")
        self.assertEqual(stake["status"], "locked")
        self.assertEqual(table["status"], "open")
        self.assertIsNone(table["current_challenge_id"])
        self.assertIsNone(table["current_match_id"])

    def test_in_match_refusal_moves_match_to_review_and_releases_table(self) -> None:
        settings = self.prepare_seed("pvp_in_match_refusal", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_in_match_refusal",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "in_match_refusal_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            match_id = started["match"]["match_id"]
            refused = record_pvp_refusal(
                connection,
                "challenge_in_match_refusal",
                reason="active_scene",
                actor_id="p_witcher_2",
            )
            match = connection.execute(
                """
                SELECT status, review_reason
                FROM gwent_runtime_matches
                WHERE match_id = ?
                """,
                (match_id,),
            ).fetchone()
            stake = connection.execute(
                """
                SELECT status
                FROM pvp_stake_ledger
                WHERE challenge_id = 'challenge_in_match_refusal'
                """
            ).fetchone()
            table = connection.execute(
                """
                SELECT status, current_challenge_id, current_match_id
                FROM pvp_table_runtime
                WHERE table_id = 'pvp_table_1'
                """
            ).fetchone()

        self.assertEqual(refused["status"], "needs_master_review")
        self.assertEqual(refused["review_reason"], "refusal:active_scene")
        self.assertEqual(match["status"], "needs_master_review")
        self.assertEqual(match["review_reason"], "refusal:active_scene")
        self.assertEqual(stake["status"], "locked")
        self.assertEqual(table["status"], "open")
        self.assertIsNone(table["current_challenge_id"])
        self.assertIsNone(table["current_match_id"])

    def test_pvp_stake_lock_blocks_parallel_challenge_reusing_same_asset(self) -> None:
        settings = self.prepare_seed(
            "pvp_stake_lock_reuse",
            extra_deck_players=("p_witcher_2", "p_witcher_3", "p_witcher_4"),
        )
        with connect(settings) as connection:
            create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_lock_owner",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "shared_stake_marker"},
                ),
            )
            with self.assertRaisesRegex(PvpError, "Stake asset is already locked"):
                create_pvp_challenge(
                    connection,
                    ChallengeCreateInput(
                        challenge_id="challenge_lock_conflict",
                        challenger_id="p_witcher_3",
                        target_id="p_witcher_4",
                        stake={"asset_type": "item", "asset_id": "shared_stake_marker"},
                    ),
                )
            locked_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM pvp_stake_ledger
                WHERE asset_id = 'shared_stake_marker'
                  AND status = 'locked'
                """
            ).fetchone()[0]

        self.assertEqual(locked_count, 1)

    def test_throttle_queue_refusal_paused_mode_and_final_lock(self) -> None:
        settings = self.prepare_seed(
            "pvp_throttle",
            extra_deck_players=(
                "p_witcher_2",
                "p_witcher_3",
                "p_witcher_4",
                "p_witcher_5",
                "p_sorc_1",
                "p_sorc_2",
                "p_sorc_3",
            ),
        )
        with connect(settings) as connection:
            limited = set_pvp_throttle_mode(connection, "limited")
            self.assertEqual(limited["throttle"]["max_tables"], 1)
            first = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_limited_first",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "limited_one"},
                ),
            )
            second = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_limited_second",
                    challenger_id="p_witcher_3",
                    target_id="p_witcher_4",
                    stake={"asset_type": "item", "asset_id": "limited_two"},
                ),
            )
            self.assertEqual(first["status"], "assigned")
            self.assertEqual(second["status"], "queued")

            deferred = record_pvp_refusal(
                connection,
                "challenge_limited_first",
                reason="active_scene",
                actor_id="p_witcher_2",
            )
            self.assertEqual(deferred["status"], "deferred")
            queued_start = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id="challenge_limited_second"),
            )
            self.assertEqual(queued_start["match"]["status"], "active")

            paused = set_pvp_throttle_mode(connection, "paused")
            self.assertEqual(paused["throttle"]["max_tables"], 0)
            paused_challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_paused",
                    challenger_id="p_witcher_5",
                    target_id="p_sorc_1",
                    stake={"asset_type": "item", "asset_id": "paused_marker"},
                ),
            )
            self.assertEqual(paused_challenge["status"], "queued")

            connection.execute(
                """
                UPDATE final_lock_state
                SET locked_at = ?, operator = 'gm', source = 'test'
                WHERE id = 1
                """,
                (datetime(2026, 6, 2, 17, 15, tzinfo=UTC).isoformat(timespec="seconds"),),
            )
            with self.assertRaisesRegex(Exception, "locked after final lock"):
                create_pvp_challenge(
                    connection,
                    ChallengeCreateInput(
                        challenger_id="p_sorc_2",
                        target_id="p_sorc_3",
                        stake={"asset_type": "item", "asset_id": "after_final_lock"},
                    ),
                )
            tokens_before_override = connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_sorc_2'
                """
            ).fetchone()["challenge_tokens"]
            master_override = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_final_lock_master_override",
                    challenger_id="p_sorc_2",
                    target_id="p_sorc_3",
                    stake={"asset_type": "item", "asset_id": "after_final_lock_override"},
                    master_approval=True,
                ),
            )
            tokens_after_override = connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_sorc_2'
                """
            ).fetchone()["challenge_tokens"]

        self.assertEqual(master_override["status"], "queued")
        self.assertTrue(master_override["master_approval"])
        self.assertEqual(tokens_after_override, tokens_before_override)

    def test_start_window_timeout_moves_to_review(self) -> None:
        started_at = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
        settings = self.prepare_seed(
            "pvp_timeout",
            extra_deck_players=("p_witcher_2",),
            started_at=started_at,
        )
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_timeout",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "timeout_marker"},
                ),
                now=started_at,
            )
            result = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
                now=started_at + timedelta(minutes=31),
            )
            review = connection.execute(
                """
                SELECT reason
                FROM pvp_reviews
                WHERE challenge_id = 'challenge_timeout'
                """
            ).fetchone()

        self.assertEqual(result["challenge"]["status"], "needs_master_review")
        self.assertEqual(result["challenge"]["review_reason"], "start_window_timeout")
        self.assertEqual(review["reason"], "start_window_timeout")

    def test_queued_challenge_start_window_begins_after_table_assignment(self) -> None:
        started_at = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
        settings = self.prepare_seed(
            "pvp_queued_timeout",
            extra_deck_players=("p_witcher_2", "p_witcher_3", "p_witcher_4"),
            started_at=started_at,
        )
        with connect(settings) as connection:
            set_pvp_throttle_mode(connection, "limited", now=started_at)
            first = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_queue_first",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "queue_first_marker"},
                ),
                now=started_at,
            )
            second = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_queue_second",
                    challenger_id="p_witcher_3",
                    target_id="p_witcher_4",
                    stake={"asset_type": "item", "asset_id": "queue_second_marker"},
                ),
                now=started_at,
            )
            self.assertEqual(first["status"], "assigned")
            self.assertEqual(second["status"], "queued")
            self.assertIsNone(second["start_window_deadline"])

            still_queued = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=second["challenge_id"]),
                now=started_at + timedelta(minutes=31),
            )
            self.assertEqual(still_queued["challenge"]["status"], "queued")
            review_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM pvp_reviews
                WHERE challenge_id = 'challenge_queue_second'
                """
            ).fetchone()[0]
            self.assertEqual(review_count, 0)

            record_pvp_refusal(
                connection,
                first["challenge_id"],
                reason="active_scene",
                actor_id="p_witcher_2",
                now=started_at + timedelta(minutes=32),
            )
            assigned = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=second["challenge_id"]),
                now=started_at + timedelta(minutes=40),
            )

        self.assertEqual(assigned["match"]["status"], "active")
        assigned_deadline = datetime.fromisoformat(assigned["challenge"]["start_window_deadline"])
        self.assertEqual(assigned_deadline, started_at + timedelta(minutes=70))

    def test_safety_refusal_before_start_refunds_token_and_goes_to_review(self) -> None:
        settings = self.prepare_seed("pvp_refusal_refund", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_refusal_refund",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "refusal_refund_marker"},
                ),
            )
            spent_tokens = connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()["challenge_tokens"]
            refused = record_pvp_refusal(
                connection,
                challenge["challenge_id"],
                reason="safety_stop",
                actor_id="p_witcher_2",
            )
            refunded_tokens = connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()["challenge_tokens"]
            review = connection.execute(
                """
                SELECT reason
                FROM pvp_reviews
                WHERE challenge_id = 'challenge_refusal_refund'
                """
            ).fetchone()

        self.assertEqual(spent_tokens, 2)
        self.assertEqual(refunded_tokens, 3)
        self.assertEqual(refused["status"], "needs_master_review")
        self.assertEqual(refused["review_reason"], "refusal:safety_stop")
        self.assertEqual(review["reason"], "refusal:safety_stop")

    def test_started_cap_counts_matches_in_master_review(self) -> None:
        started_at = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
        settings = self.prepare_seed(
            "pvp_started_cap_review",
            extra_deck_players=("p_witcher_2", "p_witcher_3"),
            started_at=started_at,
        )
        with connect(settings) as connection:
            set_pvp_throttle_mode(connection, "limited", now=started_at)
            first = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_cap_review_first",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "cap_review_first_marker"},
                ),
                now=started_at,
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=first["challenge_id"]),
                now=started_at,
            )
            match_id = started["match"]["match_id"]
            for round_number, card_id in ((1, "gwent_unit_01"), (2, "gwent_unit_02")):
                reviewed_round = record_gwent_round(
                    connection,
                    match_id,
                    {
                        "plays": [
                            {"player_id": "p_witcher_1", "card_id": card_id},
                            {"player_id": "p_witcher_2", "card_id": card_id},
                        ]
                    },
                    round_number=round_number,
                )
            self.assertEqual(reviewed_round["match"]["status"], "needs_master_review")

            connection.execute(
                """
                UPDATE pvp_challenges
                SET status = 'resolved',
                    resolved_at = ?,
                    updated_at = ?
                WHERE challenge_id = 'challenge_cap_review_first'
                """,
                (
                    (started_at + timedelta(minutes=5)).isoformat(timespec="seconds"),
                    (started_at + timedelta(minutes=5)).isoformat(timespec="seconds"),
                ),
            )
            connection.execute(
                """
                UPDATE pvp_table_runtime
                SET status = 'open',
                    current_challenge_id = NULL,
                    current_match_id = NULL
                WHERE table_id = 'pvp_table_1'
                """
            )
            second = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_cap_review_second",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_3",
                    stake={"asset_type": "item", "asset_id": "cap_review_second_marker"},
                ),
                now=started_at + timedelta(minutes=6),
            )
            blocked = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=second["challenge_id"]),
                now=started_at + timedelta(minutes=6),
            )

        self.assertEqual(blocked["challenge"]["status"], "needs_master_review")
        self.assertEqual(blocked["challenge"]["review_reason"], "started mandatory match cap reached")

    def test_gwent_finish_with_invalid_winner_moves_to_master_review_without_stake_transfer(self) -> None:
        settings = self.prepare_seed("pvp_finish_invalid_winner", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_invalid_finish",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "invalid_finish_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            match_id = started["match"]["match_id"]
            record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_02"},
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_03"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                    ]
                },
                round_number=1,
            )
            record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_04"},
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_05"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_02"},
                    ]
                },
                round_number=2,
            )
            finished = finish_gwent_match(
                connection,
                match_id,
                winner_id="p_missing",
                outcome="manual_override",
            )
            stake = connection.execute(
                """
                SELECT status
                FROM pvp_stake_ledger
                WHERE challenge_id = 'challenge_invalid_finish'
                """
            ).fetchone()
            review = connection.execute(
                """
                SELECT reason
                FROM pvp_reviews
                WHERE challenge_id = 'challenge_invalid_finish'
                """
            ).fetchone()

        self.assertEqual(finished["match"]["status"], "needs_master_review")
        self.assertEqual(finished["match"]["review_reason"], "manual_override_requires_master_review")
        self.assertEqual(finished["stake_transfer"]["status"], "not_applied")
        self.assertEqual(stake["status"], "locked")
        self.assertEqual(review["reason"], "manual_override_requires_master_review")

    def test_personal_card_conversion_rejects_unknown_lord_and_non_convertible_card(self) -> None:
        settings = self.prepare_seed("pvp_conversion_rejects", extra_deck_players=())
        with connect(settings) as connection:
            with self.assertRaisesRegex(PvpError, "Unknown lord player"):
                convert_personal_card_to_lord(
                    connection,
                    player_id="p_witcher_1",
                    lord_id="p_witcher_2",
                    personal_card_id="pc_infantry_t1",
                )

            connection.execute(
                """
                UPDATE cards
                SET card_type = 'story_keepsake',
                    army_unit_card_id = ''
                WHERE card_id = 'pc_infantry_t1'
                """
            )
            with self.assertRaisesRegex(PvpError, "cannot be converted"):
                convert_personal_card_to_lord(
                    connection,
                    player_id="p_witcher_1",
                    lord_id="p_lord_1",
                    personal_card_id="pc_infantry_t1",
                )

    def test_personal_card_conversion_rejects_non_owned_card_without_minting(self) -> None:
        settings = self.prepare_seed("pvp_card_conversion_non_owned", extra_deck_players=())
        with connect(settings) as connection:
            with self.assertRaisesRegex(PvpError, "does not own personal card"):
                convert_personal_card_to_lord(
                    connection,
                    player_id="p_witcher_1",
                    lord_id="p_lord_1",
                    personal_card_id="pc_infantry_t1",
                )

            conversion_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM personal_card_conversions
                WHERE player_id = 'p_witcher_1'
                  AND personal_card_id = 'pc_infantry_t1'
                """
            ).fetchone()[0]
            reserve_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM army_reserve_runtime
                WHERE reserve_id = 'reserve_domain_north_unit_infantry_t1_conversion'
                """
            ).fetchone()[0]

        self.assertEqual(conversion_count, 0)
        self.assertEqual(reserve_count, 0)

    def test_personal_card_conversion_rejects_pending_reward_locked_card(self) -> None:
        settings = self.prepare_seed("pvp_card_conversion_pending_reward", extra_deck_players=())
        with connect(settings) as connection:
            create_pending_reward_approval(
                connection,
                approval_id="approval_locked_conversion_card",
                reward_id="reward_pve_t4",
                player_id="p_witcher_1",
                source_event_id=None,
                now=datetime(2026, 6, 2, 11, 0, tzinfo=UTC),
            )

            with self.assertRaisesRegex(PvpError, "locked"):
                convert_personal_card_to_lord(
                    connection,
                    player_id="p_witcher_1",
                    lord_id="p_lord_1",
                    personal_card_id="pc_siege_t3",
                )

            conversion_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM personal_card_conversions
                WHERE player_id = 'p_witcher_1'
                  AND personal_card_id = 'pc_siege_t3'
                """
            ).fetchone()[0]
            reserve_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM army_reserve_runtime
                WHERE reserve_id = 'reserve_domain_north_unit_heavy_siege_t3_conversion'
                """
            ).fetchone()[0]
            active_lock_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM asset_locks
                WHERE asset_type = 'card'
                  AND asset_id = 'pc_siege_t3'
                  AND lock_type = 'reward_approval'
                  AND status = 'active'
                """
            ).fetchone()[0]

        self.assertEqual(conversion_count, 0)
        self.assertEqual(reserve_count, 0)
        self.assertEqual(active_lock_count, 1)

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_personal_card_to_lord_conversion_is_permanent_and_idempotent(self) -> None:
        settings = self.prepare_seed("pvp_card_conversion", extra_deck_players=())
        with connect(settings) as connection:
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="card",
                asset_id="pc_infantry_t1",
                source="test_conversion_seed",
                source_ref_id="pc_infantry_t1",
            )
        client = TestClient(create_app(settings))

        first = client.post(
            "/api/pvp/card-conversions",
            headers=WITCHER_1_HEADERS,
            json={
                "player_id": "p_witcher_1",
                "lord_id": "p_lord_1",
                "personal_card_id": "pc_infantry_t1",
            },
        )
        second = client.post(
            "/api/pvp/card-conversions",
            headers=WITCHER_1_HEADERS,
            json={
                "player_id": "p_witcher_1",
                "lord_id": "p_lord_1",
                "personal_card_id": "pc_infantry_t1",
            },
        )

        self.assertEqual(first.status_code, 200)
        payload = first.json()
        self.assertEqual(payload["army_unit_card_id"], "unit_infantry_t1")
        self.assertEqual(payload["tier"], 1)
        self.assertFalse(payload["duplicate"])
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["duplicate"])

        with connect(settings) as connection:
            reserve = connection.execute(
                """
                SELECT card_id, count
                FROM army_reserve_runtime
                WHERE reserve_id = 'reserve_domain_north_unit_infantry_t1_conversion'
                """
            ).fetchone()
            ownership_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM asset_ownership
                WHERE owner_player_id = 'p_witcher_1'
                  AND asset_type = 'card'
                  AND asset_id = 'pc_infantry_t1'
                  AND status = 'active'
                """
            ).fetchone()[0]
            conversion_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM personal_card_conversions
                WHERE player_id = 'p_witcher_1'
                  AND personal_card_id = 'pc_infantry_t1'
                """
            ).fetchone()[0]
            event = connection.execute(
                """
                SELECT payload_json
                FROM event_log
                WHERE event_type = 'personal_card_converted_to_lord'
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        self.assertEqual(reserve["card_id"], "unit_infantry_t1")
        self.assertEqual(reserve["count"], 1)
        self.assertEqual(ownership_count, 0)
        self.assertEqual(conversion_count, 1)
        event_payload = json.loads(event["payload_json"])
        self.assertEqual(event_payload["ownership_debit"]["quantity_before"], 1)
        self.assertEqual(event_payload["ownership_debit"]["quantity_debited"], 1)
        self.assertEqual(event_payload["ownership_debit"]["quantity_after"], 0)


if __name__ == "__main__":
    unittest.main()
