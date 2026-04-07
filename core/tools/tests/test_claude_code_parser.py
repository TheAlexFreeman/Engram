from __future__ import annotations

import importlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import ClassVar

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_claude_parser_module() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.sidecar.parsers.claude_code")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"claude parser dependencies unavailable: {exc.name}") from exc


class ClaudeCodeTranscriptParserTests(unittest.TestCase):
    parser_module: ClassVar[ModuleType]
    model_module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.parser_module = load_claude_parser_module()
        cls.model_module = importlib.import_module("engram_mcp.agent_memory_mcp.sidecar.parser")

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.projects_root = Path(self._tmpdir.name) / ".claude" / "projects"
        self.projects_root.mkdir(parents=True, exist_ok=True)

    def _write_transcript(self, relative_path: str, records: list[dict[str, object]]) -> Path:
        target = self.projects_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )
        return target

    def test_find_transcripts_discovers_recent_claude_project_logs(self) -> None:
        parser = self.parser_module.ClaudeCodeTranscriptParser(projects_root=self.projects_root)

        old_transcript = self._write_transcript(
            "project-a/old-session.jsonl",
            [{"type": "queue-operation", "timestamp": "2026-03-28T10:00:00Z"}],
        )
        recent_transcript = self._write_transcript(
            "project-a/recent-session.jsonl",
            [{"type": "queue-operation", "timestamp": "2026-03-29T10:00:00Z"}],
        )

        old_epoch = datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc).timestamp()
        recent_epoch = datetime(2026, 3, 29, 10, 0, tzinfo=timezone.utc).timestamp()
        Path(old_transcript).touch()
        Path(recent_transcript).touch()
        import os

        os.utime(old_transcript, (old_epoch, old_epoch))
        os.utime(recent_transcript, (recent_epoch, recent_epoch))

        transcripts = parser.find_transcripts(datetime(2026, 3, 29, 0, 0, tzinfo=timezone.utc))

        self.assertEqual(len(transcripts), 1)
        self.assertEqual(transcripts[0].path, recent_transcript)
        self.assertEqual(transcripts[0].platform, "claude-code")

    def test_parse_session_extracts_messages_tool_calls_and_file_references(self) -> None:
        TranscriptFile = self.model_module.TranscriptFile
        parser = self.parser_module.ClaudeCodeTranscriptParser(projects_root=self.projects_root)

        transcript_path = self._write_transcript(
            "project-b/session-001.jsonl",
            [
                {
                    "type": "queue-operation",
                    "operation": "enqueue",
                    "timestamp": "2026-03-29T09:00:00Z",
                    "sessionId": "session-001",
                },
                {
                    "type": "user",
                    "timestamp": "2026-03-29T09:00:01Z",
                    "sessionId": "session-001",
                    "message": {"role": "user", "content": "Read the parser notes."},
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-03-29T09:00:02Z",
                    "sessionId": "session-001",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "I will inspect the notes."}],
                    },
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-03-29T09:00:03Z",
                    "sessionId": "session-001",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_read_1",
                                "name": "Read",
                                "input": {
                                    "file_path": "C:\\Users\\iam\\Main\\Code\\Personal\\agent-memory-seed\\Engram\\core\\memory\\knowledge\\software-engineering\\parser.md"
                                },
                            },
                            {
                                "type": "tool_use",
                                "id": "toolu_mcp_1",
                                "name": "mcp__engram__memory_search",
                                "input": {
                                    "path": "memory/knowledge/software-engineering/parser.md"
                                },
                            },
                        ],
                    },
                },
                {
                    "type": "user",
                    "timestamp": "2026-03-29T09:00:04Z",
                    "sessionId": "session-001",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "toolu_read_1",
                                "content": "Parser notes returned.",
                            }
                        ],
                    },
                    "toolUseResult": {
                        "filePath": "C:\\Users\\iam\\Main\\Code\\Personal\\agent-memory-seed\\Engram\\core\\README.md"
                    },
                },
                {
                    "type": "assistant",
                    "timestamp": "2026-03-29T09:00:05Z",
                    "sessionId": "session-001",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "The parser notes are loaded."}],
                    },
                },
            ],
        )

        transcript = TranscriptFile(
            path=transcript_path,
            platform="claude-code",
            modified_time=datetime(2026, 3, 29, 9, 0, 5, tzinfo=timezone.utc),
        )
        session = parser.parse_session(transcript)

        self.assertEqual(session.session_id, "session-001")
        self.assertEqual(session.start_time.isoformat(), "2026-03-29T09:00:00+00:00")
        self.assertEqual(session.end_time.isoformat(), "2026-03-29T09:00:05+00:00")
        self.assertEqual(session.user_messages, ["Read the parser notes."])
        self.assertEqual(
            session.assistant_messages,
            ["I will inspect the notes.", "The parser notes are loaded."],
        )
        self.assertEqual(len(session.tool_calls), 2)
        self.assertEqual(session.tool_calls[0].name, "Read")
        self.assertEqual(
            session.tool_calls[0].result,
            {
                "filePath": "C:\\Users\\iam\\Main\\Code\\Personal\\agent-memory-seed\\Engram\\core\\README.md"
            },
        )
        self.assertEqual(session.tool_calls[1].name, "mcp__engram__memory_search")
        self.assertEqual(
            session.files_referenced,
            ["memory/knowledge/software-engineering/parser.md", "README.md"],
        )

    def test_parse_session_normalizes_absolute_memory_path_without_core_prefix(self) -> None:
        TranscriptFile = self.model_module.TranscriptFile
        parser = self.parser_module.ClaudeCodeTranscriptParser(projects_root=self.projects_root)

        transcript_path = self._write_transcript(
            "project-c/session-002.jsonl",
            [
                {
                    "type": "assistant",
                    "timestamp": "2026-03-29T10:00:00Z",
                    "sessionId": "session-002",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "toolu_search_1",
                                "name": "mcp__engram__memory_read_file",
                                "input": {
                                    "filePath": "C:\\repos\\Engram\\memory\\skills\\session-start\\SKILL.md"
                                },
                            }
                        ],
                    },
                }
            ],
        )

        session = parser.parse_session(
            TranscriptFile(
                path=transcript_path,
                platform="claude-code",
                modified_time=datetime(2026, 3, 29, 10, 0, tzinfo=timezone.utc),
            )
        )

        self.assertEqual(session.files_referenced, ["memory/skills/session-start/SKILL.md"])

    def test_detect_platform_requires_claude_projects_jsonl_path(self) -> None:
        TranscriptFile = self.model_module.TranscriptFile
        parser = self.parser_module.ClaudeCodeTranscriptParser(projects_root=self.projects_root)

        transcript = TranscriptFile(
            path=Path(self._tmpdir.name) / ".claude" / "projects" / "demo" / "session.jsonl",
            platform="claude-code",
            modified_time=datetime(2026, 3, 29, 9, 0, tzinfo=timezone.utc),
        )
        other = TranscriptFile(
            path=Path(self._tmpdir.name) / "elsewhere" / "session.jsonl",
            platform="claude-code",
            modified_time=datetime(2026, 3, 29, 9, 0, tzinfo=timezone.utc),
        )

        self.assertTrue(parser.detect_platform(transcript))
        self.assertFalse(parser.detect_platform(other))


if __name__ == "__main__":
    unittest.main()
