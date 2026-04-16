from __future__ import annotations

import asyncio
import json
import os
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
            # Opt into plan sources explicitly; cold-start default is now off.
            payload = asyncio.run(tool(project="demo-project", include_plan_sources=True))
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
                    include_plan_sources=True,
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
        """Default (summary mode) shows counts and newest hint, not file bodies."""
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, body = _parse_context_response(payload)

            self.assertIn("## IN Staging", body)
            # Summary-mode default surfaces the count, not the full table.
            self.assertIn("1 file staged", body)
            self.assertIn("staged-note.md", body)
            self.assertNotIn("secret body", body)
            # Table header is a full-mode marker — should be absent here.
            self.assertNotIn("| Path | Trust | Source | Created |", body)
            self.assertEqual(metadata.get("more_in_items"), 1)
        finally:
            tmp.cleanup()

    def test_in_manifest_full_mode_renders_table(self) -> None:
        """Explicit ``include_in_manifest='full'`` shows the original table."""
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project", include_in_manifest="full"))
            _, body = _parse_context_response(payload)

            self.assertIn("## IN Staging", body)
            self.assertIn("| Path | Trust | Source | Created |", body)
            self.assertIn("staged-note.md", body)
        finally:
            tmp.cleanup()

    def test_in_manifest_off_omits_section(self) -> None:
        """``include_in_manifest=False`` skips IN Staging entirely."""
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project", include_in_manifest=False))
            metadata, body = _parse_context_response(payload)

            self.assertNotIn("## IN Staging", body)
            dropped_reasons = {
                cast(dict[str, Any], item)["name"]: cast(dict[str, Any], item)["reason"]
                for item in metadata["budget_report"]["sections_dropped"]
            }
            self.assertEqual(dropped_reasons.get("IN Staging"), "omitted_by_request")
        finally:
            tmp.cleanup()

    def test_include_session_notes_false_omits_current_section(self) -> None:
        """``include_session_notes=False`` skips Current Session Notes."""
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project", include_session_notes=False))
            metadata, body = _parse_context_response(payload)

            self.assertNotIn("## Current Session Notes", body)
            dropped_reasons = {
                cast(dict[str, Any], item)["name"]: cast(dict[str, Any], item)["reason"]
                for item in metadata["budget_report"]["sections_dropped"]
            }
            self.assertEqual(dropped_reasons.get("Current Session Notes"), "omitted_by_request")
        finally:
            tmp.cleanup()

    def test_cold_start_default_omits_plan_sources(self) -> None:
        """Default call renders Plan State but no Source: sections."""
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            payload = asyncio.run(tool(project="demo-project"))
            _, body = _parse_context_response(payload)

            self.assertIn("## Plan State", body)
            # Plan-sources are off by default under the cold-start contract.
            self.assertNotIn("## Source: core/tools/context-source.md", body)
        finally:
            tmp.cleanup()

    def test_invalid_include_in_manifest_raises(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])
            with self.assertRaises(ValidationError):
                asyncio.run(tool(project="demo-project", include_in_manifest="bogus"))
        finally:
            tmp.cleanup()

    def test_cache_miss_then_hit_on_second_call(self) -> None:
        """Second identical call returns ``cache_hit: true`` from the on-disk cache."""
        tmp, tools = self._create_tools()
        try:
            root = Path(tmp.name)
            tool = cast(Any, tools["memory_context_project"])

            first = asyncio.run(tool(project="demo-project"))
            first_meta, _ = _parse_context_response(first)
            self.assertFalse(first_meta["cache_hit"])

            cache_file = (
                root
                / "core"
                / "memory"
                / "working"
                / "projects"
                / "demo-project"
                / ".context-cache.json"
            )
            self.assertTrue(cache_file.is_file())

            second = asyncio.run(tool(project="demo-project"))
            second_meta, _ = _parse_context_response(second)
            self.assertTrue(second_meta["cache_hit"])
            # Cache-hit timings reflect *this* call, not the first render.
            self.assertIn(
                "cache_lookup", {span["name"] for span in second_meta["timings"]["spans"]}
            )
        finally:
            tmp.cleanup()

    def test_cache_invalidates_when_project_file_changes(self) -> None:
        """Editing any file under the project subtree busts the cache."""
        tmp, tools = self._create_tools()
        try:
            root = Path(tmp.name)
            tool = cast(Any, tools["memory_context_project"])

            asyncio.run(tool(project="demo-project"))  # populate cache

            summary_path = (
                root / "core" / "memory" / "working" / "projects" / "demo-project" / "SUMMARY.md"
            )
            # Write new content *and* bump mtime; both signal a change in the hash.
            summary_path.write_text(
                "# Project\n\nRevised summary content.",
                encoding="utf-8",
            )
            # On Windows the resolution of mtime can equal the prior write; force
            # a distinct mtime_ns via os.utime so the hash actually differs.
            stat = summary_path.stat()
            os.utime(summary_path, ns=(stat.st_atime_ns + 1, stat.st_mtime_ns + 10_000_000))

            payload = asyncio.run(tool(project="demo-project"))
            meta, _ = _parse_context_response(payload)
            self.assertFalse(meta["cache_hit"])
        finally:
            tmp.cleanup()

    def test_cache_differentiates_by_params(self) -> None:
        """Two calls with different params don't share a cache entry."""
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project"])

            # Prime the default (include_plan_sources=False) cache.
            first = asyncio.run(tool(project="demo-project"))
            first_meta, _ = _parse_context_response(first)
            self.assertFalse(first_meta["cache_hit"])

            # Different params → miss, even though content is unchanged.
            second = asyncio.run(tool(project="demo-project", include_plan_sources=True))
            second_meta, _ = _parse_context_response(second)
            self.assertFalse(second_meta["cache_hit"])

            # Third call mirrors the second — should now hit.
            third = asyncio.run(tool(project="demo-project", include_plan_sources=True))
            third_meta, _ = _parse_context_response(third)
            self.assertTrue(third_meta["cache_hit"])
        finally:
            tmp.cleanup()

    def test_cache_invalidates_when_session_notes_change(self) -> None:
        """Editing memory/working/CURRENT.md busts the cache when include_session_notes is on.

        The bundle inlines CURRENT.md under the *Current Session Notes* section;
        without folding its mtime into the content hash, an agent could keep
        reading yesterday's plan after the user edits their notes.
        """
        tmp, tools = self._create_tools()
        try:
            root = Path(tmp.name)
            tool = cast(Any, tools["memory_context_project"])

            asyncio.run(tool(project="demo-project"))  # populate cache

            current_path = root / "core" / "memory" / "working" / "CURRENT.md"
            current_path.write_text(
                "# Current\n\nSwitched focus to something else entirely.",
                encoding="utf-8",
            )
            stat = current_path.stat()
            os.utime(current_path, ns=(stat.st_atime_ns + 1, stat.st_mtime_ns + 10_000_000))

            payload = asyncio.run(tool(project="demo-project"))
            meta, _ = _parse_context_response(payload)
            self.assertFalse(meta["cache_hit"])
        finally:
            tmp.cleanup()

    def test_cache_invalidates_when_user_profile_changes(self) -> None:
        """Editing memory/users/SUMMARY.md busts the cache when the profile section is in scope."""
        tmp, tools = self._create_tools(include_plan=False)
        try:
            root = Path(tmp.name)
            tool = cast(Any, tools["memory_context_project"])

            # include_plan=False → no active plan → profile is auto-included.
            asyncio.run(tool(project="demo-project"))  # populate cache

            profile_path = root / "core" / "memory" / "users" / "SUMMARY.md"
            profile_path.write_text(
                "# User\n\nBrand new partner profile.",
                encoding="utf-8",
            )
            stat = profile_path.stat()
            os.utime(profile_path, ns=(stat.st_atime_ns + 1, stat.st_mtime_ns + 10_000_000))

            payload = asyncio.run(tool(project="demo-project"))
            meta, _ = _parse_context_response(payload)
            self.assertFalse(meta["cache_hit"])
        finally:
            tmp.cleanup()

    def test_cache_invalidates_when_internal_plan_source_changes(self) -> None:
        """Editing an internal plan-source file busts the cache under include_plan_sources=True."""
        tmp, tools = self._create_tools()
        try:
            root = Path(tmp.name)
            tool = cast(Any, tools["memory_context_project"])

            # Prime the cache with sources on; the plan references core/tools/context-source.md
            # as an internal source (see _build_project_repo).
            first = asyncio.run(tool(project="demo-project", include_plan_sources=True))
            first_meta, _ = _parse_context_response(first)
            self.assertFalse(first_meta["cache_hit"])

            source_path = root / "core" / "tools" / "context-source.md"
            source_path.write_text(
                "# Source\n\nCompletely rewritten source content.",
                encoding="utf-8",
            )
            stat = source_path.stat()
            os.utime(source_path, ns=(stat.st_atime_ns + 1, stat.st_mtime_ns + 10_000_000))

            payload = asyncio.run(tool(project="demo-project", include_plan_sources=True))
            meta, _ = _parse_context_response(payload)
            self.assertFalse(meta["cache_hit"])
        finally:
            tmp.cleanup()

    def test_cache_not_written_when_truncated(self) -> None:
        """Partial bundles (time budget exceeded) must not poison the cache."""
        tmp, tools = self._create_tools()
        try:
            root = Path(tmp.name)
            tool = cast(Any, tools["memory_context_project"])

            payload = asyncio.run(tool(project="demo-project", time_budget_ms=1))
            meta, _ = _parse_context_response(payload)
            self.assertTrue(meta["truncated"])

            cache_file = (
                root
                / "core"
                / "memory"
                / "working"
                / "projects"
                / "demo-project"
                / ".context-cache.json"
            )
            # Partial renders must not persist; the next call should miss cleanly
            # under normal parameters so we do not ship a truncated bundle to
            # callers who asked for the full path.
            self.assertFalse(cache_file.is_file())
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
                    include_plan_sources=True,
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
                    include_plan_sources=True,
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

    # --- memory_context_project_lite (P0-A step 7) ---

    def test_lite_returns_summary_and_plan_listing(self) -> None:
        """Lite tool renders SUMMARY body + a plans table, nothing more."""
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project_lite"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, body = _parse_context_response(payload)

            self.assertEqual(metadata["tool"], "memory_context_project_lite")
            self.assertEqual(metadata["project"], "demo-project")
            self.assertEqual(metadata["plan_count"], 1)
            self.assertEqual(metadata["active_plan_count"], 1)
            self.assertEqual(metadata["active_plan_ids"], ["project-plan"])
            self.assertEqual(
                metadata["plans"],
                [{"id": "project-plan", "status": "active", "file": "project-plan.yaml"}],
            )
            # Nothing expensive was loaded — no User Profile, IN staging, sources,
            # or session notes.
            self.assertIn("## Project Summary", body)
            self.assertIn("## Plans", body)
            self.assertNotIn("## User Profile", body)
            self.assertNotIn("## IN Staging", body)
            self.assertNotIn("## Current Session Notes", body)
            self.assertNotIn("## Source: ", body)
            # Lite tool never writes a cache file.
            self.assertNotIn("cache_hit", metadata)
        finally:
            tmp.cleanup()

    def test_lite_unknown_project_raises_validation_error(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project_lite"])
            with self.assertRaises(ValidationError) as ctx:
                asyncio.run(tool(project="unknown-project"))
            self.assertIn("Available projects: demo-project", str(ctx.exception))
        finally:
            tmp.cleanup()

    def test_lite_missing_summary_degrades_gracefully(self) -> None:
        """A project with no SUMMARY.md still returns a (plans-only) response."""
        tmp, tools = self._create_tools()
        try:
            root = Path(tmp.name)
            # Remove the SUMMARY that _build_project_repo created; plans stay.
            summary = (
                root / "core" / "memory" / "working" / "projects" / "demo-project" / "SUMMARY.md"
            )
            summary.unlink()

            tool = cast(Any, tools["memory_context_project_lite"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, body = _parse_context_response(payload)

            self.assertNotIn("## Project Summary", body)
            self.assertIn("## Plans", body)
            self.assertTrue(
                any(
                    cast(dict[str, Any], item).get("name") == "Project Summary"
                    and cast(dict[str, Any], item).get("reason") == "missing"
                    for item in metadata["budget_report"]["sections_dropped"]
                )
            )
        finally:
            tmp.cleanup()

    def test_lite_missing_plans_folder_is_not_an_error(self) -> None:
        """A project with no plans/ folder still returns the SUMMARY body."""
        tmp, tools = self._create_tools(include_plan=False)
        try:
            tool = cast(Any, tools["memory_context_project_lite"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, body = _parse_context_response(payload)

            self.assertEqual(metadata["plan_count"], 0)
            self.assertEqual(metadata["active_plan_count"], 0)
            self.assertEqual(metadata["active_plan_ids"], [])
            self.assertIn("## Project Summary", body)
            self.assertNotIn("## Plans", body)
            self.assertTrue(
                any(
                    cast(dict[str, Any], item).get("name") == "Plans"
                    and cast(dict[str, Any], item).get("reason") == "missing"
                    for item in metadata["budget_report"]["sections_dropped"]
                )
            )
        finally:
            tmp.cleanup()

    def test_lite_plan_listing_surfaces_non_active_plans(self) -> None:
        """Completed/draft plans show up in the listing but not in active_plan_ids."""
        tmp, tools = self._create_tools(include_plan=True)
        try:
            root = Path(tmp.name)
            # Add a second plan with a different status so the ordering and
            # active-filter behavior are exercised.
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
""",
            )

            tool = cast(Any, tools["memory_context_project_lite"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, _ = _parse_context_response(payload)

            self.assertEqual(metadata["plan_count"], 2)
            self.assertEqual(metadata["active_plan_count"], 1)
            self.assertEqual(metadata["active_plan_ids"], ["project-plan"])
            # active status (0) sorts before draft status (1).
            plan_ids_in_order = [cast(dict[str, Any], entry)["id"] for entry in metadata["plans"]]
            self.assertEqual(plan_ids_in_order, ["project-plan", "draft-plan"])
        finally:
            tmp.cleanup()

    def test_lite_skips_no_cache_write(self) -> None:
        """Lite does not create or consult the .context-cache.json file."""
        tmp, tools = self._create_tools()
        try:
            root = Path(tmp.name)
            cache_file = (
                root
                / "core"
                / "memory"
                / "working"
                / "projects"
                / "demo-project"
                / ".context-cache.json"
            )

            tool = cast(Any, tools["memory_context_project_lite"])
            # Call twice — cache would materialize by the second call if the
            # tool were using the cache layer.
            asyncio.run(tool(project="demo-project"))
            asyncio.run(tool(project="demo-project"))

            self.assertFalse(cache_file.exists())
        finally:
            tmp.cleanup()

    def test_lite_completes_quickly(self) -> None:
        """Sanity check: lite reports its own wall-clock and it is small.

        The roadmap's <500ms guarantee assumes projects of arbitrary size.
        On a minimal fixture this should finish in well under 500ms; a large
        regression would be obvious in the timings field.
        """
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_project_lite"])
            payload = asyncio.run(tool(project="demo-project"))
            metadata, _ = _parse_context_response(payload)

            timings = cast(dict[str, Any], metadata["timings"])
            # Self-reported total_ms must be both present and under a loose
            # regression ceiling. Keep this well above the actual observed
            # time to avoid flakiness on slow CI.
            self.assertIn("total_ms", timings)
            self.assertLess(float(timings["total_ms"]), 500.0)
        finally:
            tmp.cleanup()

    # --- Cold-start subsection preservation (P1-A) -------------------------

    def _write_cold_start_summary(
        self, root: Path, project_id: str, *, cold_start_tail: str
    ) -> None:
        summary_path = root / "core" / "memory" / "working" / "projects" / project_id / "SUMMARY.md"
        # The verbose chaff ahead of the cold-start tail is what the fallback
        # is meant to drop when the full body overflows the budget.
        chaff_paragraph = "Background: " + (
            "detailed rationale that a cold-starting agent does not need. " * 25
        )
        summary_path.write_text(
            "---\n"
            f"type: project\n"
            f"status: active\n"
            "cognitive_mode: planning\n"
            "created: 2026-03-28\n"
            "last_activity: 2026-03-28\n"
            "open_questions: 0\n"
            "plans: 0\n"
            "active_plans: 0\n"
            "origin_session: memory/activity/2026/03/28/chat-001\n"
            "source: agent-generated\n"
            "trust: medium\n"
            "---\n\n"
            f"# Project: {project_id.replace('-', ' ').title()}\n\n"
            "## Description\n"
            f"{chaff_paragraph}\n\n"
            f"{cold_start_tail}",
            encoding="utf-8",
        )

    def test_project_summary_preserves_cold_start_sections_under_budget(self) -> None:
        """When the full SUMMARY.md overflows, cold-start subsections still load."""
        from core.tools.agent_memory_mcp.frontmatter_utils import (
            build_project_cold_start_sections,
        )

        tmp, tools = self._create_tools()
        try:
            root = Path(tmp.name)
            tail_lines = build_project_cold_start_sections(
                project_id="demo-project",
                canonical_source="https://example.com/upstream@abc123",
                active_plan_paths=["memory/working/projects/demo-project/plans/project-plan.yaml"],
                questions_file_exists=False,
                open_questions_count=0,
                last_activity_date="2026-03-28",
            )
            tail = "\n".join(tail_lines).lstrip("\n") + "\n"
            self._write_cold_start_summary(root, "demo-project", cold_start_tail=tail)

            tool = cast(Any, tools["memory_context_project"])
            # 2000 chars is enough for the cold-start tail (~600 chars) but not
            # the full body (chaff pushes it well past 2000).
            payload = asyncio.run(tool(project="demo-project", max_context_chars=2000))
            metadata, body = _parse_context_response(payload)

            # Cold-start subsections survived budget pressure.
            self.assertIn("## Layout", body)
            self.assertIn("## Canonical source", body)
            self.assertIn("## How to continue", body)
            self.assertIn("https://example.com/upstream@abc123", body)
            # Chaff was dropped.
            self.assertNotIn("detailed rationale", body)

            # The section record reflects the partial-fit reason.
            section_reasons = {
                cast(dict[str, Any], item).get("name"): cast(dict[str, Any], item).get("reason")
                for item in cast(list[Any], metadata["budget_report"]["details"])
            }
            self.assertEqual(section_reasons.get("Project Summary"), "included_cold_start_only")
        finally:
            tmp.cleanup()

    def test_extract_project_cold_start_sections_returns_only_cold_start(self) -> None:
        """Unit test: the extractor isolates the three cold-start subsections."""
        from core.tools.agent_memory_mcp.frontmatter_utils import (
            extract_project_cold_start_sections,
        )

        body = (
            "# Project: Demo\n\n"
            "## Description\n"
            "Longwinded background.\n\n"
            "## Layout\n"
            "- [IN/](memory/working/projects/demo/IN/) -- staged\n\n"
            "## Canonical source\n"
            "- https://example.com/repo@v1\n\n"
            "## How to continue\n"
            "- Active plan: [plans/main.yaml](plans/main.yaml)\n\n"
            "## Other notes\n"
            "Should not appear in extracted output.\n"
        )

        extracted = extract_project_cold_start_sections(body)
        self.assertIsNotNone(extracted)
        assert extracted is not None  # for type narrowing
        self.assertIn("## Layout", extracted)
        self.assertIn("## Canonical source", extracted)
        self.assertIn("## How to continue", extracted)
        self.assertNotIn("## Description", extracted)
        self.assertNotIn("## Other notes", extracted)
        self.assertNotIn("Longwinded background", extracted)

    def test_extract_project_cold_start_sections_returns_none_when_absent(self) -> None:
        """The extractor returns None for pre-P1-A SUMMARY.md bodies."""
        from core.tools.agent_memory_mcp.frontmatter_utils import (
            extract_project_cold_start_sections,
        )

        body = "# Project: Legacy\n\n## Description\nOld body, no cold-start tail.\n"
        self.assertIsNone(extract_project_cold_start_sections(body))
