"""Implementation of the ``engram review`` command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..errors import ValidationError
from .formatting import format_snippet
from .maintenance import apply_review_decisions, build_review_payload


def register_review(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    *,
    parents: list[argparse.ArgumentParser] | None = None,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(
        "review",
        help="Enumerate review, stale-content, and aggregation candidates from the terminal.",
        parents=parents or [],
    )
    parser.add_argument(
        "--decision",
        action="append",
        default=[],
        help="Capture a non-mutating verdict as <candidate-number|candidate-id>=approve|reject|defer. Repeat as needed.",
    )
    parser.add_argument(
        "--max-extract-words",
        type=int,
        default=40,
        help="Maximum number of body words to include for stale unverified candidates.",
    )
    parser.add_argument(
        "--no-near",
        action="store_false",
        dest="include_near",
        help="Hide near-threshold aggregation candidates and show only above-trigger items.",
    )
    parser.set_defaults(handler=run_review, include_near=True)
    return parser


def _render_human(payload: dict[str, object]) -> str:
    header = "Maintenance review"
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return header + "\n\nNo maintenance candidates found."

    counts_raw = payload.get("counts")
    counts = counts_raw if isinstance(counts_raw, dict) else {}
    lines = [header, ""]
    lines.append(
        "Candidate counts: "
        + " | ".join(
            [
                f"review_queue={counts.get('review_queue', 0)}",
                f"stale_unverified={counts.get('stale_unverified', 0)}",
                f"aggregation={counts.get('aggregation', 0)}",
            ]
        )
    )
    lines.append("")

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        number = candidate.get("number", "?")
        candidate_type = str(candidate.get("candidate_type") or "candidate").replace("_", "-")
        priority = candidate.get("priority") or "medium"
        lines.append(f"{number}. [{candidate_type}/{priority}] {candidate.get('title')}")
        lines.append(f"   id: {candidate.get('id')}")
        lines.append(f"   {candidate.get('summary')}")

        details = candidate.get("details")
        if isinstance(details, dict):
            if details.get("description"):
                lines.append(f"   {format_snippet(str(details['description']), limit=160)}")
            if details.get("extract"):
                lines.append(f"   extract: {details['extract']}")
            if details.get("status") in {"above", "near", "below"}:
                lines.append(
                    "   "
                    + f"entries: {details.get('entries')} | trigger: {details.get('trigger')} | "
                    + f"remaining: {details.get('remaining_to_trigger')}"
                )

        if candidate.get("decision"):
            lines.append(f"   decision: {candidate['decision']}")
        lines.append(f"   next: {candidate.get('action_hint')}")

    decisions = payload.get("decisions")
    if isinstance(decisions, list) and decisions:
        lines.append("")
        lines.append("Decision preview:")
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            lines.append(
                f"- {decision.get('number')} ({decision.get('id')}): {decision.get('decision')}"
            )

    return "\n".join(lines)


def run_review(args: argparse.Namespace, *, repo_root: Path, content_root: Path) -> int:
    del repo_root

    try:
        payload = build_review_payload(
            content_root,
            max_extract_words=int(getattr(args, "max_extract_words", 40) or 40),
            include_near=bool(getattr(args, "include_near", True)),
        )
        payload = apply_review_decisions(payload, list(getattr(args, "decision", []) or []))
    except ValidationError as exc:
        errors = [str(exc)]
        if args.json:
            print(json.dumps({"valid": False, "errors": errors}, indent=2))
        else:
            print("Maintenance review failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(_render_human(payload))
    return 0
