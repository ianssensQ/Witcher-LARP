from __future__ import annotations

import json
import os
import time
from contextlib import AbstractContextManager, suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import TaskosConfig
from .model import Task, TaskosError, task_list


class TaskLock(AbstractContextManager["TaskLock"]):
    def __init__(self, path: Path, timeout_seconds: float) -> None:
        self._path = path
        self._timeout_seconds = timeout_seconds
        self._fd: int | None = None

    def __enter__(self) -> TaskLock:
        started_at = time.monotonic()
        payload = f"pid={os.getpid()}\ncreated_at={datetime.now().astimezone().isoformat()}\n"
        self._path.parent.mkdir(parents=True, exist_ok=True)

        while True:
            try:
                self._fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, payload.encode("utf-8"))
                return self
            except FileExistsError:
                if time.monotonic() - started_at >= self._timeout_seconds:
                    raise TaskosError(f"Task lock is busy: {self._path}") from None
                time.sleep(0.2)

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        with suppress(FileNotFoundError):
            self._path.unlink()


def timestamp() -> str:
    now = datetime.now().astimezone()
    offset = now.strftime("%z")
    if len(offset) == 5:
        offset = f"{offset[:3]}:{offset[3:]}"
    return f"{now.strftime('%Y-%m-%d %H:%M')} {offset}"


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TaskosError(f"Missing {path}") from exc
    except json.JSONDecodeError as exc:
        raise TaskosError(f"Invalid JSON in {path}: {exc}") from exc


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        with suppress(FileNotFoundError):
            tmp_path.unlink()


def write_if_changed(path: Path, content: str) -> bool:
    normalized = content if content.endswith("\n") else f"{content}\n"
    try:
        if path.read_text(encoding="utf-8") == normalized:
            return False
    except FileNotFoundError:
        pass
    write_text_atomic(path, normalized)
    return True


def write_json(path: Path, data: Any) -> None:
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def load_tasks(root: Path, config: TaskosConfig) -> tuple[Any, list[Task]]:
    data = read_json(config.path(root, config.tasks_file))
    return data, task_list(data)


def append_progress(root: Path, config: TaskosConfig, heading: str, lines: list[str]) -> None:
    progress_path = config.path(root, config.progress_file)
    if progress_path.exists():
        existing = progress_path.read_text(encoding="utf-8")
    else:
        existing = "# Progress Log\n"

    body = "\n".join(lines).rstrip()
    entry = f"\n{timestamp()} {heading}\n{'-' * (len(heading) + 23)}\n{body}\n"
    write_text_atomic(progress_path, existing.rstrip() + "\n" + entry)
