from __future__ import annotations

import json
import unittest
from uuid import uuid4

from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect, init_database
from backend.witcher_larp.event_models import EventSyncEvent, EventSyncRequest
from backend.witcher_larp.event_service import sync_events
from backend.witcher_larp.import_service import import_seed_pack


MOBILE_ROOT = PROJECT_ROOT / "mobile"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"
TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
SECRET_VALUES = (
    "LC-RIVER-8YM4",
    "SC-MOON-4AD8",
    "WC-CAT-1HN8",
    "LORD-NORTH-R8K4",
    "MASTER-KING-4QZ8",
    "UNLOCK-A2-7GQ4",
)

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


class MobileShellContractTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_godot_project_declares_main_scene_and_autoload(self) -> None:
        project = (MOBILE_ROOT / "project.godot").read_text(encoding="utf-8")

        self.assertIn('run/main_scene="res://scenes/main.tscn"', project)
        self.assertIn('AppState="*res://scripts/app_state.gd"', project)
        self.assertIn('config/features=PackedStringArray("4.6", "Mobile")', project)

    def test_mobile_scripts_declare_offline_storage_files_for_godot_smoke(self) -> None:
        app_state = (MOBILE_ROOT / "scripts" / "app_state.gd").read_text(
            encoding="utf-8"
        )

        for path in (
            "user://settings.json",
            "user://session.json",
            "user://snapshot.json",
            "user://qr_attempts.json",
            "user://qr_event_context.json",
            "user://pve_cooldowns.json",
            "user://event_queue.json",
            "user://sync_status.json",
        ):
            self.assertIn(path, app_state)

    def test_mobile_player_facing_start_is_code_login_scene(self) -> None:
        main = (MOBILE_ROOT / "scripts" / "main.gd").read_text(encoding="utf-8")
        login_scene = (MOBILE_ROOT / "scenes" / "player_login.tscn").read_text(
            encoding="utf-8"
        )
        login_script = (MOBILE_ROOT / "scripts" / "player_login_view.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn('preload("res://scenes/player_login.tscn")', main)
        self.assertIn("login_requested", login_script)
        self.assertIn("offline_login_requested", login_script)
        self.assertIn("Код игрока", login_scene)
        self.assertIn("PlayerCodeInput", login_scene)
        self.assertIn("LoginButton", login_scene)
        self.assertIn("DiagnosticsPanel", login_scene)
        self.assertIn("visible = false", login_scene)
        self.assertIn('role_type == "witcher"', main)
        self.assertIn('role_type == "sorceress"', main)
        self.assertNotIn("Offline-first player shell", main + login_scene)
        self.assertNotIn("Login + Snapshot", main + login_scene)

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_mobile_login_snapshot_and_sync_queue_use_runtime_contracts(self) -> None:
        settings = self._settings("mobile_runtime_contract")
        report = self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        login = client.post(
            "/api/auth/player-code",
            json={"player_code": "WC-WOLF-6GF4", "device_id": "phone-wolf"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        login_payload = login.json()
        self.assertEqual(login_payload["player_id"], "p_witcher_1")
        self.assertEqual(login_payload["role_type"], "witcher")
        self.assertEqual(login_payload["device_id"], "phone-wolf")
        self.assertIn("mobile:snapshot", login_payload["permissions"])
        self.assertEqual(login_payload["snapshot_path"], "/api/content/snapshot")
        self.assertNotIn("reputation", login_payload["player"])
        self.assertNotIn("value", login_payload["player"].get("reputation_state", {}))

        snapshot = client.get(
            "/api/content/snapshot",
            params={"player_code": "WC-WOLF-6GF4"},
        )
        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        snapshot_payload = snapshot.json()
        self.assertEqual(snapshot_payload["snapshot_version"], report.snapshot_version)
        self.assertEqual(snapshot_payload["visibility"]["scope"], "player")
        self.assertEqual(snapshot_payload["player"]["player_id"], "p_witcher_1")
        self.assertEqual(snapshot_payload["players"], [snapshot_payload["player"]])
        player_reputation = snapshot_payload["player"]["reputation_state"]
        self.assertNotIn("reputation", snapshot_payload["player"])
        self.assertNotIn("value", player_reputation)
        self.assertNotIn("change_log", player_reputation)
        self.assertEqual(player_reputation["state_label"], "Neutral")
        self.assertEqual(player_reputation["player_descriptor"], "uncertain")
        self.assertEqual(player_reputation["value_visibility"], "hidden_from_player")
        self.assertNotIn("player_codes", snapshot_payload)
        self.assertNotIn("role_tokens", snapshot_payload)
        self.assertTrue(
            all(row["code"] is None for row in snapshot_payload["act_unlock_codes"])
        )
        for secret in SECRET_VALUES:
            self.assertNotIn(secret, login.text + snapshot.text)

        qr_review = self._sync_event(
            client,
            device_id="phone-wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            event_type="qr_attempt",
            payload={
                "qr_id": "qr_a1_006",
                "source": "qr_scan",
                "physical_presence_confirmed": False,
                "local_status": "needs_master_review",
                "review_reason": "honesty_violation_suspected",
            },
            sequence=1,
        )
        result = qr_review["results"][0]
        self.assertEqual(result["status"], "needs_master_review")
        self.assertEqual(result["reason"], "honesty_violation_suspected")

        with connect(settings) as connection:
            review = connection.execute(
                """
                SELECT reason
                FROM event_reviews
                WHERE event_id = ?
                """,
                (result["event_id"],),
            ).fetchone()
        self.assertEqual(review["reason"], "honesty_violation_suspected")

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_mobile_sync_rejects_early_unlock_and_forged_pve_payloads(self) -> None:
        settings = self._settings("mobile_negative_contract")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        early_unlock = self._sync_event(
            client,
            device_id="phone-wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            event_type="act_unlocked_offline",
            payload={"act_id": "act2", "code": "UNLOCK-A2-7GQ4"},
            sequence=1,
        )
        self.assertEqual(early_unlock["results"][0]["status"], "rejected")
        self.assertEqual(
            early_unlock["results"][0]["reason"],
            "act unlock code has not been revealed by masters",
        )

        forged_pve = self._sync_event(
            client,
            device_id="phone-wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            event_type="pve_completed",
            payload={
                "scenario_id": "scn_a1_001",
                "qr_id": "qr_a1_001",
                "act_id": "act1",
                "unlock_source": "act1_default",
                "result": "success",
                "reward_id": "reward_pve_t1",
                "physical_presence_confirmed": True,
            },
            sequence=2,
        )
        self.assertEqual(forged_pve["results"][0]["status"], "needs_master_review")
        self.assertEqual(
            forged_pve["results"][0]["reason"],
            "pve completion must include exactly one replayable d20 roll_log entry",
        )

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_mobile_sync_uses_authenticated_actor_not_payload_identity(self) -> None:
        settings = self._settings("mobile_auth_context")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))
        forged_event_id = f"mobile_{uuid4().hex}"
        paper_event_id = f"mobile_{uuid4().hex}"

        forged_actor = client.post(
            "/api/events/sync",
            headers={"X-Player-Code": "WC-WOLF-6GF4"},
            json={
                "device_id": "phone-wolf",
                "actor_id": "p_witcher_2",
                "actor_type": "master",
                "events": [
                    {
                        "event_id": forged_event_id,
                        "client_sequence": 1,
                        "created_at": "2026-06-02T09:00:00+00:00",
                        "event_type": "qr_scene_started",
                        "payload": {
                            "qr_id": "qr_a1_001",
                            "local_status": "accepted",
                        },
                    }
                ],
            },
        )
        forged_master_event = client.post(
            "/api/events/sync",
            headers={"X-Player-Code": "WC-WOLF-6GF4"},
            json={
                "device_id": "phone-wolf",
                "actor_id": "npc_king",
                "actor_type": "master",
                "events": [
                    {
                        "event_id": paper_event_id,
                        "client_sequence": 2,
                        "created_at": "2026-06-02T09:01:00+00:00",
                        "event_type": "paper_recovered",
                        "payload": {
                            "paper_form_id": "mobile-paper-forged",
                            "source_form_type": "paper_pve_result",
                            "operator": "gm_forged",
                            "timestamp": "2026-06-02T09:01:00+00:00",
                            "reason": "forged mobile paper event",
                        },
                    }
                ],
            },
        )

        self.assertEqual(forged_actor.status_code, 200, forged_actor.text)
        self.assertEqual(forged_actor.json()["results"][0]["status"], "accepted")
        self.assertEqual(forged_master_event.status_code, 200, forged_master_event.text)
        master_only = forged_master_event.json()["results"][0]
        self.assertEqual(master_only["status"], "rejected")
        self.assertEqual(master_only["reason"], "paper_recovered requires master auth context")

        with connect(settings) as connection:
            forged_stored = connection.execute(
                """
                SELECT actor_id, actor_type, status
                FROM events
                WHERE event_id = ?
                """,
                (forged_event_id,),
            ).fetchone()
            rejected_stored = connection.execute(
                """
                SELECT actor_id, actor_type, status
                FROM events
                WHERE event_id = ?
                """,
                (paper_event_id,),
            ).fetchone()
            audit = connection.execute(
                """
                SELECT status, reason, severity
                FROM event_reviews
                WHERE event_id = ?
                """,
                (paper_event_id,),
            ).fetchone()

        self.assertEqual(dict(forged_stored), {
            "actor_id": "p_witcher_1",
            "actor_type": "witcher",
            "status": "accepted",
        })
        self.assertEqual(dict(rejected_stored), {
            "actor_id": "p_witcher_1",
            "actor_type": "witcher",
            "status": "rejected",
        })
        self.assertEqual(audit["status"], "rejected")
        self.assertEqual(audit["reason"], "paper_recovered requires master auth context")
        self.assertEqual(audit["severity"], "P0")

    @unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
    def test_mobile_qr_rate_limit_and_pve_cooldown_are_server_authoritative(self) -> None:
        settings = self._settings("mobile_qr_pve_authority")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        last_lookup = None
        for attempt in range(5):
            last_lookup = client.post(
                "/api/qr/lookup",
                headers={"X-Player-Code": "WC-WOLF-6GF4"},
                json={
                    "code": f"QR-A1-BAD{attempt}",
                    "device_id": "phone-wolf",
                    "source": "manual_id",
                    "physical_presence_confirmed": True,
                },
            )
            self.assertEqual(last_lookup.status_code, 200, last_lookup.text)
        assert last_lookup is not None
        rate_limited = last_lookup.json()
        self.assertEqual(rate_limited["status"], "needs_master_review")
        self.assertEqual(rate_limited["reason"], "manual_rate_limit")
        self.assertEqual(rate_limited["event_context"]["review_reason"], "manual_rate_limit")

        with connect(settings) as connection:
            pve_failure = self._resolve_pve_failure_payload(connection)
        pve_failure["cooldown_until"] = "2099-01-01T00:00:00+00:00"
        sync = self._sync_event(
            client,
            device_id="phone-wolf",
            actor_id="p_witcher_1",
            actor_type="player",
            event_type="pve_completed",
            payload=pve_failure,
            sequence=1,
        )
        self.assertEqual(sync["results"][0]["status"], "accepted")

        with connect(settings) as connection:
            cooldown = connection.execute(
                """
                SELECT cooldown_until
                FROM pve_cooldowns
                WHERE player_id = 'p_witcher_1' AND qr_id = 'qr_a1_002'
                """
            ).fetchone()
        self.assertIsNotNone(cooldown["cooldown_until"])
        self.assertNotEqual(cooldown["cooldown_until"], "2099-01-01T00:00:00+00:00")

    def test_mobile_scripts_define_qr_manual_runtime_contract(self) -> None:
        app_state = (MOBILE_ROOT / "scripts" / "app_state.gd").read_text(
            encoding="utf-8"
        )
        main = (MOBILE_ROOT / "scripts" / "main.gd").read_text(encoding="utf-8")

        for contract_token in (
            "_on_qr_scan_text_pressed",
            "_on_manual_qr_pressed",
            "_on_confirm_qr_presence_pressed",
            "qr_scene_started",
            "qr_attempt",
            "qr_mode",
            "consumption_rule",
            "physical_presence_confirmed",
            "honesty_violation_suspected",
            "manual_rate_limit",
            "blocked_future_act",
            "cooldown_active",
            "success_take_physical_qr_failure_leave_it",
            "_on_unlock_act_pressed",
            "offline_unlock_act",
            "act_unlocked_offline",
            "master_unlock_code",
            "act_unlock_state",
            "act_unlock_codes",
            "code_sha256",
            "unlocked_acts",
        ):
            self.assertIn(contract_token, app_state + main)

    def test_mobile_scripts_define_event_queue_sync_contract(self) -> None:
        app_state = (MOBILE_ROOT / "scripts" / "app_state.gd").read_text(
            encoding="utf-8"
        )
        main = (MOBILE_ROOT / "scripts" / "main.gd").read_text(encoding="utf-8")
        combined = app_state + main

        for contract_token in (
            "event_queue",
            "sync_status",
            "event_id",
            "client_sequence",
            "created_at",
            "event_type",
            "payload",
            "local_status",
            "offline",
            "pending",
            "synced",
            "sync_error",
            "needs_master_review",
            "pve_completed",
            "roll_log",
            "single_d20",
            "scene_hp",
            "player_scene_hp",
            "cooldown_until",
            "pending_master_approval",
            "prepare_sync_request",
            "apply_sync_response",
            "mark_sync_batch_error",
            "_on_sync_queue_pressed",
            "_on_pve_check_pressed",
            "_record_pve_check",
            "_event_belongs_to_current_player",
            "wrong_actor_queue",
            "another player/session",
        ):
            self.assertIn(contract_token, combined)

        self.assertIn('"device_id": str(settings.get("device_id", ""))', app_state)
        self.assertIn('"actor_id": player_id', app_state)
        self.assertIn('"actor_type": "player"', app_state)
        self.assertIn('"events": request_events', app_state)
        self.assertIn("X-Player-Code", main)
        self.assertIn('server_status == "duplicate"', app_state)
        self.assertIn("_ensure_app_generated_pve_roll", app_state)
        self.assertIn("_calculate_pve_outcome", app_state)
        self.assertNotIn("suggested_pve_roll_for_result", combined)

    def test_mobile_character_ui_uses_descriptive_reputation_only(self) -> None:
        app_state = (MOBILE_ROOT / "scripts" / "app_state.gd").read_text(
            encoding="utf-8"
        )
        journal = (MOBILE_ROOT / "scripts" / "witcher_journal_view.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn("func player_reputation_display(player: Dictionary)", app_state)
        self.assertIn("reputation_state", app_state)
        self.assertIn("AppState.player_reputation_display(player)", journal)
        self.assertIn("Репутация: %s", journal)
        self.assertNotIn("Reputation: %d", journal)
        self.assertNotIn('player.get("reputation"', journal)

    def test_mobile_journal_xp_bar_uses_current_level_progress(self) -> None:
        journal = (MOBILE_ROOT / "scripts" / "witcher_journal_view.gd").read_text(
            encoding="utf-8"
        )

        self.assertIn("func _xp_window_for_player(", journal)
        self.assertIn("func _xp_required_for_next_level(", journal)
        self.assertIn("func _xp_costs_from_rules() -> Array:", journal)
        self.assertIn('"progress": int(max(0, xp_current))', journal)
        self.assertIn('"required": next_level_cost', journal)
        self.assertIn("_set_xp_bar(xp_progress, xp_required)", journal)
        self.assertIn("if xp_current > 0:", journal)
        self.assertNotIn("_set_xp_bar(xp_current, xp_target)", journal)

    def test_mobile_scripts_queue_qr_presence_and_review_contexts(self) -> None:
        app_state = (MOBILE_ROOT / "scripts" / "app_state.gd").read_text(
            encoding="utf-8"
        )

        for contract_token in (
            "_queue_qr_context_for_sync(context)",
            "func _queue_qr_context_for_sync(context: Dictionary) -> Dictionary:",
            "func _should_queue_qr_context(context: Dictionary) -> bool:",
            "func _qr_sync_payload(context: Dictionary) -> Dictionary:",
            "queued_event_ids",
            '"qr_context_id"',
            '"snapshot_version"',
            '"requires_master_review"',
            '"last_queued_event_id"',
            '"last_queued_event_type"',
            "return local_status == \"needs_master_review\"",
            'event_type == "qr_scene_started"',
            "_event_by_id(existing_event_id)",
        ):
            self.assertIn(contract_token, app_state)

        self.assertGreaterEqual(
            app_state.count("_queue_qr_context_for_sync(context)"),
            3,
        )

    def test_mobile_queued_qr_context_batch_syncs_presence_and_reviews(self) -> None:
        settings = self._settings("mobile_qr_context_queue")
        init_database(settings)
        with connect(settings) as connection:
            response = sync_events(
                connection,
                EventSyncRequest(
                    device_id="phone-wolf",
                    actor_id="p_witcher_1",
                    actor_type="player",
                    events=[
                        EventSyncEvent(
                            event_id="mobile_qr_presence_evt",
                            client_sequence=1,
                            created_at="2026-06-02T09:00:00+00:00",
                            event_type="qr_scene_started",
                            payload={
                                "qr_context_id": "qr-context-presence",
                                "qr_id": "qr_a1_001",
                                "manual_code": "QR-A1-K7Q2",
                                "source": "manual_id",
                                "local_status": "ready",
                                "physical_presence_confirmed": True,
                            },
                        ),
                        EventSyncEvent(
                            event_id="mobile_qr_honesty_evt",
                            client_sequence=2,
                            created_at="2026-06-02T09:01:00+00:00",
                            event_type="qr_attempt",
                            payload={
                                "qr_context_id": "qr-context-honesty",
                                "qr_id": "qr_a1_006",
                                "source": "qr_scan",
                                "local_status": "needs_master_review",
                                "review_reason": "honesty_violation_suspected",
                                "requires_master_review": True,
                                "physical_presence_confirmed": False,
                            },
                        ),
                        EventSyncEvent(
                            event_id="mobile_qr_manual_rate_evt",
                            client_sequence=3,
                            created_at="2026-06-02T09:02:00+00:00",
                            event_type="qr_attempt",
                            payload={
                                "qr_context_id": "qr-context-manual-rate",
                                "normalized_code": "NO-SUCH-QR",
                                "source": "manual_id",
                                "local_status": "needs_master_review",
                                "review_reason": "manual_rate_limit",
                                "requires_master_review": True,
                            },
                        ),
                    ],
                ),
            )
            review_reasons = [
                row["reason"]
                for row in connection.execute(
                    """
                    SELECT reason
                    FROM event_reviews
                    ORDER BY review_id
                    """
                ).fetchall()
            ]
            mobile_sources = {
                row["source"]
                for row in connection.execute(
                    """
                    SELECT source
                    FROM event_log
                    WHERE event_type IN ('qr_attempt', 'qr_scene_started')
                    """
                ).fetchall()
            }
            sync_state = connection.execute(
                """
                SELECT last_event_sequence
                FROM client_sync_state
                WHERE client_id = 'phone-wolf'
                """
            ).fetchone()

        self.assertEqual(
            [result.status for result in response.results],
            ["accepted", "needs_master_review", "needs_master_review"],
        )
        self.assertEqual(review_reasons, ["honesty_violation_suspected", "manual_rate_limit"])
        self.assertEqual(mobile_sources, {"mobile_qr"})
        self.assertEqual(sync_state["last_event_sequence"], 3)

    def test_mobile_pve_roll_ui_generates_immutable_app_roll(self) -> None:
        app_state = (MOBILE_ROOT / "scripts" / "app_state.gd").read_text(
            encoding="utf-8"
        )
        main = (MOBILE_ROOT / "scripts" / "main.gd").read_text(encoding="utf-8")
        combined = app_state + main

        self.assertIn("func _on_pve_check_pressed() -> void:", main)
        self.assertIn("func _record_pve_check() -> void:", main)
        self.assertNotIn("_pve_roll_input", main)
        self.assertNotIn("d20 roll 1-20", main)
        self.assertNotIn("_build_roll_log_from_input", main)
        for token in (
            "_generate_d20_roll",
            "rng.randi_range(1, 20)",
            '"source": "app_generated"',
            '"roll_id"',
            '"roll_value"',
            '"check_id"',
            '"created_at"',
            '"player_id"',
            '"qr_id"',
            '"scenario_id"',
            'context["pve_roll_log"] = [roll_entry]',
            "_save_qr_runtime_context(context)",
            '"pve_result_event_id"',
        ):
            self.assertIn(token, combined)

    def test_mobile_pve_roll_state_survives_restart_and_sync_retry_contract(self) -> None:
        app_state = (MOBILE_ROOT / "scripts" / "app_state.gd").read_text(
            encoding="utf-8"
        )

        for token in (
            "QR_EVENT_CONTEXT_PATH",
            "last_qr_event_context = _load_json(QR_EVENT_CONTEXT_PATH, {})",
            'context["pve_roll_log"] = [roll_entry]',
            "_save_qr_runtime_context(context)",
            'context.has("pve_result_event_id")',
            'event["local_status"] = "sync_error"',
            'SYNC_RETRY_STATUSES := ["offline", "pending", "sync_error"]',
        ):
            self.assertIn(token, app_state)

    def test_bundled_snapshot_is_public_artifact_without_player_codes(self) -> None:
        snapshot = json.loads(
            (MOBILE_ROOT / "assets" / "bundled_snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        readme = (MOBILE_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertEqual(snapshot["snapshot_version"], "seed-dev-2026-05-30")
        self.assertEqual(snapshot["profile"]["playable_roles"], 13)
        self.assertEqual(snapshot["profile"]["npc_masters"], 2)
        self.assertIn("non-playable dev fixture", snapshot["content_summary"]["purpose"])
        self.assertEqual(snapshot["visibility"]["scope"], "mobile_public_artifact")
        self.assertEqual(snapshot["visibility"]["player_codes"], "server_only")
        self.assertEqual(snapshot["visibility"]["role_tokens"], "server_only")
        self.assertEqual(snapshot["players"], [])
        self.assertNotIn("player_codes", snapshot)
        self.assertNotIn("role_tokens", snapshot)
        self.assertIn("non-playable dev fixture", readme)
        self.assertNotIn("mirrors the current\n  seed player codes", readme)

    def test_export_presets_document_mobile_smoke_paths_and_permissions(self) -> None:
        presets = (MOBILE_ROOT / "export_presets.cfg").read_text(encoding="utf-8")
        readme = (MOBILE_ROOT / "README.md").read_text(encoding="utf-8")
        technical_plan = (
            PROJECT_ROOT / "docs" / "app-technical-plan-v0.1.md"
        ).read_text(encoding="utf-8")

        self.assertIn('name="Android Debug APK"', presets)
        self.assertIn(
            'export_path="builds/android/witcher_larp_mobile_debug.apk"', presets
        )
        self.assertIn("permissions/internet=true", presets)
        self.assertIn('name="iOS Free Provisioning"', presets)
        self.assertIn('export_path="builds/ios/witcher_larp_mobile_ios.zip"', presets)
        self.assertIn("privacy/local_network_usage_description", presets)
        self.assertIn("Android export smoke", readme)
        self.assertIn("iOS export smoke", readme)
        self.assertIn("Native camera decoding still needs a", readme)
        self.assertIn("target-device plugin smoke before release", readme)
        self.assertIn("Camera permission is off in this shell", readme)
        self.assertIn("launch-risk: qr-camera", technical_plan)
        self.assertIn("TASK-047`/`TASK-058`/`TASK-050", technical_plan)

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def _import_valid_seed(self, settings: Settings):
        report = import_seed_pack(
            settings,
            manifest_path=FIXTURE_MANIFEST,
            snapshot_dir=None,
        )
        self.assertEqual(report.status, "success")
        return report

    def _resolve_pve_failure_payload(self, connection) -> dict[str, object]:
        from backend.witcher_larp.pve_runtime import resolve_pve_scene

        return resolve_pve_scene(
            connection,
            player_id="p_witcher_1",
            qr_id="qr_a1_002",
            roll=1,
        )

    def _sync_event(
        self,
        client: TestClient,
        *,
        device_id: str,
        actor_id: str,
        actor_type: str,
        event_type: str,
        payload: dict[str, object],
        sequence: int,
    ) -> dict[str, object]:
        response = client.post(
            "/api/events/sync",
            headers=self._auth_headers_for(actor_id, actor_type),
            json={
                "device_id": device_id,
                "actor_id": actor_id,
                "actor_type": actor_type,
                "events": [
                    {
                        "event_id": f"mobile_{uuid4().hex}",
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

    def _auth_headers_for(self, actor_id: str, actor_type: str) -> dict[str, str]:
        if actor_type in {"master", "npc_master"}:
            return {"X-Role-Token": "MASTER-KING-4QZ8"}
        player_codes = {
            "p_witcher_1": "WC-WOLF-6GF4",
            "p_lord_1": "LC-NORTH-7QK2",
            "p_sorc_1": "SC-MOON-4AD8",
        }
        return {"X-Player-Code": player_codes.get(actor_id, "WC-WOLF-6GF4")}


if __name__ == "__main__":
    unittest.main()
