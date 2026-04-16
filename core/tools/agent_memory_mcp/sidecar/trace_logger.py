"""Append tool_call trace spans from parsed transcripts (sidecar capture)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..plan_trace import _sanitize_metadata, load_session_trace_spans, record_trace
from .parser import ParsedSession, ToolCall


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


def _infer_tool_status(result: Any) -> str:
    if result is None:
        return "ok"
    data = _coerce_json_like(result)
    if isinstance(data, dict):
        if data.get("isError") is True or data.get("is_error") is True:
            return "error"
        err = data.get("error")
        if err not in (None, "", False, []):
            return "error"
        if str(data.get("type", "")).lower() in {"error", "execution_error"}:
            return "error"
    if isinstance(data, str) and data.strip().lower().startswith("error"):
        return "error"
    return "ok"


def _args_summary(args: Any) -> dict[str, Any] | None:
    if args is None:
        return None
    return _sanitize_metadata({"args": args})


def _anon_dedupe_key(call: ToolCall) -> str:
    payload = (
        f"{call.name}\0{call.timestamp and call.timestamp.isoformat()}\0{repr(call.args)[:500]}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _sidecar_dedupe_entries(spans: list[dict[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for sp in spans:
        meta = sp.get("metadata")
        if not isinstance(meta, dict) or meta.get("source") != "sidecar":
            continue
        tid = meta.get("tool_use_id")
        if isinstance(tid, str) and tid.strip():
            keys.add(("tool_use_id", tid.strip()))
        sdk = meta.get("sidecar_dedupe_key")
        if isinstance(sdk, str) and sdk.strip():
            keys.add(("sidecar_dedupe_key", sdk.strip()))
    return keys


class TraceLogger:
    """Write tool_call spans to TRACES.jsonl for a canonical activity session id."""

    def __init__(self, content_root: Path) -> None:
        self._root = content_root

    def persist_tool_spans(self, memory_session_id: str, session: ParsedSession) -> int:
        existing = load_session_trace_spans(self._root, memory_session_id)
        dedupe = _sidecar_dedupe_entries(existing)
        written = 0
        for call in session.tool_calls:
            tid = (call.tool_use_id or "").strip()
            if tid:
                dup: tuple[str, str] = ("tool_use_id", tid)
            else:
                dup = ("sidecar_dedupe_key", _anon_dedupe_key(call))
            if dup in dedupe:
                continue

            status = _infer_tool_status(call.result)
            metadata: dict[str, Any] = {
                "source": "sidecar",
                "args_summary": _args_summary(call.args),
            }
            if tid:
                metadata["tool_use_id"] = tid
            else:
                metadata["sidecar_dedupe_key"] = dup[1]

            span_name = call.name.rsplit("__", 1)[-1] if call.name else "tool"
            rid = record_trace(
                self._root,
                memory_session_id,
                span_type="tool_call",
                name=span_name,
                status=status,
                duration_ms=call.duration_ms,
                metadata=metadata,
                timestamp=call.timestamp,
            )
            if rid:
                dedupe.add(dup)
                written += 1
        return written
