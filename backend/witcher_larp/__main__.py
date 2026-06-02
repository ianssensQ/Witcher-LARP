"""Run the local backend server from `python -m backend.witcher_larp`."""

from __future__ import annotations

import os
import sys


def main() -> int:
    try:
        import uvicorn
    except ModuleNotFoundError:
        print(
            "uvicorn is not installed. Install backend dependencies with "
            "`uv sync` and run backend commands through `uv run python`.",
            file=sys.stderr,
        )
        return 2

    host = os.environ.get("WITCHER_LARP_HOST", "127.0.0.1")
    port = int(os.environ.get("WITCHER_LARP_PORT", "8000"))
    uvicorn.run("backend.witcher_larp.app:create_app", factory=True, host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
