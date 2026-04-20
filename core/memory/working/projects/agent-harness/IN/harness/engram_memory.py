"""MemoryBackend backed by Engram MCP tool functions (direct import).

Replaces FileMemory with semantic retrieval, governed session lifecycle,
and structured trace recording. Session IDs use the ``act-NNN`` prefix
to distinguish harness runs from interactive chat sessions.

Usage::

    from engram_mcp.agent_memory_mcp.server import create_mcp
    from harness.engram_memory import EngramMemory

    _mcp, tools, repo_root, repo = create_mcp(repo_root="/path/to/engram")
    memory = EngramMemory(tools, repo_root, repo=repo)
    # pass to harness.loop.run() as the memory= argument
    # after run(), call memory.finalize(result, trace_path)
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from harness.memory import Memory, MemoryBackend


def _run(coro: Any) -> Any:
    """Run an async tool function synchronously.

    The harness loop is sync, but Engram MCP tools are async. If an event
    loop is already running (e.g. inside a notebook) we schedule onto it;
    otherwise we spin up a throwaway loop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _parse_json(raw: str) -> Any:
    """Parse a JSON string, returning the raw string on failure."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def _next_act_id(activity_root: Path, day_key: str) -> str:
    """Allocate the next ``act-NNN`` session id for *day_key*.

    Scans existing ``act-*`` directories under the day folder and returns
    the next sequential number. Thread-safe enough for single-process use;
    the git commit layer provides the real serialization.
    """
    day_path = activity_root / day_key
    existing = 0
    if day_path.is_dir():
        for child in day_path.iterdir():
            m = re.match(r"act-(\d{3})$", child.name)
            if m:
                existing = max(existing, int(m.group(1)))
    return f"act-{existing + 1:03d}"


class EngramMemory:
    """MemoryBackend that delegates to Engram MCP tool functions.

    Parameters
    ----------
    tools : dict[str, object]
        The tool-callable dict returned by ``create_mcp()[1]``.
    repo_root : Path
        Resolved repo root (``create_mcp()[2]``), used for session ID
        allocation.
    repo : object
        The ``GitRepo`` returned by ``create_mcp()[3]``. Used by
        ``finalize()`` to stage the trace file into the session commit.
    user_id : str | None
        Optional user identity for namespaced session paths.
    """

    def __init__(
        self,
        tools: dict[str, object],
        repo_root: Path,
        repo: Any,
        *,
        user_id: str | None = None,
    ):
        self._tools = tools
        self._repo_root = repo_root
        self._repo = repo  # GitRepo — has .add(), .commit(), .content_root
        self._user_id = user_id
        self.session_id: str | None = None
        self._task: str = ""  # stashed by start_session for finalize()

    # ------------------------------------------------------------------
    # MemoryBackend protocol
    # ------------------------------------------------------------------

    def start_session(self, task: str) -> str:
        """Bootstrap context from Engram and allocate an act-NNN session ID."""
        self._task = task

        # 1. Allocate session ID
        now = datetime.now()
        day_key = now.strftime("%Y/%m/%d")
        if self._user_id:
            activity_root = (
                self._repo_root / "core" / "memory" / "activity" / self._user_id
            )
            act_num = _next_act_id(activity_root, day_key)
            self.session_id = f"memory/activity/{self._user_id}/{day_key}/{act_num}"
        else:
            activity_root = self._repo_root / "core" / "memory" / "activity"
            act_num = _next_act_id(activity_root, day_key)
            self.session_id = f"memory/activity/{day_key}/{act_num}"

        # 2. Bootstrap — get active plans, pending reviews, etc.
        parts: list[str] = []
        bootstrap_tool = self._tools.get("memory_session_bootstrap")
        if bootstrap_tool is not None:
            try:
                raw = _run(bootstrap_tool(max_active_plans=3, max_review_items=3))
                data = _parse_json(raw)
                if isinstance(data, dict):
                    parts.append("## Session bootstrap\n")
                    parts.append(json.dumps(data, indent=2, default=str))
                elif isinstance(data, str) and data.strip():
                    parts.append("## Session bootstrap\n")
                    parts.append(data)
            except Exception:
                pass  # graceful degradation

        # 3. Semantic search for task-relevant context
        search_tool = self._tools.get("memory_semantic_search")
        if search_tool is not None:
            try:
                raw = _run(search_tool(query=task, limit=5))
                data = _parse_json(raw)
                if isinstance(data, dict) and data.get("results"):
                    parts.append("\n## Related memory\n")
                    for hit in data["results"][:5]:
                        path = hit.get("path", "")
                        snippet = hit.get("snippet", hit.get("content", ""))
                        if snippet:
                            parts.append(f"- **{path}**: {snippet[:300]}")
                elif isinstance(data, str) and data.strip():
                    parts.append("\n## Related memory\n")
                    parts.append(data)
            except Exception:
                pass  # fall back to keyword search below

        # 4. Keyword fallback if semantic search returned nothing
        if len(parts) <= 1:
            keyword_tool = self._tools.get("memory_search")
            if keyword_tool is not None:
                try:
                    # Extract meaningful keywords from the task
                    raw = _run(keyword_tool(query=task[:120], max_results=10))
                    data = _parse_json(raw)
                    if isinstance(data, str) and data.strip():
                        parts.append("\n## Related memory (keyword)\n")
                        parts.append(data)
                except Exception:
                    pass

        return "\n".join(parts) if parts else ""

    def recall(self, query: str, k: int = 5) -> list[Memory]:
        """Semantic search across Engram memory."""
        search_tool = self._tools.get("memory_semantic_search")
        if search_tool is None:
            # Fall back to keyword search
            search_tool = self._tools.get("memory_search")
            if search_tool is None:
                return []
            try:
                raw = _run(search_tool(query=query, max_results=k))
                return [
                    Memory(
                        content=raw,
                        timestamp=datetime.now(),
                        kind="search",
                    )
                ]
            except Exception:
                return []

        try:
            raw = _run(search_tool(query=query, limit=k))
            data = _parse_json(raw)
        except Exception:
            return []

        if not isinstance(data, dict) or "results" not in data:
            if isinstance(data, str) and data.strip():
                return [Memory(content=data, timestamp=datetime.now(), kind="search")]
            return []

        memories: list[Memory] = []
        for hit in data["results"]:
            content = hit.get("snippet", hit.get("content", ""))
            path = hit.get("path", "")
            if path:
                content = f"[{path}] {content}"

            # Extract timestamp from frontmatter dates if available
            ts_str = hit.get("last_verified") or hit.get("created") or ""
            try:
                ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
            except ValueError:
                ts = datetime.now()

            kind = hit.get("type", "note")
            memories.append(Memory(content=content, timestamp=ts, kind=kind))

        return memories

    def record(self, content: str, kind: str = "note") -> None:
        """Record an observation. Errors go to trace; notes go to scratchpad."""
        if kind == "error" and self.session_id:
            trace_tool = self._tools.get("memory_record_trace")
            if trace_tool is not None:
                try:
                    _run(
                        trace_tool(
                            session_id=self.session_id,
                            span_type="tool_call",
                            name="harness_error",
                            status="error",
                            metadata={"content": content[:500]},
                        )
                    )
                except Exception:
                    pass  # trace recording is non-blocking by design

        scratchpad_tool = self._tools.get("memory_append_scratchpad")
        if scratchpad_tool is not None:
            try:
                stamp = datetime.now().isoformat(timespec="seconds")
                _run(
                    scratchpad_tool(
                        target="current",
                        content=f"- `{stamp}` [{kind}] {content}\n",
                    )
                )
            except Exception:
                pass  # non-blocking

    def end_session(self, summary: str) -> None:
        """Stash the summary for finalize(). Does NOT commit yet.

        The harness loop calls this when the model stops issuing tool
        calls. The real session recording happens in ``finalize()``,
        which has access to the ``RunResult`` and trace file. If
        ``finalize()`` is never called (e.g. crash), the summary is
        lost — that's acceptable because the trace file is the
        authoritative record.
        """
        self._summary = summary

    # ------------------------------------------------------------------
    # Post-run pipeline
    # ------------------------------------------------------------------

    def finalize(
        self,
        trace_path: Path,
        *,
        total_turns: int = 0,
        total_cost_usd: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        reasoning_tokens: int = 0,
        model: str = "",
    ) -> None:
        """Commit the full session to Engram: trace, summary, dialogue.

        Called by ``cli.py`` after the loop returns. Writes the raw
        harness trace JSONL into the ``act-NNN/`` session directory,
        builds per-turn dialogue rows from it, and calls
        ``memory_record_session`` with summary + metrics + dialogue
        in one atomic commit, then commits the trace file on top.

        Parameters
        ----------
        trace_path : Path
            Path to the harness JSONL trace file.
        total_turns, total_cost_usd, ... : numbers
            Aggregate usage from ``RunResult.usage``.
        model : str
            Model identifier.
        """
        if not self.session_id:
            return

        summary = getattr(self, "_summary", "(no summary)")
        content_root = self._repo.content_root

        # 1. Parse trace and build per-turn dialogue rows
        dialogue_rows = _build_dialogue_rows(trace_path)

        # 2. Build metrics dict
        metrics = {
            "source": "agent-harness",
            "model": model,
            "turns": total_turns,
            "total_cost_usd": round(total_cost_usd, 6),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        if cache_read_tokens:
            metrics["cache_read_tokens"] = cache_read_tokens
        if cache_write_tokens:
            metrics["cache_write_tokens"] = cache_write_tokens
        if reasoning_tokens:
            metrics["reasoning_tokens"] = reasoning_tokens

        # 3. Copy trace file into session directory
        session_dir_rel = self.session_id  # e.g. memory/activity/2026/04/19/act-001
        session_dir_abs = content_root / session_dir_rel
        session_dir_abs.mkdir(parents=True, exist_ok=True)

        dest_trace = session_dir_abs / "trace.jsonl"
        if trace_path.exists():
            shutil.copy2(trace_path, dest_trace)

        # 4. Call memory_record_session for the atomic commit
        record_tool = self._tools.get("memory_record_session")
        if record_tool is not None:
            try:
                _run(
                    record_tool(
                        session_id=self.session_id,
                        summary=summary,
                        key_topics=f"agent-harness, {model}" if model else "agent-harness",
                        metrics=metrics,
                        dialogue_entries=dialogue_rows if dialogue_rows else None,
                    )
                )
            except Exception as exc:
                import sys
                print(f"[engram] record_session failed: {exc}", file=sys.stderr)

        # 5. Stage and commit the trace file separately
        if dest_trace.exists():
            trace_rel = f"{session_dir_rel}/trace.jsonl"
            try:
                self._repo.add(trace_rel)
                self._repo.commit(f"[chat] Store harness trace for {self.session_id}")
            except Exception as exc:
                import sys
                print(f"[engram] trace commit failed: {exc}", file=sys.stderr)


def _build_dialogue_rows(trace_path: Path) -> list[dict[str, Any]]:
    """Parse a harness trace JSONL and return per-turn dialogue rows.

    Each row captures: turn number, tools called, whether any errored,
    token counts, and cost. Designed for ``memory_record_session``'s
    ``dialogue_entries`` parameter and ``memory_query_dialogue`` search.
    """
    if not trace_path.exists():
        return []

    events: list[dict[str, Any]] = []
    with trace_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not events:
        return []

    # Detect whether usage events are present (Claude has them; some
    # Grok traces don't). Fall back to model_response as turn markers.
    has_usage = any(e.get("kind") == "usage" for e in events)
    turn_marker = "usage" if has_usage else "model_response"

    # Group events by turn
    rows: list[dict[str, Any]] = []
    current_turn: int | None = None
    turn_tools: list[str] = []
    turn_errors: int = 0
    turn_usage: dict[str, Any] = {}

    for e in events:
        kind = e.get("kind")

        if kind == turn_marker:
            turn_num = e.get("turn", 0)

            # Flush previous turn if we moved on
            if current_turn is not None and turn_num != current_turn:
                rows.append(_flush_turn(current_turn, turn_tools, turn_errors, turn_usage))
                turn_tools = []
                turn_errors = 0
                turn_usage = {}

            current_turn = turn_num

            if has_usage:
                turn_usage = {
                    "input_tokens": e.get("input_tokens", 0),
                    "output_tokens": e.get("output_tokens", 0),
                    "cost_usd": round(e.get("total_cost_usd", 0.0), 6),
                }
            # else: no token data available for this turn

        elif kind == "tool_call":
            turn_tools.append(e.get("name", "unknown"))

        elif kind == "tool_result":
            if e.get("is_error"):
                turn_errors += 1

    # Flush last turn
    if current_turn is not None:
        rows.append(_flush_turn(current_turn, turn_tools, turn_errors, turn_usage))

    return rows


def _flush_turn(
    turn: int,
    tools: list[str],
    errors: int,
    usage: dict[str, Any],
) -> dict[str, Any]:
    """Build a single dialogue row from accumulated turn data."""
    # Compress tool list: ["read_file", "read_file", "edit_file"] → "read_file×2, edit_file"
    tool_counts = Counter(tools)
    tool_summary = ", ".join(
        f"{name}×{count}" if count > 1 else name
        for name, count in tool_counts.items()
    )

    row: dict[str, Any] = {
        "turn": turn,
        "tools": tool_summary or "(none)",
        "tool_count": len(tools),
    }
    if errors:
        row["errors"] = errors
    row.update(usage)
    return row
