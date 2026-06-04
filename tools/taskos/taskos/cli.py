from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .agents import ensure_agents_block
from .config import TaskosConfig, default_config, load_config, render_config
from .model import (
    Task,
    TaskosError,
    find_task,
    merge_checks,
    merge_notes,
    next_ready_task,
    ready_tasks,
    status_by_id,
    task_summary,
    unfinished_dependencies,
    validate_graph,
)
from .renderers import (
    generated_active_tasks,
    generated_dashboard,
    generated_dashboard_wrapper,
    generated_kanban,
)
from .schema import schema_json
from .storage import TaskLock, append_progress, load_tasks, write_if_changed, write_json


def project_config(args: argparse.Namespace) -> tuple[Path, TaskosConfig]:
    root = args.root.resolve()
    config = load_config(root, args.config.resolve() if args.config else None)
    return root, config


def task_file_path(root: Path, config: TaskosConfig) -> Path:
    return config.path(root, config.tasks_file)


def progress_file_path(root: Path, config: TaskosConfig) -> Path:
    return config.path(root, config.progress_file)


def lock_path(root: Path, config: TaskosConfig) -> Path:
    return config.path(root, config.lock_file)


def empty_tasks(project_name: str) -> dict[str, Any]:
    return {
        "project": {
            "name": project_name,
            "task_source": "tasks.json",
            "active_task_view": "docs/active-tasks.md",
            "created_at": datetime.now().astimezone().isoformat(),
        },
        "agent_instructions": {
            "before_start": [
                (
                    "Use docs/active-tasks.md or python scripts/taskctl.py ready "
                    "for ordinary task orientation."
                ),
                (
                    "Use tasks.json as the canonical full dependency graph only "
                    "when editing task metadata/dependencies or when the compact view is insufficient."
                ),
                "Use progress.txt as the completion log, not as a replacement for the dependency graph.",
                (
                    "Use python scripts/taskctl.py claim before implementation to atomically "
                    "claim one dependency-ready task."
                ),
                "Implement only the selected task.",
            ],
            "before_finish": [
                "Run focused checks for the changed area.",
                (
                    "Use python scripts/taskctl.py done/block/release to update task status "
                    "and progress."
                ),
                "Do not manually edit generated task views.",
            ],
        },
        "tasks": [],
    }


def render_taskctl_script() -> str:
    return '''#!/usr/bin/env python
"""Project-local compatibility wrapper for Codex TaskOS."""

from pathlib import Path
import sys

from taskos.cli import main


def _has_root_argument(argv):
    return any(arg == "--root" or arg.startswith("--root=") for arg in argv)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not _has_root_argument(args):
        args = ["--root", str(Path(__file__).resolve().parents[1]), *args]
    raise SystemExit(main(args))
'''


def validate_or_raise(tasks: list[Task]) -> None:
    errors = validate_graph(tasks)
    if errors:
        raise TaskosError("\n".join(errors))


def generated_outputs(root: Path, config: TaskosConfig, tasks: list[Task]) -> dict[Path, str]:
    dashboard_path = config.path(root, config.generated_dashboard)
    outputs = {
        config.path(root, config.generated_kanban): generated_kanban(config, tasks),
        dashboard_path: generated_dashboard(config, tasks),
    }
    active_value = config.generated_active.strip()
    if active_value:
        outputs[config.path(root, active_value)] = generated_active_tasks(config, tasks)
    entrypoint_value = config.generated_dashboard_entrypoint.strip()
    if entrypoint_value:
        entrypoint_path = config.path(root, entrypoint_value)
        if entrypoint_path != dashboard_path:
            iframe_src = Path(os.path.relpath(dashboard_path, entrypoint_path.parent)).as_posix()
            outputs[entrypoint_path] = generated_dashboard_wrapper(config, iframe_src)
    return outputs


def sync_generated_files(root: Path, config: TaskosConfig, tasks: list[Task]) -> list[Path]:
    outputs = generated_outputs(root, config, tasks)
    changed: list[Path] = []
    for path, content in outputs.items():
        if write_if_changed(path, content):
            changed.append(path)
    return changed


def task_summary_list(tasks: list[Task], *, limit: int = 5) -> str:
    shown = [task_summary(task) for task in tasks[:limit]]
    if len(tasks) > limit:
        shown.append(f"+{len(tasks) - limit} more")
    return "; ".join(shown)


def git_dirty_change_count(root: Path, lock_file: str) -> int | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    ignored_lock = lock_file.replace("\\", "/").lstrip("./")
    return len(
        [
            line
            for line in result.stdout.splitlines()
            if line.strip() and git_dirty_status_path(line) != ignored_lock
        ]
    )


def git_dirty_status_path(line: str) -> str:
    path = line[3:].strip()
    if " -> " in path:
        path = path.rsplit(" -> ", maxsplit=1)[-1]
    return path.strip('"').replace("\\", "/")


def claim_coordination_context(
    root: Path,
    config: TaskosConfig,
    tasks: list[Task],
    claimed_task_id: str,
) -> list[str]:
    context: list[str] = []
    active_tasks = [
        task
        for task in tasks
        if task.get("status") == "in_progress" and str(task.get("id")) != claimed_task_id
    ]
    if active_tasks:
        context.append(
            "- already in progress: "
            f"{task_summary_list(active_tasks)}. Parallel claims are allowed; "
            "avoid overlapping files."
        )

    dirty_count = git_dirty_change_count(root, config.lock_file)
    if dirty_count:
        context.append(
            "- worktree: "
            f"{dirty_count} local change(s) existed before this claim. "
            "This is informational in shared worktrees; do not revert unrelated changes."
        )
    return context


def append_generated_result(
    lines: list[str],
    root: Path,
    changed: list[Path],
    sync_warning: str | None,
) -> None:
    if changed:
        lines.append("")
        lines.append("Generated files refreshed:")
        lines.extend(f"- {path.relative_to(root)}" for path in changed)
    if sync_warning:
        lines.append("")
        lines.append("Generated files refresh warning:")
        lines.append(f"- {sync_warning}")


def sync_generated_files_best_effort(
    root: Path,
    config: TaskosConfig,
    tasks: list[Task],
) -> tuple[list[Path], str | None]:
    try:
        return sync_generated_files(root, config, tasks), None
    except Exception as exc:
        return [], f"Generated files refresh failed: {exc}"


def append_progress_best_effort(
    root: Path,
    config: TaskosConfig,
    heading: str,
    lines: list[str],
) -> str | None:
    try:
        append_progress(root, config, heading, lines)
    except Exception as exc:
        return f"Progress append failed: {exc}"
    return None


def print_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"taskos warning: {warning}", file=sys.stderr)


def select_claim_task(
    tasks: list[Task],
    priority_order: tuple[str, ...],
    requested_task_id: str | None,
) -> Task:
    statuses = status_by_id(tasks)
    if requested_task_id:
        task = find_task(tasks, requested_task_id)
        if task.get("status") != "pending":
            raise TaskosError(f"{requested_task_id} is {task.get('status')}, not pending")
        missing = unfinished_dependencies(task, statuses)
        if missing:
            dependencies = ", ".join(missing)
            raise TaskosError(f"{requested_task_id} has unfinished dependencies: {dependencies}")
        return task

    task = next_ready_task(tasks, priority_order)
    if task is None:
        raise TaskosError("No dependency-ready pending task exists")
    return task


def print_task_result(
    task: Task,
    action: str,
    tasks: list[Task],
    config: TaskosConfig,
    json_output: bool,
) -> None:
    next_task = next_ready_task(tasks, config.priority_order)
    if json_output:
        print(
            json.dumps(
                {
                    "action": action,
                    "task": task,
                    "next_ready": next_task,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print(f"{action}: {task_summary(task)}")
    if next_task:
        print(f"Next dependency-ready pending: {task_summary(next_task)}")
    else:
        print("Next dependency-ready pending: none")


def command_init(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    project_name = args.project_name or root.name
    config = default_config(project_name=project_name)

    config_path = args.config or root / "taskos.toml"
    config_changed = False
    if args.force or not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(render_config(config), encoding="utf-8", newline="\n")
        config_changed = True
    else:
        config = load_config(root, config_path)

    tasks_path = task_file_path(root, config)
    if args.force or not tasks_path.exists():
        write_json(tasks_path, empty_tasks(config.project_name))

    script_path = config.path(root, config.taskctl_script)
    script_changed = False
    if args.force or not script_path.exists():
        script_changed = write_if_changed(script_path, render_taskctl_script())

    progress_path = progress_file_path(root, config)
    if args.force or not progress_path.exists():
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        progress_path.write_text("# Progress Log\n", encoding="utf-8", newline="\n")

    _, tasks = load_tasks(root, config)
    validate_or_raise(tasks)
    changed = sync_generated_files(root, config, tasks)
    agents_changed = False if args.no_agents else ensure_agents_block(root, config)

    if args.json:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "config": str(config_path),
                    "config_changed": config_changed,
                    "taskctl_script_changed": script_changed,
                    "agents_changed": agents_changed,
                    "generated": [str(path.relative_to(root)) for path in changed],
                },
                indent=2,
            )
        )
        return 0

    print(f"Initialized TaskOS in {root}")
    if config_changed:
        print(f"created {config_path.relative_to(root)}")
    if script_changed:
        print(f"updated {script_path.relative_to(root)}")
    if agents_changed:
        print("updated AGENTS.md")
    for path in changed:
        print(f"updated {path.relative_to(root)}")
    return 0


def command_claim(args: argparse.Namespace) -> int:
    root, config = project_config(args)
    with TaskLock(lock_path(root, config), args.lock_timeout):
        data, tasks = load_tasks(root, config)
        validate_or_raise(tasks)
        task = select_claim_task(tasks, config.priority_order, args.task_id)
        coordination_context = claim_coordination_context(root, config, tasks, str(task["id"]))
        task["status"] = "in_progress"
        write_json(task_file_path(root, config), data)
        changed, sync_warning = sync_generated_files_best_effort(root, config, tasks)
        lines = [
            f"Task: {task_summary(task)}.",
            "",
            "Claim:",
            f"- assignee: {args.assignee}",
            f"- intent: {args.intent}",
        ]
        for assumption in args.assumption:
            lines.append(f"- assumption: {assumption}")
        if coordination_context:
            lines.append("")
            lines.append("Coordination Context:")
            lines.extend(coordination_context)
        append_generated_result(lines, root, changed, sync_warning)
        progress_warning = append_progress_best_effort(root, config, f"{task['id']} Claim", lines)
        print_warnings([warning for warning in (sync_warning, progress_warning) if warning])
        print_task_result(task, "Claimed", tasks, config, args.json)
        if not args.json and coordination_context:
            print("Coordination context:")
            for line in coordination_context:
                print(line)
    return 0


def command_done(args: argparse.Namespace) -> int:
    root, config = project_config(args)
    with TaskLock(lock_path(root, config), args.lock_timeout):
        data, tasks = load_tasks(root, config)
        validate_or_raise(tasks)
        task = find_task(tasks, args.task_id)
        task["status"] = "done"
        merge_notes(task, args.notes)
        merge_checks(task, args.check)
        write_json(task_file_path(root, config), data)
        changed, sync_warning = sync_generated_files_best_effort(root, config, tasks)
        lines = [
            f"Task: {task_summary(task)}.",
            "",
            "Done:",
            f"- {args.summary}",
        ]
        if args.check:
            lines.append("")
            lines.append("Verification:")
            lines.extend(f"- {check}" for check in args.check)
        if args.notes:
            lines.append("")
            lines.append("Notes:")
            lines.append(f"- {args.notes}")
        append_generated_result(lines, root, changed, sync_warning)
        next_task = next_ready_task(tasks, config.priority_order)
        lines.append("")
        lines.append("Next Dependency-Ready Pending Task:")
        lines.append(f"- {task_summary(next_task)}" if next_task else "- None")
        progress_warning = append_progress_best_effort(root, config, f"{task['id']} Done", lines)
        print_warnings([warning for warning in (sync_warning, progress_warning) if warning])
        print_task_result(task, "Done", tasks, config, args.json)
    return 0


def command_block(args: argparse.Namespace) -> int:
    root, config = project_config(args)
    with TaskLock(lock_path(root, config), args.lock_timeout):
        data, tasks = load_tasks(root, config)
        validate_or_raise(tasks)
        task = find_task(tasks, args.task_id)
        task["status"] = "blocked"
        merge_notes(task, args.reason)
        merge_checks(task, args.check)
        write_json(task_file_path(root, config), data)
        changed, sync_warning = sync_generated_files_best_effort(root, config, tasks)
        lines = [
            f"Task: {task_summary(task)}.",
            "",
            "Blocked:",
            f"- {args.reason}",
        ]
        if args.check:
            lines.append("")
            lines.append("Verification:")
            lines.extend(f"- {check}" for check in args.check)
        append_generated_result(lines, root, changed, sync_warning)
        progress_warning = append_progress_best_effort(root, config, f"{task['id']} Blocked", lines)
        print_warnings([warning for warning in (sync_warning, progress_warning) if warning])
        print_task_result(task, "Blocked", tasks, config, args.json)
    return 0


def command_release(args: argparse.Namespace) -> int:
    root, config = project_config(args)
    with TaskLock(lock_path(root, config), args.lock_timeout):
        data, tasks = load_tasks(root, config)
        validate_or_raise(tasks)
        task = find_task(tasks, args.task_id)
        task["status"] = "pending"
        merge_notes(task, args.reason)
        write_json(task_file_path(root, config), data)
        changed, sync_warning = sync_generated_files_best_effort(root, config, tasks)
        lines = [
            f"Task: {task_summary(task)}.",
            "",
            "Released:",
            f"- {args.reason}",
        ]
        append_generated_result(lines, root, changed, sync_warning)
        progress_warning = append_progress_best_effort(
            root,
            config,
            f"{task['id']} Released",
            lines,
        )
        print_warnings([warning for warning in (sync_warning, progress_warning) if warning])
        print_task_result(task, "Released", tasks, config, args.json)
    return 0


def command_ready(args: argparse.Namespace) -> int:
    root, config = project_config(args)
    _, tasks = load_tasks(root, config)
    validate_or_raise(tasks)
    ready = ready_tasks(tasks, config.priority_order)
    if args.json:
        print(json.dumps(ready, ensure_ascii=False, indent=2))
        return 0
    if not ready:
        print("No dependency-ready pending tasks.")
        return 2
    for task in ready:
        print(task_summary(task))
    return 0


def command_sync(args: argparse.Namespace) -> int:
    root, config = project_config(args)
    _, tasks = load_tasks(root, config)
    validate_or_raise(tasks)
    changed = sync_generated_files(root, config, tasks)
    if changed:
        for path in changed:
            print(f"updated {path.relative_to(root)}")
    else:
        print("generated files already up to date")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    root, config = project_config(args)
    _, tasks = load_tasks(root, config)
    validate_or_raise(tasks)
    print(f"{config.tasks_file} is valid ({len(tasks)} tasks).")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    root, config = project_config(args)
    _, tasks = load_tasks(root, config)
    validate_or_raise(tasks)
    ready = ready_tasks(tasks, config.priority_order)
    generated = generated_outputs(root, config, tasks)
    stale = []
    for path, expected in generated.items():
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            stale.append(path)

    result = {
        "root": str(root),
        "project_name": config.project_name,
        "tasks": len(tasks),
        "ready": len(ready),
        "stale_generated_files": [str(path.relative_to(root)) for path in stale],
        "agents_block": (root / "AGENTS.md").exists(),
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"TaskOS doctor: {config.project_name}")
        print(f"- tasks: {len(tasks)}")
        print(f"- dependency-ready: {len(ready)}")
        if stale:
            print("- generated files need sync:")
            for path in stale:
                print(f"  - {path.relative_to(root)}")
        else:
            print("- generated files are up to date")
        print(f"- AGENTS.md present: {result['agents_block']}")
    return 0


def command_schema(args: argparse.Namespace) -> int:
    if args.output:
        args.output.write_text(schema_json(), encoding="utf-8", newline="\n")
        print(f"wrote {args.output}")
    else:
        print(schema_json(), end="")
    return 0


def command_watch(args: argparse.Namespace) -> int:
    root, config = project_config(args)
    tasks_path = task_file_path(root, config)
    last_mtime = 0.0
    print(f"Watching {tasks_path} every {args.interval:g}s. Press Ctrl+C to stop.")
    while True:
        try:
            mtime = tasks_path.stat().st_mtime
            if mtime != last_mtime:
                _, tasks = load_tasks(root, config)
                validate_or_raise(tasks)
                changed = sync_generated_files(root, config, tasks)
                if changed:
                    changed_list = ", ".join(str(path.relative_to(root)) for path in changed)
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} synced {changed_list}")
                last_mtime = mtime
            time.sleep(args.interval)
        except KeyboardInterrupt:
            print("Stopped.")
            return 0


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root.")
    parser.add_argument("--config", type=Path, help="Path to taskos.toml.")
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for the task lock on mutating commands.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control a Codex TaskOS implementation queue.")
    add_common_options(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Initialize TaskOS files in a project.")
    init.add_argument("--project-name", help="Project display name.")
    init.add_argument("--force", action="store_true", help="Overwrite generated starter files.")
    init.add_argument("--no-agents", action="store_true", help="Do not update AGENTS.md.")
    init.set_defaults(func=command_init)

    claim = subparsers.add_parser("claim", help="Claim one dependency-ready pending task.")
    claim.add_argument("task_id", nargs="?", help="Optional explicit task id to claim.")
    claim.add_argument("--assignee", default="codex", help="Short assignee label for progress.")
    claim.add_argument(
        "--intent",
        default="Implement the selected task only.",
        help="Claim intent.",
    )
    claim.add_argument(
        "--assumption",
        action="append",
        default=[],
        help="Known setup assumption to include in progress. Repeatable.",
    )
    claim.set_defaults(func=command_claim)

    done = subparsers.add_parser("done", help="Mark a task done and append progress.")
    done.add_argument("task_id")
    done.add_argument("--summary", required=True, help="Short completion summary.")
    done.add_argument("--notes", help="Notes to append to the task metadata.")
    done.add_argument("--check", action="append", default=[], help="Verification command/result.")
    done.set_defaults(func=command_done)

    block = subparsers.add_parser("block", help="Mark a task blocked and append progress.")
    block.add_argument("task_id")
    block.add_argument("--reason", required=True, help="Blocker reason.")
    block.add_argument("--check", action="append", default=[], help="Verification command/result.")
    block.set_defaults(func=command_block)

    release = subparsers.add_parser("release", help="Release a task back to pending.")
    release.add_argument("task_id")
    release.add_argument("--reason", required=True, help="Release reason.")
    release.set_defaults(func=command_release)

    ready = subparsers.add_parser("ready", help="List dependency-ready pending tasks.")
    ready.set_defaults(func=command_ready)

    sync = subparsers.add_parser("sync", help="Regenerate kanban and dashboard.")
    sync.set_defaults(func=command_sync)

    validate = subparsers.add_parser("validate", help="Validate the task file.")
    validate.set_defaults(func=command_validate)

    doctor = subparsers.add_parser("doctor", help="Validate and inspect TaskOS project state.")
    doctor.set_defaults(func=command_doctor)

    schema = subparsers.add_parser("schema", help="Print or write the tasks JSON schema.")
    schema.add_argument("--output", type=Path, help="Write schema JSON to this path.")
    schema.set_defaults(func=command_schema)

    watch = subparsers.add_parser("watch", help="Continuously sync generated files.")
    watch.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds.")
    watch.set_defaults(func=command_watch)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except TaskosError as exc:
        print(f"taskos: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
