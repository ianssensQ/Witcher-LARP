from __future__ import annotations

from collections.abc import Iterable
from typing import Any


Task = dict[str, Any]

PERSISTED_STATUSES = ("pending", "in_progress", "blocked", "done")
STATUS_ORDER = ("in_progress", "ready", "blocked", "pending", "done")
STATUS_LABELS = {
    "in_progress": "In Progress",
    "ready": "Dependency Ready",
    "blocked": "Blocked",
    "pending": "Pending",
    "done": "Done",
}


class TaskosError(RuntimeError):
    """A user-facing TaskOS error."""


def task_list(data: Any) -> list[Task]:
    if isinstance(data, list):
        tasks = data
    elif isinstance(data, dict) and isinstance(data.get("tasks"), list):
        tasks = data["tasks"]
    else:
        raise TaskosError("tasks file must be a task array or an object with a 'tasks' array")

    for index, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise TaskosError(f"Task #{index} must be an object")
        for field in ("id", "title", "status"):
            if field not in task:
                raise TaskosError(f"Task #{index} is missing required field: {field}")
        status = str(task["status"])
        if status not in PERSISTED_STATUSES:
            allowed = ", ".join(PERSISTED_STATUSES)
            raise TaskosError(
                f"Task {task['id']} has invalid persisted status {status!r}. "
                f"Allowed statuses: {allowed}. 'ready' is derived and should not be stored."
            )
        dependencies = task.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise TaskosError(f"Task {task['id']} dependencies must be a list")
    return tasks


def task_summary(task: Task) -> str:
    return f"{task['id']} - {task.get('title', '')}"


def tasks_by_id(tasks: Iterable[Task]) -> dict[str, Task]:
    result: dict[str, Task] = {}
    for task in tasks:
        task_id = str(task["id"])
        if task_id in result:
            raise TaskosError(f"Duplicate task id: {task_id}")
        result[task_id] = task
    return result


def status_by_id(tasks: Iterable[Task]) -> dict[str, str]:
    return {str(task["id"]): str(task.get("status", "")) for task in tasks}


def dependency_ready(task: Task, statuses: dict[str, str]) -> bool:
    if task.get("status") != "pending":
        return False
    return all(statuses.get(str(dependency)) == "done" for dependency in task.get("dependencies", []))


def ready_tasks(tasks: list[Task], priority_order: tuple[str, ...]) -> list[Task]:
    statuses = status_by_id(tasks)
    priority_rank = {priority: index for index, priority in enumerate(priority_order)}
    indexed = list(enumerate(tasks))
    ready = [item for item in indexed if dependency_ready(item[1], statuses)]
    ready.sort(key=lambda item: (priority_rank.get(str(item[1].get("priority", "")), 99), item[0]))
    return [task for _, task in ready]


def next_ready_task(tasks: list[Task], priority_order: tuple[str, ...]) -> Task | None:
    ready = ready_tasks(tasks, priority_order)
    return ready[0] if ready else None


def find_task(tasks: Iterable[Task], task_id: str) -> Task:
    task = tasks_by_id(tasks).get(task_id)
    if task is None:
        raise TaskosError(f"Unknown task id: {task_id}")
    return task


def unfinished_dependencies(task: Task, statuses: dict[str, str]) -> list[str]:
    return [str(dep) for dep in task.get("dependencies", []) if statuses.get(str(dep)) != "done"]


def validate_graph(tasks: list[Task]) -> list[str]:
    errors: list[str] = []
    by_id = tasks_by_id(tasks)
    for task in tasks:
        for dependency in task.get("dependencies", []):
            if str(dependency) not in by_id:
                errors.append(f"Task {task['id']} depends on unknown task {dependency}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str, chain: tuple[str, ...]) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            errors.append("Dependency cycle: " + " -> ".join((*chain, task_id)))
            return
        visiting.add(task_id)
        task = by_id[task_id]
        for dependency in task.get("dependencies", []):
            dep_id = str(dependency)
            if dep_id in by_id:
                visit(dep_id, (*chain, task_id))
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in by_id:
        visit(task_id, ())

    return errors


def merge_notes(task: Task, note: str | None) -> None:
    if not note:
        return
    existing = str(task.get("notes", "")).strip()
    task["notes"] = note.strip() if not existing else f"{existing}\n{note.strip()}"


def merge_checks(task: Task, checks: list[str]) -> None:
    if not checks:
        return
    existing = [str(check) for check in task.get("test_steps", [])]
    for check in checks:
        if check not in existing:
            existing.append(check)
    task["test_steps"] = existing
