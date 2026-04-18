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
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.tools.agent_memory_mcp.identity_paths import is_working_scratchpad_path  # noqa: E402
from core.tools.agent_memory_mcp.server import create_mcp  # noqa: E402


def _parse_context_response(payload: str) -> tuple[dict[str, object], str]:
    prefix = "```json\n"
    assert payload.startswith(prefix)
    metadata_text, body = payload[len(prefix) :].split("\n```\n\n", 1)
    return json.loads(metadata_text), body


class MultiUserWorkingNamespaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.temp_root = Path(self._tmpdir.name)

    def _init_repo(self, files: dict[str, str]) -> Path:
        temp_root = self.temp_root / "repo"
        content_root = temp_root / "core"
        content_root.mkdir(parents=True, exist_ok=True)
        (content_root / "INIT.md").write_text("# Session Init\n", encoding="utf-8")

        for rel_path, content in files.items():
            target_rel_path = rel_path
            if rel_path.startswith("memory/") or rel_path.startswith("governance/"):
                target_rel_path = f"core/{rel_path}"
            target = temp_root / target_rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        subprocess.run(["git", "init"], cwd=temp_root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "add", "."], cwd=temp_root, check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["git", "commit", "-m", "seed"],
            cwd=temp_root,
            check=True,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "GIT_AUTHOR_DATE": "2026-03-30T12:00:00+00:00",
                "GIT_COMMITTER_DATE": "2026-03-30T12:00:00+00:00",
            },
        )
        return content_root

    def _create_tools(self, repo_root: Path) -> dict[str, object]:
        _, tools, _, _ = create_mcp(repo_root)
        return tools

    def _load_tool_payload(self, raw: str) -> dict[str, Any]:
        payload = cast(dict[str, Any], json.loads(raw))
        if isinstance(payload, dict) and "_session" in payload and "result" in payload:
            return cast(dict[str, Any], payload["result"])
        return payload

    def test_memory_checkpoint_writes_namespaced_current_file(self) -> None:
        repo_root = self._init_repo({"memory/working/CURRENT.md": "# Legacy Current\n"})

        with mock.patch.dict(os.environ, {"MEMORY_USER_ID": "alex"}, clear=False):
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(cast(Any, tools["memory_checkpoint"])(content="Namespaced note."))
            )

        namespaced_current = (repo_root / "memory" / "working" / "alex" / "CURRENT.md").read_text(
            encoding="utf-8"
        )
        legacy_current = (repo_root / "memory" / "working" / "CURRENT.md").read_text(
            encoding="utf-8"
        )

        self.assertEqual(payload["new_state"]["target"], "memory/working/alex/CURRENT.md")
        self.assertIn("Namespaced note.", namespaced_current)
        self.assertEqual(legacy_current, "# Legacy Current\n")

    def test_memory_append_scratchpad_routes_aliases_and_notes_to_user_scope(self) -> None:
        repo_root = self._init_repo({"memory/working/USER.md": "# Legacy User\n"})

        with mock.patch.dict(os.environ, {"MEMORY_USER_ID": "alex"}, clear=False):
            tools = self._create_tools(repo_root)
            user_payload = self._load_tool_payload(
                asyncio.run(
                    cast(Any, tools["memory_append_scratchpad"])(
                        target="user",
                        content="Private priorities.",
                    )
                )
            )
            note_payload = self._load_tool_payload(
                asyncio.run(
                    cast(Any, tools["memory_append_scratchpad"])(
                        target="memory/working/notes/2026-03-30-worklog.md",
                        content="Scoped note.",
                        section="Findings",
                    )
                )
            )

        user_file = (repo_root / "memory" / "working" / "alex" / "USER.md").read_text(
            encoding="utf-8"
        )
        note_file = (
            repo_root / "memory" / "working" / "alex" / "notes" / "2026-03-30-worklog.md"
        ).read_text(encoding="utf-8")

        self.assertEqual(user_payload["new_state"]["target"], "memory/working/alex/USER.md")
        self.assertEqual(
            note_payload["new_state"]["target"],
            "memory/working/alex/notes/2026-03-30-worklog.md",
        )
        self.assertIn("Private priorities.", user_file)
        self.assertIn("## Findings\n\nScoped note.\n", note_file)

    def test_memory_context_home_prefers_namespaced_working_files(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/HOME.md": "# Home\n\n## Top of mind\n\n- Ship working namespaces\n",
                "memory/users/SUMMARY.md": "# User\n\nProfile.\n",
                "memory/activity/SUMMARY.md": "# Activity\n\nRecent work.\n",
                "memory/working/USER.md": "# Priorities\n\nLegacy priorities.\n",
                "memory/working/CURRENT.md": "# Current\n\nLegacy current state.\n",
                "memory/working/alex/USER.md": "# Priorities\n\nAlex priorities.\n",
                "memory/working/alex/CURRENT.md": "# Current\n\nAlex current state.\n",
                "memory/working/projects/SUMMARY.md": "# Projects\n\nShared projects.\n",
            }
        )

        with mock.patch.dict(os.environ, {"MEMORY_USER_ID": "alex"}, clear=False):
            tools = self._create_tools(repo_root)
            metadata, body = _parse_context_response(
                asyncio.run(cast(Any, tools["memory_context_home"])())
            )

        self.assertIn("Alex priorities.", body)
        self.assertIn("Alex current state.", body)
        self.assertNotIn("Legacy priorities.", body)
        self.assertNotIn("Legacy current state.", body)
        self.assertIn("memory/working/alex/USER.md", metadata["loaded_files"])
        self.assertIn("memory/working/alex/CURRENT.md", metadata["loaded_files"])

    def test_memory_context_project_uses_namespaced_current_without_flat_fallback(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/users/SUMMARY.md": "# User\n\nProfile.\n",
                "memory/working/projects/demo-project/SUMMARY.md": "# Project\n\nShared summary.\n",
                "memory/working/CURRENT.md": "# Current\n\nWorking on demo-project from the legacy scratchpad.\n",
                "memory/working/alex/CURRENT.md": "# Current\n\nWorking on something else today.\n",
            }
        )

        with mock.patch.dict(os.environ, {"MEMORY_USER_ID": "alex"}, clear=False):
            tools = self._create_tools(repo_root)
            metadata, body = _parse_context_response(
                asyncio.run(cast(Any, tools["memory_context_project"])(project="demo-project"))
            )

        self.assertIn("## Project Summary", body)
        self.assertNotIn("## Current Session Notes", body)
        self.assertTrue(
            any(
                item["name"] == "Current Session Notes" and item["reason"] == "not_relevant"
                for item in metadata["budget_report"]["sections_dropped"]
            )
        )

    def test_namespaced_working_paths_are_classified_as_scratchpads(self) -> None:
        self.assertTrue(is_working_scratchpad_path("memory/working/alex/USER.md"))
        self.assertTrue(is_working_scratchpad_path("memory/working/alex/CURRENT.md"))
        self.assertTrue(is_working_scratchpad_path("memory/working/alex/notes/worklog.md"))


if __name__ == "__main__":
    unittest.main()
