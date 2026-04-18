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

import core.tools.agent_memory_mcp.git_repo as git_repo_module  # noqa: E402
from core.tools.agent_memory_mcp import server as server_module  # noqa: E402
from core.tools.agent_memory_mcp.errors import StagingError  # noqa: E402
from core.tools.agent_memory_mcp.git_repo import GitRepo  # noqa: E402
from core.tools.agent_memory_mcp.server import create_mcp  # noqa: E402


class MultiUserConcurrentWriteLockTests(unittest.TestCase):
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
                "GIT_AUTHOR_DATE": "2026-04-15T12:00:00+00:00",
                "GIT_COMMITTER_DATE": "2026-04-15T12:00:00+00:00",
            },
        )
        return content_root

    def _git_root(self, repo_root: Path) -> Path:
        return repo_root if (repo_root / ".git").exists() else repo_root.parent

    def _add_linked_worktree(self, repo_root: Path, name: str, *, ref: str = "HEAD") -> Path:
        git_root = self._git_root(repo_root)
        worktree_root = self.temp_root / name
        subprocess.run(
            ["git", "worktree", "add", str(worktree_root), ref],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return worktree_root / "core"

    def _create_tools(self, repo_root: Path) -> tuple[dict[str, object], GitRepo]:
        _, tools, _, repo = create_mcp(repo_root=repo_root, enable_raw_write_tools=True)
        return tools, repo

    def test_linked_worktrees_share_common_engram_state_dir(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        _, main_repo = self._create_tools(repo_root)
        linked_repo_root = self._add_linked_worktree(repo_root, "linked")
        _, linked_repo = self._create_tools(linked_repo_root)

        main_state_dir = main_repo.engram_state_dir(create=True)
        linked_state_dir = linked_repo.engram_state_dir(create=True)

        self.assertEqual(main_repo.git_common_dir, linked_repo.git_common_dir)
        self.assertNotEqual(main_repo.git_dir, linked_repo.git_dir)
        self.assertTrue(main_state_dir.samefile(linked_state_dir))

    def test_cross_worktree_commit_blocks_on_repo_common_write_lock(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        _, main_repo = self._create_tools(repo_root)
        linked_repo_root = self._add_linked_worktree(repo_root, "linked")
        linked_tools, linked_repo = self._create_tools(linked_repo_root)

        asyncio.run(
            cast(Any, linked_tools["memory_write"])(
                path="memory/knowledge/_unverified/linked-note.md",
                content="# Linked note\n",
            )
        )

        lock_path = main_repo._write_lock_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("pid=999\npurpose=test\n", encoding="utf-8")
        original_timeout = getattr(git_repo_module, "_WRITE_LOCK_TIMEOUT_SECONDS")
        setattr(git_repo_module, "_WRITE_LOCK_TIMEOUT_SECONDS", 0.0)
        self.addCleanup(setattr, git_repo_module, "_WRITE_LOCK_TIMEOUT_SECONDS", original_timeout)
        self.addCleanup(lock_path.unlink)

        self.assertEqual(lock_path, linked_repo._write_lock_path())
        with self.assertRaises(StagingError) as ctx:
            asyncio.run(cast(Any, linked_tools["memory_commit"])(message="[knowledge] linked note"))

        self.assertIn("Another writer is already publishing changes", str(ctx.exception))

    def test_memory_commit_reports_repo_common_writer_lock_metadata(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        linked_repo_root = self._add_linked_worktree(repo_root, "linked")
        linked_tools, _ = self._create_tools(linked_repo_root)

        asyncio.run(
            cast(Any, linked_tools["memory_write"])(
                path="memory/knowledge/_unverified/linked-note.md",
                content="# Linked note\n",
            )
        )
        payload = cast(
            dict[str, Any],
            json.loads(
                asyncio.run(
                    cast(Any, linked_tools["memory_commit"])(message="[knowledge] linked note")
                )
            ),
        )

        self.assertEqual(payload["publication"]["writer_lock"], "exclusive-repo-common-dir")

    def test_create_mcp_captures_publication_baseline_for_linked_worktree(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        git_root = self._git_root(repo_root)
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        linked_repo_root = self._add_linked_worktree(repo_root, "linked")
        captured: dict[str, object] = {}

        def fake_read_register(mcp, get_repo, get_root, session_state=None):
            captured["read"] = session_state
            return {}

        def fake_semantic_register(mcp, get_repo, get_root, session_state=None):
            captured["semantic"] = session_state
            return {}

        with (
            mock.patch.object(server_module.read_tools, "register", side_effect=fake_read_register),
            mock.patch.object(
                server_module.semantic, "register", side_effect=fake_semantic_register
            ),
        ):
            server_module.create_mcp(repo_root=linked_repo_root)

        state = cast(Any, captured["read"])
        linked_repo = GitRepo(linked_repo_root, content_prefix="core")

        self.assertIs(captured["read"], captured["semantic"])
        self.assertIsNone(state.publication_base_branch)
        self.assertIsNone(state.publication_base_ref)
        self.assertEqual(state.publication_worktree_root, str(linked_repo.root))
        self.assertEqual(state.publication_git_common_dir, str(linked_repo.git_common_dir))

    def test_create_mcp_rejects_session_branching_for_detached_linked_worktree(self) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        git_root = self._git_root(repo_root)
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        linked_repo_root = self._add_linked_worktree(repo_root, "linked")

        with mock.patch.dict(
            os.environ,
            {
                "MEMORY_USER_ID": "alex",
                "MEMORY_SESSION_ID": "memory/activity/2026/04/15/chat-001",
                "MEMORY_ENABLE_SESSION_BRANCHES": "1",
            },
            clear=False,
        ):
            with self.assertRaises(StagingError) as ctx:
                server_module.create_mcp(repo_root=linked_repo_root)

        self.assertIn("attached base branch at startup", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
