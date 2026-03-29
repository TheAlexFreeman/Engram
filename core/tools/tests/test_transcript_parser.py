from __future__ import annotations

import importlib
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar, cast

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_parser_module() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.sidecar.parser")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"sidecar parser dependencies unavailable: {exc.name}") from exc


class TranscriptParserTests(unittest.TestCase):
    parser_module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.parser_module = load_parser_module()

    def test_mock_transcript_parser_implements_contract(self) -> None:
        TranscriptFile = self.parser_module.TranscriptFile
        ParsedSession = self.parser_module.ParsedSession
        TranscriptParser = self.parser_module.TranscriptParser
        ToolCall = self.parser_module.ToolCall

        transcript = TranscriptFile(
            path=Path("transcripts/mock-session.jsonl"),
            platform="mock",
            modified_time=datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
        )

        class MockParser:
            def __init__(self, files: list[Any]) -> None:
                self._files = files

            def platform_name(self) -> str:
                return "mock"

            def detect_platform(self, transcript: Any) -> bool:
                return getattr(transcript, "platform", None) == "mock"

            def find_transcripts(self, since: datetime) -> list[Any]:
                return [item for item in self._files if item.modified_time >= since]

            def extract_tool_calls(self, raw_session: Any) -> list[Any]:
                payload = cast(dict[str, object], raw_session)
                return [
                    ToolCall(
                        name="memory_read_file",
                        args={"filePath": payload["file"]},
                        result="# Note",
                    )
                ]

            def parse_session(self, transcript: Any) -> Any:
                tool_calls = self.extract_tool_calls(
                    {"file": "memory/knowledge/software-engineering/parser.md"}
                )
                return ParsedSession(
                    session_id="mock-session-001",
                    start_time=datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc),
                    end_time=datetime(2026, 3, 29, 12, 5, tzinfo=timezone.utc),
                    user_messages=["Find the parser notes."],
                    assistant_messages=["I found the parser notes."],
                    tool_calls=tool_calls,
                    files_referenced=["memory/knowledge/software-engineering/parser.md"],
                )

        parser = MockParser([transcript])

        self.assertTrue(isinstance(parser, TranscriptParser))
        self.assertEqual(parser.platform_name(), "mock")
        self.assertTrue(parser.detect_platform(transcript))
        self.assertEqual(
            parser.find_transcripts(datetime(2026, 3, 29, 11, 59, tzinfo=timezone.utc)),
            [transcript],
        )

        session = cast(Any, parser.parse_session(transcript))
        self.assertEqual(session.session_id, "mock-session-001")
        self.assertEqual(session.start_time.isoformat(), "2026-03-29T12:00:00+00:00")
        self.assertEqual(session.end_time.isoformat(), "2026-03-29T12:05:00+00:00")
        self.assertEqual(session.user_messages, ["Find the parser notes."])
        self.assertEqual(session.assistant_messages, ["I found the parser notes."])
        self.assertEqual(
            session.all_messages(), ["Find the parser notes.", "I found the parser notes."]
        )
        self.assertEqual(len(session.tool_calls), 1)
        self.assertEqual(session.tool_calls[0].name, "memory_read_file")
        self.assertEqual(
            session.files_referenced,
            ["memory/knowledge/software-engineering/parser.md"],
        )

    def test_mock_transcript_parser_filters_by_modified_time(self) -> None:
        TranscriptFile = self.parser_module.TranscriptFile

        newer = TranscriptFile(
            path=Path("transcripts/newer.jsonl"),
            platform="mock",
            modified_time=datetime(2026, 3, 29, 12, 30, tzinfo=timezone.utc),
        )
        older = TranscriptFile(
            path=Path("transcripts/older.jsonl"),
            platform="mock",
            modified_time=datetime(2026, 3, 29, 11, 0, tzinfo=timezone.utc),
        )

        class MockParser:
            def __init__(self, files: list[Any]) -> None:
                self._files = files

            def platform_name(self) -> str:
                return "mock"

            def detect_platform(self, transcript: Any) -> bool:
                return getattr(transcript, "platform", None) == "mock"

            def find_transcripts(self, since: datetime) -> list[Any]:
                return [item for item in self._files if item.modified_time >= since]

            def extract_tool_calls(self, raw_session: Any) -> list[Any]:
                return []

            def parse_session(self, transcript: Any) -> Any:
                raise AssertionError("not needed for this test")

        parser = MockParser([older, newer])

        self.assertEqual(
            parser.find_transcripts(datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc)),
            [newer],
        )


if __name__ == "__main__":
    unittest.main()
