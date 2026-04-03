"""Implementation of the ``engram log`` subcommand."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from .formatting import (
    filter_access_entries,
    format_snippet,
    load_access_entries,
    parse_iso_date,
    visible_namespace,
)


def register_log(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "log",
        help="Show recent ACCESS timeline entries with namespace and date filters.",
        parents=parents or [],
    )
    parser.add_argument(
        "--namespace",
        help="Restrict results to a namespace or repo-relative prefix such as knowledge or memory/skills.",
    )
    parser.add_argument(
        "--since",
        help="Only include ACCESS entries on or after YYYY-MM-DD.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of ACCESS entries to show.",
    )
    parser.set_defaults(handler=run_log)
    return parser


def _entry_sort_key(item: dict[str, Any]) -> tuple[date, str, str, str]:
    return (
        parse_iso_date(item.get("date")) or date.min,
        str(item.get("date") or ""),
        str(item.get("file") or ""),
        str(item.get("access_file") or ""),
    )


def _render_human(payload: dict[str, Any]) -> str:
    filters: list[str] = []
    if payload.get("namespace"):
        filters.append(f"namespace={payload['namespace']}")
    if payload.get("since"):
        filters.append(f"since={payload['since']}")

    header = "ACCESS log"
    if filters:
        header = f"{header} ({', '.join(filters)})"

    entries = payload.get("results") or []
    if not entries:
        return header + "\n\nNo ACCESS entries found."

    lines = [header, ""]
    for index, entry in enumerate(entries, start=1):
        lines.append(
            f"{index}. {entry.get('date') or 'unknown-date'} [{entry['namespace']}] {entry['file']}"
        )
        detail_parts: list[str] = []
        if entry.get("task"):
            detail_parts.append(f"task: {entry['task']}")
        if entry.get("mode"):
            detail_parts.append(f"mode: {entry['mode']}")
        if entry.get("helpfulness") is not None:
            detail_parts.append(f"helpfulness: {float(entry['helpfulness']):.2f}")
        if entry.get("session_id"):
            detail_parts.append(f"session: {entry['session_id']}")
        if detail_parts:
            lines.append(f"   {' | '.join(detail_parts)}")
        if entry.get("note"):
            lines.append(f"   {format_snippet(str(entry['note']), limit=160)}")

    return "\n".join(lines)


def run_log(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del repo_root

    if args.since and parse_iso_date(args.since) is None:
        raise ValueError("--since must use YYYY-MM-DD")

    limit = max(int(args.limit), 1)
    entries = load_access_entries(content_root)
    filtered = filter_access_entries(entries, namespace=args.namespace, since=args.since)

    results = [
        {
            **entry.to_dict(),
            "namespace": visible_namespace(entry.file),
        }
        for entry in filtered
    ]
    results.sort(key=_entry_sort_key, reverse=True)
    results = results[:limit]

    payload = {
        "namespace": args.namespace,
        "since": args.since,
        "count": len(results),
        "results": results,
    }

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_render_human(payload))
    return 0
