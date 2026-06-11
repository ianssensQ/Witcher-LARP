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
RUNTIME_SOURCE_ENTRYPOINT = SRC_ROOT / "main.tsx"
FORBIDDEN_RUNTIME_ASSET_SUBPATHS = ("assets/generated/mobile/",)
SOURCE_IMPORT_RE = re.compile(
    r"(?:import\s+(?:[\w{}\s,*]+?\s+from\s+)?|import\()\s*[\"'](?P<path>\.[^\"']+)[\"']"
)
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


def _resolve_runtime_source_import(source_path: Path, import_path: str) -> Path | None:
    resolved = (source_path.parent / import_path).resolve()
    try:
        resolved.relative_to(SRC_ROOT)
    except ValueError:
        return None

    if resolved.suffix in {".ts", ".tsx"} and resolved.exists():
        return resolved
    if resolved.suffix:
        return None
    for suffix in (".tsx", ".ts"):
        candidate = resolved.with_suffix(suffix)
        if candidate.exists():
            return candidate
    for suffix in (".tsx", ".ts"):
        candidate = resolved / f"index{suffix}"
        if candidate.exists():
            return candidate
    return None


def _runtime_source_files() -> list[Path]:
    pending = [RUNTIME_SOURCE_ENTRYPOINT.resolve()]
    seen: set[Path] = set()
    while pending:
        source_path = pending.pop()
        if source_path in seen or not source_path.exists():
            continue
        seen.add(source_path)
        text = source_path.read_text(encoding="utf-8")
        for match in SOURCE_IMPORT_RE.finditer(text):
            imported_source = _resolve_runtime_source_import(source_path, match.group("path"))
            if imported_source and imported_source not in seen:
                pending.append(imported_source)
    return sorted(seen)


def _runtime_asset_imports() -> list[Path]:
    imports: list[Path] = []
    for source_path in _runtime_source_files():
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
    imported_assets = _runtime_asset_imports()
    forbidden = []
    for asset in imported_assets:
        try:
            relative_asset = asset.relative_to(SRC_ROOT).as_posix()
        except ValueError:
            continue
        if any(relative_asset.startswith(forbidden_path) for forbidden_path in FORBIDDEN_RUNTIME_ASSET_SUBPATHS):
            forbidden.append(asset)
    if forbidden:
        formatted = "\n".join(f"- {asset.relative_to(PROJECT_ROOT)}" for asset in forbidden)
        raise SystemExit(
            "Production lord runtime imports assets from obsolete mobile prototype folders. "
            f"Move the asset into a lord-owned folder or remove the dependency:\n{formatted}"
        )

    oversized = [
        asset
        for asset in imported_assets
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
