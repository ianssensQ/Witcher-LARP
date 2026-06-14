from __future__ import annotations

import unittest
from uuid import uuid4

from backend.witcher_larp.card_market_service import CardMarketError, buy_card, card_market_rows
from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.snapshot_exporter import build_snapshot_from_database

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"


class CardMarketServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def make_settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def import_seed(self, name: str) -> Settings:
        settings = self.make_settings(name)
        report = import_seed_pack(settings, snapshot_dir=None)
        self.assertEqual(report.status, "success", report.errors)
        return settings

    def test_card_market_offers_all_non_hero_cards(self) -> None:
        settings = self.import_seed("card_market_catalog")
        with connect(settings) as connection:
            offers = card_market_rows(connection, player_id="p_witcher_1")
            expected_regular_ids = self.regular_gwent_card_ids(connection)

        offered_ids = {offer["card_id"] for offer in offers}
        self.assertEqual(offered_ids, expected_regular_ids)
        self.assertIn("gwent_horn", offered_ids)
        self.assertIn("gwent_weather_frost", offered_ids)
        self.assertNotIn("rare_gwent_01", offered_ids)
        self.assertNotIn("rare_gwent_02", offered_ids)
        self.assertNotIn("gwent_leader_foltest_king", offered_ids)
        self.assertTrue(any(offer["status"] == "available" for offer in offers))

    def test_card_market_prices_make_stronger_cards_more_expensive(self) -> None:
        settings = self.import_seed("card_market_prices")
        with connect(settings) as connection:
            offers = [
                offer
                for offer in card_market_rows(connection)
                if offer["type"] == "unit" and offer["rarity"].lower() == "common"
            ]

        weakest = min(offers, key=lambda offer: offer["strength"])
        strongest = max(offers, key=lambda offer: offer["strength"])
        strength_delta = strongest["strength"] - weakest["strength"]
        self.assertGreater(strongest["unit_cost"], weakest["unit_cost"])
        self.assertGreaterEqual(strongest["unit_cost"] - weakest["unit_cost"], strength_delta * 2)

    def test_buy_card_debits_gold_grants_card_and_retries_without_double_charge(self) -> None:
        settings = self.import_seed("card_market_buy")
        with connect(settings) as connection:
            offer = next(
                offer
                for offer in card_market_rows(connection, player_id="p_witcher_1")
                if offer["status"] == "available" and int(offer["unit_cost"]) <= 20
            )
            before = connection.execute(
                "SELECT gold FROM player_runtime_state WHERE player_id = 'p_witcher_1'"
            ).fetchone()
            purchase = buy_card(
                connection,
                player_id="p_witcher_1",
                card_id=str(offer["card_id"]),
                purchase_id="test_card_purchase",
                source="test",
            )
            duplicate = buy_card(
                connection,
                player_id="p_witcher_1",
                card_id=str(offer["card_id"]),
                purchase_id="test_card_purchase",
                source="test",
            )
            after = connection.execute(
                "SELECT gold FROM player_runtime_state WHERE player_id = 'p_witcher_1'"
            ).fetchone()
            ownership = connection.execute(
                """
                SELECT quantity
                FROM asset_ownership
                WHERE owner_player_id = 'p_witcher_1'
                  AND asset_type = 'card'
                  AND asset_id = ?
                  AND status = 'active'
                """,
                (offer["card_id"],),
            ).fetchone()

        self.assertFalse(purchase["duplicate"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(after["gold"], before["gold"] - purchase["unit_cost"])
        self.assertEqual(ownership["quantity"], 1)

    def test_buy_card_rejects_card_already_in_player_deck_without_charging(self) -> None:
        settings = self.import_seed("card_market_buy_existing")
        with connect(settings) as connection:
            card_market_rows(connection, player_id="p_witcher_1")
            starter_deck = connection.execute(
                """
                SELECT card_ids
                FROM gwent_decks
                WHERE player_id = 'p_witcher_1'
                LIMIT 1
                """
            ).fetchone()
            owned_card_id = str(starter_deck["card_ids"]).split(";")[0]
            before = connection.execute(
                "SELECT gold FROM player_runtime_state WHERE player_id = 'p_witcher_1'"
            ).fetchone()
            with self.assertRaises(CardMarketError) as raised:
                buy_card(
                    connection,
                    player_id="p_witcher_1",
                    card_id=owned_card_id,
                    purchase_id="test_existing_card_purchase",
                    source="test",
                )
            after = connection.execute(
                "SELECT gold FROM player_runtime_state WHERE player_id = 'p_witcher_1'"
            ).fetchone()

        self.assertEqual(raised.exception.code, "card_already_owned")
        self.assertEqual(after["gold"], before["gold"])

    def test_player_snapshot_after_card_purchase_exposes_owned_card(self) -> None:
        settings = self.import_seed("card_market_snapshot_purchase")
        with connect(settings) as connection:
            offer = next(
                offer
                for offer in card_market_rows(connection, player_id="p_witcher_1")
                if offer["status"] == "available" and int(offer["unit_cost"]) <= 20
            )
            purchase = buy_card(
                connection,
                player_id="p_witcher_1",
                card_id=str(offer["card_id"]),
                purchase_id="test_snapshot_card_purchase",
                source="test",
            )
            snapshot = build_snapshot_from_database(connection, player_code="WC-WOLF-6GF4")

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        owned_cards = {
            row["asset_id"]
            for row in snapshot["asset_ownership"]
            if row["asset_type"] == "card" and row["status"] == "active"
        }
        market_status_by_card = {row["card_id"]: row["status"] for row in snapshot["card_market"]}
        self.assertIn(purchase["card_id"], owned_cards)
        self.assertEqual(market_status_by_card[purchase["card_id"]], "owned")

    def test_player_snapshot_includes_potion_and_card_market_rows(self) -> None:
        settings = self.import_seed("card_market_snapshot")
        with connect(settings) as connection:
            snapshot = build_snapshot_from_database(connection, player_code="WC-WOLF-6GF4")

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertTrue(snapshot["potion_market"])
        self.assertTrue(snapshot["card_market"])

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_player_can_buy_market_card_through_api(self) -> None:
        settings = self.import_seed("card_market_api")
        with connect(settings) as connection:
            offer = next(
                offer
                for offer in card_market_rows(connection, player_id="p_witcher_1")
                if offer["status"] == "available" and int(offer["unit_cost"]) <= 20
            )

        client = TestClient(create_app(settings))
        response = client.post(
            "/api/players/p_witcher_1/card-market/buy",
            headers={"X-Player-Code": "WC-WOLF-6GF4"},
            json={
                "card_id": offer["card_id"],
                "purchase_id": "test_api_card_purchase",
                "source": "test",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["card_id"], offer["card_id"])
        self.assertEqual(payload["gold_after"], payload["gold_before"] - payload["unit_cost"])

    def regular_gwent_card_ids(self, connection) -> set[str]:
        rows = connection.execute(
            """
            SELECT card_id, row, type, rarity, effect, ability_tags
            FROM gwent_cards
            """
        ).fetchall()
        return {
            str(row["card_id"])
            for row in rows
            if self.is_regular_gwent_card(row)
        }

    def is_regular_gwent_card(self, row) -> bool:
        type_value = str(row["type"]).strip().lower()
        row_value = str(row["row"]).strip().lower()
        rarity = str(row["rarity"]).strip().lower()
        effect = str(row["effect"]).strip().lower()
        ability_tags = {
            tag.strip().lower()
            for tag in str(row["ability_tags"]).replace(";", ",").split(",")
            if tag.strip()
        }
        return (
            type_value in {"unit", "special"}
            and row_value != "leader"
            and rarity not in {"leader", "hero", "legendary"}
            and effect != "hero"
            and "hero" not in ability_tags
        )


if __name__ == "__main__":
    unittest.main()
