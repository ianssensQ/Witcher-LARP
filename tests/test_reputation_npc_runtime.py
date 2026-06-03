from __future__ import annotations

import unittest
from uuid import uuid4

from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.npc_service import NpcEventInput
from backend.witcher_larp.npc_service import list_npc_deals, record_npc_event, review_queue
from backend.witcher_larp.reputation_service import apply_reputation_change
from backend.witcher_larp.reputation_service import get_reputation_view

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]

MASTER_HEADERS = {"X-Role-Token": "MASTER-KING-4QZ8"}


class ReputationNpcRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        (PROJECT_ROOT / ".test-data").mkdir(exist_ok=True)

    def test_reputation_clamps_persists_and_hides_number_from_player(self) -> None:
        settings = self._settings("reputation_clamp")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            player_view = get_reputation_view(connection, "p_witcher_1", visibility="player")
            master_view = get_reputation_view(connection, "p_witcher_1", visibility="master")
            change = apply_reputation_change(
                connection,
                "p_witcher_1",
                10,
                reason="saved villagers before payment",
            )

        self.assertNotIn("value", player_view)
        self.assertEqual(player_view["canonical_label"], "Нейтральный")
        self.assertEqual(master_view["value"], 0)
        self.assertEqual(change["value_after"], 5)
        self.assertEqual(change["canonical_label"], "Свет")

        with connect(settings) as connection:
            player_after_restart = get_reputation_view(
                connection, "p_witcher_1", visibility="player"
            )
            master_after_restart = get_reputation_view(
                connection, "p_witcher_1", visibility="master"
            )

        self.assertNotIn("value", player_after_restart)
        self.assertEqual(player_after_restart["value_visibility"], "hidden_from_player")
        self.assertEqual(player_after_restart["player_descriptor"], "celebrated")
        self.assertEqual(player_after_restart["threshold_access"]["axis"], "light")
        self.assertEqual(master_after_restart["value"], 5)
        self.assertEqual(master_after_restart["change_log"][0]["value_after"], 5)
        self.assertEqual(
            master_after_restart["change_log"][0]["reason"],
            "saved villagers before payment",
        )

    def test_good_and_evil_threshold_access_are_symmetric_tradeoffs(self) -> None:
        settings = self._settings("reputation_access")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            apply_reputation_change(
                connection,
                "p_sorc_1",
                3,
                reason="backed a public ruling",
            )
            apply_reputation_change(
                connection,
                "p_sorc_2",
                -3,
                reason="accepted a hidden price",
            )
            good = get_reputation_view(connection, "p_sorc_1", visibility="master")
            evil = get_reputation_view(connection, "p_sorc_2", visibility="master")

        self.assertEqual(good["canonical_label"], "Добро")
        self.assertEqual(evil["canonical_label"], "Запятнанный")
        self.assertEqual(good["threshold_access"]["tier"], evil["threshold_access"]["tier"])
        self.assertEqual(good["threshold_access"]["axis"], "light")
        self.assertEqual(evil["threshold_access"]["axis"], "dark")
        self.assertEqual(good["threshold_access"]["opposite"], "Запятнанный")
        self.assertEqual(evil["threshold_access"]["opposite"], "Добро")
        self.assertNotEqual(good["threshold_access"]["benefits"], evil["threshold_access"]["benefits"])
        self.assertNotEqual(good["threshold_access"]["costs"], evil["threshold_access"]["costs"])

    def test_king_and_wanderer_events_capture_review_routes_and_deals(self) -> None:
        settings = self._settings("npc_events")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            king_ruling = record_npc_event(
                connection,
                NpcEventInput(seed_event_id="npc_king_ruling"),
            )
            king_influence = record_npc_event(
                connection,
                NpcEventInput(seed_event_id="npc_king_influence"),
            )
            wanderer_deal = record_npc_event(
                connection,
                NpcEventInput(
                    npc_role="npc_wanderer",
                    event_type="stranger_deal",
                    target_ids=["p_witcher_4"],
                    price={"hidden_price": "final_debt"},
                    condition={"accepted_mark": True},
                    consequence={
                        "effect": "unlock_dark_path",
                        "artifact": "dark_token",
                    },
                    reputation_delta=-4,
                    severity="P0",
                    final_flag=True,
                ),
            )
            deals_for_master = list_npc_deals(connection, visibility="master")
            deals_for_player = list_npc_deals(connection, visibility="player")
            reputation = get_reputation_view(connection, "p_witcher_4", visibility="master")
            queue = review_queue(connection)

        self.assertEqual(king_ruling["npc_role"], "npc_king")
        self.assertEqual(king_ruling["event_type"], "king_ruling")
        self.assertEqual(king_ruling["review_route"], "before_next_act_or_final")
        self.assertTrue(king_ruling["blocks_progress"])
        self.assertEqual(king_influence["event_type"], "influence_grant")
        self.assertEqual(
            king_influence["influence_changes"],
            [
                {
                    "domain_id": "domain_north",
                    "delta": 1,
                    "value_before": 3,
                    "value_after": 4,
                    "source": "master_api",
                }
            ],
        )
        self.assertIsNone(king_influence["deal"])

        self.assertEqual(wanderer_deal["npc_role"], "npc_wanderer")
        self.assertEqual(wanderer_deal["review_route"], "stop_now")
        self.assertTrue(wanderer_deal["final_flag"])
        self.assertEqual(wanderer_deal["deal"]["price"]["hidden_price"], "final_debt")
        self.assertTrue(wanderer_deal["deal"]["hidden_price"])
        self.assertEqual(reputation["value"], -4)
        self.assertEqual(reputation["canonical_label"], "Тьма")
        self.assertEqual(deals_for_master[0]["price"]["hidden_price"], "final_debt")
        self.assertEqual(deals_for_player[0]["price"]["hidden_price"], "master_only")
        self.assertEqual(queue["items"][0]["severity"], "P0")
        self.assertEqual(queue["items"][0]["review_route"], "stop_now")

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_fastapi_reputation_and_npc_contract(self) -> None:
        settings = self._settings("api_reputation_npc")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        player_before = client.get(
            "/api/players/p_witcher_2/reputation",
            headers={"X-Player-Code": "WC-CAT-1HN8"},
        )
        change_response = client.post(
            "/api/master/reputation/p_witcher_2/change",
            headers=MASTER_HEADERS,
            json={
                "delta": 2,
                "reason": "accepted a public contract",
            },
        )
        master_after = client.get(
            "/api/master/reputation/p_witcher_2",
            headers=MASTER_HEADERS,
        )
        npc_response = client.post(
            "/api/master/npc/events",
            headers=MASTER_HEADERS,
            json={
                "npc_role": "npc_wanderer",
                "event_type": "stranger_deal",
                "target_ids": ["p_witcher_2"],
                "price": {"hidden_price": "owed_at_final"},
                "condition": {"must_bring": "artifact"},
                "consequence": {"effect": "alternate_victory_hook"},
                "reputation_delta": -5,
                "severity": "P1",
                "final_flag": True,
            },
        )
        missing_npc_contract = client.post(
            "/api/master/npc/events",
            headers=MASTER_HEADERS,
            json={},
        )
        unsupported_severity = client.post(
            "/api/master/npc/events",
            headers=MASTER_HEADERS,
            json={
                "npc_role": "npc_king",
                "event_type": "king_ruling",
                "severity": "P9",
            },
        )
        invalid_reputation_target = client.post(
            "/api/master/npc/events",
            headers=MASTER_HEADERS,
            json={
                "npc_role": "npc_wanderer",
                "event_type": "stranger_deal",
                "target_ids": ["p_lord_1"],
                "price": {"hidden_price": "owed_at_final"},
                "consequence": {"effect": "tempted_a_lord"},
                "reputation_delta": -1,
                "severity": "P1",
            },
        )
        queue_response = client.get("/api/master/review-queue", headers=MASTER_HEADERS)
        deals_response = client.get("/api/master/npc/deals", headers=MASTER_HEADERS)

        self.assertEqual(player_before.status_code, 200)
        self.assertNotIn("value", player_before.json())
        self.assertEqual(change_response.status_code, 200)
        self.assertEqual(change_response.json()["change"]["value_after"], 2)
        self.assertEqual(master_after.status_code, 200)
        self.assertEqual(master_after.json()["value"], 2)
        self.assertEqual(npc_response.status_code, 200)
        self.assertEqual(npc_response.json()["deal"]["final_flag"], True)
        self.assertEqual(missing_npc_contract.status_code, 400)
        self.assertIn(
            "NPC event requires npc_role and event_type",
            missing_npc_contract.json()["detail"],
        )
        self.assertEqual(unsupported_severity.status_code, 400)
        self.assertIn("Unsupported review severity: P9", unsupported_severity.json()["detail"])
        self.assertEqual(invalid_reputation_target.status_code, 400)
        self.assertIn(
            "Reputation applies only to witchers and sorceresses",
            invalid_reputation_target.json()["detail"],
        )
        self.assertEqual(queue_response.status_code, 200)
        self.assertEqual(queue_response.json()["items"][0]["review_route"], "before_next_act_or_final")
        self.assertEqual(deals_response.status_code, 200)
        self.assertEqual(deals_response.json()["items"][0]["price"]["hidden_price"], "owed_at_final")

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=PROJECT_ROOT / ".test-data" / f"{name}_{uuid4().hex}.db")

    def _import_valid_seed(self, settings: Settings):
        report = import_seed_pack(
            settings,
            manifest_path=PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "seed_valid"
            / "fixture_manifest.csv",
            snapshot_dir=None,
        )
        self.assertEqual(report.status, "success")
        return report


if __name__ == "__main__":
    unittest.main()
