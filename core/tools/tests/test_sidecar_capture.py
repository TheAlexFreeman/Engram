from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import ClassVar

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module(name)


class TraceLoggerTests(unittest.TestCase):
    trace_logger_mod: ClassVar[ModuleType]
    parser_mod: ClassVar[ModuleType]
    plan_trace_mod: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.trace_logger_mod = _load("engram_mcp.agent_memory_mcp.sidecar.trace_logger")
        cls.parser_mod = _load("engram_mcp.agent_memory_mcp.sidecar.parser")
        cls.plan_trace_mod = _load("engram_mcp.agent_memory_mcp.plan_trace")

    def test_persist_dedupes_by_tool_use_id(self) -> None:
        ToolCall = self.parser_mod.ToolCall
        ParsedSession = self.parser_mod.ParsedSession
        session = ParsedSession(
            session_id="ext-1",
            start_time=datetime(2026, 4, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 1, 1, tzinfo=timezone.utc),
            tool_calls=[
                ToolCall(
                    name="Read",
                    args={"path": "x"},
                    result=None,
                    timestamp=datetime(2026, 4, 1, 0, 0, 1, tzinfo=timezone.utc),
                    tool_use_id="t1",
                )
            ],
        )
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        sid = "memory/activity/2026/04/01/chat-001"
        lg = self.trace_logger_mod.TraceLogger(root)
        self.assertEqual(lg.persist_tool_spans(sid, session), 1)
        self.assertEqual(lg.persist_tool_spans(sid, session), 0)
        spans = self.plan_trace_mod.load_session_trace_spans(root, sid)
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].get("metadata", {}).get("source"), "sidecar")

    def test_error_status_from_result(self) -> None:
        ToolCall = self.parser_mod.ToolCall
        ParsedSession = self.parser_mod.ParsedSession
        session = ParsedSession(
            session_id="ext-2",
            start_time=datetime(2026, 4, 2, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 2, 1, tzinfo=timezone.utc),
            tool_calls=[
                ToolCall(
                    name="Bash",
                    args={},
                    result={"is_error": True, "message": "failed"},
                    timestamp=datetime(2026, 4, 2, 0, 0, 1, tzinfo=timezone.utc),
                    tool_use_id="e1",
                )
            ],
        )
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        sid = "memory/activity/2026/04/02/chat-001"
        self.trace_logger_mod.TraceLogger(root).persist_tool_spans(sid, session)
        spans = self.plan_trace_mod.load_session_trace_spans(root, sid)
        self.assertEqual(spans[0].get("status"), "error")


class DialogueLoggerTests(unittest.TestCase):
    dialogue_mod: ClassVar[ModuleType]
    parser_mod: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.dialogue_mod = _load("engram_mcp.agent_memory_mcp.sidecar.dialogue_logger")
        cls.parser_mod = _load("engram_mcp.agent_memory_mcp.sidecar.parser")

    def test_compression_and_tool_names(self) -> None:
        DialogueTurn = self.parser_mod.DialogueTurn
        ParsedSession = self.parser_mod.ParsedSession
        ts = datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)
        session = ParsedSession(
            session_id="x",
            start_time=ts,
            end_time=ts,
            dialogue_turns=[
                DialogueTurn("user", "Hello there\nsecond line", ts, ()),
                DialogueTurn("assistant", "", ts, ("Read", "Grep")),
            ],
        )
        rows = self.dialogue_mod.DialogueLogger(Path(".")).build_dialogue_entries(session)
        self.assertEqual(rows[0]["role"], "user")
        self.assertEqual(rows[0]["first_line"], "Hello there")
        self.assertEqual(rows[0]["token_estimate"], (len("Hello there\nsecond line") + 3) // 4)
        self.assertEqual(rows[1]["tool_calls_in_turn"], ["Read", "Grep"])
        self.assertFalse(rows[1]["is_empty"])

        empty_session = ParsedSession(
            session_id="y",
            start_time=ts,
            end_time=ts,
            dialogue_turns=[DialogueTurn("assistant", "  \n", ts, ())],
        )
        empty_rows = self.dialogue_mod.DialogueLogger(Path(".")).build_dialogue_entries(
            empty_session
        )
        self.assertTrue(empty_rows[0]["is_empty"])


class SessionMetricsTests(unittest.TestCase):
    metrics_mod: ClassVar[ModuleType]
    parser_mod: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.metrics_mod = _load("engram_mcp.agent_memory_mcp.sidecar.metrics")
        cls.parser_mod = _load("engram_mcp.agent_memory_mcp.sidecar.parser")

    def test_aggregation_and_classification(self) -> None:
        ParsedSession = self.parser_mod.ParsedSession
        session = ParsedSession(
            session_id="s",
            start_time=datetime(2026, 4, 4, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 4, 0, 0, 10, tzinfo=timezone.utc),
        )
        traces = [
            {"span_type": "tool_call", "name": "Read", "status": "ok", "duration_ms": 5},
            {"span_type": "tool_call", "name": "Read", "status": "error", "duration_ms": 3},
        ]
        dialogue = [
            {"role": "user", "token_estimate": 10},
            {"role": "assistant", "token_estimate": 20},
        ]
        m = self.metrics_mod.compute_session_metrics(traces, dialogue, session)
        self.assertEqual(m["total_tool_calls"], 2)
        self.assertEqual(m["unique_tools_used"], 1)
        self.assertEqual(m["error_count"], 1)
        self.assertEqual(m["estimated_total_tokens"], 30)
        self.assertGreaterEqual(m["session_duration_ms"], 10000)


class PlanTraceQueryTests(unittest.TestCase):
    def test_group_by_tool_name(self) -> None:
        pt = _load("engram_mcp.agent_memory_mcp.plan_trace")
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        sid = "memory/activity/2026/05/01/chat-001"
        pt.record_trace(root, sid, span_type="tool_call", name="alpha", status="ok")
        pt.record_trace(root, sid, span_type="tool_call", name="alpha", status="error")
        pt.record_trace(root, sid, span_type="tool_call", name="beta", status="ok")
        out = pt.query_trace_spans(root, session_id=sid, group_by="tool_name", limit=10)
        self.assertEqual(out.get("group_by"), "tool_name")
        keys = {str(g["group_key"]) for g in out.get("groups", [])}
        self.assertEqual(keys, {"alpha", "beta"})


if __name__ == "__main__":
    unittest.main()
