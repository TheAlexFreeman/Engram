"""Implementation of the ``engram aggregate`` command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..errors import ValidationError
from .maintenance import build_aggregate_preview


def register_aggregate(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "aggregate",
        help="Preview ACCESS aggregation without mutating the repository.",
        parents=parents or [],
    )
    parser.add_argument(
        "--namespace",
        help="Restrict the preview to a namespace or repo-relative memory path such as knowledge or memory/skills.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only. This is currently the only supported aggregate mode.",
    )
    parser.set_defaults(handler=run_aggregate)
    return parser


def _render_human(payload: dict[str, object]) -> str:
    filters: list[str] = []
    if payload.get("namespace"):
        filters.append(f"namespace={payload['namespace']}")

    header = "Aggregation preview"
    if filters:
        header += f" ({', '.join(filters)})"

    lines = [header, ""]
    lines.append(
        "Trigger: "
        + f"{payload.get('aggregation_trigger')} entries "
        + f"(near window {payload.get('near_trigger_window')})"
    )
    lines.append(f"Entries processed: {payload.get('entries_processed', 0)}")
    lines.append(f"Session groups processed: {payload.get('session_groups_processed', 0)}")
    if payload.get("legacy_fallback_entries"):
        lines.append(f"Legacy fallback entries: {payload['legacy_fallback_entries']}")

    reports = payload.get("reports")
    lines.append("")
    lines.append("Access logs:")
    if isinstance(reports, list) and reports:
        for report in reports:
            if not isinstance(report, dict):
                continue
            lines.append(
                "- "
                + f"{report.get('access_file')}: {report.get('entries')} entries "
                + f"[{report.get('status')}] remaining={report.get('remaining_to_trigger')}"
            )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Summary targets:")
    summary_targets = payload.get("summary_materialization_targets")
    if isinstance(summary_targets, list) and summary_targets:
        lines.extend(f"- {target}" for target in summary_targets)
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Archive targets:")
    archive_targets = payload.get("archive_targets")
    if isinstance(archive_targets, list) and archive_targets:
        lines.extend(f"- {target}" for target in archive_targets)
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Co-retrieval clusters:")
    clusters = payload.get("clusters")
    if isinstance(clusters, list) and clusters:
        for index, cluster in enumerate(clusters, start=1):
            if not isinstance(cluster, dict):
                continue
            raw_files = cluster.get("files")
            files = raw_files if isinstance(raw_files, list) else []
            lines.append(
                f"{index}. {' + '.join(str(file_path) for file_path in files)} "
                + f"({cluster.get('co_retrieval_count')} session groups)"
            )
    else:
        lines.append("- none")

    lines.append("")
    lines.append("Preview only: apply mode is not yet exposed in engram aggregate.")
    return "\n".join(lines)


def run_aggregate(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del repo_root

    try:
        payload = build_aggregate_preview(
            content_root,
            namespace=getattr(args, "namespace", None),
        )
    except ValidationError as exc:
        errors = [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            print("Aggregate preview failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_render_human(payload))
    return 0
