"""Token-aware compaction flush helpers for the optional Engram proxy."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Protocol

from .formats import APIFormat, RequestInspection, detect_api_format, inspect_request_body

_MODEL_CONTEXT_WINDOW_HEADER = "x-engram-model-context-window"
_PROJECT_HEADER = "x-engram-project"
_SESSION_ID_HEADER = "x-engram-session-id"


class CompactionToolCaller(Protocol):
    """Abstraction for calling the compaction flush write tool."""

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        """Execute the requested tool and return its payload."""


class TokenCounter(Protocol):
    """Count request tokens from normalized inspection data."""

    def count_tokens(self, inspection: RequestInspection) -> int:
        """Return the estimated input-token count for one request."""


@dataclass(slots=True)
class CompactionConfig:
    """Configuration for proxy-side compaction detection and flushing."""

    default_model_context_window: int | None = None
    flush_threshold: float = 0.85
    reset_threshold: float = 0.6
    flush_tool_name: str = "memory_session_flush"

    def __post_init__(self) -> None:
        if self.default_model_context_window is not None and self.default_model_context_window <= 0:
            raise ValueError("default_model_context_window must be > 0 when provided")
        if not (0.0 < self.flush_threshold <= 1.0):
            raise ValueError("flush_threshold must be between 0.0 and 1.0")
        if not (0.0 <= self.reset_threshold < self.flush_threshold):
            raise ValueError("reset_threshold must be >= 0.0 and less than flush_threshold")


@dataclass(slots=True)
class CompactionResult:
    """Structured outcome for one compaction-monitor request pass."""

    api_format: APIFormat | None
    token_count: int | None = None
    context_window_tokens: int | None = None
    flush_threshold_tokens: int | None = None
    flush_triggered: bool = False
    flush_tool_name: str | None = None
    session_id: str | None = None
    project_hint: str | None = None
    flush_payload: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None


@dataclass(slots=True)
class _ConversationState:
    flush_suppressed: bool = False
    last_token_count: int | None = None


class TiktokenTokenCounter:
    """Count tokens with tiktoken when the package is installed."""

    def __init__(self) -> None:
        import tiktoken  # type: ignore[import-not-found]

        self._tiktoken = tiktoken

    def count_tokens(self, inspection: RequestInspection) -> int:
        encoding = self._encoding_for_model(inspection.model_name)
        texts = [
            *inspection.system_messages,
            *inspection.user_messages,
            *inspection.assistant_messages,
            *inspection.tool_calls,
        ]
        if not texts:
            return 0
        total = 0
        for text in texts:
            stripped = text.strip()
            if not stripped:
                continue
            total += len(encoding.encode(stripped))
        message_count = (
            len(inspection.system_messages)
            + len(inspection.user_messages)
            + len(inspection.assistant_messages)
        )
        total += message_count * 4
        total += len(inspection.tool_calls) * 2
        return total

    def _encoding_for_model(self, model_name: str | None):
        if model_name:
            try:
                return self._tiktoken.encoding_for_model(model_name)
            except KeyError:
                pass
        return self._tiktoken.get_encoding("cl100k_base")


class ApproximateTokenCounter:
    """Fallback counter when tiktoken is unavailable."""

    def count_tokens(self, inspection: RequestInspection) -> int:
        joined = "\n\n".join(
            text.strip()
            for text in (
                *inspection.system_messages,
                *inspection.user_messages,
                *inspection.assistant_messages,
                *inspection.tool_calls,
            )
            if text.strip()
        )
        if not joined:
            return 0
        char_estimate = math.ceil(len(joined) / 4)
        return max(char_estimate, inspection.approximate_input_tokens)


def build_default_token_counter() -> TokenCounter:
    """Return the best available token counter for the current environment."""

    try:
        return TiktokenTokenCounter()
    except ModuleNotFoundError:
        return ApproximateTokenCounter()


class CompactionMonitor:
    """Trigger one mid-session flush per compaction cycle near the context limit."""

    def __init__(
        self,
        tool_caller: CompactionToolCaller,
        config: CompactionConfig | None = None,
        *,
        token_counter: TokenCounter | None = None,
    ) -> None:
        self._tool_caller = tool_caller
        self._config = config or CompactionConfig()
        self._token_counter = token_counter or build_default_token_counter()
        self._conversation_states: dict[str, _ConversationState] = {}

    def inspect_request(
        self,
        *,
        path: str,
        headers: dict[str, str],
        body: bytes,
        inspection: RequestInspection | None = None,
    ) -> CompactionResult:
        api_format = detect_api_format(path, headers)
        result = CompactionResult(
            api_format=api_format,
            session_id=_lookup_header(headers, _SESSION_ID_HEADER),
            project_hint=_lookup_header(headers, _PROJECT_HEADER),
        )
        if api_format is None or not body:
            result.reason = "unsupported_format"
            return result

        inspection = inspection or inspect_request_body(api_format, body)
        if inspection is None:
            result.reason = "uninspectable_request"
            return result

        token_count = self._token_counter.count_tokens(inspection)
        result.token_count = token_count

        context_window = _lookup_int_header(headers, _MODEL_CONTEXT_WINDOW_HEADER)
        if context_window is None:
            context_window = self._config.default_model_context_window
        result.context_window_tokens = context_window
        if context_window is None or context_window <= 0:
            result.reason = "no_context_window"
            return result

        threshold_tokens = max(int(context_window * self._config.flush_threshold), 1)
        reset_tokens = max(int(threshold_tokens * self._config.reset_threshold), 0)
        result.flush_threshold_tokens = threshold_tokens

        conversation_key = _conversation_key(result.session_id, result.project_hint)
        state = self._conversation_states.setdefault(conversation_key, _ConversationState())
        if state.flush_suppressed and token_count <= reset_tokens:
            state.flush_suppressed = False

        if token_count < threshold_tokens:
            state.last_token_count = token_count
            result.reason = "under_threshold"
            return result

        if state.flush_suppressed:
            state.last_token_count = token_count
            result.reason = "already_flushed"
            return result

        tool_arguments: dict[str, object] = {
            "summary": build_flush_summary(
                inspection,
                path=path,
                token_count=token_count,
                context_window=context_window,
                threshold_tokens=threshold_tokens,
                flush_threshold=self._config.flush_threshold,
                project_hint=result.project_hint,
                session_id=result.session_id,
            ),
            "label": "Context-pressure flush",
            "trigger": "context_pressure",
        }
        if result.session_id:
            tool_arguments["session_id"] = result.session_id

        raw_payload = self._tool_caller.call_tool(self._config.flush_tool_name, tool_arguments)
        result.flush_payload = _coerce_jsonish_payload(raw_payload)
        result.flush_triggered = True
        result.flush_tool_name = self._config.flush_tool_name
        result.reason = "flushed"

        state.flush_suppressed = True
        state.last_token_count = token_count
        return result


def build_flush_summary(
    inspection: RequestInspection,
    *,
    path: str,
    token_count: int,
    context_window: int,
    threshold_tokens: int,
    flush_threshold: float,
    project_hint: str | None,
    session_id: str | None,
) -> str:
    """Build a compact recovery-oriented checkpoint summary for an automatic flush."""

    usage_pct = int(round((token_count / context_window) * 100)) if context_window else 0
    threshold_pct = int(round(flush_threshold * 100))
    lines = [
        "Automatic context-pressure flush triggered by the optional proxy.",
        "",
        f"Context usage: {token_count} / {context_window} tokens ({usage_pct}%).",
        f"Flush threshold: {threshold_tokens} tokens ({threshold_pct}%).",
        f"Request path: {path}",
    ]
    if inspection.model_name:
        lines.append(f"Model: {inspection.model_name}")
    if project_hint:
        lines.append(f"Project hint: {project_hint}")
    if session_id:
        lines.append(f"Session: {session_id}")

    latest_user = _last_non_empty(inspection.user_messages)
    latest_assistant = _last_non_empty(inspection.assistant_messages)
    if latest_user:
        lines.extend(["", "Latest user request:", latest_user])
    if latest_assistant:
        lines.extend(["", "Recent assistant context:", latest_assistant])
    if inspection.tool_calls:
        lines.extend(["", "Recent tool calls:", ", ".join(inspection.tool_calls[:8])])
    return "\n".join(lines).strip()


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


def _lookup_int_header(headers: dict[str, str], key: str) -> int | None:
    raw_value = _lookup_header(headers, key)
    if raw_value is None:
        return None
    return int(raw_value)


__all__ = [
    "ApproximateTokenCounter",
    "CompactionConfig",
    "CompactionMonitor",
    "CompactionResult",
    "CompactionToolCaller",
    "TokenCounter",
    "TiktokenTokenCounter",
    "build_default_token_counter",
    "build_flush_summary",
]
