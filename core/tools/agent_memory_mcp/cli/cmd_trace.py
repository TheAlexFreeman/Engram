"""Implementation of the ``engram trace`` command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..errors import ValidationError
from ..plan_trace import TRACE_SPAN_TYPES, TRACE_STATUSES, query_trace_spans
from .formatting import format_snippet


def register_trace(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "trace",
        help="Query TRACES.jsonl spans by session, date, plan, type, or status.",
        parents=parents or [],
    )
    parser.add_argument(
        "--session-id",
        help="Restrict results to one canonical memory/activity/YYYY/MM/DD/chat-NNN session id.",
    )
    parser.add_argument(
        "--date-from",
        help="Only scan trace files on or after YYYY-MM-DD.",
    )
    parser.add_argument(
        "--date-to",
        help="Only scan trace files on or before YYYY-MM-DD.",
    )
    parser.add_argument(
        "--span-type",
        choices=sorted(TRACE_SPAN_TYPES),
        help="Restrict results to one trace span type.",
    )
    parser.add_argument(
        "--plan",
        dest="plan_id",
        help="Restrict results to spans whose metadata.plan_id matches this plan slug.",
    )
    parser.add_argument(
        "--status",
        choices=sorted(TRACE_STATUSES),
        help="Restrict results to one trace status.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of spans to return after newest-first sorting.",
    )
    parser.set_defaults(handler=run_trace)
    return parser


def _filter_summary(payload: dict[str, Any], args: argparse.Namespace) -> str:
    filters: list[str] = []
    if getattr(args, "session_id", None):
        filters.append(f"session={args.session_id}")
    if getattr(args, "date_from", None):
        filters.append(f"date_from={args.date_from}")
    if getattr(args, "date_to", None):
        filters.append(f"date_to={args.date_to}")
    if getattr(args, "span_type", None):
        filters.append(f"span_type={args.span_type}")
    if getattr(args, "plan_id", None):
        filters.append(f"plan={args.plan_id}")
    if getattr(args, "status", None):
        filters.append(f"status={args.status}")
    header = "Trace query"
    if filters:
        header += f" ({', '.join(filters)})"
    return header


def _format_counts(counts: object) -> str | None:
    if not isinstance(counts, dict) or not counts:
        return None
    parts = [f"{key}={counts[key]}" for key in sorted(counts)]
    return ", ".join(parts)


def _format_metadata(metadata: object) -> str | None:
    if not isinstance(metadata, dict) or not metadata:
        return None
    parts: list[str] = []
    for key in sorted(metadata):
        value = metadata[key]
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, sort_keys=True, default=str)
        else:
            rendered = str(value)
        parts.append(f"{key}={rendered}")
    return format_snippet(" | ".join(parts), limit=220)


def _format_cost(cost: object) -> str | None:
    if not isinstance(cost, dict):
        return None
    tokens_in = cost.get("tokens_in")
    tokens_out = cost.get("tokens_out")
    if tokens_in is None and tokens_out is None:
        return None
    return f"in={int(tokens_in or 0)} out={int(tokens_out or 0)}"


def _render_human(payload: dict[str, Any], args: argparse.Namespace) -> str:
    header = _filter_summary(payload, args)
    spans = payload.get("spans")
    if not isinstance(spans, list) or not spans:
        return header + "\n\nNo trace spans found."

    aggregates_raw = payload.get("aggregates")
    aggregates: dict[str, Any] = aggregates_raw if isinstance(aggregates_raw, dict) else {}
    total_matched = int(payload.get("total_matched") or 0)
    total_duration_ms = int(aggregates.get("total_duration_ms") or 0)
    total_cost = aggregates.get("total_cost")

    lines = [header, ""]
    lines.append(f"Matched spans: {total_matched}")
    lines.append(f"Total duration: {total_duration_ms} ms")
    if isinstance(total_cost, dict):
        lines.append(
            "Total cost: "
            + f"in={int(total_cost.get('tokens_in', 0))} out={int(total_cost.get('tokens_out', 0))}"
        )
    lines.append(f"Error rate: {float(aggregates.get('error_rate') or 0.0):.3f}")

    by_type_line = _format_counts(aggregates.get("by_type"))
    if by_type_line:
        lines.append(f"By type: {by_type_line}")
    by_status_line = _format_counts(aggregates.get("by_status"))
    if by_status_line:
        lines.append(f"By status: {by_status_line}")

    lines.append("")
    for index, span in enumerate(spans, start=1):
        if not isinstance(span, dict):
            continue
        timestamp = str(span.get("timestamp") or "unknown-time")
        span_type = str(span.get("span_type") or "unknown")
        status = str(span.get("status") or "unknown")
        name = str(span.get("name") or "unnamed")
        lines.append(f"{index}. {timestamp} [{span_type}/{status}] {name}")

        detail_parts: list[str] = []
        if span.get("session_id"):
            detail_parts.append(f"session: {span['session_id']}")
        if span.get("duration_ms") is not None:
            detail_parts.append(f"duration: {span['duration_ms']} ms")
        if span.get("span_id"):
            detail_parts.append(f"span: {span['span_id']}")
        if span.get("parent_span_id"):
            detail_parts.append(f"parent: {span['parent_span_id']}")
        if detail_parts:
            lines.append(f"   {' | '.join(detail_parts)}")

        metadata_line = _format_metadata(span.get("metadata"))
        if metadata_line:
            lines.append(f"   metadata: {metadata_line}")

        cost_line = _format_cost(span.get("cost"))
        if cost_line:
            lines.append(f"   cost: {cost_line}")

    return "\n".join(lines)


def run_trace(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del repo_root

    try:
        payload = query_trace_spans(
            content_root,
            session_id=getattr(args, "session_id", None),
            date_from=getattr(args, "date_from", None),
            date_to=getattr(args, "date_to", None),
            span_type=getattr(args, "span_type", None),
            plan_id=getattr(args, "plan_id", None),
            status=getattr(args, "status", None),
            limit=getattr(args, "limit", 100),
        )
    except ValidationError as exc:
        errors = [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            print("Trace query failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_render_human(payload, args))
    return 0
