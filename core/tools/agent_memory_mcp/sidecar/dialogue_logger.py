"""Compressed dialogue.jsonl rows derived from parsed sessions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .parser import DialogueTurn, ParsedSession

_FIRST_LINE_MAX = 200


def _format_ts(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _first_line(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    line = stripped.split("\n", 1)[0]
    if len(line) > _FIRST_LINE_MAX:
        return line[:_FIRST_LINE_MAX] + "[truncated]"
    return line


def _token_estimate(text: str) -> int:
    return max(0, (len(text) + 3) // 4)


class DialogueLogger:
    """Build and write dialogue.jsonl beside session SUMMARY.md."""

    def __init__(self, content_root: Path) -> None:
        self._root = content_root

    @staticmethod
    def build_dialogue_entries(session: ParsedSession) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        turns: list[DialogueTurn] = list(session.dialogue_turns)
        for turn in turns:
            text = turn.text or ""
            is_empty = not text.strip() and not turn.tool_names
            tool_names = [n for n in turn.tool_names if n]
            entry: dict[str, Any] = {
                "role": turn.role,
                "timestamp": _format_ts(turn.timestamp),
                "first_line": _first_line(text),
                "token_estimate": _token_estimate(text),
                "tool_calls_in_turn": tool_names,
                "is_empty": is_empty,
            }
            entries.append(entry)
        return entries

    def write_dialogue_file(self, memory_session_id: str, entries: list[dict[str, Any]]) -> None:
        if not entries:
            return
        rel_dir = memory_session_id.rstrip("/")
        path = self._root / rel_dir / "dialogue.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for row in entries:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
