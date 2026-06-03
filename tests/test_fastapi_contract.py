from __future__ import annotations

import hashlib
import json
import unittest
from uuid import uuid4

from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.pve_runtime import resolve_pve_scene

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


SECRET_VALUES = (
    "LC-RIVER-8YM4",
    "SC-MOON-4AD8",
    "WC-CAT-1HN8",
    "LORD-NORTH-R8K4",
    "MASTER-KING-4QZ8",
)
MASTER_HEADERS = {"X-Role-Token": "MASTER-KING-4QZ8"}


@unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
class FastApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        (PROJECT_ROOT / ".test-data").mkdir(exist_ok=True)

    def test_health_endpoint_reports_database_status(self) -> None:
        database_path = (
            PROJECT_ROOT / ".test-data" / f"fastapi_{uuid4().hex}.db"
        )
        settings = Settings(database_path=database_path)
        client = TestClient(create_app(settings))

        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["database"]["status"], "ok")
        self.assertEqual(payload["database"]["schema_version"], 1)

    def test_static_entrypoints_auth_and_qr_errors_are_explicit(self) -> None:
        settings = self._settings("fastapi_entry_auth_errors")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        root = client.get("/", follow_redirects=False)
        lord_panel = client.get("/lord")
        invalid_role = client.post("/api/auth/role-token", json={"token": "NO-SUCH-TOKEN"})
        valid_role = client.post("/api/auth/role-token", json={"token": "LORD-NORTH-R8K4"})
        empty_player_code = client.post(
            "/api/auth/player-code",
            json={"player_code": "   ", "device_id": "phone-empty"},
        )
        blank_qr = client.post(
            "/api/qr/lookup",
            json={
                "code": " ",
                "player_id": "p_witcher_1",
                "device_id": "phone-wolf",
            },
        )

        self.assertEqual(root.status_code, 307)
        self.assertEqual(root.headers["location"], "/lord")
        self.assertEqual(lord_panel.status_code, 200)
        self.assertEqual(invalid_role.status_code, 401)
        self.assertEqual(valid_role.status_code, 200)
        self.assertEqual(valid_role.json()["owner_id"], "p_lord_1")
        self.assertEqual(empty_player_code.status_code, 400)
        self.assertEqual(blank_qr.status_code, 400)

    def test_qr_lookup_reports_missing_imported_qr_content(self) -> None:
        settings = self._settings("fastapi_no_qr_content")
        client = TestClient(create_app(settings))

        response = client.post(
            "/api/qr/lookup",
            json={
                "code": "QR-A1-K7Q2",
                "player_id": "p_witcher_1",
                "device_id": "phone-wolf",
                "physical_presence_confirmed": True,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "No imported QR content is available.")

    def test_content_snapshot_endpoint_returns_latest_import(self) -> None:
        database_path = PROJECT_ROOT / ".test-data" / f"snapshot_api_{uuid4().hex}.db"
        settings = Settings(database_path=database_path)
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
        client = TestClient(create_app(settings))

        response = client.get("/api/content/snapshot", params={"player_code": "WC-WOLF-6GF4"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["snapshot_version"], report.snapshot_version)
        self.assertEqual(payload["visibility"]["scope"], "player")
        self.assertEqual(payload["player"]["player_id"], "p_witcher_1")
        self.assertEqual(payload["act_unlock_state"]["policy"], "server_sync_or_revealed_master_code")
        self.assertTrue(payload["act_unlock_codes"])
        self.assertTrue(all(row["code"] is None for row in payload["act_unlock_codes"]))
        self.assertTrue(all(row["code_sha256"] is None for row in payload["act_unlock_codes"]))
        self.assertNotIn("player_codes", payload)
        self.assertNotIn("role_tokens", payload)
        for secret in SECRET_VALUES:
            self.assertNotIn(secret, response.text)
        self.assertNotIn("UNLOCK-A2-7GQ4", response.text)
        self.assertNotIn(
            hashlib.sha256("UNLOCK-A2-7GQ4".encode("utf-8")).hexdigest(),
            response.text,
        )

    def test_content_snapshot_rejects_missing_or_invalid_player_code(self) -> None:
        settings = self._settings("snapshot_auth")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        missing = client.get("/api/content/snapshot")
        invalid = client.get("/api/content/snapshot", params={"player_code": "WC-NOPE-0000"})

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)

    def test_player_code_auth_returns_player_identity_without_secret_code(self) -> None:
        settings = self._settings("player_code_auth")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        response = client.post(
            "/api/auth/player-code",
            json={"player_code": "SC-MOON-4AD8", "device_id": "phone-moon"},
        )
        rejected = client.post(
            "/api/auth/player-code",
            json={"player_code": "SC-NOPE-0000", "device_id": "phone-moon"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["player_id"], "p_sorc_1")
        self.assertEqual(payload["role_type"], "sorceress")
        self.assertEqual(payload["device_id"], "phone-moon")
        self.assertIn("mobile:snapshot", payload["permissions"])
        self.assertNotIn("SC-MOON-4AD8", response.text)
        self.assertEqual(rejected.status_code, 401)

    def test_master_api_requires_master_role_token(self) -> None:
        settings = self._settings("master_auth_boundary")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        missing = client.get("/api/master/review-queue")
        wrong_role = client.get(
            "/api/master/review-queue",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        accepted = client.get(
            "/api/master/review-queue",
            headers={"X-Role-Token": "MASTER-KING-4QZ8"},
        )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong_role.status_code, 403)
        self.assertEqual(accepted.status_code, 200)

    def test_master_utility_and_lord_battle_listing_contracts(self) -> None:
        suffix = uuid4().hex
        settings = Settings(
            database_path=PROJECT_ROOT / ".test-data" / f"master_utility_{suffix}.db",
            backup_dir=PROJECT_ROOT / ".test-data" / f"master_utility_backups_{suffix}",
        )
        self._import_valid_seed(settings)
        with connect(settings) as connection:
            connection.execute(
                """
                INSERT INTO role_tokens (
                    _import_run_id, _row_number, token_id, role_type,
                    owner_id, token, enabled
                )
                VALUES (
                    'test_master_utility',
                    900,
                    'token_sorceress_api_negative',
                    'sorceress',
                    'p_sorc_1',
                    'SORC-API-NEGATIVE',
                    'true'
                )
                """
            )
        client = TestClient(create_app(settings))

        act_state = client.get("/api/master/acts/state", headers=MASTER_HEADERS)
        timers = client.get("/api/master/timers", headers=MASTER_HEADERS)
        backup = client.post("/api/backups/run", headers=MASTER_HEADERS, json={})
        missing_act_start = client.post(
            "/api/master/acts/no_such_act/start",
            headers=MASTER_HEADERS,
            json={},
        )
        hidden_unlock = client.get(
            "/api/master/acts/act2/unlock-code",
            headers=MASTER_HEADERS,
        )
        missing_unlock = client.get(
            "/api/master/acts/no_such_act/unlock-code",
            headers=MASTER_HEADERS,
        )
        battle_list = client.get("/api/lord-battles", headers=MASTER_HEADERS)
        missing_battle = client.get("/api/lord-battles/no_such_battle", headers=MASTER_HEADERS)
        wrong_battle_actor = client.post(
            "/api/lord-battles/no_such_battle/actions",
            headers={"X-Role-Token": "SORC-API-NEGATIVE"},
            json={"action_type": "defend", "actor_side": "attacker"},
        )

        self.assertEqual(act_state.status_code, 200)
        self.assertIn("current_act_id", act_state.json()["state"])
        self.assertEqual(timers.status_code, 200)
        self.assertIn("applied_now", timers.json())
        self.assertEqual(backup.status_code, 200)
        self.assertEqual(backup.json()["trigger_type"], "manual")
        self.assertEqual(missing_act_start.status_code, 404)
        self.assertEqual(hidden_unlock.status_code, 403)
        self.assertEqual(missing_unlock.status_code, 404)
        self.assertEqual(battle_list.status_code, 200)
        self.assertEqual(battle_list.json()["items"], [])
        self.assertEqual(missing_battle.status_code, 404)
        self.assertEqual(missing_battle.json()["detail"]["code"], "battle_not_found")
        self.assertEqual(wrong_battle_actor.status_code, 403)
        self.assertEqual(wrong_battle_actor.json()["detail"], "Token cannot access lord battle API.")

    def test_qr_lookup_endpoint_returns_scene_context(self) -> None:
        database_path = PROJECT_ROOT / ".test-data" / f"qr_lookup_{uuid4().hex}.db"
        settings = Settings(database_path=database_path)
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
        client = TestClient(create_app(settings))

        response = client.post(
            "/api/qr/lookup",
            json={
                "code": "QR-A1-K7Q2",
                "player_id": "p_witcher_1",
                "device_id": "device-test",
                "source": "manual_id",
                "physical_presence_confirmed": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["event_type"], "qr_scene_started")
        self.assertEqual(payload["qr"]["qr_mode"], "repeatable_scene")
        self.assertEqual(payload["scenario"]["scenario_id"], "scn_a1_001")
        self.assertEqual(payload["event_context"]["qr_mode"], "repeatable_scene")
        self.assertTrue(payload["event_context"]["physical_presence_confirmed"])

    def test_qr_lookup_locks_future_act_without_scene_payload_until_announcement(self) -> None:
        settings = self._settings("qr_future_act_locked")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        locked = client.post(
            "/api/qr/lookup",
            json={
                "code": "QR-A2-B4K8",
                "player_id": "p_witcher_1",
                "device_id": "device-future",
                "source": "manual_id",
                "physical_presence_confirmed": True,
            },
        )
        self.assertEqual(locked.status_code, 200, locked.text)
        locked_payload = locked.json()
        self.assertEqual(locked_payload["status"], "locked")
        self.assertEqual(locked_payload["reason"], "requires_act_unlock")
        self.assertEqual(locked_payload["event_type"], "qr_attempt")
        self.assertEqual(locked_payload["qr"]["qr_id"], "qr_a2_013")
        self.assertEqual(locked_payload["qr"]["qr_mode"], "repeatable_scene")
        self.assertNotIn("scenario_id", locked_payload["qr"])
        self.assertNotIn("manual_code", locked_payload["qr"])
        self.assertIsNone(locked_payload["scenario"])
        self.assertIsNone(locked_payload["event_context"]["scenario_id"])
        self.assertIsNone(locked_payload["event_context"]["scene_type"])
        self.assertTrue(locked_payload["event_context"]["requires_act_unlock"])
        dumped_locked = json.dumps(locked_payload, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("Fang secured", dumped_locked)
        self.assertNotIn("reward_pve_t2", dumped_locked)

        pending_start = client.post(
            "/api/master/acts/act2/start",
            headers=MASTER_HEADERS,
            json={"operator": "gm_qr", "physical_announcement_state": "pending"},
        )
        self.assertEqual(pending_start.status_code, 200, pending_start.text)
        still_locked = client.post(
            "/api/qr/lookup",
            json={
                "code": "QR-A2-B4K8",
                "player_id": "p_witcher_1",
                "device_id": "device-future",
                "source": "manual_id",
                "physical_presence_confirmed": True,
            },
        )
        self.assertEqual(still_locked.json()["status"], "locked")

        announcement = client.post(
            "/api/master/acts/act2/physical-announcement",
            headers=MASTER_HEADERS,
            json={"operator": "gm_qr", "state": "announced"},
        )
        self.assertEqual(announcement.status_code, 200, announcement.text)
        unlocked = client.post(
            "/api/qr/lookup",
            json={
                "code": "QR-A2-B4K8",
                "player_id": "p_witcher_1",
                "device_id": "device-future",
                "source": "manual_id",
                "physical_presence_confirmed": True,
            },
        )
        self.assertEqual(unlocked.status_code, 200, unlocked.text)
        unlocked_payload = unlocked.json()
        self.assertEqual(unlocked_payload["status"], "ok")
        self.assertEqual(unlocked_payload["event_type"], "qr_scene_started")
        self.assertEqual(unlocked_payload["scenario"]["scenario_id"], "scn_a2_013")
        self.assertEqual(unlocked_payload["scenario"]["reward_id"], "reward_pve_t2")

    def test_qr_lookup_does_not_disclose_scene_for_predictable_qr_id(self) -> None:
        settings = self._settings("qr_lookup_opaque_only")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        response = client.post(
            "/api/qr/lookup",
            json={
                "code": "witcher-larp://qr?id=qr_a1_001",
                "player_id": "p_witcher_1",
                "device_id": "device-opaque",
                "source": "qr_scan",
                "physical_presence_confirmed": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "unknown_qr")
        self.assertIsNone(payload["qr"])
        self.assertIsNone(payload["scenario"])
        self.assertIsNone(payload["event_context"]["qr_id"])

    def test_qr_lookup_accepts_seed_codes_for_each_qr_mode(self) -> None:
        database_path = PROJECT_ROOT / ".test-data" / f"qr_modes_{uuid4().hex}.db"
        settings = Settings(database_path=database_path)
        import_seed_pack(
            settings,
            manifest_path=PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "seed_valid"
            / "fixture_manifest.csv",
            snapshot_dir=None,
        )
        client = TestClient(create_app(settings))
        cases = (
            ("QR-A1-K7Q2", "manual_id", "repeatable_scene"),
            ("witcher-larp://qr?code=QR-A1-V8N1", "qr_scan", "always_available_scene"),
            ("QR-A1-X3L5", "manual_id", "unique_object"),
        )

        for code, source, expected_mode in cases:
            with self.subTest(mode=expected_mode):
                response = client.post(
                    "/api/qr/lookup",
                    json={
                        "code": code,
                        "player_id": "p_witcher_1",
                        "device_id": f"device-{expected_mode}",
                        "source": source,
                        "physical_presence_confirmed": True,
                    },
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["status"], "ok")
                self.assertEqual(payload["event_context"]["qr_mode"], expected_mode)

    def test_qr_lookup_marks_missing_presence_for_review(self) -> None:
        database_path = PROJECT_ROOT / ".test-data" / f"qr_presence_{uuid4().hex}.db"
        settings = Settings(database_path=database_path)
        import_seed_pack(
            settings,
            manifest_path=PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "seed_valid"
            / "fixture_manifest.csv",
            snapshot_dir=None,
        )
        client = TestClient(create_app(settings))

        response = client.post(
            "/api/qr/lookup",
            json={
                "code": "witcher-larp://qr?code=QR-A1-X3L5",
                "player_id": "p_witcher_1",
                "device_id": "device-review",
                "source": "qr_scan",
                "physical_presence_confirmed": False,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "needs_master_review")
        self.assertEqual(payload["reason"], "honesty_violation_suspected")
        self.assertEqual(payload["event_context"]["qr_mode"], "unique_object")
        self.assertEqual(
            payload["event_context"]["offline_instruction"],
            "success_take_physical_qr_failure_leave_it",
        )

    def test_qr_lookup_rate_limits_unknown_manual_ids(self) -> None:
        database_path = PROJECT_ROOT / ".test-data" / f"qr_rate_{uuid4().hex}.db"
        settings = Settings(database_path=database_path)
        import_seed_pack(
            settings,
            manifest_path=PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "seed_valid"
            / "fixture_manifest.csv",
            snapshot_dir=None,
        )
        client = TestClient(create_app(settings))

        payload = None
        for index in range(5):
            response = client.post(
                "/api/qr/lookup",
                json={
                    "code": f"NO-SUCH-QR-{index}",
                    "player_id": "p_witcher_1",
                    "device_id": "device-rate",
                    "source": "manual_id",
                    "physical_presence_confirmed": True,
                },
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()

        assert payload is not None
        self.assertEqual(payload["status"], "needs_master_review")
        self.assertEqual(payload["reason"], "manual_rate_limit")
        self.assertEqual(payload["event_context"]["review_reason"], "manual_rate_limit")
        self.assertEqual(payload["rate_limit"]["limit"], 5)
        with connect(settings) as connection:
            attempt_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM qr_attempts
                WHERE player_id = 'p_witcher_1'
                  AND device_id = 'device-rate'
                  AND reason = 'manual_rate_limit'
                """
            ).fetchone()[0]
            audit_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM event_log
                WHERE event_type = 'qr_attempt'
                  AND source = 'manual_id'
                  AND payload_json LIKE '%manual_rate_limit%'
                """
            ).fetchone()[0]

        self.assertEqual(attempt_count, 1)
        self.assertEqual(audit_count, 1)

    def test_qr_lookup_rate_limits_anonymous_bad_attempts(self) -> None:
        settings = self._settings("qr_rate_anonymous")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        payload = None
        for index in range(5):
            response = client.post(
                "/api/qr/lookup",
                json={
                    "code": f"NO-SUCH-ANON-{index}",
                    "source": "manual_id",
                    "physical_presence_confirmed": True,
                },
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()

        assert payload is not None
        self.assertEqual(payload["status"], "needs_master_review")
        self.assertEqual(payload["reason"], "manual_rate_limit")
        self.assertEqual(payload["event_context"]["review_reason"], "manual_rate_limit")

    def test_event_sync_accepts_pve_event_and_deduplicates_by_event_id(self) -> None:
        settings = self._settings("event_dedupe")
        report = self._import_valid_seed(settings)
        client = TestClient(create_app(settings))
        event_id = f"evt_{uuid4().hex}"
        with connect(settings) as connection:
            pve_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_001",
                roll=8,
            )
        request = {
            "device_id": "phone_wolf",
            "actor_id": "p_witcher_1",
            "actor_type": "player",
            "events": [
                {
                    "event_id": event_id,
                    "client_sequence": 1,
                    "created_at": "2026-06-02T09:00:00+00:00",
                    "event_type": "pve_completed",
                    "payload": pve_payload,
                }
            ],
        }

        first = client.post(
            "/api/events/sync",
            headers={"X-Player-Code": "WC-WOLF-6GF4"},
            json=request,
        )
        second = client.post(
            "/api/events/sync",
            headers={"X-Player-Code": "WC-WOLF-6GF4"},
            json=request,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        first_payload = first.json()
        second_payload = second.json()
        self.assertEqual(first_payload["snapshot_version"], report.snapshot_version)
        self.assertEqual(first_payload["results"][0]["status"], "accepted")
        self.assertEqual(second_payload["results"][0]["status"], "duplicate")
        self.assertEqual(
            second_payload["results"][0]["server_event_id"],
            first_payload["results"][0]["server_event_id"],
        )

        with connect(settings) as connection:
            event_count = connection.execute(
                "SELECT COUNT(*) FROM events WHERE event_id = ?",
                (event_id,),
            ).fetchone()[0]
            stored_payload = connection.execute(
                "SELECT payload_json FROM events WHERE event_id = ?",
                (event_id,),
            ).fetchone()["payload_json"]
            log_count = connection.execute(
                "SELECT COUNT(*) FROM event_log WHERE payload_json LIKE ?",
                (f"%{event_id}%",),
            ).fetchone()[0]
            approval_count = connection.execute(
                "SELECT COUNT(*) FROM reward_approvals WHERE source_event_id = ?",
                (first_payload["results"][0]["server_event_id"],),
            ).fetchone()[0]
            sync_state = connection.execute(
                "SELECT last_event_sequence FROM client_sync_state WHERE client_id = ?",
                ("phone_wolf",),
            ).fetchone()

        self.assertEqual(event_count, 1)
        self.assertIn("roll_log", stored_payload)
        self.assertIn("Сила", stored_payload)
        self.assertEqual(log_count, 1)
        self.assertEqual(approval_count, 0)
        self.assertEqual(sync_state["last_event_sequence"], 1)

    def test_event_sync_uses_auth_context_and_audits_master_only_player_events(self) -> None:
        settings = self._settings("event_auth_boundary")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))
        forged_event_id = f"evt_{uuid4().hex}"
        paper_event_id = f"evt_{uuid4().hex}"

        missing_auth = client.post(
            "/api/events/sync",
            json={
                "device_id": "phone_wolf",
                "actor_id": "p_witcher_1",
                "actor_type": "player",
                "events": [],
            },
        )
        forged_actor = client.post(
            "/api/events/sync",
            headers={"X-Player-Code": "WC-WOLF-6GF4"},
            json={
                "device_id": "phone_wolf",
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
                            "source": "mobile",
                            "local_status": "accepted",
                        },
                    }
                ],
            },
        )
        player_master_only = client.post(
            "/api/events/sync",
            headers={"X-Player-Code": "WC-WOLF-6GF4"},
            json={
                "device_id": "phone_wolf",
                "actor_id": "p_witcher_1",
                "actor_type": "master",
                "events": [
                    {
                        "event_id": paper_event_id,
                        "client_sequence": 2,
                        "created_at": "2026-06-02T09:05:00+00:00",
                        "event_type": "paper_recovered",
                        "payload": {"source_form_type": "pve_result_sheet"},
                    }
                ],
            },
        )

        self.assertEqual(missing_auth.status_code, 401)
        self.assertEqual(forged_actor.status_code, 200)
        self.assertEqual(forged_actor.json()["results"][0]["status"], "accepted")
        self.assertEqual(player_master_only.status_code, 200)
        master_only_result = player_master_only.json()["results"][0]
        self.assertEqual(master_only_result["status"], "rejected")
        self.assertEqual(
            master_only_result["reason"],
            "paper_recovered requires master auth context",
        )

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
                SELECT actor_id, actor_type, status, metadata_json
                FROM events
                WHERE event_id = ?
                """,
                (paper_event_id,),
            ).fetchone()
            review = connection.execute(
                """
                SELECT status, reason, severity
                FROM event_reviews
                WHERE event_id = ?
                """,
                (paper_event_id,),
            ).fetchone()

        self.assertEqual(forged_stored["actor_id"], "p_witcher_1")
        self.assertEqual(forged_stored["actor_type"], "player")
        self.assertEqual(forged_stored["status"], "accepted")
        self.assertEqual(rejected_stored["actor_id"], "p_witcher_1")
        self.assertEqual(rejected_stored["actor_type"], "player")
        self.assertEqual(rejected_stored["status"], "rejected")
        self.assertEqual(review["status"], "rejected")
        self.assertEqual(review["severity"], "P0")
        self.assertEqual(review["reason"], "paper_recovered requires master auth context")
        metadata = json.loads(rejected_stored["metadata_json"])
        self.assertEqual(metadata["auth_boundary"], "master_only_event")
        self.assertTrue(metadata["audit_review"])

    def test_event_sync_creates_pending_reward_approval(self) -> None:
        settings = self._settings("event_pending_reward")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))
        event_id = f"evt_{uuid4().hex}"
        with connect(settings) as connection:
            pve_payload = resolve_pve_scene(
                connection,
                player_id="p_witcher_1",
                qr_id="qr_a1_007",
                roll=11,
            )

        response = client.post(
            "/api/events/sync",
            headers={"X-Player-Code": "WC-WOLF-6GF4"},
            json={
                "device_id": "phone_wolf",
                "actor_id": "p_witcher_1",
                "actor_type": "player",
                "events": [
                    {
                        "event_id": event_id,
                        "client_sequence": 2,
                        "created_at": "2026-06-02T09:05:00+00:00",
                        "event_type": "pve_completed",
                        "payload": pve_payload,
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        result = payload["results"][0]
        self.assertEqual(result["status"], "pending_master_approval")
        self.assertEqual(result["reason"], "reward requires master approval")

        with connect(settings) as connection:
            approval = connection.execute(
                """
                SELECT reward_id, player_id, status
                FROM reward_approvals
                WHERE source_event_id = ?
                """,
                (result["server_event_id"],),
            ).fetchone()
            stored_event = connection.execute(
                """
                SELECT payload_json, metadata_json, status
                FROM events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()

        self.assertEqual(approval["reward_id"], "reward_artifact_pending")
        self.assertEqual(approval["player_id"], "p_witcher_1")
        self.assertEqual(approval["status"], "pending_master_approval")
        self.assertEqual(stored_event["status"], "pending_master_approval")
        self.assertIn("reward_artifact_pending", stored_event["payload_json"])
        self.assertIn("reward_approval_policy", stored_event["metadata_json"])

    def test_event_sync_accepts_valid_offline_act_unlock_code(self) -> None:
        settings = self._settings("event_act_unlock")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        start = client.post(
            "/api/master/acts/act2/start",
            headers=MASTER_HEADERS,
            json={"operator": "gm_king", "physical_announcement_state": "announced"},
        )
        revealed = client.get(
            "/api/master/acts/act2/unlock-code",
            headers=MASTER_HEADERS,
            params={"operator": "gm_king"},
        )
        self.assertEqual(start.status_code, 200)
        self.assertEqual(revealed.status_code, 200)

        response = client.post(
            "/api/events/sync",
            headers={"X-Player-Code": "WC-WOLF-6GF4"},
            json={
                "device_id": "phone_wolf",
                "actor_id": "p_witcher_1",
                "actor_type": "player",
                "events": [
                    {
                        "event_id": f"evt_{uuid4().hex}",
                        "client_sequence": 3,
                        "created_at": "2026-06-02T09:10:00+00:00",
                        "event_type": "act_unlocked_offline",
                        "payload": {"act_id": "act2", "code": "UNLOCK-A2-7GQ4"},
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["status"], "accepted")
        self.assertIsNone(result["reason"])

    def test_event_sync_saves_review_reason_and_raw_payload(self) -> None:
        settings = self._settings("event_review")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))
        event_id = f"evt_{uuid4().hex}"

        response = client.post(
            "/api/events/sync",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={
                "device_id": "lord_panel_north",
                "actor_id": "p_lord_1",
                "actor_type": "lord",
                "events": [
                    {
                        "event_id": event_id,
                        "client_sequence": 4,
                        "created_at": "2026-06-02T09:15:00+00:00",
                        "event_type": "trade_transfer_requested",
                        "payload": {
                            "transfer_id": "transfer_conflict_demo",
                            "asset_id": "item_order_seal",
                            "requires_master_review": True,
                            "review_reason": "asset is already locked by another pending transfer",
                        },
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["status"], "needs_master_review")
        self.assertEqual(
            result["reason"],
            "asset is already locked by another pending transfer",
        )

        with connect(settings) as connection:
            review = connection.execute(
                """
                SELECT reason
                FROM event_reviews
                WHERE server_event_id = ?
                """,
                (result["server_event_id"],),
            ).fetchone()
            stored_event = connection.execute(
                """
                SELECT payload_json, metadata_json, reason
                FROM events
                WHERE event_id = ?
                """,
                (event_id,),
            ).fetchone()

        self.assertEqual(review["reason"], result["reason"])
        self.assertIn("transfer_conflict_demo", stored_event["payload_json"])
        self.assertIn("lord_panel_north", stored_event["metadata_json"])
        self.assertEqual(stored_event["reason"], result["reason"])

    def test_master_review_lifecycle_approve_reject_correct_and_auth(self) -> None:
        settings = self._settings("event_review_lifecycle")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        approve_event_id = f"evt_review_approve_{uuid4().hex}"
        reject_event_id = f"evt_review_reject_{uuid4().hex}"
        correct_event_id = f"evt_review_correct_{uuid4().hex}"
        for sequence, event_id in enumerate(
            (approve_event_id, reject_event_id, correct_event_id),
            start=1,
        ):
            response = client.post(
                "/api/events/sync",
                headers={"X-Role-Token": "LORD-NORTH-R8K4"},
                json={
                    "device_id": "lord_panel_north",
                    "actor_id": "p_lord_1",
                    "actor_type": "lord",
                    "events": [
                        {
                            "event_id": event_id,
                            "client_sequence": sequence,
                            "created_at": "2026-06-02T09:15:00+00:00",
                            "event_type": "trade_transfer_requested",
                            "payload": {
                                "transfer_id": f"transfer_review_{sequence}",
                                "requires_master_review": True,
                                "review_reason": "conflicting offline report",
                            },
                        }
                    ],
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["results"][0]["status"], "needs_master_review")

        no_auth = client.post(
            f"/api/events/{approve_event_id}/review",
            json={"action": "approve", "reason": "approved by table ruling"},
        )
        lord_auth = client.post(
            f"/api/events/{approve_event_id}/review",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={"action": "approve", "reason": "approved by table ruling"},
        )
        approved = client.post(
            f"/api/events/{approve_event_id}/review",
            headers=MASTER_HEADERS,
            json={
                "action": "approve",
                "reason": "approved by table ruling",
                "severity": "P1",
                "operator": "gm_king",
            },
        )
        duplicate_approved = client.post(
            f"/api/events/{approve_event_id}/review",
            headers=MASTER_HEADERS,
            json={
                "action": "approve",
                "reason": "approved by table ruling",
                "severity": "P1",
                "operator": "gm_king",
            },
        )
        rejected = client.post(
            f"/api/events/{reject_event_id}/review",
            headers=MASTER_HEADERS,
            json={
                "action": "reject",
                "reason": "paper form contradicted confirmed digital state",
                "severity": "P0",
            },
        )
        corrected = client.post(
            "/api/master/corrections",
            headers=MASTER_HEADERS,
            json={
                "event_id": correct_event_id,
                "action": "correct",
                "reason": "corrected transfer id from paper form",
                "correction": {
                    "payload": {"transfer_id": "transfer_review_corrected"},
                    "metadata": {"correction_note": "paper form OCR fix"},
                },
            },
        )

        self.assertEqual(no_auth.status_code, 401)
        self.assertEqual(lord_auth.status_code, 403)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["decision"]["status"], "applied")
        self.assertEqual(approved.json()["review"]["status"], "approved")
        self.assertEqual(approved.json()["review"]["severity"], "P1")
        self.assertEqual(approved.json()["event"]["status"], "accepted")
        self.assertEqual(duplicate_approved.status_code, 200, duplicate_approved.text)
        self.assertEqual(duplicate_approved.json()["decision"]["status"], "duplicate")
        self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertEqual(rejected.json()["review"]["status"], "rejected")
        self.assertEqual(rejected.json()["event"]["status"], "rejected")
        self.assertEqual(corrected.status_code, 200, corrected.text)
        self.assertEqual(corrected.json()["review"]["status"], "corrected")
        self.assertEqual(corrected.json()["event"]["status"], "accepted")
        self.assertEqual(
            corrected.json()["correction"]["correction"]["payload"]["transfer_id"],
            "transfer_review_corrected",
        )

        with connect(settings) as connection:
            rows = connection.execute(
                """
                SELECT er.event_id, er.status, er.decision_reason, er.decided_by,
                       er.correction_id, e.status AS event_status, e.payload_json
                FROM event_reviews er
                JOIN events e ON e.server_event_id = er.server_event_id
                WHERE er.event_id IN (?, ?, ?)
                ORDER BY er.event_id
                """,
                (approve_event_id, reject_event_id, correct_event_id),
            ).fetchall()
            correction_count = connection.execute(
                "SELECT COUNT(*) FROM master_corrections"
            ).fetchone()[0]
            corrected_payload = json.loads(
                next(row for row in rows if row["event_id"] == correct_event_id)[
                    "payload_json"
                ]
            )

        self.assertEqual(correction_count, 3)
        self.assertTrue(all(row["correction_id"] for row in rows))
        self.assertEqual(corrected_payload["transfer_id"], "transfer_review_corrected")

    def test_reputation_endpoint_is_scoped_to_own_player_or_master(self) -> None:
        settings = self._settings("reputation_scope")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        missing_auth = client.get("/api/players/p_witcher_1/reputation")
        own_player = client.get(
            "/api/players/p_witcher_1/reputation",
            headers={"X-Player-Code": "WC-WOLF-6GF4"},
        )
        foreign_player = client.get(
            "/api/players/p_witcher_2/reputation",
            headers={"X-Player-Code": "WC-WOLF-6GF4"},
        )
        master_view = client.get(
            "/api/players/p_witcher_2/reputation",
            headers=MASTER_HEADERS,
        )
        lord_master_view = client.get(
            "/api/master/reputation/p_witcher_2",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )

        self.assertEqual(missing_auth.status_code, 401)
        self.assertEqual(own_player.status_code, 200, own_player.text)
        self.assertEqual(own_player.json()["player_id"], "p_witcher_1")
        self.assertNotIn("value", own_player.json())
        self.assertEqual(own_player.json()["value_visibility"], "hidden_from_player")
        self.assertEqual(foreign_player.status_code, 403)
        self.assertEqual(master_view.status_code, 200, master_view.text)
        self.assertEqual(master_view.json()["player_id"], "p_witcher_2")
        self.assertIn("value", master_view.json())
        self.assertIn("change_log", master_view.json())
        self.assertEqual(lord_master_view.status_code, 403)

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
