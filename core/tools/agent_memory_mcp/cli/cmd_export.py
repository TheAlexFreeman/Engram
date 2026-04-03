"""Implementation of the ``engram export`` subcommand."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..errors import ValidationError
from ..portability import (
    build_portability_bundle,
    render_json_bundle,
    render_markdown_bundle,
    write_tar_bundle,
    write_text_bundle,
)


def register_export(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "export",
        help="Create a portability bundle for backup, migration, or onboarding seeding.",
        parents=parents or [],
    )
    parser.add_argument(
        "--format",
        choices=("md", "json", "tar"),
        default="md",
        help="Bundle format to emit (default: md).",
    )
    parser.add_argument(
        "--output",
        help="Optional output file. Omit to stream md/json bundle content to stdout. Tar requires an output path.",
    )
    parser.set_defaults(handler=run_export)
    return parser


def _render_result(payload: dict[str, Any]) -> str:
    lines = [f"Exported bundle: {payload.get('output_path') or 'stdout'}"]
    if payload.get("format"):
        lines.append(f"Format: {payload['format']}")
    if payload.get("file_count") is not None:
        lines.append(f"Files: {payload['file_count']}")
    if payload.get("total_bytes") is not None:
        lines.append(f"Bytes: {payload['total_bytes']}")
    included_targets = payload.get("included_targets")
    if isinstance(included_targets, list) and included_targets:
        lines.append(f"Targets: {', '.join(str(item) for item in included_targets)}")
    return "\n".join(lines)


def run_export(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del content_root

    try:
        bundle = build_portability_bundle(repo_root)
        bundle_format = str(getattr(args, "format", "md"))
        output = getattr(args, "output", None)

        if bundle_format == "json":
            bundle_text = render_json_bundle(bundle)
        elif bundle_format == "md":
            bundle_text = render_markdown_bundle(bundle)
        else:
            bundle_text = None

        if output:
            output_path = Path(str(output)).expanduser().resolve()
            if bundle_format == "tar":
                payload = write_tar_bundle(bundle, output_path)
            else:
                payload = write_text_bundle(
                    str(bundle_text), output_path, bundle_format=bundle_format
                )
            if args.json:
                print(json.dumps(payload, indent=2, default=str))
            else:
                print(_render_result(payload))
            return 0

        if bundle_format == "tar":
            raise ValidationError("--output is required when --format tar is selected.")

        print(str(bundle_text), end="")
        return 0
    except ValidationError as exc:
        errors = [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            print("Export failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 2
