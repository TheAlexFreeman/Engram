"""Session lifecycle tracking for transcript-observed sessions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .access_logger import MCPToolClient
from .dialogue_logger import DialogueLogger
from .metrics import compute_session_metrics
from .parser import ParsedSession


@dataclass(slots=True)
class SessionLifecycleResult:
    """Structured result for one finalized transcript session."""

    observed_session_id: str
    memory_session_id: str
    summary: str
    key_topics: str
    record_session_payload: dict[str, Any]
    record_summary_payload: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    dialogue_rows: int = 0


@dataclass(slots=True)
class _TrackedSession:
    session: ParsedSession
    transcript_path: str | None
    last_activity: datetime
    dialogue_entries: list[dict[str, Any]] = field(default_factory=list)


class SessionLifecycleManager:
    """Detect transcript session boundaries and record them via MCP."""

    def __init__(
        self,
        client: MCPToolClient,
        *,
        content_root: Path,
        session_id_factory: Callable[[ParsedSession], str],
        inactivity_threshold: timedelta = timedelta(minutes=30),
        long_session_threshold: int = 20,
    ) -> None:
        self._client = client
        self._content_root = content_root
        self._session_id_factory = session_id_factory
        self._inactivity_threshold = inactivity_threshold
        self._long_session_threshold = long_session_threshold
        self._tracked_sessions: dict[str, _TrackedSession] = {}
        self._finalized_fingerprints: set[tuple[str, str, str]] = set()

    async def observe_session(
        self,
        session: ParsedSession,
        *,
        transcript_path: str | None = None,
        transcript_closed: bool = False,
        dialogue_entries: list[dict[str, Any]] | None = None,
    ) -> list[SessionLifecycleResult]:
        """Register or update an observed transcript session."""

        if transcript_closed and self._is_finalized_session(session, transcript_path):
            return []

        finalized: list[SessionLifecycleResult] = []
        tracked = self._tracked_sessions.get(session.session_id)

        if tracked is not None and self._should_restart_session(tracked, session, transcript_path):
            finalized.append(await self._finalize_session(session.session_id))
            tracked = None

        if tracked is None:
            self._tracked_sessions[session.session_id] = _TrackedSession(
                session=session,
                transcript_path=transcript_path,
                last_activity=session.end_time,
                dialogue_entries=list(dialogue_entries or []),
            )
        else:
            tracked.session = session
            tracked.transcript_path = transcript_path or tracked.transcript_path
            tracked.last_activity = max(tracked.last_activity, session.end_time)
            if dialogue_entries is not None:
                tracked.dialogue_entries = list(dialogue_entries)

        if transcript_closed:
            finalized.append(await self._finalize_session(session.session_id))

        return finalized

    async def close_inactive_sessions(
        self, reference_time: datetime
    ) -> list[SessionLifecycleResult]:
        """Finalize sessions that have been inactive past the configured threshold."""

        finalized: list[SessionLifecycleResult] = []
        for observed_session_id, tracked in list(self._tracked_sessions.items()):
            if reference_time - tracked.last_activity <= self._inactivity_threshold:
                continue
            finalized.append(await self._finalize_session(observed_session_id))
        return finalized

    def _should_restart_session(
        self,
        tracked: _TrackedSession,
        session: ParsedSession,
        transcript_path: str | None,
    ) -> bool:
        if (
            transcript_path
            and tracked.transcript_path
            and transcript_path != tracked.transcript_path
        ):
            return True
        return session.start_time - tracked.last_activity > self._inactivity_threshold

    def _is_finalized_session(
        self,
        session: ParsedSession,
        transcript_path: str | None,
    ) -> bool:
        return (
            self._finalization_fingerprint(session, transcript_path) in self._finalized_fingerprints
        )

    def _finalization_fingerprint(
        self,
        session: ParsedSession,
        transcript_path: str | None,
    ) -> tuple[str, str, str]:
        return (
            session.session_id,
            transcript_path or "",
            session.end_time.isoformat(),
        )

    async def _finalize_session(self, observed_session_id: str) -> SessionLifecycleResult:
        from ..plan_trace import load_session_trace_spans

        tracked = self._tracked_sessions[observed_session_id]
        session = tracked.session
        memory_session_id = self._session_id_factory(session)
        dialogue_entries = (
            list(tracked.dialogue_entries)
            if tracked.dialogue_entries
            else DialogueLogger.build_dialogue_entries(session)
        )
        trace_spans = load_session_trace_spans(self._content_root, memory_session_id)
        metrics = compute_session_metrics(trace_spans, dialogue_entries, session)
        summary = build_session_summary(session, metrics=metrics)
        key_topics = build_key_topics(session)
        warnings = _build_checkpoint_warnings(session, self._long_session_threshold)

        record_session_payload = await self._call_json_tool(
            "memory_record_session",
            {
                "session_id": memory_session_id,
                "summary": summary,
                "key_topics": key_topics,
                "metrics": metrics,
                "dialogue_entries": dialogue_entries,
            },
        )

        self._tracked_sessions.pop(observed_session_id, None)
        self._finalized_fingerprints.add(
            self._finalization_fingerprint(session, tracked.transcript_path)
        )

        return SessionLifecycleResult(
            observed_session_id=observed_session_id,
            memory_session_id=memory_session_id,
            summary=summary,
            key_topics=key_topics,
            record_session_payload=record_session_payload,
            warnings=warnings,
            dialogue_rows=len(dialogue_entries),
        )

    async def _call_json_tool(
        self,
        name: str,
        arguments: dict[str, object],
    ) -> dict[str, Any]:
        raw_payload = await self._client.call_tool(name, arguments)
        return _coerce_tool_response(raw_payload)


def _coerce_tool_response(raw_payload: Any) -> dict[str, Any]:
    if isinstance(raw_payload, dict):
        return raw_payload
    if hasattr(raw_payload, "content"):
        content = getattr(raw_payload, "content")
        if isinstance(content, list):
            fragments: list[str] = []
            for item in content:
                text = getattr(item, "text", None)
                if isinstance(text, str) and text.strip():
                    fragments.append(text)
            if fragments:
                return _coerce_tool_response("\n".join(fragments))
    if isinstance(raw_payload, str):
        stripped = raw_payload.strip()
        if not stripped:
            return {}
        return json.loads(stripped)
    return {"raw": raw_payload}


def build_session_summary(session: ParsedSession, *, metrics: dict[str, Any] | None = None) -> str:
    """Create a compact deterministic summary for a completed session."""

    task = _last_non_empty(session.user_messages)
    outcome = _last_non_empty(session.assistant_messages)

    lines: list[str] = []
    if task:
        lines.append(f"Task: {task}")
    if outcome:
        lines.append(f"Outcome: {outcome}")
    if metrics:
        breakdown = metrics.get("tool_call_breakdown") or {}
        top_tools = sorted(breakdown.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        top_line = (
            ", ".join(f"{name} ({count})" for name, count in top_tools) if top_tools else "none"
        )
        char = str(metrics.get("session_characterization") or "").strip()
        if char:
            lines.append(f"Activity: {char}. Top tools: {top_line}.")
    if not lines:
        return f"Observed transcript session {session.session_id}."
    return "\n\n".join(lines)


def build_key_topics(session: ParsedSession, *, limit: int = 3) -> str:
    """Derive lightweight key topics from referenced file names."""

    topics: list[str] = []
    seen: set[str] = set()
    for file_path in session.files_referenced:
        topic = Path(file_path).stem.replace("-", " ").strip()
        if not topic or topic in seen:
            continue
        seen.add(topic)
        topics.append(topic)
        if len(topics) >= limit:
            break
    return ", ".join(topics)


def _build_checkpoint_warnings(
    session: ParsedSession,
    long_session_threshold: int,
) -> list[str]:
    checkpoint_calls = sum(
        1
        for tool_call in session.tool_calls
        if tool_call.name.rsplit("__", 1)[-1] == "memory_checkpoint"
    )
    if len(session.tool_calls) <= long_session_threshold or checkpoint_calls > 0:
        return []
    return [
        (
            f"Observed session {session.session_id} exceeded {long_session_threshold} tool calls "
            "without any memory_checkpoint usage."
        )
    ]


def _last_non_empty(messages: list[str]) -> str:
    for message in reversed(messages):
        stripped = message.strip()
        if stripped:
            return stripped
    return ""
