#!/usr/bin/env python
"""Project-local compatibility wrapper for Codex TaskOS."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDORED_TASKOS = PROJECT_ROOT / "tools" / "taskos"

if (VENDORED_TASKOS / "taskos" / "cli.py").exists():
    sys.path.insert(0, str(VENDORED_TASKOS))

from taskos.cli import main


def _has_root_argument(argv):
    return any(arg == "--root" or arg.startswith("--root=") for arg in argv)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not _has_root_argument(args):
        args = ["--root", str(PROJECT_ROOT), *args]
    raise SystemExit(main(args))
