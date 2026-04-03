"""Implementation of the ``engram promote`` subcommand."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..errors import NotFoundError, ValidationError
from .formatting import render_governed_preview
from .governed_tools import invoke_semantic_tool


def register_promote(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "promote",
        help="Promote an _unverified knowledge file into verified memory/knowledge.",
        parents=parents or [],
    )
    parser.add_argument(
        "source_path",
        help="Repo-relative path under memory/knowledge/_unverified/, such as memory/knowledge/_unverified/topic/note.md.",
    )
    parser.add_argument(
        "--trust",
        choices=("medium", "high"),
        default="high",
        help="Trust level to assign after promotion (default: high).",
    )
    parser.add_argument(
        "--target-path",
        help="Optional explicit verified destination path under memory/knowledge/.",
    )
    parser.add_argument(
        "--summary-entry",
        help="Optional explicit summary entry for memory/knowledge/SUMMARY.md.",
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
    parser.set_defaults(handler=run_promote)
    return parser


def _render_result(payload: dict[str, Any], *, source_path: str) -> str:
    new_state = payload.get("new_state")
    state = new_state if isinstance(new_state, dict) else {}
    target_path = state.get("new_path")
    trust = state.get("trust")

    lines: list[str] = []
    if isinstance(target_path, str) and target_path:
        lines.append(f"Promoted: {source_path} -> {target_path}")
    if isinstance(trust, str) and trust:
        lines.append(f"Trust: {trust}")

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
    lines = ["Promotion failed:"]
    lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines)


def run_promote(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del content_root

    try:
        payload = invoke_semantic_tool(
            repo_root,
            "memory_promote_knowledge",
            source_path=str(getattr(args, "source_path", "")),
            trust_level=str(getattr(args, "trust", "high")),
            target_path=getattr(args, "target_path", None),
            summary_entry=getattr(args, "summary_entry", None),
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
