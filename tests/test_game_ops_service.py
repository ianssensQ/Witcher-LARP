from __future__ import annotations

import unittest
from uuid import uuid4

from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.event_models import EventSyncEvent, EventSyncRequest
from backend.witcher_larp.event_service import sync_events
from backend.witcher_larp.game_ops_service import GameOpsCorrectionError
from backend.witcher_larp.game_ops_service import apply_admin_setup_grant
from backend.witcher_larp.game_ops_service import apply_game_ops_correction, build_master_state
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.runtime_schema import log_event
from backend.witcher_larp.snapshot_exporter import build_snapshot_from_database


FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"


class GameOpsServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        (PROJECT_ROOT / ".test-data").mkdir(exist_ok=True)

    def test_master_state_exposes_event_sync_anti_snowball_and_economy_payloads(self) -> None:
        settings = self._settings("game_ops_state")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            log_event(
                connection,
                "admin_smoke_event",
                {"actor_id": "gm_ops", "paper_form_id": "paper-smoke-1"},
                source="test_game_ops",
            )
            sync_events(
                connection,
                EventSyncRequest(
                    device_id="admin-sync-phone-1",
                    actor_id="p_witcher_1",
                    actor_type="witcher",
                    events=[
                        EventSyncEvent(
                            event_id=f"admin_sync_{uuid4().hex}",
                            client_sequence=1,
                            created_at="2026-06-02T10:00:00+00:00",
                            event_type="qr_scene_started",
                            payload={"qr_id": "qr_a1_001", "source": "mobile"},
                        )
                    ],
                ),
            )

            state = build_master_state(connection, settings)

        self.assertTrue(
            any(row["event_type"] == "admin_smoke_event" for row in state["events"]["recent"])
        )
        self.assertTrue(
            any(row["client_id"] == "admin-sync-phone-1" for row in state["events"]["sync_statuses"])
        )
        self.assertTrue(state["lord_map"]["domains"])
        self.assertTrue(
            all("anti_snowball" in domain for domain in state["lord_map"]["domains"])
        )
        self.assertTrue(state["economy"]["potion_markets"])
        self.assertTrue(state["economy"]["trade_transfers"])
        self.assertGreaterEqual(state["economy"]["summary"]["player_rows"], 13)

    def test_potion_trade_and_player_corrections_are_audited(self) -> None:
        settings = self._settings("game_ops_corrections")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            state = build_master_state(connection, settings)
            market = state["economy"]["potion_markets"][0]
            transfer = state["economy"]["trade_transfers"][0]
            player = next(
                row for row in state["economy"]["player_economy"] if row["player_id"] == "p_witcher_1"
            )

            market_correction = apply_game_ops_correction(
                connection,
                target_type="potion_market",
                target_id=market["market_id"],
                patch={"stock": int(market["stock"]) + 2},
                operator="gm_ops",
                reason="paper potion market sheet checked",
            )
            trade_correction = apply_game_ops_correction(
                connection,
                target_type="trade_transfer",
                target_id=transfer["transfer_id"],
                patch={"status": "contested_review", "price_gold": 3},
                operator="gm_ops",
                reason="paper trade sheet conflicts with digital transfer",
            )
            player_correction = apply_game_ops_correction(
                connection,
                target_type="player",
                target_id=player["player_id"],
                patch={
                    "gold": int(player["gold"]) + 5,
                    "challenge_tokens": int(player["challenge_tokens"]) + 2,
                },
                operator="gm_ops",
                reason="paper economy recovery checked",
            )
            goal_correction = apply_game_ops_correction(
                connection,
                target_type="personal_goal",
                target_id="goal_witcher_1",
                patch={"public_text": "Закрыть контракт на чудовище у мастера"},
                operator="gm_ops",
                reason="player goal text clarified for journal screen",
            )
            gold_grant = apply_admin_setup_grant(
                connection,
                player_id="p_witcher_1",
                grant_type="gold",
                quantity=7,
                operator="gm_ops",
                reason="starting purse counted at registration",
            )
            card_grant = apply_admin_setup_grant(
                connection,
                player_id="p_witcher_1",
                grant_type="card",
                asset_id="pc_infantry_t1",
                quantity=2,
                operator="gm_ops",
                reason="starting cards counted at registration",
            )
            final_state = build_master_state(connection, settings)
            scoped_snapshot = build_snapshot_from_database(
                connection,
                player_code="WC-WOLF-6GF4",
            )

        self.assertEqual(market_correction["target_type"], "potion_market")
        self.assertEqual(market_correction["after"]["stock"], int(market["stock"]) + 2)
        self.assertEqual(trade_correction["target_type"], "trade_transfer")
        self.assertEqual(trade_correction["after"]["status"], "contested_review")
        self.assertEqual(trade_correction["after"]["price_gold"], 3)
        self.assertEqual(player_correction["target_type"], "player")
        self.assertEqual(player_correction["after"]["gold"], int(player["gold"]) + 5)
        self.assertEqual(
            player_correction["after"]["challenge_tokens"],
            int(player["challenge_tokens"]) + 2,
        )
        self.assertEqual(gold_grant["grant"]["grant_type"], "gold")
        self.assertEqual(
            gold_grant["grant"]["after"]["gold"],
            player_correction["after"]["gold"] + 7,
        )
        self.assertEqual(card_grant["grant"]["grant_type"], "card")
        self.assertEqual(
            card_grant["grant"]["after"]["quantity"],
            card_grant["grant"]["before"]["quantity"] + 2,
        )
        self.assertEqual(goal_correction["target_type"], "personal_goal")
        self.assertEqual(
            goal_correction["after"]["public_text"],
            "Закрыть контракт на чудовище у мастера",
        )
        self.assertIsNotNone(scoped_snapshot)
        assert scoped_snapshot is not None
        self.assertEqual(
            scoped_snapshot["goals"]["personal_goals"][0]["public_text"],
            "Закрыть контракт на чудовище у мастера",
        )
        recent_types = {row["target_type"] for row in final_state["corrections"]}
        self.assertIn("potion_market", recent_types)
        self.assertIn("trade_transfer", recent_types)
        self.assertIn("player", recent_types)
        self.assertIn("personal_goal", recent_types)
        self.assertTrue(final_state["economy"]["personal_goals"])
        self.assertGreaterEqual(final_state["admin_setup"]["summary"]["field_players"], 9)
        setup_player = next(
            row for row in final_state["admin_setup"]["players"] if row["player_id"] == "p_witcher_1"
        )
        self.assertEqual(setup_player["readiness_status"], "ready")
        self.assertGreaterEqual(setup_player["asset_counts"]["card"]["quantity"], 2)
        self.assertTrue(final_state["admin_setup"]["asset_catalog"]["card"])
        self.assertEqual(final_state["admin_setup"]["recent_grants"][0]["grant_type"], "card")

    def test_master_state_exposes_lord_command_center_payloads(self) -> None:
        settings = self._settings("game_ops_lord_command")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            build_master_state(connection, settings)
            now = "2026-06-02T10:00:00+00:00"
            connection.execute(
                """
                INSERT OR REPLACE INTO garrison_runtime_state (
                    garrison_id, territory_id, domain_id, card_id, count, status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "garrison_ops_watch",
                    "territory_fort_east",
                    "domain_north",
                    "unit_infantry_t1",
                    4,
                    "active",
                    now,
                ),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO pending_lord_moves (
                    move_id, domain_id, lord_id, from_node_id, to_node_id,
                    requested_to_node_id, route_node_ids_json, mp_cost, status,
                    source, started_at, arrival_at, completed_at, result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "move_ops_watch",
                    "domain_north",
                    "p_lord_1",
                    "node_res_north",
                    "node_fort_east",
                    "node_fort_east",
                    '["node_res_north", "node_fort_east"]',
                    2,
                    "pending",
                    "test_game_ops",
                    now,
                    "2026-06-02T10:30:00+00:00",
                    None,
                    "{}",
                ),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO order_runtime_state (
                    order_id, lord_id, target_player_id, object_id, visibility,
                    status, escrow_reward_id, accepted_by_player_id,
                    submitted_by_player_id, result_event_id, reason, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "order_ops_watch",
                    "p_lord_1",
                    "p_witcher_1",
                    "territory_fort_east",
                    "public",
                    "published",
                    None,
                    None,
                    None,
                    None,
                    None,
                    now,
                    now,
                ),
            )
            state = build_master_state(connection, settings)

        domain = next(
            row for row in state["lord_map"]["domains"] if row["domain_id"] == "domain_north"
        )
        territory = next(
            row
            for row in state["lord_map"]["territories"]
            if row["territory_id"] == "territory_fort_east"
        )
        self.assertEqual(domain["current_node"]["node_id"], "node_res_north")
        self.assertTrue(any(row["order_id"] == "order_ops_watch" for row in domain["orders"]))
        self.assertGreaterEqual(domain["active_order_count"], 1)
        self.assertTrue(any(row["move_id"] == "move_ops_watch" for row in domain["pending_moves"]))
        self.assertTrue(any(row["garrison_id"] == "garrison_ops_watch" for row in domain["garrisons"]))
        self.assertTrue(
            any(row["garrison_id"] == "garrison_ops_watch" for row in territory["garrisons"])
        )

    def test_correction_requires_operator_reason_and_supported_fields(self) -> None:
        settings = self._settings("game_ops_correction_errors")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            market_id = build_master_state(connection, settings)["economy"]["potion_markets"][0][
                "market_id"
            ]
            with self.assertRaises(GameOpsCorrectionError) as missing_reason:
                apply_game_ops_correction(
                    connection,
                    target_type="potion_market",
                    target_id=market_id,
                    patch={"stock": 3},
                    operator="gm_ops",
                    reason=" ",
                )
            with self.assertRaises(GameOpsCorrectionError) as unsupported_field:
                apply_game_ops_correction(
                    connection,
                    target_type="potion_market",
                    target_id=market_id,
                    patch={"silent_overwrite": "yes"},
                    operator="gm_ops",
                    reason="paper stock checked",
                )

        self.assertEqual(missing_reason.exception.code, "missing_reason")
        self.assertEqual(unsupported_field.exception.code, "unsupported_patch_field")

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=PROJECT_ROOT / ".test-data" / f"{name}_{uuid4().hex}.db")

    def _import_valid_seed(self, settings: Settings) -> None:
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")


if __name__ == "__main__":
    unittest.main()
