from __future__ import annotations

from datetime import UTC, datetime
import json
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.app import create_app
from backend.witcher_larp.asset_service import grant_asset_ownership
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.pve_runtime import resolve_pve_scene

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"
MASTER_HEADERS = {"X-Role-Token": "MASTER-KING-4QZ8"}
WITCHER_1_HEADERS = {"X-Player-Code": "WC-WOLF-6GF4"}
WITCHER_2_HEADERS = {"X-Player-Code": "WC-CAT-1HN8"}
LORD_NORTH_HEADERS = {"X-Role-Token": "LORD-NORTH-R8K4"}
LORD_FOREST_HEADERS = {"X-Role-Token": "LORD-FOREST-P6W3"}


@unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
class Stage1FreshRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_task059_060_pve_roll_and_modifier_bypasses_enter_review(self) -> None:
        settings = self._settings("fresh_pve_rolls")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        with connect(settings) as connection:
            first_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
        first = self._sync_api(
            client,
            headers=WITCHER_1_HEADERS,
            event_id="fresh_pve_first_roll",
            actor_id="p_witcher_1",
            event_type="pve_completed",
            payload=first_payload,
            sequence=1,
        )

        duplicate_payload = json.loads(json.dumps(first_payload))
        duplicate = self._sync_api(
            client,
            headers=WITCHER_1_HEADERS,
            event_id="fresh_pve_duplicate_roll",
            actor_id="p_witcher_1",
            event_type="pve_completed",
            payload=duplicate_payload,
            sequence=2,
        )

        with connect(settings) as connection:
            changed_roll_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=9,
                check_id=str(first_payload["check_id"]),
                now=datetime(2026, 6, 2, 9, 2, tzinfo=UTC),
            )
            forged_modifier_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_2",
                qr_id="qr_a1_001",
                roll=1,
                now=datetime(2026, 6, 2, 9, 3, tzinfo=UTC),
            )
        changed = self._sync_api(
            client,
            headers=WITCHER_1_HEADERS,
            event_id="fresh_pve_changed_roll",
            actor_id="p_witcher_1",
            event_type="pve_completed",
            payload=changed_roll_payload,
            sequence=3,
        )
        forged_modifier = {"source": "client", "label": "free +999", "value": 999}
        forged_modifier_payload["modifiers"] = [forged_modifier]
        forged_modifier_payload["roll_log"][0]["modifiers"] = [forged_modifier]
        forged_modifier_payload["total"] = 1003
        forged_modifier_payload["roll_log"][0]["total"] = 1003
        forged_modifier_payload["result"] = "success"
        forged_modifier_payload["outcome"] = "success"
        forged_modifier_payload["roll_log"][0]["outcome"] = "success"
        modifier = self._sync_api(
            client,
            headers=WITCHER_2_HEADERS,
            event_id="fresh_pve_forged_modifier",
            actor_id="p_witcher_2",
            event_type="pve_completed",
            payload=forged_modifier_payload,
            sequence=1,
        )

        self.assertEqual(first["results"][0]["status"], "accepted")
        self.assertEqual(duplicate["results"][0]["status"], "needs_master_review")
        self.assertEqual(changed["results"][0]["status"], "needs_master_review")
        self.assertEqual(modifier["results"][0]["status"], "needs_master_review")
        with connect(settings) as connection:
            review_reasons = self._review_reasons(
                connection,
                (
                    "fresh_pve_duplicate_roll",
                    "fresh_pve_changed_roll",
                    "fresh_pve_forged_modifier",
                ),
            )
            attempts = connection.execute("SELECT COUNT(*) FROM pve_attempts").fetchone()[0]

        self.assertEqual(
            review_reasons["fresh_pve_duplicate_roll"],
            "duplicate pve roll for same check_id requires master review",
        )
        self.assertEqual(
            review_reasons["fresh_pve_changed_roll"],
            "pve check_id already has a different d20 roll and needs master review",
        )
        self.assertEqual(
            review_reasons["fresh_pve_forged_modifier"],
            "pve modifiers do not match server-derived modifiers",
        )
        self.assertEqual(attempts, 1)

    def test_task061_062_future_act_secrecy_and_mobile_sync_auth_contract(self) -> None:
        settings = self._settings("fresh_qr_mobile")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        future_lookup = client.post(
            "/api/qr/lookup",
            headers=WITCHER_1_HEADERS,
            json={
                "code": "QR-A2-B4K8",
                "device_id": "phone-wolf",
                "source": "manual_id",
                "physical_presence_confirmed": True,
            },
        )
        snapshot = client.get(
            "/api/content/snapshot",
            params={"player_code": "WC-WOLF-6GF4"},
        )
        sync = self._sync_api(
            client,
            headers=WITCHER_1_HEADERS,
            event_id="fresh_mobile_trusted_actor",
            actor_id="p_witcher_2",
            actor_type="master",
            event_type="qr_scene_started",
            payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
            sequence=1,
        )
        duplicate = self._sync_api(
            client,
            headers=WITCHER_1_HEADERS,
            event_id="fresh_mobile_trusted_actor",
            actor_id="p_witcher_2",
            actor_type="master",
            event_type="qr_scene_started",
            payload={"qr_id": "qr_a1_001", "local_status": "accepted"},
            sequence=2,
        )

        self.assertEqual(future_lookup.status_code, 200, future_lookup.text)
        future_payload = future_lookup.json()
        self.assertEqual(future_payload["status"], "locked")
        self.assertEqual(future_payload["reason"], "requires_act_unlock")
        self.assertIsNone(future_payload["scenario"])
        self.assertEqual(
            future_payload["qr"],
            {
                "qr_id": "qr_a2_013",
                "qr_mode": "repeatable_scene",
                "act_id": "act2",
                "requires_act_unlock": True,
                "locked": True,
            },
        )
        self.assertIsNone(future_payload["event_context"]["manual_code"])
        self.assertIsNone(future_payload["event_context"]["scenario_id"])

        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        snapshot_payload = snapshot.json()
        self.assertTrue(all(row["code"] is None for row in snapshot_payload["act_unlock_codes"]))
        self.assertTrue(
            all(row["code_sha256"] is None for row in snapshot_payload["act_unlock_codes"])
        )
        self.assertNotIn("player_codes", snapshot_payload)
        self.assertNotIn("role_tokens", snapshot_payload)
        self.assertNotIn("UNLOCK-A2-7GQ4", snapshot.text)
        self.assertNotIn("QR-A2-B4K8", snapshot.text)
        self.assertNotIn("scn_a2_013", snapshot.text)

        self.assertEqual(sync["results"][0]["status"], "accepted")
        self.assertEqual(duplicate["results"][0]["status"], "duplicate")
        with connect(settings) as connection:
            stored = connection.execute(
                """
                SELECT actor_id, actor_type, status
                FROM events
                WHERE event_id = 'fresh_mobile_trusted_actor'
                """
            ).fetchone()
            sync_state = connection.execute(
                """
                SELECT player_id, last_event_sequence
                FROM client_sync_state
                WHERE client_id = 'phone-fresh_mobile_trusted_actor'
                """
            ).fetchone()

        self.assertEqual(dict(stored), {
            "actor_id": "p_witcher_1",
            "actor_type": "witcher",
            "status": "accepted",
        })
        self.assertEqual(sync_state["player_id"], "p_witcher_1")
        self.assertEqual(sync_state["last_event_sequence"], 2)

    def test_task063_064_pvp_stakes_winner_lord_route_and_escrow_are_authoritative(self) -> None:
        settings = self._settings("fresh_pvp_lord")
        self._import_seed(settings)
        with connect(settings) as connection:
            start_act(
                connection,
                settings,
                "act1",
                operator="gm_fresh",
                physical_announcement_state="announced",
                now=datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
            )
            self._copy_gwent_deck(connection, "p_witcher_2")
            self._grant_item(connection, "fresh_foreign_stake", "p_witcher_2")
            self._grant_item(connection, "fresh_private_stake", "p_witcher_1")
            tokens_before = self._challenge_tokens(connection, "p_witcher_1")
        client = TestClient(create_app(settings))

        foreign_stake = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenge_id": "fresh_non_owned_stake",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {"asset_type": "item", "asset_id": "fresh_foreign_stake"},
            },
        )
        self.assertEqual(foreign_stake.status_code, 400, foreign_stake.text)
        self.assertIn("does not own PvP stake asset", foreign_stake.text)
        with connect(settings) as connection:
            self.assertEqual(self._challenge_tokens(connection, "p_witcher_1"), tokens_before)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM pvp_challenges WHERE challenge_id = 'fresh_non_owned_stake'"
                ).fetchone()[0],
                0,
            )

        challenge = self._post_ok(
            client,
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenge_id": "fresh_winner_override",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {"asset_type": "item", "asset_id": "fresh_private_stake"},
            },
        )
        started = self._post_ok(
            client,
            f"/api/pvp/challenges/{challenge['challenge_id']}/start",
            headers=WITCHER_1_HEADERS,
            json={},
        )
        match_id = started["match"]["match_id"]
        for round_number, plays in (
            (
                1,
                [
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_02"},
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_03"},
                    {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                ],
            ),
            (
                2,
                [
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_04"},
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_05"},
                    {"player_id": "p_witcher_2", "card_id": "gwent_unit_02"},
                ],
            ),
        ):
            round_payload = self._post_ok(
                client,
                f"/api/pvp/matches/{match_id}/rounds",
                headers=MASTER_HEADERS,
                json={"round_number": round_number, "plays": plays},
            )
        self.assertEqual(round_payload["match"]["winner_id"], "p_witcher_1")
        loser_finish = self._post_ok(
            client,
            f"/api/pvp/matches/{match_id}/finish",
            headers=WITCHER_2_HEADERS,
            json={"winner_id": "p_witcher_2"},
        )
        self.assertEqual(loser_finish["match"]["status"], "needs_master_review")
        self.assertEqual(loser_finish["match"]["review_reason"], "winner_override_requires_master_review")
        self.assertEqual(loser_finish["stake_transfer"]["status"], "not_applied")

        lord_state = client.get("/api/lords/p_lord_1/state", headers=LORD_NORTH_HEADERS)
        self.assertEqual(lord_state.status_code, 200, lord_state.text)
        with connect(settings) as connection:
            mp_before = self._current_mp(connection, "domain_north")
        impossible_route = client.post(
            "/api/lords/p_lord_1/move",
            headers=LORD_NORTH_HEADERS,
            json={
                "to_node_id": "node_well_city",
                "route_node_ids": ["node_res_north", "node_well_city"],
            },
        )
        self.assertEqual(impossible_route.status_code, 400, impossible_route.text)
        self.assertEqual(impossible_route.json()["detail"]["code"], "invalid_route")
        with connect(settings) as connection:
            self.assertEqual(self._current_mp(connection, "domain_north"), mp_before)
            forest_gold_before = self._domain_gold(connection, "domain_forest")

        created_order = self._post_ok(
            client,
            "/api/lords/p_lord_3/orders",
            headers=LORD_FOREST_HEADERS,
            json={
                "action": "create",
                "order_id": "fresh_escrow_order",
                "object_id": "territory_lake_mist",
                "visibility": "public",
                "escrow_reward_id": "reward_order_success",
            },
        )
        self.assertEqual(created_order["status"], "created")
        with connect(settings) as connection:
            escrow = connection.execute(
                """
                SELECT reserved_gold, status
                FROM escrow_ledger
                WHERE order_id = 'fresh_escrow_order'
                """
            ).fetchone()
            forest_gold_after_reserve = self._domain_gold(connection, "domain_forest")
        self.assertEqual(escrow["status"], "reserved")
        self.assertEqual(forest_gold_after_reserve, forest_gold_before - escrow["reserved_gold"])

        cancelled = self._post_ok(
            client,
            "/api/lords/p_lord_3/orders",
            headers=LORD_FOREST_HEADERS,
            json={"action": "cancel", "order_id": "fresh_escrow_order"},
        )
        self.assertEqual(cancelled["status"], "cancelled_by_lord")
        with connect(settings) as connection:
            released = connection.execute(
                """
                SELECT status
                FROM escrow_ledger
                WHERE order_id = 'fresh_escrow_order'
                """
            ).fetchone()
            self.assertEqual(self._domain_gold(connection, "domain_forest"), forest_gold_before)
        self.assertEqual(released["status"], "released")

    def test_task065_review_corrections_and_reputation_are_master_scoped(self) -> None:
        settings = self._settings("fresh_review_reputation")
        self._import_seed(settings)
        client = TestClient(create_app(settings))

        with connect(settings) as connection:
            review_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 11, 0, tzinfo=UTC),
            )
        review_payload["physical_presence_confirmed"] = False
        review_sync = self._sync_api(
            client,
            headers=WITCHER_1_HEADERS,
            event_id="fresh_review_correction_event",
            actor_id="p_witcher_1",
            event_type="pve_completed",
            payload=review_payload,
            sequence=1,
        )
        self.assertEqual(review_sync["results"][0]["status"], "needs_master_review")

        player_review_attempt = client.post(
            "/api/events/fresh_review_correction_event/review",
            headers=WITCHER_1_HEADERS,
            json={
                "action": "approve",
                "operator": "p_witcher_1",
                "reason": "player tries to self-approve",
            },
        )
        self.assertEqual(player_review_attempt.status_code, 401)

        corrected = self._post_ok(
            client,
            "/api/events/fresh_review_correction_event/review",
            headers=MASTER_HEADERS,
            json={
                "action": "correct",
                "operator": "gm_fresh",
                "reason": "paper witness confirmed physical presence",
                "severity": "P1",
                "correction": {"payload": {"physical_presence_confirmed": True}},
            },
        )
        self.assertEqual(corrected["decision"]["status"], "applied")
        self.assertEqual(corrected["review"]["status"], "corrected")
        self.assertEqual(corrected["event"]["status"], "accepted")
        self.assertEqual(corrected["correction"]["action"], "correct")
        with connect(settings) as connection:
            pve_attempts = connection.execute(
                """
                SELECT COUNT(*)
                FROM pve_attempts
                WHERE server_event_id = ?
                """,
                (corrected["event"]["server_event_id"],),
            ).fetchone()[0]
            correction_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM master_corrections
                WHERE event_id = 'fresh_review_correction_event'
                """
            ).fetchone()[0]
        self.assertEqual(pve_attempts, 1)
        self.assertEqual(correction_count, 1)

        foreign_reputation = client.get(
            "/api/players/p_witcher_1/reputation",
            headers=WITCHER_2_HEADERS,
        )
        own_reputation = client.get(
            "/api/players/p_witcher_1/reputation",
            headers=WITCHER_1_HEADERS,
        )
        master_reputation = client.get(
            "/api/master/reputation/p_witcher_1",
            headers=MASTER_HEADERS,
        )
        lord_reputation_change = client.post(
            "/api/master/reputation/p_lord_1/change",
            headers=MASTER_HEADERS,
            json={"delta": 1, "reason": "lords do not use Good/Evil reputation"},
        )

        self.assertEqual(foreign_reputation.status_code, 403)
        self.assertEqual(own_reputation.status_code, 200, own_reputation.text)
        self.assertNotIn("value", own_reputation.json())
        self.assertEqual(master_reputation.status_code, 200, master_reputation.text)
        self.assertIn("value", master_reputation.json())
        self.assertEqual(lord_reputation_change.status_code, 400)
        self.assertIn("Reputation applies only to witchers and sorceresses", lord_reputation_change.text)

    def _settings(self, name: str) -> Settings:
        return Settings(
            database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db",
            backup_dir=TEST_TMP_ROOT / f"{name}_backups_{uuid4().hex}",
        )

    def _import_seed(self, settings: Settings):
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")
        return report

    def _sync_api(
        self,
        client: TestClient,
        *,
        headers: dict[str, str],
        event_id: str,
        actor_id: str,
        event_type: str,
        payload: dict[str, object],
        sequence: int,
        actor_type: str = "player",
    ) -> dict[str, object]:
        response = client.post(
            "/api/events/sync",
            headers=headers,
            json={
                "device_id": f"phone-{event_id}",
                "actor_id": actor_id,
                "actor_type": actor_type,
                "events": [
                    {
                        "event_id": event_id,
                        "client_sequence": sequence,
                        "created_at": "2026-06-02T09:00:00+00:00",
                        "event_type": event_type,
                        "payload": payload,
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _post_ok(self, client: TestClient, url: str, **kwargs) -> dict[str, object]:
        response = client.post(url, **kwargs)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _review_reasons(
        self,
        connection,
        event_ids: tuple[str, ...],
    ) -> dict[str, str]:
        placeholders = ", ".join("?" for _ in event_ids)
        return {
            row["event_id"]: row["reason"]
            for row in connection.execute(
                f"""
                SELECT event_id, reason
                FROM event_reviews
                WHERE event_id IN ({placeholders})
                """,
                event_ids,
            ).fetchall()
        }

    def _copy_gwent_deck(self, connection, player_id: str) -> None:
        source = connection.execute(
            """
            SELECT *
            FROM gwent_decks
            WHERE player_id = 'p_witcher_1'
            LIMIT 1
            """
        ).fetchone()
        self.assertIsNotNone(source)
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
                950,
                f"deck_fresh_{player_id}",
                player_id,
                source["leader_card_id"],
                source["card_ids"],
            ),
        )

    def _grant_item(self, connection, asset_id: str, owner_player_id: str) -> None:
        self._ensure_item_asset(connection, asset_id)
        grant_asset_ownership(
            connection,
            owner_player_id=owner_player_id,
            asset_type="item",
            asset_id=asset_id,
            source="test_stage1_fresh_regression",
            source_ref_id=asset_id,
        )

    def _ensure_item_asset(self, connection, asset_id: str) -> None:
        connection.execute(
            """
            INSERT INTO items (
                _import_run_id, _row_number, item_id, item_type, tier,
                stat_requirement_json, effect_json
            )
            SELECT
                COALESCE((SELECT _import_run_id FROM items LIMIT 1), 'test_fresh'),
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

    def _challenge_tokens(self, connection, player_id: str) -> int:
        return int(
            connection.execute(
                """
                SELECT challenge_tokens
                FROM player_runtime_state
                WHERE player_id = ?
                """,
                (player_id,),
            ).fetchone()["challenge_tokens"]
        )

    def _current_mp(self, connection, domain_id: str) -> int:
        return int(
            connection.execute(
                """
                SELECT current_mp
                FROM domain_runtime_state
                WHERE domain_id = ?
                """,
                (domain_id,),
            ).fetchone()["current_mp"]
        )

    def _domain_gold(self, connection, domain_id: str) -> int:
        return int(
            connection.execute(
                """
                SELECT gold
                FROM domain_runtime_state
                WHERE domain_id = ?
                """,
                (domain_id,),
            ).fetchone()["gold"]
        )


if __name__ == "__main__":
    unittest.main()
