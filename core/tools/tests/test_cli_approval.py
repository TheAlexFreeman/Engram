from __future__ import annotations

import importlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType

import pytest
import yaml  # type: ignore[import-untyped]

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


def _resolve_args(
    approval_id: str,
    *,
    json_output: bool = False,
    resolution: str = "approve",
    comment: str | None = None,
    preview: bool = False,
):
    return type(
        "Args",
        (),
        {
            "json": json_output,
            "approval_id": approval_id,
            "resolution": resolution,
            "comment": comment,
            "preview": preview,
        },
    )()


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
    _write(
        content_root / "memory" / "working" / "projects" / "SUMMARY.md",
        "# Projects\n\nFixture navigator.\n",
    )
    _write(
        content_root / "memory" / "working" / "projects" / "example" / "SUMMARY.md",
        textwrap.dedent(
            """\
            ---
            active_plans: 1
            cognitive_mode: execution
            created: 2026-04-03
            current_focus: Exercise approval CLI fixtures.
            last_activity: '2026-04-03'
            open_questions: 0
            origin_session: memory/activity/2026/04/03/chat-001
            plans: 1
            source: agent-generated
            status: active
            trust: medium
            type: project
            ---

            # Project: Example

            Approval fixture project summary.
            """
        ),
    )
    _write(
        content_root
        / "memory"
        / "working"
        / "projects"
        / "example"
        / "plans"
        / "tracked-plan.yaml",
        textwrap.dedent(
            """\
            id: tracked-plan
            project: example
            created: '2026-04-03'
            origin_session: memory/activity/2026/04/03/chat-001
            status: paused
            sessions_used: 1
            purpose:
              summary: Exercise terminal approval resolution
              context: Keep the approval CLI fixture realistic.
              questions: []
            work:
              phases:
                - id: phase-a
                  title: Approval-gated phase
                  status: pending
                  blockers: []
                  sources:
                    - path: core/context.md
                      type: internal
                      intent: Review approval CLI context.
                  postconditions:
                    - description: Approval can be resolved from the terminal.
                  requires_approval: true
                  changes:
                    - path: HUMANS/docs/CLI.md
                      action: update
                      description: Document terminal approval flows.
                  failures: []
            review: null
            """
        ),
    )
    _init_git_repo(repo_root)
    return repo_root, content_root


def _plan_file(content_root: Path) -> Path:
    return (
        content_root / "memory" / "working" / "projects" / "example" / "plans" / "tracked-plan.yaml"
    )


def _approval_pending_file(content_root: Path) -> Path:
    return (
        content_root / "memory" / "working" / "approvals" / "pending" / "tracked-plan--phase-a.yaml"
    )


def _approval_resolved_file(content_root: Path) -> Path:
    return (
        content_root
        / "memory"
        / "working"
        / "approvals"
        / "resolved"
        / "tracked-plan--phase-a.yaml"
    )


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


def test_approval_resolve_preview_shows_governed_preview_without_mutating_repo(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_approval_repo(tmp_path)
    _save_approval(content_root)
    _commit_all(repo_root, "seed approval fixture")

    exit_code = cmd_approval.run_approval_resolve(
        _resolve_args("tracked-plan--phase-a", resolution="approve", preview=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Mode: preview" in output
    assert "Resolve approval tracked-plan--phase-a with decision approve." in output
    assert "Commit: [plan] Approve tracked-plan:phase-a" in output

    plan_body = yaml.safe_load(_plan_file(content_root).read_text(encoding="utf-8"))
    assert plan_body["status"] == "paused"
    assert _approval_pending_file(content_root).exists()
    assert not _approval_resolved_file(content_root).exists()
    assert _git_status(repo_root) == ""


def test_approval_resolve_approve_updates_plan_and_moves_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_approval_repo(tmp_path)
    _save_approval(content_root)
    _commit_all(repo_root, "seed approval fixture")

    exit_code = cmd_approval.run_approval_resolve(
        _resolve_args(
            "tracked-plan--phase-a",
            json_output=True,
            resolution="approve",
            comment="Looks good.",
        ),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)
    state = payload["new_state"]

    assert exit_code == 0
    assert state["approval_id"] == "tracked-plan--phase-a"
    assert state["status"] == "approved"
    assert state["plan_status"] == "active"
    assert state["phase_id"] == "phase-a"
    assert state["project_id"] == "example"
    assert state["comment"] == "Looks good."
    assert payload["commit_sha"]

    plan_body = yaml.safe_load(_plan_file(content_root).read_text(encoding="utf-8"))
    approval_body = yaml.safe_load(
        _approval_resolved_file(content_root).read_text(encoding="utf-8")
    )

    assert plan_body["status"] == "active"
    assert not _approval_pending_file(content_root).exists()
    assert approval_body["status"] == "approved"
    assert approval_body["resolution"] == "approve"
    assert approval_body["comment"] == "Looks good."
    assert _git_status(repo_root) == ""


def test_approval_resolve_reject_blocks_plan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_approval_repo(tmp_path)
    _save_approval(content_root)
    _commit_all(repo_root, "seed approval fixture")

    exit_code = cmd_approval.run_approval_resolve(
        _resolve_args(
            "tracked-plan--phase-a",
            json_output=True,
            resolution="reject",
            comment="Needs more detail.",
        ),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)
    state = payload["new_state"]

    assert exit_code == 0
    assert state["status"] == "rejected"
    assert state["plan_status"] == "blocked"
    assert state["message"].startswith("Approval rejected")

    plan_body = yaml.safe_load(_plan_file(content_root).read_text(encoding="utf-8"))
    approval_body = yaml.safe_load(
        _approval_resolved_file(content_root).read_text(encoding="utf-8")
    )

    assert plan_body["status"] == "blocked"
    assert approval_body["status"] == "rejected"
    assert approval_body["resolution"] == "reject"
    assert approval_body["comment"] == "Needs more detail."
    assert _git_status(repo_root) == ""


def test_approval_resolve_expired_request_reports_clear_error(
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

    exit_code = cmd_approval.run_approval_resolve(
        _resolve_args("tracked-plan--phase-a", resolution="approve"),
        repo_root=repo_root,
        content_root=content_root,
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Approval resolution failed:" in captured.err
    assert "has expired and can no longer be resolved" in captured.err
    assert _approval_pending_file(content_root).exists()
    assert not _approval_resolved_file(content_root).exists()
    assert _git_status(repo_root) == ""


def test_approval_resolve_rejects_malformed_approval_id(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_approval_repo(tmp_path)
    _save_approval(content_root)
    _commit_all(repo_root, "seed approval fixture")

    exit_code = cmd_approval.run_approval_resolve(
        _resolve_args("tracked-plan-phase-a", resolution="approve"),
        repo_root=repo_root,
        content_root=content_root,
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Approval resolution failed:" in captured.err
    assert "approval id must be '<plan-id>--<phase-id>'" in captured.err
    assert _approval_pending_file(content_root).exists()
    assert _git_status(repo_root) == ""


def test_approval_resolve_rejects_invalid_resolution(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_approval_repo(tmp_path)
    _save_approval(content_root)
    _commit_all(repo_root, "seed approval fixture")

    exit_code = cmd_approval.run_approval_resolve(
        _resolve_args("tracked-plan--phase-a", resolution="hold"),
        repo_root=repo_root,
        content_root=content_root,
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Approval resolution failed:" in captured.err
    assert "resolution must be one of" in captured.err
    assert _approval_pending_file(content_root).exists()
    assert not _approval_resolved_file(content_root).exists()
    assert _git_status(repo_root) == ""
