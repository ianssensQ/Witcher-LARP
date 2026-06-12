"""Orchestrate CSV validation, SQLite import and snapshot export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

from .config import PROJECT_ROOT, Settings
from .csv_loader import load_pack_from_manifest, load_seed_pack
from .database import connect, init_database
from .import_models import ImportReport
from .repository import record_failed_import, replace_content
from .snapshot_exporter import build_snapshot_from_pack, export_snapshot_file
from .validation import validate_seed_pack


DEFAULT_SEED_PATH = PROJECT_ROOT / "data" / "seed"
DEFAULT_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "snapshots"


def import_seed_pack(
    settings: Settings,
    seed_root: Path = DEFAULT_SEED_PATH,
    *,
    snapshot_dir: Path | None = DEFAULT_SNAPSHOT_DIR,
    manifest_path: Path | None = None,
) -> ImportReport:
    init_database(settings)
    run_id = uuid4().hex
    pack = (
        load_pack_from_manifest(manifest_path)
        if manifest_path is not None
        else load_seed_pack(seed_root)
    )
    errors = validate_seed_pack(pack)
    if errors:
        with connect(settings) as connection:
            return record_failed_import(connection, pack, run_id, errors)

    snapshot_version, content_hash, snapshot_payload = build_snapshot_from_pack(pack)
    with connect(settings) as connection:
        report = replace_content(
            connection,
            pack,
            run_id,
            snapshot_version,
            content_hash,
            snapshot_payload,
        )
    if snapshot_dir is not None:
        export_snapshot_file(snapshot_payload, snapshot_dir)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import Witcher LARP runtime CSV into SQLite and export a mobile snapshot."
    )
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED_PATH)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    args = parser.parse_args(argv)

    settings = Settings(database_path=args.db) if args.db else Settings.from_env()
    report = import_seed_pack(
        settings,
        args.seed,
        manifest_path=args.manifest,
        snapshot_dir=args.snapshot_dir,
    )
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0 if report.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
