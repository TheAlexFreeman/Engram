"""Implementation of the ``engram status`` subcommand."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .formatting import parse_iso_date, parse_scalar_frontmatter, read_text

_DEFAULT_STAGE = "Exploration"
_DEFAULT_AGGREGATION_TRIGGER = 15
_DEFAULT_LOW_TRUST_THRESHOLD = 120


def register_status(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "status",
        help="Show repo health, review pressure, and active plans.",
        parents=parents or [],
    )
    parser.set_defaults(handler=run_status)
    return parser


def _parse_stage(init_text: str) -> str:
    match = re.search(r"## Current active stage:\s*([^\n]+)", init_text)
    if match is None:
        return _DEFAULT_STAGE
    return match.group(1).strip() or _DEFAULT_STAGE


def _parse_last_periodic_review(init_text: str) -> str | None:
    match = re.search(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", init_text)
    if match is None:
        return None
    return match.group(1)


def _parse_aggregation_trigger(init_text: str) -> int:
    match = re.search(r"aggregation trigger\s*\|\s*(\d+)\s+entries", init_text, re.IGNORECASE)
    if match is not None:
        return int(match.group(1))

    fallback = re.search(
        r"aggregate when .*?reach\s*\*\*(\d+)\*\*",
        init_text,
        re.IGNORECASE,
    )
    if fallback is not None:
        return int(fallback.group(1))
    return _DEFAULT_AGGREGATION_TRIGGER


def _parse_low_trust_threshold(init_text: str) -> int:
    match = re.search(r"low.*?(\d+)[- ]day", init_text, re.IGNORECASE)
    if match is None:
        return _DEFAULT_LOW_TRUST_THRESHOLD
    return int(match.group(1))


def _count_nonempty_lines(path: Path) -> int:
    return sum(1 for line in read_text(path).splitlines() if line.strip())


def _access_counts(content_root: Path, trigger: int) -> list[dict[str, Any]]:
    counts: list[dict[str, Any]] = []
    for rel_path in (
        "memory/users/ACCESS.jsonl",
        "memory/knowledge/ACCESS.jsonl",
        "memory/skills/ACCESS.jsonl",
        "memory/working/projects/ACCESS.jsonl",
        "memory/activity/ACCESS.jsonl",
    ):
        path = content_root / rel_path
        if not path.exists():
            continue
        entries = _count_nonempty_lines(path)
        counts.append(
            {
                "path": rel_path,
                "entries": entries,
                "above_trigger": entries >= trigger,
                "remaining_to_trigger": max(trigger - entries, 0),
            }
        )
    return counts


def _review_queue_entries(content_root: Path) -> list[dict[str, str]]:
    path = content_root / "governance" / "review-queue.md"
    if not path.exists():
        return []

    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_code_block = False
    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        heading_match = re.match(r"### \[(\d{4}-\d{2}-\d{2})\] (.+)", line)
        if heading_match is not None:
            if current is not None:
                entries.append(current)
            current = {
                "date": heading_match.group(1),
                "title": heading_match.group(2),
            }
            continue

        if current is None:
            continue
        field_match = re.match(r"\*\*(.+?):\*\*\s*(.+)", line)
        if field_match is not None:
            key = field_match.group(1).strip().lower().replace(" ", "_")
            current[key] = field_match.group(2).strip()

    if current is not None:
        entries.append(current)
    return entries


def _summarize_review_queue(content_root: Path) -> dict[str, Any]:
    entries = _review_queue_entries(content_root)
    pending = [
        entry
        for entry in entries
        if entry.get("status", "pending") == "pending"
        or (entry.get("type") == "security" and entry.get("status", "pending") == "investigated")
    ]
    return {
        "count": len(pending),
        "items": pending,
    }


def _summarize_unverified(content_root: Path, low_threshold: int) -> dict[str, Any]:
    folder = content_root / "memory" / "knowledge" / "_unverified"
    files: list[dict[str, Any]] = []
    overdue: list[dict[str, Any]] = []
    if not folder.exists():
        return {"total_files": 0, "overdue_count": 0, "overdue_files": overdue}

    today = date.today()
    for path in sorted(folder.rglob("*.md")):
        if path.name == "SUMMARY.md":
            continue
        metadata = parse_scalar_frontmatter(path)
        effective = parse_iso_date(metadata.get("last_verified") or metadata.get("created") or "")
        age_days = (today - effective).days if effective is not None else None
        item = {
            "path": path.relative_to(content_root).as_posix(),
            "trust": metadata.get("trust"),
            "source": metadata.get("source"),
            "age_days": age_days,
        }
        files.append(item)
        if metadata.get("trust") == "low" and age_days is not None and age_days > low_threshold:
            overdue.append(item)

    files.sort(key=lambda item: (-(item["age_days"] or -1), item["path"]))
    overdue.sort(key=lambda item: (-(item["age_days"] or -1), item["path"]))
    return {
        "total_files": len(files),
        "overdue_count": len(overdue),
        "overdue_files": overdue,
    }


def _parse_plan_payload(path: Path) -> dict[str, str]:
    text = read_text(path)

    try:
        import yaml  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        yaml = None  # type: ignore[assignment]

    if yaml is not None:
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError:
            payload = None
        if isinstance(payload, dict):
            raw_purpose = payload.get("purpose")
            purpose = raw_purpose if isinstance(raw_purpose, dict) else {}
            return {
                "id": str(payload.get("id", "")).strip(),
                "project": str(payload.get("project", "")).strip(),
                "status": str(payload.get("status", "")).strip(),
                "title": str(purpose.get("summary") or payload.get("id") or path.stem).strip(),
            }

    def _extract(pattern: str) -> str:
        match = re.search(pattern, text, re.MULTILINE)
        return match.group(1).strip().strip('"').strip("'") if match is not None else ""

    return {
        "id": _extract(r"^id:\s*(.+)$") or path.stem,
        "project": _extract(r"^project:\s*(.+)$") or path.parents[1].name,
        "status": _extract(r"^status:\s*(.+)$"),
        "title": _extract(r"^\s+summary:\s*(.+)$") or _extract(r"^id:\s*(.+)$") or path.stem,
    }


def _active_plans(content_root: Path) -> list[dict[str, str]]:
    projects_root = content_root / "memory" / "working" / "projects"
    plans: list[dict[str, str]] = []
    if not projects_root.exists():
        return plans

    for path in sorted(projects_root.glob("*/plans/*.yaml")):
        payload = _parse_plan_payload(path)
        if payload.get("status") != "active":
            continue
        plans.append(
            {
                "project": payload.get("project") or path.parents[1].name,
                "plan_id": payload.get("id") or path.stem,
                "title": payload.get("title") or path.stem,
                "path": path.relative_to(content_root).as_posix(),
            }
        )

    plans.sort(key=lambda item: (item["project"], item["plan_id"]))
    return plans


def _build_payload(content_root: Path) -> dict[str, Any]:
    init_text = read_text(content_root / "INIT.md")
    trigger = _parse_aggregation_trigger(init_text)
    low_threshold = _parse_low_trust_threshold(init_text)
    access_counts = _access_counts(content_root, trigger)
    warnings = [
        f"{item['path']} has {item['entries']} entries and exceeds the aggregation trigger {trigger}."
        for item in access_counts
        if item["above_trigger"]
    ]

    return {
        "stage": _parse_stage(init_text),
        "last_periodic_review": _parse_last_periodic_review(init_text),
        "aggregation_trigger": trigger,
        "access_counts": access_counts,
        "pending_reviews": _summarize_review_queue(content_root),
        "unverified_content": _summarize_unverified(content_root, low_threshold),
        "active_plans": {
            "count": len(_active_plans(content_root)),
            "items": _active_plans(content_root),
        },
        "warnings": warnings,
    }


def _render_human(payload: dict[str, Any]) -> str:
    lines = [
        f"Stage: {payload['stage']}",
        f"Last periodic review: {payload['last_periodic_review'] or 'unknown'}",
        f"Aggregation trigger: {payload['aggregation_trigger']}",
        "",
        "ACCESS counts:",
    ]

    access_counts = payload["access_counts"]
    if access_counts:
        for item in access_counts:
            suffix = " (above trigger)" if item["above_trigger"] else ""
            lines.append(f"  - {item['path']}: {item['entries']}{suffix}")
    else:
        lines.append("  - No ACCESS.jsonl files found.")

    review_payload = payload["pending_reviews"]
    lines.extend(
        [
            "",
            f"Pending reviews: {review_payload['count']}",
            f"Unverified content: {payload['unverified_content']['total_files']} files, {payload['unverified_content']['overdue_count']} overdue",
            f"Active plans: {payload['active_plans']['count']}",
        ]
    )

    if payload["active_plans"]["items"]:
        for item in payload["active_plans"]["items"]:
            lines.append(f"  - {item['project']}/{item['plan_id']}: {item['title']}")

    if payload["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        for warning in payload["warnings"]:
            lines.append(f"  - {warning}")

    return "\n".join(lines)


def run_status(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del repo_root
    payload = _build_payload(content_root)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(_render_human(payload))
    return 0
