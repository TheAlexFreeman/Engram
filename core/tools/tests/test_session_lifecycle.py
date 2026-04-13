from __future__ import annotations

import importlib
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar, cast

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_lifecycle_modules() -> tuple[ModuleType, ModuleType]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        lifecycle = importlib.import_module("engram_mcp.agent_memory_mcp.sidecar.lifecycle")
        parser = importlib.import_module("engram_mcp.agent_memory_mcp.sidecar.parser")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"sidecar lifecycle dependencies unavailable: {exc.name}") from exc
    return lifecycle, parser


class _FakeClient:
    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        self.calls.append((name, arguments or {}))
        return self._responses[name]


class SessionLifecycleTests(unittest.TestCase):
    lifecycle_module: ClassVar[ModuleType]
    parser_module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.lifecycle_module, cls.parser_module = load_lifecycle_modules()

    def _session(self, **overrides: object) -> Any:
        ParsedSession = self.parser_module.ParsedSession
        ToolCall = self.parser_module.ToolCall
        defaults: dict[str, object] = {
            "session_id": "claude-session-010",
            "start_time": datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
            "end_time": datetime(2026, 3, 29, 12, 10, tzinfo=timezone.utc),
            "user_messages": ["summarize the parser framework"],
            "assistant_messages": ["The framework centers on TranscriptFile and ParsedSession."],
            "tool_calls": [
                ToolCall(
                    name="mcp__engram__memory_read_file",
                    args={"path": "memory/knowledge/software-engineering/parser.md"},
                    result="# Parser",
                )
            ],
            "files_referenced": ["memory/knowledge/software-engineering/parser.md"],
        }
        defaults.update(overrides)
        return ParsedSession(**defaults)

    def test_close_inactive_sessions_records_session_and_summary(self) -> None:
        content_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(content_root, ignore_errors=True))
        client = _FakeClient(
            {
                "memory_record_session": json.dumps(
                    {"new_state": {"session_id": "memory/activity/2026/03/29/chat-010"}}
                ),
            }
        )
        manager = self.lifecycle_module.SessionLifecycleManager(
            client,
            content_root=content_root,
            session_id_factory=lambda _: "memory/activity/2026/03/29/chat-010",
        )
        session = self._session()

        self._run_async(manager.observe_session(session))
        results = self._run_async(
            manager.close_inactive_sessions(session.end_time + timedelta(minutes=31))
        )

        self.assertEqual(len(results), 1)
        self.assertEqual([name for name, _ in client.calls], ["memory_record_session"])
        record_session_args = client.calls[0][1]
        summary = cast(str, record_session_args["summary"])
        key_topics = cast(str, record_session_args["key_topics"])
        self.assertIn("metrics", record_session_args)
        self.assertIn("dialogue_entries", record_session_args)
        self.assertEqual(record_session_args["session_id"], "memory/activity/2026/03/29/chat-010")
        self.assertIn("Task: summarize the parser framework", summary)
        self.assertIn(
            "Outcome: The framework centers on TranscriptFile and ParsedSession.",
            summary,
        )
        self.assertEqual(key_topics, "parser")

    def test_observe_session_finalizes_prior_session_after_gap(self) -> None:
        content_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(content_root, ignore_errors=True))
        client = _FakeClient(
            {
                "memory_record_session": json.dumps(
                    {"new_state": {"session_id": "memory/activity/2026/03/29/chat-011"}}
                ),
            }
        )
        manager = self.lifecycle_module.SessionLifecycleManager(
            client,
            content_root=content_root,
            session_id_factory=lambda _: "memory/activity/2026/03/29/chat-011",
        )
        first = self._session(
            session_id="claude-session-gap",
            end_time=datetime(2026, 3, 29, 12, 5, tzinfo=timezone.utc),
        )
        second = self._session(
            session_id="claude-session-gap",
            start_time=datetime(2026, 3, 29, 13, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 29, 13, 10, tzinfo=timezone.utc),
            user_messages=["summarize the checkpoint work"],
        )

        self._run_async(manager.observe_session(first, transcript_path="a.jsonl"))
        results = self._run_async(manager.observe_session(second, transcript_path="a.jsonl"))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].observed_session_id, "claude-session-gap")
        self.assertEqual([name for name, _ in client.calls], ["memory_record_session"])

    def test_long_session_with_checkpoint_does_not_emit_warning(self) -> None:
        ToolCall = self.parser_module.ToolCall
        content_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(content_root, ignore_errors=True))
        client = _FakeClient(
            {
                "memory_record_session": json.dumps(
                    {"new_state": {"session_id": "memory/activity/2026/03/29/chat-012"}}
                ),
            }
        )
        manager = self.lifecycle_module.SessionLifecycleManager(
            client,
            content_root=content_root,
            session_id_factory=lambda _: "memory/activity/2026/03/29/chat-012",
            long_session_threshold=20,
        )
        session = self._session(
            tool_calls=[
                ToolCall(
                    name="mcp__engram__memory_read_file",
                    args={"path": f"memory/knowledge/topic-{index}.md"},
                    result=f"Topic {index}",
                )
                for index in range(21)
            ]
            + [
                ToolCall(
                    name="mcp__engram__memory_checkpoint",
                    args={"content": "captured progress"},
                    result=None,
                )
            ]
        )

        results = self._run_async(manager.observe_session(session, transcript_closed=True))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].warnings, [])

    def test_transcript_closed_finalizes_immediately_and_surfaces_checkpoint_warning(self) -> None:
        ToolCall = self.parser_module.ToolCall
        content_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(content_root, ignore_errors=True))
        client = _FakeClient(
            {
                "memory_record_session": json.dumps(
                    {"new_state": {"session_id": "memory/activity/2026/03/29/chat-013"}}
                ),
            }
        )
        manager = self.lifecycle_module.SessionLifecycleManager(
            client,
            content_root=content_root,
            session_id_factory=lambda _: "memory/activity/2026/03/29/chat-013",
            long_session_threshold=20,
        )
        session = self._session(
            session_id="claude-session-warning",
            tool_calls=[
                ToolCall(
                    name="mcp__engram__memory_read_file",
                    args={"path": f"memory/knowledge/topic-{index}.md"},
                    result=f"Topic {index}",
                )
                for index in range(21)
            ],
        )

        results = self._run_async(manager.observe_session(session, transcript_closed=True))

        self.assertEqual(len(results), 1)
        self.assertIn("without any memory_checkpoint usage", results[0].warnings[0])

    def test_duplicate_closed_session_observation_is_noop_after_successful_finalization(
        self,
    ) -> None:
        content_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(content_root, ignore_errors=True))
        client = _FakeClient(
            {
                "memory_record_session": json.dumps(
                    {"new_state": {"session_id": "memory/activity/2026/03/29/chat-014"}}
                ),
            }
        )
        manager = self.lifecycle_module.SessionLifecycleManager(
            client,
            content_root=content_root,
            session_id_factory=lambda _: "memory/activity/2026/03/29/chat-014",
        )
        session = self._session(session_id="claude-session-closed")

        first = self._run_async(
            manager.observe_session(session, transcript_path="closed.jsonl", transcript_closed=True)
        )
        second = self._run_async(
            manager.observe_session(session, transcript_path="closed.jsonl", transcript_closed=True)
        )

        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual([name for name, _ in client.calls], ["memory_record_session"])

    def test_close_inactive_sessions_does_not_replay_after_transcript_closed_finalization(
        self,
    ) -> None:
        content_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(content_root, ignore_errors=True))
        client = _FakeClient(
            {
                "memory_record_session": json.dumps(
                    {"new_state": {"session_id": "memory/activity/2026/03/29/chat-015"}}
                ),
            }
        )
        manager = self.lifecycle_module.SessionLifecycleManager(
            client,
            content_root=content_root,
            session_id_factory=lambda _: "memory/activity/2026/03/29/chat-015",
        )
        session = self._session(session_id="claude-session-finalized")

        self._run_async(
            manager.observe_session(session, transcript_path="closed.jsonl", transcript_closed=True)
        )
        later = self._run_async(
            manager.close_inactive_sessions(session.end_time + timedelta(hours=1))
        )

        self.assertEqual(later, [])
        self.assertEqual([name for name, _ in client.calls], ["memory_record_session"])

    def _run_async(self, coroutine: Any) -> Any:
        import asyncio

        return asyncio.run(coroutine)


if __name__ == "__main__":
    unittest.main()
