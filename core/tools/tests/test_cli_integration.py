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
            ".mypy_cache",
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


def _run_cli(
    repo_root: Path,
    *args: str,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["MEMORY_REPO_ROOT"] = str(repo_root)
    return subprocess.run(
        [sys.executable, "-m", "engram_mcp.agent_memory_mcp.cli.main", *args],
        cwd=str(REPO_ROOT),
        env=environment,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_warning_fixture(repo_root: Path) -> None:
    warning_file = repo_root / "core" / "memory" / "knowledge" / "cli-warning.md"
    warning_file.parent.mkdir(parents=True, exist_ok=True)
    warning_file.write_text("# Missing frontmatter warning fixture\n", encoding="utf-8")


def _seed_read_surface_fixture(repo_root: Path) -> None:
    knowledge_dir = repo_root / "core" / "memory" / "knowledge"
    feature_dir = knowledge_dir / "cli-integration"
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "SUMMARY.md").write_text(
        "---\ntrust: medium\nsource: manual\ncreated: 2026-04-03\n---\n\n"
        "CLI integration fixtures for recall and log.\n",
        encoding="utf-8",
    )
    (feature_dir / "sentinel.md").write_text(
        "---\ntrust: high\nsource: manual\ncreated: 2026-04-03\n---\n\n"
        "Sentinel recall integration phrase for the CLI expansion tests.\n",
        encoding="utf-8",
    )
    access_path = knowledge_dir / "ACCESS.jsonl"
    existing = access_path.read_text(encoding="utf-8") if access_path.exists() else ""
    extra_entry = json.dumps(
        {
            "file": "memory/knowledge/cli-integration/sentinel.md",
            "date": "2099-01-01",
            "task": "integration",
            "mode": "read",
            "helpfulness": 0.9,
            "note": "Seeded for CLI recall/log integration coverage.",
        }
    )
    access_path.write_text(existing + extra_entry + "\n", encoding="utf-8")


def _seed_add_fixture(repo_root: Path) -> None:
    summary_path = repo_root / "core" / "memory" / "knowledge" / "_unverified" / "SUMMARY.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        "# Unverified Knowledge\n\n<!-- section: cli-integration -->\n### Cli Integration\n\n---\n",
        encoding="utf-8",
    )


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
    _seed_read_surface_fixture(repo_copy)
    _seed_add_fixture(repo_copy)
    add_source = repo_copy / "cli-add-source.md"
    add_source.write_text("# CLI Add\n\nBody\n", encoding="utf-8")

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
    recall_run = _run_cli(
        repo_copy,
        "recall",
        "memory/knowledge/cli-integration/sentinel.md",
        "--json",
    )
    log_run = _run_cli(
        repo_copy,
        "log",
        "--namespace",
        "knowledge",
        "--since",
        "2099-01-01",
        "--json",
    )
    add_run = _run_cli(
        repo_copy,
        "add",
        "knowledge/cli-integration",
        str(add_source),
        "--session-id",
        "memory/activity/2026/04/03/chat-001",
        "--preview",
        "--json",
    )

    assert isinstance(json.loads(validate_run.stdout), list)
    assert "stage" in json.loads(status_run.stdout)
    assert "results" in json.loads(search_run.stdout)
    assert json.loads(recall_run.stdout)["kind"] == "file"
    assert (
        json.loads(log_run.stdout)["results"][0]["file"]
        == "memory/knowledge/cli-integration/sentinel.md"
    )
    assert (
        json.loads(add_run.stdout)["new_state"]["path"]
        == "memory/knowledge/_unverified/cli-integration/cli-add-source.md"
    )


def test_recall_and_log_human_output_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_read_surface_fixture(repo_copy)
    _seed_add_fixture(repo_copy)

    recall_run = _run_cli(repo_copy, "recall", "knowledge/cli-integration")
    log_run = _run_cli(repo_copy, "log", "--namespace", "knowledge", "--since", "2099-01-01")
    add_run = _run_cli(
        repo_copy,
        "add",
        "knowledge/cli-integration",
        "-",
        "--name",
        "cli-add-stdin",
        "--session-id",
        "memory/activity/2026/04/03/chat-001",
        input_text="# CLI Add Stdin\n\nBody\n",
    )

    assert recall_run.returncode == 0
    assert "Namespace: memory/knowledge/cli-integration" in recall_run.stdout
    assert "sentinel.md" in recall_run.stdout

    assert log_run.returncode == 0
    assert "memory/knowledge/cli-integration/sentinel.md" in log_run.stdout
    assert "2099-01-01" in log_run.stdout

    assert add_run.returncode == 0
    assert "Added: memory/knowledge/_unverified/cli-integration/cli-add-stdin.md" in add_run.stdout
