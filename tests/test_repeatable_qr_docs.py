from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORDINARY_QR_MODES = {"repeatable_scene", "always_available_scene"}


def test_repeatable_qr_doc_tracks_seed_ordinary_quests() -> None:
    doc = (ROOT / "docs/repeatable-qr-quests.md").read_text(encoding="utf-8")

    with (ROOT / "data/seed/qr_objects.csv").open(encoding="utf-8-sig", newline="") as handle:
        ordinary_rows = [
            row for row in csv.DictReader(handle) if row["qr_mode"] in ORDINARY_QR_MODES
        ]

    assert len(ordinary_rows) == 24
    assert "После награды не забирайте" in doc

    for row in ordinary_rows:
        assert row["qr_id"] in doc
        assert row["manual_code"] in doc
