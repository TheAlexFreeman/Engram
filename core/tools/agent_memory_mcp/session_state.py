"""Shared MCP session state tracking and advisory helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

_CHECKPOINT_STALE_TOOL_CALLS = 10
_FLUSH_RECOMMEND_MINUTES = 30
_FLUSH_RECOMMEND_MIN_TOOL_CALLS = 5


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _append_unique(values: list[str], value: str) -> None:
    normalized = value.strip()
    if normalized and normalized not in values:
        values.append(normalized)


@dataclass(slots=True)
class SessionAdvisory:
    """Derived advisory signals for the current MCP session."""

    flush_recommended: bool = False
    checkpoint_stale: bool = False
    unread_relevant_files: list[str] = field(default_factory=list)
    session_duration_minutes: int = 0
    tool_calls_since_checkpoint: int = 0

    def has_signals(self) -> bool:
        return self.flush_recommended or self.checkpoint_stale or bool(self.unread_relevant_files)

    def as_dict(self) -> dict[str, object]:
        return {
            "flush_recommended": self.flush_recommended,
            "checkpoint_stale": self.checkpoint_stale,
            "unread_relevant_files": list(self.unread_relevant_files),
            "session_duration_minutes": self.session_duration_minutes,
            "tool_calls_since_checkpoint": self.tool_calls_since_checkpoint,
        }


@dataclass(slots=True)
class SessionState:
    """Mutable per-connection MCP session state shared across tool handlers."""

    session_start: datetime = field(default_factory=_utcnow)
    user_id: str | None = None
    publication_base_branch: str | None = None
    publication_base_ref: str | None = None
    publication_worktree_root: str | None = None
    publication_git_common_dir: str | None = None
    publication_session_branch: str | None = None
    publication_session_branch_ref: str | None = None
    files_read: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    tool_calls: int = 0
    checkpoints: int = 0
    last_checkpoint: datetime | None = None
    last_flush: datetime | None = None
    flush_recommended: bool = False
    unread_relevant: list[str] = field(default_factory=list)
    identity_updates: int = 0
    _tool_calls_at_last_checkpoint: int = field(default=0, init=False, repr=False)

    def record_read(self, path: str) -> None:
        _append_unique(self.files_read, path)
        if path in self.unread_relevant:
            self.unread_relevant.remove(path)

    def record_write(self, path: str) -> None:
        _append_unique(self.files_written, path)

    def record_checkpoint(self) -> None:
        self.checkpoints += 1
        self.last_checkpoint = _utcnow()
        self._tool_calls_at_last_checkpoint = self.tool_calls
        self.flush_recommended = False

    def record_flush(self) -> None:
        self.last_flush = _utcnow()
        self.flush_recommended = False

    def record_tool_call(self) -> int:
        self.tool_calls += 1
        self.flush_recommended = self.should_recommend_flush()
        return self.tool_calls

    def mark_unread_relevant(self, *paths: str) -> None:
        for path in paths:
            _append_unique(self.unread_relevant, path)

    def clear_unread_relevant(self) -> None:
        self.unread_relevant.clear()

    def tool_calls_since_checkpoint(self) -> int:
        if self.last_checkpoint is None:
            return self.tool_calls
        return max(self.tool_calls - self._tool_calls_at_last_checkpoint, 0)

    def session_duration_minutes(self, *, now: datetime | None = None) -> int:
        current = now or _utcnow()
        if current < self.session_start:
            return 0
        return int((current - self.session_start).total_seconds() // 60)

    def should_recommend_flush(self, *, now: datetime | None = None) -> bool:
        duration_minutes = self.session_duration_minutes(now=now)
        tool_calls_since_checkpoint = self.tool_calls_since_checkpoint()
        checkpoint_stale = tool_calls_since_checkpoint > _CHECKPOINT_STALE_TOOL_CALLS
        if checkpoint_stale:
            return True
        return (
            duration_minutes >= _FLUSH_RECOMMEND_MINUTES
            and self.tool_calls >= _FLUSH_RECOMMEND_MIN_TOOL_CALLS
        )

    def get_advisory(self, *, now: datetime | None = None) -> SessionAdvisory:
        current = now or _utcnow()
        tool_calls_since_checkpoint = self.tool_calls_since_checkpoint()
        checkpoint_stale = tool_calls_since_checkpoint > _CHECKPOINT_STALE_TOOL_CALLS
        return SessionAdvisory(
            flush_recommended=self.should_recommend_flush(now=current),
            checkpoint_stale=checkpoint_stale,
            unread_relevant_files=list(self.unread_relevant),
            session_duration_minutes=self.session_duration_minutes(now=current),
            tool_calls_since_checkpoint=tool_calls_since_checkpoint,
        )

    def snapshot(self, *, now: datetime | None = None) -> dict[str, object]:
        advisory = self.get_advisory(now=now)
        return {
            "session_start": self.session_start.isoformat(),
            "user_id": self.user_id,
            "publication_base_branch": self.publication_base_branch,
            "publication_base_ref": self.publication_base_ref,
            "publication_worktree_root": self.publication_worktree_root,
            "publication_git_common_dir": self.publication_git_common_dir,
            "publication_session_branch": self.publication_session_branch,
            "publication_session_branch_ref": self.publication_session_branch_ref,
            "files_read": list(self.files_read),
            "files_written": list(self.files_written),
            "tool_calls_this_session": self.tool_calls,
            "checkpoints_this_session": self.checkpoints,
            "last_checkpoint": self.last_checkpoint.isoformat()
            if self.last_checkpoint is not None
            else None,
            "last_flush": self.last_flush.isoformat() if self.last_flush is not None else None,
            "flush_recommended": advisory.flush_recommended,
            "checkpoint_stale": advisory.checkpoint_stale,
            "session_duration_minutes": advisory.session_duration_minutes,
            "tool_calls_since_checkpoint": advisory.tool_calls_since_checkpoint,
            "unread_relevant_files": list(advisory.unread_relevant_files),
            "identity_updates_this_session": self.identity_updates,
        }

    def reset(self) -> dict[str, object]:
        self.session_start = _utcnow()
        self.files_read.clear()
        self.files_written.clear()
        self.tool_calls = 0
        self.checkpoints = 0
        self.last_checkpoint = None
        self.last_flush = None
        self.flush_recommended = False
        self.unread_relevant.clear()
        self.identity_updates = 0
        self._tool_calls_at_last_checkpoint = 0
        return {"reset": True, **self.snapshot(now=self.session_start)}


def create_session_state(
    *,
    user_id: str | None = None,
    publication_base_branch: str | None = None,
    publication_base_ref: str | None = None,
    publication_worktree_root: str | None = None,
    publication_git_common_dir: str | None = None,
    publication_session_branch: str | None = None,
    publication_session_branch_ref: str | None = None,
) -> SessionState:
    return SessionState(
        user_id=user_id,
        publication_base_branch=publication_base_branch,
        publication_base_ref=publication_base_ref,
        publication_worktree_root=publication_worktree_root,
        publication_git_common_dir=publication_git_common_dir,
        publication_session_branch=publication_session_branch,
        publication_session_branch_ref=publication_session_branch_ref,
    )


__all__ = ["SessionAdvisory", "SessionState", "create_session_state"]
