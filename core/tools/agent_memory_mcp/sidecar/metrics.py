"""Aggregate sidecar session metrics from traces and dialogue entries."""

from __future__ import annotations

from collections import Counter
from datetime import timezone
from typing import Any

from .parser import ParsedSession


def _normalize_tool_name(name: str) -> str:
    return name.rsplit("__", 1)[-1]


def compute_session_metrics(
    trace_spans: list[dict[str, Any]],
    dialogue: list[dict[str, Any]],
    session: ParsedSession,
) -> dict[str, Any]:
    tool_counter: Counter[str] = Counter()
    error_count = 0
    total_duration_ms = 0

    for span in trace_spans:
        if span.get("span_type") != "tool_call":
            continue
        tool_counter[_normalize_tool_name(str(span.get("name") or ""))] += 1
        if span.get("status") == "error":
            error_count += 1
        try:
            total_duration_ms += int(span.get("duration_ms") or 0)
        except (TypeError, ValueError):
            pass

    if not tool_counter and session.tool_calls:
        for call in session.tool_calls:
            tool_counter[_normalize_tool_name(call.name)] += 1

    user_turns = sum(1 for row in dialogue if row.get("role") == "user")
    assistant_turns = sum(1 for row in dialogue if row.get("role") == "assistant")
    if not dialogue:
        user_turns = len(session.user_messages)
        assistant_turns = len(session.assistant_messages)

    estimated_total_tokens = sum(int(row.get("token_estimate") or 0) for row in dialogue)

    start = session.start_time
    end = session.end_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    session_duration_ms = int((end - start).total_seconds() * 1000)

    total_tool_calls = int(sum(tool_counter.values())) if tool_counter else len(session.tool_calls)
    unique_tools_used = (
        len(tool_counter) if tool_counter else len({c.name for c in session.tool_calls})
    )

    ratio = (
        total_tool_calls / max(1, user_turns + assistant_turns)
        if (user_turns + assistant_turns)
        else 0.0
    )
    if total_tool_calls >= 15 or ratio >= 2.5:
        session_characterization = "heavy tool use session"
    elif total_tool_calls <= 2 and (user_turns + assistant_turns) >= 4:
        session_characterization = "conversational session"
    elif tool_counter.get("memory_checkpoint", 0) + tool_counter.get("memory_record_trace", 0) >= 3:
        session_characterization = "plan execution session"
    else:
        session_characterization = "mixed activity session"

    return {
        "total_tool_calls": total_tool_calls,
        "unique_tools_used": unique_tools_used,
        "tool_call_breakdown": dict(sorted(tool_counter.items(), key=lambda kv: (-kv[1], kv[0]))),
        "user_turn_count": user_turns,
        "assistant_turn_count": assistant_turns,
        "estimated_total_tokens": estimated_total_tokens,
        "session_duration_ms": session_duration_ms,
        "error_count": error_count,
        "session_characterization": session_characterization,
    }
