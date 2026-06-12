from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import unittest
from uuid import uuid4

from backend.witcher_larp.asset_service import grant_asset_ownership
from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.event_models import EventSyncEvent, EventSyncRequest
from backend.witcher_larp.event_service import sync_events
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.pve_runtime import resolve_pve_scene
from backend.witcher_larp.runtime_schema import ensure_runtime_schema


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"


class PveRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_resolve_pve_scene_logs_single_d20_modifiers_and_scene_hp(self) -> None:
        settings = self._settings("pve_math")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )

        self.assertEqual(payload["result"], "success")
        self.assertEqual(payload["roll"], 8)
        self.assertEqual(payload["stat"], "Сила")
        self.assertEqual(payload["stat_value"], 3)
        self.assertEqual(payload["modifiers"], [])
        self.assertEqual(payload["server_modifier_total"], 0)
        self.assertEqual(payload["total"], 11)
        self.assertEqual(payload["dc"], 11)
        self.assertEqual(len(payload["roll_log"]), 1)
        self.assertEqual(payload["roll_source"], "app_generated")
        self.assertEqual(payload["roll_log"][0]["source"], "app_generated")
        self.assertEqual(payload["roll_log"][0]["roll_value"], 8)
        self.assertEqual(payload["roll_log"][0]["player_id"], "p_witcher_1")
        self.assertEqual(payload["roll_log"][0]["qr_id"], "qr_a1_001")
        self.assertTrue(payload["check_id"])
        self.assertTrue(payload["roll_log"][0]["roll_id"])
        self.assertEqual(payload["scene_hp"], 8)
        self.assertEqual(payload["scene_hp_remaining"], 0)
        self.assertEqual(payload["player_scene_hp"], 7)
        self.assertIsNone(payload["cooldown_until"])

    def test_sync_reviews_arbitrary_high_client_modifier_exploit(self) -> None:
        settings = self._settings("pve_modifier_exploit")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=1,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            forged_modifier = {"source": "potion", "label": "client says +999", "value": 999}
            payload["modifiers"] = [forged_modifier]
            payload["roll_log"][0]["modifiers"] = [forged_modifier]
            payload["total"] = 1003
            payload["roll_log"][0]["total"] = 1003
            payload["result"] = "success"
            payload["outcome"] = "success"
            payload["roll_log"][0]["outcome"] = "success"
            response, event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=payload,
                sequence=1,
            )
            review = connection.execute(
                """
                SELECT reason
                FROM event_reviews
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()
            attempt_count = connection.execute(
                "SELECT COUNT(*) FROM pve_attempts WHERE qr_id = 'qr_a1_001'"
            ).fetchone()[0]
            state = connection.execute(
                "SELECT xp, gold FROM player_runtime_state WHERE player_id = 'p_witcher_1'"
            ).fetchone()

        self.assertEqual(response.results[0].status, "needs_master_review")
        self.assertEqual(review["reason"], "pve modifiers do not match server-derived modifiers")
        self.assertEqual(attempt_count, 0)
        self.assertEqual(state["xp"], 0)
        self.assertEqual(state["gold"], 20)

    def test_server_derives_modifiers_from_owned_item_potion_and_magic_effect(self) -> None:
        settings = self._settings("pve_server_modifiers")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            ensure_runtime_schema(connection)
            grant_asset_ownership(
                connection,
                owner_player_id="p_witcher_1",
                asset_type="item",
                asset_id="item_silver_dust",
                quantity=1,
                source="test_setup",
                source_ref_id="pve_server_modifiers",
            )
            connection.execute(
                """
                INSERT INTO potion_scene_usage (
                    usage_id, player_id, potion_id, scene_id, source, created_at
                )
                VALUES (
                    'usage_thunderbolt_qr_a1_001', 'p_witcher_1',
                    'potion_uncommon_thunderbolt', 'qr_a1_001',
                    'test_setup', '2026-06-02T08:59:00+00:00'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO sorceress_spell_casts (
                    cast_id, sorceress_id, spell_id, target_type, target_id,
                    cost_mana, effect_json, counterplay, visibility, status,
                    source, created_at
                )
                VALUES (
                    'cast_pve_boost', 'p_sorc_1', 'spell_boost_t1',
                    'player', 'p_witcher_1', 1,
                    '{"effect":"modifier_plus_1"}', 'visible_log',
                    'visible_log', 'active', 'test_setup',
                    '2026-06-02T08:58:00+00:00'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO magic_effects (
                    effect_id, cast_id, sorceress_id, spell_id, target_type, target_id,
                    effect_json, counterplay, visibility, status, created_at
                )
                VALUES (
                    'magic_effect_pve_boost', 'cast_pve_boost', 'p_sorc_1',
                    'spell_boost_t1', 'player', 'p_witcher_1',
                    '{"effect":"modifier_plus_1"}', 'visible_log',
                    'visible_log', 'active', '2026-06-02T08:58:00+00:00'
                )
                """
            )
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=3,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            response, _ = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=payload,
                sequence=1,
            )

        self.assertEqual(
            payload["modifiers"],
            [
                {"source": "item", "label": "item_silver_dust", "value": 2},
                {"source": "potion", "label": "potion_uncommon_thunderbolt", "value": 2},
                {"source": "magic", "label": "spell_boost_t1", "value": 1},
            ],
        )
        self.assertEqual(payload["server_modifier_total"], 5)
        self.assertEqual(payload["total"], 11)
        self.assertEqual(payload["result"], "success")
        self.assertEqual(response.results[0].status, "accepted")

    def test_sync_applies_failure_cooldown_only_for_failed_player_and_qr(self) -> None:
        settings = self._settings("pve_cooldown")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=1,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            payload["cooldown_until"] = "2099-01-01T00:00:00+00:00"
            before_sync = datetime.now(UTC)
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
                            event_type="pve_completed",
                            payload=payload,
                        )
                    ],
                ),
            )
            after_sync = datetime.now(UTC)
            cooldown = connection.execute(
                """
                SELECT player_id, qr_id, cooldown_until
                FROM pve_cooldowns
                WHERE player_id = 'p_witcher_1' AND qr_id = 'qr_a1_001'
                """
            ).fetchone()
            other_player_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM pve_cooldowns
                WHERE player_id = 'p_witcher_2' AND qr_id = 'qr_a1_001'
                """
            ).fetchone()[0]

        self.assertEqual(response.results[0].status, "accepted")
        stored_until = datetime.fromisoformat(cooldown["cooldown_until"])
        self.assertNotEqual(cooldown["cooldown_until"], "2099-01-01T00:00:00+00:00")
        self.assertGreaterEqual(stored_until, before_sync + timedelta(minutes=29))
        self.assertLessEqual(stored_until, after_sync + timedelta(minutes=31))
        self.assertEqual(other_player_count, 0)

    def test_resolve_pve_scene_cannot_force_success_from_failed_roll(self) -> None:
        settings = self._settings("pve_no_forced_success")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=1,
                result_override="success",
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )

        self.assertEqual(payload["result"], "failure")
        self.assertEqual(payload["roll_log"][0]["outcome"], "failure")

    def test_sync_sends_replay_mismatch_to_master_review(self) -> None:
        settings = self._settings("pve_review")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                modifiers=[{"source": "item", "value": 2}],
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            payload["total"] += 1
            event_id = f"evt_{uuid4().hex}"
            response = sync_events(
                connection,
                EventSyncRequest(
                    device_id="phone_wolf",
                    actor_id="p_witcher_1",
                    actor_type="player",
                    events=[
                        EventSyncEvent(
                            event_id=event_id,
                            client_sequence=1,
                            created_at="2026-06-02T09:00:00+00:00",
                            event_type="pve_completed",
                            payload=payload,
                        )
                    ],
                ),
            )
            review = connection.execute(
                """
                SELECT reason
                FROM event_reviews
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()

        self.assertEqual(response.results[0].status, "needs_master_review")
        self.assertEqual(review["reason"], "pve total does not match single_d20 replay")

    def test_sync_enforces_physical_presence_and_single_d20_replay_contract(self) -> None:
        settings = self._settings("pve_contract_edges")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            physical_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            physical_payload["physical_presence_confirmed"] = False
            physical_response, physical_event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=physical_payload,
                sequence=1,
            )

            invalid_roll_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 1, tzinfo=UTC),
            )
            invalid_roll_payload["roll"] = 21
            invalid_roll_payload["roll_log"][0]["roll"] = 21
            invalid_roll_response, invalid_roll_event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=invalid_roll_payload,
                sequence=2,
            )

            missing_modifiers_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 2, tzinfo=UTC),
            )
            missing_modifiers_payload.pop("modifiers")
            missing_modifiers_payload["roll_log"][0].pop("modifiers")
            missing_modifiers_response, missing_modifiers_event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=missing_modifiers_payload,
                sequence=3,
            )

            missing_cooldown_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=1,
                now=datetime(2026, 6, 2, 9, 3, tzinfo=UTC),
            )
            missing_cooldown_payload.pop("cooldown_until")
            missing_cooldown_response, missing_cooldown_event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=missing_cooldown_payload,
                sequence=4,
            )

            review_reasons = {
                row["event_id"]: row["reason"]
                for row in connection.execute(
                    """
                    SELECT event_id, reason
                    FROM event_reviews
                    WHERE event_id IN (?, ?, ?)
                    """,
                    (
                        physical_event_id,
                        invalid_roll_event_id,
                        missing_modifiers_event_id,
                    ),
                ).fetchall()
            }
            cooldown = connection.execute(
                """
                SELECT cooldown_until
                FROM pve_cooldowns
                WHERE player_id = 'p_witcher_1' AND qr_id = 'qr_a1_001'
                """
            ).fetchone()

        self.assertEqual(physical_response.results[0].status, "needs_master_review")
        self.assertEqual(
            review_reasons[physical_event_id],
            "physical presence confirmation required for physical QR scene",
        )
        self.assertEqual(invalid_roll_response.results[0].status, "needs_master_review")
        self.assertEqual(
            review_reasons[invalid_roll_event_id],
            "pve roll must be exactly one d20 in the 1-20 range",
        )
        self.assertEqual(missing_modifiers_response.results[0].status, "needs_master_review")
        self.assertEqual(
            review_reasons[missing_modifiers_event_id],
            "pve modifiers must be logged even when empty",
        )
        self.assertEqual(missing_cooldown_response.results[0].status, "accepted")
        self.assertNotIn(missing_cooldown_event_id, review_reasons)
        self.assertIsNotNone(cooldown["cooldown_until"])

    def test_partial_success_is_calculated_from_dc_margin(self) -> None:
        settings = self._settings("pve_partial_success")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            partial_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=7,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            partial_response, _ = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=partial_payload,
                sequence=1,
            )

            forged_partial = resolve_pve_scene(
                connection,
                player_id="p_witcher_2",
                qr_id="qr_a1_001",
                roll=1,
                now=datetime(2026, 6, 2, 9, 1, tzinfo=UTC),
            )
            forged_partial["result"] = "partial_success"
            forged_response, forged_event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_2",
                payload=forged_partial,
                sequence=1,
            )
            review = connection.execute(
                """
                SELECT reason
                FROM event_reviews
                WHERE event_id = ?
                """,
                (forged_event_id,),
            ).fetchone()

        self.assertEqual(partial_payload["result"], "partial_success")
        self.assertEqual(partial_response.results[0].status, "accepted")
        self.assertEqual(forged_response.results[0].status, "needs_master_review")
        self.assertEqual(review["reason"], "pve result does not match single_d20 replay")

    def test_unique_pve_object_is_consumed_once_with_pending_reward(self) -> None:
        settings = self._settings("pve_unique_consumed")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            first_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_006",
                roll=9,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            first_response, _ = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=first_payload,
                sequence=1,
            )
            consumed = connection.execute(
                """
                SELECT player_id, qr_id, scenario_id
                FROM pve_consumed_objects
                WHERE qr_id = 'qr_a1_006'
                """
            ).fetchone()

            second_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_2",
                qr_id="qr_a1_006",
                roll=9,
                now=datetime(2026, 6, 2, 9, 5, tzinfo=UTC),
            )
            second_response, second_event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_2",
                payload=second_payload,
                sequence=1,
            )
            review = connection.execute(
                """
                SELECT reason
                FROM event_reviews
                WHERE event_id = ?
                """,
                (second_event_id,),
            ).fetchone()
            approval_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM reward_approvals
                WHERE reward_id = 'reward_order_success'
                  AND status = 'pending_master_approval'
                """
            ).fetchone()[0]

        self.assertEqual(first_response.results[0].status, "pending_master_approval")
        self.assertEqual(consumed["player_id"], "p_witcher_1")
        self.assertEqual(consumed["scenario_id"], "scn_a1_006")
        self.assertEqual(approval_count, 1)
        self.assertEqual(second_response.results[0].status, "needs_master_review")
        self.assertEqual(review["reason"], "unique QR object already consumed")

    def test_future_act_server_sync_requires_physical_announcement_before_accepting_pve(self) -> None:
        settings = self._settings("pve_future_act_announcement")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            before_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a2_013",
                roll=12,
                unlock_source="server_sync",
                now=datetime(2026, 6, 2, 12, 0, tzinfo=UTC),
            )
            before_response, before_event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=before_payload,
                sequence=1,
            )
            start_act(
                connection,
                settings,
                "act2",
                operator="gm_pve",
                physical_announcement_state="announced",
                now=datetime(2026, 6, 2, 12, 30, tzinfo=UTC),
            )
            after_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a2_013",
                roll=12,
                unlock_source="server_sync",
                now=datetime(2026, 6, 2, 12, 35, tzinfo=UTC),
            )
            after_response, _ = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=after_payload,
                sequence=2,
            )
            before_review = connection.execute(
                """
                SELECT reason
                FROM event_reviews
                WHERE event_id = ?
                """,
                (before_event_id,),
            ).fetchone()
            accepted_attempt = connection.execute(
                """
                SELECT act_id, reward_status
                FROM pve_attempts
                WHERE qr_id = 'qr_a2_013'
                  AND player_id = 'p_witcher_1'
                """
            ).fetchone()

        self.assertEqual(before_response.results[0].status, "needs_master_review")
        self.assertEqual(
            before_review["reason"],
            "future act requires authoritative server sync after physical announcement",
        )
        self.assertEqual(after_response.results[0].status, "accepted")
        self.assertEqual(accepted_attempt["act_id"], "act2")
        self.assertEqual(accepted_attempt["reward_status"], "auto")

    def test_pve_replay_contract_reviews_die_stat_dc_and_result_mismatches(self) -> None:
        settings = self._settings("pve_replay_variants")
        self._import_valid_seed(settings)

        variants = [
            (
                "evt_bad_die",
                lambda payload: payload["roll_log"][0].update({"die": "d12"}),
                "pve check must log exactly one d20 and no reroll",
            ),
            (
                "evt_missing_roll_source",
                lambda payload: (
                    payload.pop("roll_source", None),
                    payload["roll_log"][0].pop("source", None),
                ),
                "pve roll source must be app_generated or explicit master/paper recovery",
            ),
            (
                "evt_bad_stat",
                lambda payload: payload.update({"stat": "Разум"}),
                "pve stat does not match scenario primary_stat",
            ),
            (
                "evt_bad_stat_value",
                lambda payload: payload.update({"stat_value": payload["stat_value"] + 1}),
                "pve stat_value does not match server player state",
            ),
            (
                "evt_bad_dc",
                lambda payload: payload["roll_log"][0].update({"dc": payload["dc"] + 1}),
                "pve dc does not match scenario",
            ),
            (
                "evt_bad_result",
                lambda payload: payload.update({"result": "failure"}),
                "pve result does not match single_d20 replay",
            ),
        ]

        with connect(settings) as connection:
            observed: dict[str, tuple[str, str]] = {}
            for sequence, (event_id, mutate, _expected_reason) in enumerate(variants, start=1):
                payload = resolve_pve_scene(
                    connection,
                    player_id="p_witcher_1",
                    qr_id="qr_a1_001",
                    roll=8,
                    now=datetime(2026, 6, 2, 9, sequence, tzinfo=UTC),
                )
                mutate(payload)
                response = sync_events(
                    connection,
                    EventSyncRequest(
                        device_id=f"phone_replay_{sequence}",
                        actor_id="p_witcher_1",
                        actor_type="player",
                        events=[
                            EventSyncEvent(
                                event_id=event_id,
                                client_sequence=1,
                                created_at=f"2026-06-02T09:{sequence:02d}:00+00:00",
                                event_type="pve_completed",
                                payload=payload,
                            )
                        ],
                    ),
                )
                review = connection.execute(
                    """
                    SELECT reason
                    FROM event_reviews
                    WHERE event_id = ?
                    """,
                    (event_id,),
                ).fetchone()
                observed[event_id] = (response.results[0].status, review["reason"])

        for event_id, _mutate, expected_reason in variants:
            self.assertEqual(observed[event_id], ("needs_master_review", expected_reason))

    def test_sync_reviews_duplicate_or_modified_app_generated_roll_for_same_check(self) -> None:
        settings = self._settings("pve_immutable_roll")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            first_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            first_response, _ = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=first_payload,
                sequence=1,
            )

            duplicate_payload = json.loads(json.dumps(first_payload))
            duplicate_response, duplicate_event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=duplicate_payload,
                sequence=2,
            )

            changed_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=9,
                check_id=first_payload["check_id"],
                now=datetime(2026, 6, 2, 9, 2, tzinfo=UTC),
            )
            changed_response, changed_event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=changed_payload,
                sequence=3,
            )
            reviews = {
                row["event_id"]: row["reason"]
                for row in connection.execute(
                    """
                    SELECT event_id, reason
                    FROM event_reviews
                    WHERE event_id IN (?, ?)
                    """,
                    (duplicate_event_id, changed_event_id),
                ).fetchall()
            }

        self.assertEqual(first_response.results[0].status, "accepted")
        self.assertEqual(duplicate_response.results[0].status, "needs_master_review")
        self.assertEqual(
            reviews[duplicate_event_id],
            "duplicate pve roll for same check_id requires master review",
        )
        self.assertEqual(changed_response.results[0].status, "needs_master_review")
        self.assertEqual(
            reviews[changed_event_id],
            "pve check_id already has a different d20 roll and needs master review",
        )

    def test_player_pve_completion_cannot_mask_roll_as_paper_recovery(self) -> None:
        settings = self._settings("pve_roll_source_auth")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                roll_source="paper_recovered",
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            response, event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=payload,
                sequence=1,
            )
            review = connection.execute(
                """
                SELECT reason
                FROM event_reviews
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()

        self.assertEqual(response.results[0].status, "needs_master_review")
        self.assertEqual(
            review["reason"],
            "master/paper recovered pve roll source requires master auth context",
        )

    def test_auto_rewards_apply_xp_level_gold_and_plus_one_stat(self) -> None:
        settings = self._settings("pve_rewards")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            events = []
            for sequence in range(1, 4):
                payload = resolve_pve_scene(
                    connection,
                    player_id="p_witcher_1",
                    qr_id="qr_a1_001",
                    roll=8,
                    now=datetime(2026, 6, 2, 9, sequence, tzinfo=UTC),
                )
                events.append(
                    EventSyncEvent(
                        event_id=f"evt_{uuid4().hex}",
                        client_sequence=sequence,
                        created_at=f"2026-06-02T09:0{sequence}:00+00:00",
                        event_type="pve_completed",
                        payload=payload,
                    )
                )
            response = sync_events(
                connection,
                EventSyncRequest(
                    device_id="phone_wolf",
                    actor_id="p_witcher_1",
                    actor_type="player",
                    events=events,
                ),
            )
            state = connection.execute(
                """
                SELECT xp, level, gold, stats_json
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()

        self.assertEqual([result.status for result in response.results], ["accepted"] * 3)
        self.assertEqual(state["xp"], 2)
        self.assertEqual(state["level"], 2)
        self.assertEqual(state["gold"], 50)
        self.assertEqual(json.loads(state["stats_json"])["Сила"], 4)

    def test_auto_reward_spends_xp_for_level_ups(self) -> None:
        settings = self._settings("pve_reward_spend_xp")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            connection.execute(
                "UPDATE rewards SET xp = 50, gold = 30 WHERE reward_id = 'reward_pve_t1'"
            )
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            response, _ = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=payload,
                sequence=1,
            )
            state = connection.execute(
                """
                SELECT xp, level, gold
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()

        self.assertEqual(response.results[0].status, "accepted")
        self.assertEqual(state["xp"], 15)
        self.assertEqual(state["level"], 3)
        self.assertEqual(state["gold"], 50)

    def test_missing_client_reward_id_uses_scenario_bound_auto_reward(self) -> None:
        settings = self._settings("pve_scenario_auto_reward")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            payload.pop("reward_id")
            response, _ = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=payload,
                sequence=1,
            )
            state = connection.execute(
                """
                SELECT xp, gold
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()
            attempt = connection.execute(
                """
                SELECT reward_id, reward_status
                FROM pve_attempts
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()

        self.assertEqual(response.results[0].status, "accepted")
        self.assertEqual(attempt["reward_id"], "reward_pve_t1")
        self.assertEqual(attempt["reward_status"], "auto")
        self.assertEqual(state["xp"], 4)
        self.assertEqual(state["gold"], 30)

    def test_scenario_bound_pending_reward_creates_approval_without_auto_apply(self) -> None:
        settings = self._settings("pve_scenario_pending_reward")
        self._import_valid_seed(settings)

        with connect(settings) as connection:
            payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_006",
                roll=9,
                now=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
            )
            payload.pop("reward_id")
            first_response, first_event_id = self._sync_pve_payload(
                connection,
                actor_id="p_witcher_1",
                payload=payload,
                sequence=1,
            )
            duplicate_response = sync_events(
                connection,
                EventSyncRequest(
                    device_id="phone_wolf",
                    actor_id="p_witcher_1",
                    actor_type="player",
                    events=[
                        EventSyncEvent(
                            event_id=first_event_id,
                            client_sequence=2,
                            created_at="2026-06-02T09:02:00+00:00",
                            event_type="pve_completed",
                            payload=payload,
                        )
                    ],
                ),
            )
            attempt = connection.execute(
                """
                SELECT reward_id, reward_status
                FROM pve_attempts
                WHERE player_id = 'p_witcher_1'
                  AND qr_id = 'qr_a1_006'
                """
            ).fetchone()
            state = connection.execute(
                """
                SELECT xp, level, gold
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()
            approval_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM reward_approvals
                WHERE reward_id = 'reward_order_success'
                  AND status = 'pending_master_approval'
                """
            ).fetchone()[0]
            lock_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM asset_locks
                WHERE asset_type = 'item'
                  AND asset_id = 'item_order_seal'
                  AND status = 'active'
                """
            ).fetchone()[0]
            ownership_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM asset_ownership
                WHERE owner_player_id = 'p_witcher_1'
                  AND asset_type = 'item'
                  AND asset_id = 'item_order_seal'
                  AND status = 'active'
                """
            ).fetchone()[0]

        self.assertEqual(first_response.results[0].status, "pending_master_approval")
        self.assertEqual(duplicate_response.results[0].status, "pending_master_approval")
        self.assertEqual(duplicate_response.results[0].reason, "reward requires master approval")
        self.assertEqual(attempt["reward_id"], "reward_order_success")
        self.assertEqual(attempt["reward_status"], "pending_master_approval")
        self.assertEqual(state["xp"], 0)
        self.assertEqual(state["level"], 1)
        self.assertEqual(state["gold"], 20)
        self.assertEqual(approval_count, 1)
        self.assertEqual(lock_count, 1)
        self.assertEqual(ownership_count, 0)

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def _import_valid_seed(self, settings: Settings) -> None:
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

    def _sync_pve_payload(
        self,
        connection,
        *,
        actor_id: str,
        payload: dict,
        sequence: int,
    ):
        event_id = f"evt_{uuid4().hex}"
        roll_log = payload.get("roll_log", [])
        roll_created_at = (
            roll_log[0].get("created_at")
            if isinstance(roll_log, list) and roll_log and isinstance(roll_log[0], dict)
            else None
        )
        response = sync_events(
            connection,
            EventSyncRequest(
                device_id=f"phone_{actor_id}",
                actor_id=actor_id,
                actor_type="player",
                events=[
                    EventSyncEvent(
                        event_id=event_id,
                        client_sequence=sequence,
                        created_at=str(
                            payload.get("completed_at")
                            or payload.get("client_recorded_at")
                            or roll_created_at
                            or f"2026-06-02T09:{sequence:02d}:00+00:00"
                        ),
                        event_type="pve_completed",
                        payload=payload,
                    )
                ],
            ),
        )
        return response, event_id


if __name__ == "__main__":
    unittest.main()
