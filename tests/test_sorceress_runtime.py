from __future__ import annotations

from datetime import UTC, datetime
import json
import unittest
from uuid import uuid4

from backend.witcher_larp.app import create_app
from backend.witcher_larp.asset_service import grant_asset_ownership
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.sorceress_service import SorceressError
from backend.witcher_larp.sorceress_service import accept_favorite, accept_trade_transfer
from backend.witcher_larp.sorceress_service import buy_potion
from backend.witcher_larp.sorceress_service import cast_spell, create_favorite_request
from backend.witcher_larp.sorceress_service import create_trade_transfer
from backend.witcher_larp.sorceress_service import decline_trade_transfer
from backend.witcher_larp.sorceress_service import ensure_sorceress_runtime_state
from backend.witcher_larp.sorceress_service import get_sorceress_state
from backend.witcher_larp.sorceress_service import record_alignment_evidence
from backend.witcher_larp.sorceress_service import transfer_potion, use_potion_in_scene

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"


class SorceressRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_spell_cast_spends_mana_records_effect_and_reviews_post_final_intent(self) -> None:
        settings = self.prepare_seed("sorc_spell")
        now = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)

        with connect(settings) as connection:
            ensure_sorceress_runtime_state(connection)
            connection.execute(
                """
                UPDATE player_runtime_state
                SET mana = 4
                WHERE player_id = 'p_sorc_1'
                """
            )
            cast = cast_spell(
                connection,
                sorceress_id="p_sorc_1",
                spell_id="spell_ward_t2",
                target_type="territory",
                target_id="territory_magic_corner",
                visibility="visible_log",
                now=now,
            )
            mana_after_cast = connection.execute(
                "SELECT mana FROM player_runtime_state WHERE player_id = 'p_sorc_1'"
            ).fetchone()["mana"]
            effect = connection.execute(
                """
                SELECT target_type, target_id, effect_json, visibility, status
                FROM magic_effects
                WHERE cast_id = ?
                """,
                (cast["cast_id"],),
            ).fetchone()

            connection.execute(
                """
                UPDATE final_lock_state
                SET locked_at = ?, operator = 'gm', source = 'test'
                WHERE id = 1
                """,
                (datetime(2026, 6, 2, 17, 15, tzinfo=UTC).isoformat(timespec="seconds"),),
            )
            connection.execute(
                """
                UPDATE player_runtime_state
                SET mana = 4
                WHERE player_id = 'p_sorc_1'
                """
            )
            review = cast_spell(
                connection,
                sorceress_id="p_sorc_1",
                spell_id="spell_ritual_t4",
                target_type="final_hook",
                target_id="hook_sorc_intent",
                now=now,
            )
            mana_after_review = connection.execute(
                "SELECT mana FROM player_runtime_state WHERE player_id = 'p_sorc_1'"
            ).fetchone()["mana"]
            intent = connection.execute(
                """
                SELECT status, review_reason, locked_at
                FROM locked_magical_intent
                WHERE cast_id = ?
                """,
                (review["cast_id"],),
            ).fetchone()

        self.assertEqual(cast["status"], "accepted")
        self.assertEqual(cast["mana_after"], 2)
        self.assertEqual(mana_after_cast, 2)
        self.assertEqual(effect["target_type"], "territory")
        self.assertEqual(effect["target_id"], "territory_magic_corner")
        self.assertEqual(json.loads(effect["effect_json"])["effect"], "raid_resistance_plus_1")
        self.assertEqual(effect["visibility"], "visible_log")
        self.assertEqual(effect["status"], "active")

        self.assertEqual(review["status"], "needs_master_review")
        self.assertEqual(
            review["review_reason"],
            "magical intent after final lock requires master review",
        )
        self.assertEqual(mana_after_review, 4)
        self.assertEqual(intent["status"], "needs_master_review")
        self.assertIsNone(intent["locked_at"])

    def test_spell_rejects_insufficient_mana_and_target_type_without_side_effects(self) -> None:
        settings = self.prepare_seed("sorc_spell_rejects")

        with connect(settings) as connection:
            ensure_sorceress_runtime_state(connection)
            connection.execute(
                """
                UPDATE player_runtime_state
                SET mana = 0
                WHERE player_id = 'p_sorc_1'
                """
            )
            with self.assertRaises(SorceressError) as insufficient:
                cast_spell(
                    connection,
                    sorceress_id="p_sorc_1",
                    spell_id="spell_boost_t1",
                    target_type="player",
                    target_id="p_witcher_1",
                )
            mana_after_failed_cast = connection.execute(
                "SELECT mana FROM player_runtime_state WHERE player_id = 'p_sorc_1'"
            ).fetchone()["mana"]
            cast_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM sorceress_spell_casts
                WHERE sorceress_id = 'p_sorc_1'
                """
            ).fetchone()[0]

            connection.execute(
                """
                UPDATE player_runtime_state
                SET mana = 4
                WHERE player_id = 'p_sorc_1'
                """
            )
            with self.assertRaises(SorceressError) as target_mismatch:
                cast_spell(
                    connection,
                    sorceress_id="p_sorc_1",
                    spell_id="spell_ward_t2",
                    target_type="player",
                    target_id="p_witcher_1",
                )

        self.assertEqual(insufficient.exception.code, "insufficient_mana")
        self.assertEqual(mana_after_failed_cast, 0)
        self.assertEqual(cast_count, 0)
        self.assertEqual(target_mismatch.exception.code, "spell_target_type_mismatch")

    def test_spell_target_validation_accepts_scene_and_object_but_rejects_unknown_target_without_mana_spend(self) -> None:
        settings = self.prepare_seed("sorc_spell_targets")

        with connect(settings) as connection:
            ensure_sorceress_runtime_state(connection)
            connection.execute(
                """
                UPDATE player_runtime_state
                SET mana = 6
                WHERE player_id = 'p_sorc_1'
                """
            )
            scene_cast = cast_spell(
                connection,
                sorceress_id="p_sorc_1",
                spell_id="spell_hint_t1",
                target_type="scene",
                target_id="scn_a1_001",
            )
            object_cast = cast_spell(
                connection,
                sorceress_id="p_sorc_1",
                spell_id="spell_reveal_t2",
                target_type="object",
                target_id="qr_a1_001",
            )
            mana_after_valid_targets = connection.execute(
                "SELECT mana FROM player_runtime_state WHERE player_id = 'p_sorc_1'"
            ).fetchone()["mana"]
            with self.assertRaises(SorceressError) as missing_target:
                cast_spell(
                    connection,
                    sorceress_id="p_sorc_1",
                    spell_id="spell_hint_t1",
                    target_type="scene",
                    target_id="",
                )
            with self.assertRaises(SorceressError) as unknown_object:
                cast_spell(
                    connection,
                    sorceress_id="p_sorc_1",
                    spell_id="spell_reveal_t2",
                    target_type="object",
                    target_id="no_such_object",
                )
            mana_after_rejected_targets = connection.execute(
                "SELECT mana FROM player_runtime_state WHERE player_id = 'p_sorc_1'"
            ).fetchone()["mana"]

        self.assertEqual(scene_cast["status"], "accepted")
        self.assertEqual(scene_cast["effect"]["effect"], "reveal_hint")
        self.assertEqual(object_cast["status"], "accepted")
        self.assertEqual(object_cast["effect"]["effect"], "reveal_hidden_flag")
        self.assertEqual(mana_after_valid_targets, 3)
        self.assertEqual(missing_target.exception.code, "missing_target")
        self.assertEqual(unknown_object.exception.code, "unknown_spell_target")
        self.assertEqual(mana_after_rejected_targets, 3)

    def test_potion_wholesale_transfer_and_scene_cap(self) -> None:
        settings = self.prepare_seed("sorc_potions")

        with connect(settings) as connection:
            with self.assertRaisesRegex(SorceressError, "not a sorceress"):
                buy_potion(
                    connection,
                    buyer_id="p_witcher_1",
                    potion_id="potion_common_swallow",
                )

            bought = buy_potion(
                connection,
                buyer_id="p_sorc_1",
                potion_id="potion_common_swallow",
                quantity=3,
            )
            sold = transfer_potion(
                connection,
                from_player_id="p_sorc_1",
                to_player_id="p_witcher_1",
                potion_id="potion_common_swallow",
                quantity=1,
                price_gold=12,
                mode="sell",
                auto_accept=True,
            )
            gifted = transfer_potion(
                connection,
                from_player_id="p_sorc_1",
                to_player_id="p_witcher_1",
                potion_id="potion_common_swallow",
                quantity=2,
                mode="gift",
                auto_accept=True,
            )
            first_use = use_potion_in_scene(
                connection,
                player_id="p_witcher_1",
                potion_id="potion_common_swallow",
                scene_id="scn_a1_001",
            )
            with self.assertRaisesRegex(SorceressError, "one potion"):
                use_potion_in_scene(
                    connection,
                    player_id="p_witcher_1",
                    potion_id="potion_common_swallow",
                    scene_id="scn_a1_001",
                )
            sorceress = connection.execute(
                "SELECT gold FROM player_runtime_state WHERE player_id = 'p_sorc_1'"
            ).fetchone()
            witcher = connection.execute(
                "SELECT gold FROM player_runtime_state WHERE player_id = 'p_witcher_1'"
            ).fetchone()
            market = connection.execute(
                """
                SELECT stock
                FROM potion_market_runtime
                WHERE potion_id = 'potion_common_swallow'
                """
            ).fetchone()

        self.assertEqual(bought["total_cost"], 24)
        self.assertEqual(bought["inventory"]["quantity"], 3)
        self.assertEqual(sold["status"], "accepted")
        self.assertEqual(sold["price_gold"], 12)
        self.assertEqual(gifted["status"], "accepted")
        self.assertEqual(first_use["max_potions_per_scene"], 1)
        self.assertEqual(first_use["inventory"]["quantity"], 3)
        self.assertEqual(sorceress["gold"], 18)
        self.assertEqual(witcher["gold"], 8)
        self.assertEqual(market["stock"], 5)

    def test_potion_buy_rejects_invalid_quantity_stock_and_gold_without_inventory_side_effects(self) -> None:
        settings = self.prepare_seed("sorc_potion_buy_rejects")

        with connect(settings) as connection:
            ensure_sorceress_runtime_state(connection)
            with self.assertRaises(SorceressError) as invalid_quantity:
                buy_potion(
                    connection,
                    buyer_id="p_sorc_1",
                    potion_id="potion_common_swallow",
                    quantity=0,
                )

            connection.execute(
                """
                UPDATE potion_market_runtime
                SET stock = 0
                WHERE potion_id = 'potion_common_swallow'
                """
            )
            with self.assertRaises(SorceressError) as empty_stock:
                buy_potion(
                    connection,
                    buyer_id="p_sorc_1",
                    potion_id="potion_common_swallow",
                    quantity=1,
                )

            connection.execute(
                """
                UPDATE potion_market_runtime
                SET stock = 8
                WHERE potion_id = 'potion_common_swallow'
                """
            )
            connection.execute(
                """
                UPDATE player_runtime_state
                SET gold = 7
                WHERE player_id = 'p_sorc_1'
                """
            )
            with self.assertRaises(SorceressError) as insufficient_gold:
                buy_potion(
                    connection,
                    buyer_id="p_sorc_1",
                    potion_id="potion_common_swallow",
                    quantity=1,
                )
            state = connection.execute(
                """
                SELECT gold
                FROM player_runtime_state
                WHERE player_id = 'p_sorc_1'
                """
            ).fetchone()
            market = connection.execute(
                """
                SELECT stock
                FROM potion_market_runtime
                WHERE potion_id = 'potion_common_swallow'
                """
            ).fetchone()
            inventory_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM potion_inventory
                WHERE player_id = 'p_sorc_1'
                  AND potion_id = 'potion_common_swallow'
                """
            ).fetchone()[0]

        self.assertEqual(invalid_quantity.exception.code, "invalid_quantity")
        self.assertEqual(empty_stock.exception.code, "market_stock_empty")
        self.assertEqual(insufficient_gold.exception.code, "insufficient_gold")
        self.assertEqual(state["gold"], 7)
        self.assertEqual(market["stock"], 8)
        self.assertEqual(inventory_count, 0)

    def test_potion_resale_price_policy_hard_blocks_out_of_band_gold(self) -> None:
        settings = self.prepare_seed("sorc_potion_price")

        with connect(settings) as connection:
            buy_potion(
                connection,
                buyer_id="p_sorc_1",
                potion_id="potion_common_swallow",
                quantity=2,
            )
            with self.assertRaises(SorceressError) as below_band:
                transfer_potion(
                    connection,
                    from_player_id="p_sorc_1",
                    to_player_id="p_witcher_1",
                    potion_id="potion_common_swallow",
                    price_gold=11,
                    mode="sell",
                )
            with self.assertRaises(SorceressError) as above_band:
                transfer_potion(
                    connection,
                    from_player_id="p_sorc_1",
                    to_player_id="p_witcher_1",
                    potion_id="potion_common_swallow",
                    price_gold=16,
                    mode="sell",
                )
            with self.assertRaises(SorceressError) as priced_exchange:
                transfer_potion(
                    connection,
                    from_player_id="p_sorc_1",
                    to_player_id="p_witcher_1",
                    potion_id="potion_common_swallow",
                    price_gold=12,
                    mode="exchange",
                )
            valid = transfer_potion(
                connection,
                from_player_id="p_sorc_1",
                to_player_id="p_witcher_1",
                potion_id="potion_common_swallow",
                price_gold=12,
                mode="sell",
            )

        self.assertEqual(below_band.exception.code, "resale_price_out_of_band")
        self.assertEqual(above_band.exception.code, "resale_price_out_of_band")
        self.assertEqual(priced_exchange.exception.code, "exchange_price_forbidden")
        self.assertEqual(valid["status"], "pending_locked")
        self.assertEqual(valid["price_gold"], 12)

    def test_pending_trade_requires_target_consent_and_decline_releases_locked_potion(self) -> None:
        settings = self.prepare_seed("sorc_trade_consent")

        with connect(settings) as connection:
            buy_potion(
                connection,
                buyer_id="p_sorc_1",
                potion_id="potion_common_swallow",
                quantity=1,
            )
            pending = transfer_potion(
                connection,
                from_player_id="p_sorc_1",
                to_player_id="p_witcher_1",
                potion_id="potion_common_swallow",
                transfer_id="trade_consent_demo",
            )
            inventory_after_lock = connection.execute(
                """
                SELECT quantity
                FROM potion_inventory
                WHERE player_id = 'p_sorc_1'
                  AND potion_id = 'potion_common_swallow'
                """
            ).fetchone()["quantity"]
            with self.assertRaises(SorceressError) as wrong_target:
                accept_trade_transfer(
                    connection,
                    "trade_consent_demo",
                    accepted_by_player_id="p_witcher_2",
                )
            declined = decline_trade_transfer(
                connection,
                "trade_consent_demo",
                declined_by_player_id="p_sorc_1",
                reason="owner_cancelled",
            )
            inventory_after_decline = connection.execute(
                """
                SELECT quantity
                FROM potion_inventory
                WHERE player_id = 'p_sorc_1'
                  AND potion_id = 'potion_common_swallow'
                """
            ).fetchone()["quantity"]
            lock = connection.execute(
                """
                SELECT status, reason
                FROM asset_locks
                WHERE source_ref_id = 'trade_consent_demo'
                """
            ).fetchone()

        self.assertEqual(pending["status"], "pending_locked")
        self.assertEqual(inventory_after_lock, 0)
        self.assertEqual(wrong_target.exception.code, "trade_consent_mismatch")
        self.assertEqual(declined["status"], "cancelled")
        self.assertEqual(declined["closed_by_player_id"], "p_sorc_1")
        self.assertEqual(inventory_after_decline, 1)
        self.assertEqual(lock["status"], "released")
        self.assertEqual(lock["reason"], "owner_cancelled")

    def test_transfer_guardrails_duplicate_modes_prices_and_auto_accept_gold(self) -> None:
        settings = self.prepare_seed("sorc_trade_guardrails")

        with connect(settings) as connection:
            buy_potion(
                connection,
                buyer_id="p_sorc_1",
                potion_id="potion_common_swallow",
                quantity=2,
            )

            with self.assertRaises(SorceressError) as invalid_potion_mode:
                transfer_potion(
                    connection,
                    from_player_id="p_sorc_1",
                    to_player_id="p_witcher_1",
                    potion_id="potion_common_swallow",
                    mode="loan",
                )
            with self.assertRaises(SorceressError) as invalid_potion_quantity:
                transfer_potion(
                    connection,
                    from_player_id="p_sorc_1",
                    to_player_id="p_witcher_1",
                    potion_id="potion_common_swallow",
                    quantity=0,
                )

            connection.execute(
                "UPDATE player_runtime_state SET gold = 5 WHERE player_id = 'p_witcher_1'"
            )
            with self.assertRaises(SorceressError) as auto_accept_gold:
                transfer_potion(
                    connection,
                    from_player_id="p_sorc_1",
                    to_player_id="p_witcher_1",
                    potion_id="potion_common_swallow",
                    quantity=1,
                    price_gold=12,
                    mode="sell",
                    transfer_id="trade_auto_gold_blocked",
                    auto_accept=True,
                )
            inventory_after_block = connection.execute(
                """
                SELECT quantity
                FROM potion_inventory
                WHERE player_id = 'p_sorc_1'
                  AND potion_id = 'potion_common_swallow'
                """
            ).fetchone()["quantity"]
            blocked_trade_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM trade_transfer_runtime
                WHERE transfer_id = 'trade_auto_gold_blocked'
                """
            ).fetchone()[0]

            valid = transfer_potion(
                connection,
                from_player_id="p_sorc_1",
                to_player_id="p_witcher_1",
                potion_id="potion_common_swallow",
                quantity=1,
                transfer_id="trade_duplicate_guard",
            )
            duplicate = transfer_potion(
                connection,
                from_player_id="p_sorc_1",
                to_player_id="p_witcher_1",
                potion_id="potion_common_swallow",
                quantity=1,
                transfer_id="trade_duplicate_guard",
            )

            with self.assertRaises(SorceressError) as invalid_asset_mode:
                create_trade_transfer(
                    connection,
                    from_player_id="p_witcher_1",
                    to_player_id="p_witcher_2",
                    asset_type="item",
                    asset_id="item_gwent_marker",
                    mode="loan",
                )
            with self.assertRaises(SorceressError) as invalid_asset_price:
                create_trade_transfer(
                    connection,
                    from_player_id="p_witcher_1",
                    to_player_id="p_witcher_2",
                    asset_type="item",
                    asset_id="item_gwent_marker",
                    mode="sell",
                    price_gold=-1,
                )
            with self.assertRaises(SorceressError) as gift_price:
                create_trade_transfer(
                    connection,
                    from_player_id="p_witcher_1",
                    to_player_id="p_witcher_2",
                    asset_type="item",
                    asset_id="item_gwent_marker",
                    mode="gift",
                    price_gold=1,
                )

        self.assertEqual(invalid_potion_mode.exception.code, "invalid_transfer_mode")
        self.assertEqual(invalid_potion_quantity.exception.code, "invalid_quantity")
        self.assertEqual(auto_accept_gold.exception.code, "insufficient_gold")
        self.assertEqual(inventory_after_block, 2)
        self.assertEqual(blocked_trade_count, 0)
        self.assertEqual(valid["status"], "pending_locked")
        self.assertFalse(valid["duplicate"])
        self.assertEqual(duplicate["status"], "pending_locked")
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(invalid_asset_mode.exception.code, "invalid_transfer_mode")
        self.assertEqual(invalid_asset_price.exception.code, "invalid_price")
        self.assertEqual(gift_price.exception.code, "gift_price_forbidden")

    def test_favorite_consent_caps_history_and_alignment_evidence(self) -> None:
        settings = self.prepare_seed("sorc_favorites")

        with connect(settings) as connection:
            requested = create_favorite_request(
                connection,
                sorceress_id="p_sorc_3",
                favored_player_id="p_witcher_2",
                slot="primary",
                favorite_id="fav_runtime_demo",
            )
            accepted = accept_favorite(
                connection,
                "fav_runtime_demo",
                accepted_by_player_id="p_witcher_2",
            )
            with self.assertRaisesRegex(SorceressError, "passive"):
                create_favorite_request(
                    connection,
                    sorceress_id="p_sorc_4",
                    favored_player_id="p_witcher_3",
                    slot="primary",
                    passive_bonus_requested=True,
                )
            with self.assertRaisesRegex(SorceressError, "once per act"):
                create_favorite_request(
                    connection,
                    sorceress_id="p_sorc_3",
                    favored_player_id="p_witcher_3",
                    slot="secondary",
                )
            with self.assertRaisesRegex(SorceressError, "maximum sorceress attention"):
                create_favorite_request(
                    connection,
                    sorceress_id="p_sorc_4",
                    favored_player_id="p_witcher_1",
                    slot="primary",
                )
            evidence = record_alignment_evidence(
                connection,
                sorceress_id="p_sorc_3",
                alignment_state="double_game",
                evidence_type="two_sided_evidence",
                payload={"lords": ["p_lord_1", "p_lord_3"]},
                final_flag=True,
            )
            state = get_sorceress_state(connection, "p_sorc_3")
            history_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM favorite_history
                WHERE favorite_id = 'fav_runtime_demo'
                """
            ).fetchone()[0]

        self.assertEqual(requested["status"], "pending")
        self.assertTrue(requested["consent_required"])
        self.assertFalse(requested["passive_bonus_allowed"])
        self.assertEqual(accepted["status"], "accepted")
        self.assertFalse(accepted["final_summary_signal"]["passive_runtime_bonus"])
        self.assertEqual(evidence["evidence_required"], "two_sided_evidence")
        self.assertTrue(evidence["final_flag"])
        self.assertEqual(state["favorites"][0]["favorite_id"], "fav_runtime_demo")
        self.assertEqual(state["alignment_evidence"][0]["alignment_state"], "double_game")
        self.assertEqual(history_count, 2)

    def test_favorite_duplicate_invalid_slot_wrong_accept_and_unknown_alignment_are_rejected(self) -> None:
        settings = self.prepare_seed("sorc_favorite_rejects")

        with connect(settings) as connection:
            first = create_favorite_request(
                connection,
                sorceress_id="p_sorc_3",
                favored_player_id="p_witcher_2",
                slot="primary",
                favorite_id="fav_reject_demo",
            )
            duplicate = create_favorite_request(
                connection,
                sorceress_id="p_sorc_3",
                favored_player_id="p_witcher_2",
                slot="primary",
                favorite_id="fav_reject_demo",
            )
            with self.assertRaises(SorceressError) as invalid_slot:
                create_favorite_request(
                    connection,
                    sorceress_id="p_sorc_4",
                    favored_player_id="p_witcher_3",
                    slot="tertiary",
                )
            with self.assertRaises(SorceressError) as wrong_accept:
                accept_favorite(
                    connection,
                    "fav_reject_demo",
                    accepted_by_player_id="p_witcher_3",
                )
            with self.assertRaises(SorceressError) as unknown_alignment:
                record_alignment_evidence(
                    connection,
                    sorceress_id="p_sorc_3",
                    alignment_state="triple_game",
                    evidence_type="two_sided_evidence",
                )
            history_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM favorite_history
                WHERE favorite_id = 'fav_reject_demo'
                """
            ).fetchone()[0]
            evidence_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM sorceress_alignment_evidence
                WHERE sorceress_id = 'p_sorc_3'
                """
            ).fetchone()[0]

        self.assertEqual(first["status"], "pending")
        self.assertFalse(first["duplicate"])
        self.assertEqual(duplicate["status"], "pending")
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(invalid_slot.exception.code, "invalid_favorite_slot")
        self.assertEqual(wrong_accept.exception.code, "favorite_consent_mismatch")
        self.assertEqual(unknown_alignment.exception.code, "unknown_alignment_state")
        self.assertEqual(history_count, 1)
        self.assertEqual(evidence_count, 0)

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_fastapi_sorceress_runtime_contract(self) -> None:
        settings = self.prepare_seed("sorc_api")
        with connect(settings) as connection:
            ensure_sorceress_runtime_state(connection)
            connection.execute(
                "UPDATE player_runtime_state SET mana = 2 WHERE player_id = 'p_sorc_1'"
            )
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="item_herb_bundle",
                source="test_seed",
                source_ref_id="api_trade_accept_owned",
            )
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="item_silver_dust",
                source="test_seed",
                source_ref_id="api_trade_decline_owned",
            )
        client = TestClient(create_app(settings))
        master = {"X-Role-Token": "MASTER-KING-4QZ8"}
        sorc_1 = {"X-Player-Code": "SC-MOON-4AD8"}
        sorc_3 = {"X-Player-Code": "SC-OWL-2RW7"}
        sorc_4 = {"X-Player-Code": "SC-STAR-5TN6"}
        witcher_1 = {"X-Player-Code": "WC-WOLF-6GF4"}
        witcher_2 = {"X-Player-Code": "WC-CAT-1HN8"}
        witcher_3 = {"X-Player-Code": "WC-GRIFFIN-7LX2"}

        state = client.get("/api/sorceresses/p_sorc_1/state", headers=sorc_1)
        cast = client.post(
            "/api/sorceresses/p_sorc_1/spells/cast",
            headers=sorc_1,
            json={
                "spell_id": "spell_boost_t1",
                "target_type": "player",
                "target_id": "p_witcher_1",
            },
        )
        bad_cast = client.post(
            "/api/sorceresses/p_sorc_1/spells/cast",
            headers=sorc_1,
            json={
                "spell_id": "spell_ward_t2",
                "target_type": "player",
                "target_id": "p_witcher_1",
            },
        )
        bought = client.post(
            "/api/sorceresses/p_sorc_1/potions/buy",
            headers=sorc_1,
            json={"potion_id": "potion_common_swallow", "quantity": 2},
        )
        potion_transfer = client.post(
            "/api/sorceresses/p_sorc_1/potions/transfer",
            headers=sorc_1,
            json={
                "transfer_id": "potion_api_transfer",
                "to_player_id": "p_witcher_1",
                "potion_id": "potion_common_swallow",
                "quantity": 1,
            },
        )
        potion_transfer_accepted = client.post(
            "/api/trade-transfers/potion_api_transfer/accept",
            headers=witcher_1,
            json={"accepted_by_player_id": "p_witcher_1"},
        )
        bad_potion_transfer = client.post(
            "/api/sorceresses/p_sorc_1/potions/transfer",
            headers=sorc_1,
            json={
                "to_player_id": "p_witcher_1",
                "potion_id": "potion_common_swallow",
                "quantity": 99,
            },
        )
        potion_use = client.post(
            "/api/players/p_witcher_1/potions/use",
            headers=witcher_1,
            json={"potion_id": "potion_common_swallow", "scene_id": "scn_a1_001"},
        )
        repeated_potion_use = client.post(
            "/api/players/p_witcher_1/potions/use",
            headers=witcher_1,
            json={"potion_id": "potion_common_swallow", "scene_id": "scn_a1_001"},
        )
        direct_witcher_buy = client.post(
            "/api/sorceresses/p_witcher_1/potions/buy",
            headers=master,
            json={"potion_id": "potion_common_swallow"},
        )
        trade_accept_create = client.post(
            "/api/trade-transfers",
            headers=witcher_1,
            json={
                "transfer_id": "trade_api_accept",
                "from_player_id": "p_witcher_1",
                "to_player_id": "p_witcher_2",
                "asset_type": "item",
                "asset_id": "item_herb_bundle",
            },
        )
        trade_accepted = client.post(
            "/api/trade-transfers/trade_api_accept/accept",
            headers=witcher_2,
            json={"accepted_by_player_id": "p_witcher_2"},
        )
        accepted_trade_decline = client.post(
            "/api/trade-transfers/trade_api_accept/decline",
            headers=witcher_2,
            json={"declined_by_player_id": "p_witcher_2", "reason": "too late"},
        )
        trade_decline_create = client.post(
            "/api/trade-transfers",
            headers=witcher_1,
            json={
                "transfer_id": "trade_api_decline",
                "from_player_id": "p_witcher_1",
                "to_player_id": "p_witcher_2",
                "asset_type": "item",
                "asset_id": "item_silver_dust",
            },
        )
        wrong_trade_accept = client.post(
            "/api/trade-transfers/trade_api_decline/accept",
            headers=witcher_3,
            json={"accepted_by_player_id": "p_witcher_3"},
        )
        trade_declined = client.post(
            "/api/trade-transfers/trade_api_decline/decline",
            headers=witcher_2,
            json={"declined_by_player_id": "p_witcher_2", "reason": "changed mind"},
        )
        invalid_favorite = client.post(
            "/api/favorites",
            headers=sorc_3,
            json={
                "sorceress_id": "p_sorc_3",
                "favored_player_id": "p_witcher_2",
                "slot": "tertiary",
            },
        )
        favorite = client.post(
            "/api/favorites",
            headers=sorc_4,
            json={
                "favorite_id": "fav_api_demo",
                "sorceress_id": "p_sorc_4",
                "favored_player_id": "p_witcher_3",
                "slot": "primary",
            },
        )
        wrong_favorite_accept = client.post(
            "/api/favorites/fav_api_demo/accept",
            headers=witcher_2,
            json={"accepted_by_player_id": "p_witcher_2"},
        )
        accepted = client.post(
            "/api/favorites/fav_api_demo/accept",
            headers=witcher_3,
            json={"accepted_by_player_id": "p_witcher_3"},
        )
        alignment = client.post(
            "/api/sorceresses/p_sorc_1/alignment-evidence",
            headers=sorc_1,
            json={
                "alignment_state": "double_game",
                "evidence_type": "two_sided_evidence",
                "payload": {"lords": ["p_lord_1", "p_lord_3"]},
                "final_flag": True,
            },
        )
        invalid_alignment = client.post(
            "/api/sorceresses/p_sorc_1/alignment-evidence",
            headers=sorc_1,
            json={
                "alignment_state": "triple_game",
                "evidence_type": "two_sided_evidence",
            },
        )

        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.json()["player"]["role_type"], "sorceress")
        self.assertEqual(cast.status_code, 200)
        self.assertEqual(cast.json()["status"], "accepted")
        self.assertEqual(cast.json()["mana_after"], 1)
        self.assertEqual(bad_cast.status_code, 400)
        self.assertIn(
            bad_cast.json()["detail"]["code"],
            {"insufficient_mana", "spell_target_type_mismatch"},
        )
        self.assertEqual(bought.status_code, 200)
        self.assertEqual(bought.json()["inventory"]["quantity"], 2)
        self.assertEqual(potion_transfer.status_code, 200)
        self.assertEqual(potion_transfer.json()["status"], "pending_locked")
        self.assertEqual(potion_transfer_accepted.status_code, 200)
        self.assertEqual(potion_transfer_accepted.json()["status"], "accepted")
        self.assertEqual(bad_potion_transfer.status_code, 400)
        self.assertEqual(
            bad_potion_transfer.json()["detail"]["code"],
            "insufficient_potion_inventory",
        )
        self.assertEqual(potion_use.status_code, 200)
        self.assertEqual(potion_use.json()["max_potions_per_scene"], 1)
        self.assertEqual(repeated_potion_use.status_code, 400)
        self.assertEqual(repeated_potion_use.json()["detail"]["code"], "potion_scene_cap")
        self.assertEqual(direct_witcher_buy.status_code, 400)
        self.assertEqual(direct_witcher_buy.json()["detail"]["code"], "role_not_allowed")
        self.assertEqual(trade_accept_create.status_code, 200)
        self.assertEqual(trade_accept_create.json()["status"], "pending_locked")
        self.assertEqual(trade_accepted.status_code, 200)
        self.assertEqual(trade_accepted.json()["status"], "accepted")
        self.assertEqual(accepted_trade_decline.status_code, 400)
        self.assertEqual(accepted_trade_decline.json()["detail"]["code"], "trade_already_accepted")
        self.assertEqual(trade_decline_create.status_code, 200)
        self.assertEqual(trade_decline_create.json()["status"], "pending_locked")
        self.assertEqual(wrong_trade_accept.status_code, 400)
        self.assertEqual(wrong_trade_accept.json()["detail"]["code"], "trade_consent_mismatch")
        self.assertEqual(trade_declined.status_code, 200)
        self.assertEqual(trade_declined.json()["status"], "declined")
        self.assertEqual(invalid_favorite.status_code, 400)
        self.assertEqual(invalid_favorite.json()["detail"]["code"], "invalid_favorite_slot")
        self.assertEqual(favorite.status_code, 200)
        self.assertEqual(wrong_favorite_accept.status_code, 400)
        self.assertEqual(wrong_favorite_accept.json()["detail"]["code"], "favorite_consent_mismatch")
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["status"], "accepted")
        self.assertEqual(alignment.status_code, 200)
        self.assertEqual(alignment.json()["evidence_required"], "two_sided_evidence")
        self.assertTrue(alignment.json()["final_flag"])
        self.assertEqual(invalid_alignment.status_code, 400)
        self.assertEqual(invalid_alignment.json()["detail"]["code"], "unknown_alignment_state")

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_fastapi_sorceress_trade_favorite_mutations_reject_foreign_auth_ids(self) -> None:
        settings = self.prepare_seed("sorc_api_auth_scope")
        client = TestClient(create_app(settings))
        sorc_3 = {"X-Player-Code": "SC-OWL-2RW7"}
        witcher_1 = {"X-Player-Code": "WC-WOLF-6GF4"}
        witcher_2 = {"X-Player-Code": "WC-CAT-1HN8"}

        foreign_state = client.get("/api/sorceresses/p_sorc_1/state", headers=sorc_3)
        foreign_spell = client.post(
            "/api/sorceresses/p_sorc_1/spells/cast",
            headers=sorc_3,
            json={"spell_id": "spell_boost_t1", "target_id": "p_witcher_1"},
        )
        foreign_potion_use = client.post(
            "/api/players/p_witcher_1/potions/use",
            headers=witcher_2,
            json={"potion_id": "potion_common_swallow", "scene_id": "scn_a1_001"},
        )
        foreign_trade_create = client.post(
            "/api/trade-transfers",
            headers=witcher_2,
            json={
                "from_player_id": "p_witcher_1",
                "to_player_id": "p_witcher_2",
                "asset_type": "item",
                "asset_id": "item_herb_bundle",
            },
        )
        foreign_trade_accept = client.post(
            "/api/trade-transfers/no_such_transfer/accept",
            headers=witcher_2,
            json={"accepted_by_player_id": "p_witcher_1"},
        )
        foreign_favorite_create = client.post(
            "/api/favorites",
            headers=sorc_3,
            json={
                "sorceress_id": "p_sorc_1",
                "favored_player_id": "p_witcher_2",
                "slot": "primary",
            },
        )
        foreign_favorite_accept = client.post(
            "/api/favorites/no_such_favorite/accept",
            headers=witcher_1,
            json={"accepted_by_player_id": "p_witcher_2"},
        )
        target_auto_accept = client.post(
            "/api/trade-transfers",
            headers=witcher_2,
            json={
                "from_player_id": "p_witcher_1",
                "to_player_id": "p_witcher_2",
                "asset_type": "item",
                "asset_id": "item_herb_bundle",
                "auto_accept": True,
            },
        )
        source_auto_accept = client.post(
            "/api/trade-transfers",
            headers=witcher_1,
            json={
                "from_player_id": "p_witcher_1",
                "to_player_id": "p_witcher_2",
                "asset_type": "item",
                "asset_id": "item_herb_bundle",
                "auto_accept": True,
            },
        )

        for response in (
            foreign_state,
            foreign_spell,
            foreign_potion_use,
            foreign_trade_create,
            foreign_trade_accept,
            foreign_favorite_create,
            foreign_favorite_accept,
            target_auto_accept,
            source_auto_accept,
        ):
            self.assertEqual(response.status_code, 403, response.text)

    def prepare_seed(self, name: str) -> Settings:
        settings = Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")
        return settings


if __name__ == "__main__":
    unittest.main()
