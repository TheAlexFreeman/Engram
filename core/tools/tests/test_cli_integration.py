from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml  # type: ignore[import-untyped]

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
    # On Windows the pytest tmp prefix + the deeply nested IN/ fixture tree can
    # exceed the default MSYS / Win32 MAX_PATH (260 chars), which makes
    # `git add -A` fail with "fatal: adding files failed". Enable long-path
    # support on the cloned repo so subsequent add/commit calls work everywhere.
    subprocess.run(
        ["git", "config", "core.longpaths", "true"],
        cwd=clone_root,
        check=True,
        capture_output=True,
        text=True,
    )
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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _commit_with_date(repo_root: Path, message: str, when: str) -> None:
    environment = dict(os.environ)
    environment["GIT_AUTHOR_DATE"] = when
    environment["GIT_COMMITTER_DATE"] = when
    subprocess.run(
        ["git", "add", "-A"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
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


def _seed_plan_fixture(repo_root: Path) -> None:
    plan_path = (
        repo_root
        / "core"
        / "memory"
        / "working"
        / "projects"
        / "example"
        / "plans"
        / "tracked-plan.yaml"
    )
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    (repo_root / "core" / "memory" / "working" / "projects" / "SUMMARY.md").write_text(
        "# Projects\n\nIntegration fixture navigator.\n",
        encoding="utf-8",
    )
    (repo_root / "core" / "memory" / "working" / "projects" / "example" / "SUMMARY.md").write_text(
        textwrap.dedent(
            """\
            ---
            active_plans: 1
            cognitive_mode: execution
            created: 2026-04-03
            current_focus: Exercise plan CLI integration fixtures.
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

            Integration fixture project summary.
            """
        ),
        encoding="utf-8",
    )
    (repo_root / "core" / "context.md").write_text(
        "CLI plan integration fixture\n", encoding="utf-8"
    )
    plan_path.write_text(
        "id: tracked-plan\n"
        "project: example\n"
        "created: '2026-04-03'\n"
        "origin_session: memory/activity/2026/04/03/chat-001\n"
        "status: active\n"
        "sessions_used: 1\n"
        "purpose:\n"
        "  summary: Track CLI plan work\n"
        "  context: Exercise the plan CLI group.\n"
        "  questions: []\n"
        "work:\n"
        "  phases:\n"
        "    - id: phase-a\n"
        "      title: Complete groundwork\n"
        "      status: completed\n"
        "      commit: abc1234\n"
        "      blockers: []\n"
        "      sources:\n"
        "        - path: core/context.md\n"
        "          type: internal\n"
        "          intent: Review plan CLI context.\n"
        "      postconditions:\n"
        "        - description: Groundwork exists.\n"
        "      requires_approval: false\n"
        "      changes:\n"
        "        - path: HUMANS/docs/CLI.md\n"
        "          action: update\n"
        "          description: Note groundwork.\n"
        "      failures: []\n"
        "    - id: phase-b\n"
        "      title: Ship read surfaces\n"
        "      status: pending\n"
        "      blockers: []\n"
        "      sources:\n"
        "        - path: core/context.md\n"
        "          type: internal\n"
        "          intent: Reuse context.\n"
        "      postconditions:\n"
        "        - description: Read surfaces render terminal output.\n"
        "          type: check\n"
        "          target: memory/working/projects/example/plans/tracked-plan.yaml\n"
        "      requires_approval: false\n"
        "      changes:\n"
        "        - path: core/tools/agent_memory_mcp/cli/cmd_plan.py\n"
        "          action: create\n"
        "          description: Add plan read surfaces.\n"
        "      failures: []\n"
        "review: null\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "seed plan fixture"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_approval_fixture(repo_root: Path) -> None:
    approval_path = (
        repo_root
        / "core"
        / "memory"
        / "working"
        / "approvals"
        / "pending"
        / "tracked-plan--phase-a.yaml"
    )
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(
        "plan_id: tracked-plan\n"
        "phase_id: phase-a\n"
        "project_id: example\n"
        "status: pending\n"
        "requested: 2026-04-03T09:00:00Z\n"
        "expires: 2099-04-10T09:00:00Z\n"
        "context:\n"
        "  phase_title: Approval-gated phase\n"
        "  phase_summary: Phase requires approval before execution.\n"
        "  change_class: proposed\n"
        "  sources:\n"
        "    - core/context.md\n"
        "  changes:\n"
        "    - path: HUMANS/docs/CLI.md\n"
        "      action: update\n"
        "      description: Document approval listing.\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "seed approval fixture"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_approval_resolution_fixture(repo_root: Path) -> None:
    context_path = repo_root / "core" / "context.md"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text("Approval resolution integration fixture\n", encoding="utf-8")

    projects_summary = repo_root / "core" / "memory" / "working" / "projects" / "SUMMARY.md"
    projects_summary.parent.mkdir(parents=True, exist_ok=True)
    projects_summary.write_text("# Projects\n\nIntegration fixture navigator.\n", encoding="utf-8")

    project_summary = (
        repo_root / "core" / "memory" / "working" / "projects" / "example" / "SUMMARY.md"
    )
    project_summary.parent.mkdir(parents=True, exist_ok=True)
    project_summary.write_text(
        textwrap.dedent(
            """\
            ---
            active_plans: 1
            cognitive_mode: execution
            created: 2026-04-03
            current_focus: Exercise approval CLI integration fixtures.
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
        encoding="utf-8",
    )

    plan_path = (
        repo_root
        / "core"
        / "memory"
        / "working"
        / "projects"
        / "example"
        / "plans"
        / "tracked-plan.yaml"
    )
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
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
        encoding="utf-8",
    )

    approval_path = (
        repo_root
        / "core"
        / "memory"
        / "working"
        / "approvals"
        / "pending"
        / "tracked-plan--phase-a.yaml"
    )
    approval_path.parent.mkdir(parents=True, exist_ok=True)
    approval_path.write_text(
        "plan_id: tracked-plan\n"
        "phase_id: phase-a\n"
        "project_id: example\n"
        "status: pending\n"
        "requested: 2026-04-03T09:00:00Z\n"
        "expires: 2099-04-10T09:00:00Z\n"
        "context:\n"
        "  phase_title: Approval-gated phase\n"
        "  phase_summary: Phase requires approval before execution.\n"
        "  change_class: proposed\n"
        "  sources:\n"
        "    - core/context.md\n"
        "  changes:\n"
        "    - path: HUMANS/docs/CLI.md\n"
        "      action: update\n"
        "      description: Document approval resolution.\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "seed approval resolution fixture"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_trace_fixture(repo_root: Path) -> None:
    trace_path = (
        repo_root / "core" / "memory" / "activity" / "2026" / "04" / "03" / "chat-001.traces.jsonl"
    )
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "session_id": "memory/activity/2026/04/03/chat-001",
                        "timestamp": "2026-04-03T12:00:00Z",
                        "span_type": "plan_action",
                        "name": "approval follow-through",
                        "status": "error",
                        "duration_ms": 25,
                        "span_id": "span-001",
                        "metadata": {"plan_id": "tracked-plan", "phase_id": "phase-a"},
                        "cost": {"tokens_in": 11, "tokens_out": 7},
                    }
                ),
                json.dumps(
                    {
                        "session_id": "memory/activity/2026/04/03/chat-001",
                        "timestamp": "2026-04-03T11:30:00Z",
                        "span_type": "retrieval",
                        "name": "background lookup",
                        "status": "ok",
                        "duration_ms": 10,
                        "span_id": "span-000",
                        "metadata": {"plan_id": "other-plan"},
                        "cost": {"tokens_in": 3, "tokens_out": 2},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "seed trace fixture"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_diff_fixture(repo_root: Path) -> None:
    knowledge_file = repo_root / "core" / "memory" / "knowledge" / "cli-diff.md"
    knowledge_file.parent.mkdir(parents=True, exist_ok=True)
    knowledge_file.write_text(
        "---\n"
        "trust: low\n"
        "created: 2099-01-01\n"
        "origin_session: manual\n"
        "source: manual\n"
        "---\n\n"
        "CLI diff integration fixture.\n",
        encoding="utf-8",
    )
    _commit_with_date(repo_root, "seed diff fixture", "2099-01-01T09:00:00Z")

    knowledge_file.write_text(
        "---\n"
        "trust: medium\n"
        "created: 2099-01-01\n"
        "last_verified: 2099-01-02\n"
        "origin_session: manual\n"
        "source: manual\n"
        "---\n\n"
        "CLI diff integration fixture, verified.\n",
        encoding="utf-8",
    )
    _commit_with_date(repo_root, "update diff fixture trust", "2099-01-02T11:30:00Z")


def _seed_maintenance_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "core" / "INIT.md",
        "# Session Init\n\n"
        "## Current active stage: Exploration\n\n"
        "## Last periodic review\n\n"
        "**Date:** 2026-03-19\n\n"
        "| Parameter | Active value | Stage |\n"
        "|---|---|---|\n"
        "| Aggregation trigger | 3 entries | Exploration |\n"
        "| Low-trust retirement threshold | 120 days | Exploration |\n",
    )
    _write(
        repo_root / "core" / "governance" / "review-queue.md",
        "### [2026-04-03] Review maintenance preview workflow\n"
        "**Type:** proposed\n"
        "**Description:** Confirm the terminal maintenance preview commands.\n"
        "**Status:** pending\n",
    )
    _write(
        repo_root / "core" / "memory" / "knowledge" / "_unverified" / "draft.md",
        "---\n"
        "source: external-research\n"
        "trust: low\n"
        "created: 2025-01-01\n"
        "origin_session: manual\n"
        "---\n\n"
        "Draft note for review preview coverage.\n",
    )
    _write(repo_root / "core" / "memory" / "knowledge" / "topic.md", "# Topic\n")
    _write(repo_root / "core" / "memory" / "working" / "projects" / "demo.md", "# Demo\n")
    _write(
        repo_root / "core" / "memory" / "skills" / "session-start" / "SKILL.md", "# Session Start\n"
    )
    _write(
        repo_root / "core" / "memory" / "knowledge" / "SUMMARY.md",
        "# Knowledge\n\n## Usage patterns\n\n_No access data yet._\n",
    )
    _write(
        repo_root / "core" / "memory" / "working" / "projects" / "SUMMARY.md",
        "# Plans\n\n## Usage patterns\n\n_No access data yet._\n",
    )
    _write(
        repo_root / "core" / "memory" / "skills" / "SUMMARY.md",
        "# Skills\n\n## Usage patterns\n\n_No access data yet._\n",
    )
    _write(
        repo_root / "core" / "memory" / "knowledge" / "ACCESS.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "date": "2099-01-03",
                        "session_id": "memory/activity/2099/01/03/chat-001",
                        "file": "memory/knowledge/topic.md",
                        "helpfulness": 0.8,
                    }
                ),
                json.dumps(
                    {
                        "date": "2099-01-04",
                        "session_id": "memory/activity/2099/01/04/chat-001",
                        "file": "memory/knowledge/topic.md",
                        "helpfulness": 0.8,
                    }
                ),
                json.dumps(
                    {
                        "date": "2099-01-05",
                        "session_id": "memory/activity/2099/01/05/chat-001",
                        "file": "memory/knowledge/topic.md",
                        "helpfulness": 0.8,
                    }
                ),
            ]
        )
        + "\n",
    )
    _write(
        repo_root / "core" / "memory" / "working" / "projects" / "ACCESS.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "date": "2099-01-03",
                        "session_id": "memory/activity/2099/01/03/chat-001",
                        "file": "memory/working/projects/demo.md",
                        "helpfulness": 0.7,
                    }
                ),
                json.dumps(
                    {
                        "date": "2099-01-04",
                        "session_id": "memory/activity/2099/01/04/chat-001",
                        "file": "memory/working/projects/demo.md",
                        "helpfulness": 0.7,
                    }
                ),
                json.dumps(
                    {
                        "date": "2099-01-05",
                        "session_id": "memory/activity/2099/01/05/chat-001",
                        "file": "memory/working/projects/demo.md",
                        "helpfulness": 0.7,
                    }
                ),
            ]
        )
        + "\n",
    )
    _write(
        repo_root / "core" / "memory" / "skills" / "ACCESS.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "date": "2099-01-03",
                        "session_id": "memory/activity/2099/01/03/chat-001",
                        "file": "memory/skills/session-start/SKILL.md",
                        "helpfulness": 0.9,
                    }
                ),
                json.dumps(
                    {
                        "date": "2099-01-04",
                        "session_id": "memory/activity/2099/01/04/chat-001",
                        "file": "memory/skills/session-start/SKILL.md",
                        "helpfulness": 0.9,
                    }
                ),
                json.dumps(
                    {
                        "date": "2099-01-05",
                        "session_id": "memory/activity/2099/01/05/chat-001",
                        "file": "memory/skills/session-start/SKILL.md",
                        "helpfulness": 0.9,
                    }
                ),
            ]
        )
        + "\n",
    )
    _commit_with_date(repo_root, "seed maintenance fixture", "2099-01-05T12:00:00Z")


def _seed_lifecycle_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "core" / "memory" / "knowledge" / "_unverified" / "lifecycle" / "promote-me.md",
        "---\ncreated: 2099-01-06\nsource: test\ntrust: low\n---\n\n# Promote Me\n",
    )
    _write(
        repo_root / "core" / "memory" / "knowledge" / "lifecycle" / "archive-me.md",
        "---\n"
        "created: 2099-01-06\n"
        "source: test\n"
        "trust: high\n"
        "last_verified: 2099-01-06\n"
        "---\n\n"
        "# Archive Me\n",
    )
    _write(
        repo_root / "core" / "memory" / "knowledge" / "_unverified" / "SUMMARY.md",
        "# Unverified Knowledge\n\n"
        "<!-- section: lifecycle -->\n"
        "### Lifecycle\n"
        "- **[promote-me.md](memory/knowledge/_unverified/lifecycle/promote-me.md)** — Promote Me\n\n"
        "---\n",
    )
    _write(
        repo_root / "core" / "memory" / "knowledge" / "SUMMARY.md",
        "# Knowledge\n\n"
        "<!-- section: lifecycle -->\n"
        "### Lifecycle\n"
        "- **[archive-me.md](memory/knowledge/lifecycle/archive-me.md)** — Archive Me\n\n"
        "---\n",
    )
    _commit_with_date(repo_root, "seed lifecycle fixture", "2099-01-06T15:00:00Z")


def _seed_export_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "core" / "memory" / "knowledge" / "portable.md",
        "---\ntrust: high\nsource: manual\ncreated: 2099-01-07\n---\n\n# Portable\n",
    )
    _commit_with_date(repo_root, "seed export fixture", "2099-01-07T09:00:00Z")


def _seed_import_conflict_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "core" / "memory" / "knowledge" / "portable.md",
        "---\ntrust: low\nsource: manual\ncreated: 2099-01-07\n---\n\n# Different Portable\n",
    )
    _commit_with_date(repo_root, "seed import conflict fixture", "2099-01-07T10:00:00Z")


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
    _seed_diff_fixture(repo_copy)
    _seed_maintenance_fixture(repo_copy)
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
    diff_run = _run_cli(
        repo_copy,
        "diff",
        "--since",
        "2099-01-01",
        "--namespace",
        "knowledge",
        "--json",
    )
    review_run = _run_cli(repo_copy, "review", "--json")
    aggregate_run = _run_cli(repo_copy, "aggregate", "--namespace", "knowledge", "--json")
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
    log_payload = json.loads(log_run.stdout)
    assert log_payload["results"]
    assert all(entry["file"].startswith("memory/knowledge/") for entry in log_payload["results"])
    diff_payload = json.loads(diff_run.stdout)
    assert diff_payload["commits"]
    assert all(
        file_entry["path"].startswith("memory/knowledge/")
        for commit in diff_payload["commits"]
        for file_entry in commit["files"]
    )
    review_payload = json.loads(review_run.stdout)
    assert review_payload["counts"]["review_queue"] == 1
    assert review_payload["counts"]["stale_unverified"] == 1
    assert review_payload["counts"]["aggregation"] >= 3
    assert json.loads(aggregate_run.stdout)["entries_processed"] == 3
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


def test_plan_list_and_show_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_plan_fixture(repo_copy)

    list_run = _run_cli(
        repo_copy,
        "plan",
        "list",
        "--status",
        "active",
        "--project",
        "example",
        "--json",
    )
    show_run = _run_cli(repo_copy, "plan", "show", "tracked-plan", "--project", "example")

    assert list_run.returncode == 0
    assert json.loads(list_run.stdout)["results"][0]["plan_id"] == "tracked-plan"

    assert show_run.returncode == 0
    assert "Plan: tracked-plan [active]" in show_run.stdout
    assert "Phase: phase-b [pending]" in show_run.stdout


def test_plan_create_preview_and_help_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_plan_fixture(repo_copy)
    create_input = (
        "plan_id: preview-plan\n"
        "project_id: example\n"
        "purpose_summary: Preview the terminal create flow\n"
        "purpose_context: Exercise stdin preview integration.\n"
        "session_id: memory/activity/2026/04/03/chat-010\n"
        "phases:\n"
        "  - id: preview-phase\n"
        "    title: Preview the plan\n"
        "    changes:\n"
        "      - path: HUMANS/docs/CLI.md\n"
        "        action: update\n"
        "        description: Mention preview integration.\n"
    )

    preview_run = _run_cli(
        repo_copy,
        "plan",
        "create",
        "--preview",
        "--json",
        input_text=create_input,
    )
    help_run = _run_cli(repo_copy, "plan", "create", "--help")

    assert preview_run.returncode == 0
    assert (
        json.loads(preview_run.stdout)["new_state"]["plan_path"]
        == "memory/working/projects/example/plans/preview-plan.yaml"
    )

    assert help_run.returncode == 0
    assert "Schema-backed help for plan creation." in help_run.stdout
    assert "--json-schema" in help_run.stdout


def test_plan_create_apply_and_schema_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_plan_fixture(repo_copy)
    create_input_path = tmp_path / "apply-plan.yaml"
    create_input_path.write_text(
        "plan_id: integrated-plan\n"
        "project_id: example\n"
        "purpose_summary: Create a plan through the CLI entrypoint\n"
        "purpose_context: Exercise the real apply path from the terminal CLI.\n"
        "session_id: memory/activity/2026/04/03/chat-011\n"
        "phases:\n"
        "  - id: integrated-phase\n"
        "    title: Create the plan\n"
        "    changes:\n"
        "      - path: HUMANS/docs/CLI.md\n"
        "        action: update\n"
        "        description: Verify terminal plan creation.\n",
        encoding="utf-8",
    )

    create_run = _run_cli(repo_copy, "plan", "create", str(create_input_path), "--json")
    schema_run = _run_cli(repo_copy, "plan", "create", "--json-schema")

    assert create_run.returncode == 0
    create_payload = json.loads(create_run.stdout)
    assert (
        create_payload["new_state"]["plan_path"]
        == "memory/working/projects/example/plans/integrated-plan.yaml"
    )
    assert create_payload["commit_sha"]
    assert (
        repo_copy
        / "core"
        / "memory"
        / "working"
        / "projects"
        / "example"
        / "plans"
        / "integrated-plan.yaml"
    ).exists()

    status_run = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_run.stdout.strip() == ""

    assert schema_run.returncode == 0
    schema_payload = json.loads(schema_run.stdout)
    assert schema_payload["tool_name"] == "memory_plan_create"
    assert "phases" in schema_payload["properties"]


def test_plan_advance_start_and_complete_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_plan_fixture(repo_copy)
    review_file = tmp_path / "advance-review.yaml"
    review_file.write_text(
        "outcome: completed\n"
        "purpose_assessment: The terminal advance flow completed the plan successfully.\n"
        "follow_up: cli-v3-approval-trace\n",
        encoding="utf-8",
    )

    start_run = _run_cli(
        repo_copy,
        "plan",
        "advance",
        "tracked-plan",
        "--project",
        "example",
        "--session-id",
        "memory/activity/2026/04/03/chat-012",
        "--json",
    )
    assert start_run.returncode == 0
    start_payload = json.loads(start_run.stdout)
    assert start_payload["new_state"]["phase_status"] == "in-progress"
    assert start_payload["new_state"]["phase_id"] == "phase-b"

    complete_run = _run_cli(
        repo_copy,
        "plan",
        "advance",
        "tracked-plan",
        "--project",
        "example",
        "--session-id",
        "memory/activity/2026/04/03/chat-012",
        "--commit-sha",
        "abc1234",
        "--verify",
        "--review-file",
        str(review_file),
        "--json",
    )

    assert complete_run.returncode == 0
    complete_payload = json.loads(complete_run.stdout)
    assert complete_payload["new_state"]["phase_status"] == "completed"
    assert complete_payload["new_state"]["plan_status"] == "completed"
    assert complete_payload["new_state"]["review_written"] is True
    assert complete_payload["commit_sha"]

    plan_body = yaml.safe_load(
        (
            repo_copy
            / "core"
            / "memory"
            / "working"
            / "projects"
            / "example"
            / "plans"
            / "tracked-plan.yaml"
        ).read_text(encoding="utf-8")
    )
    assert plan_body["status"] == "completed"
    assert plan_body["review"]["purpose_assessment"] == (
        "The terminal advance flow completed the plan successfully."
    )

    status_run = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_run.stdout.strip() == ""


def test_approval_list_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_approval_fixture(repo_copy)

    list_run = _run_cli(repo_copy, "approval", "list", "--json")

    assert list_run.returncode == 0
    payload = json.loads(list_run.stdout)
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == "tracked-plan--phase-a"
    assert payload["results"][0]["status"] == "pending"

    status_run = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_run.stdout.strip() == ""


def test_approval_resolve_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_approval_resolution_fixture(repo_copy)

    resolve_run = _run_cli(
        repo_copy,
        "approval",
        "resolve",
        "tracked-plan--phase-a",
        "approve",
        "--comment",
        "Ship it.",
        "--json",
    )

    assert resolve_run.returncode == 0
    payload = json.loads(resolve_run.stdout)
    assert payload["new_state"]["approval_id"] == "tracked-plan--phase-a"
    assert payload["new_state"]["status"] == "approved"
    assert payload["new_state"]["plan_status"] == "active"
    assert payload["new_state"]["comment"] == "Ship it."
    assert payload["commit_sha"]

    resolved_approval = (
        repo_copy
        / "core"
        / "memory"
        / "working"
        / "approvals"
        / "resolved"
        / "tracked-plan--phase-a.yaml"
    )
    pending_approval = (
        repo_copy
        / "core"
        / "memory"
        / "working"
        / "approvals"
        / "pending"
        / "tracked-plan--phase-a.yaml"
    )
    assert resolved_approval.exists()
    assert not pending_approval.exists()

    plan_body = yaml.safe_load(
        (
            repo_copy
            / "core"
            / "memory"
            / "working"
            / "projects"
            / "example"
            / "plans"
            / "tracked-plan.yaml"
        ).read_text(encoding="utf-8")
    )
    assert plan_body["status"] == "active"

    status_run = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_run.stdout.strip() == ""


def test_trace_json_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_trace_fixture(repo_copy)

    trace_run = _run_cli(
        repo_copy,
        "trace",
        "--date-from",
        "2026-04-03",
        "--plan",
        "tracked-plan",
        "--status",
        "error",
        "--json",
    )

    assert trace_run.returncode == 0
    payload = json.loads(trace_run.stdout)
    assert payload["total_matched"] == 1
    assert payload["spans"][0]["name"] == "approval follow-through"
    assert payload["aggregates"]["total_duration_ms"] == 25
    assert payload["aggregates"]["total_cost"] == {"tokens_in": 11, "tokens_out": 7}
    assert payload["aggregates"]["by_status"] == {"error": 1}

    status_run = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_run.stdout.strip() == ""


def test_diff_human_output_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_diff_fixture(repo_copy)

    diff_run = _run_cli(
        repo_copy,
        "diff",
        "--since",
        "2099-01-01",
        "--namespace",
        "knowledge",
    )

    assert diff_run.returncode == 0
    assert "Diff query (namespace=knowledge, since=2099-01-01)" in diff_run.stdout
    assert "memory/knowledge/cli-diff.md [modified/knowledge]" in diff_run.stdout
    assert "frontmatter changed; trust: low -> medium" in diff_run.stdout

    status_run = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_run.stdout.strip() == ""


def test_review_and_aggregate_human_output_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_maintenance_fixture(repo_copy)

    review_run = _run_cli(repo_copy, "review", "--decision", "1=approve")
    aggregate_run = _run_cli(repo_copy, "aggregate", "--namespace", "knowledge")

    assert review_run.returncode == 0
    assert "Maintenance review" in review_run.stdout
    assert "Decision preview:" in review_run.stdout
    assert (
        "1 (review-queue:2026-04-03:review-maintenance-preview-workflow): approve"
        in review_run.stdout
    )

    assert aggregate_run.returncode == 0
    assert "Aggregation preview (namespace=knowledge)" in aggregate_run.stdout
    assert "Entries processed: 3" in aggregate_run.stdout
    assert (
        "Preview only: apply mode is not yet exposed in engram aggregate." in aggregate_run.stdout
    )

    status_run = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_run.stdout.strip() == ""


def test_promote_and_archive_json_preview_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_lifecycle_fixture(repo_copy)

    promote_run = _run_cli(
        repo_copy,
        "promote",
        "memory/knowledge/_unverified/lifecycle/promote-me.md",
        "--trust",
        "medium",
        "--preview",
        "--json",
    )
    archive_run = _run_cli(
        repo_copy,
        "archive",
        "memory/knowledge/lifecycle/archive-me.md",
        "--reason",
        "stale",
        "--preview",
        "--json",
    )

    promote_payload = json.loads(promote_run.stdout)
    archive_payload = json.loads(archive_run.stdout)

    assert promote_run.returncode == 0
    assert promote_payload["preview"]["mode"] == "preview"
    assert promote_payload["new_state"]["new_path"] == "memory/knowledge/lifecycle/promote-me.md"

    assert archive_run.returncode == 0
    assert archive_payload["preview"]["mode"] == "preview"
    assert (
        archive_payload["new_state"]["archive_path"]
        == "memory/knowledge/_archive/lifecycle/archive-me.md"
    )

    status_run = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_run.stdout.strip() == ""


def test_promote_and_archive_human_output_integration(tmp_path: Path) -> None:
    repo_copy = _copy_repo_tree(tmp_path)
    _seed_lifecycle_fixture(repo_copy)

    promote_run = _run_cli(
        repo_copy,
        "promote",
        "memory/knowledge/_unverified/lifecycle/promote-me.md",
        "--trust",
        "medium",
    )
    archive_run = _run_cli(
        repo_copy,
        "archive",
        "memory/knowledge/lifecycle/archive-me.md",
        "--reason",
        "stale",
    )

    promoted_path = repo_copy / "core" / "memory" / "knowledge" / "lifecycle" / "promote-me.md"
    archived_path = (
        repo_copy / "core" / "memory" / "knowledge" / "_archive" / "lifecycle" / "archive-me.md"
    )

    assert promote_run.returncode == 0
    assert (
        "Promoted: memory/knowledge/_unverified/lifecycle/promote-me.md -> memory/knowledge/lifecycle/promote-me.md"
        in promote_run.stdout
    )
    assert "Trust: medium" in promote_run.stdout
    assert promoted_path.exists()
    assert "trust: medium" in promoted_path.read_text(encoding="utf-8")

    assert archive_run.returncode == 0
    assert (
        "Archived: memory/knowledge/lifecycle/archive-me.md -> memory/knowledge/_archive/lifecycle/archive-me.md"
        in archive_run.stdout
    )
    assert archived_path.exists()
    assert "status: archived" in archived_path.read_text(encoding="utf-8")

    status_run = subprocess.run(
        ["git", "status", "--short"],
        cwd=repo_copy,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_run.stdout.strip() == ""


def test_export_and_import_json_integration(tmp_path: Path) -> None:
    source_repo = _copy_repo_tree(tmp_path / "source")
    target_repo = _copy_repo_tree(tmp_path / "target")
    _seed_export_fixture(source_repo)
    bundle_path = tmp_path / "portable-bundle.json"

    export_run = _run_cli(
        source_repo,
        "export",
        "--format",
        "json",
        "--output",
        str(bundle_path),
        "--json",
    )
    import_run = _run_cli(
        target_repo,
        "import",
        str(bundle_path),
        "--apply",
        "--json",
    )

    export_payload = json.loads(export_run.stdout)
    import_payload = json.loads(import_run.stdout)

    assert export_run.returncode == 0
    assert export_payload["format"] == "json"
    assert bundle_path.exists()

    assert import_run.returncode == 0
    assert import_payload["commit_sha"]
    assert "core/memory/knowledge/portable.md" in import_payload["new_state"]["created_paths"]
    assert (target_repo / "core" / "memory" / "knowledge" / "portable.md").exists()

    status_run = subprocess.run(
        ["git", "status", "--short"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_run.stdout.strip() == ""


def test_export_markdown_and_import_preview_human_output_integration(tmp_path: Path) -> None:
    source_repo = _copy_repo_tree(tmp_path / "source")
    target_repo = _copy_repo_tree(tmp_path / "target")
    _seed_export_fixture(source_repo)
    _seed_import_conflict_fixture(target_repo)
    bundle_path = tmp_path / "portable-bundle.md"

    export_run = _run_cli(
        source_repo,
        "export",
        "--format",
        "md",
        "--output",
        str(bundle_path),
    )
    import_run = _run_cli(target_repo, "import", str(bundle_path))

    assert export_run.returncode == 0
    assert "Exported bundle:" in export_run.stdout
    assert "Format: md" in export_run.stdout

    assert import_run.returncode == 0
    assert "Mode: preview" in import_run.stdout
    assert "Summary: Import" in import_run.stdout
    assert "can_apply: False" in import_run.stdout

    status_run = subprocess.run(
        ["git", "status", "--short"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status_run.stdout.strip() == ""
