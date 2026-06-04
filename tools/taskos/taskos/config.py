from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_PRIORITY_ORDER = ("P0", "P1", "P2", "P3")
DEFAULT_CANONICAL_DOCS = ("docs/PRD.md", "docs/architecture.md", "docs/roadmap.md")


@dataclass(frozen=True)
class TaskosConfig:
    project_name: str = "Codex TaskOS"
    tasks_file: str = "tasks.json"
    progress_file: str = "progress.txt"
    lock_file: str = ".taskos.lock"
    generated_active: str = "docs/active-tasks.md"
    generated_kanban: str = "docs/kanban.md"
    generated_dashboard: str = "docs/helpers/task-board.html"
    generated_dashboard_entrypoint: str = "docs/task-board.html"
    taskctl_script: str = "scripts/taskctl.py"
    canonical_docs: tuple[str, ...] = DEFAULT_CANONICAL_DOCS
    priority_order: tuple[str, ...] = DEFAULT_PRIORITY_ORDER
    command_name: str = "python scripts/taskctl.py"

    def path(self, root: Path, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return root / path


def default_config(project_name: str | None = None) -> TaskosConfig:
    if project_name:
        return TaskosConfig(project_name=project_name)
    return TaskosConfig()


def load_config(root: Path, config_path: Path | None = None) -> TaskosConfig:
    path = config_path or root / "taskos.toml"
    if not path.exists():
        return default_config(project_name=root.name)

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return default_config(project_name=root.name)

    values: dict[str, Any] = {}
    for field in TaskosConfig.__dataclass_fields__:
        if field in data:
            values[field] = data[field]

    if "canonical_docs" in values:
        values["canonical_docs"] = tuple(str(item) for item in values["canonical_docs"])
    if "priority_order" in values:
        values["priority_order"] = tuple(str(item) for item in values["priority_order"])

    if "project_name" not in values:
        values["project_name"] = root.name

    return TaskosConfig(**values)


def render_config(config: TaskosConfig) -> str:
    docs = ", ".join(f'"{item}"' for item in config.canonical_docs)
    priority_order = ", ".join(f'"{item}"' for item in config.priority_order)
    return "\n".join(
        [
            f'project_name = "{config.project_name}"',
            f'tasks_file = "{config.tasks_file}"',
            f'progress_file = "{config.progress_file}"',
            f'lock_file = "{config.lock_file}"',
            f'generated_active = "{config.generated_active}"',
            f'generated_kanban = "{config.generated_kanban}"',
            f'generated_dashboard = "{config.generated_dashboard}"',
            f'generated_dashboard_entrypoint = "{config.generated_dashboard_entrypoint}"',
            f'taskctl_script = "{config.taskctl_script}"',
            f"canonical_docs = [{docs}]",
            f"priority_order = [{priority_order}]",
            f'command_name = "{config.command_name}"',
            "",
        ]
    )
