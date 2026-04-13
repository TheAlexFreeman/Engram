"""Transcript parser interfaces and shared data models for sidecar ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class TranscriptFile:
    """A transcript file discovered from a host platform."""

    path: Path
    platform: str
    modified_time: datetime


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool call extracted from a transcript."""

    name: str
    args: Any = None
    result: Any = None
    timestamp: datetime | None = None
    duration_ms: int | None = None
    tool_use_id: str | None = None


@dataclass(frozen=True, slots=True)
class DialogueTurn:
    """One user or assistant turn in transcript order (for compressed dialogue logs)."""

    role: Literal["user", "assistant"]
    text: str
    timestamp: datetime | None = None
    tool_names: tuple[str, ...] = ()


@dataclass(slots=True)
class ParsedSession:
    """Normalized transcript data for a single observed session."""

    session_id: str
    start_time: datetime
    end_time: datetime
    user_messages: list[str] = field(default_factory=list)
    assistant_messages: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    files_referenced: list[str] = field(default_factory=list)
    platform_metadata: dict[str, Any] = field(default_factory=dict)
    user_timestamps: list[datetime | None] = field(default_factory=list)
    assistant_timestamps: list[datetime | None] = field(default_factory=list)
    dialogue_turns: list[DialogueTurn] = field(default_factory=list)

    def all_messages(self) -> list[str]:
        return [*self.user_messages, *self.assistant_messages]


@runtime_checkable
class TranscriptParser(Protocol):
    """Contract implemented by platform-specific transcript parsers."""

    def platform_name(self) -> str:
        """Return the human-readable platform name for this parser."""

    def detect_platform(self, transcript: TranscriptFile) -> bool:
        """Return True when the transcript belongs to this parser's platform."""

    def find_transcripts(self, since: datetime) -> list[TranscriptFile]:
        """Discover transcript files modified on or after *since*."""

    def extract_tool_calls(self, raw_session: Any) -> list[ToolCall]:
        """Extract normalized tool calls from a raw platform session object."""

    def parse_session(self, transcript: TranscriptFile) -> ParsedSession:
        """Parse a transcript file into the normalized session model."""
