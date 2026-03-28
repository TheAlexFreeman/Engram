"""Shared fixtures for agent_memory_mcp tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a temporary git repo with minimal Engram memory structure."""
    core = tmp_path / "core"
    mem = core / "memory"
    gov = core / "governance"
    for d in [
        mem / "knowledge" / "_unverified",
        mem / "users",
        mem / "skills",
        mem / "activity",
        mem / "working" / "projects",
        mem / "working" / "notes",
        mem / "working" / "approvals" / "pending",
        mem / "working" / "approvals" / "resolved",
        gov,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    (mem / "HOME.md").write_text("# Home\n", encoding="utf-8")
    (mem / "working" / "CURRENT.md").write_text(
        "# Agent working notes\n\n## Active threads\n\n"
        "## Immediate next actions\n\n## Open questions\n\n## Drill-down refs\n",
        encoding="utf-8",
    )
    (core / "INIT.md").write_text("# Session Init\n", encoding="utf-8")

    subprocess.run(
        ["git", "init", "--initial-branch=core"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return tmp_path


@pytest.fixture
def content_root(tmp_repo: Path) -> Path:
    """Return the core/ directory of a temporary repo."""
    return tmp_repo / "core"
