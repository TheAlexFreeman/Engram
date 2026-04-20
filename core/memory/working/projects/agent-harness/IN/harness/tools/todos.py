from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .fs import WorkspaceScope

_TODO_STATUSES = frozenset({"pending", "in_progress", "completed", "cancelled"})
_MAX_ITEMS = 100
_MAX_CONTENT_LEN = 2000
_DEFAULT_FILE = "todos.json"
_ANALYZE_ID_CAP = 30


def _todo_path(scope: WorkspaceScope, args: dict) -> Path:
    return scope.resolve(str(args.get("path", _DEFAULT_FILE)))


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"cannot read todos file: {e}") from e
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in todos file: {e}") from e
    if not isinstance(data, list):
        raise ValueError("todos file must contain a JSON array")
    return [x for x in data if isinstance(x, dict)]


def _validate_item(item: Mapping[str, Any]) -> dict[str, str]:
    if not isinstance(item, Mapping):
        raise ValueError("each todo must be an object")
    tid = item.get("id")
    if not isinstance(tid, str) or not tid.strip():
        raise ValueError("each todo needs a non-empty string id")
    content = item.get("content")
    if not isinstance(content, str):
        raise ValueError("each todo needs a string content")
    if len(content) > _MAX_CONTENT_LEN:
        raise ValueError(f"content exceeds {_MAX_CONTENT_LEN} characters for id {tid.strip()!r}")
    status = item.get("status")
    if not isinstance(status, str) or status not in _TODO_STATUSES:
        raise ValueError(
            f"invalid status for id {tid.strip()!r}: {status!r} "
            f"(use one of: {', '.join(sorted(_TODO_STATUSES))})"
        )
    return {"id": tid.strip(), "content": content, "status": status}


def _validate_list(items: Sequence[Any]) -> list[dict[str, str]]:
    if len(items) > _MAX_ITEMS:
        raise ValueError(f"at most {_MAX_ITEMS} todos allowed")
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for i, raw in enumerate(items):
        row = _validate_item(raw if isinstance(raw, Mapping) else {})
        if row["id"] in seen:
            raise ValueError(f"duplicate todo id: {row['id']!r}")
        seen.add(row["id"])
        out.append(row)
    return out


_SAVE_LOCKS: dict[str, threading.Lock] = {}
_SAVE_LOCKS_GUARD = threading.Lock()


def _lock_for(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _SAVE_LOCKS_GUARD:
        lock = _SAVE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _SAVE_LOCKS[key] = lock
        return lock


def _atomic_replace(src: Path, dst: Path) -> None:
    """os.replace with a short retry on Windows, where antivirus scanners or
    transient filesystem locks can surface PermissionError on freshly-written
    source files even when no Python code holds them open."""
    delay = 0.005
    last_err: OSError | None = None
    for _ in range(10):
        try:
            os.replace(src, dst)
            return
        except PermissionError as exc:
            last_err = exc
            time.sleep(delay)
            delay = min(delay * 2, 0.1)
    assert last_err is not None
    raise last_err


def _save(path: Path, items: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(items, indent=2, ensure_ascii=False) + "\n"
    # Unique tmp name per call so concurrent writers don't clobber each other's
    # tmp file before the atomic replace; a per-path in-process lock serializes
    # replace-over-destination (Windows can error on concurrent replaces).
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        with _lock_for(path):
            _atomic_replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _relative_display(args: dict) -> str:
    return str(args.get("path", _DEFAULT_FILE))


class WriteTodos:
    name = "write_todos"
    description = (
        "Replace the entire todo list in the workspace (default file: todos.json). "
        "This overwrites previous todos; use update_todo for single-item status or content changes. "
        f"Statuses: {', '.join(sorted(_TODO_STATUSES))}. "
        f"At most {_MAX_ITEMS} items; content per item at most {_MAX_CONTENT_LEN} characters. "
        "Consider adding todos.json to .gitignore if you do not want it committed."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "Full replacement list of todo objects.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "content": {"type": "string"},
                        "status": {"type": "string"},
                    },
                    "required": ["id", "content", "status"],
                },
            },
            "path": {
                "type": "string",
                "description": f"Workspace-relative JSON path. Default: {_DEFAULT_FILE}.",
            },
        },
        "required": ["todos"],
    }

    def __init__(self, scope: WorkspaceScope):
        self.scope = scope

    def run(self, args: dict) -> str:
        path = _todo_path(self.scope, args)
        todos = args.get("todos")
        if not isinstance(todos, list):
            raise ValueError("todos must be an array")
        validated = _validate_list(todos)
        _save(path, validated)
        rel = _relative_display(args)
        return f"wrote {len(validated)} todo(s) to {rel}"


class ReadTodos:
    name = "read_todos"
    description = (
        "List todos from the workspace JSON file (default todos.json). "
        "Optional status filter. Paths are workspace-relative."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": f"Workspace-relative path. Default: {_DEFAULT_FILE}.",
            },
            "status": {
                "type": "string",
                "description": f"If set, only todos with this status ({', '.join(sorted(_TODO_STATUSES))}).",
            },
        },
    }

    def __init__(self, scope: WorkspaceScope):
        self.scope = scope

    def run(self, args: dict) -> str:
        path = _todo_path(self.scope, args)
        items = _load(path)
        status_filter = args.get("status")
        if status_filter is not None:
            if not isinstance(status_filter, str) or status_filter not in _TODO_STATUSES:
                raise ValueError(
                    f"status must be one of: {', '.join(sorted(_TODO_STATUSES))}"
                )
            items = [i for i in items if i.get("status") == status_filter]
        if not items:
            return "(no todos)"
        lines: list[str] = []
        for i, row in enumerate(items, start=1):
            try:
                v = _validate_item(row)
            except ValueError as e:
                lines.append(f"{i}. (invalid row skipped: {e})")
                continue
            lines.append(f"{i}. [{v['status']}] {v['id']}: {v['content']}")
        return "\n".join(lines) + "\n"


class UpdateTodo:
    name = "update_todo"
    description = (
        "Update one todo by id (status and/or content) without replacing the whole list. "
        f"Default file todos.json; statuses: {', '.join(sorted(_TODO_STATUSES))}."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Todo id to update."},
            "status": {"type": "string"},
            "content": {"type": "string"},
            "path": {
                "type": "string",
                "description": f"Workspace-relative path. Default: {_DEFAULT_FILE}.",
            },
        },
        "required": ["id"],
    }

    def __init__(self, scope: WorkspaceScope):
        self.scope = scope

    def run(self, args: dict) -> str:
        tid = args.get("id")
        if not isinstance(tid, str) or not tid.strip():
            raise ValueError("id must be a non-empty string")
        tid = tid.strip()
        new_status = args.get("status")
        new_content = args.get("content")
        has_status = new_status is not None
        has_content = new_content is not None
        if not has_status and not has_content:
            raise ValueError("provide at least one of status or content")
        if has_status and (
            not isinstance(new_status, str) or new_status not in _TODO_STATUSES
        ):
            raise ValueError(f"status must be one of: {', '.join(sorted(_TODO_STATUSES))}")
        if has_content:
            if not isinstance(new_content, str):
                raise ValueError("content must be a string")
            if len(new_content) > _MAX_CONTENT_LEN:
                raise ValueError(f"content exceeds {_MAX_CONTENT_LEN} characters")

        path = _todo_path(self.scope, args)
        items_raw = _load(path)
        items = []
        for row in items_raw:
            if isinstance(row, dict):
                items.append(dict(row))
        found = False
        for row in items:
            rid = row.get("id")
            if isinstance(rid, str) and rid.strip() == tid:
                if has_status:
                    row["status"] = new_status
                if has_content:
                    row["content"] = new_content
                validated_row = _validate_item(row)
                row.clear()
                row.update(validated_row)
                found = True
                break
        if not found:
            raise ValueError(f"unknown todo id: {tid!r}")
        _validate_list(items)
        _save(path, items)
        return f"updated todo {tid!r} in {_relative_display(args)}"


class AnalyzeTodos:
    name = "analyze_todos"
    description = (
        "Summarize todos (counts by status, ids for pending/in_progress) without printing full bodies. "
        f"Default file {_DEFAULT_FILE}."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": f"Workspace-relative path. Default: {_DEFAULT_FILE}.",
            },
        },
    }

    def __init__(self, scope: WorkspaceScope):
        self.scope = scope

    def run(self, args: dict) -> str:
        path = _todo_path(self.scope, args)
        items_raw = _load(path)
        valid: list[dict[str, str]] = []
        for row in items_raw:
            if not isinstance(row, dict):
                continue
            try:
                valid.append(_validate_item(row))
            except ValueError:
                continue

        counts: dict[str, int] = {s: 0 for s in _TODO_STATUSES}
        for v in valid:
            counts[v["status"]] = counts.get(v["status"], 0) + 1

        pending_ids = [v["id"] for v in valid if v["status"] == "pending"][:_ANALYZE_ID_CAP]
        inprog_ids = [v["id"] for v in valid if v["status"] == "in_progress"][:_ANALYZE_ID_CAP]
        n_inprog = counts.get("in_progress", 0)

        lines = [
            f"file: {_relative_display(args)}",
            f"total (valid rows): {len(valid)}",
            "counts: "
            + ", ".join(f"{k}={counts.get(k, 0)}" for k in sorted(_TODO_STATUSES)),
        ]
        if pending_ids:
            lines.append("pending ids (up to 30): " + ", ".join(pending_ids))
        if inprog_ids:
            lines.append("in_progress ids (up to 30): " + ", ".join(inprog_ids))
        if n_inprog > 1:
            lines.append(
                f"note: {n_inprog} items are in_progress; consider marking extras pending or completed."
            )
        return "\n".join(lines) + "\n"
