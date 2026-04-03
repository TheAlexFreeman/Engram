"""Implementation of the ``engram validate`` subcommand."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .validators import Finding, validate_repo


def register_validate(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "validate",
        help="Validate repository integrity.",
        parents=parents or [],
    )
    parser.set_defaults(handler=run_validate)
    return parser


def _exit_code(findings: list[Finding]) -> int:
    if any(item.severity == "error" for item in findings):
        return 2
    if findings:
        return 1
    return 0


def _render_human(findings: list[Finding]) -> str:
    if not findings:
        return "Validation passed with no findings."

    warnings = [item for item in findings if item.severity == "warning"]
    errors = [item for item in findings if item.severity == "error"]
    lines: list[str] = []

    if warnings:
        lines.append(f"Warnings ({len(warnings)}):")
        for item in warnings:
            prefix = f"{item.path}: " if item.path else ""
            lines.append(f"  - {prefix}{item.message}")

    if errors:
        if lines:
            lines.append("")
        lines.append(f"Errors ({len(errors)}):")
        for item in errors:
            prefix = f"{item.path}: " if item.path else ""
            lines.append(f"  - {prefix}{item.message}")

    if errors:
        lines.append("")
        lines.append(
            f"Validation failed with {len(errors)} error(s) and {len(warnings)} warning(s)."
        )
    else:
        lines.append("")
        lines.append(f"Validation completed with {len(warnings)} warning(s).")
    return "\n".join(lines)


def run_validate(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del content_root
    findings = validate_repo(repo_root)
    if args.json:
        print(json.dumps([item.to_dict() for item in findings], indent=2))
    else:
        print(_render_human(findings))
    return _exit_code(findings)
