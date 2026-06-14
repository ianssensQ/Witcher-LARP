from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import random
from types import SimpleNamespace
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.app import create_app
from backend.witcher_larp.asset_service import grant_asset_ownership
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.pvp_service import ChallengeCreateInput, ChallengeStartInput, GwentActionInput, GwentBotMatchInput, GwentDeckSaveInput, GwentPreparationInput, PvpError
from backend.witcher_larp.pvp_service import convert_personal_card_to_lord
from backend.witcher_larp.pvp_service import create_pvp_challenge, finish_gwent_match
from backend.witcher_larp.pvp_service import get_player_pvp_state, prepare_gwent_challenge, record_gwent_action, record_gwent_round, record_pvp_refusal, save_gwent_runtime_deck, start_gwent_bot_match
from backend.witcher_larp.pvp_service import set_pvp_throttle_mode, start_pvp_challenge
from backend.witcher_larp.reward_service import create_pending_reward_approval
from scripts.ios_gwent_http_smoke import Player as SmokePlayer
from scripts.ios_gwent_http_smoke import SmokeError, run_bot_smoke, run_preflight, run_smoke

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
    "deck_contract_copy_limit",
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
NORTHERN_TEST_UNITS = (
    "gwent_unit_13",
    "gwent_unit_03",
    "nr_blue_stripes_commando_2",
    "nr_blue_stripes_commando_3",
    "gwent_unit_16",
    "nr_catapult_2",
    "gwent_unit_12",
    "nr_crinfrid_reavers_dragon_hunter_2",
    "nr_crinfrid_reavers_dragon_hunter_3",
    "gwent_unit_10",
    "gwent_unit_09",
    "nr_esterad_thyssen",
    "nr_john_natalis",
    "gwent_unit_05",
    "nr_kaedweni_siege_expert_2",
    "nr_kaedweni_siege_expert_3",
    "gwent_unit_07",
    "nr_philippa_eilhart",
    "nr_poor_fucking_infantry_1",
    "nr_poor_fucking_infantry_2",
    "nr_poor_fucking_infantry_3",
    "gwent_unit_06",
    "gwent_unit_01",
    "gwent_unit_08",
    "nr_sheldon_skaggs",
    "gwent_unit_11",
    "gwent_unit_02",
    "nr_sigismund_dijkstra",
    "nr_sile_de_tansarville",
    "nr_thaler",
    "gwent_unit_14",
    "nr_trebuchet_2",
    "nr_vernon_roche",
    "nr_ves",
    "nr_yarpen_zigrin",
)
SCOIATAEL_TEST_UNITS = (
    "gwent_unit_17",
    "sc_ciaran",
    "sc_dennis_cranmer",
    "sc_dol_blathanna_archer",
    "sc_dol_blathanna_scout_1",
    "sc_dol_blathanna_scout_2",
    "sc_dol_blathanna_scout_3",
    "gwent_unit_18",
    "sc_dwarven_skirmisher_2",
    "sc_dwarven_skirmisher_3",
    "sc_eithne",
    "sc_elven_skirmisher_1",
    "sc_elven_skirmisher_2",
    "sc_elven_skirmisher_3",
    "sc_filavandrel",
    "sc_havekar_healer_1",
    "sc_havekar_healer_2",
    "sc_havekar_healer_3",
    "sc_havekar_smuggler_1",
    "sc_havekar_smuggler_2",
    "sc_havekar_smuggler_3",
    "sc_ida_emean",
)
MONSTERS_TEST_UNITS = (
    "mo_arachas_1",
    "mo_arachas_2",
    "mo_arachas_3",
    "mo_arachas_behemoth",
    "mo_botchling",
    "mo_celaeno_harpy",
    "mo_cockatrice",
    "mo_crone_brewess",
    "mo_crone_weavess",
    "mo_crone_whispess",
    "mo_draug",
    "mo_earth_elemental",
    "mo_endrega",
    "mo_fiend",
    "mo_fire_elemental",
    "mo_foglet",
    "mo_forktail",
    "mo_frightener",
    "mo_gargoyle",
    "mo_ghoul_1",
    "mo_ghoul_2",
    "mo_ghoul_3",
    "mo_nekker_3",
    "gwent_unit_19",
    "gwent_unit_20",
)


class TestClientSmokeApi:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.base_url = "testserver"

    def get(self, path: str, *, player_code: str | None = None) -> dict:
        response = self.client.get(path, headers=self._headers(player_code))
        return self._json_response("GET", path, response)

    def post(self, path: str, body: dict, *, player_code: str | None = None) -> dict:
        response = self.client.post(path, headers=self._headers(player_code), json=body)
        return self._json_response("POST", path, response)

    def _headers(self, player_code: str | None) -> dict[str, str]:
        return {"X-Player-Code": player_code} if player_code else {}

    def _json_response(self, method: str, path: str, response) -> dict:
        if response.status_code >= 400:
            raise SmokeError(f"{method} {path} failed with HTTP {response.status_code}: {response.text}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise SmokeError(f"{method} {path} returned non-object JSON: {payload!r}")
        return payload


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
            self.install_legacy_pvp_test_decks(connection)
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

    def install_legacy_pvp_test_decks(self, connection) -> None:
        nilfgaard_starter = connection.execute(
            """
            SELECT card_ids
            FROM gwent_decks
            WHERE player_id = 'p_witcher_3'
            LIMIT 1
            """
        ).fetchone()
        self.assertIsNotNone(nilfgaard_starter)
        decks = (
            (
                "deck_witcher_wolf",
                "p_witcher_1",
                "gwent_leader_wolf",
                NORTHERN_TEST_UNITS,
            ),
            (
                "deck_witcher_wolf_scoiatael",
                "p_witcher_1",
                "gwent_leader_scoiatael",
                SCOIATAEL_TEST_UNITS,
            ),
            (
                "deck_witcher_wolf_nilfgaard",
                "p_witcher_1",
                "gwent_leader_nilfgaard",
                tuple(str(nilfgaard_starter["card_ids"]).split(";")),
            ),
            (
                "deck_witcher_wolf_monsters",
                "p_witcher_1",
                "gwent_leader_monsters",
                MONSTERS_TEST_UNITS,
            ),
            (
                "deck_witcher_cat",
                "p_witcher_2",
                "gwent_leader_wolf",
                NORTHERN_TEST_UNITS,
            ),
            (
                "deck_p_witcher_2_scoiatael",
                "p_witcher_2",
                "gwent_leader_scoiatael",
                SCOIATAEL_TEST_UNITS,
            ),
        )
        import_run_id = connection.execute(
            "SELECT _import_run_id FROM gwent_decks LIMIT 1"
        ).fetchone()["_import_run_id"]
        for index, (deck_id, player_id, leader_card_id, card_ids) in enumerate(decks, start=1):
            card_ids_value = ";".join(card_ids)
            updated = connection.execute(
                """
                UPDATE gwent_decks
                SET player_id = ?,
                    leader_card_id = ?,
                    card_ids = ?
                WHERE deck_id = ?
                """,
                (player_id, leader_card_id, card_ids_value, deck_id),
            )
            if updated.rowcount:
                continue
            connection.execute(
                """
                INSERT INTO gwent_decks (
                    _import_run_id, _row_number, deck_id, player_id,
                    leader_card_id, card_ids
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    import_run_id,
                    800 + index,
                    deck_id,
                    player_id,
                    leader_card_id,
                    card_ids_value,
                ),
            )

    def potion_quantity(self, connection, player_id: str, potion_id: str) -> int:
        row = connection.execute(
            """
            SELECT quantity
            FROM potion_inventory
            WHERE player_id = ? AND potion_id = ?
            """,
            (player_id, potion_id),
        ).fetchone()
        return int(row["quantity"]) if row is not None else 0

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
                    -100 + index,
                    f"deck_{player_id}",
                    player_id,
                    source["leader_card_id"],
                    source["card_ids"],
                ),
            )

    def opening_hand_for(
        self,
        connection,
        *,
        challenge_id: str,
        player_id: str,
        deck_id: str | None = None,
    ) -> list[str]:
        if deck_id:
            deck = connection.execute(
                """
                SELECT deck_id, card_ids
                FROM gwent_decks
                WHERE player_id = ? AND deck_id = ?
                LIMIT 1
                """,
                (player_id, deck_id),
            ).fetchone()
        else:
            deck = connection.execute(
                """
                SELECT deck_id, card_ids
                FROM gwent_decks
                WHERE player_id = ?
                ORDER BY _row_number
                LIMIT 1
                """,
                (player_id,),
            ).fetchone()
        self.assertIsNotNone(deck)
        card_ids = [card_id for card_id in str(deck["card_ids"]).split(";") if card_id]
        shuffled = list(card_ids)
        random.Random(f"{challenge_id}:{player_id}:{deck['deck_id']}:witcher3-gwent-v2").shuffle(shuffled)
        return shuffled[:10]

    def make_player_scoiatael_start(self, connection, player_id: str = "p_witcher_1") -> None:
        default_deck = connection.execute(
            """
            SELECT deck_id
            FROM gwent_decks
            WHERE player_id = ?
            ORDER BY _row_number
            LIMIT 1
            """,
            (player_id,),
        ).fetchone()
        self.assertIsNotNone(default_deck)
        connection.execute(
            """
            UPDATE gwent_decks
            SET leader_card_id = 'gwent_leader_scoiatael',
                card_ids = ?
            WHERE deck_id = ?
            """,
            (";".join(SCOIATAEL_TEST_UNITS), default_deck["deck_id"]),
        )

    def strongest_legal_unit_action(self, connection, player_state: dict) -> dict:
        best_action = None
        best_strength = -1
        for action in player_state["legal_actions"]["playable_cards"]:
            if action.get("type") != "unit" or action.get("effect") == "spy":
                continue
            if not action.get("allowed_rows"):
                continue
            card = connection.execute(
                "SELECT strength FROM gwent_cards WHERE card_id = ?",
                (action["card_id"],),
            ).fetchone()
            strength = int(card["strength"] or 0) if card is not None else 0
            if strength > best_strength:
                best_action = action
                best_strength = strength
        self.assertIsNotNone(best_action)
        return best_action

    def replace_active_round_deck_state(self, connection, match_id: str, deck_state: dict) -> None:
        base_deck_state = {
            key: value
            for key, value in deck_state.items()
            if key != "active_round"
        }
        deck_state["active_round"]["base_deck_state"] = json.loads(json.dumps(base_deck_state))
        connection.execute(
            """
            UPDATE gwent_runtime_matches
            SET deck_state_json = ?
            WHERE match_id = ?
            """,
            (json.dumps(deck_state, ensure_ascii=False, sort_keys=True), match_id),
        )

    def force_cards_into_match_hands(
        self,
        connection,
        match_id: str,
        cards_by_player: dict[str, list[str]],
    ) -> None:
        match = connection.execute(
            """
            SELECT deck_state_json
            FROM gwent_runtime_matches
            WHERE match_id = ?
            """,
            (match_id,),
        ).fetchone()
        self.assertIsNotNone(match)
        deck_state = json.loads(match["deck_state_json"])
        for player_id, card_ids in cards_by_player.items():
            player_state = deck_state[player_id]
            hand = list(player_state.get("hand") or [])
            draw_pile = list(player_state.get("draw_pile") or [])
            for card_id in card_ids:
                if card_id not in hand:
                    hand.insert(0, card_id)
                if card_id in draw_pile:
                    draw_pile.remove(card_id)
            player_state["hand"] = hand
            player_state["draw_pile"] = draw_pile
        self.replace_active_round_deck_state(connection, match_id, deck_state)

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

    def test_player_pvp_state_service_tracks_active_match_and_pending_submission(self) -> None:
        settings = self.prepare_seed(
            "pvp_player_state_service",
            extra_deck_players=("p_witcher_2", "p_witcher_3"),
        )
        with connect(settings) as connection:
            self.make_player_scoiatael_start(connection)
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    challenge_id="challenge_player_state_service",
                    stake={"asset_type": "item", "asset_id": "stake_banner"},
                ),
            )
            pre_start = get_player_pvp_state(connection, "p_witcher_1")
            self.assertEqual(pre_start["active_challenge"]["challenge_id"], challenge["challenge_id"])
            self.assertIsNone(pre_start["active_match"])
            self.assertTrue(pre_start["legal_actions"]["can_start"])

            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    preferred_starting_player_id="p_witcher_1",
                ),
            )
            match_id = started["match"]["match_id"]
            player_state = get_player_pvp_state(connection, "p_witcher_1")
            self.assertEqual(player_state["active_match"]["match_id"], match_id)
            self.assertEqual(player_state["opponent_id"], "p_witcher_2")
            self.assertEqual(len(player_state["player_hand"]), 10)
            self.assertEqual(player_state["current_round"]["status"], "ready_for_submission")
            self.assertTrue(player_state["legal_actions"]["can_play_card"])
            self.assertEqual(player_state["table"]["zone_name"], "main_house_table")

            first_action = next(
                action
                for action in player_state["legal_actions"]["playable_cards"]
                if action.get("type") == "unit" and action.get("allowed_rows")
            )
            record_gwent_round(
                connection,
                match_id,
                {"plays": [{"player_id": "p_witcher_1", "card_id": first_action["card_id"]}]},
                round_number=player_state["legal_actions"]["round_number"],
                actor_id="p_witcher_1",
            )

            pending_state = get_player_pvp_state(connection, "p_witcher_1")
            self.assertEqual(pending_state["current_round"]["status"], "pending_player_submissions")
            self.assertTrue(pending_state["current_round"]["player_submitted"])
            self.assertFalse(pending_state["legal_actions"]["can_play_card"])

            target_state = get_player_pvp_state(connection, "p_witcher_2")
            self.assertFalse(target_state["current_round"]["player_submitted"])
            self.assertTrue(target_state["legal_actions"]["can_play_card"])

            unrelated_state = get_player_pvp_state(connection, "p_witcher_3")
            self.assertIsNone(unrelated_state["active_match"])
            self.assertIsNone(unrelated_state["active_challenge"])
            opponent_ids = {row["player_id"] for row in unrelated_state["opponents"]}
            self.assertIn("p_witcher_1", opponent_ids)
            self.assertIn("p_witcher_2", opponent_ids)
            self.assertIn("p_sorc_1", opponent_ids)
            self.assertNotIn("p_witcher_3", opponent_ids)
            self.assertNotIn("p_lord_1", opponent_ids)

    def test_gwent_preparation_requires_both_players_ready_before_starting_match(self) -> None:
        settings = self.prepare_seed("pvp_gwent_preparation", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            connection.execute(
                """
                INSERT INTO gwent_decks (
                    _import_run_id, _row_number, deck_id, player_id,
                    leader_card_id, card_ids
                )
                SELECT
                    _import_run_id,
                    777,
                    'deck_witcher_1_alt',
                    player_id,
                    leader_card_id,
                    card_ids
                FROM gwent_decks
                WHERE player_id = 'p_witcher_1'
                LIMIT 1
                """
            )
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    challenge_id="challenge_gwent_preparation",
                    stake={"asset_type": "gold", "asset_id": "gold", "amount": 5},
                ),
            )
            p1_mulligan = self.opening_hand_for(
                connection,
                challenge_id=challenge["challenge_id"],
                player_id="p_witcher_1",
                deck_id="deck_witcher_1_alt",
            )[0]
            p2_mulligan = self.opening_hand_for(
                connection,
                challenge_id=challenge["challenge_id"],
                player_id="p_witcher_2",
            )[0]
            first_ready = prepare_gwent_challenge(
                connection,
                GwentPreparationInput(
                    challenge_id=challenge["challenge_id"],
                    player_id="p_witcher_1",
                    mulligans=[p1_mulligan],
                    deck_id="deck_witcher_1_alt",
                ),
            )
            duplicate_ready = prepare_gwent_challenge(
                connection,
                GwentPreparationInput(
                    challenge_id=challenge["challenge_id"],
                    player_id="p_witcher_1",
                ),
            )
            p1_state = get_player_pvp_state(connection, "p_witcher_1")
            second_ready = prepare_gwent_challenge(
                connection,
                GwentPreparationInput(
                    challenge_id=challenge["challenge_id"],
                    player_id="p_witcher_2",
                    mulligans=[p2_mulligan],
                ),
            )
            match_id = second_ready["match"]["match_id"]
            p2_state = get_player_pvp_state(connection, "p_witcher_2")

        self.assertIsNone(first_ready["match"])
        self.assertFalse(first_ready["started"])
        self.assertEqual(first_ready["prep"]["ready_players"], ["p_witcher_1"])
        self.assertEqual(first_ready["prep"]["missing_players"], ["p_witcher_2"])
        self.assertEqual(first_ready["prep"]["deck_ids_by_player"]["p_witcher_1"], "deck_witcher_1_alt")
        self.assertTrue(duplicate_ready["duplicate"])
        self.assertEqual(duplicate_ready["prep"]["mulligans_by_player"]["p_witcher_1"], [p1_mulligan])
        self.assertEqual(duplicate_ready["prep"]["deck_ids_by_player"]["p_witcher_1"], "deck_witcher_1_alt")
        self.assertIsNone(p1_state["active_match"])
        self.assertEqual(p1_state["active_challenge"]["prep"]["ready_players"], ["p_witcher_1"])
        self.assertTrue(second_ready["started"])
        self.assertEqual(second_ready["challenge"]["status"], "started")
        self.assertEqual(second_ready["match"]["deck_state"]["p_witcher_1"]["deck_id"], "deck_witcher_1_alt")
        self.assertEqual(second_ready["match"]["deck_state"]["p_witcher_1"]["mulligans"], [p1_mulligan])
        self.assertEqual(second_ready["match"]["deck_state"]["p_witcher_2"]["mulligans"], [p2_mulligan])
        self.assertEqual(p2_state["active_match"]["match_id"], match_id)
        self.assertEqual(p2_state["active_challenge"]["prep"]["ready_players"], ["p_witcher_1", "p_witcher_2"])

    def test_gwent_action_flow_tracks_turns_board_pass_and_round_resolution(self) -> None:
        settings = self.prepare_seed("pvp_action_flow", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            self.make_player_scoiatael_start(connection)
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    challenge_id="challenge_action_flow",
                    stake={"asset_type": "item", "asset_id": "stake_banner"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    preferred_starting_player_id="p_witcher_1",
                ),
            )
            match_id = started["match"]["match_id"]

            opening_state = get_player_pvp_state(connection, "p_witcher_1")
            self.assertEqual(opening_state["current_round"]["phase"], "active_turn")
            self.assertEqual(opening_state["legal_actions"]["turn_player_id"], "p_witcher_1")
            self.assertTrue(opening_state["legal_actions"]["can_play_card"])

            first_action = self.strongest_legal_unit_action(connection, opening_state)
            played = record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id="p_witcher_1",
                    action="play_card",
                    card_id=first_action["card_id"],
                    row=first_action["allowed_rows"][0],
                    action_id="p1-action-1",
                ),
            )
            self.assertFalse(played["duplicate"])
            self.assertEqual(played["current_round"]["turn_player_id"], "p_witcher_2")
            self.assertNotIn(first_action["card_id"], played["current_round"]["player_hand"])
            self.assertIn(
                first_action["card_id"],
                [
                    unit["card_id"]
                    for unit in played["current_round"]["board"]["p_witcher_1"][first_action["allowed_rows"][0]]
                ],
            )

            duplicate = record_gwent_action(
                connection,
                GwentActionInput(
                        match_id=match_id,
                        player_id="p_witcher_1",
                        action="play_card",
                        card_id=first_action["card_id"],
                        row=first_action["allowed_rows"][0],
                        action_id="p1-action-1",
                    ),
                )
            self.assertTrue(duplicate["duplicate"])

            with self.assertRaisesRegex(PvpError, "out of turn"):
                record_gwent_action(
                    connection,
                    GwentActionInput(
                        match_id=match_id,
                        player_id="p_witcher_1",
                        action="pass",
                    ),
                )

            p2_pass = record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id="p_witcher_2",
                    action="pass",
                    action_id="p2-pass-1",
                ),
            )
            self.assertEqual(p2_pass["current_round"]["turn_player_id"], "p_witcher_1")
            self.assertFalse(p2_pass["current_round"]["passed"]["p_witcher_1"])
            self.assertTrue(p2_pass["current_round"]["passed"]["p_witcher_2"])

            resolved = record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id="p_witcher_1",
                    action="pass",
                    action_id="p1-pass-1",
                ),
            )
            self.assertEqual(resolved["round"]["winner_id"], "p_witcher_1")
            self.assertEqual(resolved["match"]["round_losses"]["p_witcher_2"], 1)

            next_state = get_player_pvp_state(connection, "p_witcher_1")
            self.assertEqual(next_state["current_round"]["round_number"], 2)
            self.assertEqual(next_state["current_round"]["phase"], "active_turn")

    def test_gwent_action_decoy_replaces_unit_and_returns_target_live(self) -> None:
        settings = self.prepare_seed("pvp_live_decoy", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            self.make_player_scoiatael_start(connection)
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    challenge_id="challenge_live_decoy",
                    stake={"asset_type": "item", "asset_id": "stake_banner"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    preferred_starting_player_id="p_witcher_1",
                ),
            )
            match_id = started["match"]["match_id"]
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {"p_witcher_1": ["gwent_unit_01", "gwent_decoy"]},
            )

            first_play = record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id="p_witcher_1",
                    action="play_card",
                    round_number=1,
                    card_id="gwent_unit_01",
                    row="melee",
                    action_id="p1-live-decoy-unit",
                ),
            )
            self.assertNotIn("gwent_unit_01", first_play["current_round"]["player_hand"])

            record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id="p_witcher_2",
                    action="pass",
                    round_number=1,
                    action_id="p2-live-decoy-pass",
                ),
            )

            decoy_play = record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id="p_witcher_1",
                    action="play_card",
                    round_number=1,
                    card_id="gwent_decoy",
                    target_card_id="gwent_unit_01",
                    action_id="p1-live-decoy-play",
                ),
            )

        current_round = decoy_play["current_round"]
        self.assertIn("gwent_unit_01", current_round["player_hand"])
        self.assertNotIn("gwent_decoy", current_round["player_hand"])
        own_melee = current_round["board"]["p_witcher_1"]["melee"]
        active_card_ids = [unit["card_id"] for unit in own_melee if not unit["removed"]]
        self.assertNotIn("gwent_unit_01", active_card_ids)
        self.assertIn("gwent_decoy", active_card_ids)
        returned_unit = next(unit for unit in own_melee if unit["card_id"] == "gwent_unit_01")
        decoy_unit = next(unit for unit in own_melee if unit["card_id"] == "gwent_decoy")
        self.assertTrue(returned_unit["returned_by_decoy"])
        self.assertTrue(decoy_unit["decoy_placeholder"])
        self.assertEqual(decoy_unit["replaced_card_id"], "gwent_unit_01")
        self.assertEqual(decoy_unit["row"], "melee")

    def test_gwent_action_flow_auto_passes_empty_hands_and_resolves_round(self) -> None:
        settings = self.prepare_seed("pvp_action_empty_hands", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    challenge_id="challenge_action_empty_hands",
                    stake={"asset_type": "item", "asset_id": "stake_banner"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    deck_ids_by_player={"p_witcher_1": "deck_witcher_wolf_scoiatael"},
                    preferred_starting_player_id="p_witcher_1",
                ),
            )
            match_id = started["match"]["match_id"]
            deck_state = started["match"]["deck_state"]
            deck_state["p_witcher_1"]["hand"] = ["gwent_unit_17"]
            deck_state["p_witcher_1"]["draw_pile"] = []
            deck_state["p_witcher_2"]["hand"] = ["gwent_unit_02"]
            deck_state["p_witcher_2"]["draw_pile"] = []
            self.replace_active_round_deck_state(connection, match_id, deck_state)

            first = record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id="p_witcher_1",
                    action="play_card",
                    card_id="gwent_unit_17",
                    row="melee",
                    action_id="p1-empty-hand-card",
                ),
            )
            self.assertTrue(first["current_round"]["passed"]["p_witcher_1"])
            self.assertEqual(first["current_round"]["turn_player_id"], "p_witcher_2")

            resolved = record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id="p_witcher_2",
                    action="play_card",
                    card_id="gwent_unit_02",
                    row="melee",
                    action_id="p2-empty-hand-card",
                ),
            )

        self.assertEqual(resolved["round"]["round_number"], 1)
        self.assertEqual(resolved["round"]["passed"], {"p_witcher_1": True, "p_witcher_2": True})
        self.assertEqual(resolved["match"]["status"], "active")
        self.assertEqual(resolved["current_round"]["round_number"], 2)

    def test_gwent_start_records_server_shuffle_coin_toss_and_audit(self) -> None:
        settings = self.prepare_seed("pvp_shuffle_coin_toss", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    challenge_id="challenge_shuffle_coin_toss",
                    stake={"asset_type": "item", "asset_id": "stake_banner"},
                ),
            )
            started = start_pvp_challenge(connection, ChallengeStartInput(challenge_id=challenge["challenge_id"]))
            deck_state = started["match"]["deck_state"]
            event = connection.execute(
                """
                SELECT payload_json
                FROM event_log
                WHERE event_type = 'gwent_match_started'
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        first_turn = deck_state["faction_effects"][0]
        self.assertEqual(first_turn["effect"], "coin_toss_first_turn")
        self.assertEqual(deck_state["active_round"]["starting_player_id"], first_turn["starting_player_id"])
        for player_id in ("p_witcher_1", "p_witcher_2"):
            player_state = deck_state[player_id]
            shuffle_log = player_state["shuffle_log"]
            self.assertEqual(player_state["hand"], shuffle_log["opening_hand"])
            self.assertEqual(sorted(shuffle_log["original_card_ids"]), sorted(shuffle_log["shuffled_card_ids"]))
            self.assertNotEqual(shuffle_log["original_card_ids"], shuffle_log["shuffled_card_ids"])
        self.assertIsNotNone(event)
        payload = json.loads(event["payload_json"])
        self.assertEqual(payload["starting_player_id"], deck_state["active_round"]["starting_player_id"])
        self.assertEqual(
            payload["shuffle_audit"]["p_witcher_1"]["shuffle_seed"],
            deck_state["p_witcher_1"]["shuffle_seed"],
        )

    def test_gwent_runtime_deckbuilder_deck_can_start_match(self) -> None:
        settings = self.prepare_seed("pvp_runtime_deckbuilder", extra_deck_players=("p_witcher_2",))
        runtime_card_ids = list(SCOIATAEL_TEST_UNITS)
        with connect(settings) as connection:
            saved = save_gwent_runtime_deck(
                connection,
                GwentDeckSaveInput(
                    player_id="p_witcher_1",
                    deck_id="runtime_deck_wolf_scoia_test",
                    leader_card_id="gwent_leader_scoiatael",
                    card_ids=runtime_card_ids,
                    source="test_deckbuilder",
                ),
            )
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    challenge_id="challenge_runtime_deckbuilder",
                    stake={"asset_type": "item", "asset_id": "stake_banner"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    deck_ids_by_player={"p_witcher_1": saved["deck"]["deck_id"]},
                    preferred_starting_player_id="p_witcher_1",
                ),
            )

        p1_state = started["match"]["deck_state"]["p_witcher_1"]
        self.assertEqual(saved["deck"]["card_ids"], runtime_card_ids)
        self.assertEqual(p1_state["deck_id"], "runtime_deck_wolf_scoia_test")
        self.assertEqual(p1_state["leader_card_id"], "gwent_leader_scoiatael")
        self.assertEqual(p1_state["faction"], "scoiatael")
        self.assertEqual(started["match"]["deck_state"]["active_round"]["starting_player_id"], "p_witcher_1")

    def test_gwent_action_flow_places_spy_on_opponent_side_and_draws_cards(self) -> None:
        settings = self.prepare_seed("pvp_action_spy", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    challenge_id="challenge_action_spy",
                    stake={"asset_type": "item", "asset_id": "stake_banner"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    deck_ids_by_player={"p_witcher_1": "deck_witcher_wolf_scoiatael"},
                    preferred_starting_player_id="p_witcher_1",
                ),
            )
            match_id = started["match"]["match_id"]
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {"p_witcher_1": ["rare_gwent_04"]},
            )
            opening_state = get_player_pvp_state(connection, "p_witcher_1")
            spy_action = next(
                action
                for action in opening_state["legal_actions"]["playable_cards"]
                if "spy" in action["effects"]
            )

            played = record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id="p_witcher_1",
                    action="play_card",
                    card_id=spy_action["card_id"],
                    row=spy_action["allowed_rows"][0],
                    action_id="p1-spy-action",
                ),
            )

        spy_row = spy_action["allowed_rows"][0]
        opponent_row = played["current_round"]["board"]["p_witcher_2"][spy_row]
        spy_effect = next(item for item in played["current_round"]["effects_applied"] if item["effect"] == "spy")
        self.assertIn(spy_action["card_id"], [unit["card_id"] for unit in opponent_row])
        self.assertEqual(spy_effect["placed_for_player_id"], "p_witcher_2")
        self.assertEqual(len(spy_effect["drawn_card_ids"]), 2)
        self.assertEqual(len(played["current_round"]["player_hand"]), len(opening_state["player_hand"]) + 1)

    def test_gwent_action_e2e_finishes_applies_stake_and_stays_visible_to_players(self) -> None:
        settings = self.prepare_seed("pvp_action_e2e_finish", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            self.make_player_scoiatael_start(connection)
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    challenge_id="challenge_action_e2e_finish",
                    stake={"asset_type": "gold", "asset_id": "gold", "amount": 5},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    preferred_starting_player_id="p_witcher_1",
                ),
            )
            match_id = started["match"]["match_id"]

            def win_round(round_number: int) -> dict:
                p1_state = get_player_pvp_state(connection, "p_witcher_1")
                self.assertEqual(p1_state["active_match"]["match_id"], match_id)
                self.assertEqual(p1_state["legal_actions"]["turn_player_id"], "p_witcher_1")
                self.assertTrue(p1_state["legal_actions"]["is_player_turn"])
                action = self.strongest_legal_unit_action(connection, p1_state)
                record_gwent_action(
                    connection,
                    GwentActionInput(
                        match_id=match_id,
                        player_id="p_witcher_1",
                        action="play_card",
                        card_id=action["card_id"],
                        row=action["allowed_rows"][0],
                        action_id=f"p1-r{round_number}-play",
                    ),
                )

                p2_state = get_player_pvp_state(connection, "p_witcher_2")
                self.assertEqual(p2_state["legal_actions"]["turn_player_id"], "p_witcher_2")
                self.assertTrue(p2_state["legal_actions"]["is_player_turn"])
                record_gwent_action(
                    connection,
                    GwentActionInput(
                        match_id=match_id,
                        player_id="p_witcher_2",
                        action="pass",
                        action_id=f"p2-r{round_number}-pass",
                    ),
                )

                p1_pass_state = get_player_pvp_state(connection, "p_witcher_1")
                self.assertEqual(p1_pass_state["legal_actions"]["turn_player_id"], "p_witcher_1")
                return record_gwent_action(
                    connection,
                    GwentActionInput(
                        match_id=match_id,
                        player_id="p_witcher_1",
                        action="pass",
                        action_id=f"p1-r{round_number}-pass",
                    ),
                )

            first_round = win_round(1)
            second_round = win_round(2)
            finished = finish_gwent_match(connection, match_id, winner_id="p_witcher_1")
            p1_finished_state = get_player_pvp_state(connection, "p_witcher_1")
            p2_finished_state = get_player_pvp_state(connection, "p_witcher_2")
            ledger = connection.execute(
                """
                SELECT status, quantity, winner_id, loser_id
                FROM pvp_stake_ledger
                WHERE challenge_id = ?
                """,
                (challenge["challenge_id"],),
            ).fetchone()

        self.assertEqual(first_round["round"]["winner_id"], "p_witcher_1")
        self.assertEqual(first_round["match"]["round_losses"]["p_witcher_2"], 1)
        self.assertEqual(second_round["match"]["status"], "awaiting_finish")
        self.assertEqual(second_round["match"]["winner_id"], "p_witcher_1")
        self.assertEqual(finished["match"]["status"], "finished")
        self.assertEqual(finished["match"]["stake"]["status"], "applied")
        self.assertEqual(finished["match"]["stake"]["quantity"], 5)
        self.assertEqual(finished["stake_transfer"]["status"], "applied")
        self.assertIsNone(p1_finished_state["active_match"])
        self.assertIsNone(p2_finished_state["active_match"])
        self.assertEqual(p1_finished_state["recent_match"]["match_id"], match_id)
        self.assertEqual(p2_finished_state["recent_match"]["match_id"], match_id)
        self.assertEqual(p1_finished_state["recent_match"]["status"], "finished")
        self.assertEqual(p1_finished_state["recent_match"]["winner_id"], "p_witcher_1")
        self.assertEqual(p1_finished_state["recent_match"]["stake"]["status"], "applied")
        self.assertEqual(p2_finished_state["recent_match"]["stake"]["winner_id"], "p_witcher_1")
        self.assertEqual(p1_finished_state["opponent_id"], "p_witcher_2")
        self.assertEqual(p2_finished_state["opponent_id"], "p_witcher_1")
        self.assertEqual(p1_finished_state["recent_match"]["deck_state"]["p_witcher_2"]["hand"], [])
        self.assertEqual(p2_finished_state["recent_match"]["deck_state"]["p_witcher_1"]["hand"], [])
        self.assertEqual(
            dict(ledger),
            {
                "status": "applied",
                "quantity": 5,
                "winner_id": "p_witcher_1",
                "loser_id": "p_witcher_2",
            },
        )

    def test_gwent_bot_match_auto_plays_and_finishes_without_stake(self) -> None:
        settings = self.prepare_seed("pvp_bot_match", extra_deck_players=())
        with connect(settings) as connection:
            started = start_gwent_bot_match(
                connection,
                GwentBotMatchInput(player_id="p_witcher_1"),
            )
            match_id = started["match"]["match_id"]
            self.assertEqual(started["match"]["target_id"], "p_gwent_bot_training")
            self.assertEqual(started["current_round"]["turn_player_id"], "p_witcher_1")
            ordinary_state = get_player_pvp_state(connection, "p_witcher_1")
            self.assertIsNone(ordinary_state["active_challenge"])
            self.assertIsNone(ordinary_state["active_match"])
            self.assertTrue(ordinary_state["can_create_challenge"])

            for index in range(8):
                row = connection.execute(
                    "SELECT status FROM gwent_runtime_matches WHERE match_id = ?",
                    (match_id,),
                ).fetchone()
                if row["status"] == "finished":
                    break
                state = get_player_pvp_state(connection, "p_witcher_1", include_training=True)
                legal = state["legal_actions"]
                if legal.get("can_pass"):
                    record_gwent_action(
                        connection,
                        GwentActionInput(
                            match_id=match_id,
                            player_id="p_witcher_1",
                            action="pass",
                            action_id=f"human-pass-{index}",
                        ),
                    )
                else:
                    break

            match = connection.execute(
                "SELECT status, winner_id, result_applied_at FROM gwent_runtime_matches WHERE match_id = ?",
                (match_id,),
            ).fetchone()
            challenge = connection.execute(
                "SELECT status FROM pvp_challenges WHERE challenge_id = ?",
                (started["challenge"]["challenge_id"],),
            ).fetchone()
            stake_count = connection.execute(
                "SELECT COUNT(*) FROM pvp_stake_ledger WHERE challenge_id = ?",
                (started["challenge"]["challenge_id"],),
            ).fetchone()[0]
            finished_state = get_player_pvp_state(connection, "p_witcher_1", include_training=True)
            ordinary_finished_state = get_player_pvp_state(connection, "p_witcher_1")

        self.assertEqual(match["status"], "finished")
        self.assertIn(match["winner_id"], {"p_witcher_1", "p_gwent_bot_training"})
        self.assertIsNotNone(match["result_applied_at"])
        self.assertEqual(challenge["status"], "resolved")
        self.assertEqual(stake_count, 0)
        self.assertIsNone(finished_state["active_match"])
        self.assertEqual(finished_state["recent_match"]["match_id"], match_id)
        self.assertEqual(finished_state["recent_match"]["status"], "finished")
        self.assertIsNone(ordinary_finished_state["recent_match"])

    def test_gwent_bot_training_state_does_not_block_regular_pvp_state(self) -> None:
        settings = self.prepare_seed("pvp_bot_state_hidden", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            start_gwent_bot_match(
                connection,
                GwentBotMatchInput(player_id="p_witcher_1"),
            )
            ordinary_state = get_player_pvp_state(connection, "p_witcher_1")
            self.assertIsNone(ordinary_state["active_challenge"])
            self.assertIsNone(ordinary_state["active_match"])
            self.assertTrue(ordinary_state["can_create_challenge"])

            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    challenge_id="challenge_after_hidden_bot",
                    stake={"asset_type": "gold", "asset_id": "gold", "amount": 1},
                ),
            )
            state_after_challenge = get_player_pvp_state(connection, "p_witcher_1")

        self.assertEqual(challenge["challenge_id"], "challenge_after_hidden_bot")
        self.assertEqual(state_after_challenge["active_challenge"]["challenge_id"], "challenge_after_hidden_bot")
        self.assertIsNone(state_after_challenge["active_match"])

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_player_pvp_state_exposes_active_match_and_pending_submission(self) -> None:
        settings = self.prepare_seed(
            "pvp_api_player_state",
            extra_deck_players=("p_witcher_2", "p_witcher_3"),
        )
        with connect(settings) as connection:
            self.make_player_scoiatael_start(connection)
        client = TestClient(create_app(settings))
        challenge = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenge_id": "challenge_player_state_demo",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {"asset_type": "item", "asset_id": "stake_banner"},
            },
        ).json()

        pre_start = client.get("/api/pvp/player-state", headers=WITCHER_1_HEADERS)
        self.assertEqual(pre_start.status_code, 200)
        pre_start_state = pre_start.json()
        self.assertEqual(pre_start_state["active_challenge"]["challenge_id"], challenge["challenge_id"])
        self.assertIsNone(pre_start_state["active_match"])
        self.assertTrue(pre_start_state["legal_actions"]["can_start"])
        self.assertEqual(pre_start_state["challenge_tokens"], 2)
        self.assertFalse(pre_start_state["can_create_challenge"])

        started = client.post(
            f"/api/pvp/challenges/{challenge['challenge_id']}/start",
            headers=WITCHER_1_HEADERS,
            json={"preferred_starting_player_id": "p_witcher_1"},
        )
        self.assertEqual(started.status_code, 200)
        match_id = started.json()["match"]["match_id"]

        player_state = client.get("/api/pvp/player-state", headers=WITCHER_1_HEADERS)
        self.assertEqual(player_state.status_code, 200)
        state_payload = player_state.json()
        self.assertEqual(state_payload["active_match"]["match_id"], match_id)
        self.assertEqual(state_payload["opponent_id"], "p_witcher_2")
        self.assertEqual(len(state_payload["player_hand"]), 10)
        self.assertEqual(state_payload["current_round"]["status"], "ready_for_submission")
        self.assertEqual(state_payload["legal_actions"]["round_number"], 1)
        self.assertTrue(state_payload["legal_actions"]["can_play_card"])
        self.assertEqual(state_payload["table"]["zone_name"], "main_house_table")

        first_action = next(
            action
            for action in state_payload["legal_actions"]["playable_cards"]
            if action.get("type") == "unit" and action.get("allowed_rows")
        )
        submitted = client.post(
            f"/api/pvp/matches/{match_id}/actions",
            headers=WITCHER_1_HEADERS,
            json={
                "round_number": state_payload["legal_actions"]["round_number"],
                "action": "play_card",
                "card_id": first_action["card_id"],
                "row": first_action["allowed_rows"][0],
                "action_id": "api-player-state-p1-play",
            },
        )
        self.assertEqual(submitted.status_code, 200)

        pending_state = client.get("/api/pvp/player-state", headers=WITCHER_1_HEADERS).json()
        self.assertEqual(pending_state["current_round"]["status"], "ready_for_submission")
        self.assertEqual(pending_state["current_round"]["turn_player_id"], "p_witcher_2")
        self.assertFalse(pending_state["legal_actions"]["can_play_card"])

        target_state = client.get("/api/pvp/player-state", headers=WITCHER_2_HEADERS).json()
        self.assertTrue(target_state["legal_actions"]["can_play_card"])

        unrelated_state = client.get("/api/pvp/player-state", headers=WITCHER_3_HEADERS).json()
        self.assertIsNone(unrelated_state["active_match"])
        self.assertIsNone(unrelated_state["active_challenge"])
        self.assertEqual(unrelated_state["challenge_tokens"], 3)
        self.assertTrue(unrelated_state["can_create_challenge"])
        opponent_ids = {row["player_id"] for row in unrelated_state["opponents"]}
        self.assertIn("p_witcher_1", opponent_ids)
        self.assertIn("p_witcher_2", opponent_ids)
        self.assertIn("p_sorc_1", opponent_ids)
        self.assertNotIn("p_witcher_3", opponent_ids)
        self.assertNotIn("p_lord_1", opponent_ids)

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_ios_gwent_preflight_requires_challenge_token_before_pvp_mutation(self) -> None:
        settings = self.make_settings("pvp_api_ios_preflight_no_tokens")
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")
        client = TestClient(create_app(settings))
        args = SimpleNamespace(
            bot=False,
            p1_deck_id="",
            p2_deck_id="",
        )
        smoke_report: dict[str, object] = {
            "rounds": [],
            "steps": [],
            "idempotency_checks": [],
        }

        with self.assertRaisesRegex(SmokeError, "no challenge tokens"):
            run_preflight(
                TestClientSmokeApi(client),
                SmokePlayer("p_witcher_1", "WC-WOLF-6GF4"),
                SmokePlayer("p_witcher_2", "WC-CAT-1HN8"),
                args,
                smoke_report,
            )

        with connect(settings) as connection:
            challenge_count = connection.execute("SELECT COUNT(*) FROM pvp_challenges").fetchone()[0]
            match_count = connection.execute("SELECT COUNT(*) FROM gwent_runtime_matches").fetchone()[0]

        self.assertEqual(challenge_count, 0)
        self.assertEqual(match_count, 0)

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_gwent_ready_endpoint_starts_after_both_players_prepare(self) -> None:
        settings = self.prepare_seed("pvp_api_gwent_ready", extra_deck_players=("p_witcher_2",))
        client = TestClient(create_app(settings))
        challenge = client.post(
            "/api/pvp/challenges",
            headers=WITCHER_1_HEADERS,
            json={
                "challenge_id": "challenge_api_gwent_ready",
                "challenger_id": "p_witcher_1",
                "target_id": "p_witcher_2",
                "stake": {"asset_type": "gold", "asset_id": "gold", "amount": 5},
            },
        )
        self.assertEqual(challenge.status_code, 200)
        with connect(settings) as connection:
            p1_mulligan = self.opening_hand_for(
                connection,
                challenge_id="challenge_api_gwent_ready",
                player_id="p_witcher_1",
            )[0]
            p2_mulligan = self.opening_hand_for(
                connection,
                challenge_id="challenge_api_gwent_ready",
                player_id="p_witcher_2",
            )[0]

        p1_ready = client.post(
            "/api/pvp/challenges/challenge_api_gwent_ready/ready",
            headers=WITCHER_1_HEADERS,
            json={"mulligans": [p1_mulligan]},
        )
        self.assertEqual(p1_ready.status_code, 200)
        p1_payload = p1_ready.json()
        self.assertFalse(p1_payload["started"])
        self.assertIsNone(p1_payload["match"])
        self.assertEqual(p1_payload["prep"]["ready_players"], ["p_witcher_1"])

        p2_ready = client.post(
            "/api/pvp/challenges/challenge_api_gwent_ready/ready",
            headers=WITCHER_2_HEADERS,
            json={"mulligans": [p2_mulligan]},
        )
        self.assertEqual(p2_ready.status_code, 200)
        p2_payload = p2_ready.json()
        self.assertTrue(p2_payload["started"])
        self.assertEqual(p2_payload["challenge"]["status"], "started")
        self.assertEqual(p2_payload["match"]["deck_state"]["p_witcher_1"]["mulligans"], [p1_mulligan])
        self.assertEqual(p2_payload["match"]["deck_state"]["p_witcher_2"]["mulligans"], [p2_mulligan])

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_ios_gwent_http_smoke_handles_scoiatael_opponent_first_turn(self) -> None:
        settings = self.prepare_seed("pvp_api_ios_smoke_scoia", extra_deck_players=())
        client = TestClient(create_app(settings))
        args = SimpleNamespace(
            challenge_id="challenge_ios_http_smoke_scoia",
            p1_deck_id="deck_witcher_wolf_scoiatael",
            p1_starting_player_id="p_witcher_2",
            p2_deck_id="deck_witcher_cat",
            p2_starting_player_id="",
            stake_gold=5,
            skip_preflight=False,
            skip_idempotency_check=False,
            poll_attempts=4,
            poll_seconds=0.0,
        )
        report: dict[str, object] = {
            "challenge_id": args.challenge_id,
            "rounds": [],
            "steps": [],
            "idempotency_checks": [],
        }

        run_smoke(
            TestClientSmokeApi(client),
            SmokePlayer("p_witcher_1", "WC-WOLF-6GF4"),
            SmokePlayer("p_witcher_2", "WC-CAT-1HN8"),
            args,
            report,
        )

        self.assertEqual(report["starting_player_id"], "p_witcher_2")
        self.assertEqual(report["winner_id"], "p_witcher_1")
        self.assertEqual(report["stake_transfer_status"], "applied")
        self.assertEqual(report["recent_match_id"], report["match_id"])
        self.assertEqual(report["idempotency_checks"][0]["duplicate"], True)
        self.assertEqual(report["rounds"][0]["actions"][0]["player_id"], "p_witcher_2")
        self.assertEqual(report["rounds"][0]["actions"][0]["action"], "pass")

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_ios_gwent_bot_http_smoke_finishes_training_match(self) -> None:
        settings = self.prepare_seed("pvp_api_ios_bot_smoke", extra_deck_players=())
        client = TestClient(create_app(settings))
        args = SimpleNamespace(
            challenge_id="challenge_ios_bot_http_smoke",
            p1_deck_id="deck_witcher_wolf",
            skip_preflight=False,
            skip_idempotency_check=False,
            poll_attempts=4,
            poll_seconds=0.0,
            bot_max_actions=40,
        )
        report: dict[str, object] = {
            "challenge_id": args.challenge_id,
            "rounds": [],
            "steps": [],
            "idempotency_checks": [],
        }

        run_bot_smoke(
            TestClientSmokeApi(client),
            SmokePlayer("p_witcher_1", "WC-WOLF-6GF4"),
            args,
            report,
        )

        self.assertEqual(report["recent_match_id"], report["match_id"])
        self.assertIn(report["finished_match_status"], {"finished", "needs_master_review"})
        if report["finished_match_status"] == "finished":
            self.assertIn(report["winner_id"], {"p_witcher_1", "p_gwent_bot_training"})
        else:
            self.assertEqual(report["review_reason"], "double_loss_tie_requires_master_review")
        self.assertEqual(report["stake_transfer_status"], "practice_no_stake")
        self.assertEqual(report["bot"]["player_id"], "p_gwent_bot_training")
        self.assertEqual(report["idempotency_checks"][0]["duplicate"], True)

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_ios_gwent_preflight_only_checks_readiness_without_creating_match(self) -> None:
        settings = self.prepare_seed("pvp_api_ios_preflight_only", extra_deck_players=())
        client = TestClient(create_app(settings))
        args = SimpleNamespace(
            bot=False,
            p1_deck_id="deck_witcher_wolf_scoiatael",
            p2_deck_id="deck_witcher_cat",
        )
        report: dict[str, object] = {
            "rounds": [],
            "steps": [],
            "idempotency_checks": [],
        }

        run_preflight(
            TestClientSmokeApi(client),
            SmokePlayer("p_witcher_1", "WC-WOLF-6GF4"),
            SmokePlayer("p_witcher_2", "WC-CAT-1HN8"),
            args,
            report,
        )

        with connect(settings) as connection:
            challenge_count = connection.execute("SELECT COUNT(*) FROM pvp_challenges").fetchone()[0]
            match_count = connection.execute("SELECT COUNT(*) FROM gwent_runtime_matches").fetchone()[0]
            stake_count = connection.execute("SELECT COUNT(*) FROM pvp_stake_ledger").fetchone()[0]

        self.assertEqual(report["health"]["status"], "ok")
        self.assertEqual(report["health"]["database_status"], "ok")
        self.assertEqual(report["health"]["api_revision"], "ios-gwent-pvp-v1")
        self.assertIn("ios_gwent_preflight", report["health"]["api_features"])
        self.assertGreaterEqual(report["tables"]["count"], 1)
        self.assertEqual(
            report["snapshots"]["p_witcher_1"]["selected_deck_id"],
            "deck_witcher_wolf_scoiatael",
        )
        self.assertEqual(
            report["snapshots"]["p_witcher_2"]["selected_deck_id"],
            "deck_witcher_cat",
        )
        self.assertEqual(challenge_count, 0)
        self.assertEqual(match_count, 0)
        self.assertEqual(stake_count, 0)

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
        with connect(settings) as connection:
            p1_mulligan = self.opening_hand_for(
                connection,
                challenge_id=challenge["challenge_id"],
                player_id="p_witcher_1",
            )[0]
        started = client.post(
            f"/api/pvp/challenges/{challenge['challenge_id']}/start",
            headers=WITCHER_1_HEADERS,
            json={"mulligans_by_player": {"p_witcher_1": [p1_mulligan]}},
        )

        self.assertEqual(started.status_code, 200)
        match = started.json()["match"]
        match_id = match["match_id"]
        self.assertEqual(match["status"], "active")
        self.assertEqual(len(match["deck_state"]["p_witcher_1"]["hand"]), 10)
        self.assertEqual(match["deck_state"]["p_witcher_1"]["mulligans"], [p1_mulligan])
        self.assertFalse(match["deck_state"]["cards_burn_after_round"])

        with connect(settings) as connection:
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["gwent_unit_02", "gwent_unit_03"],
                    "p_witcher_2": ["gwent_unit_01"],
                },
            )
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
        self.assertEqual(round_payload["row_scores"]["p_witcher_2"]["melee"], 1)
        self.assertFalse(round_payload["round_state"]["cards_burned"])
        first_match = first_round.json()["match"]
        self.assertNotIn("gwent_unit_02", first_match["deck_state"]["p_witcher_1"]["hand"])
        self.assertIn("gwent_unit_02", first_match["deck_state"]["p_witcher_1"]["graveyard"])

        with connect(settings) as connection:
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["gwent_unit_07"],
                    "p_witcher_2": ["gwent_unit_02", "gwent_unit_03"],
                },
            )
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

        with connect(settings) as connection:
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["gwent_unit_08", "gwent_unit_05"],
                    "p_witcher_2": ["gwent_unit_08"],
                },
            )
        third_round = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=MASTER_HEADERS,
            json={
                "round_number": 3,
                "plays": [
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_08"},
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_05"},
                    {"player_id": "p_witcher_2", "card_id": "gwent_unit_08"},
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
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_3": ["gwent_unit_01"],
                    "p_witcher_4": ["gwent_unit_02", "gwent_unit_03"],
                },
            )
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
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_3": ["gwent_unit_08"],
                    "p_witcher_4": ["gwent_unit_08", "gwent_unit_05"],
                },
            )
            second_round = record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_3", "card_id": "gwent_unit_08"},
                        {"player_id": "p_witcher_4", "card_id": "gwent_unit_08"},
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

    def test_potion_stake_refunds_or_transfers_inventory_once(self) -> None:
        settings = self.prepare_seed(
            "pvp_potion_stakes",
            extra_deck_players=("p_witcher_2", "p_witcher_3", "p_witcher_4"),
        )
        with connect(settings) as connection:
            now = datetime(2026, 6, 2, 10, 5, tzinfo=UTC).isoformat(timespec="seconds")
            connection.execute(
                """
                INSERT INTO potion_inventory (
                    inventory_id, player_id, potion_id, quantity, updated_at
                )
                VALUES
                    ('inv_pvp_potion_refund', 'p_witcher_1', 'potion_common_swallow', 2, ?),
                    ('inv_pvp_potion_finish', 'p_witcher_3', 'potion_common_swallow', 1, ?)
                """,
                (now, now),
            )

            cancelled = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_potion_cancel",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={
                        "asset_type": "potion",
                        "asset_id": "potion_common_swallow",
                        "quantity": 2,
                    },
                ),
            )
            p1_after_lock = self.potion_quantity(connection, "p_witcher_1", "potion_common_swallow")
            record_pvp_refusal(
                connection,
                cancelled["challenge_id"],
                reason="safety_stop",
                actor_id="p_witcher_2",
            )
            p1_after_refund = self.potion_quantity(connection, "p_witcher_1", "potion_common_swallow")
            refunded_stake = connection.execute(
                """
                SELECT status, asset_type, asset_id, quantity
                FROM pvp_stake_ledger
                WHERE challenge_id = 'challenge_potion_cancel'
                """
            ).fetchone()

            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_potion_finish",
                    challenger_id="p_witcher_3",
                    target_id="p_witcher_4",
                    stake={"asset_type": "potion", "asset_id": "potion_common_swallow"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            match_id = started["match"]["match_id"]
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_3": ["gwent_unit_01"],
                    "p_witcher_4": ["gwent_unit_02", "gwent_unit_03"],
                },
            )
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
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_3": ["gwent_unit_08"],
                    "p_witcher_4": ["gwent_unit_08", "gwent_unit_05"],
                },
            )
            record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_3", "card_id": "gwent_unit_08"},
                        {"player_id": "p_witcher_4", "card_id": "gwent_unit_08"},
                        {"player_id": "p_witcher_4", "card_id": "gwent_unit_05"},
                    ],
                    "passed": {"p_witcher_3": True, "p_witcher_4": True},
                },
                round_number=2,
            )
            finished = finish_gwent_match(connection, match_id, winner_id="p_witcher_4")
            duplicate_finish = finish_gwent_match(connection, match_id, winner_id="p_witcher_4")
            p3_after_finish = self.potion_quantity(connection, "p_witcher_3", "potion_common_swallow")
            p4_after_finish = self.potion_quantity(connection, "p_witcher_4", "potion_common_swallow")
            active_stake_locks = connection.execute(
                "SELECT COUNT(*) FROM asset_locks WHERE lock_type = 'pvp_stake' AND status = 'active'"
            ).fetchone()[0]

        self.assertEqual(p1_after_lock, 0)
        self.assertEqual(p1_after_refund, 2)
        self.assertEqual(
            dict(refunded_stake),
            {
                "status": "refunded",
                "asset_type": "potion",
                "asset_id": "potion_common_swallow",
                "quantity": 2,
            },
        )
        self.assertEqual(finished["stake_transfer"]["status"], "applied")
        self.assertFalse(finished["duplicate"])
        self.assertTrue(duplicate_finish["duplicate"])
        self.assertEqual(p3_after_finish, 0)
        self.assertEqual(p4_after_finish, 1)
        self.assertEqual(active_stake_locks, 0)

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_api_player_gwent_round_submission_requires_master(self) -> None:
        settings = self.prepare_seed("pvp_api_player_round_submit_rejected", extra_deck_players=("p_witcher_2",))
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

        player_submit = client.post(
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
        self.assertEqual(player_submit.status_code, 403, player_submit.text)
        self.assertIn("use /actions for gameplay", player_submit.json()["detail"])

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

        with connect(settings) as connection:
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {"p_witcher_1": ["gwent_unit_02"]},
            )
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
        with connect(settings) as connection:
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["gwent_unit_02", "gwent_unit_03"],
                    "p_witcher_2": ["gwent_unit_01"],
                },
            )
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
        with connect(settings) as connection:
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["gwent_unit_08", "gwent_unit_05"],
                    "p_witcher_2": ["gwent_unit_02"],
                },
            )
        second_round = client.post(
            f"/api/pvp/matches/{match_id}/rounds",
            headers=MASTER_HEADERS,
            json={
                "round_number": 2,
                "plays": [
                    {"player_id": "p_witcher_1", "card_id": "gwent_unit_08"},
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
        self.assertIn("cannot be converted into lord army unit cards", invalid_conversion.json()["detail"])
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
            self.make_player_scoiatael_start(connection)
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
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    preferred_starting_player_id="p_witcher_1",
                ),
            )
            match_id = started["match"]["match_id"]
            p1_state = get_player_pvp_state(connection, "p_witcher_1")
            not_in_hand = None
            not_in_hand_row = None
            for card_id in started["match"]["deck_state"]["p_witcher_1"]["draw_pile"]:
                if card_id in p1_state["player_hand"]:
                    continue
                card = connection.execute(
                    "SELECT row, type FROM gwent_cards WHERE card_id = ?",
                    (card_id,),
                ).fetchone()
                if card is None or str(card["type"]) != "unit":
                    continue
                row = str(card["row"] or "melee")
                not_in_hand = card_id
                not_in_hand_row = row if row in {"melee", "ranged", "siege"} else "melee"
                break
            self.assertIsNotNone(not_in_hand)
            self.assertIsNotNone(not_in_hand_row)

            with self.assertRaisesRegex(PvpError, "not in current hand"):
                record_gwent_action(
                    connection,
                    GwentActionInput(
                        match_id=match_id,
                        player_id="p_witcher_1",
                        action="play_card",
                        card_id=not_in_hand,
                        row=not_in_hand_row,
                    ),
                )

            played_action = self.strongest_legal_unit_action(connection, p1_state)
            record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id="p_witcher_1",
                    action="play_card",
                    card_id=played_action["card_id"],
                    row=played_action["allowed_rows"][0],
                ),
            )
            record_gwent_action(
                connection,
                GwentActionInput(
                    match_id=match_id,
                    player_id="p_witcher_2",
                    action="pass",
                ),
            )
            with self.assertRaisesRegex(PvpError, "not in current hand"):
                record_gwent_action(
                    connection,
                    GwentActionInput(
                        match_id=match_id,
                        player_id="p_witcher_1",
                        action="play_card",
                        card_id=played_action["card_id"],
                        row=played_action["allowed_rows"][0],
                    ),
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

            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["gwent_unit_01"],
                    "p_witcher_2": ["gwent_unit_01"],
                },
            )
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

            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["gwent_unit_02"],
                    "p_witcher_2": ["gwent_unit_02"],
                },
            )
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
        units = list(NORTHERN_TEST_UNITS)
        p1_cards = [
            "gwent_unit_01",
            "gwent_unit_02",
            "gwent_decoy",
            "gwent_horn",
            "gwent_weather_frost",
            "gwent_scorch",
            *[card_id for card_id in units if card_id not in {"gwent_unit_01", "gwent_unit_02"}],
        ]
        with connect(settings) as connection:
            connection.execute(
                "UPDATE gwent_cards SET strength = 10 WHERE card_id = 'sc_ciaran'"
            )
            connection.execute(
                "UPDATE gwent_decks SET card_ids = ? WHERE player_id = 'p_witcher_1'",
                (";".join(p1_cards),),
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
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    deck_ids_by_player={"p_witcher_2": "deck_p_witcher_2_scoiatael"},
                ),
            )
            match_id = started["match"]["match_id"]

            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": [
                        "gwent_unit_01",
                        "gwent_unit_02",
                        "gwent_decoy",
                        "gwent_horn",
                        "gwent_weather_frost",
                        "gwent_scorch",
                    ],
                    "p_witcher_2": ["sc_ciaran", "rare_gwent_01"],
                },
            )
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
                        {"player_id": "p_witcher_2", "card_id": "sc_ciaran", "row": "ranged"},
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
        self.assertIn({"card_id": "rare_gwent_01", "effect": "hero", "scope": "unit"}, effects)
        self.assertIn({"card_id": "rare_gwent_01", "effect": "morale", "scope": "unit"}, effects)
        self.assertEqual(scorch["removed_card_ids"], ["sc_ciaran"])
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
        with connect(settings) as connection:
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
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    deck_ids_by_player={"p_witcher_1": "deck_witcher_wolf_monsters"},
                ),
            )
            match_id = started["match"]["match_id"]

            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["mo_botchling", "mo_cockatrice"],
                    "p_witcher_2": ["gwent_unit_01"],
                },
            )
            first = record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "mo_botchling"},
                        {"player_id": "p_witcher_1", "card_id": "mo_cockatrice"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                    ],
                    "passed": {"p_witcher_1": True, "p_witcher_2": True},
                },
                round_number=1,
            )
            revive_target = next(
                card_id
                for card_id in ("mo_botchling", "mo_cockatrice")
                if card_id in first["match"]["deck_state"]["p_witcher_1"]["graveyard"]
            )
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["rare_gwent_04", "rare_gwent_05", "gwent_unit_19", "gwent_unit_20"],
                },
            )
            result = record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_leader_monsters", "row": "melee"},
                        {"player_id": "p_witcher_1", "card_id": "rare_gwent_04"},
                        {
                            "player_id": "p_witcher_1",
                            "card_id": "rare_gwent_05",
                            "revive_card_id": revive_target,
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
        self.assertEqual(medic["revived_card_id"], revive_target)
        self.assertEqual(set(muster["mustered_card_ids"]), {"gwent_unit_20", "mo_nekker_3"})
        self.assertEqual(leader["effect"], "leader_eredin_melee_horn")
        self.assertTrue(result["match"]["deck_state"]["p_witcher_1"]["leader_used"])
        self.assertIn("gwent_unit_20", round_state["consumed_cards"]["p_witcher_1"])
        self.assertIn("mo_nekker_3", round_state["consumed_cards"]["p_witcher_1"])
        self.assertIn("rare_gwent_04", [unit["card_id"] for unit in round_state["board"]["p_witcher_2"]["melee"]])

    def test_gwent_rare_base_cards_apply_mysterious_elf_and_dandelion(self) -> None:
        settings = self.prepare_seed("pvp_rare_base_cards", extra_deck_players=("p_witcher_2",))
        units = list(NORTHERN_TEST_UNITS[:22])
        desired_opening = {"gwent_weather_frost", "gwent_clear_weather", "rare_gwent_04", "rare_gwent_06"}
        p1_cards = [
            "gwent_weather_frost",
            "gwent_clear_weather",
            "rare_gwent_04",
            "rare_gwent_06",
            *units,
        ]
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_rare_base_cards",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "rare_specials_marker"},
                ),
            )
            for offset in range(len(p1_cards)):
                candidate_cards = p1_cards[offset:] + p1_cards[:offset]
                connection.execute(
                    "UPDATE gwent_decks SET card_ids = ? WHERE player_id = 'p_witcher_1'",
                    (";".join(candidate_cards),),
                )
                if desired_opening.issubset(
                    set(
                        self.opening_hand_for(
                            connection,
                            challenge_id=challenge["challenge_id"],
                            player_id="p_witcher_1",
                        )
                    )
                ):
                    break
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            deck_state = started["match"]["deck_state"]
            deck_state["p_witcher_1"]["hand"] = [
                "gwent_weather_frost",
                "gwent_clear_weather",
                "rare_gwent_04",
                "rare_gwent_06",
            ]
            deck_state["p_witcher_1"]["draw_pile"] = [
                card_id
                for card_id in p1_cards
                if card_id not in deck_state["p_witcher_1"]["hand"]
            ]
            self.replace_active_round_deck_state(connection, started["match"]["match_id"], deck_state)
            result = record_gwent_round(
                connection,
                started["match"]["match_id"],
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_weather_frost"},
                        {"player_id": "p_witcher_1", "card_id": "gwent_clear_weather"},
                        {"player_id": "p_witcher_1", "card_id": "rare_gwent_04"},
                        {"player_id": "p_witcher_1", "card_id": "rare_gwent_06"},
                    ],
                    "passed": {"p_witcher_1": True, "p_witcher_2": True},
                },
                round_number=1,
            )

        round_state = result["round"]["round_state"]
        effects = round_state["effects_applied"]
        mysterious_elf_spy = next(item for item in effects if item["card_id"] == "rare_gwent_04" and item["effect"] == "spy")
        dandelion_horn = next(item for item in effects if item["card_id"] == "rare_gwent_06")

        self.assertEqual(round_state["weather_rows"], [])
        self.assertEqual(round_state["horn_rows"]["p_witcher_1"], ["melee"])
        self.assertEqual(len(mysterious_elf_spy["drawn_card_ids"]), 2)
        self.assertEqual(dandelion_horn["effect"], "commanders_horn")
        for drawn_card_id in mysterious_elf_spy["drawn_card_ids"]:
            self.assertIn(drawn_card_id, result["match"]["deck_state"]["p_witcher_1"]["hand"])
            self.assertNotIn(drawn_card_id, result["match"]["deck_state"]["p_witcher_1"]["draw_pile"])
        self.assertIn("rare_gwent_04", [unit["card_id"] for unit in round_state["board"]["p_witcher_2"]["melee"]])
        self.assertIn(
            {"card_id": "gwent_clear_weather", "effect": "clear_weather", "scope": "special"},
            effects,
        )

    def test_gwent_northern_realms_draws_card_after_winning_round(self) -> None:
        settings = self.prepare_seed("pvp_northern_round_win_draw", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            self.ensure_test_item_asset(connection, "northern_round_win_marker")
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="northern_round_win_marker",
                source="test_pvp_northern_round_win",
                source_ref_id="northern_round_win_marker",
            )
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_northern_round_win_draw",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "northern_round_win_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(challenge_id=challenge["challenge_id"]),
            )
            self.force_cards_into_match_hands(
                connection,
                started["match"]["match_id"],
                {
                    "p_witcher_1": ["gwent_unit_16"],
                    "p_witcher_2": ["gwent_unit_01"],
                },
            )
            result = record_gwent_round(
                connection,
                started["match"]["match_id"],
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_16"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                    ],
                    "passed": {"p_witcher_1": True, "p_witcher_2": True},
                },
                round_number=1,
            )

        effects = result["round"]["round_state"]["effects_applied"]
        faction_effect = next(item for item in effects if item["effect"] == "faction_northern_realms_draw")
        p1_state = result["match"]["deck_state"]["p_witcher_1"]
        self.assertEqual(result["round"]["winner_id"], "p_witcher_1")
        self.assertEqual(started["match"]["deck_state"]["p_witcher_1"]["faction"], "northern")
        self.assertEqual(faction_effect["player_id"], "p_witcher_1")
        self.assertEqual(len(faction_effect["drawn_card_ids"]), 1)
        northern_drawn = faction_effect["drawn_card_ids"][0]
        self.assertIn(northern_drawn, p1_state["hand"])
        self.assertNotIn(northern_drawn, p1_state["draw_pile"])

    def test_gwent_monsters_keep_one_unit_after_round(self) -> None:
        settings = self.prepare_seed("pvp_monsters_carryover", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_monsters_carryover",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "stake_banner"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    deck_ids_by_player={"p_witcher_1": "deck_witcher_wolf_monsters"},
                ),
            )
            match_id = started["match"]["match_id"]
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["gwent_unit_19"],
                    "p_witcher_2": ["gwent_unit_01"],
                },
            )
            result = record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_19"},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                    ],
                    "passed": {"p_witcher_1": True, "p_witcher_2": True},
                },
                round_number=1,
            )

        effect = next(
            item
            for item in result["round"]["round_state"]["effects_applied"]
            if item["effect"] == "faction_monsters_keep_unit"
        )
        carryover_units = [
            unit
            for row_units in result["match"]["deck_state"]["p_witcher_1"]["rows"].values()
            for unit in row_units
        ]
        self.assertEqual(len(carryover_units), 1)
        self.assertEqual(carryover_units[0]["card_id"], effect["kept_card_id"])
        self.assertTrue(carryover_units[0]["carried_by_faction"])

    def test_gwent_skellige_deck_is_not_available_in_base_seed(self) -> None:
        settings = self.prepare_seed("pvp_skellige_restore", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_skellige_restore",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "stake_banner"},
                ),
            )
            with self.assertRaisesRegex(PvpError, "not available"):
                start_pvp_challenge(
                    connection,
                    ChallengeStartInput(
                        challenge_id=challenge["challenge_id"],
                        deck_ids_by_player={"p_witcher_1": "deck_witcher_wolf_skellige"},
                    ),
                )

    def test_gwent_nilfgaard_wins_scored_tie_round(self) -> None:
        settings = self.prepare_seed("pvp_nilfgaard_tie_win", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            self.ensure_test_item_asset(connection, "nilfgaard_tie_marker")
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="nilfgaard_tie_marker",
                source="test_pvp_nilfgaard_tie",
                source_ref_id="nilfgaard_tie_marker",
            )
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_nilfgaard_tie_win",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "nilfgaard_tie_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    deck_ids_by_player={"p_witcher_1": "deck_witcher_wolf_nilfgaard"},
                ),
            )
            deck_state = started["match"]["deck_state"]
            deck_state["p_witcher_1"]["hand"] = ["neutral_vesemir"]
            deck_state["p_witcher_1"]["draw_pile"] = []
            deck_state["p_witcher_2"]["hand"] = ["neutral_vesemir"]
            deck_state["p_witcher_2"]["draw_pile"] = []
            self.replace_active_round_deck_state(connection, started["match"]["match_id"], deck_state)
            result = record_gwent_round(
                connection,
                started["match"]["match_id"],
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "neutral_vesemir"},
                        {"player_id": "p_witcher_2", "card_id": "neutral_vesemir"},
                    ],
                    "passed": {"p_witcher_1": True, "p_witcher_2": True},
                },
                round_number=1,
            )

        effects = result["round"]["round_state"]["effects_applied"]
        faction_effect = next(item for item in effects if item["effect"] == "faction_nilfgaard_tie_win")
        self.assertEqual(started["match"]["deck_state"]["p_witcher_1"]["faction"], "nilfgaard")
        self.assertEqual(result["round"]["row_scores"]["p_witcher_1"]["melee"], 6)
        self.assertEqual(result["round"]["row_scores"]["p_witcher_2"]["melee"], 6)
        self.assertFalse(result["round"]["tie"])
        self.assertEqual(result["round"]["winner_id"], "p_witcher_1")
        self.assertEqual(result["match"]["round_losses"]["p_witcher_1"], 0)
        self.assertEqual(result["match"]["round_losses"]["p_witcher_2"], 1)
        self.assertEqual(faction_effect["player_id"], "p_witcher_1")

    def test_gwent_emhyr_spy_hand_reveals_deterministic_random_cards(self) -> None:
        settings = self.prepare_seed("pvp_emhyr_random_reveal", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            self.ensure_test_item_asset(connection, "emhyr_random_reveal_marker")
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="emhyr_random_reveal_marker",
                source="test_pvp_emhyr_random_reveal",
                source_ref_id="emhyr_random_reveal_marker",
            )
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_emhyr_random_reveal",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "emhyr_random_reveal_marker"},
                ),
            )
            connection.execute(
                """
                UPDATE gwent_decks
                SET leader_card_id = 'gwent_leader_emhyr_emperor'
                WHERE deck_id = 'deck_witcher_wolf_nilfgaard'
                """
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    deck_ids_by_player={"p_witcher_1": "deck_witcher_wolf_nilfgaard"},
                ),
            )
            deck_state = started["match"]["deck_state"]
            opponent_hand = [
                "gwent_unit_01",
                "gwent_unit_02",
                "gwent_unit_03",
                "gwent_unit_05",
                "gwent_unit_06",
            ]
            deck_state["p_witcher_2"]["hand"] = list(opponent_hand)
            self.replace_active_round_deck_state(connection, started["match"]["match_id"], deck_state)

            result = record_gwent_round(
                connection,
                started["match"]["match_id"],
                {
                    "plays": [{"player_id": "p_witcher_1", "card_id": "gwent_leader_emhyr_emperor"}],
                    "passed": {"p_witcher_1": True, "p_witcher_2": True},
                },
                round_number=1,
            )

        p1_state = result["match"]["deck_state"]["p_witcher_1"]
        reveal = p1_state["private_reveals"][0]
        expected = random.Random(reveal["reveal_seed"]).sample(opponent_hand, 3)
        self.assertEqual(reveal["card_ids"], expected)
        self.assertNotEqual(reveal["card_ids"], opponent_hand[:3])
        leader_effect = next(item for item in result["round"]["round_state"]["effects_applied"] if item["scope"] == "leader")
        self.assertEqual(leader_effect["revealed_count"], 3)
        self.assertEqual(leader_effect["reveal_seed"], reveal["reveal_seed"])

    def test_gwent_eredin_discard_draw_requires_explicit_card_choices(self) -> None:
        settings = self.prepare_seed("pvp_eredin_discard_draw_choices", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            self.ensure_test_item_asset(connection, "eredin_choice_marker")
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="eredin_choice_marker",
                source="test_pvp_eredin_choice",
                source_ref_id="eredin_choice_marker",
            )
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_eredin_choice",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "eredin_choice_marker"},
                ),
            )
            connection.execute(
                """
                UPDATE gwent_decks
                SET leader_card_id = 'gwent_leader_eredin_destroyer'
                WHERE deck_id = 'deck_witcher_wolf_monsters'
                """
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    deck_ids_by_player={"p_witcher_1": "deck_witcher_wolf_monsters"},
                ),
            )
            match_id = started["match"]["match_id"]
            p1_state = started["match"]["deck_state"]["p_witcher_1"]
            discard_ids = list(p1_state["hand"][:2])
            target_card_id = str(p1_state["draw_pile"][0])

            with self.assertRaisesRegex(PvpError, "requires exactly two distinct discard_card_ids"):
                record_gwent_round(
                    connection,
                    match_id,
                    {
                        "plays": [{"player_id": "p_witcher_1", "card_id": "gwent_leader_eredin_destroyer"}],
                        "passed": {"p_witcher_1": True, "p_witcher_2": True},
                    },
                    round_number=1,
                )

            result = record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {
                            "player_id": "p_witcher_1",
                            "card_id": "gwent_leader_eredin_destroyer",
                            "target_card_id": target_card_id,
                            "discard_card_ids": discard_ids,
                        }
                    ],
                    "passed": {"p_witcher_1": True, "p_witcher_2": True},
                },
                round_number=1,
            )

        p1_after = result["match"]["deck_state"]["p_witcher_1"]
        leader_effect = next(item for item in result["round"]["round_state"]["effects_applied"] if item["scope"] == "leader")
        self.assertEqual(leader_effect["discarded_card_ids"], discard_ids)
        self.assertEqual(leader_effect["drawn_card_id"], target_card_id)
        for discard_id in discard_ids:
            self.assertIn(discard_id, p1_after["graveyard"])
            self.assertNotIn(discard_id, p1_after["hand"])
        self.assertIn(target_card_id, p1_after["hand"])
        self.assertNotIn(target_card_id, p1_after["draw_pile"])

    def test_gwent_scoiatael_ready_choice_controls_first_turn(self) -> None:
        settings = self.prepare_seed("pvp_scoiatael_first_turn", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            self.ensure_test_item_asset(connection, "scoiatael_first_turn_marker")
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="scoiatael_first_turn_marker",
                source="test_pvp_scoiatael_first_turn",
                source_ref_id="scoiatael_first_turn_marker",
            )
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_scoiatael_first_turn",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "scoiatael_first_turn_marker"},
                ),
            )

            with self.assertRaisesRegex(PvpError, "requires a Scoia'tael deck"):
                prepare_gwent_challenge(
                    connection,
                    GwentPreparationInput(
                        challenge_id=challenge["challenge_id"],
                        player_id="p_witcher_1",
                        preferred_starting_player_id="p_witcher_2",
                    ),
                )

            p1_ready = prepare_gwent_challenge(
                connection,
                GwentPreparationInput(
                    challenge_id=challenge["challenge_id"],
                    player_id="p_witcher_1",
                    deck_id="deck_witcher_wolf_scoiatael",
                    preferred_starting_player_id="p_witcher_2",
                ),
            )
            p2_ready = prepare_gwent_challenge(
                connection,
                GwentPreparationInput(
                    challenge_id=challenge["challenge_id"],
                    player_id="p_witcher_2",
                ),
            )

        self.assertFalse(p1_ready["started"])
        self.assertEqual(
            p1_ready["prep"]["preferred_starting_player_ids_by_player"]["p_witcher_1"],
            "p_witcher_2",
        )
        self.assertTrue(p2_ready["started"])
        active_round = p2_ready["match"]["deck_state"]["active_round"]
        faction_effect = p2_ready["match"]["deck_state"]["faction_effects"][0]
        self.assertEqual(p2_ready["match"]["deck_state"]["p_witcher_1"]["faction"], "scoiatael")
        self.assertEqual(active_round["starting_player_id"], "p_witcher_2")
        self.assertEqual(active_round["turn_player_id"], "p_witcher_2")
        self.assertEqual(faction_effect["effect"], "faction_scoiatael_choose_first")
        self.assertEqual(faction_effect["player_id"], "p_witcher_1")
        self.assertEqual(faction_effect["starting_player_id"], "p_witcher_2")

    def test_gwent_scoiatael_mirror_uses_coin_toss_instead_of_implicit_choice(self) -> None:
        settings = self.prepare_seed("pvp_scoiatael_mirror_first_turn", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            self.ensure_test_item_asset(connection, "scoiatael_mirror_marker")
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="scoiatael_mirror_marker",
                source="test_pvp_scoiatael_mirror",
                source_ref_id="scoiatael_mirror_marker",
            )
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_scoiatael_mirror",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "scoiatael_mirror_marker"},
                ),
            )
            started = start_pvp_challenge(
                connection,
                ChallengeStartInput(
                    challenge_id=challenge["challenge_id"],
                    deck_ids_by_player={
                        "p_witcher_1": "deck_witcher_wolf_scoiatael",
                        "p_witcher_2": "deck_p_witcher_2_scoiatael",
                    },
                ),
            )

        active_round = started["match"]["deck_state"]["active_round"]
        faction_effect = started["match"]["deck_state"]["faction_effects"][0]
        self.assertEqual(faction_effect["effect"], "faction_scoiatael_mirror_coin_toss")
        self.assertEqual(faction_effect["scoiatael_player_ids"], ["p_witcher_1", "p_witcher_2"])
        self.assertIn(active_round["starting_player_id"], ["p_witcher_1", "p_witcher_2"])
        self.assertEqual(active_round["starting_player_id"], faction_effect["starting_player_id"])

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

            self.force_cards_into_match_hands(
                connection,
                match_id,
                {"p_witcher_2": ["gwent_unit_01"]},
            )
            p1_leader = started["match"]["deck_state"]["p_witcher_1"]["leader_card_id"]
            record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": p1_leader},
                        {"player_id": "p_witcher_2", "card_id": "gwent_unit_01"},
                    ]
                },
                round_number=1,
            )
            with self.assertRaisesRegex(PvpError, "leader was already used"):
                record_gwent_round(
                    connection,
                    match_id,
                    {"plays": [{"player_id": "p_witcher_1", "card_id": p1_leader}]},
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

    def test_gwent_deck_contract_rejects_bad_mulligans_leader_unknown_cards_copy_limit_and_special_cap(self) -> None:
        units = list(NORTHERN_TEST_UNITS[:22])
        eleven_specials = [
            "gwent_weather_frost",
            "neutral_biting_frost_2",
            "neutral_biting_frost_3",
            "gwent_clear_weather",
            "neutral_clear_weather_2",
            "neutral_clear_weather_3",
            "gwent_horn",
            "neutral_commanders_horn_2",
            "neutral_commanders_horn_3",
            "neutral_commanders_horn_4",
            "gwent_decoy",
        ]
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
                "copy_limit",
                {"card_ids": ";".join([*units, "gwent_horn", "gwent_horn"])},
                {},
                "exceeds card copy limit",
            ),
            (
                "special_cap",
                {"card_ids": ";".join([*units, *eleven_specials])},
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

        settings = self.prepare_seed("pvp_deck_contract_selected_deck", extra_deck_players=("p_witcher_2",))
        with connect(settings) as connection:
            challenge = create_pvp_challenge(
                connection,
                ChallengeCreateInput(
                    challenge_id="challenge_deck_contract_selected_deck",
                    challenger_id="p_witcher_1",
                    target_id="p_witcher_2",
                    stake={"asset_type": "item", "asset_id": "deck_contract_unknown_card"},
                ),
            )
            with self.assertRaisesRegex(PvpError, "Gwent deck is not available for player"):
                prepare_gwent_challenge(
                    connection,
                    GwentPreparationInput(
                        challenge_id=challenge["challenge_id"],
                        player_id="p_witcher_1",
                        deck_id="deck_p_witcher_2",
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
        units = list(NORTHERN_TEST_UNITS[:22])
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
        units = list(NORTHERN_TEST_UNITS)
        p1_cards = [
            "rare_gwent_02",
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
            self.force_cards_into_match_hands(
                connection,
                missing_started["match"]["match_id"],
                {"p_witcher_1": ["gwent_decoy"]},
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
            self.force_cards_into_match_hands(
                connection,
                hero_started["match"]["match_id"],
                {"p_witcher_1": ["rare_gwent_02", "gwent_decoy"]},
            )
            with self.assertRaisesRegex(PvpError, "decoy target is not a non-hero unit"):
                record_gwent_round(
                    connection,
                    hero_started["match"]["match_id"],
                    {
                        "plays": [
                            {"player_id": "p_witcher_1", "card_id": "rare_gwent_02"},
                            {
                                "player_id": "p_witcher_1",
                                "card_id": "gwent_decoy",
                                "target_card_id": "rare_gwent_02",
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
                self.force_cards_into_match_hands(
                    connection,
                    match_id,
                    {
                        "p_witcher_1": [card_id],
                        "p_witcher_2": [card_id],
                    },
                )
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
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["gwent_unit_02", "gwent_unit_03"],
                    "p_witcher_2": ["gwent_unit_01"],
                },
            )
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
                self.force_cards_into_match_hands(
                    connection,
                    match_id,
                    {
                        "p_witcher_1": [card_id],
                        "p_witcher_2": [card_id],
                    },
                )
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
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["gwent_unit_02", "gwent_unit_03"],
                    "p_witcher_2": ["gwent_unit_01"],
                },
            )
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
            self.force_cards_into_match_hands(
                connection,
                match_id,
                {
                    "p_witcher_1": ["gwent_unit_08", "gwent_unit_05"],
                    "p_witcher_2": ["gwent_unit_02"],
                },
            )
            record_gwent_round(
                connection,
                match_id,
                {
                    "plays": [
                        {"player_id": "p_witcher_1", "card_id": "gwent_unit_08"},
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

    def test_personal_card_conversion_is_not_a_supported_runtime_path(self) -> None:
        settings = self.prepare_seed("pvp_conversion_rejects", extra_deck_players=())
        with connect(settings) as connection:
            with self.assertRaisesRegex(PvpError, "cannot be converted into lord army unit cards"):
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
            with self.assertRaisesRegex(PvpError, "cannot be converted into lord army unit cards"):
                convert_personal_card_to_lord(
                    connection,
                    player_id="p_witcher_1",
                    lord_id="p_lord_1",
                    personal_card_id="pc_infantry_t1",
                )

    def test_personal_card_conversion_rejects_non_owned_card_without_minting(self) -> None:
        settings = self.prepare_seed("pvp_card_conversion_non_owned", extra_deck_players=())
        with connect(settings) as connection:
            with self.assertRaisesRegex(PvpError, "cannot be converted into lord army unit cards"):
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

            with self.assertRaisesRegex(PvpError, "cannot be converted into lord army unit cards"):
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
    def test_api_personal_card_to_lord_conversion_rejects_without_consuming_card(self) -> None:
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

        self.assertEqual(first.status_code, 400)
        self.assertIn("cannot be converted into lord army unit cards", first.json()["detail"])
        self.assertEqual(second.status_code, 400)
        self.assertIn("cannot be converted into lord army unit cards", second.json()["detail"])

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
        self.assertIsNone(reserve)
        self.assertEqual(ownership_count, 1)
        self.assertEqual(conversion_count, 0)
        self.assertIsNone(event)


if __name__ == "__main__":
    unittest.main()
