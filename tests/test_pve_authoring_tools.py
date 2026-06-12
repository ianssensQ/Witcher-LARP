from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from backend.witcher_larp.config import PROJECT_ROOT
from scripts import pve_authoring


class PveAuthoringToolsTest(unittest.TestCase):
    def test_validate_authoring_pack(self) -> None:
        report = pve_authoring.validate_authoring(PROJECT_ROOT)

        self.assertEqual(report.errors, [])
        self.assertEqual(report.summary["qr_slots"], 72)
        self.assertEqual(
            report.summary["act_counts"],
            {"act1": 20, "act2": 22, "act3": 22, "final_act": 8},
        )
        self.assertEqual(
            report.summary["qr_mode_counts"],
            {
                "always_available_scene": 9,
                "repeatable_scene": 15,
                "unique_object": 48,
            },
        )
        self.assertEqual(
            report.summary["content_lane_counts"],
            {"anti_idle": 24, "story_quest": 48},
        )
        self.assertEqual(
            set(report.summary["trial_type_counts"]),
            {"combat", "choice", "ritual_check"},
        )
        self.assertEqual(
            set(report.summary["scene_type_counts"]),
            {"monster_hunt", "moral_choice", "puzzle_check"},
        )

    def test_render_print_html_contains_local_qr_svgs(self) -> None:
        html = pve_authoring.render_print_html(PROJECT_ROOT)

        self.assertIn("PvE QR print sheet: pve72_v1", html)
        self.assertEqual(html.count('<article class="card">'), 72)
        self.assertEqual(html.count('<svg class="qr"'), 72)
        self.assertIn("QR-A1-TRV-001-K7Q2", html)
        self.assertIn("QR-FA-VUT-008-H5Q1", html)

    def test_compile_seed_writes_runtime_qr_and_pve_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            summary = pve_authoring.compile_seed_pack(PROJECT_ROOT, output_dir)
            qr_csv = (output_dir / "qr_objects.csv").read_text(encoding="utf-8")
            pve_csv = (output_dir / "pve_scenarios.csv").read_text(encoding="utf-8")

        self.assertEqual(summary["qr_objects"], 72)
        self.assertEqual(summary["pve_scenarios"], 72)
        self.assertEqual(summary["content_lane_counts"], {"anti_idle": 24, "story_quest": 48})
        self.assertIn("qr_id,manual_code,scenario_id,qr_mode", qr_csv)
        self.assertIn("qr_a1_001,QR-A1-TRV-001-K7Q2,scn_a1_001", qr_csv)
        self.assertIn("qr_fa_008,QR-FA-VUT-008-H5Q1,scn_fa_008", qr_csv)
        self.assertIn("scenario_id,act_id,tier,scene_type", pve_csv)
        self.assertIn("scenario_title", pve_csv)
        self.assertIn("trial_type", pve_csv)
        self.assertIn("visual_asset_id", pve_csv)
        self.assertIn("reward_summary", pve_csv)
        self.assertIn("board_description", pve_csv)
        self.assertIn("choice_options_json", pve_csv)
        self.assertIn("choice_morality_json", pve_csv)
        self.assertIn("encounter_steps_json", pve_csv)
        self.assertIn("victory_rule", pve_csv)
        self.assertIn("scn_fa_008,final_act,4,moral_choice", pve_csv)

    def test_freeze_roundtrip_has_no_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            freeze_path = Path(temp_dir) / "freeze.json"

            pve_authoring.write_freeze(freeze_path, PROJECT_ROOT)
            freeze = json.loads(freeze_path.read_text(encoding="utf-8"))

            self.assertEqual(freeze["schema"], "pve_qr_freeze_v1")
            self.assertEqual(freeze["row_count"], 72)
            self.assertEqual(
                pve_authoring.check_freeze(freeze_path, PROJECT_ROOT),
                [],
            )


if __name__ == "__main__":
    unittest.main()
