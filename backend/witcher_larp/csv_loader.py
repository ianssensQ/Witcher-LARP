"""CSV and fixture-manifest loading for the runtime seed pack."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .content_schema import REQUIRED_FILES, table_name
from .import_models import ImportErrorDetail


@dataclass(frozen=True)
class CsvRecord:
    row_number: int
    values: dict[str, str]


@dataclass(frozen=True)
class CsvTable:
    file_name: str
    name: str
    path: Path
    headers: tuple[str, ...]
    rows: tuple[CsvRecord, ...]


@dataclass(frozen=True)
class SeedPack:
    source_path: Path
    tables: dict[str, CsvTable]
    load_errors: tuple[ImportErrorDetail, ...] = ()
    manifest_id: str | None = None

    @property
    def files(self) -> list[str]:
        return sorted(self.tables)


def load_seed_pack(
    seed_root: Path,
    *,
    overrides_root: Path | None = None,
    override_files: list[str] | None = None,
    manifest_id: str | None = None,
) -> SeedPack:
    root = seed_root.resolve()
    overrides = overrides_root.resolve() if overrides_root else None
    override_set = set(override_files or [])
    tables: dict[str, CsvTable] = {}
    errors: list[ImportErrorDetail] = []

    for file_name in REQUIRED_FILES:
        path = root / file_name
        if file_name in override_set and overrides is not None:
            path = overrides / file_name
        table = _load_csv_table(file_name, path)
        if isinstance(table, ImportErrorDetail):
            errors.append(table)
            continue
        tables[file_name] = table

    for file_name in sorted(override_set - set(REQUIRED_FILES)):
        errors.append(
            ImportErrorDetail(
                code="unknown_override_file",
                file=file_name,
                message=f"Override file is not part of the runtime CSV schema: {file_name}",
            )
        )

    return SeedPack(
        source_path=root,
        tables=tables,
        load_errors=tuple(errors),
        manifest_id=manifest_id,
    )


def load_pack_from_manifest(manifest_path: Path) -> SeedPack:
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        manifest_rows = list(csv.DictReader(handle))
    if not manifest_rows:
        return SeedPack(
            source_path=manifest_path.parent,
            tables={},
            load_errors=(
                ImportErrorDetail(
                    code="manifest_empty",
                    file=manifest_path.name,
                    message="Fixture manifest has no rows.",
                ),
            ),
        )

    manifest = manifest_rows[0]
    base_path = (manifest_path.parent / manifest["base_path"]).resolve()
    override_files = [
        part.strip()
        for part in manifest.get("override_files", "").split(";")
        if part.strip()
    ]
    return load_seed_pack(
        base_path,
        overrides_root=manifest_path.parent,
        override_files=override_files,
        manifest_id=manifest.get("fixture_id") or manifest_path.parent.name,
    )


def _load_csv_table(file_name: str, path: Path) -> CsvTable | ImportErrorDetail:
    if not path.exists():
        return ImportErrorDetail(
            code="missing_file",
            file=file_name,
            message=f"Required CSV file is missing: {path}",
        )

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return ImportErrorDetail(
                code="missing_header",
                file=file_name,
                message=f"CSV file has no header row: {path}",
            )
        headers = tuple(reader.fieldnames)
        rows: list[CsvRecord] = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                return ImportErrorDetail(
                    code="extra_columns",
                    file=file_name,
                    row=row_number,
                    message=f"CSV row has extra columns: {row[None]}",
                )
            rows.append(
                CsvRecord(
                    row_number=row_number,
                    values={
                        header: row.get(header) if row.get(header) is not None else ""
                        for header in headers
                    },
                )
            )

    return CsvTable(
        file_name=file_name,
        name=table_name(file_name),
        path=path,
        headers=headers,
        rows=tuple(rows),
    )
