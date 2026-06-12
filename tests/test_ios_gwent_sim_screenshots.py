import importlib.util
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "ios_gwent_sim_screenshots.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("ios_gwent_sim_screenshots", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_png_header(path: Path, width: int, height: int) -> None:
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height))


class IosGwentSimScreenshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = load_script_module()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_png_dimensions_reads_ihdr_size(self) -> None:
        screenshot = self.root / "screenshot.png"
        write_png_header(screenshot, 1334, 750)

        self.assertEqual(self.script.png_dimensions(screenshot), (1334, 750))

    def test_validate_png_screenshot_rejects_wrong_orientation(self) -> None:
        screenshot = self.root / "table.png"
        write_png_header(screenshot, 750, 1334)

        with self.assertRaisesRegex(self.script.SimScreenshotError, "wrong orientation"):
            self.script.validate_png_screenshot(
                screenshot,
                expected_orientation="landscape",
                min_file_bytes=1,
            )

    def test_validate_png_screenshot_rejects_tiny_png(self) -> None:
        screenshot = self.root / "blank-ish.png"
        write_png_header(screenshot, 1334, 750)

        with self.assertRaisesRegex(self.script.SimScreenshotError, "too small"):
            self.script.validate_png_screenshot(screenshot, expected_orientation="landscape")

    def test_default_wait_allows_first_swiftui_frame(self) -> None:
        script = SCRIPT_PATH.read_text(encoding="utf-8")

        self.assertIn('parser.add_argument("--wait-seconds", type=float, default=12.0)', script)

    def test_validate_png_screenshot_accepts_landscape(self) -> None:
        screenshot = self.root / "table.png"
        write_png_header(screenshot, 1334, 750)

        result = self.script.validate_png_screenshot(
            screenshot,
            expected_orientation="landscape",
            min_file_bytes=1,
        )

        self.assertEqual(result["orientation"], "landscape")
        self.assertEqual(result["width"], 1334)
        self.assertEqual(result["height"], 750)

    def test_normalize_landscape_framebuffer_rotates_portrait_raw_capture(self) -> None:
        screenshot = self.root / "table.png"
        write_png_header(screenshot, 750, 1334)
        summary = {"steps": []}

        def fake_run(command, summary, name, **_kwargs):
            self.assertEqual(name, "normalize_gwent_table_landscape")
            self.assertEqual(command[0], "sips")
            self.assertEqual(command[1:3], ["-r", "-90"])
            out_index = command.index("--out")
            write_png_header(Path(command[out_index + 1]), 1334, 750)
            summary["steps"].append(
                {
                    "name": name,
                    "command": command,
                    "returncode": 0,
                    "output_tail": "",
                }
            )
            return subprocess.CompletedProcess(command, 0, "", "")

        self.script.run = fake_run

        self.script.normalize_landscape_framebuffer(screenshot, summary, command_timeout=1)

        raw = self.root / "table-raw-portrait.png"
        self.assertTrue(raw.exists())
        self.assertEqual(self.script.png_dimensions(raw), (750, 1334))
        self.assertEqual(self.script.png_dimensions(screenshot), (1334, 750))
        self.assertEqual(summary["steps"][-1]["raw_path"], str(raw))

    def test_run_process_times_out_hung_command(self) -> None:
        completed, timed_out = self.script.run_process(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout_seconds=0.05,
        )

        self.assertTrue(timed_out)
        self.assertNotEqual(completed.returncode, 0)

    def test_run_process_reports_oserror_as_completed_process(self) -> None:
        completed, timed_out = self.script.run_process(
            [str(self.root / "missing-command")],
            timeout_seconds=0.05,
        )

        self.assertFalse(timed_out)
        self.assertEqual(completed.returncode, 126)
        self.assertIn("No such file", completed.stderr)


if __name__ == "__main__":
    unittest.main()
