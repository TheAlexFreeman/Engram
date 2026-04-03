"""Implementation of the ``engram import`` subcommand."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..errors import ValidationError
from ..portability import apply_import_bundle, preview_import_bundle
from .formatting import render_governed_preview


def register_import(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "import",
        help="Validate or apply a portability bundle created by engram export.",
        parents=parents or [],
    )
    parser.add_argument(
        "source",
        help="Path to a markdown, json, or tar portability bundle.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the validated bundle to the current repo. Preview is the default mode.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow apply mode to overwrite existing files that differ from the bundle.",
    )
    parser.set_defaults(handler=run_import)
    return parser


def _render_result(payload: dict[str, Any]) -> str:
    new_state = payload.get("new_state")
    state = new_state if isinstance(new_state, dict) else {}

    lines = [f"Imported bundle: {state.get('source') or 'unknown source'}"]
    if state.get("format"):
        lines.append(f"Format: {state['format']}")
    if state.get("file_count") is not None:
        lines.append(f"Bundle files: {state['file_count']}")

    created = state.get("created_paths")
    if isinstance(created, list):
        lines.append(f"Created: {len(created)}")

    updated = state.get("updated_paths")
    if isinstance(updated, list):
        lines.append(f"Updated: {len(updated)}")

    unchanged = state.get("unchanged_paths")
    if isinstance(unchanged, list):
        lines.append(f"Unchanged: {len(unchanged)}")

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

    return "\n".join(lines)


def run_import(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    try:
        source_path = Path(str(getattr(args, "source", ""))).expanduser().resolve()
        if getattr(args, "apply", False):
            payload = apply_import_bundle(
                repo_root,
                content_root,
                source_path,
                overwrite=bool(getattr(args, "overwrite", False)),
            )
        else:
            payload = preview_import_bundle(
                repo_root,
                content_root,
                source_path,
                overwrite=bool(getattr(args, "overwrite", False)),
            )
    except ValidationError as exc:
        errors = [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            print("Import failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        if not getattr(args, "apply", False) and isinstance(payload.get("preview"), dict):
            print(render_governed_preview(payload["preview"]))
        else:
            print(_render_result(payload))
    return 0
