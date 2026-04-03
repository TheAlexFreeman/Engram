"""Implementation of the ``engram archive`` subcommand."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..errors import NotFoundError, ValidationError
from .formatting import render_governed_preview
from .governed_tools import invoke_semantic_tool


def register_archive(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "archive",
        help="Archive a knowledge file into memory/knowledge/_archive.",
        parents=parents or [],
    )
    parser.add_argument(
        "source_path",
        help="Repo-relative path under memory/knowledge/, such as memory/knowledge/topic/note.md.",
    )
    parser.add_argument(
        "--reason",
        help="Optional archival reason stored in the commit message.",
    )
    parser.add_argument(
        "--version-token",
        help="Optional optimistic-lock token for the source path.",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Render the governed preview without writing or committing.",
    )
    parser.set_defaults(handler=run_archive)
    return parser


def _render_result(payload: dict[str, Any], *, source_path: str) -> str:
    new_state = payload.get("new_state")
    state = new_state if isinstance(new_state, dict) else {}
    archive_path = state.get("archive_path")

    lines: list[str] = []
    if isinstance(archive_path, str) and archive_path:
        lines.append(f"Archived: {source_path} -> {archive_path}")

    commit_sha = payload.get("commit_sha")
    if isinstance(commit_sha, str) and commit_sha:
        lines.append(f"Commit: {commit_sha}")

    commit_message = payload.get("commit_message")
    if isinstance(commit_message, str) and commit_message:
        lines.append(f"Message: {commit_message}")

    warnings = payload.get("warnings")
    if isinstance(warnings, list) and warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in warnings)

    if not lines:
        return json.dumps(payload, indent=2, default=str)
    return "\n".join(lines)


def _render_errors(errors: list[str]) -> str:
    lines = ["Archival failed:"]
    lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines)


def run_archive(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del content_root

    try:
        payload = invoke_semantic_tool(
            repo_root,
            "memory_archive_knowledge",
            source_path=str(getattr(args, "source_path", "")),
            reason=getattr(args, "reason", None),
            version_token=getattr(args, "version_token", None),
            preview=bool(getattr(args, "preview", False)),
        )
    except (NotFoundError, ValidationError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            print(_render_errors(errors), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        if getattr(args, "preview", False) and isinstance(payload.get("preview"), dict):
            print(render_governed_preview(payload["preview"]))
        else:
            print(_render_result(payload, source_path=str(getattr(args, "source_path", ""))))
    return 0
