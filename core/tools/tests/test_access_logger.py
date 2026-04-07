from __future__ import annotations

import importlib
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar, cast

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_sidecar_modules() -> tuple[ModuleType, ModuleType]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        access_logger = importlib.import_module("engram_mcp.agent_memory_mcp.sidecar.access_logger")
        parser = importlib.import_module("engram_mcp.agent_memory_mcp.sidecar.parser")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(
            f"sidecar access logger dependencies unavailable: {exc.name}"
        ) from exc
    return access_logger, parser


class _FakeClient:
    def __init__(self, responses: dict[str, Any]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    async def call_tool(self, name: str, arguments: dict[str, object] | None = None) -> Any:
        self.calls.append((name, arguments))
        return self._responses[name]


class AccessLoggerTests(unittest.TestCase):
    access_logger_module: ClassVar[ModuleType]
    parser_module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.access_logger_module, cls.parser_module = load_sidecar_modules()

    def _parsed_session(self, **overrides: object) -> Any:
        ParsedSession = self.parser_module.ParsedSession
        ToolCall = self.parser_module.ToolCall
        defaults: dict[str, object] = {
            "session_id": "claude-session-001",
            "start_time": datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
            "end_time": datetime(2026, 3, 29, 12, 5, tzinfo=timezone.utc),
            "user_messages": ["summarize the parser framework"],
            "assistant_messages": [
                "The parser framework defines TranscriptFile, ParsedSession, and TranscriptParser."
            ],
            "tool_calls": [
                ToolCall(
                    name="mcp__engram__memory_read_file",
                    args={"path": "memory/knowledge/software-engineering/parser.md"},
                    result=json.dumps(
                        {
                            "path": "memory/knowledge/software-engineering/parser.md",
                            "inline": True,
                            "content": (
                                "The parser framework defines TranscriptFile, ParsedSession, "
                                "and TranscriptParser."
                            ),
                        }
                    ),
                )
            ],
            "files_referenced": ["memory/knowledge/software-engineering/parser.md"],
        }
        defaults.update(overrides)
        return ParsedSession(**defaults)

    def test_build_access_entries_uses_tool_result_content_and_estimator(self) -> None:
        session = self._parsed_session(
            tool_calls=[
                self.parser_module.ToolCall(
                    name="mcp__engram__memory_read_file",
                    args={"path": "memory/knowledge/software-engineering/parser.md"},
                    result=json.dumps(
                        {
                            "path": "memory/knowledge/software-engineering/parser.md",
                            "inline": True,
                            "content": (
                                "The parser framework defines TranscriptFile, ParsedSession, "
                                "and TranscriptParser."
                            ),
                        }
                    ),
                ),
                self.parser_module.ToolCall(
                    name="Read",
                    args={"file_path": "README.md"},
                    result="ignored local read",
                ),
            ]
        )

        entries = self.access_logger_module.build_access_entries(session)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["file"], "memory/knowledge/software-engineering/parser.md")
        self.assertEqual(entries[0]["task"], "summarize the parser framework")
        self.assertEqual(entries[0]["mode"], "read")
        self.assertEqual(entries[0]["estimator"], "sidecar")
        self.assertGreaterEqual(float(entries[0]["helpfulness"]), 0.75)

    def test_build_access_entries_ignores_search_and_folder_discovery_tools(self) -> None:
        session = self._parsed_session(
            tool_calls=[
                self.parser_module.ToolCall(
                    name="mcp__engram__memory_search",
                    args={"query": "parser"},
                    result=(
                        "**memory/knowledge/software-engineering/parser.md**\n"
                        "  3: parser match\n"
                        "**memory/skills/session-start/SKILL.md**\n"
                        "  2: another match"
                    ),
                ),
                self.parser_module.ToolCall(
                    name="mcp__engram__memory_list_folder",
                    args={"path": "memory/knowledge/software-engineering"},
                    result=json.dumps(
                        {
                            "path": "memory/knowledge/software-engineering",
                            "entries": [
                                {
                                    "path": "memory/knowledge/software-engineering/parser.md",
                                    "kind": "file",
                                }
                            ],
                        }
                    ),
                ),
            ],
            files_referenced=[
                "memory/knowledge/software-engineering/parser.md",
                "memory/skills/session-start/SKILL.md",
            ],
        )

        entries = self.access_logger_module.build_access_entries(session)

        self.assertEqual(entries, [])

    def test_build_access_entries_uses_temp_file_content_for_canonical_result_path(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tempdir:
            temp_path = Path(tempdir) / "readback.md"
            temp_path.write_text(
                "The parser framework defines TranscriptFile, ParsedSession, and TranscriptParser.",
                encoding="utf-8",
            )
            session = self._parsed_session(
                tool_calls=[
                    self.parser_module.ToolCall(
                        name="mcp__engram__memory_read_file",
                        args={"path": "memory/knowledge/software-engineering/wrong.md"},
                        result=json.dumps(
                            {
                                "path": "memory/knowledge/software-engineering/parser.md",
                                "inline": False,
                                "temp_file": str(temp_path),
                            }
                        ),
                    )
                ]
            )

            entries = self.access_logger_module.build_access_entries(session)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["file"], "memory/knowledge/software-engineering/parser.md")
        self.assertGreaterEqual(float(entries[0]["helpfulness"]), 0.75)

    def test_log_session_access_batches_entries_and_runs_aggregation(self) -> None:
        session = self._parsed_session(
            user_messages=["resume the project summary"],
            assistant_messages=[
                "The current focus and active plan are both in the project summary."
            ],
            tool_calls=[
                self.parser_module.ToolCall(
                    name="mcp__engram__memory_read_file",
                    args={"path": "memory/working/projects/session-management/SUMMARY.md"},
                    result=json.dumps(
                        {
                            "path": "memory/working/projects/session-management/SUMMARY.md",
                            "inline": True,
                            "content": "The current focus and active plan are both in the project summary.",
                        }
                    ),
                ),
                self.parser_module.ToolCall(
                    name="mcp__engram__memory_read_file",
                    args={"path": "memory/knowledge/software-engineering/parser.md"},
                    result=json.dumps(
                        {
                            "path": "memory/knowledge/software-engineering/parser.md",
                            "inline": True,
                            "content": "Parser notes unrelated to the final answer.",
                        }
                    ),
                ),
            ],
            files_referenced=[
                "memory/working/projects/session-management/SUMMARY.md",
                "memory/knowledge/software-engineering/parser.md",
            ],
        )
        client = _FakeClient(
            {
                "memory_log_access_batch": json.dumps(
                    {
                        "new_state": {
                            "access_jsonls": [
                                "memory/working/projects/ACCESS.jsonl",
                                "memory/knowledge/ACCESS_SCANS.jsonl",
                            ],
                            "entry_count": 2,
                            "scan_entry_count": 1,
                        }
                    }
                ),
                "memory_check_aggregation_triggers": json.dumps(
                    {
                        "above_trigger": ["memory/working/projects/ACCESS.jsonl"],
                        "near_trigger": [],
                        "reports": [],
                    }
                ),
                "memory_run_aggregation": json.dumps(
                    {"new_state": {"folders": ["memory/working/projects"]}}
                ),
            }
        )
        logger = self.access_logger_module.AccessLogger(client)

        result = self._run_async(
            logger.log_session_access(
                session,
                session_id="memory/activity/2026/03/29/chat-001",
                min_helpfulness=0.7,
            )
        )

        self.assertEqual(
            [name for name, _ in client.calls],
            [
                "memory_log_access_batch",
                "memory_check_aggregation_triggers",
                "memory_run_aggregation",
            ],
        )
        batch_call = client.calls[0][1]
        self.assertIsNotNone(batch_call)
        batch_args = cast(dict[str, object], batch_call)
        self.assertEqual(batch_args["session_id"], "memory/activity/2026/03/29/chat-001")
        self.assertEqual(batch_args["min_helpfulness"], 0.7)
        access_entries = cast(list[dict[str, object]], batch_args["access_entries"])
        self.assertIsInstance(access_entries, list)
        self.assertEqual(access_entries[0]["estimator"], "sidecar")
        self.assertEqual(access_entries[0]["mode"], "read")
        self.assertEqual(result.aggregated_folders, ["memory/working/projects"])
        self.assertIsNotNone(result.aggregation_payload)

    def test_log_session_access_skips_aggregation_when_no_changed_hot_log_crosses_trigger(
        self,
    ) -> None:
        session = self._parsed_session()
        client = _FakeClient(
            {
                "memory_log_access_batch": json.dumps(
                    {
                        "new_state": {
                            "access_jsonls": ["memory/knowledge/ACCESS_SCANS.jsonl"],
                            "entry_count": 1,
                            "scan_entry_count": 1,
                        }
                    }
                ),
                "memory_check_aggregation_triggers": json.dumps(
                    {
                        "above_trigger": ["memory/working/projects/ACCESS.jsonl"],
                        "near_trigger": [],
                        "reports": [],
                    }
                ),
            }
        )
        logger = self.access_logger_module.AccessLogger(client)

        result = self._run_async(logger.log_session_access(session, min_helpfulness=0.7))

        self.assertEqual(
            [name for name, _ in client.calls],
            [
                "memory_log_access_batch",
                "memory_check_aggregation_triggers",
            ],
        )
        self.assertEqual(result.aggregated_folders, [])
        self.assertIsNone(result.aggregation_payload)

    def _run_async(self, coroutine: Any) -> Any:
        import asyncio

        return asyncio.run(coroutine)


if __name__ == "__main__":
    unittest.main()
