#!/usr/bin/env python3
"""Run the no-PvP iOS machine gate and optionally verify real-iPhone evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import plistlib
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SERVER = "http://192.168.68.118:8002"
REAL_DEVICE_CHECKS = [
    "installed_release_build",
    "local_network_permission_allowed",
    "camera_permission_allowed",
    "login_against_8002",
    "snapshot_survives_restart",
    "physical_qr_scanned",
    "offline_event_survives_restart",
    "sync_retry_success",
]


class GateError(RuntimeError):
    """Raised when a required release-gate check fails."""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the no-PvP iOS machine gate: scaffold tests, Debug/Release "
            "builds and live iOS API smoke on port 8002. Real iPhone evidence "
            "is verified when provided."
        )
    )
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP smoke timeout.")
    parser.add_argument("--command-timeout", type=float, default=120.0)
    parser.add_argument("--skip-builds", action="store_true")
    parser.add_argument("--skip-http", action="store_true")
    parser.add_argument(
        "--include-sim-visual-smoke",
        action="store_true",
        help="Install the Release simulator app into a booted Simulator and screenshot seeded Home UI.",
    )
    parser.add_argument("--sim-device", default="booted", help="Simulator UDID or 'booted'.")
    parser.add_argument("--sim-visual-wait", type=float, default=6.0)
    parser.add_argument("--include-qr-lookup", action="store_true")
    parser.add_argument("--include-empty-sync", action="store_true")
    parser.add_argument(
        "--device-id",
        help="Optional connected iPhone destination id for device-target Release builds.",
    )
    parser.add_argument(
        "--signed-device-build",
        action="store_true",
        help="Also build a signed Release app for --device-id and report signing/provisioning metadata.",
    )
    parser.add_argument(
        "--install-signed-device-app",
        action="store_true",
        help="Install the signed Release app on --device-id with devicectl. Requires --signed-device-build.",
    )
    parser.add_argument("--real-device-evidence", type=Path)
    parser.add_argument("--require-real-device-evidence", action="store_true")
    parser.add_argument("--write-real-device-template", type=Path)
    args = parser.parse_args(argv)

    if args.signed_device_build and not args.device_id:
        parser.error("--signed-device-build requires --device-id")
    if args.install_signed_device_app and not args.signed_device_build:
        parser.error("--install-signed-device-app requires --signed-device-build")
    if args.include_sim_visual_smoke and args.skip_builds:
        parser.error("--include-sim-visual-smoke requires Release simulator build output")

    if args.write_real_device_template:
        _write_real_device_template(args.write_real_device_template, args.server)

    artifact_dir = args.artifact_dir or Path(
        f"/private/tmp/ios-no-pvp-release-gate-{int(time.time())}"
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "status": "failed",
        "ready_for_players": False,
        "server": args.server,
        "artifact_dir": str(artifact_dir),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "steps": [],
        "real_device_required_checks": REAL_DEVICE_CHECKS,
    }
    machine_real_device_checks: dict[str, bool] = {}
    python = _python_executable()
    report["python"] = python

    try:
        _run(
            report,
            "py_compile_no_pvp_smoke",
            [
                python,
                "-m",
                "py_compile",
                "scripts/ios_no_pvp_http_smoke.py",
                "scripts/ios_no_pvp_sim_visual_smoke.py",
            ],
            timeout=args.command_timeout,
        )
        _run(
            report,
            "ios_scaffold_tests",
            [python, "-m", "pytest", "tests/test_ios_project_scaffold.py", "-q"],
            timeout=args.command_timeout,
        )

        if not args.skip_builds:
            _run(
                report,
                "xcodebuild_debug",
                [
                    "xcodebuild",
                    "-quiet",
                    "-project",
                    "ios/WitcherLARP.xcodeproj",
                    "-scheme",
                    "WitcherLARP",
                    "-sdk",
                    "iphonesimulator",
                    "-configuration",
                    "Debug",
                    "-derivedDataPath",
                    str(artifact_dir / "debug-dd"),
                    "CODE_SIGNING_ALLOWED=NO",
                    "build",
                ],
                timeout=max(args.command_timeout, 180.0),
            )
            _run(
                report,
                "xcodebuild_release",
                [
                    "xcodebuild",
                    "-quiet",
                    "-project",
                    "ios/WitcherLARP.xcodeproj",
                    "-scheme",
                    "WitcherLARP",
                    "-sdk",
                    "iphonesimulator",
                    "-configuration",
                    "Release",
                    "-derivedDataPath",
                    str(artifact_dir / "release-dd"),
                    "CODE_SIGNING_ALLOWED=NO",
                    "build",
                ],
                timeout=max(args.command_timeout, 180.0),
            )
            if args.include_sim_visual_smoke:
                sim_visual_report = artifact_dir / "ios-no-pvp-sim-visual-smoke.json"
                _run(
                    report,
                    "ios_no_pvp_sim_visual_smoke",
                    [
                        python,
                        "scripts/ios_no_pvp_sim_visual_smoke.py",
                        "--server",
                        args.server,
                        "--timeout",
                        str(args.timeout),
                        "--device",
                        args.sim_device,
                        "--wait",
                        str(args.sim_visual_wait),
                        "--app",
                        str(
                            artifact_dir
                            / "release-dd"
                            / "Build"
                            / "Products"
                            / "Release-iphonesimulator"
                            / "WitcherLARP.app"
                        ),
                        "--artifact-dir",
                        str(artifact_dir / "sim-visual"),
                        "--json-report",
                        str(sim_visual_report),
                    ],
                    timeout=max(args.command_timeout, 90.0),
                    extra={"json_report": str(sim_visual_report)},
                )
            if args.device_id:
                _run(
                    report,
                    "xcodebuild_release_device",
                    [
                        "xcodebuild",
                        "-quiet",
                        "-project",
                        "ios/WitcherLARP.xcodeproj",
                        "-scheme",
                        "WitcherLARP",
                        "-configuration",
                        "Release",
                        "-destination",
                        f"id={args.device_id}",
                        "-derivedDataPath",
                        str(artifact_dir / "device-release-dd"),
                        "CODE_SIGNING_ALLOWED=NO",
                        "build",
                    ],
                    timeout=max(args.command_timeout, 180.0),
                )
            if args.signed_device_build and args.device_id:
                _run(
                    report,
                    "xcodebuild_signed_release_device",
                    [
                        "xcodebuild",
                        "-quiet",
                        "-project",
                        "ios/WitcherLARP.xcodeproj",
                        "-scheme",
                        "WitcherLARP",
                        "-configuration",
                        "Release",
                        "-destination",
                        f"id={args.device_id}",
                        "-derivedDataPath",
                        str(artifact_dir / "signed-device-release-dd"),
                        "build",
                    ],
                    timeout=max(args.command_timeout, 180.0),
                )
                app_path = (
                    artifact_dir
                    / "signed-device-release-dd"
                    / "Build"
                    / "Products"
                    / "Release-iphoneos"
                    / "WitcherLARP.app"
                )
                report["signed_device_app"] = _collect_signed_app_summary(
                    app_path,
                    device_id=args.device_id,
                    timeout=max(args.command_timeout, 30.0),
                )
                if args.install_signed_device_app:
                    install_json = artifact_dir / "devicectl-install-signed-device-app.json"
                    _run(
                        report,
                        "devicectl_install_signed_device_app",
                        [
                            "xcrun",
                            "devicectl",
                            "device",
                            "install",
                            "app",
                            "--device",
                            args.device_id,
                            str(app_path),
                            "--json-output",
                            str(install_json),
                            "--timeout",
                            str(int(max(args.command_timeout, 60.0))),
                        ],
                        timeout=max(args.command_timeout, 60.0),
                        extra={"json_report": str(install_json)},
                    )
                    machine_real_device_checks["installed_release_build"] = True
        else:
            _skip(report, "xcodebuild_debug")
            _skip(report, "xcodebuild_release")
            if args.device_id:
                _skip(report, "xcodebuild_release_device")
            if args.signed_device_build:
                _skip(report, "xcodebuild_signed_release_device")
            if args.install_signed_device_app:
                _skip(report, "devicectl_install_signed_device_app")
            if args.include_sim_visual_smoke:
                _skip(report, "ios_no_pvp_sim_visual_smoke")

        if not args.skip_http:
            smoke_report = artifact_dir / "ios-no-pvp-http-smoke.json"
            smoke_command = [
                python,
                "scripts/ios_no_pvp_http_smoke.py",
                "--server",
                args.server,
                "--timeout",
                str(args.timeout),
                "--json-report",
                str(smoke_report),
            ]
            if args.include_qr_lookup:
                smoke_command.append("--include-qr-lookup")
            if args.include_empty_sync:
                smoke_command.append("--include-empty-sync")
            _run(
                report,
                "ios_no_pvp_http_smoke",
                smoke_command,
                timeout=max(args.command_timeout, 30.0),
                extra={"json_report": str(smoke_report)},
            )
        else:
            _skip(report, "ios_no_pvp_http_smoke")

        report["machine_real_device_checks"] = {
            key: value for key, value in sorted(machine_real_device_checks.items())
        }
        evidence = _load_real_device_evidence(
            args.real_device_evidence,
            args.server,
            machine_checks=machine_real_device_checks,
        )
        report["real_device_evidence"] = evidence
        missing_evidence = evidence["missing"] or evidence["failed"]
        if missing_evidence:
            report["status"] = "machine_passed_real_device_required"
            if args.require_real_device_evidence:
                raise GateError("real iPhone evidence is missing or incomplete")
            print("[todo] real iPhone smoke evidence is still required")
        else:
            report["status"] = "passed"
            report["ready_for_players"] = True
            print("[ok] real iPhone smoke evidence verified")

        return 0
    except Exception as exc:
        report["error"] = str(exc)
        print(f"[fail] {exc}", file=sys.stderr)
        return 1
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        report_path = artifact_dir / "ios-no-pvp-release-gate.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"[report] {report_path}")


def _run(
    report: dict[str, Any],
    name: str,
    command: list[str],
    *,
    timeout: float,
    extra: dict[str, Any] | None = None,
) -> None:
    print(f"[run] {name}")
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=_subprocess_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    step = {
        "name": name,
        "command": command,
        "returncode": completed.returncode,
        "output_tail": completed.stdout[-4000:],
    }
    if extra:
        step.update(extra)
    report["steps"].append(step)
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
        raise GateError(f"{name} failed with code {completed.returncode}")
    print(f"[ok] {name}")


def _skip(report: dict[str, Any], name: str) -> None:
    report["steps"].append({"name": name, "status": "skipped"})
    print(f"[skip] {name}")


def _python_executable() -> str:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONPYCACHEPREFIX", "/private/tmp/witcher-larp-pycache")
    return env


def _collect_signed_app_summary(app_path: Path, *, device_id: str, timeout: float) -> dict[str, Any]:
    if not app_path.exists():
        raise GateError(f"signed app was not produced: {app_path}")

    info = plistlib.loads((app_path / "Info.plist").read_bytes())
    codesign = subprocess.run(
        ["codesign", "-dv", "--verbose=4", str(app_path)],
        cwd=PROJECT_ROOT,
        env=_subprocess_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    if codesign.returncode != 0:
        raise GateError(f"codesign metadata read failed with code {codesign.returncode}")

    codesign_values = _parse_key_value_lines(codesign.stdout)
    profile = _load_embedded_mobileprovision(app_path / "embedded.mobileprovision")
    entitlements = profile.get("Entitlements", {})
    provisioned_devices = [str(value) for value in profile.get("ProvisionedDevices", [])]
    team_ids = [str(value) for value in profile.get("TeamIdentifier", [])]

    return {
        "app_path": str(app_path),
        "bundle_identifier": info.get("CFBundleIdentifier"),
        "display_name": info.get("CFBundleDisplayName"),
        "minimum_os_version": info.get("MinimumOSVersion"),
        "platform": info.get("DTPlatformName"),
        "sdk": info.get("DTSDKName"),
        "codesign_identifier": codesign_values.get("Identifier"),
        "codesign_team_identifier": codesign_values.get("TeamIdentifier"),
        "codesign_format": codesign_values.get("Format"),
        "profile_name": profile.get("Name"),
        "profile_uuid": profile.get("UUID"),
        "profile_expiration": _jsonable(profile.get("ExpirationDate")),
        "profile_time_to_live_days": profile.get("TimeToLive"),
        "profile_local_provision": profile.get("LocalProvision"),
        "profile_team_identifiers": team_ids,
        "profile_provisioned_device_count": len(provisioned_devices),
        "profile_contains_destination_device": device_id in provisioned_devices,
        "entitlement_application_identifier": entitlements.get("application-identifier"),
        "entitlement_get_task_allow": entitlements.get("get-task-allow"),
    }


def _parse_key_value_lines(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _load_embedded_mobileprovision(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise GateError(f"embedded.mobileprovision is missing: {path}")
    data = path.read_bytes()
    start = data.find(b"<?xml")
    end = data.find(b"</plist>")
    if start < 0 or end < 0:
        raise GateError(f"embedded.mobileprovision does not contain a plist: {path}")
    return plistlib.loads(data[start:end + len(b"</plist>")])


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    return value


def _load_real_device_evidence(
    path: Path | None,
    server: str,
    *,
    machine_checks: dict[str, bool] | None = None,
) -> dict[str, Any]:
    machine_proven = {
        check: True
        for check, value in (machine_checks or {}).items()
        if check in REAL_DEVICE_CHECKS and value is True
    }
    if path is None:
        checks = dict(machine_proven)
        missing = [check for check in REAL_DEVICE_CHECKS if check not in checks]
        return {
            "path": None,
            "status": "passed" if not missing else ("incomplete" if checks else "missing"),
            "machine_proven": sorted(machine_proven),
            "missing": missing,
            "failed": [],
        }
    if not path.exists():
        checks = dict(machine_proven)
        missing = [check for check in REAL_DEVICE_CHECKS if check not in checks]
        return {
            "path": str(path),
            "status": "passed" if not missing else ("incomplete" if checks else "missing"),
            "machine_proven": sorted(machine_proven),
            "missing": missing,
            "failed": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    checks = dict(payload.get("checks", {}))
    checks.update(machine_proven)
    missing = [check for check in REAL_DEVICE_CHECKS if check not in checks]
    failed = [check for check in REAL_DEVICE_CHECKS if check in checks and checks[check] is not True]
    if payload.get("server") != server:
        failed.append("server_matches_8002")
    return {
        "path": str(path),
        "status": "passed" if not missing and not failed else "incomplete",
        "device": payload.get("device"),
        "tester": payload.get("tester"),
        "server": payload.get("server"),
        "machine_proven": sorted(machine_proven),
        "missing": missing,
        "failed": failed,
    }


def _write_real_device_template(path: Path, server: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    template = {
        "server": server,
        "device": "iPhone model / iOS version",
        "tester": "",
        "tested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": {check: False for check in REAL_DEVICE_CHECKS},
        "notes": "",
    }
    path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] wrote real-device evidence template: {path}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
