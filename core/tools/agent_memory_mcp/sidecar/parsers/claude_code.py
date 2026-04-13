"""Claude Code transcript parsing."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..parser import DialogueTurn, ParsedSession, ToolCall, TranscriptFile

_RELATIVE_PATH_FIELD_NAMES = {
    "file",
    "filepath",
    "file_path",
    "path",
    "paths",
    "target",
    "targets",
}
_ROOT_FILES = frozenset(
    {"README.md", "CHANGELOG.md", "AGENTS.md", "CLAUDE.md", "agent-bootstrap.toml"}
)
_RELATIVE_FILE_RE = re.compile(
    r"^(?:memory|governance|HUMANS|views|tools)/[A-Za-z0-9._/\-]+\.(?:md|jsonl|ya?ml|toml|py|js|html|css)$"
)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_duration_ms(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("duration_ms", "durationMs", "latency_ms"):
        raw = payload.get(key)
        if raw is None:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def _coerce_text_blocks(content: Any) -> list[str]:
    if isinstance(content, str):
        stripped = content.strip()
        return [stripped] if stripped else []
    if not isinstance(content, list):
        return []

    text_blocks: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "text":
            continue
        text = str(block.get("text", "")).strip()
        if text:
            text_blocks.append(text)
    return text_blocks


def _normalize_file_reference(value: str) -> str | None:
    candidate = value.strip().strip('"').strip("'")
    if not candidate:
        return None

    normalized = candidate.replace("\\", "/")
    if normalized.startswith("file://"):
        normalized = normalized[len("file://") :]
    normalized = normalized.rstrip("/.,:;)")

    if normalized in _ROOT_FILES:
        return normalized
    if normalized.startswith("core/"):
        normalized = normalized[len("core/") :]
    if _RELATIVE_FILE_RE.match(normalized):
        return normalized

    for marker in ("/core/memory/", "/core/governance/", "/core/HUMANS/", "/core/views/"):
        if marker in normalized:
            return normalized.split("/core/", 1)[1]
    for marker in ("/memory/", "/governance/", "/HUMANS/", "/views/"):
        if marker in normalized:
            return marker.lstrip("/") + normalized.split(marker, 1)[1]

    for root_file in _ROOT_FILES:
        if normalized.endswith("/" + root_file):
            return root_file
    return None


def _extract_file_references(payload: Any, *, field_name: str | None = None) -> list[str]:
    matches: list[str] = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            key_name = str(key)
            if key_name.lower() in _RELATIVE_PATH_FIELD_NAMES:
                matches.extend(_extract_file_references(value, field_name=key_name.lower()))
            elif isinstance(value, dict):
                matches.extend(_extract_file_references(value))
            elif isinstance(value, list):
                nested_field = (
                    key_name.lower() if key_name.lower() in _RELATIVE_PATH_FIELD_NAMES else None
                )
                matches.extend(_extract_file_references(value, field_name=nested_field))
        return matches

    if isinstance(payload, list):
        nested_field = "path" if field_name in {"paths", "targets", "files"} else field_name
        for item in payload:
            matches.extend(_extract_file_references(item, field_name=nested_field))
        return matches

    if isinstance(payload, str) and field_name in _RELATIVE_PATH_FIELD_NAMES:
        normalized = _normalize_file_reference(payload)
        return [normalized] if normalized else []
    return []


class ClaudeCodeTranscriptParser:
    """Parser for Claude Code JSONL transcripts stored under `.claude/projects/`."""

    def __init__(self, projects_root: Path | None = None) -> None:
        env_root = os.environ.get("CLAUDE_CODE_PROJECTS_DIR", "").strip()
        self._projects_root = (
            Path(env_root).expanduser()
            if env_root
            else (projects_root or Path.home() / ".claude" / "projects")
        )

    def platform_name(self) -> str:
        return "claude-code"

    def detect_platform(self, transcript: TranscriptFile) -> bool:
        normalized_parts = {part.lower() for part in transcript.path.parts}
        return (
            transcript.path.suffix == ".jsonl"
            and ".claude" in normalized_parts
            and "projects" in normalized_parts
        )

    def find_transcripts(self, since: datetime) -> list[TranscriptFile]:
        if not self._projects_root.exists():
            return []

        results: list[TranscriptFile] = []
        for path in self._projects_root.rglob("*.jsonl"):
            modified_time = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified_time < since.astimezone(timezone.utc):
                continue
            transcript = TranscriptFile(
                path=path,
                platform=self.platform_name(),
                modified_time=modified_time,
            )
            if self.detect_platform(transcript):
                results.append(transcript)

        results.sort(key=lambda item: (item.modified_time, item.path.as_posix()))
        return results

    def extract_tool_calls(self, raw_session: Any) -> list[ToolCall]:
        if not isinstance(raw_session, dict):
            return []
        if raw_session.get("type") != "assistant":
            return []

        ts = _parse_timestamp(raw_session.get("timestamp"))
        message = raw_session.get("message")
        if not isinstance(message, dict):
            return []
        content = message.get("content")
        if not isinstance(content, list):
            return []

        tool_calls: list[ToolCall] = []
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            use_id = str(block.get("id", "")).strip()
            tool_calls.append(
                ToolCall(
                    name=str(block.get("name", "")),
                    args=block.get("input"),
                    result=None,
                    timestamp=ts,
                    tool_use_id=use_id or None,
                )
            )
        return tool_calls

    def parse_session(self, transcript: TranscriptFile) -> ParsedSession:
        raw_lines = transcript.path.read_text(encoding="utf-8").splitlines()
        records: list[dict[str, Any]] = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if isinstance(payload, dict):
                records.append(payload)

        session_id = self._resolve_session_id(records, transcript)
        timestamps = [
            timestamp
            for timestamp in (_parse_timestamp(record.get("timestamp")) for record in records)
            if timestamp
        ]
        start_time = min(timestamps) if timestamps else transcript.modified_time
        end_time = max(timestamps) if timestamps else transcript.modified_time

        platform_metadata: dict[str, Any] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            for key in ("cwd", "gitBranch", "agentId", "entrypoint"):
                if key in platform_metadata:
                    continue
                val = record.get(key)
                if val is not None and str(val).strip():
                    platform_metadata[key] = val
            if len(platform_metadata) >= 4:
                break

        user_messages: list[str] = []
        assistant_messages: list[str] = []
        user_timestamps: list[datetime | None] = []
        assistant_timestamps: list[datetime | None] = []
        dialogue_turns: list[DialogueTurn] = []
        pending_tool_calls: dict[str, dict[str, Any]] = {}
        files_referenced: list[str] = []

        for record in records:
            record_type = str(record.get("type", ""))
            message = record.get("message")
            ts = _parse_timestamp(record.get("timestamp"))

            if record_type == "user" and isinstance(message, dict):
                text_blocks = _coerce_text_blocks(message.get("content"))
                if text_blocks:
                    user_messages.extend(text_blocks)
                    user_timestamps.extend([ts] * len(text_blocks))
                    for tb in text_blocks:
                        dialogue_turns.append(DialogueTurn("user", tb, ts, ()))

                content_blocks = message.get("content")
                if isinstance(content_blocks, list):
                    for block in content_blocks:
                        if not isinstance(block, dict) or block.get("type") != "tool_result":
                            continue
                        tool_use_id = str(block.get("tool_use_id", ""))
                        result_payload = record.get("toolUseResult", block.get("content"))
                        if tool_use_id and tool_use_id in pending_tool_calls:
                            pending_tool_calls[tool_use_id]["result"] = result_payload
                            duration_ms = _parse_duration_ms(result_payload)
                            if duration_ms is not None:
                                pending_tool_calls[tool_use_id]["duration_ms"] = duration_ms
                        files_referenced.extend(_extract_file_references(result_payload))
                continue

            if record_type != "assistant" or not isinstance(message, dict):
                continue

            content_blocks = message.get("content")
            tool_names_list: list[str] = []
            if isinstance(content_blocks, list):
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_names_list.append(str(block.get("name", "")))

            text_blocks = _coerce_text_blocks(message.get("content"))
            if text_blocks:
                assistant_messages.extend(text_blocks)
                assistant_timestamps.extend([ts] * len(text_blocks))
            merged_assistant = "\n".join(text_blocks)
            dialogue_turns.append(
                DialogueTurn("assistant", merged_assistant, ts, tuple(tool_names_list))
            )

            if not isinstance(content_blocks, list):
                continue
            for block in content_blocks:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                tool_use_id = str(block.get("id", ""))
                input_payload = block.get("input")
                if tool_use_id:
                    pending_tool_calls[tool_use_id] = {
                        "name": str(block.get("name", "")),
                        "args": input_payload,
                        "result": None,
                        "timestamp": ts,
                        "tool_use_id": tool_use_id or None,
                        "duration_ms": None,
                    }
                files_referenced.extend(_extract_file_references(input_payload))

        tool_calls = [
            ToolCall(
                name=str(payload["name"]),
                args=payload.get("args"),
                result=payload.get("result"),
                timestamp=payload.get("timestamp"),
                duration_ms=payload.get("duration_ms"),
                tool_use_id=payload.get("tool_use_id"),
            )
            for payload in pending_tool_calls.values()
        ]

        return ParsedSession(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            user_messages=user_messages,
            assistant_messages=assistant_messages,
            tool_calls=tool_calls,
            files_referenced=_dedupe_preserving_order(files_referenced),
            platform_metadata=platform_metadata,
            user_timestamps=user_timestamps,
            assistant_timestamps=assistant_timestamps,
            dialogue_turns=dialogue_turns,
        )

    def _resolve_session_id(
        self, records: Iterable[dict[str, Any]], transcript: TranscriptFile
    ) -> str:
        for record in records:
            session_id = record.get("sessionId")
            if isinstance(session_id, str) and session_id.strip():
                return session_id.strip()
        return transcript.path.stem


def _dedupe_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
