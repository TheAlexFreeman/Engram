"""API format detection and lightweight request adapters for the optional proxy."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

APIFormat = Literal["openai", "anthropic"]


@dataclass(slots=True)
class ObservedToolCall:
    """Normalized tool-call observation extracted from API traffic."""

    name: str
    tool_call_id: str | None = None
    args: Any = None
    result: Any = None


@dataclass(slots=True)
class RequestInspection:
    """Normalized request summary extracted from an API payload."""

    api_format: APIFormat
    model_name: str | None = None
    system_messages: list[str] = field(default_factory=list)
    user_messages: list[str] = field(default_factory=list)
    assistant_messages: list[str] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    observed_tool_calls: list[ObservedToolCall] = field(default_factory=list)
    approximate_input_tokens: int = 0


class RequestAdapter(Protocol):
    """Protocol shared by OpenAI and Anthropic request adapters."""

    api_format: APIFormat

    def inspect_payload(self, payload: dict[str, Any]) -> RequestInspection:
        """Return normalized request metadata for the parsed JSON payload."""

    def inject_system_context(self, payload: dict[str, Any], context: str) -> dict[str, Any]:
        """Return a copy of the payload with additional system context injected."""


def detect_api_format(path: str, headers: dict[str, str] | None = None) -> APIFormat | None:
    """Detect the upstream API format from the request path and headers."""

    normalized_path = urlsplit(path).path.rstrip("/")
    header_lookup = {key.lower(): value for key, value in (headers or {}).items()}

    if normalized_path.endswith("/chat/completions"):
        return "openai"
    if normalized_path.endswith("/messages") or "anthropic-version" in header_lookup:
        return "anthropic"
    return None


def adapter_for_format(api_format: APIFormat) -> RequestAdapter:
    """Return the request adapter for a supported API format."""

    if api_format == "openai":
        return OpenAIChatAdapter()
    if api_format == "anthropic":
        return AnthropicMessagesAdapter()
    raise ValueError(f"Unsupported API format: {api_format}")


class OpenAIChatAdapter:
    """Adapter for OpenAI-style chat completions payloads."""

    api_format: APIFormat = "openai"

    def inspect_payload(self, payload: dict[str, Any]) -> RequestInspection:
        system_messages: list[str] = []
        user_messages: list[str] = []
        assistant_messages: list[str] = []
        tool_calls: list[str] = []
        observed_tool_calls: list[ObservedToolCall] = []
        pending_tool_calls: dict[str, ObservedToolCall] = {}

        for message in _message_list(payload.get("messages")):
            role = str(message.get("role", "")).strip().lower()
            content_text = _normalize_openai_content(message.get("content"))
            if role == "system" and content_text:
                system_messages.append(content_text)
            elif role == "user" and content_text:
                user_messages.append(content_text)
            elif role == "assistant":
                if content_text:
                    assistant_messages.append(content_text)
                for tool_call in _dict_list(message.get("tool_calls")):
                    name = str(tool_call.get("function", {}).get("name", "")).strip()
                    if name:
                        tool_calls.append(name)
                        observed = ObservedToolCall(
                            name=name,
                            tool_call_id=_normalize_optional_string(tool_call.get("id")),
                            args=_coerce_jsonish_value(
                                tool_call.get("function", {}).get("arguments")
                            ),
                        )
                        observed_tool_calls.append(observed)
                        if observed.tool_call_id:
                            pending_tool_calls[observed.tool_call_id] = observed
            elif role == "tool":
                tool_call_id = _normalize_optional_string(message.get("tool_call_id"))
                matched_observed = pending_tool_calls.get(tool_call_id) if tool_call_id else None
                if matched_observed is not None:
                    matched_observed.result = _coerce_tool_result_content(message.get("content"))
                    continue

                fallback_name = _normalize_optional_string(message.get("name"))
                if fallback_name:
                    observed_tool_calls.append(
                        ObservedToolCall(
                            name=fallback_name,
                            tool_call_id=tool_call_id,
                            result=_coerce_tool_result_content(message.get("content")),
                        )
                    )

        approximate_input_tokens = _estimate_token_count(
            [*system_messages, *user_messages, *assistant_messages]
        )
        return RequestInspection(
            api_format=self.api_format,
            model_name=_model_name(payload),
            system_messages=system_messages,
            user_messages=user_messages,
            assistant_messages=assistant_messages,
            tool_calls=tool_calls,
            observed_tool_calls=observed_tool_calls,
            approximate_input_tokens=approximate_input_tokens,
        )

    def inject_system_context(self, payload: dict[str, Any], context: str) -> dict[str, Any]:
        cloned = copy.deepcopy(payload)
        messages = _message_list(cloned.get("messages"))
        injected_message = {"role": "system", "content": context}
        if messages and str(messages[0].get("role", "")).strip().lower() == "system":
            existing = _normalize_openai_content(messages[0].get("content"))
            messages[0]["content"] = _merge_context(existing, context)
        else:
            messages.insert(0, injected_message)
        cloned["messages"] = messages
        return cloned


class AnthropicMessagesAdapter:
    """Adapter for Anthropic-style messages payloads."""

    api_format: APIFormat = "anthropic"

    def inspect_payload(self, payload: dict[str, Any]) -> RequestInspection:
        system_messages = _normalize_anthropic_system(payload.get("system"))
        user_messages: list[str] = []
        assistant_messages: list[str] = []
        tool_calls: list[str] = []
        observed_tool_calls: list[ObservedToolCall] = []
        pending_tool_calls: dict[str, ObservedToolCall] = {}

        for message in _message_list(payload.get("messages")):
            role = str(message.get("role", "")).strip().lower()
            content_text = _normalize_anthropic_content(message.get("content"))
            if role == "user" and content_text:
                user_messages.append(content_text)
            if role == "user":
                for block in _dict_list(message.get("content")):
                    if str(block.get("type", "")).strip().lower() != "tool_result":
                        continue
                    tool_call_id = _normalize_optional_string(block.get("tool_use_id"))
                    matched_observed = (
                        pending_tool_calls.get(tool_call_id) if tool_call_id else None
                    )
                    if matched_observed is None:
                        continue
                    matched_observed.result = _coerce_tool_result_content(block.get("content"))
            elif role == "assistant":
                if content_text:
                    assistant_messages.append(content_text)
                for block in _dict_list(message.get("content")):
                    if str(block.get("type", "")).strip().lower() != "tool_use":
                        continue
                    name = str(block.get("name", "")).strip()
                    if name:
                        tool_calls.append(name)
                        observed = ObservedToolCall(
                            name=name,
                            tool_call_id=_normalize_optional_string(block.get("id")),
                            args=block.get("input"),
                        )
                        observed_tool_calls.append(observed)
                        if observed.tool_call_id:
                            pending_tool_calls[observed.tool_call_id] = observed

        approximate_input_tokens = _estimate_token_count(
            [*system_messages, *user_messages, *assistant_messages]
        )
        return RequestInspection(
            api_format=self.api_format,
            model_name=_model_name(payload),
            system_messages=system_messages,
            user_messages=user_messages,
            assistant_messages=assistant_messages,
            tool_calls=tool_calls,
            observed_tool_calls=observed_tool_calls,
            approximate_input_tokens=approximate_input_tokens,
        )

    def inject_system_context(self, payload: dict[str, Any], context: str) -> dict[str, Any]:
        cloned = copy.deepcopy(payload)
        system_messages = _normalize_anthropic_system(cloned.get("system"))
        merged_text = _merge_context("\n\n".join(system_messages), context)
        cloned["system"] = merged_text
        return cloned


def inspect_request_body(
    api_format: APIFormat | None,
    raw_body: bytes,
) -> RequestInspection | None:
    """Parse and inspect a JSON request body when the format is known."""

    if api_format is None or not raw_body:
        return None
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return adapter_for_format(api_format).inspect_payload(payload)


def _estimate_token_count(values: list[str]) -> int:
    joined = " ".join(value for value in values if value).strip()
    if not joined:
        return 0
    return len(joined.split())


def _model_name(payload: dict[str, Any]) -> str | None:
    value = payload.get("model")
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _merge_context(existing: str, context: str) -> str:
    existing = existing.strip()
    context = context.strip()
    if not existing:
        return context
    if not context:
        return existing
    return context + "\n\n" + existing


def _message_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _normalize_optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _coerce_jsonish_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return stripped
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return stripped


def _coerce_tool_result_content(value: Any) -> Any:
    if isinstance(value, str):
        return _coerce_jsonish_value(value)
    if not isinstance(value, list):
        return value

    text_parts: list[str] = []
    for block in value:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type", "")).strip().lower()
        if block_type == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())
        elif block_type == "tool_result":
            return _coerce_tool_result_content(block.get("content"))

    if not text_parts:
        return value
    return _coerce_jsonish_value("\n\n".join(text_parts))


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


def _normalize_anthropic_system(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    parts: list[str] = []
    for block in _dict_list(value):
        if str(block.get("type", "")).strip().lower() != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return parts


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
    "APIFormat",
    "AnthropicMessagesAdapter",
    "ObservedToolCall",
    "OpenAIChatAdapter",
    "RequestInspection",
    "adapter_for_format",
    "detect_api_format",
    "inspect_request_body",
]
