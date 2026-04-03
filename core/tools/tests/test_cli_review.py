from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module(module_name: str) -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module(module_name)


cmd_review = _load_module("engram_mcp.agent_memory_mcp.cli.cmd_review")
cli_main = _load_module("engram_mcp.agent_memory_mcp.cli.main")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _review_args(
    *,
    json_output: bool = False,
    decisions: list[str] | None = None,
    max_extract_words: int = 40,
    include_near: bool = True,
):
    return type(
        "Args",
        (),
        {
            "json": json_output,
            "decision": decisions or [],
            "max_extract_words": max_extract_words,
            "include_near": include_near,
        },
    )()


def _seed_review_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"

    _write(
        content_root / "INIT.md",
        "# Session Init\n\n"
        "## Current active stage: Exploration\n\n"
        "## Last periodic review\n\n"
        "**Date:** 2026-03-19\n\n"
        "| Parameter | Active value | Stage |\n"
        "|---|---|---|\n"
        "| Aggregation trigger | 15 entries | Exploration |\n"
        "| Low-trust retirement threshold | 120 days | Exploration |\n",
    )
    _write(
        content_root / "governance" / "review-queue.md",
        "### [2026-04-03] Review architecture proposal\n"
        "**Type:** proposed\n"
        "**Description:** Assess the queued architecture change.\n"
        "**Status:** pending\n\n"
        "### [2026-04-01] Old queue item\n"
        "**Type:** proposed\n"
        "**Description:** Already resolved.\n"
        "**Status:** approved\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "_unverified" / "draft.md",
        "---\n"
        "source: external-research\n"
        "trust: low\n"
        "created: 2025-01-01\n"
        "origin_session: manual\n"
        "---\n\n"
        "Draft note for maintenance review preview coverage.\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "ACCESS.jsonl",
        "".join(
            json.dumps(
                {
                    "file": f"memory/knowledge/item-{index}.md",
                    "date": "2026-04-03",
                    "helpfulness": 0.7,
                    "session_id": f"memory/activity/2026/04/03/chat-{index:03d}",
                }
            )
            + "\n"
            for index in range(15)
        ),
    )
    _write(
        content_root / "memory" / "skills" / "ACCESS.jsonl",
        "".join(
            json.dumps(
                {
                    "file": f"memory/skills/item-{index}.md",
                    "date": "2026-04-03",
                    "helpfulness": 0.5,
                    "session_id": f"memory/activity/2026/04/03/chat-{index:03d}",
                }
            )
            + "\n"
            for index in range(12)
        ),
    )
    return repo_root, content_root


def test_review_handles_empty_candidate_sets(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"
    _write(content_root / "INIT.md", "# Session Init\n")

    exit_code = cmd_review.run_review(
        _review_args(),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No maintenance candidates found." in output


def test_review_human_output_numbers_candidates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_review_repo(tmp_path)

    exit_code = cmd_review.run_review(
        _review_args(max_extract_words=5),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Candidate counts: review_queue=1 | stale_unverified=1 | aggregation=2" in output
    assert "1. [review-queue/high] Review architecture proposal" in output
    assert "2. [stale-unverified/high] memory/knowledge/_unverified/draft.md" in output
    assert "extract: Draft note for maintenance review" in output
    assert "3. [aggregation/high] memory/knowledge" in output


def test_review_json_captures_scripted_decisions(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_review_repo(tmp_path)

    exit_code = cmd_review.run_review(
        _review_args(json_output=True, decisions=["1=approve", "2=defer"]),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["resolved_count"] == 2
    assert payload["unresolved_count"] == 2
    assert payload["decisions"] == [
        {
            "number": 1,
            "id": "review-queue:2026-04-03:review-architecture-proposal",
            "decision": "approve",
            "candidate_type": "review_queue",
        },
        {
            "number": 2,
            "id": "unverified:memory/knowledge/_unverified/draft.md",
            "decision": "defer",
            "candidate_type": "stale_unverified",
        },
    ]
    assert payload["candidates"][0]["decision"] == "approve"
    assert payload["candidates"][1]["decision"] == "defer"


def test_review_command_is_registered_in_main_parser() -> None:
    parser = cli_main.build_parser()
    args = parser.parse_args(["review", "--decision", "1=approve", "--json"])

    assert args.command == "review"
    assert args.decision == ["1=approve"]
    assert args.json is True
    assert args.handler is cmd_review.run_review
