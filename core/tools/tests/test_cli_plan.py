from __future__ import annotations

import importlib
import json
import sys
import textwrap
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_cmd_plan() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("engram_mcp.agent_memory_mcp.cli.cmd_plan")


cmd_plan = _load_cmd_plan()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _list_args(
    *,
    json_output: bool = False,
    status: str | None = None,
    project: str | None = None,
):
    return type(
        "Args",
        (),
        {
            "json": json_output,
            "status": status,
            "project": project,
        },
    )()


def _show_args(
    plan_id: str,
    *,
    json_output: bool = False,
    project: str | None = None,
    phase: str | None = None,
):
    return type(
        "Args",
        (),
        {
            "json": json_output,
            "plan_id": plan_id,
            "project": project,
            "phase": phase,
        },
    )()


def _seed_plan_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    content_root = repo_root / "core"

    _write(content_root / "context.md", "Plan context fixture.\n")

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
            status: active
            sessions_used: 1
            budget:
              max_sessions: 4
              advisory: true
            purpose:
              summary: Track CLI plan work
              context: Ship read surfaces before create and advance.
              questions: []
            work:
              phases:
                - id: phase-a
                  title: Complete schema groundwork
                  status: completed
                  commit: abc1234
                  blockers: []
                  sources:
                    - path: core/context.md
                      type: internal
                      intent: Confirm the existing command shape.
                  postconditions:
                    - description: Schema foundations are complete.
                  requires_approval: false
                  changes:
                    - path: HUMANS/docs/MCP.md
                      action: update
                      description: Document the schema surface.
                  failures: []
                - id: phase-b
                  title: Ship read surfaces
                  status: pending
                  blockers: []
                  sources:
                    - path: core/context.md
                      type: internal
                      intent: Reuse the current plan context.
                  postconditions:
                    - description: Read surfaces render current phase data.
                      type: check
                      target: memory/working/projects/example/plans/tracked-plan.yaml
                  requires_approval: false
                  changes:
                    - path: core/tools/agent_memory_mcp/cli/cmd_plan.py
                      action: create
                      description: Add plan list and show commands.
                  failures: []
            review: null
            """
        ),
    )
    _write(
        content_root
        / "memory"
        / "working"
        / "projects"
        / "secondary"
        / "plans"
        / "draft-plan.yaml",
        textwrap.dedent(
            """\
            id: draft-plan
            project: secondary
            created: '2026-04-03'
            origin_session: memory/activity/2026/04/03/chat-002
            status: draft
            sessions_used: 0
            purpose:
              summary: Draft future work
              context: Reserved for a later CLI slice.
              questions: []
            work:
              phases:
                - id: phase-a
                  title: Hold future work
                  status: pending
                  blockers: []
                  sources:
                    - path: core/context.md
                      type: internal
                      intent: Keep a valid internal source.
                  postconditions:
                    - description: Future work is specified.
                  requires_approval: false
                  changes:
                    - path: HUMANS/docs/CLI.md
                      action: update
                      description: Document the future command.
                  failures: []
            review: null
            """
        ),
    )
    return repo_root, content_root


def test_plan_list_human_output_shows_active_and_draft_entries(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_plan_repo(tmp_path)

    exit_code = cmd_plan.run_plan_list(
        _list_args(),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "tracked-plan [active]" in output
    assert "draft-plan [draft]" in output
    assert "next: phase-b - Ship read surfaces" in output


def test_plan_list_json_output_is_structured(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_plan_repo(tmp_path)

    exit_code = cmd_plan.run_plan_list(
        _list_args(json_output=True, status="active"),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["count"] == 1
    assert payload["results"][0]["plan_id"] == "tracked-plan"
    assert payload["results"][0]["next_action"]["id"] == "phase-b"


def test_plan_show_human_output_renders_current_phase_details(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_plan_repo(tmp_path)

    exit_code = cmd_plan.run_plan_show(
        _show_args("tracked-plan", project="example"),
        repo_root=repo_root,
        content_root=content_root,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Plan: tracked-plan [active]" in output
    assert "Phase: phase-b [pending]" in output
    assert "Sources:" in output
    assert "core/context.md" in output
    assert "Blockers:" in output
    assert "phase-a (implicit, satisfied" in output
    assert "Postconditions:" in output
    assert "Changes:" in output


def test_plan_show_json_output_is_structured(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_plan_repo(tmp_path)

    exit_code = cmd_plan.run_plan_show(
        _show_args("tracked-plan", json_output=True, project="example"),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["path"] == "memory/working/projects/example/plans/tracked-plan.yaml"
    assert payload["phase"]["id"] == "phase-b"
    assert payload["progress"]["done"] == 1
    assert payload["phase"]["changes"][0]["action"] == "create"


def test_plan_list_skips_invalid_plan_files_with_warning(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo_root, content_root = _seed_plan_repo(tmp_path)
    _write(
        content_root / "memory" / "working" / "projects" / "broken" / "plans" / "broken-plan.yaml",
        textwrap.dedent(
            """\
            id: broken-plan
            project: broken
            created: '2026-04-03'
            origin_session: memory/activity/2026/04/03/chat-009
            status: active
            purpose:
              summary: Broken plan
              context: This plan intentionally uses an invalid phase status.
              questions: []
            work:
              phases:
                - id: phase-a
                  title: Broken phase
                  status: complete
                  blockers: []
                  sources:
                    - path: core/context.md
                      type: internal
                      intent: Keep path validation satisfied.
                  postconditions:
                    - description: Never reached.
                  requires_approval: false
                  changes:
                    - path: HUMANS/docs/CLI.md
                      action: update
                      description: Broken test fixture.
                  failures: []
            review: null
            """
        ),
    )

    exit_code = cmd_plan.run_plan_list(
        _list_args(json_output=True),
        repo_root=repo_root,
        content_root=content_root,
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["count"] == 2
    assert payload["warnings"]
    assert "broken-plan.yaml" in payload["warnings"][0]
