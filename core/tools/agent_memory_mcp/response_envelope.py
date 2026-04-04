"""Helpers for structured tool responses with session metadata."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .session_state import SessionState


def build_session_response_metadata(session_state: "SessionState | None") -> dict[str, Any]:
    """Return compact, stable session metadata for tool responses."""
    if session_state is None:
        return {
            "signals": [],
            "tool_calls_this_session": 0,
            "tool_calls_since_checkpoint": 0,
            "session_duration_minutes": 0,
            "unread_relevant_files": [],
        }

    advisory = session_state.get_advisory()
    signals: list[str] = []
    if advisory.flush_recommended:
        signals.append("flush_recommended")
    if advisory.checkpoint_stale:
        signals.append("checkpoint_stale")
    if advisory.unread_relevant_files:
        signals.append("unread_relevant_files")

    return {
        "signals": signals,
        "tool_calls_this_session": session_state.tool_calls,
        "tool_calls_since_checkpoint": advisory.tool_calls_since_checkpoint,
        "session_duration_minutes": advisory.session_duration_minutes,
        "unread_relevant_files": list(advisory.unread_relevant_files),
    }


def envelope_tool_result(result: Any, session_state: "SessionState | None") -> dict[str, Any]:
    """Wrap a structured tool result with compact session metadata."""
    return {
        "result": result,
        "_session": build_session_response_metadata(session_state),
    }


def dump_tool_result(
    result: Any,
    session_state: "SessionState | None",
    *,
    indent: int = 2,
    default: Any | None = None,
) -> str:
    """Serialize a structured tool result envelope to JSON."""
    json_kwargs: dict[str, Any] = {"indent": indent}
    if default is not None:
        json_kwargs["default"] = default
    return json.dumps(envelope_tool_result(result, session_state), **json_kwargs)


__all__ = [
    "build_session_response_metadata",
    "dump_tool_result",
    "envelope_tool_result",
]
