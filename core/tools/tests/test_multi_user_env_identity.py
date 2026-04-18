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

    def _git_root(self, repo_root: Path) -> Path:
        return repo_root.parent

    def _rename_branch(self, repo_root: Path, name: str = "alex") -> Path:
        git_root = self._git_root(repo_root)
        subprocess.run(
            ["git", "branch", "-M", name],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return git_root

    def _rev_parse(self, git_root: Path, ref: str) -> str:
        return subprocess.run(
            ["git", "rev-parse", ref],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def _diverge_base_branch(self, git_root: Path, branch: str = "alex") -> str:
        base_ref = f"refs/heads/{branch}"
        base_sha_before = self._rev_parse(git_root, base_ref)
        base_tree = self._rev_parse(git_root, f"{base_ref}^{{tree}}")
        diverged_sha = subprocess.run(
            ["git", "commit-tree", base_tree, "-p", base_sha_before, "-m", "diverged base"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "update-ref", base_ref, diverged_sha, base_sha_before],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return diverged_sha

    def _write_and_commit(self, repo_root: Path, rel_path: str, content: str, message: str) -> str:
        target = repo_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        git_root = self._git_root(repo_root)
        subprocess.run(
            ["git", "add", "."],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return self._rev_parse(git_root, "HEAD")

    def _session_branch_env(
        self, session_id: str = "memory/activity/2026/03/29/chat-002"
    ) -> dict[str, str]:
        return {
            "MEMORY_USER_ID": "alex",
            "MEMORY_SESSION_ID": session_id,
            "MEMORY_ENABLE_SESSION_BRANCHES": "1",
        }

    def _aggregation_fixture_files(self) -> dict[str, str]:
        return {
            "memory/knowledge/topic.md": "# Topic\n",
            "memory/working/projects/demo.md": "# Demo\n",
            "memory/skills/session-start/SKILL.md": "# Session Start\n",
            "memory/knowledge/SUMMARY.md": "# Knowledge\n\n## Usage patterns\n\n_No access data yet._\n",
            "memory/working/projects/SUMMARY.md": "# Plans\n\n## Usage patterns\n\n_No access data yet._\n",
            "memory/skills/SUMMARY.md": "# Skills\n\n## Usage patterns\n\n_No access data yet._\n",
            "memory/knowledge/ACCESS.jsonl": "\n".join(
                [
                    json.dumps(
                        {
                            "date": "2026-03-18",
                            "session_id": "memory/activity/2026/03/18/chat-001",
                            "file": "memory/knowledge/topic.md",
                            "helpfulness": 0.8,
                        }
                    ),
                    json.dumps(
                        {
                            "date": "2026-03-19",
                            "file": "memory/knowledge/topic.md",
                            "helpfulness": 0.8,
                        }
                    ),
                    json.dumps(
                        {
                            "date": "2026-03-20",
                            "session_id": "memory/activity/2026/03/20/chat-001",
                            "file": "memory/knowledge/topic.md",
                            "helpfulness": 0.8,
                        }
                    ),
                ]
            )
            + "\n",
            "memory/working/projects/ACCESS.jsonl": "\n".join(
                [
                    json.dumps(
                        {
                            "date": "2026-03-18",
                            "session_id": "memory/activity/2026/03/18/chat-001",
                            "file": "memory/working/projects/demo.md",
                            "helpfulness": 0.7,
                        }
                    ),
                    json.dumps(
                        {
                            "date": "2026-03-19",
                            "file": "memory/working/projects/demo.md",
                            "helpfulness": 0.7,
                        }
                    ),
                    json.dumps(
                        {
                            "date": "2026-03-20",
                            "session_id": "memory/activity/2026/03/20/chat-001",
                            "file": "memory/working/projects/demo.md",
                            "helpfulness": 0.7,
                        }
                    ),
                ]
            )
            + "\n",
            "memory/skills/ACCESS.jsonl": "\n".join(
                [
                    json.dumps(
                        {
                            "date": "2026-03-18",
                            "session_id": "memory/activity/2026/03/18/chat-001",
                            "file": "memory/skills/session-start/SKILL.md",
                            "helpfulness": 0.9,
                        }
                    ),
                    json.dumps(
                        {
                            "date": "2026-03-19",
                            "file": "memory/skills/session-start/SKILL.md",
                            "helpfulness": 0.9,
                        }
                    ),
                    json.dumps(
                        {
                            "date": "2026-03-20",
                            "session_id": "memory/activity/2026/03/20/chat-001",
                            "file": "memory/skills/session-start/SKILL.md",
                            "helpfulness": 0.9,
                        }
                    ),
                ]
            )
            + "\n",
        }

    def _periodic_review_fixture_files(self) -> dict[str, str]:
        return {
            "core/INIT.md": """# Home

## Current active stage: Exploration

_Last assessed: 2026-03-01 — Exploration retained_

## Last periodic review

**Date:** 2026-03-01

| Parameter | Active value | Stage |
|---|---|---|
| Low-trust retirement threshold | 120 days | Exploration |
| Medium-trust flagging threshold | 180 days | Exploration |
| Staleness trigger (no access) | 120 days | Exploration |
| Aggregation trigger | 15 entries | Exploration |
| Identity churn alarm | 5 traits/session | Exploration |
| Knowledge flooding alarm | 5 files/day | Exploration |
| Task similarity method | Session co-occurrence | Exploration |
| Cluster co-retrieval threshold | 3 sessions | Exploration |

## Active task similarity method

**Method:** Session co-occurrence
""",
            "core/governance/belief-diff-log.md": "# Belief Diff Log\n",
            "core/governance/review-queue.md": "# Review Queue\n\n_No pending items._\n",
        }

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

    def test_create_mcp_restores_original_base_branch_on_session_branch_restart(self) -> None:
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

        with mock.patch.dict(
            os.environ,
            {
                "MEMORY_USER_ID": "alex",
                "MEMORY_SESSION_ID": "memory/activity/2026/03/29/chat-002",
                "MEMORY_ENABLE_SESSION_BRANCHES": "1",
            },
            clear=False,
        ):
            _, _, _, first_repo = self.server.create_mcp(repo_root=repo_root)

            def fake_read_register(mcp, get_repo, get_root, session_state=None):
                captured["read"] = session_state
                return {}

            def fake_semantic_register(mcp, get_repo, get_root, session_state=None):
                captured["semantic"] = session_state
                return {}

            with (
                mock.patch.object(
                    self.server.read_tools, "register", side_effect=fake_read_register
                ),
                mock.patch.object(
                    self.server.semantic, "register", side_effect=fake_semantic_register
                ),
            ):
                _, _, _, restarted_repo = self.server.create_mcp(repo_root=repo_root)

        metadata = json.loads(
            first_repo.session_branch_metadata_path(session_branch).read_text(encoding="utf-8")
        )
        state = cast(Any, captured["read"])
        self.assertIs(captured["read"], captured["semantic"])
        self.assertEqual(restarted_repo.current_branch_name(), session_branch)
        self.assertEqual(metadata["base_branch"], "alex")
        self.assertEqual(metadata["base_ref"], "refs/heads/alex")
        self.assertEqual(state.publication_base_branch, "alex")
        self.assertEqual(state.publication_base_ref, "refs/heads/alex")
        self.assertEqual(state.publication_session_branch, session_branch)
        self.assertEqual(state.publication_session_branch_ref, f"refs/heads/{session_branch}")

    def test_create_mcp_rejects_session_branch_restart_without_persisted_base_metadata(
        self,
    ) -> None:
        repo_root = self._init_repo({"memory/knowledge/README.md": "# Knowledge\n"})
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            _, _, _, repo = self.server.create_mcp(repo_root=repo_root)
            repo.session_branch_metadata_path(session_branch).unlink()

            with self.assertRaises(self.errors.StagingError) as ctx:
                self.server.create_mcp(repo_root=repo_root)

        self.assertIn("without persisted base metadata", str(ctx.exception))

    def test_memory_session_flush_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/USER.md": "# User\n",
                "memory/knowledge/README.md": "# Knowledge\n",
            }
        )
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_session_flush"](
                        summary="Decision: flush should advance the preserved base branch.",
                        session_id="memory/activity/2026/03/29/chat-002",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_record_session_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/activity/SUMMARY.md": "# Chats\n## Structure\n",
                "memory/knowledge/topic.md": "# Topic\n",
            }
        )
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_record_session"](
                        session_id="memory/activity/2026/03/29/chat-002",
                        summary="# Session Summary\n\nRecorded the session.\n",
                        key_topics="merge",
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, session_sha)
        self.assertEqual(
            payload["new_state"]["session_id"], "memory/activity/alex/2026/03/29/chat-002"
        )
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_record_chat_summary_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo({"memory/activity/SUMMARY.md": "# Chats\n## Structure\n"})
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_record_chat_summary"](
                        session_id="memory/activity/2026/03/29/chat-002",
                        summary="# Session Summary\n\nRecorded the summary.\n",
                        key_topics="merge",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, session_sha)
        self.assertEqual(
            payload["new_state"]["session_id"], "memory/activity/alex/2026/03/29/chat-002"
        )
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_record_reflection_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo({"memory/activity/SUMMARY.md": "# Chats\n## Structure\n"})
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            asyncio.run(
                tools["memory_record_chat_summary"](
                    session_id="memory/activity/2026/03/29/chat-002",
                    summary="# Session Summary\n\nRecorded the summary.\n",
                )
            )
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_record_reflection"](
                        session_id="memory/activity/2026/03/29/chat-002",
                        memory_retrieved="Referenced the prior summary.",
                        memory_influence="Guided the implementation choice.",
                        outcome_quality="Good outcome.",
                        gaps_noticed="Need better eval coverage.",
                        system_observations="No tooling surprises.",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, session_sha)
        self.assertEqual(
            payload["new_state"]["reflection_path"],
            "memory/activity/alex/2026/03/29/chat-002/reflection.md",
        )
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_append_scratchpad_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo({"memory/working/USER.md": "# User\n"})
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_append_scratchpad"](
                        target="current",
                        content="Appended scratchpad note.",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, session_sha)
        self.assertEqual(payload["new_state"]["target"], "memory/working/alex/CURRENT.md")
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_log_access_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/literature/galatea.md": "# Galatea\n",
                "memory/knowledge/ACCESS.jsonl": "",
            }
        )
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_log_access"](
                        file="memory/knowledge/literature/galatea.md",
                        task="User asked about AI literature references",
                        helpfulness=0.8,
                        note="Core reference for the answer.",
                        session_id="memory/activity/2026/03/29/chat-002",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_log_access_batch_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/working/projects/demo.md": "# Demo\n",
                "memory/activity/CURRENT_SESSION": "memory/activity/2026/03/29/chat-002\n",
            }
        )
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_log_access_batch"](
                        access_entries=[
                            {
                                "file": "memory/knowledge/lit/foo.md",
                                "task": "batch test",
                                "helpfulness": 0.8,
                                "note": "knowledge entry",
                            },
                            {
                                "file": "memory/working/projects/demo.md",
                                "task": "batch test",
                                "helpfulness": 0.4,
                                "note": "plan entry",
                            },
                        ],
                        session_id="memory/activity/2026/03/29/chat-002",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_session_flush_reports_blocked_fast_forward_when_base_diverged(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/working/USER.md": "# User\n",
                "memory/knowledge/README.md": "# Knowledge\n",
            }
        )
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            base_sha_before = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            base_tree = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex^{tree}"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            diverged_sha = subprocess.run(
                ["git", "commit-tree", base_tree, "-p", base_sha_before, "-m", "diverged base"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "update-ref", "refs/heads/alex", diverged_sha, base_sha_before],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_session_flush"](
                        summary="Decision: flush should report a blocked fast-forward when the base diverges.",
                        session_id="memory/activity/2026/03/29/chat-002",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )

    def test_memory_record_session_reports_blocked_fast_forward_when_base_diverged(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/activity/SUMMARY.md": "# Chats\n## Structure\n",
                "memory/knowledge/topic.md": "# Topic\n",
            }
        )
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            base_sha_before = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            base_tree = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex^{tree}"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            diverged_sha = subprocess.run(
                ["git", "commit-tree", base_tree, "-p", base_sha_before, "-m", "diverged base"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "update-ref", "refs/heads/alex", diverged_sha, base_sha_before],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_record_session"](
                        session_id="memory/activity/2026/03/29/chat-002",
                        summary="# Session Summary\n\nRecorded the session.\n",
                        key_topics="merge",
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )

    def test_memory_record_chat_summary_reports_blocked_fast_forward_when_base_diverged(
        self,
    ) -> None:
        repo_root = self._init_repo({"memory/activity/SUMMARY.md": "# Chats\n## Structure\n"})
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            base_sha_before = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            base_tree = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex^{tree}"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            diverged_sha = subprocess.run(
                ["git", "commit-tree", base_tree, "-p", base_sha_before, "-m", "diverged base"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "update-ref", "refs/heads/alex", diverged_sha, base_sha_before],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_record_chat_summary"](
                        session_id="memory/activity/2026/03/29/chat-002",
                        summary="# Session Summary\n\nRecorded the summary.\n",
                        key_topics="merge",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )

    def test_memory_record_reflection_reports_blocked_fast_forward_when_base_diverged(
        self,
    ) -> None:
        repo_root = self._init_repo({"memory/activity/SUMMARY.md": "# Chats\n## Structure\n"})
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            asyncio.run(
                tools["memory_record_chat_summary"](
                    session_id="memory/activity/2026/03/29/chat-002",
                    summary="# Session Summary\n\nRecorded the summary.\n",
                )
            )
            base_sha_before = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            base_tree = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex^{tree}"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            diverged_sha = subprocess.run(
                ["git", "commit-tree", base_tree, "-p", base_sha_before, "-m", "diverged base"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "update-ref", "refs/heads/alex", diverged_sha, base_sha_before],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_record_reflection"](
                        session_id="memory/activity/2026/03/29/chat-002",
                        memory_retrieved="Referenced the prior summary.",
                        memory_influence="Guided the implementation choice.",
                        outcome_quality="Good outcome.",
                        gaps_noticed="Need better eval coverage.",
                        system_observations="No tooling surprises.",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )

    def test_memory_log_access_reports_blocked_fast_forward_when_base_diverged(self) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/literature/galatea.md": "# Galatea\n",
                "memory/knowledge/ACCESS.jsonl": "",
            }
        )
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            base_sha_before = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            base_tree = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex^{tree}"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            diverged_sha = subprocess.run(
                ["git", "commit-tree", base_tree, "-p", base_sha_before, "-m", "diverged base"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "update-ref", "refs/heads/alex", diverged_sha, base_sha_before],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_log_access"](
                        file="memory/knowledge/literature/galatea.md",
                        task="User asked about AI literature references",
                        helpfulness=0.8,
                        note="Core reference for the answer.",
                        session_id="memory/activity/2026/03/29/chat-002",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )

    def test_memory_log_access_batch_reports_blocked_fast_forward_when_base_diverged(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "memory/knowledge/lit/foo.md": "# Foo\n",
                "memory/working/projects/demo.md": "# Demo\n",
                "memory/activity/CURRENT_SESSION": "memory/activity/2026/03/29/chat-002\n",
            }
        )
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            base_sha_before = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            base_tree = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex^{tree}"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            diverged_sha = subprocess.run(
                ["git", "commit-tree", base_tree, "-p", base_sha_before, "-m", "diverged base"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "update-ref", "refs/heads/alex", diverged_sha, base_sha_before],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_log_access_batch"](
                        access_entries=[
                            {
                                "file": "memory/knowledge/lit/foo.md",
                                "task": "batch test",
                                "helpfulness": 0.8,
                                "note": "knowledge entry",
                            },
                            {
                                "file": "memory/working/projects/demo.md",
                                "task": "batch test",
                                "helpfulness": 0.4,
                                "note": "plan entry",
                            },
                        ],
                        session_id="memory/activity/2026/03/29/chat-002",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )

    def test_memory_append_scratchpad_reports_blocked_fast_forward_when_base_diverged(
        self,
    ) -> None:
        repo_root = self._init_repo({"memory/working/USER.md": "# User\n"})
        git_root = repo_root.parent
        subprocess.run(
            ["git", "branch", "-M", "alex"],
            cwd=git_root,
            check=True,
            capture_output=True,
            text=True,
        )
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
            tools = self._create_tools(repo_root)
            base_sha_before = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            base_tree = subprocess.run(
                ["git", "rev-parse", "refs/heads/alex^{tree}"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            diverged_sha = subprocess.run(
                ["git", "commit-tree", base_tree, "-p", base_sha_before, "-m", "diverged base"],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            subprocess.run(
                ["git", "update-ref", "refs/heads/alex", diverged_sha, base_sha_before],
                cwd=git_root,
                check=True,
                capture_output=True,
                text=True,
            )

            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_append_scratchpad"](
                        target="current",
                        content="Appended scratchpad note.",
                    )
                )
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
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )

    def test_memory_flag_for_review_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo(
            {
                "governance/review-queue.md": "# Review Queue\n\n_No pending items._\n",
                "memory/working/projects/demo.md": "# Demo\n",
            }
        )
        git_root = self._rename_branch(repo_root)
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        with mock.patch.dict(os.environ, self._session_branch_env(), clear=False):
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_flag_for_review"](
                        path="memory/working/projects/demo.md",
                        reason="Needs human review before promotion.",
                        priority="urgent",
                    )
                )
            )

        base_sha = self._rev_parse(git_root, "refs/heads/alex")
        session_sha = self._rev_parse(git_root, f"refs/heads/{session_branch}")
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_flag_for_review_reports_blocked_fast_forward_when_base_diverged(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "governance/review-queue.md": "# Review Queue\n\n_No pending items._\n",
                "memory/working/projects/demo.md": "# Demo\n",
            }
        )
        git_root = self._rename_branch(repo_root)
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        with mock.patch.dict(os.environ, self._session_branch_env(), clear=False):
            tools = self._create_tools(repo_root)
            diverged_sha = self._diverge_base_branch(git_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_flag_for_review"](
                        path="memory/working/projects/demo.md",
                        reason="Needs human review before promotion.",
                        priority="urgent",
                    )
                )
            )

        base_sha = self._rev_parse(git_root, "refs/heads/alex")
        session_sha = self._rev_parse(git_root, f"refs/heads/{session_branch}")
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )

    def test_memory_resolve_review_item_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo(
            {
                "governance/review-queue.md": """# Review Queue

### [2026-03-20] Review memory/working/projects/demo.md
**Item ID:** 2026-03-20-review-memory-working-projects-demo-md
**Type:** proposed
**File:** memory/working/projects/demo.md
**Priority:** normal
**Reason:** Review it.
**Status:** pending
""",
            }
        )
        git_root = self._rename_branch(repo_root)
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        with mock.patch.dict(os.environ, self._session_branch_env(), clear=False):
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_resolve_review_item"](
                        item_id="2026-03-20-review-memory-working-projects-demo-md",
                        resolution_note="Handled during maintenance.",
                    )
                )
            )

        base_sha = self._rev_parse(git_root, "refs/heads/alex")
        session_sha = self._rev_parse(git_root, f"refs/heads/{session_branch}")
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_resolve_review_item_reports_blocked_fast_forward_when_base_diverged(
        self,
    ) -> None:
        repo_root = self._init_repo(
            {
                "governance/review-queue.md": """# Review Queue

### [2026-03-20] Review memory/working/projects/demo.md
**Item ID:** 2026-03-20-review-memory-working-projects-demo-md
**Type:** proposed
**File:** memory/working/projects/demo.md
**Priority:** normal
**Reason:** Review it.
**Status:** pending
""",
            }
        )
        git_root = self._rename_branch(repo_root)
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        with mock.patch.dict(os.environ, self._session_branch_env(), clear=False):
            tools = self._create_tools(repo_root)
            diverged_sha = self._diverge_base_branch(git_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_resolve_review_item"](
                        item_id="2026-03-20-review-memory-working-projects-demo-md",
                        resolution_note="Handled during maintenance.",
                    )
                )
            )

        base_sha = self._rev_parse(git_root, "refs/heads/alex")
        session_sha = self._rev_parse(git_root, f"refs/heads/{session_branch}")
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )

    def test_memory_run_aggregation_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo(self._aggregation_fixture_files())
        git_root = self._rename_branch(repo_root)
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        with mock.patch.dict(os.environ, self._session_branch_env(), clear=False):
            tools = self._create_tools(repo_root)
            payload = self._load_tool_payload(
                asyncio.run(tools["memory_run_aggregation"](dry_run=False))
            )

        base_sha = self._rev_parse(git_root, "refs/heads/alex")
        session_sha = self._rev_parse(git_root, f"refs/heads/{session_branch}")
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, session_sha)
        self.assertEqual(payload["new_state"]["entries_processed"], 9)
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_run_aggregation_reports_blocked_fast_forward_when_base_diverged(
        self,
    ) -> None:
        repo_root = self._init_repo(self._aggregation_fixture_files())
        git_root = self._rename_branch(repo_root)
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        with mock.patch.dict(os.environ, self._session_branch_env(), clear=False):
            tools = self._create_tools(repo_root)
            diverged_sha = self._diverge_base_branch(git_root)
            payload = self._load_tool_payload(
                asyncio.run(tools["memory_run_aggregation"](dry_run=False))
            )

        base_sha = self._rev_parse(git_root, "refs/heads/alex")
        session_sha = self._rev_parse(git_root, f"refs/heads/{session_branch}")
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )

    def test_memory_record_periodic_review_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo(self._periodic_review_fixture_files())
        git_root = self._rename_branch(repo_root)
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        with mock.patch.dict(os.environ, self._session_branch_env(), clear=False):
            tools = self._create_tools(repo_root)
            preview = self._load_tool_payload(
                asyncio.run(
                    tools["memory_record_periodic_review"](
                        review_date="2026-03-19",
                        assessment_summary="Exploration retained after review.",
                        belief_diff_entry="## [2026-03-19] Periodic review\n",
                        review_queue_entries="### [2026-03-19] Follow-up\n**Status:** pending\n",
                        preview=True,
                    )
                )
            )
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_record_periodic_review"](
                        review_date="2026-03-19",
                        assessment_summary="Exploration retained after review.",
                        belief_diff_entry="## [2026-03-19] Periodic review\n",
                        review_queue_entries="### [2026-03-19] Follow-up\n**Status:** pending\n",
                        approval_token=preview["new_state"]["approval_token"],
                    )
                )
            )

        base_sha = self._rev_parse(git_root, "refs/heads/alex")
        session_sha = self._rev_parse(git_root, f"refs/heads/{session_branch}")
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, session_sha)
        self.assertEqual(payload["new_state"]["review_date"], "2026-03-19")
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_record_periodic_review_reports_blocked_fast_forward_when_base_diverged(
        self,
    ) -> None:
        repo_root = self._init_repo(self._periodic_review_fixture_files())
        git_root = self._rename_branch(repo_root)
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        with mock.patch.dict(os.environ, self._session_branch_env(), clear=False):
            tools = self._create_tools(repo_root)
            preview = self._load_tool_payload(
                asyncio.run(
                    tools["memory_record_periodic_review"](
                        review_date="2026-03-19",
                        assessment_summary="Exploration retained after review.",
                        belief_diff_entry="## [2026-03-19] Periodic review\n",
                        review_queue_entries="### [2026-03-19] Follow-up\n**Status:** pending\n",
                        preview=True,
                    )
                )
            )
            diverged_sha = self._diverge_base_branch(git_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_record_periodic_review"](
                        review_date="2026-03-19",
                        assessment_summary="Exploration retained after review.",
                        belief_diff_entry="## [2026-03-19] Periodic review\n",
                        review_queue_entries="### [2026-03-19] Follow-up\n**Status:** pending\n",
                        approval_token=preview["new_state"]["approval_token"],
                    )
                )
            )

        base_sha = self._rev_parse(git_root, "refs/heads/alex")
        session_sha = self._rev_parse(git_root, f"refs/heads/{session_branch}")
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )

    def test_memory_revert_commit_fast_forwards_preserved_base_branch(self) -> None:
        repo_root = self._init_repo({"memory/working/projects/demo.md": "# Demo\n\nOriginal\n"})
        git_root = self._rename_branch(repo_root)
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        with mock.patch.dict(os.environ, self._session_branch_env(), clear=False):
            tools = self._create_tools(repo_root)
            target_sha = self._write_and_commit(
                repo_root,
                "memory/working/projects/demo.md",
                "# Demo\n\nUpdated\n",
                "[plan] Update demo plan",
            )
            preview = self._load_tool_payload(
                asyncio.run(tools["memory_revert_commit"](sha=target_sha))
            )
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_revert_commit"](
                        sha=target_sha,
                        confirm=True,
                        preview_token=preview["new_state"]["preview_token"],
                    )
                )
            )

        restored = (repo_root / "memory" / "working" / "projects" / "demo.md").read_text(
            encoding="utf-8"
        )
        base_sha = self._rev_parse(git_root, "refs/heads/alex")
        session_sha = self._rev_parse(git_root, f"refs/heads/{session_branch}")
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertIn("Original", restored)
        self.assertNotIn("Updated", restored)
        self.assertEqual(base_sha, session_sha)
        self.assertEqual(payload["new_state"]["reverted_sha"], target_sha)
        self.assertEqual(merge["status"], "fast-forwarded")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertEqual(merge["target_ref"], "refs/heads/alex")
        self.assertEqual(merge["source_ref"], f"refs/heads/{session_branch}")
        self.assertEqual(merge["applied_sha"], base_sha)

    def test_memory_revert_commit_reports_blocked_fast_forward_when_base_diverged(
        self,
    ) -> None:
        repo_root = self._init_repo({"memory/working/projects/demo.md": "# Demo\n\nOriginal\n"})
        git_root = self._rename_branch(repo_root)
        session_branch = "engram/sessions/alex/2026-03-29-chat-002"

        with mock.patch.dict(os.environ, self._session_branch_env(), clear=False):
            tools = self._create_tools(repo_root)
            target_sha = self._write_and_commit(
                repo_root,
                "memory/working/projects/demo.md",
                "# Demo\n\nUpdated\n",
                "[plan] Update demo plan",
            )
            preview = self._load_tool_payload(
                asyncio.run(tools["memory_revert_commit"](sha=target_sha))
            )
            diverged_sha = self._diverge_base_branch(git_root)
            payload = self._load_tool_payload(
                asyncio.run(
                    tools["memory_revert_commit"](
                        sha=target_sha,
                        confirm=True,
                        preview_token=preview["new_state"]["preview_token"],
                    )
                )
            )

        restored = (repo_root / "memory" / "working" / "projects" / "demo.md").read_text(
            encoding="utf-8"
        )
        base_sha = self._rev_parse(git_root, "refs/heads/alex")
        session_sha = self._rev_parse(git_root, f"refs/heads/{session_branch}")
        merge = cast(dict[str, Any], payload["new_state"]["merge"])

        self.assertIn("Original", restored)
        self.assertNotIn("Updated", restored)
        self.assertEqual(base_sha, diverged_sha)
        self.assertNotEqual(base_sha, session_sha)
        self.assertEqual(merge["status"], "blocked")
        self.assertEqual(merge["base_branch"], "alex")
        self.assertEqual(merge["session_branch"], session_branch)
        self.assertIn("cannot be fast-forwarded", cast(str, merge["reason"]))
        self.assertTrue(
            any(
                "preserved base branch was not advanced" in warning
                for warning in cast(list[str], payload["warnings"])
            )
        )


if __name__ == "__main__":
    unittest.main()
