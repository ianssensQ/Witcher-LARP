#!/usr/bin/env python3
"""Run the iOS Gwent HTTP smokes against a temporary real FastAPI process."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.witcher_larp.act_service import start_act
from backend.witcher_larp.config import Settings
from backend.witcher_larp.database import connect
from backend.witcher_larp.import_service import import_seed_pack


FIXTURE_MANIFEST = PROJECT_ROOT / "tests" / "fixtures" / "seed_valid" / "fixture_manifest.csv"


class AcceptanceError(RuntimeError):
    """Raised when the local process-level acceptance gate fails."""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Start a temporary FastAPI/SQLite server from this checkout and run "
            "the iOS Gwent preflight, bot and two-player HTTP smokes against it."
        )
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="Use 0 to choose a free local port.")
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--json-dir", help="Directory for JSON smoke reports and server.log.")
    args = parser.parse_args(argv)

    artifact_dir = Path(args.json_dir).expanduser() if args.json_dir else _new_artifact_dir()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    database_path = artifact_dir / "ios_gwent_acceptance.db"
    server_log_path = artifact_dir / "server.log"
    port = args.port or _free_port(args.host)
    base_url = f"http://{args.host}:{port}"
    summary: dict[str, Any] = {
        "status": "failed",
        "base_url": base_url,
        "database_path": str(database_path),
        "artifact_dir": str(artifact_dir),
        "server_log": str(server_log_path),
        "started_at": int(time.time()),
        "steps": [],
    }

    server: subprocess.Popen[str] | None = None
    log_handle = None
    try:
        settings = _prepare_database(database_path)
        summary["snapshot_version"] = _latest_snapshot_version(settings)
        summary["steps"].append({"name": "database_prepared", "database_path": str(database_path)})

        env = os.environ.copy()
        env["WITCHER_LARP_DB"] = str(database_path)
        env["WITCHER_LARP_HOST"] = args.host
        env["WITCHER_LARP_PORT"] = str(port)
        log_handle = server_log_path.open("w", encoding="utf-8")
        server = subprocess.Popen(
            [sys.executable, "-m", "backend.witcher_larp"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
        _wait_for_health(base_url, args.timeout)
        summary["steps"].append({"name": "server_started", "base_url": base_url})

        _run_smoke(
            [
                "--preflight-only",
                "--json-report",
                str(artifact_dir / "preflight.json"),
            ],
            base_url=base_url,
            timeout=args.timeout,
            summary=summary,
            name="preflight",
        )
        _run_smoke(
            [
                "--bot",
                "--json-report",
                str(artifact_dir / "bot.json"),
            ],
            base_url=base_url,
            timeout=args.timeout,
            summary=summary,
            name="bot",
        )
        _run_smoke(
            [
                "--p1-deck-id",
                "deck_witcher_wolf_scoiatael",
                "--p1-starting-player-id",
                "p_witcher_2",
                "--json-report",
                str(artifact_dir / "pvp-scoiatael.json"),
            ],
            base_url=base_url,
            timeout=args.timeout,
            summary=summary,
            name="pvp_scoiatael",
        )
        summary["status"] = "passed"
        summary["finished_at"] = int(time.time())
        print("OK: iOS Gwent process-level acceptance gate passed.")
        print(f"reports: {artifact_dir}")
        return 0
    except Exception as exc:
        summary["error"] = str(exc)
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        if server is not None:
            _stop_server(server)
        if log_handle is not None:
            log_handle.close()
        summary_path = artifact_dir / "acceptance-summary.json"
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"summary: {summary_path}")


def _prepare_database(database_path: Path) -> Settings:
    settings = Settings(database_path=database_path, backup_dir=database_path.parent / "backups")
    report = import_seed_pack(settings, manifest_path=FIXTURE_MANIFEST, snapshot_dir=None)
    if report.status != "success":
        raise AcceptanceError(f"seed import failed: {report.as_dict()}")
    with connect(settings) as connection:
        start_act(
            connection,
            settings,
            "act1",
            operator="ios_gwent_acceptance_gate",
            physical_announcement_state="announced",
            now=datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
        )
    return settings


def _latest_snapshot_version(settings: Settings) -> str | None:
    with connect(settings) as connection:
        row = connection.execute(
            "SELECT snapshot_version FROM snapshot_versions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return None if row is None else str(row["snapshot_version"])


def _run_smoke(
    smoke_args: list[str],
    *,
    base_url: str,
    timeout: float,
    summary: dict[str, Any],
    name: str,
) -> None:
    command = [
        sys.executable,
        "scripts/ios_gwent_http_smoke.py",
        "--server",
        base_url,
        "--timeout",
        str(timeout),
        "--poll-seconds",
        "0.1",
        "--poll-attempts",
        "80",
        *smoke_args,
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=max(30.0, timeout * 8),
        check=False,
    )
    summary["steps"].append(
        {
            "name": name,
            "returncode": completed.returncode,
            "output_tail": completed.stdout[-2000:],
        }
    )
    print(completed.stdout, end="")
    if completed.returncode != 0:
        raise AcceptanceError(f"{name} smoke failed with code {completed.returncode}")


def _wait_for_health(base_url: str, timeout: float) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urlopen(f"{base_url}/health", timeout=1.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            api = payload.get("api") if isinstance(payload, dict) else {}
            if isinstance(api, dict) and api.get("revision") == "ios-gwent-pvp-v1":
                return
            last_error = AcceptanceError(f"server health has wrong API revision: {payload!r}")
        except (OSError, URLError, json.JSONDecodeError) as exc:
            last_error = exc
        time.sleep(0.2)
    raise AcceptanceError(f"server did not become healthy at {base_url}: {last_error}")


def _stop_server(server: subprocess.Popen[str]) -> None:
    if server.poll() is not None:
        return
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)


def _free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _new_artifact_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="ios-gwent-acceptance-", dir="/private/tmp"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
