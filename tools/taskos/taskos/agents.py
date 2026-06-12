from __future__ import annotations

from pathlib import Path

from .config import TaskosConfig


START = "<!-- TASKOS:START -->"
END = "<!-- TASKOS:END -->"


def render_agents_block(config: TaskosConfig) -> str:
    docs = "\n".join(f"- `{path}`" for path in config.canonical_docs)
    docs_section = (
        "\nCanonical docs to read when relevant before broad or architectural changes:\n\n"
        + docs
        + "\n"
        if config.canonical_docs
        else ""
    )
    generated_views = []
    if config.generated_active:
        generated_views.append(config.generated_active)
    generated_views.extend([config.generated_kanban, config.generated_dashboard])
    if config.generated_dashboard_entrypoint:
        generated_views.append(config.generated_dashboard_entrypoint)
    generated = ", ".join(f"`{path}`" for path in generated_views)
    return f"""{START}
## Codex TaskOS Loop

When a chat is opened to continue implementation from the TaskOS queue:

- Use `{config.generated_active}` or `{config.command_name} ready` first for ordinary orientation; it is the compact generated view of unfinished work.
- Treat `{config.tasks_file}` as the canonical source of truth for task status and dependencies, but open the full file only when editing task metadata/dependencies or when the compact view is insufficient.
- Treat `{config.progress_file}` as the completion log, not as a replacement for the dependency graph.
- Run `{config.command_name} claim` before implementation changes.
- If the user names a task id, run `{config.command_name} claim <TASK_ID>`.
- Never adopt an existing `in_progress` task unless the current user explicitly names it.
- Implement exactly one newly claimed dependency-ready task.
- Use `{config.command_name} done <TASK_ID> --summary "..." --check "..."` after completion.
- Use `{config.command_name} block <TASK_ID> --reason "..."` when work is blocked.
- Use `{config.command_name} release <TASK_ID> --reason "..."` if abandoning a claim.
- Do not manually edit generated views such as {generated}.
- Use `{config.command_name} sync` after manual `{config.tasks_file}` metadata edits.
- Run relevant checks before marking a task done.
- Do not make a git commit unless the user explicitly asks.
{docs_section}{END}
"""


def ensure_agents_block(root: Path, config: TaskosConfig) -> bool:
    path = root / "AGENTS.md"
    block = render_agents_block(config)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    else:
        existing = "# AGENTS.md\n\n"

    if START in existing and END in existing:
        before, rest = existing.split(START, 1)
        _, after = rest.split(END, 1)
        updated = before.rstrip() + "\n\n" + block.rstrip() + "\n" + after.lstrip()
    else:
        updated = existing.rstrip() + "\n\n" + block

    if existing == updated:
        return False
    path.write_text(updated, encoding="utf-8", newline="\n")
    return True
