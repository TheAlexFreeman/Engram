from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[3]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.tools.agent_memory_mcp.errors import ValidationError  # noqa: E402
from core.tools.agent_memory_mcp.plan_utils import (  # noqa: E402
    ChangeSpec,
    PlanDocument,
    PlanPhase,
    PlanPurpose,
    PostconditionSpec,
    SourceSpec,
    save_plan,
)
from core.tools.agent_memory_mcp.server import create_mcp  # noqa: E402


def _parse_context_response(payload: str) -> tuple[dict[str, object], str]:
    prefix = "```json\n"
    assert payload.startswith(prefix)
    metadata_text, body = payload[len(prefix) :].split("\n```\n\n", 1)
    return json.loads(metadata_text), body


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)


def _write(root: Path, rel_path: str, content: str) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _save_project_plan(
    root: Path,
    project_id: str,
    *,
    status: str = "active",
    phase_status: str = "pending",
    requires_approval: bool = False,
) -> None:
    plan = PlanDocument(
        id="project-plan",
        project=project_id,
        created="2026-03-28",
        origin_session="memory/activity/2026/03/28/chat-001",
        status=status,
        purpose=PlanPurpose(
            summary="Project plan summary",
            context="Project plan context with enough detail to exercise the section renderer.",
        ),
        phases=[
            PlanPhase(
                id="phase-one",
                title="Implement feature",
                status=phase_status,
                requires_approval=requires_approval,
                sources=[
                    SourceSpec(
                        path="core/tools/context-source.md",
                        type="internal",
                        intent="Read the source context.",
                    )
                ],
                postconditions=[
                    PostconditionSpec(
                        description="Tests pass",
                        type="test",
                        target="pytest core/tools/tests/test_context_project.py -q",
                    )
                ],
                changes=[
                    ChangeSpec(
                        path=f"memory/working/projects/{project_id}/notes/outcome.md",
                        action="create",
                        description="Record outcome.",
                    )
                ],
            )
        ],
        review=None,
    )
    plan_path = (
        root
        / "core"
        / "memory"
        / "working"
        / "projects"
        / project_id
        / "plans"
        / "project-plan.yaml"
    )
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    save_plan(plan_path, plan)


def _build_project_repo(
    root: Path, *, include_plan: bool = True, current_mentions_project: bool = True
) -> None:
    project_id = "demo-project"
    _write(root, "core/memory/users/SUMMARY.md", "# User\n\nAgent partner profile.")
    _write(
        root,
        f"core/memory/working/projects/{project_id}/SUMMARY.md",
        "# Project\n\nProject summary content.",
    )
    _write(
        root,
        "core/tools/context-source.md",
        "# Source\n\nImplementation details for the project source file.",
    )
    _write(
        root,
        f"core/memory/working/projects/{project_id}/IN/staged-note.md",
        "---\ntrust: low\nsource: external-research\ncreated: 2026-03-28\n---\n\n# Staged\n\nsecret body",
    )
    current_body = (
        f"# Current\n\nWorking on {project_id} today."
        if current_mentions_project
        else "# Current\n\nWorking on something else."
    )
    _write(root, "core/memory/working/CURRENT.md", current_body)
    if include_plan:
        _save_project_plan(root, project_id)


class MemoryContextProjectTests(unittest.TestCase):
    def _create_tools(
        self, *, include_plan: bool = True, current_mentions_project: bool = True
    ) -> tuple[tempfile.TemporaryDirectory[str], dict[str, object]]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        _init_git_repo(root)
        _build_project_repo(
            root, include_plan=include_plan, current_mentions_project=current_mentions_project
        )
        _, tools, _, _ = create_mcp(root)
        return tmp, tools

    def test_valid_project_returns_summary_plan_and_metadata(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, body = _parse_context_response(payload)

            self.assertEqual(metadata["tool"], "memory_context_project")
            self.assertEqual(metadata["project"], "demo-project")
            self.assertEqual(metadata["plan_id"], "project-plan")
            self.assertEqual(metadata["plan_source"], "validated")
            self.assertEqual(metadata["current_phase_title"], "Implement feature")
            self.assertEqual(
                metadata["next_action"],
                {
                    "id": "phase-one",
                    "title": "Implement feature",
                    "requires_approval": False,
                    "attempt_number": 1,
                    "has_prior_failures": False,
                },
            )
            self.assertEqual(
                metadata["body_sections"][0]["path"],
                "memory/working/projects/demo-project/SUMMARY.md",
            )
            self.assertNotIn("## User Profile", body)
            self.assertIn("## Project Summary", body)
            self.assertIn("_Source: memory/working/projects/demo-project/SUMMARY.md_", body)
            self.assertIn("## Plan State", body)
            self.assertIn("## Source: core/tools/context-source.md", body)
            self.assertTrue(
                any(
                    item["name"] == "User Profile" and item["reason"] == "auto_omitted"
                    for item in metadata["budget_report"]["sections_dropped"]
                )
            )
        finally:
            tmp.cleanup()

    def test_raw_yaml_fallback_surfaces_draft_plan_context(self) -> None:
        tmp, tools = self._create_tools(include_plan=False)
        try:
            root = Path(tmp.name)
            _write(
                root,
                "core/memory/working/projects/demo-project/plans/draft-plan.yaml",
                """id: draft-plan
project: demo-project
status: draft
purpose:
  summary: Draft plan summary
  context: Draft plan context
work:
  phases:
    - id: phase-a
      title: Draft phase
      status: pending
      requires_approval: true
      sources:
        - path: core/tools/context-source.md
          type: internal
          intent: Read source
      postconditions:
        - type: check
          description: Exists without formal target yet
""",
            )

            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, body = _parse_context_response(payload)

            self.assertEqual(metadata["plan_id"], "draft-plan")
            self.assertEqual(metadata["plan_source"], "raw_yaml_fallback")
            self.assertEqual(metadata["current_phase_title"], "Draft phase")
            self.assertEqual(
                metadata["next_action"],
                {
                    "id": "phase-a",
                    "title": "Draft phase",
                    "requires_approval": True,
                },
            )
            self.assertNotIn("## User Profile", body)
            self.assertIn("Loaded from raw YAML fallback", body)
            self.assertIn("Exists without formal target yet", body)
        finally:
            tmp.cleanup()

    def test_unknown_project_raises_validation_error(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            with self.assertRaises(ValidationError) as ctx:
                asyncio.run(tool(project="unknown-project"))
            self.assertIn("Available projects: demo-project", str(ctx.exception))
        finally:
            tmp.cleanup()

    def test_no_plan_degrades_gracefully(self) -> None:
        tmp, tools = self._create_tools(include_plan=False)
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, body = _parse_context_response(payload)

            self.assertIsNone(metadata["plan_id"])
            self.assertIsNone(metadata["next_action"])
            self.assertIn("## User Profile", body)
            self.assertIn("No active plan found", body)
        finally:
            tmp.cleanup()

    def test_completed_plan_reports_null_next_action(self) -> None:
        tmp, tools = self._create_tools(include_plan=False)
        try:
            root = Path(tmp.name)
            _save_project_plan(root, "demo-project", status="completed", phase_status="completed")

            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, body = _parse_context_response(payload)

            self.assertEqual(metadata["plan_id"], "project-plan")
            self.assertIsNone(metadata["next_action"])
            self.assertIsNone(metadata["current_phase_id"])
            self.assertNotIn("## User Profile", body)
            self.assertIn("No actionable phase is available.", body)
        finally:
            tmp.cleanup()

    def test_budget_pressure_drops_source_before_summary(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(
                tool(
                    project="demo-project",
                    max_context_chars=240,
                )
            )
            metadata, body = _parse_context_response(payload)

            self.assertIn("## Project Summary", body)
            self.assertNotIn("## Source: core/tools/context-source.md", body)
            self.assertTrue(
                any(
                    item["name"] == "Source: core/tools/context-source.md"
                    and item["reason"] == "over_budget"
                    for item in metadata["budget_report"]["sections_dropped"]
                )
            )
        finally:
            tmp.cleanup()

    def test_explicit_user_profile_false_omits_profile_section(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(
                tool(
                    project="demo-project",
                    include_user_profile=False,
                )
            )
            metadata, body = _parse_context_response(payload)

            self.assertNotIn("## User Profile", body)
            self.assertTrue(
                any(
                    item["name"] == "User Profile" and item["reason"] == "omitted_by_request"
                    for item in metadata["budget_report"]["sections_dropped"]
                )
            )
        finally:
            tmp.cleanup()

    def test_explicit_user_profile_true_overrides_auto_omit(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project", include_user_profile=True))
            metadata, body = _parse_context_response(payload)

            self.assertIn("## User Profile", body)
            self.assertEqual(metadata["body_sections"][0]["path"], "memory/users/SUMMARY.md")
        finally:
            tmp.cleanup()

    def test_in_listing_shows_metadata_not_body(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project"))
            _, body = _parse_context_response(payload)

            self.assertIn("## IN Staging", body)
            self.assertIn("staged-note.md", body)
            self.assertNotIn("secret body", body)
        finally:
            tmp.cleanup()

    def test_current_notes_only_include_relevant_project(self) -> None:
        tmp, tools = self._create_tools(current_mentions_project=False)
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, body = _parse_context_response(payload)

            self.assertNotIn("## Current Session Notes", body)
            self.assertTrue(
                any(
                    item["name"] == "Current Session Notes" and item["reason"] == "not_relevant"
                    for item in metadata["budget_report"]["sections_dropped"]
                )
            )
        finally:
            tmp.cleanup()
