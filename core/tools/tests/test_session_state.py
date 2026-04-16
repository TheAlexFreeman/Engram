from __future__ import annotations

import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_module(name: str) -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module(name)


class SessionStateTests(unittest.TestCase):
    module: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.module = _load_module("engram_mcp.agent_memory_mcp.session_state")
        except ModuleNotFoundError as exc:
            raise unittest.SkipTest(f"session state dependencies unavailable: {exc.name}") from exc

    def test_session_state_tracks_touched_files_and_checkpoint_metadata(self) -> None:
        start = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
        state = self.module.SessionState(session_start=start)

        with mock.patch.object(self.module, "_utcnow", return_value=start + timedelta(minutes=6)):
            state.record_tool_call()
            state.record_read("memory/users/profile.md")
            state.record_tool_call()
            state.record_write("memory/users/profile.md")
            state.record_checkpoint()
            state.record_flush()
            snapshot = state.snapshot()

        self.assertEqual(state.files_read, ["memory/users/profile.md"])
        self.assertEqual(state.files_written, ["memory/users/profile.md"])
        self.assertEqual(state.tool_calls, 2)
        self.assertEqual(state.checkpoints, 1)
        self.assertIsNotNone(state.last_checkpoint)
        self.assertIsNotNone(state.last_flush)
        self.assertFalse(state.flush_recommended)
        self.assertEqual(snapshot["checkpoints_this_session"], 1)
        self.assertEqual(snapshot["tool_calls_since_checkpoint"], 0)
        self.assertEqual(snapshot["session_duration_minutes"], 6)

    def test_session_state_recommends_flush_when_checkpoint_is_stale(self) -> None:
        start = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
        state = self.module.SessionState(session_start=start)

        with mock.patch.object(self.module, "_utcnow", return_value=start + timedelta(minutes=12)):
            for _ in range(11):
                state.record_tool_call()
            advisory = state.get_advisory()

        self.assertTrue(advisory.flush_recommended)
        self.assertTrue(advisory.checkpoint_stale)
        self.assertEqual(advisory.tool_calls_since_checkpoint, 11)
        self.assertEqual(advisory.session_duration_minutes, 12)

    def test_reset_clears_all_session_tracking_fields(self) -> None:
        start = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
        reset_time = start + timedelta(minutes=9)
        state = self.module.SessionState(session_start=start)

        with mock.patch.object(self.module, "_utcnow", return_value=start + timedelta(minutes=5)):
            state.record_tool_call()
            state.record_read("memory/knowledge/topic.md")
            state.record_write("memory/working/CURRENT.md")
            state.record_checkpoint()
            state.record_flush()
            state.identity_updates = 3

        with mock.patch.object(self.module, "_utcnow", return_value=reset_time):
            payload = state.reset()

        self.assertEqual(state.session_start, reset_time)
        self.assertEqual(state.files_read, [])
        self.assertEqual(state.files_written, [])
        self.assertEqual(state.tool_calls, 0)
        self.assertEqual(state.checkpoints, 0)
        self.assertIsNone(state.last_checkpoint)
        self.assertIsNone(state.last_flush)
        self.assertEqual(state.identity_updates, 0)
        self.assertTrue(payload["reset"])
        self.assertEqual(payload["files_read"], [])
        self.assertEqual(payload["files_written"], [])
        self.assertEqual(payload["tool_calls_this_session"], 0)
        self.assertEqual(payload["checkpoints_this_session"], 0)
        self.assertEqual(payload["identity_updates_this_session"], 0)

    def test_reset_preserves_publication_baseline_fields(self) -> None:
        start = datetime(2026, 3, 28, 12, 0, tzinfo=timezone.utc)
        reset_time = start + timedelta(minutes=9)
        state = self.module.SessionState(
            session_start=start,
            user_id="alex",
            publication_base_branch="main",
            publication_base_ref="refs/heads/main",
            publication_worktree_root="/tmp/repo",
            publication_git_common_dir="/tmp/repo/.git",
            publication_session_branch="engram/sessions/alex/2026-03-28-chat-001",
            publication_session_branch_ref="refs/heads/engram/sessions/alex/2026-03-28-chat-001",
        )

        with mock.patch.object(self.module, "_utcnow", return_value=reset_time):
            payload = state.reset()

        self.assertEqual(state.publication_base_branch, "main")
        self.assertEqual(state.publication_base_ref, "refs/heads/main")
        self.assertEqual(state.publication_worktree_root, "/tmp/repo")
        self.assertEqual(state.publication_git_common_dir, "/tmp/repo/.git")
        self.assertEqual(
            state.publication_session_branch, "engram/sessions/alex/2026-03-28-chat-001"
        )
        self.assertEqual(
            state.publication_session_branch_ref,
            "refs/heads/engram/sessions/alex/2026-03-28-chat-001",
        )
        self.assertEqual(payload["publication_base_branch"], "main")
        self.assertEqual(payload["publication_base_ref"], "refs/heads/main")
        self.assertEqual(payload["publication_worktree_root"], "/tmp/repo")
        self.assertEqual(payload["publication_git_common_dir"], "/tmp/repo/.git")
        self.assertEqual(
            payload["publication_session_branch"],
            "engram/sessions/alex/2026-03-28-chat-001",
        )
        self.assertEqual(
            payload["publication_session_branch_ref"],
            "refs/heads/engram/sessions/alex/2026-03-28-chat-001",
        )


class CreateMcpSessionStateWiringTests(unittest.TestCase):
    server: ModuleType
    session_state_module: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.server = _load_module("engram_mcp.agent_memory_mcp.server")
            cls.session_state_module = _load_module("engram_mcp.agent_memory_mcp.session_state")
        except ModuleNotFoundError as exc:
            raise unittest.SkipTest(
                f"agent_memory_mcp dependencies unavailable: {exc.name}"
            ) from exc

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)

    def _init_repo(self) -> Path:
        temp_root = Path(self._tmpdir.name) / "repo"
        content_root = temp_root / "core"
        content_root.mkdir(parents=True, exist_ok=True)
        (content_root / "INIT.md").write_text("# Session Init\n", encoding="utf-8")

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

    def test_create_mcp_shares_one_session_state_between_read_and_semantic_tools(self) -> None:
        repo_root = self._init_repo()
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        captured: dict[str, object] = {}

        def fake_read_register(mcp, get_repo, get_root, session_state=None):
            captured["read"] = session_state
            return {}

        def fake_semantic_register(mcp, get_repo, get_root, session_state=None):
            captured["semantic"] = session_state
            return {}

        with (
            mock.patch.object(self.server.read_tools, "register", side_effect=fake_read_register),
            mock.patch.object(self.server.semantic, "register", side_effect=fake_semantic_register),
        ):
            self.server.create_mcp(repo_root=repo_root)

        self.assertIs(captured["read"], captured["semantic"])
        self.assertIsInstance(captured["read"], self.session_state_module.SessionState)
        state = cast(Any, captured["read"])
        self.assertEqual(state.publication_base_branch, "alex")
        self.assertEqual(state.publication_base_ref, "refs/heads/alex")
        self.assertEqual(Path(state.publication_worktree_root).resolve(), git_root.resolve())
        self.assertEqual(
            Path(state.publication_git_common_dir).resolve(), (git_root / ".git").resolve()
        )


if __name__ == "__main__":
    unittest.main()
