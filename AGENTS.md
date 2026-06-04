# AGENTS.md

## Project Context

This repo contains the product and implementation plan for a Witcher-themed
one-day LARP control app. The working documentation language is Russian.
Before broad product, architecture, or task changes, read these project-specific
sources:

- `docs/core-engine-v1.2.md` - исходная игровая механика и ролевая модель.
- `docs/app-technical-plan-v0.1.md` - актуальный технический план и ограничения площадки.
- `docs/PRD.md` - продуктовый контур MVP и пользовательские сценарии.
- `docs/architecture.md` - архитектура, данные и игровые контуры.
- `docs/roadmap.md` - порядок реализации и milestone gates.

Keep the app plan aligned with the current production profile: 15 people total,
13 playable roles plus 2 NPC masters: 4 lords, 4 sorceresses, 5 witchers,
3 story acts plus final act, Good/Evil reputation,
offline-first phones, local Wi-Fi sync, local FastAPI/SQLite server, browser
panels for lords, and master-operated conflict resolution.

Do not rewrite `docs/core-engine-v1.2.md` unless the user explicitly asks.
Treat it as a historical source document. `docs/app-technical-plan-v0.1.md`
is current technical canon and should be updated with TaskOS canonical docs and
`tasks.json` when implementation planning changes.

`scripts/taskctl.py` uses the vendored TaskOS package in `tools/taskos`, so the
task loop should work without a global `taskos` install.

Python/backend/tooling environment is managed with `uv`. Use `uv sync` to create
or update the project `.venv`, and run Python commands through `uv run python`
instead of a manually created virtual environment.

<!-- TASKOS:START -->
## Codex TaskOS Loop

When a chat is opened to continue implementation from the TaskOS queue:

- Use `docs/active-tasks.md` or `uv run python scripts/taskctl.py ready` first for ordinary orientation; it is the compact generated view of unfinished work.
- Treat `tasks.json` as the canonical source of truth for task status and dependencies, but open the full file only when editing task metadata/dependencies or when the compact view is insufficient.
- Treat `progress.txt` as the completion log, not as a replacement for the dependency graph.
- Run `uv run python scripts/taskctl.py claim` before implementation changes.
- If the user names a task id, run `uv run python scripts/taskctl.py claim <TASK_ID>`.
- Never adopt an existing `in_progress` task unless the current user explicitly names it.
- Implement exactly one newly claimed dependency-ready task.
- Use `uv run python scripts/taskctl.py done <TASK_ID> --summary "..." --check "..."` after completion.
- Use `uv run python scripts/taskctl.py block <TASK_ID> --reason "..."` when work is blocked.
- Use `uv run python scripts/taskctl.py release <TASK_ID> --reason "..."` if abandoning a claim.
- Do not manually edit generated views such as `docs/active-tasks.md`, `docs/kanban.md`, `docs/helpers/task-board.html`, `docs/task-board.html`.
- Use `uv run python scripts/taskctl.py sync` after manual `tasks.json` metadata edits.
- Run relevant checks before marking a task done.
- Do not make a git commit unless the user explicitly asks.

Canonical docs to read when relevant before broad or architectural changes:

- `docs/PRD.md`
- `docs/architecture.md`
- `docs/roadmap.md`
<!-- TASKOS:END -->
