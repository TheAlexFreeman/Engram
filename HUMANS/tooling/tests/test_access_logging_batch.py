from __future__ import annotations

import asyncio
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, ClassVar, Coroutine, cast

REPO_ROOT = Path(__file__).resolve().parents[3]
ToolCallable = Callable[..., Coroutine[Any, Any, str]]


def load_server_module():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.server")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"agent_memory_mcp dependencies unavailable: {exc.name}") from exc


class AccessLoggingBatchTests(unittest.TestCase):
    server: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = load_server_module()

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def _init_repo(self, files: dict[str, str]) -> Path:
        repo_root = Path(self._tmpdir.name) / "repo"
        repo_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )

        for rel_path, content in files.items():
            target = repo_root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        subprocess.run(
            ["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["git", "commit", "-m", "seed"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return repo_root

    def _create_tools(self, repo_root: Path) -> dict[str, ToolCallable]:
        _, tools, _, _ = self.server.create_mcp(repo_root=repo_root)
        return cast(dict[str, ToolCallable], tools)

    def test_memory_log_access_batch_appends_entries_in_single_commit_with_optional_fields(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/working/projects/demo.md": "# Demo\n",
                "HUMANS/tooling/agent-memory-capabilities.toml": (
                    '[access_logging]\ntask_ids = ["plan-review", "validation"]\n'
                ),
            }
        )
        tools = self._create_tools(repo_root)

        before_count = int(
            subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )

        raw = asyncio.run(
            tools["memory_log_access_batch"](
                access_entries=[
                    {
                        "file": "memory/knowledge/lit/foo.md",
                        "task": "batch test",
                        "helpfulness": 0.8,
                        "note": "knowledge entry",
                        "mode": "write",
                        "task_id": "plan-review",
                    },
                    {
                        "file": "memory/working/projects/demo.md",
                        "task": "batch test",
                        "helpfulness": 0.6,
                        "note": "plan entry",
                    },
                ],
                session_id="memory/activity/2026/03/20/chat-020",
            )
        )

        after_count = int(
            subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )

        payload = json.loads(raw)
        knowledge_entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        plan_entry = json.loads(
            (repo_root / "memory" / "working" / "projects" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )

        self.assertEqual(after_count - before_count, 1)
        self.assertEqual(payload["new_state"]["entry_count"], 2)
        self.assertEqual(
            sorted(payload["new_state"]["access_jsonls"]),
            ["memory/knowledge/ACCESS.jsonl", "memory/working/projects/ACCESS.jsonl"],
        )
        self.assertEqual(knowledge_entry["session_id"], "memory/activity/2026/03/20/chat-020")
        self.assertEqual(knowledge_entry["mode"], "write")
        self.assertEqual(knowledge_entry["task_id"], "plan-review")
        self.assertEqual(plan_entry["session_id"], "memory/activity/2026/03/20/chat-020")

    def test_memory_log_access_batch_routes_low_helpfulness_to_scans_sidecar(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/working/projects/demo.md": "# Demo\n",
            }
        )
        tools = self._create_tools(repo_root)

        raw = asyncio.run(
            tools["memory_log_access_batch"](
                access_entries=[
                    {
                        "file": "memory/knowledge/lit/foo.md",
                        "task": "batch test",
                        "helpfulness": 0.9,
                        "note": "keep in hot log",
                    },
                    {
                        "file": "memory/working/projects/demo.md",
                        "task": "batch test",
                        "helpfulness": 0.2,
                        "note": "route to scans",
                    },
                ],
                session_id="memory/activity/2026/03/20/chat-021",
                min_helpfulness=0.7,
            )
        )

        payload = json.loads(raw)
        knowledge_entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        plan_scan_entry = json.loads(
            (repo_root / "memory" / "working" / "projects" / "ACCESS_SCANS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )

        self.assertEqual(payload["new_state"]["scan_entry_count"], 1)
        self.assertEqual(
            sorted(payload["new_state"]["access_jsonls"]),
            ["memory/knowledge/ACCESS.jsonl", "memory/working/projects/ACCESS_SCANS.jsonl"],
        )
        self.assertEqual(knowledge_entry["session_id"], "memory/activity/2026/03/20/chat-021")
        self.assertEqual(plan_scan_entry["session_id"], "memory/activity/2026/03/20/chat-021")
        self.assertEqual(plan_scan_entry["helpfulness"], 0.2)
