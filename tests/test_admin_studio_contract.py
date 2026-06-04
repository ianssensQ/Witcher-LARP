from __future__ import annotations

import unittest
from uuid import uuid4

from backend.witcher_larp.app import create_app
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.event_schema import ensure_event_schema
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.reward_service import create_pending_reward_approval

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None  # type: ignore[assignment]


MASTER_HEADERS = {"X-Role-Token": "MASTER-KING-4QZ8"}
LORD_HEADERS = {"X-Role-Token": "LORD-NORTH-R8K4"}
SECRET_VALUES = (
    "MASTER-KING-4QZ8",
    "MASTER-WANDERER-2LF6",
    "LORD-NORTH-R8K4",
    "LC-RIVER-8YM4",
)


@unittest.skipIf(TestClient is None, "FastAPI/httpx dependencies are not installed")
class AdminStudioContractTests(unittest.TestCase):
    def setUp(self) -> None:
        (PROJECT_ROOT / ".test-data").mkdir(exist_ok=True)

    def test_admin_static_shell_is_served_without_node_build(self) -> None:
        client = TestClient(create_app(self._settings("admin_static")))

        page = client.get("/admin")
        script = client.get("/static/admin/admin.js")
        styles = client.get("/static/admin/admin.css")

        self.assertEqual(page.status_code, 200)
        self.assertIn('data-app="admin-studio"', page.text)
        self.assertIn('id="section-nav"', page.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("/api/auth/role-token", script.text)
        self.assertIn("/api/master/admin/overview", script.text)
        self.assertIn("/api/master/content/import", script.text)
        self.assertIn("/api/master/state", script.text)
        self.assertIn("/api/master/visibility-audit", script.text)
        self.assertIn("/api/master/game-ops/corrections", script.text)
        self.assertIn("/api/master/backups/status", script.text)
        self.assertIn("/api/master/final-summary", script.text)
        self.assertIn("Submit paper recovery", script.text)
        self.assertIn("paper_pve_result", script.text)
        self.assertIn("paper_pvp_stake", script.text)
        self.assertIn("paper_lord_action", script.text)
        self.assertIn("paper_lord_battle", script.text)
        self.assertIn("paper_order_resolution", script.text)
        self.assertIn("paper_npc_deal", script.text)
        self.assertIn("paper_final_evidence", script.text)
        self.assertIn("Recent event log and sync status", script.text)
        self.assertIn("Anti-snowball state", script.text)
        self.assertIn("Potion market correction", script.text)
        self.assertIn("Trade transfer correction", script.text)
        self.assertIn("Player economy correction", script.text)
        self.assertIn("Apply correction", script.text)
        self.assertIn("QR/manual checklist", script.text)
        self.assertIn("Handout checklist", script.text)
        self.assertIn("PvP throttle", script.text)
        self.assertIn("Record King event", script.text)
        self.assertIn("Wanderer hidden price", script.text)
        self.assertIn("Capture NPC deal", script.text)
        self.assertIn("Exact reputation view", script.text)
        self.assertIn("Artifact visibility audit", script.text)
        self.assertIn("Open final summary", script.text)
        self.assertIn("Export final summary", script.text)
        self.assertIn("npc_master", script.text)
        self.assertIn("Master role token required", script.text)
        self.assertEqual(styles.status_code, 200)
        self.assertIn("[hidden]", styles.text)
        self.assertIn(".status-badge", styles.text)
        self.assertIn(".content-controls", styles.text)
        self.assertIn(".ops-panel", styles.text)
        self.assertIn(".paper-fieldset", styles.text)
        self.assertIn(".typed-correction", styles.text)
        self.assertIn('id="dashboard-status"', page.text)
        self.assertFalse(
            (PROJECT_ROOT / "backend" / "witcher_larp" / "web" / "package.json").exists()
        )

    def test_admin_overview_requires_master_role_token(self) -> None:
        settings = self._settings("admin_access")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        missing = client.get("/api/master/admin/overview")
        invalid = client.get(
            "/api/master/admin/overview",
            headers={"X-Role-Token": "NO-SUCH-TOKEN"},
        )
        lord = client.get("/api/master/admin/overview", headers=LORD_HEADERS)
        master = client.get("/api/master/admin/overview", headers=MASTER_HEADERS)

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(lord.status_code, 403)
        self.assertEqual(master.status_code, 200, master.text)

        payload = master.json()
        self.assertEqual(payload["stage"], "STAGE-2: Admin Studio")
        self.assertEqual(payload["visibility"]["scope"], "master")
        section_ids = {section["id"] for section in payload["sections"]}
        self.assertEqual(
            section_ids,
            {"content", "game-ops", "events", "npc", "backups", "final"},
        )
        self.assertEqual(
            [item["id"] for item in payload["navigation"]],
            ["content", "game-ops", "events", "npc", "backups", "final"],
        )
        self.assertIn("master:read", self._auth(client)["permissions"])
        for secret in SECRET_VALUES:
            self.assertNotIn(secret, master.text)

    def test_admin_overview_reports_real_and_pending_surfaces(self) -> None:
        settings = self._settings("admin_overview")
        report = self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        response = client.get("/api/master/admin/overview", headers=MASTER_HEADERS)

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["snapshot_version"], report.snapshot_version)
        sections = {section["id"]: section for section in payload["sections"]}

        content_metrics = self._metrics(sections["content"])
        self.assertEqual(content_metrics["Players"], 13)
        self.assertEqual(content_metrics["Snapshot"], report.snapshot_version)
        self.assertEqual(
            self._actions(sections["content"])["import_validation"]["status"],
            "ready",
        )
        self.assertEqual(
            self._actions(sections["content"])["snapshot_export"]["endpoint"],
            "/api/master/content/snapshot/export",
        )
        self.assertEqual(
            self._actions(sections["content"])["player_snapshot"]["status"],
            "player_code_required",
        )

        self.assertEqual(self._actions(sections["game-ops"])["acts_state"]["endpoint"], "/api/master/acts/state")
        self.assertEqual(
            self._actions(sections["game-ops"])["master_state"]["endpoint"],
            "/api/master/state",
        )
        self.assertEqual(
            self._actions(sections["game-ops"])["event_log"]["endpoint"],
            "/api/master/state",
        )
        self.assertEqual(
            self._actions(sections["game-ops"])["sync_status"]["endpoint"],
            "/api/master/state",
        )
        self.assertEqual(
            self._actions(sections["game-ops"])["anti_snowball"]["endpoint"],
            "/api/master/state",
        )
        self.assertEqual(
            self._actions(sections["game-ops"])["visibility_audit"]["endpoint"],
            "/api/master/visibility-audit",
        )
        self.assertEqual(
            self._actions(sections["game-ops"])["game_ops_correction"]["endpoint"],
            "/api/master/game-ops/corrections",
        )
        self.assertEqual(
            self._actions(sections["game-ops"])["potion_trade_corrections"]["endpoint"],
            "/api/master/game-ops/corrections",
        )
        self.assertEqual(self._actions(sections["events"])["review_queue"]["status"], "ready")
        self.assertEqual(
            self._actions(sections["events"])["paper_recovery"]["endpoint"],
            "/api/events/sync",
        )
        self.assertEqual(self._actions(sections["npc"])["npc_deals"]["endpoint"], "/api/master/npc/deals")
        self.assertEqual(
            self._actions(sections["backups"])["backup_status"]["endpoint"],
            "/api/master/backups/status",
        )
        self.assertEqual(self._actions(sections["backups"])["run_backup"]["status"], "ready")
        self.assertEqual(
            self._actions(sections["backups"])["restore_backup"]["status"],
            "pending_backend",
        )
        self.assertEqual(self._actions(sections["final"])["final_summary"]["status"], "ready")

    def test_game_ops_dashboard_state_and_mutations_cover_day_ops(self) -> None:
        settings = self._settings("admin_game_ops")
        self._import_valid_seed(settings)
        with connect(settings) as connection:
            self._insert_review(connection, event_id="ops_review_1", severity="P1")
            create_pending_reward_approval(
                connection,
                approval_id="ops_reward_1",
                reward_id="reward_pve_t3",
                player_id="p_witcher_1",
                source_event_id=None,
            )

        client = TestClient(create_app(settings))
        missing = client.get("/api/master/state")
        self.assertEqual(missing.status_code, 401)

        start = client.post(
            "/api/master/acts/act2/start",
            headers=MASTER_HEADERS,
            json={"operator": "gm_ops", "physical_announcement_state": "pending"},
        )
        self.assertEqual(start.status_code, 200, start.text)
        self.assertFalse(start.json()["unlock_code"]["available"])
        self.assertIsNone(start.json()["unlock_code"]["code"])

        state = client.get("/api/master/state", headers=MASTER_HEADERS)
        self.assertEqual(state.status_code, 200, state.text)
        payload = state.json()
        self.assertEqual(payload["acts"]["state"]["current_act_id"], "act2")
        self.assertNotIn("UNLOCK-A2-7GQ4", state.text)
        self.assertIn("recent", payload["events"])
        self.assertIn("sync_statuses", payload["events"])
        self.assertIn("economy", payload)
        self.assertEqual(payload["events"]["review"]["critical_open_count"], 1)
        self.assertEqual(payload["reward_approvals"]["pending"][0]["severity"], "P1")
        self.assertTrue(
            any(
                territory["territory_id"] == "territory_fort_east"
                for territory in payload["lord_map"]["territories"]
            )
        )
        self.assertTrue(
            all("anti_snowball" in domain for domain in payload["lord_map"]["domains"])
        )

        announced = client.post(
            "/api/master/acts/act2/physical-announcement",
            headers=MASTER_HEADERS,
            json={"operator": "gm_ops", "state": "announced"},
        )
        self.assertEqual(announced.status_code, 200, announced.text)
        revealed = client.get(
            "/api/master/acts/act2/unlock-code",
            headers=MASTER_HEADERS,
            params={"operator": "gm_ops"},
        )
        self.assertEqual(revealed.status_code, 200, revealed.text)
        self.assertEqual(revealed.json()["code"], "UNLOCK-A2-7GQ4")

        review = client.post(
            "/api/events/ops_review_1/review",
            headers=MASTER_HEADERS,
            json={
                "action": "approve",
                "operator": "gm_ops",
                "reason": "paper log checked",
                "severity": "P1",
            },
        )
        self.assertEqual(review.status_code, 200, review.text)
        self.assertEqual(review.json()["review"]["status"], "approved")

        reward = client.post(
            "/api/master/reward-approvals/ops_reward_1",
            headers=MASTER_HEADERS,
            json={"action": "approve", "operator": "gm_ops", "reason": "roll log checked"},
        )
        self.assertEqual(reward.status_code, 200, reward.text)
        self.assertEqual(reward.json()["status"], "approved")

        throttle = client.post(
            "/api/master/pvp-throttle",
            headers=MASTER_HEADERS,
            json={"mode": "limited", "operator": "gm_ops"},
        )
        self.assertEqual(throttle.status_code, 200, throttle.text)
        self.assertEqual(throttle.json()["throttle"]["mode"], "limited")

        correction_missing_reason = client.post(
            "/api/master/game-ops/corrections",
            headers=MASTER_HEADERS,
            json={
                "target_type": "territory",
                "target_id": "territory_fort_east",
                "operator": "gm_ops",
                "reason": " ",
                "patch": {"owner_domain_id": "domain_north", "status": "controlled"},
            },
        )
        self.assertEqual(correction_missing_reason.status_code, 400)
        self.assertEqual(correction_missing_reason.json()["detail"]["code"], "missing_reason")

        correction = client.post(
            "/api/master/game-ops/corrections",
            headers=MASTER_HEADERS,
            json={
                "target_type": "territory",
                "target_id": "territory_fort_east",
                "operator": "gm_ops",
                "reason": "paper fallback checked",
                "patch": {"owner_domain_id": "domain_north", "status": "controlled"},
            },
        )
        self.assertEqual(correction.status_code, 200, correction.text)
        self.assertEqual(correction.json()["after"]["owner_domain_id"], "domain_north")

        backup_status = client.get("/api/master/backups/status", headers=MASTER_HEADERS)
        self.assertEqual(backup_status.status_code, 200, backup_status.text)
        backup = client.post(
            "/api/backups/run",
            headers=MASTER_HEADERS,
            json={"operator": "gm_ops", "trigger_type": "manual"},
        )
        self.assertEqual(backup.status_code, 200, backup.text)
        self.assertEqual(backup.json()["status"], "success")

        final_state = client.get("/api/master/state", headers=MASTER_HEADERS).json()
        self.assertEqual(final_state["pvp"]["throttle"]["mode"], "limited")
        self.assertEqual(final_state["events"]["review"]["critical_open_count"], 0)
        self.assertEqual(final_state["reward_approvals"]["pending_count"], 0)
        self.assertTrue(final_state["corrections"])
        self.assertEqual(final_state["backups"]["last_run"]["status"], "success")

    def test_admin_paper_recovery_uses_master_sync_and_conflict_review(self) -> None:
        settings = self._settings("admin_paper_recovery")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        clean = client.post(
            "/api/events/sync",
            headers=MASTER_HEADERS,
            json={
                "device_id": "admin-paper-terminal",
                "actor_id": "forged_client_actor",
                "actor_type": "player",
                "events": [
                    {
                        "event_id": "admin_paper_clean",
                        "client_sequence": 1,
                        "created_at": "2026-06-02T13:30:00+00:00",
                        "event_type": "paper_recovered",
                        "payload": {
                            "paper_form_id": "admin-paper-clean-1",
                            "source_form_type": "paper_pve_result",
                            "operator": "gm_admin",
                            "timestamp": "2026-06-02T13:30:00+00:00",
                            "reason": "phone outage during QR scene",
                            "player_id": "p_witcher_1",
                            "qr_id": "qr_a1_001",
                            "result": "success",
                            "roll": 8,
                            "conflict_status": "clean",
                        },
                    }
                ],
            },
        )
        conflict = client.post(
            "/api/events/sync",
            headers=MASTER_HEADERS,
            json={
                "device_id": "admin-paper-terminal",
                "actor_id": "forged_client_actor",
                "actor_type": "player",
                "events": [
                    {
                        "event_id": "admin_paper_battle_conflict",
                        "client_sequence": 2,
                        "created_at": "2026-06-02T14:00:00+00:00",
                        "event_type": "paper_recovered",
                        "payload": {
                            "paper_form_id": "admin-paper-battle-1",
                            "source_form_type": "paper_lord_battle",
                            "operator": "gm_admin",
                            "timestamp": "2026-06-02T14:00:00+00:00",
                            "reason": "paper battle result conflicts with digital battle",
                            "battle_id": "battle-paper-1",
                            "result": "attacker_won",
                            "losses": {"attacker": 1, "defender": 2},
                            "conflict_status": "duplicate_conflict_needs_review",
                        },
                    }
                ],
            },
        )

        self.assertEqual(clean.status_code, 200, clean.text)
        self.assertEqual(conflict.status_code, 200, conflict.text)
        self.assertEqual(clean.json()["results"][0]["status"], "accepted")
        self.assertEqual(conflict.json()["results"][0]["status"], "needs_master_review")
        self.assertEqual(
            conflict.json()["results"][0]["reason"],
            "paper battle result conflicts with digital battle",
        )

        with connect(settings) as connection:
            stored_clean = connection.execute(
                """
                SELECT actor_id, actor_type, source
                FROM events
                WHERE event_id = 'admin_paper_clean'
                """
            ).fetchone()
            review = connection.execute(
                """
                SELECT reason, status
                FROM event_reviews
                WHERE event_id = 'admin_paper_battle_conflict'
                """
            ).fetchone()
            runtime_state = connection.execute(
                """
                SELECT xp, gold
                FROM player_runtime_state
                WHERE player_id = 'p_witcher_1'
                """
            ).fetchone()
            pve_attempt = connection.execute(
                """
                SELECT player_id, qr_id, result, reward_id, reward_status
                FROM pve_attempts
                WHERE server_event_id = (
                    SELECT server_event_id
                    FROM events
                    WHERE event_id = 'admin_paper_clean'
                )
                """
            ).fetchone()

        self.assertEqual(
            dict(stored_clean),
            {"actor_id": "npc_king", "actor_type": "master", "source": "paper_recovered"},
        )
        self.assertEqual(dict(review), {
            "reason": "paper battle result conflicts with digital battle",
            "status": "needs_master_review",
        })
        self.assertEqual(dict(runtime_state), {"xp": 4, "gold": 30})
        self.assertEqual(
            dict(pve_attempt),
            {
                "player_id": "p_witcher_1",
                "qr_id": "qr_a1_001",
                "result": "success",
                "reward_id": "reward_pve_t1",
                "reward_status": "auto",
            },
        )

    def test_admin_content_import_api_reports_validation_and_checklists(self) -> None:
        settings = self._settings("admin_content")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))
        valid_manifest = (
            PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"
        )
        invalid_manifest = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "seed_invalid_missing_refs"
            / "fixture_manifest.csv"
        )

        packs = client.get("/api/master/content/packs", headers=MASTER_HEADERS)
        self.assertEqual(packs.status_code, 200, packs.text)
        pack_ids = {pack["id"] for pack in packs.json()["packs"]}
        self.assertIn("data_seed", pack_ids)
        self.assertIn("seed_valid", pack_ids)

        valid = client.post(
            "/api/master/content/import",
            headers=MASTER_HEADERS,
            json={"manifest_path": str(valid_manifest), "export_snapshot": False},
        )
        self.assertEqual(valid.status_code, 200, valid.text)
        valid_report = valid.json()
        self.assertEqual(valid_report["status"], "success")
        self.assertEqual(valid_report["error_count"], 0)
        self.assertTrue(valid_report["snapshot_version"])

        export_dir = PROJECT_ROOT / ".test-data" / f"admin_snapshots_{uuid4().hex}"
        exported = client.post(
            "/api/master/content/snapshot/export",
            headers=MASTER_HEADERS,
            json={"target_dir": str(export_dir)},
        )
        self.assertEqual(exported.status_code, 200, exported.text)
        exported_payload = exported.json()
        self.assertEqual(exported_payload["snapshot_version"], valid_report["snapshot_version"])
        self.assertTrue((PROJECT_ROOT / exported_payload["path"]).exists())

        invalid = client.post(
            "/api/master/content/import",
            headers=MASTER_HEADERS,
            json={"manifest_path": str(invalid_manifest), "export_snapshot": False},
        )
        self.assertEqual(invalid.status_code, 200, invalid.text)
        invalid_report = invalid.json()
        self.assertEqual(invalid_report["status"], "failed")
        self.assertGreater(invalid_report["error_count"], 0)
        first_error = invalid_report["errors"][0]
        self.assertIn("file", first_error)
        self.assertIn("row", first_error)
        self.assertIn("record_id", first_error)
        self.assertIn("code", first_error)
        self.assertIn("message", first_error)

        latest = client.get(
            "/api/master/content/import-report/latest",
            headers=MASTER_HEADERS,
        )
        self.assertEqual(latest.status_code, 200, latest.text)
        self.assertEqual(latest.json()["status"], "failed")

        overview = client.get("/api/master/admin/overview", headers=MASTER_HEADERS)
        self.assertEqual(overview.status_code, 200, overview.text)
        self.assertEqual(overview.json()["snapshot_version"], valid_report["snapshot_version"])

        qr = client.get("/api/master/content/qr-checklist", headers=MASTER_HEADERS)
        self.assertEqual(qr.status_code, 200, qr.text)
        qr_payload = qr.json()
        self.assertEqual(qr_payload["snapshot_version"], valid_report["snapshot_version"])
        self.assertEqual(qr_payload["total"], 40)
        self.assertTrue(qr_payload["policy"]["qr_honesty"])
        self.assertIn("manual_code", qr_payload["items"][0])
        self.assertIn("mode", qr_payload["items"][0])
        self.assertIn("location_node_id", qr_payload["items"][0])

        handouts = client.get("/api/master/content/handout-checklist", headers=MASTER_HEADERS)
        self.assertEqual(handouts.status_code, 200, handouts.text)
        handout_payload = handouts.json()
        self.assertEqual(handout_payload["status"], "ready")
        self.assertTrue(all(check["ready"] for check in handout_payload["policy_checks"]))
        self.assertIn("handout_common", {item["handout_id"] for item in handout_payload["items"]})

    def test_admin_npc_visibility_and_final_tools_contract(self) -> None:
        settings = self._settings("admin_npc_visibility_final")
        self._import_valid_seed(settings)
        client = TestClient(create_app(settings))

        king = client.post(
            "/api/master/npc/events",
            headers=MASTER_HEADERS,
            json={
                "npc_role": "npc_king",
                "event_type": "influence_grant",
                "target_ids": ["domain_north"],
                "consequence": {"influence_delta": 2},
                "severity": "P2",
                "operator": "gm_king",
            },
        )
        wanderer = client.post(
            "/api/master/npc/events",
            headers=MASTER_HEADERS,
            json={
                "npc_role": "npc_wanderer",
                "event_type": "dark_artifact",
                "target_ids": ["p_witcher_4"],
                "price": {"hidden_price": "owed_at_final"},
                "condition": {"must_bring": "artifact_black_seal"},
                "consequence": {"effect": "alternate_victory_hook"},
                "reputation_delta": -3,
                "severity": "P1",
                "final_flag": True,
                "operator": "gm_wanderer",
            },
        )
        raid = client.post(
            "/api/lords/p_lord_1/raids",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
            json={"target_territory_id": "territory_res_river"},
        )
        visibility_missing = client.get("/api/master/visibility-audit")
        visibility_lord = client.get("/api/master/visibility-audit", headers=LORD_HEADERS)
        visibility = client.get("/api/master/visibility-audit", headers=MASTER_HEADERS)
        master_state = client.get("/api/master/state", headers=MASTER_HEADERS)
        lord_state = client.get(
            "/api/lords/p_lord_1/state",
            headers={"X-Role-Token": "LORD-NORTH-R8K4"},
        )
        forest_state = client.get(
            "/api/lords/p_lord_3/state",
            headers={"X-Role-Token": "LORD-FOREST-P6W3"},
        )
        player_reputation = client.get(
            "/api/players/p_witcher_4/reputation",
            headers={"X-Player-Code": "WC-BEAR-3SC5"},
        )
        master_reputation = client.get(
            "/api/master/reputation/p_witcher_4",
            headers=MASTER_HEADERS,
        )
        note = client.post(
            "/api/master/final-summary/notes",
            headers=MASTER_HEADERS,
            json={
                "category": "trial",
                "target_id": "p_witcher_4",
                "note_text": "Use hidden price as final trial evidence.",
                "operator": "gm_final",
            },
        )
        final_summary = client.get("/api/master/final-summary", headers=MASTER_HEADERS)

        self.assertEqual(king.status_code, 200, king.text)
        self.assertEqual(king.json()["influence_changes"][0]["value_after"], 5)
        self.assertEqual(wanderer.status_code, 200, wanderer.text)
        self.assertEqual(wanderer.json()["deal"]["price"]["hidden_price"], "owed_at_final")
        self.assertEqual(wanderer.json()["review_route"], "before_next_act_or_final")
        self.assertEqual(raid.status_code, 200, raid.text)
        self.assertEqual(visibility_missing.status_code, 401)
        self.assertEqual(visibility_lord.status_code, 403)
        self.assertEqual(visibility.status_code, 200, visibility.text)
        self.assertEqual(master_state.status_code, 200, master_state.text)
        self.assertIn("visibility_audit", master_state.json())

        audit = visibility.json()
        self.assertEqual(audit["scope"], "master")
        self.assertTrue(audit["policy"]["master_exact_values"])
        river_garrison = next(
            item for item in audit["hidden_garrisons"] if item["garrison_id"] == "garrison_river_home"
        )
        self.assertEqual(river_garrison["card_id"], "unit_guard_t1")
        self.assertEqual(river_garrison["count"], 1)
        self.assertIn("domain_north", river_garrison["redacted_for_domain_ids"])
        raid_audit = audit["raid_effects"][0]
        self.assertEqual(raid_audit["payload"]["visibility"], "source_target_and_masters")
        self.assertEqual(
            set(raid_audit["visible_to_domain_ids"]),
            {"domain_north", "domain_river"},
        )
        artifact_audit = {
            item["artifact_id"]: item
            for item in audit["artifacts"]
        }
        self.assertEqual(artifact_audit["artifact_black_seal"]["player_visibility"], "hidden_from_players")

        self.assertEqual(lord_state.status_code, 200, lord_state.text)
        river_view = next(
            item for item in lord_state.json()["other_territories"]
            if item["territory_id"] == "territory_res_river"
        )
        self.assertEqual(river_view["garrisons"][0]["status"], "hidden_foreign_garrison")
        self.assertNotIn("count", river_view["garrisons"][0])
        self.assertEqual(forest_state.status_code, 200, forest_state.text)
        self.assertEqual(forest_state.json()["raid_effects"], [])

        self.assertEqual(player_reputation.status_code, 200)
        self.assertNotIn("value", player_reputation.json())
        self.assertEqual(master_reputation.status_code, 200)
        self.assertEqual(master_reputation.json()["value"], -3)
        self.assertTrue(master_reputation.json()["change_log"])

        self.assertEqual(note.status_code, 200, note.text)
        self.assertEqual(final_summary.status_code, 200, final_summary.text)
        summary = final_summary.json()
        self.assertTrue(summary["export"]["json_ready"])
        self.assertEqual(summary["npc_prices"][0]["price"]["hidden_price"], "owed_at_final")
        self.assertEqual(summary["master_final_notes"][0]["category"], "trial")

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

    def _auth(self, client: TestClient) -> dict[str, object]:
        response = client.post("/api/auth/role-token", json={"token": "MASTER-KING-4QZ8"})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _insert_review(self, connection, *, event_id: str, severity: str) -> None:
        ensure_event_schema(connection)
        cursor = connection.execute(
            """
            INSERT INTO events (
                event_id, device_id, actor_id, actor_type, client_sequence,
                client_created_at, event_type, status, reason, payload_json,
                metadata_json, source, received_at
            )
            VALUES (
                ?, 'admin_ops_test', 'p_witcher_1', 'player', 1,
                '2026-06-02T09:00:00+00:00', 'manual_ops_review',
                'needs_master_review', 'needs master check', '{}', '{}',
                'test_admin_game_ops', '2026-06-02T09:01:00+00:00'
            )
            """,
            (event_id,),
        )
        connection.execute(
            """
            INSERT INTO event_reviews (
                server_event_id, event_id, status, reason, severity, created_at
            )
            VALUES (?, ?, 'needs_master_review', 'needs master check', ?, '2026-06-02T09:01:00+00:00')
            """,
            (int(cursor.lastrowid), event_id, severity),
        )

    def _metrics(self, section: dict[str, object]) -> dict[str, object]:
        return {item["label"]: item["value"] for item in section["metrics"]}

    def _actions(self, section: dict[str, object]) -> dict[str, dict[str, object]]:
        return {item["id"]: item for item in section["actions"]}


if __name__ == "__main__":
    unittest.main()
