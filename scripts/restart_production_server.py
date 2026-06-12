from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROD_HOST = "0.0.0.0"
PROD_PORT = 8002
DEFAULT_PUBLIC_HOST = "192.168.0.103"
GAME_PORTS = (8000, 8001, 8002, 5173, 5174, 5175, 5176, 5177, 5178, 5179)
LOG_DIR = Path(os.environ.get("TEMP", str(PROJECT_ROOT))) / "witcher-larp-run-logs"
SERVER_STDOUT = LOG_DIR / "witcher-production-8002.out.log"
SERVER_STDERR = LOG_DIR / "witcher-production-8002.err.log"
APP_TARGET = "backend.witcher_larp.app:create_app"


def _run(command: list[str], *, cwd: Path = PROJECT_ROOT) -> None:
    print(f"$ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def _netstat_listeners() -> dict[int, set[int]]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    listeners: dict[int, set[int]] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
            continue
        local_address = parts[1]
        pid_text = parts[4]
        try:
            port = int(local_address.rsplit(":", 1)[1])
            pid = int(pid_text)
        except ValueError:
            continue
        listeners.setdefault(port, set()).add(pid)
    return listeners


def _stop_pid(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        check=False,
        capture_output=True,
        text=True,
    )


def _stop_game_ports() -> None:
    listeners = _netstat_listeners()
    pids = sorted({pid for port in GAME_PORTS for pid in listeners.get(port, set())})
    if not pids:
        print("No existing game listeners on 8000-8002 or 5173-5179.", flush=True)
        return
    print(f"Stopping game listener PIDs: {', '.join(str(pid) for pid in pids)}", flush=True)
    for pid in pids:
        _stop_pid(pid)
    time.sleep(1)


def _clean_server_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path_value = os.environ.get("Path") or os.environ.get("PATH") or ""
    for name, value in os.environ.items():
        if name.upper() == "PATH":
            continue
        env[name] = value
    env["Path"] = path_value
    env["WITCHER_LARP_HOST"] = PROD_HOST
    env["WITCHER_LARP_PORT"] = str(PROD_PORT)
    return env


def _server_command() -> list[str]:
    if os.name == "nt":
        uvicorn = PROJECT_ROOT / ".venv" / "Scripts" / "uvicorn.exe"
    else:
        uvicorn = PROJECT_ROOT / ".venv" / "bin" / "uvicorn"
    if uvicorn.exists():
        return [
            str(uvicorn),
            APP_TARGET,
            "--factory",
            "--host",
            PROD_HOST,
            "--port",
            str(PROD_PORT),
        ]
    return [
        sys.executable,
        "-m",
        "uvicorn",
        APP_TARGET,
        "--factory",
        "--host",
        PROD_HOST,
        "--port",
        str(PROD_PORT),
    ]


def _start_server() -> subprocess.Popen[bytes]:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stdout = SERVER_STDOUT.open("wb")
    stderr = SERVER_STDERR.open("wb")
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    command = _server_command()
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        env=_clean_server_env(),
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
        close_fds=True,
        creationflags=creationflags,
    )
    stdout.close()
    stderr.close()
    print(f"Started production server PID {process.pid}: {' '.join(command)}", flush=True)
    return process


def _http_status(url: str, *, timeout: float = 2.0) -> int | None:
    try:
        with urlopen(url, timeout=timeout) as response:
            return response.status
    except URLError:
        return None
    except TimeoutError:
        return None


def _tail(path: Path, *, max_lines: int = 30) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return "\n".join(text.splitlines()[-max_lines:])


def _verify(process: subprocess.Popen[bytes], *, public_host: str, timeout_seconds: int) -> None:
    health_url = f"http://127.0.0.1:{PROD_PORT}/health"
    lord_url = f"http://127.0.0.1:{PROD_PORT}/lords/home"
    deadline = time.monotonic() + timeout_seconds
    health_ok = False
    lord_ok = False
    while time.monotonic() < deadline:
        health_ok = _http_status(health_url) == 200
        lord_ok = _http_status(lord_url) == 200
        if health_ok and lord_ok:
            break
        time.sleep(0.5)

    listeners = _netstat_listeners()
    extra_ports = {
        port: sorted(pids)
        for port, pids in listeners.items()
        if port in GAME_PORTS and port != PROD_PORT and pids
    }
    if health_ok and lord_ok and not extra_ports:
        time.sleep(2)
        health_ok = _http_status(health_url) == 200
        lord_ok = _http_status(lord_url) == 200
        listeners = _netstat_listeners()
        extra_ports = {
            port: sorted(pids)
            for port, pids in listeners.items()
            if port in GAME_PORTS and port != PROD_PORT and pids
        }

    if health_ok and lord_ok and not extra_ports:
        print(f"Production is ready: http://{public_host}:{PROD_PORT}/lords/home", flush=True)
        print(f"Health check passed: {health_url}", flush=True)
        return

    if process.poll() is None:
        process.kill()
    _stop_game_ports()
    raise SystemExit(
        "Production server did not become healthy within "
        f"{timeout_seconds}s.\n"
        f"health_ok={health_ok} lord_ok={lord_ok} extra_ports={extra_ports}\n"
        f"stderr tail:\n{_tail(SERVER_STDERR)}\n"
        f"stdout tail:\n{_tail(SERVER_STDOUT)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and restart the single production FastAPI server.")
    parser.add_argument("--skip-build", action="store_true", help="Skip rebuilding the lord frontend.")
    parser.add_argument("--public-host", default=DEFAULT_PUBLIC_HOST, help="LAN host to print for players.")
    parser.add_argument("--timeout", type=int, default=15, help="Seconds to wait for health checks.")
    args = parser.parse_args(argv)

    if not args.skip_build:
        _run([sys.executable, "scripts/build_lord_frontend.py"])
    _stop_game_ports()
    process = _start_server()
    _verify(process, public_host=args.public_host, timeout_seconds=args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
