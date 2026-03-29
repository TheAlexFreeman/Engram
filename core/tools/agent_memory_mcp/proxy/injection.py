"""Context injection helpers for the optional Engram proxy."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from .formats import (
    APIFormat,
    RequestInspection,
    adapter_for_format,
    detect_api_format,
    inspect_request_body,
)

_PROJECT_HEADER = "x-engram-project"
_SESSION_ID_HEADER = "x-engram-session-id"
_MAX_CONTEXT_CHARS_HEADER = "x-engram-max-context-chars"
_MODEL_CONTEXT_WINDOW_HEADER = "x-engram-model-context-window"
_INCLUDE_PLAN_SOURCES_HEADER = "x-engram-include-plan-sources"
_INCLUDE_PROJECT_INDEX_HEADER = "x-engram-include-project-index"
_CONTROL_HEADERS = frozenset(
    {
        _PROJECT_HEADER,
        _SESSION_ID_HEADER,
        _MAX_CONTEXT_CHARS_HEADER,
        _MODEL_CONTEXT_WINDOW_HEADER,
        _INCLUDE_PLAN_SOURCES_HEADER,
        _INCLUDE_PROJECT_INDEX_HEADER,
    }
)
_JSON_HEADER_PREFIX = "```json\n"
_JSON_HEADER_DELIMITER = "\n```\n\n"


class ContextToolCaller(Protocol):
    """Abstraction for calling context injector tools via MCP or a test double."""

    def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        """Execute one context tool call and return its payload."""


@dataclass(slots=True)
class InjectionConfig:
    """Configuration for proxy-side context injection."""

    default_max_context_chars: int = 12000
    model_context_window: int | None = None
    reserve_tokens: int = 2000
    chars_per_token: int = 4
    include_project_index: bool = True
    include_plan_sources: bool = True


@dataclass(slots=True)
class _BudgetDecision:
    max_context_chars: int
    skip_injection: bool = False


@dataclass(slots=True)
class ContextInjectionResult:
    """Result of optional pre-query context injection for one request."""

    body: bytes
    headers: dict[str, str]
    api_format: APIFormat | None
    injected: bool = False
    context_tool_name: str | None = None
    project_hint: str | None = None
    context_budget_chars: int | None = None
    injected_context_chars: int = 0
    context_metadata: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None


class ContextInjector:
    """Call Engram context tools and prepend their Markdown to model requests."""

    def __init__(
        self, tool_caller: ContextToolCaller, config: InjectionConfig | None = None
    ) -> None:
        self._tool_caller = tool_caller
        self._config = config or InjectionConfig()

    def inject_request(
        self,
        *,
        path: str,
        headers: dict[str, str],
        body: bytes,
        inspection: RequestInspection | None = None,
    ) -> ContextInjectionResult:
        forwarded_headers = strip_injection_control_headers(headers)
        api_format = detect_api_format(path, headers)
        result = ContextInjectionResult(
            body=body,
            headers=forwarded_headers,
            api_format=api_format,
        )
        if api_format is None or not body:
            result.reason = "unsupported_format"
            return result

        payload = _decode_json_object(body)
        if payload is None:
            result.reason = "non_json_payload"
            return result

        inspection = inspection or inspect_request_body(api_format, body)
        budget = self._resolve_budget(headers, inspection)
        result.context_budget_chars = budget.max_context_chars
        if budget.skip_injection:
            result.reason = "budget_exhausted"
            return result

        project_hint = _lookup_header(headers, _PROJECT_HEADER)
        result.project_hint = project_hint
        tool_name, tool_arguments = self._context_tool_request(
            project_hint=project_hint,
            max_context_chars=budget.max_context_chars,
            headers=headers,
        )
        raw_payload = self._tool_caller.call_tool(tool_name, tool_arguments)
        tool_text = _coerce_tool_text(raw_payload)
        metadata, markdown_body = parse_context_tool_response(tool_text)
        injected_markdown = markdown_body.strip()
        result.context_metadata = metadata
        result.context_tool_name = tool_name
        if not injected_markdown:
            result.reason = "empty_context"
            return result

        injected_payload = adapter_for_format(api_format).inject_system_context(
            payload, injected_markdown
        )
        encoded_body = json.dumps(injected_payload).encode("utf-8")
        forwarded_headers["Content-Length"] = str(len(encoded_body))
        result.body = encoded_body
        result.headers = forwarded_headers
        result.injected = True
        result.injected_context_chars = len(injected_markdown)
        result.reason = "injected"
        return result

    def _context_tool_request(
        self,
        *,
        project_hint: str | None,
        max_context_chars: int,
        headers: dict[str, str],
    ) -> tuple[str, dict[str, object]]:
        if project_hint:
            include_plan_sources = _lookup_bool_header(
                headers,
                _INCLUDE_PLAN_SOURCES_HEADER,
                default=self._config.include_plan_sources,
            )
            return (
                "memory_context_project",
                {
                    "project": project_hint,
                    "max_context_chars": max_context_chars,
                    "include_plan_sources": include_plan_sources,
                },
            )

        include_project_index = _lookup_bool_header(
            headers,
            _INCLUDE_PROJECT_INDEX_HEADER,
            default=self._config.include_project_index,
        )
        return (
            "memory_context_home",
            {
                "max_context_chars": max_context_chars,
                "include_project_index": include_project_index,
            },
        )

    def _resolve_budget(
        self,
        headers: dict[str, str],
        inspection: RequestInspection | None,
    ) -> _BudgetDecision:
        explicit_budget = _lookup_int_header(headers, _MAX_CONTEXT_CHARS_HEADER)
        if explicit_budget is not None:
            if explicit_budget < 0:
                raise ValueError("x-engram-max-context-chars must be >= 0")
            return _BudgetDecision(max_context_chars=explicit_budget)

        model_context_window = _lookup_int_header(headers, _MODEL_CONTEXT_WINDOW_HEADER)
        if model_context_window is None:
            model_context_window = self._config.model_context_window
        if model_context_window is None:
            return _BudgetDecision(max_context_chars=self._config.default_max_context_chars)

        if model_context_window <= 0:
            return _BudgetDecision(max_context_chars=0, skip_injection=True)

        used_tokens = inspection.approximate_input_tokens if inspection is not None else 0
        available_tokens = max(model_context_window - used_tokens - self._config.reserve_tokens, 0)
        if available_tokens <= 0:
            return _BudgetDecision(max_context_chars=0, skip_injection=True)

        available_chars = available_tokens * self._config.chars_per_token
        if self._config.default_max_context_chars == 0:
            return _BudgetDecision(max_context_chars=available_chars)
        return _BudgetDecision(
            max_context_chars=min(self._config.default_max_context_chars, available_chars)
        )


def parse_context_tool_response(payload: str) -> tuple[dict[str, Any], str]:
    """Split context-tool markdown into metadata header and body."""

    if not payload.startswith(_JSON_HEADER_PREFIX):
        return {}, payload
    try:
        metadata_text, body = payload[len(_JSON_HEADER_PREFIX) :].split(_JSON_HEADER_DELIMITER, 1)
        metadata = json.loads(metadata_text)
    except (ValueError, json.JSONDecodeError):
        return {}, payload
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata, body


def strip_injection_control_headers(headers: dict[str, str]) -> dict[str, str]:
    """Remove proxy-only control headers before forwarding to the upstream API."""

    return {key: value for key, value in headers.items() if key.lower() not in _CONTROL_HEADERS}


def _coerce_tool_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("content", "text"):
            if isinstance(value.get(key), str):
                return value[key]
            if isinstance(value.get(key), list):
                pieces: list[str] = []
                for item in value[key]:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text")
                    if isinstance(text, str):
                        pieces.append(text)
                if pieces:
                    return "\n".join(pieces)
    if isinstance(value, list):
        block_texts: list[str] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                block_texts.append(text)
        if block_texts:
            return "\n".join(block_texts)
    raise TypeError("Context tool caller must return text or text-like content blocks")


def _decode_json_object(body: bytes) -> dict[str, Any] | None:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


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


def _lookup_bool_header(headers: dict[str, str], key: str, *, default: bool) -> bool:
    raw_value = _lookup_header(headers, key)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} must be a boolean value")


__all__ = [
    "ContextInjectionResult",
    "ContextInjector",
    "ContextToolCaller",
    "InjectionConfig",
    "parse_context_tool_response",
    "strip_injection_control_headers",
]
