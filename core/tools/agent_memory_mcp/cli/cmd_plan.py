"""Implementation of the ``engram plan`` command group."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from ..errors import AlreadyDoneError, NotFoundError, ValidationError
from ..git_repo import GitRepo
from ..path_policy import validate_slug
from ..plan_utils import (
    PLAN_STATUSES,
    budget_status,
    load_plan,
    next_action,
    phase_payload,
    plan_create_input_schema,
    plan_progress,
    plan_title,
    raise_collected_validation_errors,
    resolve_phase,
    validation_error_messages,
)
from ..tools.semantic.plan_tools import create_plan_write_result, execute_plan_action_result
from .formatting import render_governed_preview
from .plan_help import build_plan_create_help_text

_STATUS_ORDER = {
    "active": 0,
    "draft": 1,
    "blocked": 2,
    "paused": 3,
    "completed": 4,
    "abandoned": 5,
}

_PLAN_CREATE_SCHEMA = plan_create_input_schema()
_PLAN_CREATE_HELP = build_plan_create_help_text(_PLAN_CREATE_SCHEMA)
_PLAN_CREATE_FIELDS = frozenset(str(name) for name in (_PLAN_CREATE_SCHEMA.get("properties") or {}))


def register_plan(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "plan",
        help="Inspect structured project plans from the terminal.",
    )
    parser.set_defaults(handler=_run_plan_help, _plan_parser=parser)

    plan_subparsers = parser.add_subparsers(dest="plan_command")

    list_parser = plan_subparsers.add_parser(
        "list",
        help="List plans with progress and next-action summaries.",
        parents=parents or [],
    )
    list_parser.add_argument(
        "--status",
        choices=sorted(PLAN_STATUSES),
        help="Restrict results to one plan status.",
    )
    list_parser.add_argument(
        "--project",
        help="Restrict results to one project slug.",
    )
    list_parser.set_defaults(handler=run_plan_list)

    show_parser = plan_subparsers.add_parser(
        "show",
        help="Show the current or selected phase for one plan.",
        parents=parents or [],
    )
    show_parser.add_argument("plan_id", help="Plan slug to inspect.")
    show_parser.add_argument(
        "--project",
        help="Project slug when the plan id is ambiguous across projects.",
    )
    show_parser.add_argument(
        "--phase",
        help="Optional phase slug to render instead of the current actionable phase.",
    )
    show_parser.set_defaults(handler=run_plan_show)

    create_parser = plan_subparsers.add_parser(
        "create",
        help="Create a structured plan from YAML file input or stdin.",
        description=_PLAN_CREATE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=parents or [],
    )
    create_parser.add_argument(
        "input",
        nargs="?",
        help="YAML file containing the plan-create input. Omit or use '-' to read from stdin.",
    )
    create_parser.add_argument(
        "--preview",
        action="store_true",
        help="Validate and render the governed preview without writing or committing.",
    )
    create_parser.add_argument(
        "--json-schema",
        action="store_true",
        help="Print the raw JSON schema accepted by plan create and exit.",
    )
    create_parser.set_defaults(handler=run_plan_create)

    advance_parser = plan_subparsers.add_parser(
        "advance",
        help="Start or complete the current plan phase from the terminal.",
        parents=parents or [],
    )
    advance_parser.add_argument("plan_id", help="Plan slug to advance.")
    advance_parser.add_argument(
        "--project",
        help="Project slug when the plan id is ambiguous across projects.",
    )
    advance_parser.add_argument(
        "--phase",
        help="Optional phase slug to advance instead of the current actionable phase.",
    )
    advance_parser.add_argument(
        "--session-id",
        required=True,
        help="Canonical memory/activity/YYYY/MM/DD/chat-NNN session id for the state change.",
    )
    advance_parser.add_argument(
        "--commit-sha",
        help="Required when the selected phase is already in progress and the command will complete it.",
    )
    advance_parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify postconditions before completing an in-progress phase.",
    )
    advance_parser.add_argument(
        "--preview",
        action="store_true",
        help="Render the governed preview or guarded state without writing.",
    )
    advance_parser.add_argument(
        "--review-file",
        help="YAML or JSON file containing the final review payload. Use '-' to read from stdin.",
    )
    advance_parser.set_defaults(handler=run_plan_advance)
    return parser


def _run_plan_help(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    content_root: Path,
) -> int:
    del repo_root, content_root

    parser = getattr(args, "_plan_parser", None)
    if isinstance(parser, argparse.ArgumentParser):
        parser.print_help()
        return 0
    raise ValueError("plan parser unavailable")


def _content_prefix(repo_root: Path, content_root: Path) -> str:
    try:
        return content_root.relative_to(repo_root).as_posix()
    except ValueError:
        return ""


def _read_plan_input(raw_input: str | None) -> tuple[str, str | None]:
    if raw_input is None or raw_input == "-":
        if raw_input is None and sys.stdin.isatty():
            raise ValueError("Provide a YAML file path or pipe plan input via stdin.")
        return sys.stdin.read(), None

    input_path = Path(raw_input).expanduser().resolve()
    try:
        return input_path.read_text(encoding="utf-8"), str(input_path)
    except OSError as exc:
        raise ValueError(f"Could not read input file: {raw_input}") from exc


def _normalize_create_request(text: str, *, preview: bool) -> dict[str, Any]:
    try:
        raw_payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValidationError(f"Plan input is not valid YAML: {exc}") from exc

    if not isinstance(raw_payload, dict):
        raise ValidationError("Plan input must contain a top-level mapping")

    errors = [
        f"{field}: unexpected top-level field"
        for field in sorted({str(key) for key in raw_payload} - _PLAN_CREATE_FIELDS)
    ]
    raw_preview = raw_payload.get("preview")
    if "preview" in raw_payload and not isinstance(raw_preview, bool):
        errors.append("preview must be a boolean when provided")
    raise_collected_validation_errors(errors)

    return {
        "plan_id": str(raw_payload.get("plan_id", "")),
        "project_id": str(raw_payload.get("project_id", "")),
        "purpose_summary": str(raw_payload.get("purpose_summary", "")),
        "purpose_context": str(raw_payload.get("purpose_context", "")),
        "phases": raw_payload.get("phases", []),
        "session_id": str(raw_payload.get("session_id", "")),
        "questions": raw_payload.get("questions"),
        "budget": raw_payload.get("budget"),
        "status": str(raw_payload.get("status", "active")),
        "preview": preview or bool(raw_preview),
    }


def _render_create_errors(errors: list[str]) -> str:
    lines = ["Plan creation failed:"]
    if errors:
        lines.extend(f"- {error}" for error in errors)
    lines.append("Use 'engram plan create --json-schema' to inspect the nested contract.")
    return "\n".join(lines)


def _render_create_preview(payload: dict[str, Any]) -> str:
    preview_payload = payload.get("preview")
    if not isinstance(preview_payload, dict):
        return json.dumps(payload, indent=2, default=str)

    rendered = render_governed_preview(preview_payload)
    new_state = payload.get("new_state")
    if isinstance(new_state, dict):
        errors = new_state.get("errors")
        if isinstance(errors, list) and errors:
            rendered += "\n\nErrors:\n" + "\n".join(f"  - {error}" for error in errors)
    return rendered


def _render_create_result(payload: dict[str, Any]) -> str:
    new_state = payload.get("new_state") if isinstance(payload.get("new_state"), dict) else {}
    lines: list[str] = []

    plan_path = new_state.get("plan_path") if isinstance(new_state, dict) else None
    if plan_path:
        lines.append(f"Created plan: {plan_path}")

    status = new_state.get("status") if isinstance(new_state, dict) else None
    if status:
        lines.append(f"Status: {status}")

    phase_count = new_state.get("phase_count") if isinstance(new_state, dict) else None
    if isinstance(phase_count, int):
        lines.append(f"Phases: {phase_count}")

    next_step = new_state.get("next_action") if isinstance(new_state, dict) else None
    if isinstance(next_step, dict):
        lines.append(f"Next action: {next_step.get('id')} - {next_step.get('title')}")

    budget_line = _summary_budget_line(
        new_state.get("budget_status") if isinstance(new_state, dict) else None
    )
    if budget_line:
        lines.append(f"Budget: {budget_line}")

    commit_sha = payload.get("commit_sha")
    if commit_sha:
        lines.append(f"Commit: {commit_sha}")

    commit_message = payload.get("commit_message")
    if commit_message:
        lines.append(f"Message: {commit_message}")

    warnings = payload.get("warnings")
    if isinstance(warnings, list) and warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in warnings)

    if not lines:
        return json.dumps(payload, indent=2, default=str)
    return "\n".join(lines)


def _read_mapping_input(raw_input: str, *, label: str) -> dict[str, Any]:
    text, _input_path = _read_plan_input(raw_input)
    del _input_path

    try:
        raw_payload = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValidationError(f"{label.capitalize()} input is not valid YAML: {exc}") from exc

    if raw_payload is None:
        return {}
    if not isinstance(raw_payload, dict):
        raise ValidationError(f"{label.capitalize()} input must contain a top-level mapping")
    if label in raw_payload and isinstance(raw_payload[label], dict) and len(raw_payload) == 1:
        return dict(raw_payload[label])
    return dict(raw_payload)


def _resolve_advance_target(
    content_root: Path,
    *,
    plan_id: str,
    project_id: str | None,
    phase_id: str | None,
) -> tuple[str, str, str]:
    plan_file, resolved_project_id = _resolve_plan_path(content_root, plan_id, project_id)
    plan = load_plan(plan_file, content_root)

    try:
        phase = resolve_phase(plan, phase_id)
    except NotFoundError as exc:
        if phase_id is None:
            raise ValidationError(f"Plan '{plan.id}' has no actionable phase to advance.") from exc
        raise

    if phase.status in {"pending", "blocked"}:
        return "start", resolved_project_id, phase.id
    if phase.status == "in-progress":
        return "complete", resolved_project_id, phase.id
    raise ValidationError(f"Phase '{phase.id}' cannot be advanced from status '{phase.status}'.")


def _format_next_action(raw_next_action: Any) -> str | None:
    if isinstance(raw_next_action, dict):
        phase_id = raw_next_action.get("id")
        title = raw_next_action.get("title")
        if isinstance(phase_id, str) and isinstance(title, str):
            return f"{phase_id} - {title}"
        if isinstance(title, str):
            return title
        if isinstance(phase_id, str):
            return phase_id
        return None
    if isinstance(raw_next_action, str) and raw_next_action.strip():
        return raw_next_action.strip()
    return None


def _format_plan_progress(raw_progress: Any) -> str | None:
    if (
        isinstance(raw_progress, list)
        and len(raw_progress) == 2
        and all(isinstance(item, int) for item in raw_progress)
    ):
        return f"{raw_progress[0]}/{raw_progress[1]}"
    return None


def _effective_advance_state(payload: dict[str, Any]) -> dict[str, Any]:
    new_state = payload.get("new_state")
    if isinstance(new_state, dict):
        return new_state
    return payload


def _render_verification_results(payload: dict[str, Any], lines: list[str]) -> None:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        parts: list[str] = []
        for key in ("passed", "failed", "errors", "skipped"):
            value = summary.get(key)
            if isinstance(value, int):
                parts.append(f"{key}: {value}")
        if parts:
            lines.append(f"Verification: {' | '.join(parts)}")

    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return

    lines.append("")
    lines.append("Verification results:")
    for item in results:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "unknown")
        description = str(item.get("postcondition") or "verification item")
        line = f"- [{status}] {description}"
        result_type = item.get("type")
        if isinstance(result_type, str) and result_type:
            line += f" ({result_type})"
        detail = item.get("detail")
        if isinstance(detail, str) and detail:
            line += f": {detail}"
        lines.append(line)


def _render_advance_preview(payload: dict[str, Any]) -> str:
    preview_payload = payload.get("preview")
    if not isinstance(preview_payload, dict):
        return _render_advance_result(payload)
    return render_governed_preview(preview_payload)


def _render_advance_result(payload: dict[str, Any]) -> str:
    state = _effective_advance_state(payload)
    phase_id = state.get("phase_id") or payload.get("phase_id") or "unknown"
    phase_status = state.get("phase_status") or payload.get("phase_status")
    plan_status = state.get("plan_status") or payload.get("plan_status")

    if payload.get("status") == "verification_failed":
        header = f"Verification failed: {phase_id}"
    elif phase_status == "completed":
        header = f"Completed phase: {phase_id}"
    elif phase_status == "in-progress":
        header = f"Started phase: {phase_id}"
    elif phase_status == "blocked" or plan_status == "blocked":
        header = f"Blocked phase: {phase_id}"
    elif plan_status == "paused":
        header = f"Paused phase: {phase_id}"
    else:
        header = f"Plan advance: {phase_id}"

    lines = [header]
    message = state.get("message") or payload.get("message")
    if isinstance(message, str) and message:
        lines.append(message)

    if isinstance(plan_status, str) and plan_status:
        lines.append(f"Plan status: {plan_status}")
    if isinstance(phase_status, str) and phase_status:
        lines.append(f"Phase status: {phase_status}")

    next_action = _format_next_action(state.get("next_action"))
    if next_action:
        lines.append(f"Next action: {next_action}")

    plan_progress = _format_plan_progress(state.get("plan_progress"))
    if plan_progress:
        lines.append(f"Progress: {plan_progress}")

    phase_commit = state.get("phase_commit")
    if isinstance(phase_commit, str) and phase_commit:
        lines.append(f"Commit: {phase_commit}")

    sessions_used = state.get("sessions_used")
    if isinstance(sessions_used, int):
        lines.append(f"Sessions used: {sessions_used}")

    if isinstance(state.get("approval_required"), bool):
        lines.append("Approval required: " + ("yes" if state.get("approval_required") else "no"))

    approval_file = state.get("approval_file")
    if isinstance(approval_file, str) and approval_file:
        lines.append(f"Approval file: {approval_file}")

    expires = state.get("expires")
    if isinstance(expires, str) and expires:
        lines.append(f"Approval expires: {expires}")

    approval = state.get("approval") if isinstance(state.get("approval"), dict) else None
    if approval is None and isinstance(payload.get("approval"), dict):
        approval = payload["approval"]
    if isinstance(approval, dict):
        approval_status = approval.get("status")
        if isinstance(approval_status, str) and approval_status:
            lines.append(f"Approval status: {approval_status}")

    budget_line = _summary_budget_line(state.get("budget_status"))
    if budget_line:
        lines.append(f"Budget: {budget_line}")

    if isinstance(state.get("review_written"), bool):
        lines.append("Review written: " + ("yes" if state.get("review_written") else "no"))

    blocked_by = state.get("blocked_by")
    if isinstance(blocked_by, list) and blocked_by:
        lines.append("")
        lines.append("Blockers:")
        for blocker in blocked_by:
            if not isinstance(blocker, dict):
                continue
            reference = str(blocker.get("reference") or "unknown")
            extras: list[str] = []
            kind = blocker.get("kind")
            if isinstance(kind, str) and kind:
                extras.append(kind)
            status = blocker.get("status")
            if isinstance(status, str) and status:
                extras.append(f"status={status}")
            line = f"- {reference}"
            if extras:
                line += f" ({', '.join(extras)})"
            detail = blocker.get("detail")
            if isinstance(detail, str) and detail:
                line += f": {detail}"
            lines.append(line)

    if payload.get("status") == "verification_failed":
        _render_verification_results(payload, lines)

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


def _render_advance_errors(errors: list[str]) -> str:
    lines = ["Plan advance failed:"]
    if errors:
        lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines)


def _plans_root(content_root: Path) -> Path:
    return content_root / "memory" / "working" / "projects"


def _list_plan_files(content_root: Path, project_id: str | None = None) -> list[Path]:
    plans_root = _plans_root(content_root)
    if not plans_root.is_dir():
        return []

    project_glob = (
        f"{validate_slug(project_id, field_name='project_id')}/plans/*.yaml"
        if project_id is not None
        else "*/plans/*.yaml"
    )
    return [path for path in sorted(plans_root.glob(project_glob)) if path.is_file()]


def _find_plan_matches(content_root: Path, plan_id: str) -> list[tuple[Path, str]]:
    plan_slug = validate_slug(plan_id, field_name="plan_id")
    matches: list[tuple[Path, str]] = []
    for plan_file in _list_plan_files(content_root):
        if plan_file.stem != plan_slug:
            continue
        matches.append((plan_file, plan_file.parents[1].name))
    return matches


def _resolve_plan_path(
    content_root: Path,
    plan_id: str,
    project_id: str | None,
) -> tuple[Path, str]:
    plan_slug = validate_slug(plan_id, field_name="plan_id")
    if project_id is not None:
        project_slug = validate_slug(project_id, field_name="project_id")
        candidate = _plans_root(content_root) / project_slug / "plans" / f"{plan_slug}.yaml"
        if not candidate.is_file():
            raise NotFoundError(
                f"Plan not found: memory/working/projects/{project_slug}/plans/{plan_slug}.yaml"
            )
        return candidate, project_slug

    matches = _find_plan_matches(content_root, plan_slug)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        project_list = ", ".join(project for _path, project in matches)
        raise ValidationError(
            f"Plan '{plan_slug}' exists in multiple projects ({project_list}); specify --project."
        )
    raise NotFoundError(f"Plan not found: {plan_slug}")


def _sort_entries(entry: dict[str, Any]) -> tuple[int, str, str]:
    status = str(entry.get("status") or "")
    return (
        _STATUS_ORDER.get(status, len(_STATUS_ORDER)),
        str(entry.get("project_id") or ""),
        str(entry.get("plan_id") or ""),
    )


def _build_list_payload(
    content_root: Path, *, status: str | None, project_id: str | None
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    for plan_file in _list_plan_files(content_root, project_id=project_id):
        try:
            plan = load_plan(plan_file, content_root)
        except (NotFoundError, ValidationError) as exc:
            warnings.append(f"Skipped {plan_file.relative_to(content_root).as_posix()}: {exc}")
            continue
        if status is not None and plan.status != status:
            continue
        done, total = plan_progress(plan)
        entry: dict[str, Any] = {
            "plan_id": plan.id,
            "project_id": plan.project,
            "path": plan_file.relative_to(content_root).as_posix(),
            "title": plan_title(plan),
            "status": plan.status,
            "next_action": next_action(plan),
            "created": plan.created,
            "phase_progress": {"done": done, "total": total},
        }
        plan_budget = budget_status(plan)
        if plan_budget is not None:
            entry["budget_status"] = plan_budget
        entries.append(entry)
    entries.sort(key=_sort_entries)
    return {
        "status": status,
        "project_id": project_id,
        "count": len(entries),
        "results": entries,
        "warnings": warnings,
    }


def _summary_budget_line(raw_status: Any) -> str | None:
    if not isinstance(raw_status, dict):
        return None

    parts: list[str] = []
    sessions_used = raw_status.get("sessions_used")
    max_sessions = raw_status.get("max_sessions")
    if isinstance(sessions_used, int) and isinstance(max_sessions, int):
        parts.append(f"sessions: {sessions_used}/{max_sessions}")
    elif isinstance(sessions_used, int):
        parts.append(f"sessions used: {sessions_used}")

    deadline = raw_status.get("deadline")
    days_remaining = raw_status.get("days_remaining")
    if isinstance(deadline, str) and deadline:
        if isinstance(days_remaining, int):
            parts.append(f"deadline: {deadline} ({days_remaining} days)")
        else:
            parts.append(f"deadline: {deadline}")

    if raw_status.get("over_budget"):
        parts.append("over budget")

    return " | ".join(parts) or None


def _render_list(payload: dict[str, Any]) -> str:
    filters: list[str] = []
    if payload.get("status"):
        filters.append(f"status={payload['status']}")
    if payload.get("project_id"):
        filters.append(f"project={payload['project_id']}")

    header = "Plans"
    if filters:
        header = f"{header} ({', '.join(filters)})"

    entries = payload.get("results") or []
    if not entries:
        lines = [header, "", "No plans found."]
        warnings = payload.get("warnings") or []
        if warnings:
            lines.append("")
            lines.append(f"Skipped {len(warnings)} invalid plan file(s).")
        return "\n".join(lines)

    lines = [header, ""]
    for index, entry in enumerate(entries, start=1):
        lines.append(f"{index}. {entry['plan_id']} [{entry['status']}] {entry['title']}")
        progress = entry.get("phase_progress") or {}
        lines.append(
            f"   project: {entry['project_id']} | phases: {progress.get('done', 0)}/{progress.get('total', 0)}"
        )
        lines.append(f"   path: {entry['path']}")

        next_step = entry.get("next_action")
        if isinstance(next_step, dict):
            lines.append(f"   next: {next_step.get('id')} - {next_step.get('title')}")

        budget_line = _summary_budget_line(entry.get("budget_status"))
        if budget_line:
            lines.append(f"   budget: {budget_line}")

    warnings = payload.get("warnings") or []
    if warnings:
        lines.append("")
        lines.append(f"Skipped {len(warnings)} invalid plan file(s).")
        for warning in warnings[:3]:
            lines.append(f"- {warning}")
        remaining = len(warnings) - 3
        if remaining > 0:
            lines.append(f"- {remaining} more warning(s) omitted")

    return "\n".join(lines)


def _build_show_payload(
    content_root: Path,
    *,
    plan_id: str,
    project_id: str | None,
    phase_id: str | None,
) -> dict[str, Any]:
    plan_file, resolved_project_id = _resolve_plan_path(content_root, plan_id, project_id)
    plan = load_plan(plan_file, content_root)

    try:
        phase = resolve_phase(plan, phase_id)
    except NotFoundError:
        if phase_id is not None:
            raise
        done, total = plan_progress(plan)
        payload: dict[str, Any] = {
            "plan_id": plan.id,
            "project_id": resolved_project_id,
            "path": plan_file.relative_to(content_root).as_posix(),
            "title": plan_title(plan),
            "plan_status": plan.status,
            "purpose": plan.purpose.to_dict(),
            "progress": {
                "done": done,
                "total": total,
                "next_action": next_action(plan),
            },
            "phase": None,
            "message": "Plan has no actionable phase.",
        }
        plan_budget = budget_status(plan)
        if plan_budget is not None:
            payload["budget_status"] = plan_budget
        return payload

    payload = phase_payload(plan, phase, content_root)
    payload["path"] = plan_file.relative_to(content_root).as_posix()
    payload["title"] = plan_title(plan)
    return payload


def _render_section(lines: list[str], title: str, entries: list[str]) -> None:
    lines.append("")
    lines.append(f"{title}:")
    if not entries:
        lines.append("- none")
        return
    lines.extend(entries)


def _render_show(payload: dict[str, Any]) -> str:
    lines = [
        f"Plan: {payload['plan_id']} [{payload['plan_status']}]",
        f"Project: {payload['project_id']}",
    ]
    if payload.get("title"):
        lines.append(f"Plan title: {payload['title']}")
    if payload.get("path"):
        lines.append(f"Path: {payload['path']}")

    progress = payload.get("progress") or {}
    lines.append(f"Progress: {progress.get('done', 0)}/{progress.get('total', 0)} completed")
    next_step = progress.get("next_action")
    if isinstance(next_step, dict):
        lines.append(f"Next action: {next_step.get('id')} - {next_step.get('title')}")

    budget_line = _summary_budget_line(payload.get("budget_status"))
    if budget_line:
        lines.append(f"Budget: {budget_line}")

    purpose = payload.get("purpose") or {}
    if purpose.get("summary"):
        lines.append(f"Purpose: {purpose['summary']}")

    phase = payload.get("phase")
    if not isinstance(phase, dict):
        lines.append("")
        lines.append(str(payload.get("message") or "Plan has no actionable phase."))
        return "\n".join(lines)

    lines.append("")
    lines.append(f"Phase: {phase['id']} [{phase['status']}]")
    lines.append(f"Phase title: {phase['title']}")
    lines.append(f"Change class: {phase['change_class']}")
    lines.append("Approval required: " + ("yes" if phase.get("approval_required") else "no"))
    if phase.get("commit"):
        lines.append(f"Commit: {phase['commit']}")
    lines.append(f"Attempt: {phase.get('attempt_number', 1)}")

    source_lines: list[str] = []
    for source in phase.get("sources") or []:
        line = f"- [{source['type']}] {source['path']}: {source['intent']}"
        source_lines.append(line)
        if source.get("uri"):
            source_lines.append(f"  uri: {source['uri']}")
        if source.get("mcp_server") and source.get("mcp_tool"):
            source_lines.append(f"  mcp: {source['mcp_server']}::{source['mcp_tool']}")
    _render_section(lines, "Sources", source_lines)

    blocker_lines: list[str] = []
    for blocker in phase.get("blockers") or []:
        status = blocker.get("status") or "unknown"
        state = "satisfied" if blocker.get("satisfied") else "blocked"
        line = f"- {blocker['reference']} ({blocker['kind']}, {state}, status={status})"
        if blocker.get("detail"):
            line += f": {blocker['detail']}"
        blocker_lines.append(line)
        if blocker.get("commit"):
            blocker_lines.append(f"  commit: {blocker['commit']}")
    _render_section(lines, "Blockers", blocker_lines)

    postcondition_lines: list[str] = []
    for postcondition in phase.get("postconditions") or []:
        kind = postcondition.get("type") or "manual"
        line = f"- [{kind}] {postcondition['description']}"
        if postcondition.get("target"):
            line += f" -> {postcondition['target']}"
        postcondition_lines.append(line)
    _render_section(lines, "Postconditions", postcondition_lines)

    change_lines: list[str] = []
    for change in phase.get("changes") or []:
        change_lines.append(f"- {change['action']} {change['path']}: {change['description']}")
    _render_section(lines, "Changes", change_lines)

    failure_lines: list[str] = []
    for failure in phase.get("failures") or []:
        failure_lines.append(
            f"- attempt {failure.get('attempt', 1)} at {failure['timestamp']}: {failure['reason']}"
        )
    if failure_lines:
        _render_section(lines, "Failures", failure_lines)

    return "\n".join(lines)


def run_plan_list(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del repo_root

    payload = _build_list_payload(
        content_root,
        status=getattr(args, "status", None),
        project_id=getattr(args, "project", None),
    )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_render_list(payload))
    return 0


def run_plan_show(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del repo_root

    payload = _build_show_payload(
        content_root,
        plan_id=args.plan_id,
        project_id=getattr(args, "project", None),
        phase_id=getattr(args, "phase", None),
    )
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_render_show(payload))
    return 0


def run_plan_create(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    if getattr(args, "json_schema", False):
        print(json.dumps(_PLAN_CREATE_SCHEMA, indent=2))
        return 0

    try:
        input_text, _input_path = _read_plan_input(getattr(args, "input", None))
        create_request = _normalize_create_request(
            input_text,
            preview=bool(getattr(args, "preview", False)),
        )
        repo = GitRepo(repo_root, content_prefix=_content_prefix(repo_root, content_root))
        result = create_plan_write_result(
            repo=repo,
            root=content_root,
            plan_id=create_request["plan_id"],
            project_id=create_request["project_id"],
            purpose_summary=create_request["purpose_summary"],
            purpose_context=create_request["purpose_context"],
            phases=create_request["phases"],
            session_id=create_request["session_id"],
            questions=create_request["questions"],
            budget=create_request["budget"],
            status=create_request["status"],
            preview=bool(create_request["preview"]),
        )
    except (NotFoundError, ValidationError, ValueError) as exc:
        errors = validation_error_messages(exc) if isinstance(exc, ValidationError) else [str(exc)]
        if args.json:
            print(
                json.dumps(
                    {
                        "valid": False,
                        "errors": errors,
                        "schema_command": "engram plan create --json-schema",
                    },
                    indent=2,
                )
            )
        else:
            print(_render_create_errors(errors), file=sys.stderr)
        return 2

    if args.json:
        print(result.to_json())
    else:
        payload = result.to_dict()
        if create_request["preview"]:
            print(_render_create_preview(payload))
        else:
            print(_render_create_result(payload))
    return 0


def run_plan_advance(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    try:
        action, resolved_project_id, resolved_phase_id = _resolve_advance_target(
            content_root,
            plan_id=args.plan_id,
            project_id=getattr(args, "project", None),
            phase_id=getattr(args, "phase", None),
        )

        review_payload: dict[str, Any] | None = None
        if action == "start":
            if getattr(args, "commit_sha", None):
                raise ValidationError(
                    "--commit-sha is only valid when advancing an in-progress phase."
                )
            if getattr(args, "verify", False):
                raise ValidationError(
                    "--verify is only valid when completing an in-progress phase."
                )
            if getattr(args, "review_file", None):
                raise ValidationError(
                    "--review-file is only valid when completing an in-progress phase."
                )
        else:
            if not getattr(args, "commit_sha", None):
                raise ValidationError(
                    "--commit-sha is required when advancing an in-progress phase."
                )
            review_file = getattr(args, "review_file", None)
            if review_file:
                review_payload = _read_mapping_input(review_file, label="review")

        repo = GitRepo(repo_root, content_prefix=_content_prefix(repo_root, content_root))
        payload = execute_plan_action_result(
            repo=repo,
            root=content_root,
            plan_id=args.plan_id,
            project_id=resolved_project_id,
            phase_id=resolved_phase_id,
            action=action,
            session_id=args.session_id,
            commit_sha=getattr(args, "commit_sha", None),
            review=review_payload,
            verify=bool(getattr(args, "verify", False)),
            preview=bool(getattr(args, "preview", False)),
        )
    except (AlreadyDoneError, NotFoundError, ValidationError, ValueError) as exc:
        errors = validation_error_messages(exc) if isinstance(exc, ValidationError) else [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            print(_render_advance_errors(errors), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        if getattr(args, "preview", False) and isinstance(payload.get("preview"), dict):
            print(_render_advance_preview(payload))
        else:
            print(_render_advance_result(payload))
    return 0
