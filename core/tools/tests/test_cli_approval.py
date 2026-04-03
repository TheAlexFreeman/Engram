from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module(module_name: str) -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module(module_name)


cmd_approval = _load_module("engram_mcp.agent_memory_mcp.cli.cmd_approval")
plan_approvals = _load_module("engram_mcp.agent_memory_mcp.plan_approvals")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _list_args(*, json_output: bool = False):
    return type("Args", (), {"json": json_output})()


def _init_git_repo(repo_root: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "snapshot"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _commit_all(repo_root: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_status(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _seed_approval_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"
    _write(content_root / "context.md", "Approval context fixture.\n")
    _init_git_repo(repo_root)
    return repo_root, content_root


def _save_approval(
    content_root: Path,
    *,
    plan_id: str = "tracked-plan",
    phase_id: str = "phase-a",
    project_id: str = "example",
    requested: str = "2026-04-03T09:00:00Z",
    expires: str = "2099-04-10T09:00:00Z",
    additional_context: str | None = None,
) -> None:
    context: dict[str, object] = {
        "phase_title": "Approval-gated phase",
        "phase_summary": "Phase requires approval before execution.",
        "sources": ["core/context.md"],
        "changes": [
            {
                "path": "HUMANS/docs/CLI.md",
                "action": "update",
                "description": "Document approval listing.",
            }
        ],
        "change_class": "proposed",
    }
    if additional_context is not None:
        context["additional_context"] = additional_context

    approval = plan_approvals.ApprovalDocument(
        plan_id=plan_id,
        phase_id=phase_id,
        project_id=project_id,
        status="pending",
        requested=requested,
        expires=expires,
        context=context,
    )
    plan_approvals.save_approval(content_root, approval)


def test_approval_list_empty_human_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_approval_repo(tmp_path)

    exit_code = cmd_approval.run_approval_list(
        _list_args(),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Approval queue" in output
    assert "No pending approvals." in output


def test_approval_list_human_output_shows_pending_context(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_approval_repo(tmp_path)
    _save_approval(
        content_root,
        additional_context="Needs a human sign-off before protected writes.",
    )
    _commit_all(repo_root, "seed approval fixture")

    exit_code = cmd_approval.run_approval_list(
        _list_args(),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "tracked-plan--phase-a [pending] Approval-gated phase" in output
    assert "scope: example / tracked-plan / phase-a" in output
    assert "sources: 1 | changes: 1" in output
    assert "Needs a human sign-off" in output


def test_approval_list_json_output_is_structured(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_approval_repo(tmp_path)
    _save_approval(content_root)
    _commit_all(repo_root, "seed approval fixture")

    exit_code = cmd_approval.run_approval_list(
        _list_args(json_output=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == "tracked-plan--phase-a"
    assert payload["results"][0]["status"] == "pending"
    assert payload["results"][0]["scope"]["project_id"] == "example"
    assert (
        payload["results"][0]["path"]
        == "memory/working/approvals/pending/tracked-plan--phase-a.yaml"
    )


def test_approval_list_marks_expired_without_mutating_repo(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_approval_repo(tmp_path)
    _save_approval(
        content_root,
        requested="2026-03-01T09:00:00Z",
        expires="2026-03-02T09:00:00Z",
    )
    _commit_all(repo_root, "seed expired approval fixture")

    exit_code = cmd_approval.run_approval_list(
        _list_args(json_output=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["results"][0]["status"] == "expired"
    assert (
        content_root / "memory" / "working" / "approvals" / "pending" / "tracked-plan--phase-a.yaml"
    ).exists()
    assert not (
        content_root
        / "memory"
        / "working"
        / "approvals"
        / "resolved"
        / "tracked-plan--phase-a.yaml"
    ).exists()
    assert _git_status(repo_root) == ""
