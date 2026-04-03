"""Centralized pre-write guard pipeline.

Provides a pluggable validation layer that runs before write operations.
Each ``Guard`` subclass implements a ``check()`` method that inspects a
``GuardContext`` and returns a ``GuardResult``.  The ``GuardPipeline``
executes guards in order, short-circuiting on the first ``block`` result.
"""

from __future__ import annotations

import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .errors import MemoryPermissionError, ValidationError
from .frontmatter_policy import validate_frontmatter_metadata, validate_trust_boundary
from .path_policy import (
    validate_raw_move_destination,
    validate_raw_mutation_source,
    validate_raw_write_target,
)

_DEFAULT_MAX_FILE_BYTES = 512_000
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(slots=True)
class GuardContext:
    """Context for a guard check."""

    path: str
    operation: str
    root: Path
    content: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


GuardStatus = Literal["pass", "block", "warn", "require_approval"]


@dataclass(slots=True)
class GuardResult:
    """Result of a single guard check."""

    status: GuardStatus
    guard_name: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "guard_name": self.guard_name,
            "message": self.message,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class PipelineResult:
    """Aggregated result of running all guards."""

    allowed: bool
    results: list[GuardResult]
    warnings: list[str]
    blocked_by: str | None = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "results": [r.to_dict() for r in self.results],
            "warnings": list(self.warnings),
            "blocked_by": self.blocked_by,
            "duration_ms": self.duration_ms,
        }


class Guard(ABC):
    """Abstract base class for pre-write guards."""

    name: str = "guard"

    @abstractmethod
    def check(self, context: GuardContext) -> GuardResult:
        """Evaluate the guard and return a result."""


class PathGuard(Guard):
    """Wraps existing path_policy.py validation."""

    name = "PathGuard"

    def __init__(self, repo: Any) -> None:
        self._repo = repo

    def check(self, context: GuardContext) -> GuardResult:
        try:
            if context.operation == "write":
                validate_raw_write_target(self._repo, context.path)
            elif context.operation == "delete":
                validate_raw_mutation_source(self._repo, context.path, operation="delete")
            elif context.operation == "move":
                validate_raw_move_destination(self._repo, context.path)
        except (MemoryPermissionError, ValidationError) as exc:
            return GuardResult(
                status="block",
                guard_name=self.name,
                message=str(exc),
            )
        return GuardResult(status="pass", guard_name=self.name, message="")


class ContentSizeGuard(Guard):
    """Blocks writes exceeding a configurable file size threshold."""

    name = "ContentSizeGuard"

    def check(self, context: GuardContext) -> GuardResult:
        if context.content is None:
            return GuardResult(status="pass", guard_name=self.name, message="")

        max_bytes = _DEFAULT_MAX_FILE_BYTES
        env_max = os.environ.get("ENGRAM_MAX_FILE_SIZE", "").strip()
        if env_max:
            try:
                max_bytes = int(env_max)
            except ValueError:
                pass

        size = len(context.content.encode("utf-8"))
        if size > max_bytes:
            return GuardResult(
                status="block",
                guard_name=self.name,
                message=(f"Content size {size:,} bytes exceeds limit of {max_bytes:,} bytes"),
                metadata={"size": size, "limit": max_bytes},
            )
        return GuardResult(status="pass", guard_name=self.name, message="")


class FrontmatterGuard(Guard):
    """Validates YAML frontmatter schema on markdown file writes."""

    name = "FrontmatterGuard"

    def check(self, context: GuardContext) -> GuardResult:
        if context.content is None:
            return GuardResult(status="pass", guard_name=self.name, message="")
        if not context.path.endswith(".md"):
            return GuardResult(status="pass", guard_name=self.name, message="")

        match = _FRONTMATTER_RE.match(context.content)
        if match is None:
            return GuardResult(status="pass", guard_name=self.name, message="")

        import yaml

        try:
            fm = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return GuardResult(
                status="block",
                guard_name=self.name,
                message="Frontmatter YAML is malformed",
            )
        if not isinstance(fm, dict):
            return GuardResult(
                status="block",
                guard_name=self.name,
                message="Frontmatter YAML must deserialize to a mapping",
            )

        try:
            validate_frontmatter_metadata(fm)
        except ValidationError as exc:
            return GuardResult(
                status="block",
                guard_name=self.name,
                message=str(exc),
            )

        return GuardResult(status="pass", guard_name=self.name, message="")


class TrustBoundaryGuard(Guard):
    """Prevents unconfirmed trust:high assignment by agents."""

    name = "TrustBoundaryGuard"

    def check(self, context: GuardContext) -> GuardResult:
        if context.content is None:
            return GuardResult(status="pass", guard_name=self.name, message="")
        if not context.path.endswith(".md"):
            return GuardResult(status="pass", guard_name=self.name, message="")

        match = _FRONTMATTER_RE.match(context.content)
        if match is None:
            return GuardResult(status="pass", guard_name=self.name, message="")

        import yaml

        try:
            fm = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return GuardResult(status="pass", guard_name=self.name, message="")
        if not isinstance(fm, dict):
            return GuardResult(status="pass", guard_name=self.name, message="")

        try:
            validate_trust_boundary(fm)
        except ValidationError as exc:
            return GuardResult(
                status="require_approval",
                guard_name=self.name,
                message=str(exc),
                metadata={"trust": fm.get("trust"), "source": fm.get("source")},
            )

        return GuardResult(status="pass", guard_name=self.name, message="")


class GuardPipeline:
    """Executes a sequence of guards, short-circuiting on block."""

    def __init__(self, guards: list[Guard] | None = None) -> None:
        self.guards: list[Guard] = guards or []

    def run(
        self,
        context: GuardContext,
    ) -> PipelineResult:
        start = time.monotonic()
        results: list[GuardResult] = []
        warnings: list[str] = []
        blocked_by: str | None = None

        for guard in self.guards:
            result = guard.check(context)
            results.append(result)

            if result.status == "warn":
                warnings.append(f"{result.guard_name}: {result.message}")
            elif result.status in {"block", "require_approval"}:
                blocked_by = result.guard_name
                break

        elapsed = int((time.monotonic() - start) * 1000)
        allowed = blocked_by is None

        self._emit_trace(context, results, warnings, blocked_by, elapsed)

        return PipelineResult(
            allowed=allowed,
            results=results,
            warnings=warnings,
            blocked_by=blocked_by,
            duration_ms=elapsed,
        )

    def _emit_trace(
        self,
        context: GuardContext,
        results: list[GuardResult],
        warnings: list[str],
        blocked_by: str | None,
        duration_ms: int,
    ) -> None:
        from .plan_utils import record_trace

        session_id = context.session_id
        if not session_id:
            session_id = os.environ.get("MEMORY_SESSION_ID", "").strip() or None
        if not session_id:
            return

        record_trace(
            context.root,
            session_id,
            span_type="guardrail_check",
            name="guard_pipeline",
            status="denied" if blocked_by else "ok",
            duration_ms=duration_ms,
            metadata={
                "path": context.path,
                "operation": context.operation,
                "guards_run": len(results),
                "blocked_by": blocked_by,
                "warnings": warnings,
            },
        )


def default_pipeline(*, repo: Any | None = None) -> GuardPipeline:
    """Build the standard guard pipeline with all built-in guards.

    When *repo* is provided, PathGuard is included as the first stage.
    """
    guards: list[Guard] = []
    if repo is not None:
        guards.append(PathGuard(repo))
    guards.extend(
        [
            ContentSizeGuard(),
            FrontmatterGuard(),
            TrustBoundaryGuard(),
        ]
    )
    return GuardPipeline(guards)


def run_default_guards(
    *,
    path: str,
    operation: str,
    root: Path,
    content: str | None = None,
    repo: Any | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PipelineResult:
    """Run the standard guard pipeline for a pending write-like operation."""
    context = GuardContext(
        path=path,
        operation=operation,
        root=root,
        content=content,
        session_id=session_id,
        metadata=dict(metadata or {}),
    )
    return default_pipeline(repo=repo).run(context)


def require_guarded_write_pass(
    *,
    path: str,
    operation: str,
    root: Path,
    content: str | None = None,
    repo: Any | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PipelineResult:
    """Run the standard guards and raise ValidationError on block/approval."""
    result = run_default_guards(
        path=path,
        operation=operation,
        root=root,
        content=content,
        repo=repo,
        session_id=session_id,
        metadata=metadata,
    )
    if result.allowed:
        return result

    blocked = next(
        guard_result
        for guard_result in result.results
        if guard_result.status in {"block", "require_approval"}
    )
    raise ValidationError(f"Blocked by {blocked.guard_name}: {blocked.message}")


__all__ = [
    "ContentSizeGuard",
    "FrontmatterGuard",
    "Guard",
    "GuardContext",
    "GuardPipeline",
    "GuardResult",
    "GuardStatus",
    "PathGuard",
    "PipelineResult",
    "TrustBoundaryGuard",
    "default_pipeline",
    "require_guarded_write_pass",
    "run_default_guards",
]
