"""Shared import report models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImportErrorDetail:
    code: str
    file: str
    message: str
    row: int | None = None
    record_id: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "file": self.file,
            "row": self.row,
            "record_id": self.record_id,
            "message": self.message,
        }


@dataclass
class ImportReport:
    run_id: str
    status: str
    files: list[str]
    errors: list[ImportErrorDetail] = field(default_factory=list)
    snapshot_version: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "files": self.files,
            "errors": [error.as_dict() for error in self.errors],
            "snapshot_version": self.snapshot_version,
        }
