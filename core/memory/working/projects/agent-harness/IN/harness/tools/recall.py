"""Tool exposing Engram memory recall to the model.

When the EngramMemory backend is active, this tool lets the agent
search its own persistent memory on demand — retrieving past session
context, knowledge entries, project notes, and error patterns.
"""

from __future__ import annotations

import json
from datetime import datetime

from harness.memory import Memory, MemoryBackend


class RecallMemory:
    """Model-callable tool for querying the memory backend."""

    name = "recall_memory"
    description = (
        "Search persistent memory for relevant context. Returns past session "
        "notes, knowledge entries, project decisions, and error patterns. "
        "Use when you need context from previous sessions or stored knowledge "
        "that isn't in the current workspace files. Prefer this over guessing "
        "about past work or decisions."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Natural language search query describing what you're "
                    "looking for. Be specific — e.g. 'authentication migration "
                    "decisions' rather than just 'auth'."
                ),
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (1–20). Default 5.",
            },
        },
        "required": ["query"],
    }

    def __init__(self, memory: MemoryBackend):
        self._memory = memory

    def run(self, args: dict) -> str:
        query = args.get("query", "")
        if not query:
            return "Error: query is required."

        k = min(max(int(args.get("max_results", 5)), 1), 20)

        memories = self._memory.recall(query, k=k)
        if not memories:
            return f"No memory results for: {query!r}"

        lines: list[str] = [f"Found {len(memories)} result(s) for: {query!r}\n"]
        for i, mem in enumerate(memories, 1):
            ts = mem.timestamp.isoformat(timespec="seconds")
            lines.append(f"### [{i}] ({mem.kind}) {ts}")
            lines.append(mem.content)
            lines.append("")

        return "\n".join(lines)
