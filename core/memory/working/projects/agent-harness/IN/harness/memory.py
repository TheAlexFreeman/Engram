from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class Memory:
    content: str
    timestamp: datetime
    kind: str  # "note", "error", "decision", "summary", ...


@runtime_checkable
class MemoryBackend(Protocol):
    """The contract. FileMemory honors it naively; Engram will honor it properly."""

    def start_session(self, task: str) -> str:
        """Return prior context to seed the session. May be empty."""

    def recall(self, query: str, k: int = 5) -> list[Memory]:
        """Query-based retrieval. FileMemory ignores the query; that's the point."""

    def record(self, content: str, kind: str = "note") -> None:
        """Capture an observation during the session."""

    def end_session(self, summary: str) -> None:
        """Wrap up. Persist whatever needs persisting."""


class FileMemory:
    """Dumb on purpose. One markdown file, appended to forever."""

    def __init__(self, path: Path):
        self.path = path
        self.path.touch(exist_ok=True)
        self._buffered_records: list[str] = []

    def start_session(self, task: str) -> str:
        existing = self.path.read_text(encoding="utf-8")
        stamp = datetime.now().isoformat(timespec="seconds")
        self._append(f"\n## Session {stamp}\n**Task:** {task}\n\n")
        return existing

    def recall(self, query: str, k: int = 5) -> list[Memory]:
        # Honest: we have no notion of query here. Return nothing.
        # This is the exact gap Engram fills.
        return []

    def record(self, content: str, kind: str = "note") -> None:
        stamp = datetime.now().isoformat(timespec="seconds")
        self._append(f"- `{stamp}` [{kind}] {content}\n")

    def end_session(self, summary: str) -> None:
        self._append(f"\n**Summary:** {summary}\n")

    def _append(self, text: str) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(text)
