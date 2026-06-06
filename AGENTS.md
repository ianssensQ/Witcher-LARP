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

## Frontend UX/UI Screen Work

When continuing visual frontend work, especially for lord browser screens,
read `docs/ui/frontend-ux-ui-screen-workflow.md` before editing. It defines the
current screen-by-screen workflow, accepted tool choices, asset rules, Motion
design rules, and the handoff for the lord login screen.

For visual prototyping chats that are not explicitly working from TaskOS, do
one screen at a time. Confirm the role, device, screen purpose and references
before generating assets or editing code. Game UI must feel native to the
illustration: use generated/local bitmap layers, transparent cutouts, exact
hit-zones over painted slots, React + Tailwind for interaction, Motion for
runtime animation, OpenRouter as the default image-generation provider, and
Figma MCP for design handoff/acceptance boards. Do not put technical labels,
API notes or acceptance text into player-facing screens.

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

<!-- CODEGRAPH:START -->
## CodeGraph Loop

This project is indexed with CodeGraph. In new Codex chats, use CodeGraph as
the default code navigation and impact-analysis layer before broad code edits.
Prefer CodeGraph MCP tools when they are available; if they are not exposed in
the current chat, use the local CLI commands below.

Keep TaskOS as the source of implementation order. CodeGraph does not replace
`tasks.json`, `docs/active-tasks.md`, `progress.txt`, or `scripts/taskctl.py`.

New chat boot sequence for implementation work:

1. Start with TaskOS orientation: read `docs/active-tasks.md` or run
   `uv run python scripts/taskctl.py ready`.
2. Check graph health with `codegraph status .`; if the index is stale after
   local edits, run `codegraph sync .` before relying on query, impact or
   affected-test results.
3. After claiming a task, use CodeGraph to find the code surface before opening
   many files manually:
   - `codegraph files --path .`
   - `codegraph query <domain-or-symbol> --path . --limit 10`
   - `codegraph callers <symbol> --path .`
   - `codegraph callees <symbol> --path .`
   - `codegraph impact <symbol> --path . --depth 3`
4. Use the graph result as a map, not as proof. Open and read the relevant
   source files before editing, then use `rg` for text, docs, CSV, Godot `.gd`,
   fixtures, and generated/non-indexed content.
5. Before choosing checks, ask CodeGraph for likely affected tests:
   `codegraph affected <changed-file> --path . --quiet`. Combine that with
   project judgment and TaskOS test steps; do not skip a required test just
   because CodeGraph did not name it.
6. After meaningful code edits, especially changes that add, remove, move,
   rename or rewire symbols, run `codegraph sync .` and then `codegraph status .`
   before final impact/test selection and handoff. This keeps later
   query/impact/caller/callee lookups useful for the next chat.

Use CodeGraph especially for backend/runtime work in `backend/witcher_larp/`,
FastAPI routes, snapshot/export paths, event sync, review/recovery, lord panel
state, PvP/PvE services, and test impact. For product docs, roadmap/task
metadata, CSV seed content, and mobile Godot scripts, rely on direct file
inspection and `rg` first, then use CodeGraph only if it has relevant indexed
symbols.

When reporting work, mention the CodeGraph checks that materially shaped the
edit or test selection. The local `.codegraph/` index is generated state and
must not be committed.
<!-- CODEGRAPH:END -->
