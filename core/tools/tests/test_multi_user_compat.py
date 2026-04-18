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

from core.tools.agent_memory_mcp.server import create_mcp  # noqa: E402


def _parse_context_response(payload: str) -> tuple[dict[str, object], str]:
    prefix = "```json\n"
    assert payload.startswith(prefix)
    metadata_text, body = payload[len(prefix) :].split("\n```\n\n", 1)
    return json.loads(metadata_text), body


class MultiUserCompatTests(unittest.TestCase):
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

    def test_working_tools_keep_flat_paths_without_memory_user_id(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/USER.md": "# User\n",
                "memory/working/CURRENT.md": "# Current\n",
            }
        )
        tools = self._create_tools(repo_root)

        checkpoint_payload = self._load_tool_payload(
            asyncio.run(cast(Any, tools["memory_checkpoint"])(content="Flat checkpoint."))
        )
        user_payload = self._load_tool_payload(
            asyncio.run(
                cast(Any, tools["memory_append_scratchpad"])(
                    target="user",
                    content="Flat priorities.",
                )
            )
        )
        note_payload = self._load_tool_payload(
            asyncio.run(
                cast(Any, tools["memory_append_scratchpad"])(
                    target="memory/working/notes/2026-03-30-log.md",
                    content="Flat notes.",
                )
            )
        )

        self.assertEqual(checkpoint_payload["new_state"]["target"], "memory/working/CURRENT.md")
        self.assertEqual(user_payload["new_state"]["target"], "memory/working/USER.md")
        self.assertEqual(
            note_payload["new_state"]["target"],
            "memory/working/notes/2026-03-30-log.md",
        )
        self.assertFalse((repo_root / "memory" / "working" / "alex").exists())

    def test_memory_context_home_uses_flat_working_files_without_memory_user_id(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/HOME.md": "# Home\n\n## Top of mind\n\n- Keep flat layout\n",
                "memory/users/SUMMARY.md": "# User\n\nProfile.\n",
                "memory/activity/SUMMARY.md": "# Activity\n\nRecent work.\n",
                "memory/working/USER.md": "# Priorities\n\nFlat priorities.\n",
                "memory/working/CURRENT.md": "# Current\n\nFlat current state.\n",
                "memory/working/alex/USER.md": "# Priorities\n\nAlex priorities.\n",
                "memory/working/alex/CURRENT.md": "# Current\n\nAlex current state.\n",
                "memory/working/projects/SUMMARY.md": "# Projects\n\nShared projects.\n",
            }
        )
        tools = self._create_tools(repo_root)

        metadata, body = _parse_context_response(
            asyncio.run(cast(Any, tools["memory_context_home"])())
        )

        self.assertIn("Flat priorities.", body)
        self.assertIn("Flat current state.", body)
        self.assertNotIn("Alex priorities.", body)
        self.assertNotIn("Alex current state.", body)
        self.assertIn("memory/working/USER.md", metadata["loaded_files"])
        self.assertIn("memory/working/CURRENT.md", metadata["loaded_files"])

    def test_memory_record_session_keeps_flat_activity_paths_without_memory_user_id(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/activity/SUMMARY.md": "# Chats\n## Structure\n",
                "memory/knowledge/topic.md": "# Topic\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                cast(Any, tools["memory_record_session"])(
                    session_id="memory/activity/2026/03/30/chat-001",
                    summary="# Session Summary\n\nFlat layout.\n",
                    key_topics="compat",
                    access_entries=[
                        {
                            "file": "memory/knowledge/topic.md",
                            "task": "compat check",
                            "helpfulness": 0.7,
                            "note": "Flat session remained valid.",
                        }
                    ],
                )
            )
        )

        summary_path = (
            repo_root / "memory" / "activity" / "2026" / "03" / "30" / "chat-001" / "SUMMARY.md"
        )
        access_entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )

        self.assertEqual(payload["new_state"]["session_id"], "memory/activity/2026/03/30/chat-001")
        self.assertTrue(summary_path.exists())
        self.assertNotIn("user_id", access_entry)
        self.assertEqual(access_entry["session_id"], "memory/activity/2026/03/30/chat-001")

    def test_access_tools_default_to_repo_wide_scope_without_user_filter(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/projects/ACCESS.jsonl": "".join(
                    [
                        json.dumps(
                            {
                                "file": "memory/working/projects/alex-plan.md",
                                "date": "2026-03-30",
                                "task": "planning",
                                "helpfulness": 0.9,
                                "note": "alex-only",
                                "user_id": "alex",
                            }
                        )
                        + "\n",
                        json.dumps(
                            {
                                "file": "memory/working/projects/blake-plan.md",
                                "date": "2026-03-30",
                                "task": "planning",
                                "helpfulness": 0.3,
                                "note": "blake-only",
                                "user_id": "blake",
                            }
                        )
                        + "\n",
                    ]
                ),
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(cast(Any, tools["memory_aggregate_access"])())
        )

        self.assertIsNone(payload["filters"]["user_id"])
        self.assertEqual(payload["entries_considered"], 2)
        self.assertEqual(payload["files_considered"], 2)


if __name__ == "__main__":
    unittest.main()
