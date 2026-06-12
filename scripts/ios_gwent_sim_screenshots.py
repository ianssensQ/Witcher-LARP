#!/usr/bin/env python3
"""Capture repeatable iOS simulator screenshots for the Gwent UI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import struct
import sys
import time
import traceback
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT = PROJECT_ROOT / "ios" / "WitcherLARP.xcodeproj"
DEFAULT_SCREENSHOT_DIR = PROJECT_ROOT / "docs" / "ui" / "screenshots" / "ios-sim-gwent-latest"
DEFAULT_DERIVED_DATA_PATH = Path("/tmp/witcher-ios-gwent-dd")


class SimScreenshotError(RuntimeError):
    """Raised when the simulator screenshot smoke cannot complete."""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build, install and launch the iOS client in Simulator, then capture "
            "Gwent lobby and fullscreen table screenshots."
        )
    )
    parser.add_argument("--device", default="iPhone 16", help="Simulator device name.")
    parser.add_argument("--udid", default="", help="Use a specific simulator UDID.")
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--scheme", default="WitcherLARP")
    parser.add_argument("--bundle-id", default="local.witcherlarp.app")
    parser.add_argument(
        "--derived-data-path",
        type=Path,
        default=DEFAULT_DERIVED_DATA_PATH,
        help="Dedicated DerivedData path used for repeatable fresh simulator builds.",
    )
    parser.add_argument("--app-path", type=Path, help="Use a known built .app path instead of xcodebuild settings.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_SCREENSHOT_DIR)
    parser.add_argument("--skip-build", action="store_true", help="Use the existing DerivedData app.")
    parser.add_argument("--skip-install", action="store_true", help="Launch the app already installed on Simulator.")
    parser.add_argument("--assume-booted", action="store_true", help="Skip Simulator boot/discovery checks for a known booted UDID.")
    parser.add_argument(
        "--restart-device",
        action="store_true",
        help="Soft-restart the selected Simulator device before install/launch.",
    )
    parser.add_argument(
        "--uninstall-before-install",
        action="store_true",
        help="Remove the existing app from Simulator before installing the built app.",
    )
    parser.add_argument("--wait-seconds", type=float, default=12.0)
    parser.add_argument(
        "--command-timeout",
        type=float,
        default=90.0,
        help="Maximum seconds to wait for an individual xcodebuild/simctl command.",
    )
    parser.add_argument("--json-summary", type=Path)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate existing screenshots without booting or launching Simulator.",
    )
    parser.add_argument("--lobby-screenshot", type=Path, help="Existing Gwent lobby screenshot.")
    parser.add_argument("--table-screenshot", type=Path, help="Existing fullscreen Gwent table screenshot.")
    args = parser.parse_args(argv)

    summary: dict[str, Any] = {
        "status": "failed",
        "device": args.device,
        "project": str(args.project),
        "scheme": args.scheme,
        "bundle_id": args.bundle_id,
        "derived_data_path": str(args.derived_data_path) if args.derived_data_path else None,
        "output_dir": str(args.output_dir),
        "steps": [],
    }
    summary_path = args.json_summary or (args.output_dir / "summary.json")

    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if args.validate_only:
            lobby = args.lobby_screenshot or (args.output_dir / "gwent-lobby.png")
            table = args.table_screenshot or (args.output_dir / "gwent-table-landscape.png")
            summary["screenshots"] = validate_screenshots(lobby, table)
            summary["status"] = "passed"
            print(f"OK: validated Gwent screenshots in {args.output_dir}")
            return 0

        udid = args.udid.strip() or find_device_udid(args.device, args.command_timeout)
        summary["udid"] = udid
        summary["steps"].append({"name": "device_selected", "udid": udid})

        if not args.skip_build:
            run(
                xcodebuild_command(args.project, args.scheme, args.derived_data_path, ["build"]),
                summary,
                "build",
                timeout_seconds=args.command_timeout,
            )

        app_path = args.app_path or resolve_app_path(
            args.project,
            args.scheme,
            args.derived_data_path,
            args.command_timeout,
        )
        summary["app_path"] = str(app_path)
        if not app_path.exists():
            raise SimScreenshotError(f"Built app does not exist: {app_path}")

        if args.restart_device:
            run(
                ["xcrun", "simctl", "shutdown", udid],
                summary,
                "restart_shutdown",
                allow_failure=True,
                timeout_seconds=args.command_timeout,
            )
            run(
                ["xcrun", "simctl", "boot", udid],
                summary,
                "restart_boot",
                timeout_seconds=args.command_timeout,
            )
            run(
                ["xcrun", "simctl", "bootstatus", udid, "-b"],
                summary,
                "restart_bootstatus",
                timeout_seconds=args.command_timeout,
            )

        initial_state = "Booted" if args.assume_booted else device_state(udid, args.command_timeout)
        summary["steps"].append({"name": "device_state_before_boot", "state": initial_state})
        if initial_state == "Booted":
            summary["steps"].append({"name": "boot", "skipped": True, "reason": "device already Booted"})
        else:
            run(
                ["xcrun", "simctl", "boot", udid],
                summary,
                "boot",
                allow_failure=True,
                timeout_seconds=args.command_timeout,
            )
        state = "Booted" if args.assume_booted else device_state(udid, args.command_timeout)
        summary["steps"].append({"name": "device_state_after_boot", "state": state})
        if state == "Booted":
            summary["steps"].append({"name": "bootstatus", "skipped": True, "reason": "device already Booted"})
        else:
            run(
                ["xcrun", "simctl", "bootstatus", udid, "-b"],
                summary,
                "bootstatus",
                timeout_seconds=args.command_timeout,
            )
        if args.skip_install:
            summary["steps"].append({"name": "install", "skipped": True, "reason": "--skip-install"})
        else:
            run(
                ["xcrun", "simctl", "terminate", udid, args.bundle_id],
                summary,
                "preinstall_terminate",
                allow_failure=True,
                timeout_seconds=min(args.command_timeout, 8.0),
            )
            if args.uninstall_before_install:
                run(
                    ["xcrun", "simctl", "uninstall", udid, args.bundle_id],
                    summary,
                    "preinstall_uninstall",
                    allow_failure=True,
                    timeout_seconds=args.command_timeout,
                )
            run(
                ["xcrun", "simctl", "install", udid, str(app_path)],
                summary,
                "install",
                timeout_seconds=args.command_timeout,
            )

        lobby = args.output_dir / "gwent-lobby.png"
        table = args.output_dir / "gwent-table-landscape.png"
        capture_app_state(
            udid,
            args.bundle_id,
            ["--demo-snapshot", "--initial-tab", "gwent"],
            lobby,
            args.wait_seconds,
            summary,
            "gwent_lobby",
            args.command_timeout,
        )
        summary["steps"].append(
            {
                "name": "rotate_landscape",
                "skipped": True,
                "reason": "GwentTableView requests landscape orientation in-app",
            }
        )
        capture_app_state(
            udid,
            args.bundle_id,
            ["--demo-snapshot", "--initial-tab", "gwent", "--show-gwent-table"],
            table,
            args.wait_seconds,
            summary,
            "gwent_table",
            args.command_timeout,
        )
        normalize_landscape_framebuffer(table, summary, args.command_timeout)
        summary["screenshots"] = validate_screenshots(lobby, table)
        summary["status"] = "passed"
        print(f"OK: captured Gwent simulator screenshots in {args.output_dir}")
        return 0
    except Exception as exc:
        summary["error"] = str(exc)
        summary["traceback_tail"] = traceback.format_exc()[-4000:]
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"summary: {summary_path}")


def find_device_udid(device_name: str, timeout_seconds: float | None) -> str:
    completed, timed_out = run_process(
        ["xcrun", "simctl", "list", "devices", "available", "-j"],
        timeout_seconds=timeout_seconds,
        stderr_to_stdout=False,
    )
    if timed_out:
        raise SimScreenshotError(f"simctl list devices timed out after {timeout_seconds:g}s")
    if completed.returncode != 0:
        raise SimScreenshotError(completed.stderr.strip() or "simctl list devices failed")
    payload = json.loads(completed.stdout)
    for devices in payload.get("devices", {}).values():
        for device in devices:
            if device.get("name") == device_name and device.get("isAvailable") is True:
                return str(device["udid"])
    raise SimScreenshotError(f"No available simulator named {device_name!r}")


def device_state(udid: str, timeout_seconds: float | None) -> str | None:
    completed, timed_out = run_process(
        ["xcrun", "simctl", "list", "devices", "available", "-j"],
        timeout_seconds=timeout_seconds,
        stderr_to_stdout=False,
    )
    if timed_out:
        return None
    if completed.returncode != 0:
        return None
    payload = json.loads(completed.stdout)
    for devices in payload.get("devices", {}).values():
        for device in devices:
            if device.get("udid") == udid:
                return str(device.get("state") or "")
    return None


def xcodebuild_command(
    project: Path,
    scheme: str,
    derived_data_path: Path | None,
    action: list[str],
) -> list[str]:
    command = [
        "xcodebuild",
        "-project",
        str(project),
        "-scheme",
        scheme,
        "-sdk",
        "iphonesimulator",
        "-destination",
        "generic/platform=iOS Simulator",
    ]
    if derived_data_path is not None:
        command.extend(["-derivedDataPath", str(derived_data_path)])
    command.extend(action)
    return command


def resolve_app_path(
    project: Path,
    scheme: str,
    derived_data_path: Path | None,
    timeout_seconds: float | None,
) -> Path:
    completed, timed_out = run_process(
        xcodebuild_command(project, scheme, derived_data_path, ["-showBuildSettings"]),
        timeout_seconds=timeout_seconds,
    )
    if timed_out:
        raise SimScreenshotError(f"xcodebuild -showBuildSettings timed out after {timeout_seconds:g}s")
    if completed.returncode != 0:
        raise SimScreenshotError(completed.stdout[-2000:])
    settings: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if " = " not in line:
            continue
        key, value = line.split(" = ", 1)
        settings[key.strip()] = value.strip()
    target_build_dir = settings.get("TARGET_BUILD_DIR")
    full_product_name = settings.get("FULL_PRODUCT_NAME")
    if not target_build_dir or not full_product_name:
        raise SimScreenshotError("Could not resolve TARGET_BUILD_DIR/FULL_PRODUCT_NAME from xcodebuild.")
    return Path(target_build_dir) / full_product_name


def capture_app_state(
    udid: str,
    bundle_id: str,
    launch_args: list[str],
    screenshot_path: Path,
    wait_seconds: float,
    summary: dict[str, Any],
    name: str,
    command_timeout: float,
) -> None:
    run(
        ["xcrun", "simctl", "terminate", udid, bundle_id],
        summary,
        f"{name}_terminate",
        allow_failure=True,
        timeout_seconds=min(command_timeout, 5.0),
    )
    run(
        ["xcrun", "simctl", "launch", udid, bundle_id, *launch_args],
        summary,
        f"{name}_launch",
        timeout_seconds=command_timeout,
    )
    time.sleep(wait_seconds)
    run(
        ["xcrun", "simctl", "io", udid, "screenshot", str(screenshot_path)],
        summary,
        f"{name}_screenshot",
        timeout_seconds=command_timeout,
    )


def normalize_landscape_framebuffer(
    table: Path,
    summary: dict[str, Any],
    command_timeout: float | None,
) -> None:
    width, height = png_dimensions(table)
    if width > height:
        summary["steps"].append(
            {
                "name": "normalize_gwent_table_landscape",
                "skipped": True,
                "reason": "captured screenshot is already landscape",
                "width": width,
                "height": height,
            }
        )
        return

    raw_table = table.with_name(f"{table.stem}-raw-portrait{table.suffix}")
    if raw_table.exists():
        raw_table.unlink()
    table.rename(raw_table)
    run(
        ["sips", "-r", "-90", str(raw_table), "--out", str(table)],
        summary,
        "normalize_gwent_table_landscape",
        timeout_seconds=command_timeout,
    )
    normalized_width, normalized_height = png_dimensions(table)
    if normalized_width <= normalized_height:
        raise SimScreenshotError(
            f"Could not normalize Gwent table screenshot to landscape: "
            f"{table} ({normalized_width}x{normalized_height})"
        )
    summary["steps"].append(
        {
            "name": "normalize_gwent_table_raw_framebuffer",
            "raw_path": str(raw_table),
            "normalized_path": str(table),
            "raw_width": width,
            "raw_height": height,
            "normalized_width": normalized_width,
            "normalized_height": normalized_height,
        }
    )


def validate_screenshots(lobby: Path, table: Path) -> dict[str, Any]:
    return {
        "gwent_lobby": validate_png_screenshot(lobby, expected_orientation="portrait"),
        "gwent_table": validate_png_screenshot(table, expected_orientation="landscape"),
    }


def validate_png_screenshot(
    path: Path,
    *,
    expected_orientation: str,
    min_file_bytes: int = 120_000,
    min_short_side_px: int = 300,
) -> dict[str, Any]:
    if not path.exists():
        raise SimScreenshotError(f"Screenshot does not exist: {path}")
    file_size = path.stat().st_size
    if file_size < min_file_bytes:
        raise SimScreenshotError(
            f"Screenshot is too small to be credible UI evidence: {path} ({file_size} bytes)"
        )
    width, height = png_dimensions(path)
    if min(width, height) < min_short_side_px:
        raise SimScreenshotError(f"Screenshot is too small: {path} ({width}x{height})")
    actual_orientation = "landscape" if width > height else "portrait" if height > width else "square"
    if actual_orientation != expected_orientation:
        raise SimScreenshotError(
            f"Screenshot has wrong orientation for {path.name}: expected "
            f"{expected_orientation}, got {actual_orientation} ({width}x{height}). "
            "For the fullscreen Gwent table, rotate the simulator before capture."
        )
    return {
        "path": str(path),
        "width": width,
        "height": height,
        "orientation": actual_orientation,
        "file_size": file_size,
    }


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise SimScreenshotError(f"Not a PNG screenshot: {path}")
    return struct.unpack(">II", header[16:24])


def run(
    command: list[str],
    summary: dict[str, Any],
    name: str,
    *,
    allow_failure: bool = False,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    completed, timed_out = run_process(command, timeout_seconds=timeout_seconds)
    output = completed.stdout or ""
    if timed_out:
        summary["steps"].append(
            {
                "name": name,
                "command": command,
                "returncode": completed.returncode,
                "timed_out_after_seconds": timeout_seconds,
                "output_tail": output[-2000:],
            }
        )
        if allow_failure:
            return completed
        raise SimScreenshotError(
            f"{name} timed out after {timeout_seconds:g}s: {output[-1200:] or 'no output'}"
        )
    summary["steps"].append(
        {
            "name": name,
            "command": command,
            "returncode": completed.returncode,
            "output_tail": output[-2000:],
        }
    )
    if completed.returncode != 0 and not allow_failure:
        raise SimScreenshotError(f"{name} failed with code {completed.returncode}: {output[-1200:]}")
    return completed


def run_process(
    command: list[str],
    *,
    timeout_seconds: float | None,
    stderr_to_stdout: bool = True,
) -> tuple[subprocess.CompletedProcess[str], bool]:
    output = ""
    error_output = ""
    timed_out = False
    returncode = 124
    try:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if stderr_to_stdout else subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(command, 126, "", str(exc)), False
    try:
        output, error_output = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        output = _text(exc.stdout)
        error_output = "" if stderr_to_stdout else _text(exc.stderr)
        _terminate_process_group(process)
        try:
            extra_output, _ = process.communicate(timeout=2)
            output += extra_output or ""
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            try:
                extra_output, _ = process.communicate(timeout=2)
                output += extra_output or ""
            except subprocess.TimeoutExpired:
                pass
        else:
            returncode = process.returncode
        if process.returncode is not None:
            returncode = process.returncode

    completed = subprocess.CompletedProcess(
        command,
        returncode if timed_out else process.returncode,
        output or "",
        error_output or "",
    )
    return completed, timed_out


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def _kill_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
