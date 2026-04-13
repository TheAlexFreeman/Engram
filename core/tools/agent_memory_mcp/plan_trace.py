"""Trace span schema and helpers for structured plan traces."""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .path_policy import validate_session_id, validate_slug

_log = logging.getLogger(__name__)

TRACE_SPAN_TYPES = {
    "tool_call",
    "plan_action",
    "retrieval",
    "verification",
    "guardrail_check",
    "policy_violation",
}
TRACE_STATUSES = {"ok", "error", "denied"}

_TRACE_STR_MAX = 200
_TRACE_META_MAX_BYTES = 2048
_CREDENTIAL_FIELD_RE = re.compile(r"(key|token|secret|password|auth)", re.IGNORECASE)
_CHARS_PER_TOKEN = 4
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _sanitize_metadata(
    metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Sanitize trace span metadata per the finalized design decisions.

    Rules:
    - Strings > 200 chars are truncated with '[truncated]' suffix.
    - Field names matching credential patterns are replaced with '[redacted]'.
    - Objects nested beyond depth 2 are stringified.
    - Total JSON size > 2 KB is reduced to top-level scalar fields only.
    """
    if metadata is None:
        return None

    def _sanitize_value(key: str, val: Any, depth: int) -> Any:
        if _CREDENTIAL_FIELD_RE.search(key):
            return "[redacted]"
        if isinstance(val, dict):
            if depth >= 2:
                s = str(val)
                return s[:_TRACE_STR_MAX] + "[truncated]" if len(s) > _TRACE_STR_MAX else s
            return {k: _sanitize_value(k, v, depth + 1) for k, v in val.items()}
        if isinstance(val, str) and len(val) > _TRACE_STR_MAX:
            return val[:_TRACE_STR_MAX] + "[truncated]"
        return val

    sanitized: dict[str, Any] = {k: _sanitize_value(k, v, 0) for k, v in metadata.items()}
    try:
        if len(json.dumps(sanitized, ensure_ascii=False)) > _TRACE_META_MAX_BYTES:
            sanitized = {k: v for k, v in sanitized.items() if not isinstance(v, (dict, list))}
    except (TypeError, ValueError):
        sanitized = {}
    return sanitized or None


def _make_span_id() -> str:
    """Generate a 12-char lowercase hex span ID (first 12 hex chars of UUID4)."""
    return uuid.uuid4().hex[:12]


@dataclass(slots=True)
class TraceSpan:
    """A single trace span written to a session's TRACES.jsonl file."""

    span_id: str
    session_id: str
    timestamp: str
    span_type: str
    name: str
    status: str
    parent_span_id: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] | None = None
    cost: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.span_type not in TRACE_SPAN_TYPES:
            raise ValidationError(
                f"span_type must be one of {sorted(TRACE_SPAN_TYPES)}: {self.span_type!r}"
            )
        if self.status not in TRACE_STATUSES:
            raise ValidationError(
                f"status must be one of {sorted(TRACE_STATUSES)}: {self.status!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "span_id": self.span_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "span_type": self.span_type,
            "name": self.name,
            "status": self.status,
        }
        if self.parent_span_id is not None:
            d["parent_span_id"] = self.parent_span_id
        if self.duration_ms is not None:
            d["duration_ms"] = self.duration_ms
        if self.metadata is not None:
            d["metadata"] = self.metadata
        if self.cost is not None:
            d["cost"] = self.cost
        return d


def trace_file_path(session_id: str) -> str:
    """Derive the TRACES.jsonl repo-relative path from a session_id.

    Session IDs look like ``memory/activity/YYYY/MM/DD/chat-NNN``.
    Trace files live at ``memory/activity/YYYY/MM/DD/chat-NNN.traces.jsonl``.
    """
    return f"{session_id}.traces.jsonl"


def estimate_cost(
    *,
    input_chars: int = 0,
    output_chars: int = 0,
    chars_per_token: int = _CHARS_PER_TOKEN,
) -> dict[str, int]:
    """Estimate token cost from character counts.  Returns ``{tokens_in, tokens_out}``."""
    return {
        "tokens_in": max(0, (input_chars + chars_per_token - 1) // chars_per_token),
        "tokens_out": max(0, (output_chars + chars_per_token - 1) // chars_per_token),
    }


def _format_trace_timestamp(when: datetime) -> str:
    utc = when.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def record_trace(
    root: Path,
    session_id: str | None,
    *,
    span_type: str,
    name: str,
    status: str = "ok",
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
    cost: dict[str, Any] | None = None,
    parent_span_id: str | None = None,
    timestamp: datetime | None = None,
) -> str | None:
    """Append a trace span to the session's TRACES.jsonl file.

    Non-blocking: all exceptions are caught and swallowed.
    Returns the generated ``span_id`` on success, ``None`` on failure or when
    ``session_id`` is absent.
    """
    if not session_id:
        return None
    try:
        sanitized_metadata = _sanitize_metadata(metadata)
        ts = timestamp if timestamp is not None else datetime.now(timezone.utc)
        now_iso = _format_trace_timestamp(ts)
        span = TraceSpan(
            span_id=_make_span_id(),
            session_id=session_id,
            timestamp=now_iso,
            span_type=span_type,
            name=name,
            status=status,
            parent_span_id=parent_span_id,
            duration_ms=duration_ms,
            metadata=sanitized_metadata,
            cost=cost,
        )
        abs_trace = root / trace_file_path(session_id)
        abs_trace.parent.mkdir(parents=True, exist_ok=True)
        with abs_trace.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(span.to_dict(), ensure_ascii=False) + "\n")
        return span.span_id
    except Exception:  # noqa: BLE001
        _log.debug("record_trace failed for session %s", session_id, exc_info=True)
        return None


def load_session_trace_spans(root: Path, session_id: str) -> list[dict[str, Any]]:
    """Load all spans from a session's trace file (best-effort, skips bad lines)."""
    validate_session_id(session_id)
    path = root / trace_file_path(session_id)
    if not path.exists():
        return []
    spans: list[dict[str, Any]] = []
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for raw_line in raw_lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            span = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(span, dict):
            spans.append(span)
    return spans


def _session_id_from_trace_path(activity_root: Path, trace_file: Path) -> str | None:
    try:
        rel = trace_file.relative_to(activity_root)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 4:
        return None
    name = parts[-1]
    if not name.endswith(".traces.jsonl"):
        return None
    stem = name[: -len(".traces.jsonl")]
    day = "/".join(parts[:3])
    return f"memory/activity/{day}/{stem}"


def _span_date_key(span: dict[str, Any]) -> str:
    ts = str(span.get("timestamp") or "")
    return ts[:10] if len(ts) >= 10 else "unknown"


def query_trace_spans(
    root: Path,
    *,
    session_id: str | None = None,
    sessions: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    span_type: str | None = None,
    plan_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    group_by: str | None = None,
) -> dict[str, Any]:
    """Query trace spans across one session or a date-filtered activity window."""
    if span_type is not None and span_type not in TRACE_SPAN_TYPES:
        raise ValidationError(f"span_type must be one of {sorted(TRACE_SPAN_TYPES)}: {span_type!r}")
    if status is not None and status not in TRACE_STATUSES:
        raise ValidationError(f"status must be one of {sorted(TRACE_STATUSES)}: {status!r}")
    if date_from is not None and not _DATE_RE.match(date_from):
        raise ValidationError("date_from must be in YYYY-MM-DD format")
    if date_to is not None and not _DATE_RE.match(date_to):
        raise ValidationError("date_to must be in YYYY-MM-DD format")
    if session_id is not None:
        validate_session_id(session_id)
    if sessions:
        for sid in sessions:
            validate_session_id(sid)
    if session_id is not None and sessions:
        raise ValidationError("Provide only one of session_id or sessions, not both")
    if plan_id is not None:
        plan_id = validate_slug(plan_id, field_name="plan_id")
    if group_by is not None and group_by not in {"tool_name", "span_type", "session_id", "date"}:
        raise ValidationError(
            "group_by must be one of tool_name, span_type, session_id, date when provided"
        )

    try:
        normalized_limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValidationError("limit must be an integer >= 1") from exc
    if normalized_limit < 1:
        raise ValidationError("limit must be >= 1")

    activity_root = root / "memory" / "activity"
    trace_files: list[tuple[Path, str | None]] = []

    if sessions:
        for sid in sessions:
            candidate = root / trace_file_path(sid)
            if candidate.exists():
                trace_files.append((candidate, sid))
    elif session_id is not None:
        candidate = root / trace_file_path(session_id)
        if candidate.exists():
            trace_files.append((candidate, session_id))
    elif activity_root.is_dir():
        for trace_file in sorted(activity_root.rglob("*.traces.jsonl"), reverse=True):
            parts = trace_file.relative_to(activity_root).parts
            if len(parts) >= 4:
                file_date = f"{parts[0]}-{parts[1]}-{parts[2]}"
                if date_from is not None and file_date < date_from:
                    continue
                if date_to is not None and file_date > date_to:
                    continue
            trace_files.append((trace_file, _session_id_from_trace_path(activity_root, trace_file)))

    all_spans: list[dict[str, Any]] = []
    for trace_file, sid_hint in trace_files:
        try:
            raw_lines = trace_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        for raw_line in raw_lines:
            line = raw_line.strip()
            if not line:
                continue
            try:
                span = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(span, dict):
                continue
            if span_type is not None and span.get("span_type") != span_type:
                continue
            if status is not None and span.get("status") != status:
                continue
            if plan_id is not None:
                metadata = span.get("metadata")
                if not isinstance(metadata, dict) or metadata.get("plan_id") != plan_id:
                    continue
            resolved_sid = span.get("session_id") or sid_hint
            if resolved_sid is not None:
                span = {**span, "session_id": resolved_sid}
            all_spans.append(span)

    all_spans.sort(key=lambda span: str(span.get("timestamp") or ""), reverse=True)
    total_matched = len(all_spans)

    total_duration_ms = 0
    total_tokens_in = 0
    total_tokens_out = 0
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    error_count = 0
    for span in all_spans:
        try:
            total_duration_ms += int(span.get("duration_ms") or 0)
        except (TypeError, ValueError):
            pass

        span_type_name = str(span.get("span_type") or "unknown")
        by_type[span_type_name] = by_type.get(span_type_name, 0) + 1

        status_name = str(span.get("status") or "unknown")
        by_status[status_name] = by_status.get(status_name, 0) + 1
        if status_name == "error":
            error_count += 1

        span_cost = span.get("cost")
        if isinstance(span_cost, dict):
            try:
                total_tokens_in += int(span_cost.get("tokens_in", 0))
            except (TypeError, ValueError):
                pass
            try:
                total_tokens_out += int(span_cost.get("tokens_out", 0))
            except (TypeError, ValueError):
                pass

    aggregates = {
        "total_duration_ms": total_duration_ms,
        "total_cost": {
            "tokens_in": total_tokens_in,
            "tokens_out": total_tokens_out,
        },
        "by_type": by_type,
        "by_status": by_status,
        "error_rate": round(error_count / total_matched, 3) if total_matched > 0 else 0.0,
    }

    if group_by:
        buckets: dict[str, list[dict[str, Any]]] = {}
        for span in all_spans:
            if group_by == "tool_name":
                key = str(span.get("name") or "")
            elif group_by == "span_type":
                key = str(span.get("span_type") or "")
            elif group_by == "session_id":
                key = str(span.get("session_id") or "")
            else:
                key = _span_date_key(span)
            buckets.setdefault(key, []).append(span)

        group_rows: list[dict[str, Any]] = []
        for key, group_spans in buckets.items():
            g_count = len(group_spans)
            g_dur = 0
            g_err = 0
            for sp in group_spans:
                try:
                    g_dur += int(sp.get("duration_ms") or 0)
                except (TypeError, ValueError):
                    pass
                if str(sp.get("status") or "") == "error":
                    g_err += 1
            group_rows.append(
                {
                    "group_key": key,
                    "count": g_count,
                    "total_duration_ms": g_dur,
                    "mean_duration_ms": round(g_dur / g_count, 3) if g_count else 0.0,
                    "error_rate": round(g_err / g_count, 3) if g_count else 0.0,
                }
            )
        group_rows.sort(key=lambda row: (-int(row["count"]), str(row["group_key"])))
        limited_groups = group_rows[:normalized_limit]
        return {
            "spans": [],
            "groups": limited_groups,
            "group_by": group_by,
            "total_matched": total_matched,
            "aggregates": aggregates,
        }

    limited_spans = all_spans[:normalized_limit]
    return {
        "spans": limited_spans,
        "total_matched": total_matched,
        "aggregates": aggregates,
    }
