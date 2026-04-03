"""Implementation of the ``engram approval`` command group."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..errors import NotFoundError, ValidationError
from ..git_repo import GitRepo
from ..path_policy import validate_slug
from ..plan_approvals import approval_filename, approvals_summary_path, list_approval_documents
from ..tools.semantic import plan_tools as plan_tool_runtime
from .formatting import render_governed_preview

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
        help="Inspect and resolve plan approval requests from the terminal.",
    )
    parser.set_defaults(handler=_run_approval_help, _approval_parser=parser)

    approval_subparsers = parser.add_subparsers(dest="approval_command")

    list_parser = approval_subparsers.add_parser(
        "list",
        help="List pending approval requests with expiry and scope context.",
        parents=parents or [],
    )
    list_parser.set_defaults(handler=run_approval_list)

    resolve_parser = approval_subparsers.add_parser(
        "resolve",
        help="Approve or reject a pending approval request by stable approval id.",
        parents=parents or [],
    )
    resolve_parser.add_argument(
        "approval_id",
        help="Stable approval id from `engram approval list`, such as tracked-plan--phase-a.",
    )
    resolve_parser.add_argument(
        "resolution",
        help="Decision to record: approve or reject.",
    )
    resolve_parser.add_argument(
        "--comment",
        help="Optional reviewer comment stored on the resolved approval document.",
    )
    resolve_parser.add_argument(
        "--preview",
        action="store_true",
        help="Render the governed preview without writing or committing.",
    )
    resolve_parser.set_defaults(handler=run_approval_resolve)
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


def _content_prefix(repo_root: Path, content_root: Path) -> str:
    try:
        return content_root.relative_to(repo_root).as_posix()
    except ValueError:
        return ""


def _parse_approval_id(raw_approval_id: str) -> tuple[str, str, str]:
    candidate = Path(str(raw_approval_id or "").strip()).name
    if candidate.endswith(".yaml"):
        candidate = candidate.removesuffix(".yaml")

    parts = candidate.split("--")
    if len(parts) != 2 or not all(parts):
        raise ValueError("approval id must be '<plan-id>--<phase-id>'")

    plan_id = validate_slug(parts[0], field_name="plan_id")
    phase_id = validate_slug(parts[1], field_name="phase_id")
    return candidate, plan_id, phase_id


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


def _resolve_state(payload: dict[str, Any]) -> dict[str, Any]:
    new_state = payload.get("new_state")
    return new_state if isinstance(new_state, dict) else {}


def _render_resolve_preview(payload: dict[str, Any]) -> str:
    preview_payload = payload.get("preview")
    if not isinstance(preview_payload, dict):
        return _render_resolve_result(payload)
    return render_governed_preview(preview_payload)


def _render_resolve_result(payload: dict[str, Any]) -> str:
    state = _resolve_state(payload)
    approval_id = state.get("approval_id") or "unknown"
    status = state.get("status") or payload.get("status") or "resolved"

    lines = [f"Resolved approval: {approval_id} [{status}]"]

    message = state.get("message")
    if isinstance(message, str) and message:
        lines.append(message)

    plan_status = state.get("plan_status")
    if isinstance(plan_status, str) and plan_status:
        lines.append(f"Plan status: {plan_status}")

    project_id = state.get("project_id")
    if isinstance(project_id, str) and project_id:
        lines.append(f"Project: {project_id}")

    phase_id = state.get("phase_id")
    if isinstance(phase_id, str) and phase_id:
        lines.append(f"Phase: {phase_id}")

    approval_file = state.get("approval_file")
    if isinstance(approval_file, str) and approval_file:
        lines.append(f"Approval file: {approval_file}")

    comment = state.get("comment")
    if isinstance(comment, str) and comment:
        lines.append(f"Comment: {comment}")

    commit_sha = payload.get("commit_sha")
    if isinstance(commit_sha, str) and commit_sha:
        lines.append(f"Commit SHA: {commit_sha}")

    commit_message = payload.get("commit_message")
    if isinstance(commit_message, str) and commit_message:
        lines.append(f"Message: {commit_message}")

    warnings = payload.get("warnings")
    if isinstance(warnings, list) and warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in warnings)

    return "\n".join(lines)


def _render_resolve_errors(errors: list[str]) -> str:
    lines = ["Approval resolution failed:"]
    if errors:
        lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines)


def run_approval_list(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del repo_root

    payload = _build_list_payload(content_root)
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_render_list(payload))
    return 0


def run_approval_resolve(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    try:
        _approval_key, plan_id, phase_id = _parse_approval_id(args.approval_id)
        repo = GitRepo(repo_root, content_prefix=_content_prefix(repo_root, content_root))
        resolve_helper = getattr(plan_tool_runtime, "resolve_approval_action_result")
        payload = resolve_helper(
            repo=repo,
            root=content_root,
            plan_id=plan_id,
            phase_id=phase_id,
            resolution=str(getattr(args, "resolution", "")),
            comment=getattr(args, "comment", None),
            preview=bool(getattr(args, "preview", False)),
        )
    except (NotFoundError, ValidationError, ValueError) as exc:
        errors = [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            print(_render_resolve_errors(errors), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        if getattr(args, "preview", False) and isinstance(payload.get("preview"), dict):
            print(_render_resolve_preview(payload))
        else:
            print(_render_resolve_result(payload))
    return 0
