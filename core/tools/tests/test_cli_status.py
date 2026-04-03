from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_cmd_status() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("engram_mcp.agent_memory_mcp.cli.cmd_status")


cmd_status = _load_cmd_status()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _args(*, json_output: bool = False):
    return type("Args", (), {"json": json_output})()


def _seed_status_repo(tmp_path: Path, *, access_entries: int = 3) -> tuple[Path, Path]:
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
        "### [2026-04-01] Review the queue\n**Status:** pending\n**Type:** governance\n",
    )
    _write(
        content_root / "memory" / "knowledge" / "_unverified" / "draft.md",
        "---\n"
        "source: external-research\n"
        "trust: low\n"
        "created: 2025-01-01\n"
        "origin_session: manual\n"
        "---\n\n"
        "Draft note\n",
    )
    _write(
        content_root
        / "memory"
        / "working"
        / "projects"
        / "cli-expansion"
        / "plans"
        / "cli-v0.yaml",
        "id: cli-v0\n"
        "project: cli-expansion\n"
        "status: active\n"
        "purpose:\n"
        "  summary: Implement the first three engram CLI commands.\n",
    )
    access_lines = [
        json.dumps({"file": "memory/knowledge/example.md"}) for _ in range(access_entries)
    ]
    _write(
        content_root / "memory" / "knowledge" / "ACCESS.jsonl",
        "\n".join(access_lines) + ("\n" if access_lines else ""),
    )
    return repo_root, content_root


def test_status_reports_expected_sections(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_status_repo(tmp_path)

    exit_code = cmd_status.run_status(_args(), repo_root=repo_root, content_root=content_root)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Stage: Exploration" in output
    assert "Pending reviews: 1" in output
    assert "Active plans: 1" in output
    assert "cli-expansion/cli-v0" in output


def test_status_handles_missing_access_files(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_status_repo(tmp_path, access_entries=0)
    (content_root / "memory" / "knowledge" / "ACCESS.jsonl").unlink()

    exit_code = cmd_status.run_status(_args(), repo_root=repo_root, content_root=content_root)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No ACCESS.jsonl files found." in output


def test_status_json_output_structure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_status_repo(tmp_path)

    exit_code = cmd_status.run_status(
        _args(json_output=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["stage"] == "Exploration"
    assert payload["pending_reviews"]["count"] == 1
    assert payload["active_plans"]["count"] == 1


def test_status_warns_when_access_count_exceeds_trigger(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_status_repo(tmp_path, access_entries=16)

    exit_code = cmd_status.run_status(_args(), repo_root=repo_root, content_root=content_root)
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Warnings:" in output
    assert "exceeds the aggregation trigger 15" in output
