from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _copy_repo_tree(tmp_path: Path) -> Path:
    clone_root = tmp_path / "repo-copy"
    shutil.copytree(
        REPO_ROOT,
        clone_root,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
            "agent_memory_mcp.egg-info",
            ".engram",
            "nul",
        ),
    )
    subprocess.run(["git", "init"], cwd=clone_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=clone_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=clone_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=clone_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "snapshot"],
        cwd=clone_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return clone_root


def _run_cli(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["MEMORY_REPO_ROOT"] = str(repo_root)
    return subprocess.run(
        [sys.executable, "-m", "engram_mcp.agent_memory_mcp.cli.main", *args],
        cwd=str(REPO_ROOT),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_warning_fixture(repo_root: Path) -> None:
    warning_file = repo_root / "core" / "memory" / "knowledge" / "cli-warning.md"
    warning_file.parent.mkdir(parents=True, exist_ok=True)
    warning_file.write_text("# Missing frontmatter warning fixture\n", encoding="utf-8")


def test_validate_status_and_search_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_warning_fixture(repo_copy)

    validate_run = _run_cli(repo_copy, "validate")
    assert validate_run.returncode == 1
    assert "missing YAML frontmatter" in validate_run.stdout

    status_run = _run_cli(repo_copy, "status")
    assert status_run.returncode == 0
    assert "Stage:" in status_run.stdout
    assert "Active plans:" in status_run.stdout

    search_run = _run_cli(
        repo_copy,
        "search",
        "warning",
        "--keyword",
        "--scope",
        "memory/knowledge",
    )
    assert search_run.returncode == 0


def test_json_subcommands_emit_parseable_output(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_warning_fixture(repo_copy)

    validate_run = _run_cli(repo_copy, "validate", "--json")
    status_run = _run_cli(repo_copy, "status", "--json")
    search_run = _run_cli(
        repo_copy,
        "search",
        "periodic",
        "--keyword",
        "--scope",
        "memory/knowledge",
        "--json",
    )

    assert isinstance(json.loads(validate_run.stdout), list)
    assert "stage" in json.loads(status_run.stdout)
    assert "results" in json.loads(search_run.stdout)
