# Seed fixtures

`seed_valid` points at the authoritative `data/seed` pack. Invalid fixture
directories are overlay packs: start with `data/seed`, then replace the CSV
files present in the invalid fixture directory.

The overlay convention keeps TASK-003 as the single editable seed source while
giving TASK-004 exact broken files to load without renaming.
