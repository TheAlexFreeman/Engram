"""Automatic checkpoint extraction from model responses for the optional proxy."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from .formats import APIFormat, RequestInspection, detect_api_format

_PROJECT_HEADER = "x-engram-project"
_SESSION_ID_HEADER = "x-engram-session-id"
_DECISION_PHRASES = (
    "i'll ",
    "i will ",
    "let's ",
    "the approach is",
    "the plan is",
    "we should",
    "i'm going to",
)
_TASK_COMPLETION_PHRASES = (
    "i implemented",
    "i fixed",
    "i resolved",
    "i updated",
    "i added",
    "i created",
    "i changed",
    "i completed",
)
_PREFERENCE_PHRASES = (
    "you prefer",
    "you'd rather",
    "i'll remember",
    "noted",
)
_CORRECTION_PHRASES = (
    "actually",
    "no, i meant",
    "rather than",
    "instead of",
)


class AutoCheckpointToolCaller(Protocol):
    """Abstraction for calling the checkpoint tool via MCP or a test double."""

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        """Execute one checkpointing tool call and return its payload."""


@dataclass(slots=True)
class AutoCheckpointConfig:
    """Configuration for proxy-side automatic checkpoint extraction."""

    min_response_tokens: int = 24
    min_tool_calls_between_checkpoints: int = 5
    checkpoint_tool_name: str = "memory_checkpoint"
    max_content_chars: int = 1600

    def __post_init__(self) -> None:
        if self.min_response_tokens < 1:
            raise ValueError("min_response_tokens must be >= 1")
        if self.min_tool_calls_between_checkpoints < 0:
            raise ValueError("min_tool_calls_between_checkpoints must be >= 0")
        if self.max_content_chars < 80:
            raise ValueError("max_content_chars must be >= 80")


@dataclass(slots=True)
class ResponseInspection:
    """Normalized summary extracted from one non-streaming model response."""

    api_format: APIFormat
    assistant_texts: list[str] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    approximate_output_tokens: int = 0


@dataclass(slots=True)
class AutoCheckpointResult:
    """Structured outcome for one response-side checkpoint analysis."""

    api_format: APIFormat | None
    checkpoint_triggered: bool = False
    checkpoint_tool_name: str | None = None
    checkpoint_label: str | None = None
    checkpoint_session_id: str | None = None
    extracted_content_chars: int = 0
    response_tokens: int | None = None
    conversation_tool_calls: int = 0
    tool_calls_since_last_checkpoint: int | None = None
    checkpoint_payload: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None


@dataclass(slots=True)
class _CheckpointState:
    last_checkpoint_tool_calls: int | None = None


class AutoCheckpointMonitor:
    """Detect checkpoint-worthy responses and persist them conservatively."""

    def __init__(
        self,
        tool_caller: AutoCheckpointToolCaller,
        config: AutoCheckpointConfig | None = None,
    ) -> None:
        self._tool_caller = tool_caller
        self._config = config or AutoCheckpointConfig()
        self._conversation_states: dict[str, _CheckpointState] = {}

    def inspect_response(
        self,
        *,
        path: str,
        request_headers: dict[str, str],
        request_inspection: RequestInspection | None,
        response_headers: dict[str, str],
        response_body: bytes,
        status_code: int,
        streaming_response: bool,
    ) -> AutoCheckpointResult:
        api_format = detect_api_format(path, request_headers)
        session_id = _lookup_header(request_headers, _SESSION_ID_HEADER)
        result = AutoCheckpointResult(
            api_format=api_format,
            checkpoint_session_id=session_id,
        )
        if api_format is None:
            result.reason = "unsupported_format"
            return result
        if streaming_response:
            result.reason = "streaming_response"
            return result
        if status_code < 200 or status_code >= 300:
            result.reason = "non_success_status"
            return result
        if not _is_json_response(response_headers):
            result.reason = "non_json_response"
            return result
        if not response_body:
            result.reason = "empty_response"
            return result

        response_inspection = inspect_response_body(api_format, response_body)
        if response_inspection is None:
            result.reason = "uninspectable_response"
            return result

        assistant_text = _last_non_empty(response_inspection.assistant_texts)
        if not assistant_text:
            result.reason = "empty_text"
            return result

        result.response_tokens = response_inspection.approximate_output_tokens
        if response_inspection.approximate_output_tokens < self._config.min_response_tokens:
            result.reason = "short_response"
            return result

        latest_user = (
            _last_non_empty(request_inspection.user_messages) if request_inspection else ""
        )
        label = _classify_checkpoint_label(assistant_text, latest_user)
        if label is None:
            result.reason = "not_checkpoint_worthy"
            return result

        conversation_tool_calls = len(request_inspection.tool_calls) if request_inspection else 0
        conversation_tool_calls += len(response_inspection.tool_calls)
        result.conversation_tool_calls = conversation_tool_calls

        project_hint = _lookup_header(request_headers, _PROJECT_HEADER)
        state = self._conversation_states.setdefault(
            _conversation_key(session_id, project_hint),
            _CheckpointState(),
        )
        if state.last_checkpoint_tool_calls is None:
            tool_call_delta = conversation_tool_calls
        else:
            tool_call_delta = max(conversation_tool_calls - state.last_checkpoint_tool_calls, 0)
            if tool_call_delta < self._config.min_tool_calls_between_checkpoints:
                result.tool_calls_since_last_checkpoint = tool_call_delta
                result.reason = "rate_limited"
                return result
        result.tool_calls_since_last_checkpoint = tool_call_delta

        checkpoint_content = build_checkpoint_content(
            latest_user=latest_user,
            assistant_text=assistant_text,
            tool_calls=response_inspection.tool_calls,
            max_content_chars=self._config.max_content_chars,
        )
        tool_arguments: dict[str, object] = {
            "content": checkpoint_content,
            "label": label,
        }
        if session_id:
            tool_arguments["session_id"] = session_id

        raw_payload = self._tool_caller.call_tool(self._config.checkpoint_tool_name, tool_arguments)
        result.checkpoint_payload = _coerce_jsonish_payload(raw_payload)
        result.checkpoint_triggered = True
        result.checkpoint_tool_name = self._config.checkpoint_tool_name
        result.checkpoint_label = label
        result.extracted_content_chars = len(checkpoint_content)
        result.reason = "checkpointed"
        state.last_checkpoint_tool_calls = conversation_tool_calls
        return result


def inspect_response_body(
    api_format: APIFormat | None, raw_body: bytes
) -> ResponseInspection | None:
    """Parse and inspect a non-streaming JSON response body when the format is known."""

    if api_format is None or not raw_body:
        return None
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if api_format == "openai":
        return _inspect_openai_response(payload)
    if api_format == "anthropic":
        return _inspect_anthropic_response(payload)
    return None


def build_checkpoint_content(
    *,
    latest_user: str,
    assistant_text: str,
    tool_calls: list[str],
    max_content_chars: int,
) -> str:
    """Build the memory_checkpoint content for one automatic capture."""

    lines: list[str] = []
    if latest_user:
        lines.extend(["User request:", latest_user.strip(), ""])
    lines.extend(
        [
            "Assistant response:",
            _truncate_text(assistant_text.strip(), max_content_chars=max_content_chars),
        ]
    )
    if tool_calls:
        lines.extend(["", "Tool calls:", ", ".join(tool_calls[:8])])
    return "\n".join(line for line in lines if line is not None).strip()


def _inspect_openai_response(payload: dict[str, Any]) -> ResponseInspection:
    assistant_texts: list[str] = []
    tool_calls: list[str] = []
    for choice in _dict_list(payload.get("choices")):
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        text = _normalize_openai_content(message.get("content"))
        if text:
            assistant_texts.append(text)
        for tool_call in _dict_list(message.get("tool_calls")):
            name = str(tool_call.get("function", {}).get("name", "")).strip()
            if name:
                tool_calls.append(name)
    return ResponseInspection(
        api_format="openai",
        assistant_texts=assistant_texts,
        tool_calls=tool_calls,
        approximate_output_tokens=_estimate_token_count([*assistant_texts, *tool_calls]),
    )


def _inspect_anthropic_response(payload: dict[str, Any]) -> ResponseInspection:
    assistant_texts: list[str] = []
    tool_calls: list[str] = []
    text = _normalize_anthropic_content(payload.get("content"))
    if text:
        assistant_texts.append(text)
    for block in _dict_list(payload.get("content")):
        if str(block.get("type", "")).strip().lower() != "tool_use":
            continue
        name = str(block.get("name", "")).strip()
        if name:
            tool_calls.append(name)
    return ResponseInspection(
        api_format="anthropic",
        assistant_texts=assistant_texts,
        tool_calls=tool_calls,
        approximate_output_tokens=_estimate_token_count([*assistant_texts, *tool_calls]),
    )


def _classify_checkpoint_label(assistant_text: str, latest_user: str) -> str | None:
    normalized_assistant = _normalize_phrase_text(assistant_text)
    normalized_user = _normalize_phrase_text(latest_user)

    if _contains_any(normalized_user, _CORRECTION_PHRASES):
        return "User correction"
    if _contains_any(normalized_assistant, _TASK_COMPLETION_PHRASES):
        return "Task completion"
    if _contains_any(normalized_assistant, _DECISION_PHRASES):
        return "Decision"
    if _contains_any(normalized_assistant, _PREFERENCE_PHRASES):
        return "Preference"
    return None


def _normalize_phrase_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _truncate_text(text: str, *, max_content_chars: int) -> str:
    if len(text) <= max_content_chars:
        return text
    return text[: max_content_chars - 16].rstrip() + " ...[truncated]"


def _coerce_jsonish_payload(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, dict):
        return raw_payload
    if isinstance(raw_payload, str):
        stripped = raw_payload.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return {"raw": raw_payload}
        return parsed if isinstance(parsed, dict) else {"raw": parsed}
    return {"raw": raw_payload}


def _conversation_key(session_id: str | None, project_hint: str | None) -> str:
    if session_id:
        return f"session:{session_id}"
    if project_hint:
        return f"project:{project_hint}"
    return "global"


def _estimate_token_count(values: list[str]) -> int:
    joined = " ".join(value for value in values if value).strip()
    if not joined:
        return 0
    return len(joined.split())


def _is_json_response(headers: dict[str, str]) -> bool:
    content_type = headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    return content_type == "application/json"


def _last_non_empty(values: list[str]) -> str:
    for value in reversed(values):
        stripped = value.strip()
        if stripped:
            return stripped
    return ""


def _lookup_header(headers: dict[str, str], key: str) -> str | None:
    for header_name, header_value in headers.items():
        if header_name.lower() == key:
            stripped = header_value.strip()
            return stripped or None
    return None


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _normalize_openai_content(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for block in value:
        if not isinstance(block, dict):
            continue
        if str(block.get("type", "")).strip().lower() != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def _normalize_anthropic_content(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    parts: list[str] = []
    for block in _dict_list(value):
        if str(block.get("type", "")).strip().lower() != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


__all__ = [
    "AutoCheckpointConfig",
    "AutoCheckpointMonitor",
    "AutoCheckpointResult",
    "AutoCheckpointToolCaller",
    "ResponseInspection",
    "build_checkpoint_content",
    "inspect_response_body",
]
