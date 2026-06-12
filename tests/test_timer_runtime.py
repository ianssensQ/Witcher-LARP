from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest
from uuid import uuid4

from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.config import PROJECT_ROOT, Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack
from backend.witcher_larp.lord_runtime import ensure_lord_runtime_state
from backend.witcher_larp.sorceress_service import record_alignment_evidence
from backend.witcher_larp.timer_service import apply_due_timers


TEST_TMP_ROOT = PROJECT_ROOT / ".test-data"
FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"


class TimerRuntimeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TMP_ROOT.mkdir(exist_ok=True)

    def test_mana_income_first_tick_is_relative_to_actual_act_start(self) -> None:
        cases = (
            ("act1", datetime(2026, 6, 2, 10, 7, tzinfo=UTC), "timer_income_act1"),
            ("act2", datetime(2026, 6, 2, 12, 46, tzinfo=UTC), "timer_income_act2"),
            ("act3", datetime(2026, 6, 2, 15, 13, tzinfo=UTC), "timer_income_act3"),
        )
        for act_id, started_at, timer_id in cases:
            with self.subTest(act_id=act_id):
                settings = self._settings(f"timer_{act_id}")
                self._import_valid_seed(settings)
                with connect(settings) as connection:
                    start_act(
                        connection,
                        settings,
                        act_id,
                        operator="gm_timer",
                        physical_announcement_state="announced",
                        now=started_at,
                    )
                    before = apply_due_timers(connection, settings, now=started_at + timedelta(minutes=29))
                    due = apply_due_timers(connection, settings, now=started_at + timedelta(minutes=30))
                    before_second = apply_due_timers(
                        connection,
                        settings,
                        now=started_at + timedelta(minutes=59),
                    )
                    second_due = apply_due_timers(
                        connection,
                        settings,
                        now=started_at + timedelta(minutes=60),
                    )
                    stored_rows = connection.execute(
                        """
                        SELECT timer_id, due_at
                        FROM applied_timer_ticks
                        WHERE timer_id = ?
                        ORDER BY due_at
                        """,
                        (timer_id,),
                    ).fetchall()

                self.assertEqual(before, [])
                self.assertEqual([tick["effect_type"] for tick in due], ["lord_income_and_mana"])
                self.assertEqual(due[0]["domain_updates"][0]["influence_gain"], 1)
                self.assertEqual(before_second, [])
                self.assertEqual(
                    [tick["effect_type"] for tick in second_due],
                    ["lord_income_and_mana"],
                )
                self.assertEqual(
                    [row["due_at"] for row in stored_rows],
                    [
                        (started_at + timedelta(minutes=30)).isoformat(timespec="seconds"),
                        (started_at + timedelta(minutes=60)).isoformat(timespec="seconds"),
                    ],
                )

    def test_mana_regen_uses_runtime_owner_and_current_patron(self) -> None:
        settings = self._settings("timer_mana_runtime_owner")
        self._import_valid_seed(settings)
        started_at = datetime(2026, 6, 2, 10, 7, tzinfo=UTC)

        with connect(settings) as connection:
            start_act(
                connection,
                settings,
                "act1",
                operator="gm_timer",
                physical_announcement_state="announced",
                now=started_at,
            )
            ensure_lord_runtime_state(connection)
            connection.execute(
                """
                UPDATE territories
                SET owner_domain_id = 'domain_forest'
                WHERE territory_id = 'territory_magic_corner'
                """
            )
            connection.execute(
                """
                UPDATE territory_runtime_state
                SET owner_domain_id = 'domain_river',
                    status = 'controlled',
                    contested_by_domain_id = NULL,
                    updated_at = ?
                WHERE territory_id = 'territory_magic_corner'
                """,
                (started_at.isoformat(timespec="seconds"),),
            )
            record_alignment_evidence(
                connection,
                sorceress_id="p_sorc_1",
                alignment_state="declared_new_patron",
                evidence_type="public_declaration_or_trade",
                payload={"patron_lord_id": "p_lord_2"},
                now=started_at,
            )

            due = apply_due_timers(connection, settings, now=started_at + timedelta(minutes=30))
            mana_rows = connection.execute(
                """
                SELECT player_id, mana
                FROM player_runtime_state
                WHERE player_id IN ('p_sorc_1', 'p_sorc_2', 'p_sorc_3')
                ORDER BY player_id
                """
            ).fetchall()

        mana = {row["player_id"]: row["mana"] for row in mana_rows}
        updates = {row["player_id"]: row for row in due[0]["sorceress_updates"]}
        self.assertEqual(mana, {"p_sorc_1": 3, "p_sorc_2": 3, "p_sorc_3": 2})
        self.assertEqual(updates["p_sorc_1"]["patron_domain_id"], "domain_river")
        self.assertEqual(updates["p_sorc_1"]["bonus_sources"], ["territory_magic_corner"])
        self.assertEqual(updates["p_sorc_2"]["patron_domain_id"], "domain_river")
        self.assertEqual(updates["p_sorc_3"]["patron_domain_id"], "domain_forest")

    def _settings(self, name: str) -> Settings:
        return Settings(database_path=TEST_TMP_ROOT / f"{name}_{uuid4().hex}.db")

    def _import_valid_seed(self, settings: Settings) -> None:
        report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
        self.assertEqual(report.status, "success")


if __name__ == "__main__":
    unittest.main()
