"""Implementation of the ``engram approval`` command group."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ..plan_approvals import approval_filename, approvals_summary_path, list_approval_documents

_STATUS_ORDER = {
    "expired": 0,
    "pending": 1,
    "approved": 2,
    "rejected": 3,
}


def register_approval(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "approval",
        help="Inspect plan approval requests from the terminal.",
    )
    parser.set_defaults(handler=_run_approval_help, _approval_parser=parser)

    approval_subparsers = parser.add_subparsers(dest="approval_command")

    list_parser = approval_subparsers.add_parser(
        "list",
        help="List pending approval requests with expiry and scope context.",
        parents=parents or [],
    )
    list_parser.set_defaults(handler=run_approval_list)
    return parser


def _run_approval_help(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    content_root: Path,
) -> int:
    del repo_root, content_root

    parser = getattr(args, "_approval_parser", None)
    if isinstance(parser, argparse.ArgumentParser):
        parser.print_help()
        return 0
    raise ValueError("approval parser unavailable")


def _approval_id(plan_id: str, phase_id: str) -> str:
    return approval_filename(plan_id, phase_id).removesuffix(".yaml")


def _approval_sort_key(entry: dict[str, Any]) -> tuple[int, str, str, str]:
    return (
        _STATUS_ORDER.get(str(entry.get("status") or ""), len(_STATUS_ORDER)),
        str(entry.get("expires") or ""),
        str(entry.get("requested") or ""),
        str(entry.get("id") or ""),
    )


def _build_list_payload(content_root: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for rel_path, approval in list_approval_documents(content_root):
        context = approval.context if isinstance(approval.context, dict) else {}
        raw_sources = context.get("sources")
        raw_changes = context.get("changes")
        sources: list[Any] = list(raw_sources) if isinstance(raw_sources, list) else []
        changes: list[Any] = list(raw_changes) if isinstance(raw_changes, list) else []
        entries.append(
            {
                "id": _approval_id(approval.plan_id, approval.phase_id),
                "path": rel_path,
                "status": approval.status,
                "requested": approval.requested,
                "expires": approval.expires,
                "title": str(context.get("phase_title") or approval.phase_id),
                "summary": str(context.get("phase_summary") or ""),
                "change_class": str(context.get("change_class") or ""),
                "source_count": len(sources),
                "change_count": len(changes),
                "sources": sources,
                "changes": changes,
                "additional_context": str(context.get("additional_context") or ""),
                "scope": {
                    "project_id": approval.project_id,
                    "plan_id": approval.plan_id,
                    "phase_id": approval.phase_id,
                },
            }
        )

    entries.sort(key=_approval_sort_key)
    return {
        "count": len(entries),
        "results": entries,
        "summary_path": approvals_summary_path(),
    }


def _render_list(payload: dict[str, Any]) -> str:
    entries = payload.get("results") or []
    if not entries:
        return "Approval queue\n\nNo pending approvals."

    lines = ["Approval queue", ""]
    for index, entry in enumerate(entries, start=1):
        lines.append(f"{index}. {entry['id']} [{entry['status']}] {entry['title']}")
        scope = entry.get("scope") or {}
        lines.append(
            "   scope: "
            + f"{scope.get('project_id', '?')} / {scope.get('plan_id', '?')} / {scope.get('phase_id', '?')}"
        )

        detail_parts: list[str] = []
        if entry.get("requested"):
            detail_parts.append(f"requested: {entry['requested'][:10]}")
        if entry.get("expires"):
            detail_parts.append(f"expires: {entry['expires'][:10]}")
        if entry.get("change_class"):
            detail_parts.append(f"change class: {entry['change_class']}")
        if detail_parts:
            lines.append(f"   {' | '.join(detail_parts)}")

        if entry.get("summary"):
            lines.append(f"   {entry['summary']}")

        lines.append(
            f"   sources: {entry.get('source_count', 0)} | changes: {entry.get('change_count', 0)}"
        )

        if entry.get("additional_context"):
            lines.append(f"   context: {entry['additional_context']}")

    return "\n".join(lines)


def run_approval_list(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del repo_root

    payload = _build_list_payload(content_root)
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_render_list(payload))
    return 0
