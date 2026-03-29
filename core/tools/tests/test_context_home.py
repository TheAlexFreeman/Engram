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


def _build_home_repo(root: Path) -> None:
    _write(
        root,
        "core/memory/HOME.md",
        "# Home\n\n## Top of mind\n\n- Ship context injectors\n- Keep budgets soft\n",
    )
    _write(root, "core/memory/users/SUMMARY.md", "# User\n\nPrefers terse updates.")
    _write(root, "core/memory/activity/SUMMARY.md", "# Activity\n\nRecent work summary.")
    _write(root, "core/memory/working/USER.md", "# Priorities\n\nFocus on MCP ergonomics.")
    _write(root, "core/memory/working/CURRENT.md", "# Current\n\nImplement context injectors.")
    _write(root, "core/memory/working/projects/SUMMARY.md", "# Projects\n\nOne active project.")
    _write(root, "core/memory/knowledge/SUMMARY.md", "# Knowledge\n\nKnowledge index.")
    _write(root, "core/memory/skills/SUMMARY.md", "# Skills\n\nSkill index.")


class MemoryContextHomeTests(unittest.TestCase):
    def _create_tools(self) -> tuple[tempfile.TemporaryDirectory[str], dict[str, object]]:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        _init_git_repo(root)
        _build_home_repo(root)
        _, tools, _, _ = create_mcp(root)
        return tmp, tools

    def test_full_load_returns_markdown_and_metadata(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_home"])
            payload = asyncio.run(tool())
            metadata, body = _parse_context_response(payload)

            self.assertEqual(metadata["tool"], "memory_context_home")
            self.assertEqual(metadata["format_version"], 1)
            self.assertIn("memory/HOME.md", metadata["loaded_files"])
            self.assertEqual(
                metadata["top_of_mind"], ["Ship context injectors", "Keep budgets soft"]
            )
            self.assertEqual(metadata["body_sections"][0]["path"], "memory/users/SUMMARY.md")
            self.assertIn("## User Summary", body)
            self.assertIn("_Source: memory/users/SUMMARY.md_", body)
            self.assertIn("## Recent Activity", body)
            self.assertIn("## Projects Index", body)
        finally:
            tmp.cleanup()

    def test_budget_pressure_drops_lower_priority_sections_first(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_home"])
            payload = asyncio.run(
                tool(
                    max_context_chars=80,
                    include_project_index=True,
                )
            )
            metadata, body = _parse_context_response(payload)
            dropped = metadata["budget_report"]["sections_dropped"]

            self.assertIn("## User Summary", body)
            self.assertNotIn("## Projects Index", body)
            self.assertTrue(any(item["name"] == "Projects Index" for item in dropped))
        finally:
            tmp.cleanup()

    def test_placeholder_user_file_is_skipped(self) -> None:
        tmp, tools = self._create_tools()
        try:
            root = Path(tmp.name)
            _write(root, "core/memory/working/USER.md", "[TEMPLATE]")

            tool = cast(Any, tools["memory_context_home"])
            payload = asyncio.run(tool())
            metadata, body = _parse_context_response(payload)

            self.assertNotIn("## User Priorities", body)
            self.assertTrue(
                any(
                    item["name"] == "User Priorities" and item["reason"] == "placeholder"
                    for item in metadata["budget_report"]["sections_dropped"]
                )
            )
        finally:
            tmp.cleanup()

    def test_include_flags_control_optional_indexes(self) -> None:
        tmp, tools = self._create_tools()
        try:
            tool = cast(Any, tools["memory_context_home"])
            payload = asyncio.run(
                tool(
                    include_project_index=False,
                    include_knowledge_index=True,
                    include_skills_index=True,
                )
            )
            _, body = _parse_context_response(payload)

            self.assertNotIn("## Projects Index", body)
            self.assertIn("## Knowledge Index", body)
            self.assertIn("## Skills Index", body)
        finally:
            tmp.cleanup()

    def test_missing_summary_file_degrades_gracefully(self) -> None:
        tmp, tools = self._create_tools()
        try:
            activity_path = Path(tmp.name) / "core" / "memory" / "activity" / "SUMMARY.md"
            activity_path.unlink()

            tool = cast(Any, tools["memory_context_home"])
            payload = asyncio.run(tool())
            metadata, body = _parse_context_response(payload)

            self.assertNotIn("## Recent Activity", body)
            self.assertTrue(
                any(
                    item["name"] == "Recent Activity" and item["reason"] == "missing"
                    for item in metadata["budget_report"]["sections_dropped"]
                )
            )
        finally:
            tmp.cleanup()
