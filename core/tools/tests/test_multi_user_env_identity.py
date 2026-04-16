from __future__ import annotations

import asyncio
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Coroutine, cast
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
ToolCallable = Callable[..., Coroutine[Any, Any, str]]


def _load_module(name: str) -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module(name)


class MultiUserEnvIdentityTests(unittest.TestCase):
    server: ModuleType
    session_state_module: ModuleType
    errors: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.server = _load_module("engram_mcp.agent_memory_mcp.server")
            cls.session_state_module = _load_module("engram_mcp.agent_memory_mcp.session_state")
            cls.errors = _load_module("engram_mcp.agent_memory_mcp.errors")
        except ModuleNotFoundError as exc:
            raise unittest.SkipTest(
                f"agent_memory_mcp dependencies unavailable: {exc.name}"
            ) from exc

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
                "GIT_AUTHOR_DATE": "2026-03-28T12:00:00+00:00",
                "GIT_COMMITTER_DATE": "2026-03-28T12:00:00+00:00",
            },
        )
        return content_root

    def _create_tools(self, repo_root: Path) -> dict[str, ToolCallable]:
        _, tools, _, _ = self.server.create_mcp(repo_root=repo_root)
        return cast(dict[str, ToolCallable], tools)

    def _load_tool_payload(self, raw: str) -> dict[str, Any]:
        payload = cast(dict[str, Any], json.loads(raw))
        if isinstance(payload, dict) and "_session" in payload and "result" in payload:
            return cast(dict[str, Any], payload["result"])
        return payload

    def test_session_state_snapshot_includes_user_id_and_reset_preserves_it(self) -> None:
        start = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
        reset_time = start + timedelta(minutes=9)
        state = self.session_state_module.SessionState(session_start=start, user_id="alex")

        with mock.patch.object(self.session_state_module, "_utcnow", return_value=reset_time):
            payload = state.reset()

        self.assertEqual(state.user_id, "alex")
        self.assertEqual(payload["user_id"], "alex")

    def test_create_mcp_reads_memory_user_id_from_environment(self) -> None:
        repo_root = self._init_repo({})
        captured: dict[str, object] = {}

        def fake_read_register(mcp, get_repo, get_root, session_state=None):
            captured["read"] = session_state
            return {}

        def fake_semantic_register(mcp, get_repo, get_root, session_state=None):
            captured["semantic"] = session_state
            return {}

        with (
            mock.patch.dict(os.environ, {"MEMORY_USER_ID": "alex"}, clear=False),
            mock.patch.object(self.server.read_tools, "register", side_effect=fake_read_register),
            mock.patch.object(self.server.semantic, "register", side_effect=fake_semantic_register),
        ):
            self.server.create_mcp(repo_root=repo_root)

        self.assertIs(captured["read"], captured["semantic"])
        self.assertEqual(cast(Any, captured["read"]).user_id, "alex")

    def test_create_mcp_allows_missing_memory_user_id(self) -> None:
        repo_root = self._init_repo({})
        captured: dict[str, object] = {}

        def fake_read_register(mcp, get_repo, get_root, session_state=None):
            captured["read"] = session_state
            return {}

        def fake_semantic_register(mcp, get_repo, get_root, session_state=None):
            captured["semantic"] = session_state
            return {}

        with (
            mock.patch.dict(os.environ, {}, clear=False),
            mock.patch.object(self.server.read_tools, "register", side_effect=fake_read_register),
            mock.patch.object(self.server.semantic, "register", side_effect=fake_semantic_register),
        ):
            os.environ.pop("MEMORY_USER_ID", None)
            self.server.create_mcp(repo_root=repo_root)

        self.assertIsNone(cast(Any, captured["read"]).user_id)

    def test_memory_log_access_includes_user_id_from_environment(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/literature/galatea.md": "# Galatea\n",
                "memory/knowledge/ACCESS.jsonl": "",
            }
        )
        with mock.patch.dict(os.environ, {"MEMORY_USER_ID": "alex"}, clear=False):
            tools = self._create_tools(repo_root)
            asyncio.run(
                tools["memory_log_access"](
                    file="memory/knowledge/literature/galatea.md",
                    task="User asked about AI literature references",
                    helpfulness=0.8,
                    note="Core reference for the answer.",
                    session_id="memory/activity/2026/03/19/chat-001",
                )
            )

        entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertEqual(entry["user_id"], "alex")
        self.assertEqual(entry["session_id"], "memory/activity/alex/2026/03/19/chat-001")

    def test_memory_session_flush_writes_user_id_comment(self) -> None:
        repo_root = self._init_repo({"memory/working/USER.md": "# User\n"})
        with mock.patch.dict(os.environ, {"MEMORY_USER_ID": "alex"}, clear=False):
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_session_flush"](
                        summary="Decision: enable token-aware compaction monitoring.",
                        session_id="memory/activity/2026/03/29/chat-002",
                        label="Proxy compaction",
                    )
                )
            )

        checkpoint = (
            repo_root
            / "memory"
            / "activity"
            / "alex"
            / "2026"
            / "03"
            / "29"
            / "chat-002"
            / "checkpoint.md"
        ).read_text(encoding="utf-8")
        self.assertEqual(payload["new_state"]["user_id"], "alex")
        self.assertEqual(
            payload["new_state"]["session_id"], "memory/activity/alex/2026/03/29/chat-002"
        )
        self.assertIn("<!-- user_id: alex -->\n", checkpoint)

    def test_memory_record_session_persists_user_id_in_summary_and_access_entries(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/activity/SUMMARY.md": "# Chats\n## Structure\n",
                "memory/knowledge/topic.md": "# Topic\n",
            }
        )
        with mock.patch.dict(os.environ, {"MEMORY_USER_ID": "alex"}, clear=False):
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_record_session"](
                        session_id="memory/activity/2026/03/20/chat-002",
                        summary="# Session Summary\n\nDid the work.\n",
                        key_topics="semantic-tools,wrapup",
                        access_entries=[
                            {
                                "file": "memory/knowledge/topic.md",
                                "task": "session wrap-up",
                                "helpfulness": 0.8,
                                "note": "Relevant context for summary.",
                            }
                        ],
                    )
                )
            )

        session_summary = (
            repo_root
            / "memory"
            / "activity"
            / "alex"
            / "2026"
            / "03"
            / "20"
            / "chat-002"
            / "SUMMARY.md"
        ).read_text(encoding="utf-8")
        activity_summary = (repo_root / "memory" / "activity" / "SUMMARY.md").read_text(
            encoding="utf-8"
        )
        access_entry = json.loads(
            (repo_root / "memory" / "knowledge" / "ACCESS.jsonl")
            .read_text(encoding="utf-8")
            .strip()
        )
        self.assertEqual(payload["new_state"]["user_id"], "alex")
        self.assertEqual(
            payload["new_state"]["session_id"], "memory/activity/alex/2026/03/20/chat-002"
        )
        self.assertIn("user_id: alex\n", session_summary)
        self.assertIn("user `alex`", activity_summary)
        self.assertEqual(access_entry["user_id"], "alex")
        self.assertEqual(access_entry["session_id"], "memory/activity/alex/2026/03/20/chat-002")

    def test_memory_query_dialogue_reads_namespaced_sessions(self) -> None:
        repo_root = self._init_repo({"memory/activity/SUMMARY.md": "# Chats\n## Structure\n"})
        with mock.patch.dict(os.environ, {"MEMORY_USER_ID": "alex"}, clear=False):
            tools = self._create_tools(repo_root)
            asyncio.run(
                tools["memory_record_session"](
                    session_id="memory/activity/2026/03/21/chat-003",
                    summary="# Session Summary\n\nCaptured a dialogue row.\n",
                    key_topics="dialogue",
                    dialogue_entries=[
                        {
                            "role": "user",
                            "timestamp": "2026-03-21T10:00:00Z",
                            "first_line": "Hello there",
                            "token_estimate": 2,
                            "tool_calls_in_turn": [],
                            "is_empty": False,
                        }
                    ],
                )
            )
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_query_dialogue"](
                        sessions=["memory/activity/alex/2026/03/21/chat-003"]
                    )
                )
            )

        self.assertEqual(payload["total_matched"], 1)
        self.assertEqual(
            payload["entries"][0]["session_id"], "memory/activity/alex/2026/03/21/chat-003"
        )

    def test_create_mcp_records_and_checks_out_session_branch_when_enabled(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        captured: dict[str, object] = {}
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        def fake_read_register(mcp, get_repo, get_root, session_state=None):
            captured["read"] = session_state
            return {}

        def fake_semantic_register(mcp, get_repo, get_root, session_state=None):
            captured["semantic"] = session_state
            return {}

        with (
            mock.patch.dict(
                os.environ,
                {
                    "MEMORY_USER_ID": "alex",
                    "MEMORY_SESSION_ID": "memory/activity/2026/03/29/chat-002",
                    "MEMORY_ENABLE_SESSION_BRANCHES": "1",
                },
                clear=False,
            ),
            mock.patch.object(self.server.read_tools, "register", side_effect=fake_read_register),
            mock.patch.object(self.server.semantic, "register", side_effect=fake_semantic_register),
        ):
            _, _, _, repo = self.server.create_mcp(repo_root=repo_root)

        state = cast(Any, captured["read"])
        self.assertIs(captured["read"], captured["semantic"])
        self.assertEqual(repo.current_branch_name(), session_branch)
        self.assertEqual(state.publication_base_branch, "alex")
        self.assertEqual(state.publication_base_ref, "refs/heads/alex")
        self.assertEqual(state.publication_session_branch, session_branch)
        self.assertEqual(state.publication_session_branch_ref, f"refs/heads/{session_branch}")

    def test_create_mcp_rejects_dirty_worktree_when_session_branching_enabled(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        (repo_root / "INIT.md").write_text("# Dirty init\n", encoding="utf-8")

        with mock.patch.dict(
            os.environ,
            {
                "MEMORY_USER_ID": "alex",
                "MEMORY_SESSION_ID": "memory/activity/2026/03/29/chat-002",
                "MEMORY_ENABLE_SESSION_BRANCHES": "1",
            },
            clear=False,
        ):
            with self.assertRaises(self.errors.StagingError) as ctx:
                self.server.create_mcp(repo_root=repo_root)

        self.assertIn("staged or unstaged tracked changes", str(ctx.exception))

    def test_memory_commit_uses_session_branch_when_enabled(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        seed_sha = subprocess.run(
            ["git", "rev-parse", "refs/heads/alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        with mock.patch.dict(
            os.environ,
            {
                "MEMORY_USER_ID": "alex",
                "MEMORY_SESSION_ID": "memory/activity/2026/03/29/chat-002",
                "MEMORY_ENABLE_SESSION_BRANCHES": "1",
            },
            clear=False,
        ):
            _, tools, _, repo = self.server.create_mcp(
                repo_root=repo_root,
                enable_raw_write_tools=True,
            )
            asyncio.run(
                cast(Any, tools["memory_write"])(
                    path="memory/knowledge/_unverified/session-branch-note.md",
                    content="# Session branch note\n",
                )
            )
            asyncio.run(
                cast(Any, tools["memory_commit"])(message="[knowledge] session branch note")
            )

        base_sha = subprocess.run(
            ["git", "rev-parse", "refs/heads/alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        session_sha = subprocess.run(
            ["git", "rev-parse", f"refs/heads/{session_branch}"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        session_subject = subprocess.run(
            ["git", "log", "-1", "--pretty=%s", session_branch],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        self.assertEqual(repo.current_branch_name(), session_branch)
        self.assertEqual(base_sha, seed_sha)
        self.assertNotEqual(session_sha, seed_sha)
        self.assertEqual(session_subject, "[knowledge] session branch note")


if __name__ == "__main__":
    unittest.main()
