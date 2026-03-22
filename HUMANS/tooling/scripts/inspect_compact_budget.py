#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import validate_memory_repo as validator


def build_report(root: Path) -> dict[str, Any]:
    result = validator.ValidationResult()
    measurements = validator.iter_compact_startup_measurements(root, result)
    files: list[dict[str, Any]] = []
    total_tokens = 0

    for rel_path, tokens, _ in measurements:
        target = validator.COMPACT_RETURNING_TARGETS.get(rel_path)
        total_tokens += tokens
        files.append(
            {
                "path": rel_path,
                "tokens": tokens,
                "target": target,
                "delta": None if target is None else tokens - target,
                "over_target": False if target is None else tokens > target,
            }
        )

    remaining = validator.COMPACT_RETURNING_BUDGET - total_tokens
    if total_tokens > validator.COMPACT_RETURNING_BUDGET:
        status = "error"
    elif total_tokens > validator.COMPACT_RETURNING_BUDGET - validator.COMPACT_RETURNING_HEADROOM:
        status = "tight"
    else:
        status = "ok"

    return {
        "root": str(root),
        "status": status,
        "budget_limit": validator.COMPACT_RETURNING_BUDGET,
        "headroom_target": validator.COMPACT_RETURNING_HEADROOM,
        "total_tokens": total_tokens,
        "remaining_tokens": remaining,
        "files": files,
        "warnings": result.warnings,
        "errors": result.errors,
    }


def render_human_report(report: dict[str, Any]) -> str:
    lines = [
        "Compact returning budget inspection",
        f"status: {report['status']}",
        f"total: {report['total_tokens']} / {report['budget_limit']} tokens",
        f"remaining: {report['remaining_tokens']} tokens",
        f"headroom target: {report['headroom_target']} tokens",
        "",
        "files:",
    ]

    for entry in report["files"]:
        target = entry["target"]
        if target is None:
            target_str = "n/a"
            delta_str = "n/a"
        else:
            delta_str = f"{entry['delta']:+d}"
            target_str = str(target)
        lines.append(
            f"- {entry['path']}: {entry['tokens']} tokens (target {target_str}, delta {delta_str})"
        )

    if report["warnings"]:
        lines.extend(["", "warnings:"])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    if report["errors"]:
        lines.extend(["", "errors:"])
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect compact startup budget usage.")
    parser.add_argument(
        "root", nargs="?", default=None, help="Repo root (defaults to current repo)."
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Emit machine-readable JSON."
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[3]
    report = build_report(root)
    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        print(render_human_report(report))
    return 1 if report["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
