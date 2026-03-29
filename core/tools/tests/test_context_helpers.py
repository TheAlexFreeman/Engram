from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.tools.agent_memory_mcp.tools.read_tools._context import (  # noqa: E402
    _assemble_markdown_response,
    _build_budget_report,
    _is_placeholder,
    _read_file_content,
    _read_section_with_budget,
)


class ContextHelperTests(unittest.TestCase):
    def test_is_placeholder_detects_markers_and_heading_stub(self) -> None:
        self.assertTrue(_is_placeholder("{{PLACEHOLDER}}"))
        self.assertTrue(_is_placeholder("# Template"))
        self.assertFalse(_is_placeholder("# Real content\n\nThis section has substance."))

    def test_read_file_content_strips_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "core"
            target = root / "memory" / "users" / "SUMMARY.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                "---\ntrust: high\n---\n\n# User\n\nImportant notes.\n",
                encoding="utf-8",
            )

            content = _read_file_content(root, "memory/users/SUMMARY.md")

            self.assertEqual(content, "# User\n\nImportant notes.")

    def test_read_section_with_budget_respects_limit_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "core"
            target = root / "memory" / "activity" / "SUMMARY.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Activity\n\nRecent continuity.", encoding="utf-8")

            content, chars_used = _read_section_with_budget(root, "memory/activity/SUMMARY.md", 200)
            self.assertEqual(content, "# Activity\n\nRecent continuity.")
            self.assertEqual(chars_used, len("# Activity\n\nRecent continuity."))

            over_budget, over_budget_chars = _read_section_with_budget(
                root,
                "memory/activity/SUMMARY.md",
                10,
            )
            self.assertIsNone(over_budget)
            self.assertEqual(over_budget_chars, 0)

            missing, missing_chars = _read_section_with_budget(root, "memory/missing.md", 200)
            self.assertIsNone(missing)
            self.assertEqual(missing_chars, 0)

    def test_read_section_with_budget_treats_zero_as_unbounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "core"
            target = root / "memory" / "working" / "CURRENT.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Current\n\nThis content exceeds a tiny budget.", encoding="utf-8")

            content, chars_used = _read_section_with_budget(root, "memory/working/CURRENT.md", 0)

            self.assertEqual(content, "# Current\n\nThis content exceeds a tiny budget.")
            self.assertEqual(chars_used, len("# Current\n\nThis content exceeds a tiny budget."))

    def test_build_budget_report_summarizes_included_and_dropped_sections(self) -> None:
        report = _build_budget_report(
            [
                {
                    "name": "User Summary",
                    "path": "memory/users/SUMMARY.md",
                    "chars": 120,
                    "included": True,
                    "reason": "included",
                },
                {
                    "name": "Knowledge Index",
                    "path": "memory/knowledge/SUMMARY.md",
                    "chars": 0,
                    "included": False,
                    "reason": "over_budget",
                },
            ],
            max_context_chars=160,
        )

        self.assertEqual(report["total_chars"], 120)
        self.assertEqual(report["remaining_chars"], 40)
        self.assertEqual(report["sections_included"], ["User Summary"])
        self.assertEqual(report["sections_dropped"][0]["reason"], "over_budget")

    def test_assemble_markdown_response_emits_parseable_json_header(self) -> None:
        response = _assemble_markdown_response(
            {"tool": "memory_context_home", "loaded_files": ["memory/users/SUMMARY.md"]},
            [
                {
                    "name": "User Summary",
                    "path": "memory/users/SUMMARY.md",
                    "content": "# User\n\nNotes",
                }
            ],
        )

        self.assertTrue(response.startswith("```json\n"))
        metadata_block = response.split("```", 2)[1].replace("json\n", "", 1)
        metadata = json.loads(metadata_block)
        self.assertEqual(metadata["tool"], "memory_context_home")
        self.assertEqual(metadata["format_version"], 1)
        self.assertEqual(metadata["body_sections"][0]["path"], "memory/users/SUMMARY.md")
        self.assertIn("## User Summary", response)
        self.assertIn("_Source: memory/users/SUMMARY.md_", response)
