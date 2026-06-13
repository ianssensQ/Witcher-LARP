#!/usr/bin/env python3
"""Seed and screenshot the no-PvP iOS Release app in a booted Simulator."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import struct
import subprocess
import sys
import time
from typing import Any
from urllib.parse import quote
from urllib.request import urlopen
import zlib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SERVER = "http://192.168.68.118:8002"
DEFAULT_BUNDLE_ID = "local.witcherlarp.app"
DEFAULT_PLAYER_CODE = "WC-WOLF-6GF4"


class VisualSmokeError(RuntimeError):
    """Raised when the simulator visual smoke cannot prove the expected state."""


@dataclass(frozen=True)
class PNGStats:
    width: int
    height: int
    body_sample_count: int
    body_nonwhite_ratio: float
    body_dark_ratio: float
    body_luma_stddev: float

    @property
    def body_looks_nonblank(self) -> bool:
        return (
            self.width >= 320
            and self.height >= 600
            and self.body_sample_count > 0
            and self.body_nonwhite_ratio >= 0.015
            and self.body_dark_ratio >= 0.001
            and self.body_luma_stddev >= 8.0
        )

    def as_json(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "body_sample_count": self.body_sample_count,
            "body_nonwhite_ratio": round(self.body_nonwhite_ratio, 5),
            "body_dark_ratio": round(self.body_dark_ratio, 5),
            "body_luma_stddev": round(self.body_luma_stddev, 3),
            "body_looks_nonblank": self.body_looks_nonblank,
        }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install a Release simulator .app, seed player snapshot storage, "
            "launch it and screenshot Home to catch blank or wrong no-PvP UI."
        )
    )
    parser.add_argument("--app", type=Path, required=True, help="Release-iphonesimulator .app path.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--player-code", default=DEFAULT_PLAYER_CODE)
    parser.add_argument("--device", default="booted", help="Simulator UDID or 'booted'.")
    parser.add_argument("--bundle-id", default=DEFAULT_BUNDLE_ID)
    parser.add_argument("--wait", type=float, default=6.0, help="Seconds to wait after launch.")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout.")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=Path(f"/private/tmp/ios-no-pvp-sim-visual-smoke-{int(time.time())}"),
    )
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args(argv)

    report: dict[str, Any] = {
        "status": "failed",
        "server": args.server,
        "player_code": args.player_code,
        "device": args.device,
        "bundle_id": args.bundle_id,
        "app": str(args.app),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": {},
    }
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    report["artifact_dir"] = str(args.artifact_dir)

    try:
        if not args.app.exists():
            raise VisualSmokeError(f"simulator app is missing: {args.app}")
        if not args.app.is_dir():
            raise VisualSmokeError(f"simulator app is not a directory: {args.app}")

        health = _http_json(f"{args.server.rstrip('/')}/health", timeout=args.timeout)
        report["health"] = health
        _check(report, "server_health_ok", health.get("status") == "ok")

        snapshot = _http_json(
            f"{args.server.rstrip('/')}/api/content/snapshot?player_code={quote(args.player_code)}",
            timeout=args.timeout,
        )
        report["snapshot_version"] = str(snapshot.get("snapshot_version") or "")
        report["snapshot_player"] = (snapshot.get("player") or {}).get("player_id")
        _check(report, "snapshot_loaded", bool(snapshot.get("player")))

        _run(["xcrun", "simctl", "install", args.device, str(args.app)], timeout=90)
        _run(["xcrun", "simctl", "terminate", args.device, args.bundle_id], timeout=15, allow_failure=True)
        container = _run(
            ["xcrun", "simctl", "get_app_container", args.device, args.bundle_id, "data"],
            timeout=30,
        ).strip()
        report["app_container"] = container
        _seed_local_store(
            Path(container),
            server=args.server,
            player_code=args.player_code,
            snapshot=snapshot,
        )
        _check(report, "app_container_seeded", True)

        launch_output = _run(["xcrun", "simctl", "launch", args.device, args.bundle_id], timeout=30)
        report["launch_output"] = launch_output.strip()
        time.sleep(max(0.5, args.wait))

        screenshot_path = args.artifact_dir / "release-home.png"
        _run(["xcrun", "simctl", "io", args.device, "screenshot", str(screenshot_path)], timeout=30)
        report["screenshot"] = str(screenshot_path)
        _check(report, "screenshot_written", screenshot_path.exists() and screenshot_path.stat().st_size > 10_000)

        stats = _png_stats(screenshot_path)
        report["image_stats"] = stats.as_json()
        _check(report, "screenshot_dimensions_ok", stats.width >= 320 and stats.height >= 600)
        _check(report, "home_body_not_blank", stats.body_looks_nonblank)

        failed = [name for name, ok in report["checks"].items() if not ok]
        if failed:
            raise VisualSmokeError(f"visual smoke failed checks: {', '.join(failed)}")

        report["status"] = "passed"
        print(f"[ok] iOS no-PvP simulator visual smoke passed: {screenshot_path}")
        return 0
    except Exception as exc:
        report["error"] = str(exc)
        print(f"[fail] {exc}", file=sys.stderr)
        return 1
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        report_path = args.json_report or (args.artifact_dir / "ios-no-pvp-sim-visual-smoke.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"[report] {report_path}")


def _check(report: dict[str, Any], name: str, value: bool) -> None:
    report["checks"][name] = bool(value)


def _http_json(url: str, *, timeout: float) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _run(command: list[str], *, timeout: float, allow_failure: bool = False) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0 and not allow_failure:
        raise VisualSmokeError(
            f"{' '.join(command)} failed with code {completed.returncode}: {completed.stdout[-1000:]}"
        )
    return completed.stdout


def _seed_local_store(
    container: Path,
    *,
    server: str,
    player_code: str,
    snapshot: dict[str, Any],
) -> None:
    storage = container / "Documents" / "WitcherLARP"
    storage.mkdir(parents=True, exist_ok=True)
    (storage / "server_url.json").write_text(json.dumps(server), encoding="utf-8")
    (storage / "player_code.json").write_text(json.dumps(player_code), encoding="utf-8")
    (storage / "snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _png_stats(path: Path) -> PNGStats:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise VisualSmokeError(f"not a PNG screenshot: {path}")

    offset = 8
    width = height = bit_depth = color_type = interlace = None
    idat = bytearray()
    while offset < len(data):
        if offset + 8 > len(data):
            raise VisualSmokeError("truncated PNG chunk header")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk_data = data[offset + 8:offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    if width is None or height is None or bit_depth is None or color_type is None:
        raise VisualSmokeError("PNG is missing IHDR")
    if bit_depth != 8 or interlace != 0:
        raise VisualSmokeError(f"unsupported PNG format: bit_depth={bit_depth}, interlace={interlace}")

    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise VisualSmokeError(f"unsupported PNG color_type={color_type}")

    raw = zlib.decompress(bytes(idat))
    row_bytes = width * channels
    previous = bytearray(row_bytes)
    lumas: list[float] = []
    nonwhite = 0
    dark = 0
    sample_count = 0
    body_top = max(140, int(height * 0.12))
    body_bottom = min(height - 90, int(height * 0.92))
    x_step = max(1, width // 240)
    y_step = max(1, height // 500)

    cursor = 0
    for y in range(height):
        filter_type = raw[cursor]
        cursor += 1
        row = bytearray(raw[cursor:cursor + row_bytes])
        cursor += row_bytes
        _unfilter_scanline(row, previous, channels, filter_type)

        if body_top <= y < body_bottom and y % y_step == 0:
            for x in range(0, width, x_step):
                r, g, b = _pixel_rgb(row, x, channels, color_type)
                luma = (0.2126 * r) + (0.7152 * g) + (0.0722 * b)
                lumas.append(luma)
                sample_count += 1
                if max(r, g, b) < 245 or min(r, g, b) < 235:
                    nonwhite += 1
                if luma < 90:
                    dark += 1

        previous = row

    return PNGStats(
        width=width,
        height=height,
        body_sample_count=sample_count,
        body_nonwhite_ratio=nonwhite / sample_count if sample_count else 0.0,
        body_dark_ratio=dark / sample_count if sample_count else 0.0,
        body_luma_stddev=statistics.pstdev(lumas) if len(lumas) > 1 else 0.0,
    )


def _unfilter_scanline(row: bytearray, previous: bytearray, bpp: int, filter_type: int) -> None:
    for i, value in enumerate(row):
        left = row[i - bpp] if i >= bpp else 0
        up = previous[i]
        up_left = previous[i - bpp] if i >= bpp else 0
        if filter_type == 0:
            delta = 0
        elif filter_type == 1:
            delta = left
        elif filter_type == 2:
            delta = up
        elif filter_type == 3:
            delta = (left + up) // 2
        elif filter_type == 4:
            delta = _paeth(left, up, up_left)
        else:
            raise VisualSmokeError(f"unsupported PNG filter type {filter_type}")
        row[i] = (value + delta) & 0xFF


def _paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    up_left_distance = abs(estimate - up_left)
    if left_distance <= up_distance and left_distance <= up_left_distance:
        return left
    if up_distance <= up_left_distance:
        return up
    return up_left


def _pixel_rgb(row: bytearray, x: int, channels: int, color_type: int) -> tuple[int, int, int]:
    start = x * channels
    if color_type == 0:
        value = row[start]
        return value, value, value
    if color_type == 4:
        value = row[start]
        return value, value, value
    return row[start], row[start + 1], row[start + 2]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
