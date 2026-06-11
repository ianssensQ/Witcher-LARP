from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "prototypes" / "stage2b-v2"
SRC_ROOT = FRONTEND_ROOT / "src"
DIST_ROOT = FRONTEND_ROOT / "dist"
MAX_RUNTIME_ASSET_BYTES = 20 * 1024 * 1024
ASSET_IMPORT_RE = re.compile(
    r"import\s+[\w{}\s,*]+?\s+from\s+[\"'](?P<path>\./assets/[^\"']+)[\"']"
)


def _find_node() -> str:
    node = shutil.which("node")
    if node:
        return node
    raise SystemExit("node executable was not found in PATH. Install Node or run from Codex bundled runtime.")


def _run(command: list[str], *, cwd: Path) -> None:
    print(f"$ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def _runtime_asset_imports() -> list[Path]:
    imports: list[Path] = []
    for source_path in SRC_ROOT.rglob("*"):
        if source_path.suffix not in {".ts", ".tsx"}:
            continue
        text = source_path.read_text(encoding="utf-8")
        for match in ASSET_IMPORT_RE.finditer(text):
            asset_path = (source_path.parent / match.group("path")).resolve()
            try:
                asset_path.relative_to(SRC_ROOT)
            except ValueError:
                continue
            imports.append(asset_path)
    return sorted(set(imports))


def _audit_runtime_assets() -> None:
    oversized = [
        asset
        for asset in _runtime_asset_imports()
        if asset.exists() and asset.stat().st_size > MAX_RUNTIME_ASSET_BYTES
    ]
    if not oversized:
        return

    formatted = "\n".join(
        f"- {asset.relative_to(PROJECT_ROOT)} ({asset.stat().st_size / 1024 / 1024:.1f} MB)"
        for asset in oversized
    )
    raise SystemExit(
        "Runtime frontend imports oversized assets. Convert them to WebP/AVIF or remove them from "
        f"the runtime import graph:\n{formatted}"
    )


def _dist_summary() -> str:
    if not DIST_ROOT.exists():
        return "dist is missing"
    total_bytes = sum(path.stat().st_size for path in DIST_ROOT.rglob("*") if path.is_file())
    return f"dist ready at {DIST_ROOT.relative_to(PROJECT_ROOT)} ({total_bytes / 1024 / 1024:.1f} MB)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the production lord React frontend served by FastAPI.")
    parser.add_argument("--skip-vite", action="store_true", help="Run TypeScript and asset audit only.")
    args = parser.parse_args(argv)

    node = _find_node()
    tsc = FRONTEND_ROOT / "node_modules" / "typescript" / "bin" / "tsc"
    vite = FRONTEND_ROOT / "node_modules" / "vite" / "bin" / "vite.js"
    if not tsc.exists() or not vite.exists():
        raise SystemExit("Frontend dependencies are missing. Install prototypes/stage2b-v2 node_modules first.")

    _run([node, str(tsc)], cwd=FRONTEND_ROOT)
    _audit_runtime_assets()
    if not args.skip_vite:
        _run([node, str(vite), "build"], cwd=FRONTEND_ROOT)
        print(_dist_summary(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
