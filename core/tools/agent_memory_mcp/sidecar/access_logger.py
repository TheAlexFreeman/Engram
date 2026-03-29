"""Automatic ACCESS logging for transcript-observed retrievals."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .estimator import estimate_helpfulness
from .parser import ParsedSession, ToolCall

_ACCESS_TRACKED_ROOTS = (
    "memory/users",
    "memory/knowledge",
    "memory/skills",
    "memory/working/projects",
    "memory/activity",
)
_DIRECT_READ_TOOL_NAME = "memory_read_file"


@dataclass(slots=True)
class AccessLoggingResult:
    """Structured result from a sidecar ACCESS logging pass."""

    entries: list[dict[str, object]] = field(default_factory=list)
    batch_payload: dict[str, Any] | None = None
    trigger_payload: dict[str, Any] | None = None
    aggregation_payload: dict[str, Any] | None = None
    aggregated_folders: list[str] = field(default_factory=list)


@runtime_checkable
class MCPToolClient(Protocol):
    """Minimal MCP client contract needed by the sidecar logger."""

    async def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        """Call a named MCP tool and return its raw payload."""


def build_access_entries(
    session: ParsedSession,
    *,
    file_contents: Mapping[str, str] | None = None,
    estimator_name: str = "sidecar",
) -> list[dict[str, object]]:
    """Convert a parsed transcript session into ACCESS entry payloads."""

    estimator = estimator_name.strip()
    if not estimator:
        raise ValueError("estimator_name must be a non-empty string")

    files_to_log = _collect_retrieved_files(session.tool_calls)
    if not files_to_log:
        return []

    retrieved_content = _build_content_index(session.tool_calls, file_contents)
    task_description = _select_task_description(session)
    response_text = "\n\n".join(
        message.strip() for message in session.assistant_messages if message.strip()
    )
    note = f"auto-logged from sidecar transcript session {session.session_id}"

    entries: list[dict[str, object]] = []
    for file_path in files_to_log:
        helpfulness = estimate_helpfulness(
            retrieved_content.get(file_path, ""),
            response_text,
            task_description,
        )
        entries.append(
            {
                "file": file_path,
                "task": task_description,
                "helpfulness": helpfulness,
                "note": note,
                "mode": "read",
                "estimator": estimator,
            }
        )
    return entries


class AccessLogger:
    """Batch ACCESS logging through the Engram MCP server."""

    def __init__(self, client: MCPToolClient) -> None:
        self._client = client

    async def log_session_access(
        self,
        session: ParsedSession,
        *,
        session_id: str | None = None,
        file_contents: Mapping[str, str] | None = None,
        min_helpfulness: float | None = None,
    ) -> AccessLoggingResult:
        """Log ACCESS entries for one observed session and run aggregation if needed."""

        entries = build_access_entries(session, file_contents=file_contents)
        if not entries:
            return AccessLoggingResult(entries=[])

        batch_arguments: dict[str, object] = {"access_entries": entries}
        if session_id is not None:
            batch_arguments["session_id"] = session_id
        if min_helpfulness is not None:
            batch_arguments["min_helpfulness"] = float(min_helpfulness)

        batch_payload = await self._call_json_tool(
            "memory_log_access_batch",
            batch_arguments,
        )
        trigger_payload = await self._call_json_tool("memory_check_aggregation_triggers")
        aggregated_folders = _folders_to_aggregate(batch_payload, trigger_payload)

        aggregation_payload: dict[str, Any] | None = None
        if aggregated_folders:
            aggregation_payload = await self._call_json_tool(
                "memory_run_aggregation",
                {"folders": aggregated_folders, "dry_run": False},
            )

        return AccessLoggingResult(
            entries=entries,
            batch_payload=batch_payload,
            trigger_payload=trigger_payload,
            aggregation_payload=aggregation_payload,
            aggregated_folders=aggregated_folders,
        )

    async def _call_json_tool(
        self,
        name: str,
        arguments: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        raw_payload = await self._client.call_tool(name, arguments)
        return _coerce_tool_response(raw_payload)


def _normalize_tool_name(name: str) -> str:
    return name.rsplit("__", 1)[-1]


def _collect_retrieved_files(tool_calls: list[ToolCall]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    for file_path, _ in _iter_direct_read_observations(tool_calls):
        if file_path in seen:
            continue
        seen.add(file_path)
        ordered.append(file_path)

    return ordered


def _build_content_index(
    tool_calls: list[ToolCall],
    file_contents: Mapping[str, str] | None,
) -> dict[str, str]:
    indexed: dict[str, str] = {}
    normalized_file_contents: dict[str, str] = {}

    if file_contents:
        for raw_path, content in file_contents.items():
            normalized = _normalize_file_path(raw_path)
            if normalized is None:
                continue
            normalized_file_contents[normalized] = content

    for file_path, retrieved_text in _iter_direct_read_observations(tool_calls):
        if file_path in normalized_file_contents:
            indexed.setdefault(file_path, normalized_file_contents[file_path])
            continue
        if retrieved_text:
            indexed.setdefault(file_path, retrieved_text)

    return indexed


def _select_task_description(session: ParsedSession) -> str:
    for message in reversed(session.user_messages):
        stripped = message.strip()
        if stripped:
            return stripped
    return f"observed transcript session {session.session_id}"


def _iter_direct_read_observations(tool_calls: list[ToolCall]) -> list[tuple[str, str]]:
    observations: list[tuple[str, str]] = []
    for tool_call in tool_calls:
        observation = _extract_direct_read_observation(tool_call)
        if observation is not None:
            observations.append(observation)
    return observations


def _extract_direct_read_observation(tool_call: ToolCall) -> tuple[str, str] | None:
    if _normalize_tool_name(tool_call.name) != _DIRECT_READ_TOOL_NAME:
        return None

    args_payload = _coerce_json_like(tool_call.args)
    result_payload = _coerce_json_like(tool_call.result)

    raw_path: str | None = None
    if isinstance(result_payload, Mapping):
        candidate = result_payload.get("path")
        if isinstance(candidate, str):
            raw_path = candidate
    if raw_path is None and isinstance(args_payload, Mapping):
        candidate = args_payload.get("path")
        if isinstance(candidate, str):
            raw_path = candidate
    if raw_path is None:
        return None

    normalized_path = _normalize_file_path(raw_path)
    if normalized_path is None:
        return None

    return normalized_path, _extract_direct_read_text(result_payload)


def _extract_direct_read_text(payload: Any) -> str:
    if isinstance(payload, str) and payload.strip():
        return payload.strip()

    if not isinstance(payload, Mapping):
        return ""

    inline = payload.get("inline")
    content = payload.get("content")
    if inline is True and isinstance(content, str) and content.strip():
        return content.strip()

    temp_file = payload.get("temp_file")
    if isinstance(temp_file, str):
        temp_path = Path(temp_file)
        if temp_path.exists():
            try:
                return temp_path.read_text(encoding="utf-8").strip()
            except OSError:
                pass

    return ""


def _normalize_file_path(value: str) -> str | None:
    candidate = value.strip().strip('"').strip("'")
    if not candidate:
        return None

    normalized = candidate.replace("\\", "/")
    if normalized.startswith("file://"):
        normalized = normalized[len("file://") :]
    normalized = normalized.rstrip("/.,:;)")

    if normalized.startswith("core/"):
        normalized = normalized[len("core/") :]

    for marker in ("/core/memory/", "/memory/"):
        if marker in normalized:
            normalized = "memory/" + normalized.split(marker, 1)[1]
            break

    if not _is_access_tracked_path(normalized):
        return None
    return normalized


def _is_access_tracked_path(path: str) -> bool:
    return any(path == root or path.startswith(root + "/") for root in _ACCESS_TRACKED_ROOTS)


def _folders_to_aggregate(
    batch_payload: Mapping[str, Any],
    trigger_payload: Mapping[str, Any],
) -> list[str]:
    new_state = batch_payload.get("new_state")
    if not isinstance(new_state, Mapping):
        return []

    changed_logs: list[str] = []
    access_jsonls = new_state.get("access_jsonls")
    if isinstance(access_jsonls, list):
        changed_logs.extend(
            str(item)
            for item in access_jsonls
            if isinstance(item, str) and item.endswith("/ACCESS.jsonl")
        )
    access_jsonl = new_state.get("access_jsonl")
    if isinstance(access_jsonl, str) and access_jsonl.endswith("/ACCESS.jsonl"):
        changed_logs.append(access_jsonl)

    above_trigger = trigger_payload.get("above_trigger")
    if not isinstance(above_trigger, list):
        return []

    hot_logs = {str(item) for item in above_trigger if isinstance(item, str)}
    folders = {log_path.rsplit("/", 1)[0] for log_path in changed_logs if log_path in hot_logs}
    return sorted(folders)


def _coerce_tool_response(payload: Any) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return dict(payload)

    if hasattr(payload, "content"):
        content = getattr(payload, "content")
        if isinstance(content, list):
            fragments: list[str] = []
            for item in content:
                text = getattr(item, "text", None)
                if isinstance(text, str) and text.strip():
                    fragments.append(text)
            if fragments:
                return _coerce_tool_response("\n".join(fragments))

    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return {}
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            return {"raw": stripped}
        if isinstance(decoded, Mapping):
            return dict(decoded)
        return {"data": decoded}

    return {"raw": payload}


def _coerce_json_like(payload: Any) -> Any:
    if not isinstance(payload, str):
        return payload

    stripped = payload.strip()
    if not stripped or stripped[0] not in "[{":
        return stripped

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return stripped


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
