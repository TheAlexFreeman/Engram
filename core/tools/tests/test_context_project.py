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
    trailer = payload[len(prefix) :]
    # When every section is skipped (e.g. the time-budget degradation path)
    # the body is empty and the payload ends with the closing fence directly.
    if "\n```\n\n" in trailer:
        metadata_text, body = trailer.split("\n```\n\n", 1)
    else:
        metadata_text, _, body = trailer.partition("\n```\n")
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

    def test_response_metadata_includes_per_section_timings(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, _ = _parse_context_response(payload)

            timings = metadata.get("timings")
            self.assertIsInstance(timings, dict)
            timings_dict = cast(dict[str, Any], timings)
            self.assertIn("total_ms", timings_dict)
            self.assertIsInstance(timings_dict["total_ms"], (int, float))
            self.assertGreaterEqual(timings_dict["total_ms"], 0.0)

            spans = timings_dict.get("spans")
            self.assertIsInstance(spans, list)
            span_names = {cast(dict[str, Any], span)["name"] for span in spans}
            # Sections that always run on the demo repo (plan + IN + current)
            self.assertIn("plan_selection", span_names)
            self.assertIn("project_summary", span_names)
            self.assertIn("in_manifest", span_names)
            for span in spans:
                span_dict = cast(dict[str, Any], span)
                self.assertIn("name", span_dict)
                self.assertIn("duration_ms", span_dict)
                self.assertIn("status", span_dict)
                self.assertGreaterEqual(span_dict["duration_ms"], 0.0)
                self.assertEqual(span_dict["status"], "ok")
        finally:
            tmp.cleanup()

    def test_response_metadata_defaults_truncated_false_under_budget(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, _ = _parse_context_response(payload)

            self.assertEqual(metadata.get("truncated"), False)
            self.assertEqual(metadata.get("sections_omitted"), [])
            timings = cast(dict[str, Any], metadata.get("timings"))
            # Default budget is the module-level constant, surfaced verbatim.
            self.assertIsInstance(timings.get("budget_ms"), int)
            self.assertGreater(timings["budget_ms"], 0)
        finally:
            tmp.cleanup()

    def test_zero_time_budget_skips_sections_after_plan_selection(self) -> None:
        """A near-zero budget forces every post-plan-selection section to bail.

        ``time_budget_ms=1`` gets exhausted immediately inside ``plan_selection``
        itself (which always runs — it is load-bearing for metadata), so every
        subsequent section should be recorded as skipped with reason
        ``time_budget_exceeded`` and the response should carry ``truncated:
        true``.
        """
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(
                tool(project="demo-project", time_budget_ms=1, include_user_profile=True)
            )
            metadata, body = _parse_context_response(payload)

            self.assertTrue(metadata["truncated"])
            sections_omitted = cast(list[str], metadata["sections_omitted"])
            # Sections skipped by the time budget. Plan sources iterate per
            # source, so we only require the major sections here.
            for expected in (
                "User Profile",
                "Project Summary",
                "IN Staging",
            ):
                self.assertIn(expected, sections_omitted)

            dropped_reasons = {
                cast(dict[str, Any], item)["name"]: cast(dict[str, Any], item)["reason"]
                for item in metadata["budget_report"]["sections_dropped"]
            }
            self.assertEqual(dropped_reasons.get("Project Summary"), "time_budget_exceeded")
            self.assertEqual(dropped_reasons.get("IN Staging"), "time_budget_exceeded")
            # The skipped sections must not appear in the rendered body.
            self.assertNotIn("## Project Summary", body)
            self.assertNotIn("## IN Staging", body)
        finally:
            tmp.cleanup()

    def test_disabled_time_budget_runs_every_section(self) -> None:
        """``time_budget_ms=0`` disables the budget (matches coercion contract)."""
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project", time_budget_ms=0))
            metadata, _ = _parse_context_response(payload)

            self.assertFalse(metadata["truncated"])
            self.assertEqual(metadata["sections_omitted"], [])
            self.assertEqual(metadata["timings"]["budget_ms"], 0)
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

    def test_plan_sources_count_cap_excludes_extras(self) -> None:
        """More than 10 internal plan-sources → extras recorded as capped.

        Builds a plan with 12 internal sources (each small enough that the char
        cap isn't what trips first) and verifies the first 10 inline, the
        remaining 2 are recorded with reason ``plan_sources_cap``, and
        ``more_plan_sources`` == 2 in the response metadata.
        """
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        try:
            _init_git_repo(root)
            project_id = "capped-project"
            _write(
                root,
                "core/memory/users/SUMMARY.md",
                "# User\n\nAgent partner profile.",
            )
            _write(
                root,
                f"core/memory/working/projects/{project_id}/SUMMARY.md",
                "# Project\n\nProject summary content.",
            )
            source_count = 12
            source_specs: list[SourceSpec] = []
            for index in range(source_count):
                rel = f"core/tools/sources/source-{index:02d}.md"
                _write(root, rel, f"# Source {index}\n\nBody {index}.")
                source_specs.append(
                    SourceSpec(path=rel, type="internal", intent=f"Read source {index}")
                )

            plan = PlanDocument(
                id="project-plan",
                project=project_id,
                created="2026-03-28",
                origin_session="memory/activity/2026/03/28/chat-001",
                status="active",
                purpose=PlanPurpose(
                    summary="Cap test plan",
                    context="Exercises the plan_sources count cap.",
                ),
                phases=[
                    PlanPhase(
                        id="phase-one",
                        title="Implement feature",
                        status="pending",
                        requires_approval=False,
                        sources=source_specs,
                        postconditions=[
                            PostconditionSpec(
                                description="Tests pass",
                                type="test",
                                target="pytest -q",
                            )
                        ],
                        changes=[
                            ChangeSpec(
                                path=(f"memory/working/projects/{project_id}/notes/outcome.md"),
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

            _, tools, _, _ = create_mcp(root)
            tool = cast(Any, tools["memory_context_project"])
            # Disable char budget and time budget so the only thing that trips
            # is the explicit source count cap.
            payload = asyncio.run(
                tool(
                    project=project_id,
                    max_context_chars=0,
                    time_budget_ms=0,
                )
            )
            metadata, body = _parse_context_response(payload)

            self.assertEqual(metadata.get("more_plan_sources"), 2)
            capped = [
                cast(dict[str, Any], item)
                for item in metadata["budget_report"]["sections_dropped"]
                if cast(dict[str, Any], item).get("reason") == "plan_sources_cap"
            ]
            self.assertEqual(len(capped), 2)
            # The first 10 sources should appear in the rendered body; the
            # last two should be absent.
            for index in range(10):
                self.assertIn(f"## Source: core/tools/sources/source-{index:02d}.md", body)
            for index in (10, 11):
                self.assertNotIn(f"## Source: core/tools/sources/source-{index:02d}.md", body)
        finally:
            tmp.cleanup()

    def test_plan_sources_char_cap_excludes_extras(self) -> None:
        """Cumulative source chars over 8KB trip the cap before count does.

        Builds 5 internal sources, each ~3KB, so the 3rd source brings the
        cumulative total above 8KB and the remaining 2 are capped. Verifies
        ``more_plan_sources`` == 2.
        """
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        try:
            _init_git_repo(root)
            project_id = "char-capped-project"
            _write(
                root,
                "core/memory/users/SUMMARY.md",
                "# User\n\nAgent partner profile.",
            )
            _write(
                root,
                f"core/memory/working/projects/{project_id}/SUMMARY.md",
                "# Project\n\nProject summary content.",
            )
            big_body = "x" * 3200  # each source ~3.2KB of inlined content
            source_specs: list[SourceSpec] = []
            for index in range(5):
                rel = f"core/tools/big-sources/source-{index}.md"
                _write(root, rel, f"# Source {index}\n\n{big_body}")
                source_specs.append(SourceSpec(path=rel, type="internal", intent=f"Read {index}"))

            plan = PlanDocument(
                id="project-plan",
                project=project_id,
                created="2026-03-28",
                origin_session="memory/activity/2026/03/28/chat-001",
                status="active",
                purpose=PlanPurpose(
                    summary="Char cap test plan",
                    context="Exercises the plan_sources char cap.",
                ),
                phases=[
                    PlanPhase(
                        id="phase-one",
                        title="Implement feature",
                        status="pending",
                        requires_approval=False,
                        sources=source_specs,
                        postconditions=[
                            PostconditionSpec(
                                description="Tests pass",
                                type="test",
                                target="pytest -q",
                            )
                        ],
                        changes=[
                            ChangeSpec(
                                path=(f"memory/working/projects/{project_id}/notes/outcome.md"),
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

            _, tools, _, _ = create_mcp(root)
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(
                tool(
                    project=project_id,
                    max_context_chars=0,
                    time_budget_ms=0,
                )
            )
            metadata, _ = _parse_context_response(payload)

            # 3 sources fit under 8KB (3 * ~3.2KB = ~9.6KB — the 3rd source
            # pushes the cumulative total over the cap, so on the next
            # iteration the cap trips). Remaining 2 are capped.
            self.assertEqual(metadata.get("more_plan_sources"), 2)
            capped_paths = {
                cast(dict[str, Any], item).get("path")
                for item in metadata["budget_report"]["sections_dropped"]
                if cast(dict[str, Any], item).get("reason") == "plan_sources_cap"
            }
            self.assertEqual(
                capped_paths,
                {
                    "core/tools/big-sources/source-3.md",
                    "core/tools/big-sources/source-4.md",
                },
            )
        finally:
            tmp.cleanup()

    def test_plan_sources_under_cap_reports_zero_more(self) -> None:
        """Default small plan (1 source) → ``more_plan_sources`` is 0."""
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, _ = _parse_context_response(payload)

            self.assertEqual(metadata.get("more_plan_sources"), 0)
        finally:
            tmp.cleanup()
