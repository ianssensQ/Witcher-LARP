#!/usr/bin/env python3
"""Smoke the no-PvP HTTP flow used by the iOS player app."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class SmokeError(RuntimeError):
    """Raised when the iOS no-PvP smoke cannot complete."""


@dataclass
class SmokeReport:
    server: str
    player_code: str
    checks: list[str] = field(default_factory=list)
    health: dict[str, Any] | None = None
    auth: dict[str, Any] | None = None
    snapshot_version: str | None = None
    qr_lookup: dict[str, Any] | None = None
    empty_sync: dict[str, Any] | None = None

    def ok(self, message: str) -> None:
        self.checks.append(message)
        print(f"[ok] {message}")


class ApiClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get(self, path: str, *, player_code: str | None = None) -> dict[str, Any]:
        return self._request("GET", path, player_code=player_code)

    def post(self, path: str, body: dict[str, Any], *, player_code: str | None = None) -> dict[str, Any]:
        return self._request("POST", path, body=body, player_code=player_code)

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        player_code: str | None = None,
    ) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        if player_code:
            request.add_header("X-Player-Code", player_code)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SmokeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise SmokeError(f"{method} {path} failed: {exc}") from exc
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SmokeError(f"{method} {path} returned non-JSON: {raw[:200]}") from exc
        if not isinstance(value, dict):
            raise SmokeError(f"{method} {path} returned non-object JSON: {value!r}")
        return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Smoke the live no-PvP iOS flow: /health, player-code auth and "
            "player-scoped snapshot. QR lookup and empty sync are optional "
            "because they write lightweight runtime rows."
        )
    )
    parser.add_argument("--server", default="http://192.168.68.118:8002", help="FastAPI base URL.")
    parser.add_argument("--player-code", default="WC-WOLF-6GF4", help="Seed player code to test.")
    parser.add_argument("--device-id", default=f"ios-no-pvp-smoke-{int(time.time())}")
    parser.add_argument("--qr-code", default="QR-A1-TRV-001-K7Q2", help="QR/manual code for optional lookup.")
    parser.add_argument("--include-qr-lookup", action="store_true", help="Also call /api/qr/lookup.")
    parser.add_argument("--include-empty-sync", action="store_true", help="Also call /api/events/sync with no events.")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--json-report", help="Write a machine-readable smoke report.")
    args = parser.parse_args(argv)

    client = ApiClient(args.server, args.timeout)
    report = SmokeReport(server=args.server, player_code=args.player_code)

    health = client.get("/health")
    report.health = health
    require(health.get("status") == "ok", f"/health status is not ok: {health!r}")
    report.ok(f"health ok ({health.get('api', {}).get('revision', 'no revision')})")

    auth = client.post(
        "/api/auth/player-code",
        {"player_code": args.player_code, "device_id": args.device_id},
    )
    report.auth = auth
    player_id = str(auth.get("player_id") or "")
    role_type = str(auth.get("role_type") or "")
    require(player_id, f"auth did not return player_id: {auth!r}")
    require(role_type in {"witcher", "sorceress"}, f"expected mobile role, got {role_type!r}")
    report.ok(f"player auth ok ({player_id}, {role_type})")

    snapshot = client.get(f"/api/content/snapshot?player_code={quote(args.player_code)}")
    report.snapshot_version = str(snapshot.get("snapshot_version") or "")
    require(snapshot.get("auth", {}).get("player_id") == player_id, "snapshot auth player mismatch")
    require(snapshot.get("player", {}).get("player_id") == player_id, "snapshot player mismatch")
    require("player_codes" not in snapshot, "snapshot leaks player_codes")
    require("role_tokens" not in snapshot, "snapshot leaks role_tokens")
    require(isinstance(snapshot.get("qr_objects"), list) and snapshot["qr_objects"], "snapshot has no qr_objects")
    require(
        isinstance(snapshot.get("pve_scenarios"), list) and snapshot["pve_scenarios"],
        "snapshot has no pve_scenarios",
    )
    report.ok(f"snapshot ok ({report.snapshot_version or 'no version'})")

    if args.include_qr_lookup:
        lookup = client.post(
            "/api/qr/lookup",
            {
                "code": args.qr_code,
                "player_id": player_id,
                "device_id": args.device_id,
                "source": "qr_scan",
                "physical_presence_confirmed": True,
            },
            player_code=args.player_code,
        )
        report.qr_lookup = lookup
        require(lookup.get("status") in {"ok", "locked"}, f"unexpected QR status: {lookup!r}")
        report.ok(f"qr lookup ok ({lookup.get('status')})")

    if args.include_empty_sync:
        sync = client.post(
            "/api/events/sync",
            {
                "device_id": args.device_id,
                "actor_id": player_id,
                "actor_type": role_type,
                "events": [],
            },
            player_code=args.player_code,
        )
        report.empty_sync = sync
        require(isinstance(sync.get("results"), list), f"sync response has no results list: {sync!r}")
        require(sync["results"] == [], f"empty sync returned unexpected results: {sync!r}")
        report.ok("empty sync ok")

    if args.json_report:
        output = Path(args.json_report)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
        report.ok(f"report written to {output}")

    print("[done] iOS no-PvP HTTP smoke passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except SmokeError as exc:
        print(f"[fail] {exc}", file=sys.stderr)
        raise SystemExit(1)
