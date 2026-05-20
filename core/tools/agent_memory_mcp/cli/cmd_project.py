"""Implementation of the ``engram project`` command group."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from ..errors import NotFoundError, ValidationError
from ..git_repo import GitRepo
from ..plan_utils import validation_error_messages
from ..tools.semantic.plan_tools import (
    add_project_questions_result,
    create_project_write_result,
    resolve_project_question_result,
)
from .formatting import render_governed_preview


def register_project(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "project",
        help="Manage Engram projects.",
    )
    parser.set_defaults(handler=_run_project_help, _project_parser=parser)

    project_subparsers = parser.add_subparsers(dest="project_command")

    create_parser = project_subparsers.add_parser(
        "create",
        help="Create a new project scaffold.",
        description=(
            "Create a new project with SUMMARY.md and navigator index.\n\n"
            "Accepts either inline arguments or a YAML file via stdin.\n\n"
            "Examples:\n"
            "  engram project create my-project --description 'Build the widget' --session-id memory/activity/2026/04/03/chat-001\n"
            "  cat project.yaml | engram project create -\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=parents or [],
    )
    create_parser.add_argument(
        "input",
        nargs="?",
        help=(
            "Project ID (for inline mode) or YAML file path (for file mode). "
            "Use '-' to read YAML from stdin."
        ),
    )
    create_parser.add_argument(
        "--description",
        help="Project description (inline mode).",
    )
    create_parser.add_argument(
        "--session-id",
        help="Canonical memory/activity/YYYY/MM/DD/chat-NNN session id.",
    )
    create_parser.add_argument(
        "--cognitive-mode",
        choices=["planning", "exploration", "execution"],
        default="planning",
        help="Project cognitive mode (default: planning).",
    )
    create_parser.add_argument(
        "--status",
        choices=["active", "draft", "paused"],
        default="active",
        help="Project status (default: active).",
    )
    create_parser.add_argument(
        "--question",
        action="append",
        dest="questions",
        help="Open question to seed in questions.md (repeatable).",
    )
    create_parser.add_argument(
        "--canonical-source",
        dest="canonical_source",
        default=None,
        help=(
            "Optional upstream pointer (repo URL, commit ref, path) for projects "
            "that snapshot external code. Rendered as the Canonical source subsection."
        ),
    )
    create_parser.add_argument(
        "--preview",
        action="store_true",
        help="Validate and render the governed preview without writing.",
    )
    create_parser.set_defaults(handler=run_project_create)

    add_q_parser = project_subparsers.add_parser(
        "add-question",
        help="Add open questions to a project.",
        parents=parents or [],
    )
    add_q_parser.add_argument("project_id", help="Project slug.")
    add_q_parser.add_argument(
        "--question",
        action="append",
        dest="questions",
        required=True,
        help="Question text (repeatable).",
    )
    add_q_parser.add_argument(
        "--session-id",
        required=True,
        help="Canonical session id.",
    )
    add_q_parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview without writing.",
    )
    add_q_parser.set_defaults(handler=run_project_add_question)

    resolve_q_parser = project_subparsers.add_parser(
        "resolve-question",
        help="Resolve an open question in a project.",
        parents=parents or [],
    )
    resolve_q_parser.add_argument("project_id", help="Project slug.")
    resolve_q_parser.add_argument("question_id", help="Question id (e.g. q-001).")
    resolve_q_parser.add_argument(
        "--resolution",
        required=True,
        help="Resolution summary.",
    )
    resolve_q_parser.add_argument(
        "--session-id",
        required=True,
        help="Canonical session id.",
    )
    resolve_q_parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview without writing.",
    )
    resolve_q_parser.set_defaults(handler=run_project_resolve_question)

    list_parser = project_subparsers.add_parser(
        "list",
        help="List projects with status summaries.",
        parents=parents or [],
    )
    list_parser.add_argument(
        "--status",
        choices=["active", "draft", "paused", "completed", "abandoned"],
        help="Filter by project status.",
    )
    list_parser.set_defaults(handler=run_project_list)

    return parser


def _run_project_help(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    content_root: Path,
) -> int:
    del repo_root, content_root
    parser = getattr(args, "_project_parser", None)
    if isinstance(parser, argparse.ArgumentParser):
        parser.print_help()
        return 0
    raise ValueError("project parser unavailable")


def _content_prefix(repo_root: Path, content_root: Path) -> str:
    try:
        return content_root.relative_to(repo_root).as_posix()
    except ValueError:
        return ""


def _parse_create_input(
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Parse project create input from either inline args or YAML file/stdin."""
    raw_input = getattr(args, "input", None)

    # YAML file/stdin mode
    if raw_input is not None and (raw_input == "-" or raw_input.endswith((".yaml", ".yml"))):
        if raw_input == "-":
            text = sys.stdin.read()
        else:
            text = Path(raw_input).read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("YAML input must be a mapping")
        canonical_source_raw = data.get("canonical_source")
        return {
            "project_id": str(data.get("project_id", "")),
            "description": str(data.get("description", "")),
            "session_id": str(data.get("session_id", "")),
            "cognitive_mode": str(data.get("cognitive_mode", "planning")),
            "status": str(data.get("status", "active")),
            "questions": data.get("questions"),
            "first_plan": data.get("first_plan"),
            "canonical_source": (
                str(canonical_source_raw) if canonical_source_raw is not None else None
            ),
            "preview": bool(data.get("preview", getattr(args, "preview", False))),
        }

    # Inline mode: input is the project_id
    project_id = raw_input or ""
    description = getattr(args, "description", None) or ""
    session_id = getattr(args, "session_id", None) or ""

    if not project_id:
        raise ValueError(
            "project_id is required. Usage: engram project create <project-id> "
            "--description '...' --session-id '...'"
        )
    if not description:
        raise ValueError("--description is required for inline mode")
    if not session_id:
        raise ValueError("--session-id is required for inline mode")

    return {
        "project_id": project_id,
        "description": description,
        "session_id": session_id,
        "cognitive_mode": getattr(args, "cognitive_mode", "planning"),
        "status": getattr(args, "status", "active"),
        "questions": getattr(args, "questions", None),
        "first_plan": None,
        "canonical_source": getattr(args, "canonical_source", None),
        "preview": bool(getattr(args, "preview", False)),
    }


def run_project_create(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    try:
        request = _parse_create_input(args)
        repo = GitRepo(repo_root, content_prefix=_content_prefix(repo_root, content_root))
        result = create_project_write_result(
            repo=repo,
            root=content_root,
            project_id=request["project_id"],
            description=request["description"],
            session_id=request["session_id"],
            cognitive_mode=request["cognitive_mode"],
            status=request["status"],
            questions=request["questions"],
            first_plan=request["first_plan"],
            canonical_source=request.get("canonical_source"),
            preview=request["preview"],
        )
    except (NotFoundError, ValidationError, ValueError) as exc:
        errors = validation_error_messages(exc) if isinstance(exc, ValidationError) else [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            for error in errors:
                print(f"  error: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(result.to_json())
    else:
        payload = result.to_dict()
        if request["preview"]:
            print(render_governed_preview(payload.get("preview", {})))
        else:
            project_id = payload.get("new_state", {}).get("project_id", "?")
            print(f"  Project created: {project_id}")
            if payload.get("commit_sha"):
                print(f"  Commit: {payload['commit_sha'][:12]}")
            first_plan = payload.get("new_state", {}).get("first_plan")
            if first_plan:
                print(f"  First plan: {first_plan.get('plan_path', '?')}")
    return 0


def run_project_add_question(
    args: argparse.Namespace, *, repo_root: Path, content_root: Path
) -> int:
    try:
        repo = GitRepo(repo_root, content_prefix=_content_prefix(repo_root, content_root))
        result = add_project_questions_result(
            repo=repo,
            root=content_root,
            project_id=args.project_id,
            questions=args.questions,
            session_id=args.session_id,
            preview=bool(getattr(args, "preview", False)),
        )
    except (NotFoundError, ValidationError, ValueError) as exc:
        errors = validation_error_messages(exc) if isinstance(exc, ValidationError) else [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            for error in errors:
                print(f"  error: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(result.to_json())
    else:
        payload = result.to_dict()
        if getattr(args, "preview", False):
            print(render_governed_preview(payload.get("preview", {})))
        else:
            q_ids = payload.get("new_state", {}).get("question_ids", [])
            print(f"  Added {len(q_ids)} question(s): {', '.join(q_ids)}")
            if payload.get("commit_sha"):
                print(f"  Commit: {payload['commit_sha'][:12]}")
    return 0


def run_project_resolve_question(
    args: argparse.Namespace, *, repo_root: Path, content_root: Path
) -> int:
    try:
        repo = GitRepo(repo_root, content_prefix=_content_prefix(repo_root, content_root))
        result = resolve_project_question_result(
            repo=repo,
            root=content_root,
            project_id=args.project_id,
            question_id=args.question_id,
            resolution=args.resolution,
            session_id=args.session_id,
            preview=bool(getattr(args, "preview", False)),
        )
    except (NotFoundError, ValidationError, ValueError) as exc:
        errors = validation_error_messages(exc) if isinstance(exc, ValidationError) else [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            for error in errors:
                print(f"  error: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(result.to_json())
    else:
        payload = result.to_dict()
        if getattr(args, "preview", False):
            print(render_governed_preview(payload.get("preview", {})))
        else:
            q_id = payload.get("new_state", {}).get("resolved_question", "?")
            remaining = payload.get("new_state", {}).get("open_questions", 0)
            print(f"  Resolved: {q_id}")
            print(f"  Open questions remaining: {remaining}")
            if payload.get("commit_sha"):
                print(f"  Commit: {payload['commit_sha'][:12]}")
    return 0


def run_project_list(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    from ..frontmatter_utils import collect_project_entries

    entries = collect_project_entries(content_root)
    status_filter = getattr(args, "status", None)
    if status_filter:
        entries = [e for e in entries if str(e.get("status")) == status_filter]

    if args.json:
        print(json.dumps(entries, indent=2, default=str))
        return 0

    if not entries:
        print("  No projects found.")
        return 0

    print(f"{'Project':<30} {'Status':<12} {'Mode':<14} {'Plans':<8} {'Last activity'}")
    print(f"{'─' * 30} {'─' * 12} {'─' * 14} {'─' * 8} {'─' * 14}")
    for entry in entries:
        print(
            f"{str(entry.get('project_id', '')):<30} "
            f"{str(entry.get('status', 'unknown')):<12} "
            f"{str(entry.get('cognitive_mode', 'unknown')):<14} "
            f"{entry.get('plans', 0)!s:<8} "
            f"{str(entry.get('last_activity', ''))}"
        )
    return 0
