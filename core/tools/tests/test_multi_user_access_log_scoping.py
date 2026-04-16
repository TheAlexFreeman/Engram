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


class MultiUserAccessLogScopingTests(unittest.TestCase):
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

    def test_memory_aggregate_access_filters_entries_by_user_id(self) -> None:
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
                                "session_id": f"memory/activity/alex/2026/03/30/chat-{idx:03d}",
                            }
                        )
                        + "\n"
                        for idx in range(1, 4)
                    ]
                    + [
                        json.dumps(
                            {
                                "file": "memory/working/projects/blake-plan.md",
                                "date": "2026-03-30",
                                "task": "planning",
                                "helpfulness": 0.2,
                                "note": "blake-only",
                                "user_id": "blake",
                                "session_id": f"memory/activity/blake/2026/03/30/chat-{idx:03d}",
                            }
                        )
                        + "\n"
                        for idx in range(1, 3)
                    ]
                ),
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(cast(Any, tools["memory_aggregate_access"])(folder="plans", user_id="alex"))
        )

        self.assertEqual(payload["filters"]["user_id"], "alex")
        self.assertEqual(payload["entries_considered"], 3)
        self.assertEqual(payload["files_considered"], 1)
        self.assertEqual(
            payload["file_summaries"][0]["file"],
            "memory/working/projects/alex-plan.md",
        )

    def test_memory_access_analytics_filters_entries_by_user_id(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/ACCESS.jsonl": "".join(
                    [
                        json.dumps(
                            {
                                "date": "2026-03-30",
                                "file": "memory/knowledge/alex-core.md",
                                "task": "analysis",
                                "helpfulness": 0.8,
                                "user_id": "alex",
                            }
                        )
                        + "\n"
                        for _ in range(5)
                    ]
                    + [
                        json.dumps(
                            {
                                "date": "2026-03-30",
                                "file": "memory/knowledge/blake-retire.md",
                                "task": "analysis",
                                "helpfulness": 0.2,
                                "user_id": "blake",
                            }
                        )
                        + "\n"
                        for _ in range(4)
                    ]
                ),
                "memory/knowledge/alex-core.md": "# Alex Core\n",
                "memory/knowledge/blake-retire.md": "# Blake Retire\n",
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                cast(Any, tools["memory_access_analytics"])(folders="knowledge", user_id="alex")
            )
        )

        self.assertEqual(payload["user_id"], "alex")
        self.assertEqual(payload["total_entries"], 5)
        self.assertEqual(payload["unique_files"], 1)
        self.assertEqual(
            payload["categories"]["core_memory"],
            [{"file": "memory/knowledge/alex-core.md", "access_count": 5, "mean_helpfulness": 0.8}],
        )
        self.assertEqual(payload["categories"]["retirement_candidate"], [])

    def test_memory_get_file_provenance_filters_access_summary_by_user_id(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/topic.md": "# Topic\n\nNote.\n",
                "memory/knowledge/ACCESS.jsonl": "".join(
                    [
                        json.dumps(
                            {
                                "file": "memory/knowledge/topic.md",
                                "date": "2026-03-30",
                                "task": "research",
                                "helpfulness": 0.9,
                                "note": "alex lookup",
                                "user_id": "alex",
                                "session_id": f"memory/activity/alex/2026/03/30/chat-{idx:03d}",
                            }
                        )
                        + "\n"
                        for idx in range(1, 3)
                    ]
                    + [
                        json.dumps(
                            {
                                "file": "memory/knowledge/topic.md",
                                "date": "2026-03-30",
                                "task": "research",
                                "helpfulness": 0.4,
                                "note": "blake lookup",
                                "user_id": "blake",
                                "session_id": "memory/activity/blake/2026/03/30/chat-001",
                            }
                        )
                        + "\n"
                    ]
                ),
            }
        )
        tools = self._create_tools(repo_root)

        payload = self._load_tool_payload(
            asyncio.run(
                cast(Any, tools["memory_get_file_provenance"])(
                    path="memory/knowledge/topic.md",
                    user_id="alex",
                )
            )
        )

        self.assertEqual(payload["access_filter_user_id"], "alex")
        self.assertEqual(payload["access_summary"]["entry_count"], 2)
        self.assertEqual(payload["access_summary"]["session_count"], 2)
        self.assertEqual(
            payload["access_summary"]["session_ids"],
            [
                "memory/activity/alex/2026/03/30/chat-001",
                "memory/activity/alex/2026/03/30/chat-002",
            ],
        )


if __name__ == "__main__":
    unittest.main()
