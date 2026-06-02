# Runtime seed CSV pack

This directory is the editable source-of-truth seed pack for Stage 1 runtime
development. CSV files are UTF-8, comma-delimited, include a header row, and use
stable opaque IDs for cross-file references.

The valid fixture in `tests/fixtures/seed_valid` points to this directory to
avoid a second mutable source. Invalid fixture packs use the same base pack plus
local CSV overrides with the same file names.

Core layout contract:

- `data/seed/`: authoritative runtime CSV seed.
- `data/snapshots/`: generated mobile snapshots.
- `data/backups/`: SQLite/export backups.
- `tests/fixtures/seed_valid/`: valid fixture manifest for this seed.
- `tests/fixtures/seed_invalid_*`: intentional broken packs for TASK-004.

Mechanics canon: `docs/game-mechanics.md`.
