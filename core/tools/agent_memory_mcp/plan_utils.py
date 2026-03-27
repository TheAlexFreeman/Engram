"""Structured YAML plan schema helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date as date_type
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .errors import DuplicateContentError, NotFoundError, ValidationError
from .path_policy import validate_session_id, validate_slug

PLAN_STATUSES = {"draft", "active", "blocked", "paused", "completed", "abandoned"}
PHASE_STATUSES = {"pending", "blocked", "in-progress", "completed", "skipped"}
PLAN_OUTCOMES = {"completed", "partial", "abandoned"}
CHANGE_ACTIONS = {"create", "rewrite", "update", "delete", "rename"}
SOURCE_TYPES = {"internal", "external", "mcp"}
POSTCONDITION_TYPES = {"check", "grep", "test", "manual"}
TRACE_SPAN_TYPES = {"tool_call", "plan_action", "retrieval", "verification", "guardrail_check"}
TRACE_STATUSES = {"ok", "error", "denied"}
COST_TIERS: frozenset[str] = frozenset({"free", "low", "medium", "high"})
APPROVAL_STATUSES: frozenset[str] = frozenset({"pending", "approved", "rejected", "expired"})
APPROVAL_RESOLUTIONS: frozenset[str] = frozenset({"approve", "reject"})

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CREDENTIAL_FIELD_RE = re.compile(r"(key|token|secret|password|auth)", re.IGNORECASE)


def project_plan_path(project_id: str, plan_id: str) -> str:
    return (
        f"memory/working/projects/{validate_slug(project_id, field_name='project_id')}"
        f"/plans/{validate_slug(plan_id, field_name='plan_id')}.yaml"
    )


# Known content-prefix directories (e.g. "core/").  Used as a fallback when
# root is the repository root but project_plan_path returns content-relative
# paths, or when SourceSpec paths redundantly include the content prefix while
# root is already the content root.
_CONTENT_PREFIXES = ("core",)


def _resolve_plan_file(root: Path, project_id: str, plan_id: str) -> Path | None:
    """Locate a plan YAML, tolerating both content-root and repo-root as *root*.

    ``project_plan_path`` returns a content-relative path (``memory/working/…``).
    If *root* is the content root the direct join works.  When *root* is the
    repository root we fall back to checking known content-prefix subdirectories.
    Returns the resolved ``Path`` or ``None`` if the file cannot be found.
    """
    rel = project_plan_path(project_id, plan_id)
    direct = root / rel
    if direct.exists():
        return direct
    for prefix in _CONTENT_PREFIXES:
        candidate = root / prefix / rel
        if candidate.exists():
            return candidate
    return None


def _resolve_content_root(root: Path) -> Path:
    if (root / "memory").exists():
        return root
    for prefix in _CONTENT_PREFIXES:
        candidate = root / prefix
        if (candidate / "memory").exists():
            return candidate
    return root


def _resolve_repo_root(root: Path) -> Path:
    content_root = _resolve_content_root(root)
    if content_root.name in _CONTENT_PREFIXES:
        return content_root.parent
    return content_root


def project_operations_log_path(project_id: str) -> str:
    return (
        f"memory/working/projects/{validate_slug(project_id, field_name='project_id')}"
        "/operations.jsonl"
    )


def project_outbox_root(project_id: str, plan_id: str) -> str:
    return (
        f"memory/working/projects/OUT/{validate_slug(project_id, field_name='project_id')}"
        f"/{validate_slug(plan_id, field_name='plan_id')}"
    )


def outbox_summary_path() -> str:
    return "memory/working/projects/OUT/SUMMARY.md"


def _normalize_repo_relative_path(raw_path: str, *, field_name: str = "path") -> str:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValidationError(f"{field_name} must be a non-empty repo-relative path")

    normalized = raw_path.replace("\\", "/").strip()
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        raise ValidationError(f"{field_name} must be repo-relative: {raw_path!r}")
    if re.match(r"^[A-Za-z]:[/\\]", normalized):
        raise ValidationError(f"{field_name} must be repo-relative: {raw_path!r}")
    return normalized.rstrip("/")


class _PlanDumper(yaml.SafeDumper):
    pass


def _represent_string(dumper: yaml.SafeDumper, value: str) -> yaml.nodes.ScalarNode:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_PlanDumper.add_representer(str, _represent_string)


@dataclass(slots=True)
class ChangeSpec:
    path: str
    action: str
    description: str

    def __post_init__(self) -> None:
        self.path = _normalize_repo_relative_path(self.path)
        if self.action not in CHANGE_ACTIONS:
            raise ValidationError(
                f"change action must be one of {sorted(CHANGE_ACTIONS)}: {self.action!r}"
            )
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValidationError("change description must be a non-empty string")
        self.description = self.description.strip()

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "action": self.action,
            "description": self.description,
        }


@dataclass(slots=True)
class SourceSpec:
    """A source to read/analyze before executing phase changes."""

    path: str
    type: str
    intent: str
    uri: str | None = None
    mcp_server: str | None = None
    mcp_tool: str | None = None
    mcp_arguments: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.type not in SOURCE_TYPES:
            raise ValidationError(
                f"source type must be one of {sorted(SOURCE_TYPES)}: {self.type!r}"
            )
        if not isinstance(self.intent, str) or not self.intent.strip():
            raise ValidationError("source intent must be a non-empty string")
        self.intent = self.intent.strip()
        if self.type == "internal":
            self.path = _normalize_repo_relative_path(self.path, field_name="source path")
        else:
            if not isinstance(self.path, str) or not self.path.strip():
                raise ValidationError("source path must be a non-empty string")
            self.path = self.path.strip()
        if self.type == "external" and not self.uri:
            raise ValidationError("external sources must include a uri")
        if self.mcp_server is not None:
            if self.type != "mcp":
                raise ValidationError("mcp_server is only valid for source type 'mcp'")
            if not isinstance(self.mcp_server, str) or not self.mcp_server.strip():
                raise ValidationError("mcp_server must be a non-empty string when provided")
            self.mcp_server = self.mcp_server.strip()
        if self.mcp_tool is not None:
            if self.type != "mcp":
                raise ValidationError("mcp_tool is only valid for source type 'mcp'")
            if not isinstance(self.mcp_tool, str) or not self.mcp_tool.strip():
                raise ValidationError("mcp_tool must be a non-empty string when provided")
            self.mcp_tool = self.mcp_tool.strip()
        if (self.mcp_server is None) != (self.mcp_tool is None):
            raise ValidationError("mcp sources must provide both mcp_server and mcp_tool")
        if self.mcp_arguments is not None:
            if self.type != "mcp":
                raise ValidationError("mcp_arguments is only valid for source type 'mcp'")
            if not isinstance(self.mcp_arguments, dict):
                raise ValidationError("mcp_arguments must be a mapping when provided")

    def validate_exists(self, root: Path) -> None:
        """Raise if this is an internal source and the file does not exist.

        Handles both conventions: paths may be content-relative (relative to
        the content root, e.g. ``tools/file.py``) or git-relative (including
        the content prefix, e.g. ``core/tools/file.py``).  When *root* is the
        content root and the path redundantly starts with the content-prefix
        directory name we strip the prefix before checking.

        Also checks the repository root (root.parent) when root is a known
        content-prefix directory, so paths like ``HUMANS/docs/DESIGN.md``
        that live outside the content prefix are found.
        """
        if self.type != "internal":
            return
        if (root / self.path).exists():
            return
        # Backward compat: path may include a content prefix that root
        # already incorporates (e.g. root="…/core", path="core/tools/…").
        first, _, rest = self.path.partition("/")
        if first and rest and root.name == first and (root / rest).exists():
            return
        # Repo-root fallback: when root is a content-prefix directory, check
        # the parent (repo root) for paths that live outside the prefix.
        if root.name in _CONTENT_PREFIXES and (root.parent / self.path).exists():
            return
        raise ValidationError(f"internal source does not exist: {self.path}")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "type": self.type,
            "intent": self.intent,
        }
        if self.uri is not None:
            payload["uri"] = self.uri
        if self.mcp_server is not None:
            payload["mcp_server"] = self.mcp_server
        if self.mcp_tool is not None:
            payload["mcp_tool"] = self.mcp_tool
        if self.mcp_arguments is not None:
            payload["mcp_arguments"] = self.mcp_arguments
        return payload


@dataclass(slots=True)
class PostconditionSpec:
    """A success criterion for a phase.

    Always has a free-text description. Optionally includes a formal
    validator type and target for automation.
    """

    description: str
    type: str = "manual"
    target: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValidationError("postcondition description must be a non-empty string")
        self.description = self.description.strip()
        if self.type not in POSTCONDITION_TYPES:
            raise ValidationError(
                f"postcondition type must be one of {sorted(POSTCONDITION_TYPES)}: {self.type!r}"
            )
        if self.type != "manual" and not self.target:
            raise ValidationError(f"postcondition type '{self.type}' requires a non-empty target")
        if self.target is not None:
            if not isinstance(self.target, str) or not self.target.strip():
                raise ValidationError("postcondition target must be a non-empty string")
            self.target = self.target.strip()

    def to_dict(self) -> dict[str, Any]:
        if self.type == "manual" and self.target is None:
            return {"description": self.description}
        payload: dict[str, Any] = {
            "description": self.description,
            "type": self.type,
        }
        if self.target is not None:
            payload["target"] = self.target
        return payload


@dataclass(slots=True)
class PhaseFailure:
    """Record of a failed attempt on a phase."""

    timestamp: str
    reason: str
    verification_results: list[dict[str, Any]] | None = None
    attempt: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, str) or not self.timestamp.strip():
            raise ValidationError("failure timestamp must be a non-empty string")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValidationError("failure reason must be a non-empty string")
        self.timestamp = self.timestamp.strip()
        self.reason = self.reason.strip()
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ValidationError("failure attempt must be an integer >= 1")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "timestamp": self.timestamp,
            "reason": self.reason,
            "attempt": self.attempt,
        }
        if self.verification_results is not None:
            payload["verification_results"] = self.verification_results
        return payload


@dataclass(slots=True)
class PlanPhase:
    id: str
    title: str
    status: str = "pending"
    commit: str | None = None
    blockers: list[str] = field(default_factory=list)
    sources: list[SourceSpec] = field(default_factory=list)
    postconditions: list[PostconditionSpec] = field(default_factory=list)
    requires_approval: bool = False
    changes: list[ChangeSpec] = field(default_factory=list)
    failures: list[PhaseFailure] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.id = validate_slug(self.id, field_name="phase_id")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValidationError("phase title must be a non-empty string")
        self.title = self.title.strip()
        if self.status not in PHASE_STATUSES:
            raise ValidationError(
                f"phase status must be one of {sorted(PHASE_STATUSES)}: {self.status!r}"
            )
        if self.commit is not None and not isinstance(self.commit, str):
            raise ValidationError("phase commit must be a string or null")
        validated_blockers: list[str] = []
        for blocker in self.blockers:
            if not isinstance(blocker, str) or not blocker.strip():
                raise ValidationError("blockers must be non-empty strings")
            validated_blockers.append(blocker.strip())
        self.blockers = validated_blockers

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "commit": self.commit,
            "blockers": list(self.blockers),
        }
        if self.sources:
            payload["sources"] = [source.to_dict() for source in self.sources]
        if self.postconditions:
            payload["postconditions"] = [pc.to_dict() for pc in self.postconditions]
        if self.requires_approval:
            payload["requires_approval"] = True
        payload["changes"] = [change.to_dict() for change in self.changes]
        if self.failures:
            payload["failures"] = [f.to_dict() for f in self.failures]
        return payload


@dataclass(slots=True)
class PlanPurpose:
    summary: str
    context: str
    questions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValidationError("purpose.summary must be a non-empty string")
        if not isinstance(self.context, str) or not self.context.strip():
            raise ValidationError("purpose.context must be a non-empty string")
        self.summary = self.summary.strip()
        self.context = self.context.strip("\n")
        normalized_questions: list[str] = []
        for question in self.questions:
            if not isinstance(question, str) or not question.strip():
                raise ValidationError("purpose.questions must contain non-empty strings")
            normalized_questions.append(question.strip())
        self.questions = normalized_questions

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "context": self.context,
            "questions": list(self.questions),
        }


@dataclass(slots=True)
class PlanReview:
    completed: str
    completed_session: str
    outcome: str
    purpose_assessment: str
    unresolved: list[dict[str, str]] = field(default_factory=list)
    follow_up: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.completed, str) or not self.completed.strip():
            raise ValidationError("review.completed must be a non-empty date string")
        validate_session_id(self.completed_session)
        if self.outcome not in PLAN_OUTCOMES:
            raise ValidationError(
                f"review.outcome must be one of {sorted(PLAN_OUTCOMES)}: {self.outcome!r}"
            )
        if not isinstance(self.purpose_assessment, str) or not self.purpose_assessment.strip():
            raise ValidationError("review.purpose_assessment must be a non-empty string")
        normalized_unresolved: list[dict[str, str]] = []
        for item in self.unresolved:
            if not isinstance(item, dict):
                raise ValidationError("review.unresolved must contain mapping items")
            question = item.get("question")
            note = item.get("note")
            if not isinstance(question, str) or not question.strip():
                raise ValidationError("review.unresolved.question must be a non-empty string")
            if not isinstance(note, str) or not note.strip():
                raise ValidationError("review.unresolved.note must be a non-empty string")
            normalized_unresolved.append({"question": question.strip(), "note": note.strip()})
        self.unresolved = normalized_unresolved
        if self.follow_up is not None:
            self.follow_up = validate_slug(self.follow_up, field_name="follow_up")
        self.purpose_assessment = self.purpose_assessment.strip("\n")

    def to_dict(self) -> dict[str, Any]:
        return {
            "completed": self.completed,
            "completed_session": self.completed_session,
            "outcome": self.outcome,
            "purpose_assessment": self.purpose_assessment,
            "unresolved": list(self.unresolved),
            "follow_up": self.follow_up,
        }


@dataclass(slots=True)
class PlanBudget:
    """Execution budget constraints for a plan."""

    deadline: str | None = None
    max_sessions: int | None = None
    advisory: bool = True

    def __post_init__(self) -> None:
        if self.deadline is not None:
            if not isinstance(self.deadline, str) or not _DATE_RE.match(self.deadline):
                raise ValidationError(
                    f"budget.deadline must be YYYY-MM-DD format: {self.deadline!r}"
                )
        if self.max_sessions is not None:
            if not isinstance(self.max_sessions, int) or self.max_sessions < 1:
                raise ValidationError("budget.max_sessions must be an integer >= 1")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.deadline is not None:
            payload["deadline"] = self.deadline
        if self.max_sessions is not None:
            payload["max_sessions"] = self.max_sessions
        if not self.advisory:
            payload["advisory"] = False
        return payload


@dataclass(slots=True)
class PlanDocument:
    id: str
    project: str
    created: str
    origin_session: str
    status: str
    purpose: PlanPurpose
    phases: list[PlanPhase]
    review: PlanReview | None = None
    budget: PlanBudget | None = None
    sessions_used: int = 0

    def __post_init__(self) -> None:
        self.id = validate_slug(self.id, field_name="plan_id")
        self.project = validate_slug(self.project, field_name="project_id")
        validate_session_id(self.origin_session)
        if not isinstance(self.created, str) or not self.created.strip():
            raise ValidationError("created must be a non-empty date string")
        if self.status not in PLAN_STATUSES:
            raise ValidationError(
                f"plan status must be one of {sorted(PLAN_STATUSES)}: {self.status!r}"
            )
        if not self.phases:
            raise ValidationError("work.phases must contain at least one phase")
        phase_ids = [phase.id for phase in self.phases]
        if len(set(phase_ids)) != len(phase_ids):
            raise ValidationError("work.phases ids must be unique within a plan")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "project": self.project,
            "created": self.created,
            "origin_session": self.origin_session,
            "status": self.status,
        }
        if self.budget is not None:
            payload["budget"] = self.budget.to_dict()
        if self.sessions_used > 0:
            payload["sessions_used"] = self.sessions_used
        payload["purpose"] = self.purpose.to_dict()
        payload["work"] = {"phases": [phase.to_dict() for phase in self.phases]}
        payload["review"] = None if self.review is None else self.review.to_dict()
        return payload


def _coerce_change_specs(raw_changes: Any) -> list[ChangeSpec]:
    if not isinstance(raw_changes, list) or not raw_changes:
        raise ValidationError("phase changes must be a non-empty list")
    changes: list[ChangeSpec] = []
    for raw_change in raw_changes:
        if not isinstance(raw_change, dict):
            raise ValidationError("phase changes must contain mapping items")
        changes.append(
            ChangeSpec(
                path=str(raw_change.get("path", "")),
                action=str(raw_change.get("action", "")),
                description=str(raw_change.get("description", "")),
            )
        )
    return changes


def _coerce_source_specs(raw_sources: Any) -> list[SourceSpec]:
    if raw_sources is None:
        return []
    if not isinstance(raw_sources, list):
        raise ValidationError("phase sources must be a list when provided")
    sources: list[SourceSpec] = []
    for raw_source in raw_sources:
        if not isinstance(raw_source, dict):
            raise ValidationError("phase sources must contain mapping items")
        sources.append(
            SourceSpec(
                path=str(raw_source.get("path", "")),
                type=str(raw_source.get("type", "internal")),
                intent=str(raw_source.get("intent", "")),
                uri=raw_source.get("uri"),
                mcp_server=raw_source.get("mcp_server"),
                mcp_tool=raw_source.get("mcp_tool"),
                mcp_arguments=raw_source.get("mcp_arguments"),
            )
        )
    return sources


def _coerce_postconditions(raw_postconditions: Any) -> list[PostconditionSpec]:
    if raw_postconditions is None:
        return []
    if not isinstance(raw_postconditions, list):
        raise ValidationError("phase postconditions must be a list when provided")
    specs: list[PostconditionSpec] = []
    for item in raw_postconditions:
        if isinstance(item, str):
            # Bare string shorthand → manual postcondition
            specs.append(PostconditionSpec(description=item))
        elif isinstance(item, dict):
            specs.append(
                PostconditionSpec(
                    description=str(item.get("description", "")),
                    type=str(item.get("type", "manual")),
                    target=item.get("target"),
                )
            )
        else:
            raise ValidationError("postconditions must contain strings or mapping items")
    return specs


def _coerce_failures(raw_failures: Any) -> list[PhaseFailure]:
    if raw_failures is None:
        return []
    if not isinstance(raw_failures, list):
        raise ValidationError("phase failures must be a list when provided")
    failures: list[PhaseFailure] = []
    for item in raw_failures:
        if not isinstance(item, dict):
            raise ValidationError("phase failures must contain mapping items")
        failures.append(
            PhaseFailure(
                timestamp=str(item.get("timestamp", "")),
                reason=str(item.get("reason", "")),
                verification_results=item.get("verification_results"),
                attempt=int(item.get("attempt", len(failures) + 1)),
            )
        )
    return failures


def _coerce_budget(raw_budget: Any) -> PlanBudget | None:
    if raw_budget is None:
        return None
    if not isinstance(raw_budget, dict):
        raise ValidationError("budget must be null or a mapping")
    deadline = raw_budget.get("deadline")
    max_sessions = raw_budget.get("max_sessions")
    advisory = raw_budget.get("advisory", True)
    return PlanBudget(
        deadline=None if deadline is None else str(deadline),
        max_sessions=int(max_sessions) if max_sessions is not None else None,
        advisory=bool(advisory),
    )


def _coerce_phases(raw_phases: Any) -> list[PlanPhase]:
    if not isinstance(raw_phases, list) or not raw_phases:
        raise ValidationError("work.phases must be a non-empty list")
    phases: list[PlanPhase] = []
    for raw_phase in raw_phases:
        if not isinstance(raw_phase, dict):
            raise ValidationError("work.phases must contain mapping items")
        blockers = raw_phase.get("blockers")
        if blockers is None:
            blockers = []
        if not isinstance(blockers, list):
            raise ValidationError("phase blockers must be a list when provided")
        phases.append(
            PlanPhase(
                id=str(raw_phase.get("id", "")),
                title=str(raw_phase.get("title", "")),
                status=str(raw_phase.get("status", "pending")),
                commit=raw_phase.get("commit")
                if raw_phase.get("commit") is None
                else str(raw_phase.get("commit")),
                blockers=[str(blocker) for blocker in blockers],
                sources=_coerce_source_specs(raw_phase.get("sources")),
                postconditions=_coerce_postconditions(raw_phase.get("postconditions")),
                requires_approval=bool(raw_phase.get("requires_approval", False)),
                changes=_coerce_change_specs(raw_phase.get("changes")),
                failures=_coerce_failures(raw_phase.get("failures")),
            )
        )
    return phases


def _coerce_review(raw_review: Any) -> PlanReview | None:
    if raw_review is None:
        return None
    if not isinstance(raw_review, dict):
        raise ValidationError("review must be null or a mapping")
    unresolved = raw_review.get("unresolved") or []
    if not isinstance(unresolved, list):
        raise ValidationError("review.unresolved must be a list")
    follow_up = raw_review.get("follow_up")
    return PlanReview(
        completed=str(raw_review.get("completed", "")),
        completed_session=str(raw_review.get("completed_session", "")),
        outcome=str(raw_review.get("outcome", "")),
        purpose_assessment=str(raw_review.get("purpose_assessment", "")),
        unresolved=[dict(item) for item in unresolved],
        follow_up=None if follow_up is None else str(follow_up),
    )


def load_plan(abs_path: Path, root: Path | None = None) -> PlanDocument:
    try:
        raw = yaml.safe_load(abs_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML plan file: {abs_path.name}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValidationError(f"Plan file must contain a top-level mapping: {abs_path.name}")

    purpose = raw.get("purpose")
    if not isinstance(purpose, dict):
        raise ValidationError("purpose must be a mapping")
    work = raw.get("work")
    if not isinstance(work, dict):
        raise ValidationError("work must be a mapping")

    plan = PlanDocument(
        id=str(raw.get("id", "")),
        project=str(raw.get("project", "")),
        created=str(raw.get("created", "")),
        origin_session=str(raw.get("origin_session", "")),
        status=str(raw.get("status", "")),
        purpose=PlanPurpose(
            summary=str(purpose.get("summary", "")),
            context=str(purpose.get("context", "")),
            questions=[str(item) for item in purpose.get("questions", []) or []],
        ),
        phases=_coerce_phases(work.get("phases")),
        review=_coerce_review(raw.get("review")),
        budget=_coerce_budget(raw.get("budget")),
        sessions_used=int(raw.get("sessions_used", 0)),
    )
    if root is not None:
        validate_plan_references(plan, root)
    return plan


def save_plan(abs_path: Path, plan: PlanDocument, root: Path | None = None) -> None:
    if root is not None:
        validate_plan_references(plan, root)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.dump(
        plan.to_dict(),
        Dumper=_PlanDumper,
        sort_keys=False,
        allow_unicode=False,
        width=88,
    )
    abs_path.write_text(text, encoding="utf-8")


def _resolve_phase(plan: PlanDocument, phase_id: str) -> PlanPhase:
    for phase in plan.phases:
        if phase.id == phase_id:
            return phase
    raise NotFoundError(f"Plan '{plan.id}' does not define phase '{phase_id}'")


def validate_plan_references(plan: PlanDocument, root: Path) -> None:
    for phase in plan.phases:
        for blocker in phase.blockers:
            if ":" not in blocker:
                _resolve_phase(plan, blocker)
                continue
            other_plan_id, other_phase_id = blocker.split(":", 1)
            other_plan_path = _resolve_plan_file(root, plan.project, other_plan_id)
            if other_plan_path is None:
                raise ValidationError(
                    f"blocker references missing plan '{other_plan_id}' in project '{plan.project}'"
                )
            other_plan = load_plan(other_plan_path)
            _resolve_phase(other_plan, other_phase_id)
        for source in phase.sources:
            source.validate_exists(root)


def plan_title(plan: PlanDocument) -> str:
    return plan.purpose.summary


def plan_progress(plan: PlanDocument) -> tuple[int, int]:
    completed = sum(1 for phase in plan.phases if phase.status == "completed")
    return completed, len(plan.phases)


def next_phase(plan: PlanDocument) -> PlanPhase | None:
    for phase in plan.phases:
        if phase.status in {"pending", "blocked", "in-progress"}:
            return phase
    return None


def next_action(plan: PlanDocument) -> dict[str, Any] | None:
    """Return a structured directive for the next actionable phase.

    Returns a dict with id, title, sources, requires_approval so the
    calling agent knows what to read and whether to pause for approval.
    """
    phase = next_phase(plan)
    if phase is None:
        return None
    directive: dict[str, Any] = {
        "id": phase.id,
        "title": phase.title,
        "requires_approval": phase.requires_approval,
    }
    if phase.sources:
        directive["sources"] = [source.to_dict() for source in phase.sources]
    if phase.postconditions:
        directive["postconditions"] = [pc.to_dict() for pc in phase.postconditions]
    attempt_number = len(phase.failures) + 1
    directive["attempt_number"] = attempt_number
    directive["has_prior_failures"] = bool(phase.failures)
    if len(phase.failures) >= 3:
        directive["suggest_revision"] = True
    return directive


def phase_change_class(phase: PlanPhase) -> str:
    for change in phase.changes:
        if not change.path.startswith("memory/"):
            return "protected"
    return "proposed"


def phase_blockers(
    plan: PlanDocument,
    phase: PlanPhase,
    root: Path,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for index, candidate in enumerate(plan.phases):
        if candidate.id != phase.id:
            continue
        if index > 0:
            previous = plan.phases[index - 1]
            satisfied = previous.status in {"completed", "skipped"}
            blockers.append(
                {
                    "reference": previous.id,
                    "kind": "implicit",
                    "satisfied": satisfied,
                    "status": previous.status,
                    "commit": previous.commit,
                    "detail": previous.title,
                }
            )
        break

    for blocker in phase.blockers:
        if ":" not in blocker:
            other_phase = _resolve_phase(plan, blocker)
            blockers.append(
                {
                    "reference": blocker,
                    "kind": "intra-plan",
                    "satisfied": other_phase.status in {"completed", "skipped"},
                    "status": other_phase.status,
                    "commit": other_phase.commit,
                    "detail": other_phase.title,
                }
            )
            continue

        other_plan_id, other_phase_id = blocker.split(":", 1)
        other_plan_path = _resolve_plan_file(root, plan.project, other_plan_id)
        if other_plan_path is None:
            blockers.append(
                {
                    "reference": blocker,
                    "kind": "inter-plan",
                    "satisfied": False,
                    "status": "missing-plan",
                    "commit": None,
                    "detail": f"Missing plan {other_plan_id}",
                }
            )
            continue
        other_plan = load_plan(other_plan_path)
        other_phase = _resolve_phase(other_plan, other_phase_id)
        blockers.append(
            {
                "reference": blocker,
                "kind": "inter-plan",
                "satisfied": other_phase.status in {"completed", "skipped"}
                and bool(other_phase.commit),
                "status": other_phase.status,
                "commit": other_phase.commit,
                "detail": other_phase.title,
            }
        )
    return blockers


def unresolved_blockers(plan: PlanDocument, phase: PlanPhase, root: Path) -> list[dict[str, Any]]:
    return [entry for entry in phase_blockers(plan, phase, root) if not entry["satisfied"]]


def budget_status(plan: PlanDocument) -> dict[str, Any] | None:
    """Return budget consumption info, or None if no budget is set."""
    if plan.budget is None:
        return None
    status: dict[str, Any] = {
        "sessions_used": plan.sessions_used,
        "advisory": plan.budget.advisory,
    }
    if plan.budget.deadline is not None:
        from datetime import date as date_type

        try:
            deadline = date_type.fromisoformat(plan.budget.deadline)
            today = date_type.today()
            status["deadline"] = plan.budget.deadline
            status["days_remaining"] = (deadline - today).days
            status["past_deadline"] = today > deadline
        except ValueError:
            status["deadline"] = plan.budget.deadline
            status["days_remaining"] = None
            status["past_deadline"] = False
    if plan.budget.max_sessions is not None:
        status["max_sessions"] = plan.budget.max_sessions
        status["sessions_remaining"] = plan.budget.max_sessions - plan.sessions_used
        status["over_session_budget"] = plan.sessions_used >= plan.budget.max_sessions
    status["over_budget"] = status.get("past_deadline", False) or status.get(
        "over_session_budget", False
    )
    return status


def phase_payload(plan: PlanDocument, phase: PlanPhase, root: Path) -> dict[str, Any]:
    blockers = phase_blockers(plan, phase, root)
    phase_dict: dict[str, Any] = {
        "id": phase.id,
        "title": phase.title,
        "status": phase.status,
        "commit": phase.commit,
        "blockers": blockers,
        "changes": [change.to_dict() for change in phase.changes],
        "change_class": phase_change_class(phase),
        "approval_required": (
            phase.requires_approval or phase_change_class(phase) in {"proposed", "protected"}
        ),
        "requires_approval": phase.requires_approval,
    }
    if phase.sources:
        phase_dict["sources"] = [source.to_dict() for source in phase.sources]
    if phase.postconditions:
        phase_dict["postconditions"] = [pc.to_dict() for pc in phase.postconditions]
    phase_dict["failures"] = [f.to_dict() for f in phase.failures]
    phase_dict["attempt_number"] = len(phase.failures) + 1

    result: dict[str, Any] = {
        "plan_id": plan.id,
        "project_id": plan.project,
        "plan_status": plan.status,
        "phase": phase_dict,
        "purpose": plan.purpose.to_dict(),
        "progress": {
            "done": plan_progress(plan)[0],
            "total": plan_progress(plan)[1],
            "next_action": next_action(plan),
        },
    }
    bs = budget_status(plan)
    if bs is not None:
        result["budget_status"] = bs
    result["tool_policies"] = _resolve_tool_policies(phase, root)
    fetch_directives: list[dict[str, Any]] = []
    mcp_calls: list[dict[str, Any]] = []
    for index, source in enumerate(phase.sources):
        if _resolve_verify_path(root, source.path) is not None:
            continue
        if source.type == "external":
            fetch_directives.append(
                {
                    "source_index": index,
                    "action": "fetch_and_stage",
                    "source_path": source.path,
                    "source_uri": source.uri,
                    "suggested_filename": Path(source.path).name or source.path,
                    "target_project": plan.project,
                    "intent": source.intent,
                    "reason": (
                        "Source file does not exist on disk; fetch and stage before "
                        "starting phase work."
                    ),
                }
            )
        elif source.type == "mcp" and source.mcp_server and source.mcp_tool:
            mcp_calls.append(
                {
                    "source_index": index,
                    "server": source.mcp_server,
                    "tool": source.mcp_tool,
                    "arguments": source.mcp_arguments or {},
                    "source_path": source.path,
                    "suggested_filename": Path(source.path).name or source.path,
                    "target_project": plan.project,
                    "intent": source.intent,
                }
            )
    result["fetch_directives"] = fetch_directives
    result["mcp_calls"] = mcp_calls
    return result


def _serialized_length(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except TypeError:
        return len(str(value))


def _truncate_briefing_text(text: str, limit: int) -> tuple[str, bool]:
    if limit <= 0:
        return "", bool(text)
    if len(text) <= limit:
        return text, False

    marker = "\n...\n"
    if limit <= len(marker) + 20:
        return text[:limit], True

    head = max(1, (limit - len(marker)) // 2)
    tail = max(1, limit - len(marker) - head)
    return f"{text[:head]}{marker}{text[-tail:]}", True


def _allocate_source_budgets(lengths: list[int], total_budget: int) -> list[int]:
    if not lengths:
        return []
    if total_budget <= 0:
        return [0] * len(lengths)

    total_length = sum(lengths)
    if total_length <= total_budget:
        return list(lengths)

    minimum = 200
    count = len(lengths)
    if total_budget < minimum * count:
        even_share = total_budget // count
        return [min(length, even_share) for length in lengths]

    budgets = [min(length, minimum) for length in lengths]
    remaining = total_budget - sum(budgets)
    desired = [max(length - budget, 0) for length, budget in zip(lengths, budgets, strict=False)]
    desired_total = sum(desired)

    if remaining <= 0 or desired_total <= 0:
        return budgets

    allocations = [0] * count
    allocated = 0
    for index, want in enumerate(desired):
        share = min(want, (remaining * want) // desired_total)
        allocations[index] = share
        allocated += share

    leftover = remaining - allocated
    for index, want in sorted(enumerate(desired), key=lambda item: item[1], reverse=True):
        if leftover <= 0:
            break
        spare = want - allocations[index]
        if spare <= 0:
            continue
        bump = min(spare, leftover)
        allocations[index] += bump
        leftover -= bump

    return [
        min(length, budget + allocations[index])
        for index, (length, budget) in enumerate(zip(lengths, budgets, strict=False))
    ]


def _failure_summary(phase: PlanPhase) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for failure in reversed(phase.failures):
        entry = {
            "attempt": failure.attempt,
            "timestamp": failure.timestamp,
            "reason": failure.reason,
        }
        failed_postconditions: list[str] = []
        for result in failure.verification_results or []:
            status = str(result.get("status", ""))
            if status not in {"fail", "error"}:
                continue
            description = result.get("description") or result.get("target") or result.get("type")
            if description is not None:
                failed_postconditions.append(str(description))
        if failed_postconditions:
            entry["failed_postconditions"] = failed_postconditions
        summary.append(entry)
    return summary


def _collect_recent_plan_traces(
    root: Path,
    plan_id: str,
    *,
    session_id: str | None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    def _matching_from_files(trace_files: list[Path]) -> list[dict[str, Any]]:
        spans: list[dict[str, Any]] = []
        for trace_file in trace_files:
            try:
                lines = trace_file.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for raw_line in reversed(lines):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    span = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(span, dict):
                    continue
                metadata = span.get("metadata")
                if not isinstance(metadata, dict) or metadata.get("plan_id") != plan_id:
                    continue
                spans.append(
                    {
                        "span_type": span.get("span_type"),
                        "name": span.get("name"),
                        "status": span.get("status"),
                        "duration_ms": span.get("duration_ms"),
                        "timestamp": span.get("timestamp"),
                    }
                )
                if len(spans) >= limit:
                    return spans
        return spans

    preferred_files: list[Path] = []
    seen_files: set[Path] = set()
    if session_id:
        preferred = root / trace_file_path(session_id)
        if preferred.exists():
            preferred_files.append(preferred)
            seen_files.add(preferred)

    preferred_spans = _matching_from_files(preferred_files)
    if preferred_spans:
        return preferred_spans[:limit]

    activity_root = root / "memory" / "activity"
    if not activity_root.is_dir():
        return []

    fallback_files = [
        trace_file
        for trace_file in sorted(activity_root.rglob("*.traces.jsonl"), reverse=True)
        if trace_file not in seen_files
    ]
    return _matching_from_files(fallback_files)[:limit]


def assemble_briefing(
    plan: PlanDocument,
    phase: PlanPhase,
    root: Path,
    *,
    max_context_chars: int = 8000,
    include_sources: bool = True,
    include_traces: bool = True,
    include_approval: bool = True,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Assemble a single-call briefing packet for a plan phase."""
    if max_context_chars < 0:
        raise ValidationError("max_context_chars must be >= 0")

    phase_section = phase_payload(plan, phase, root)
    failure_summary = _failure_summary(phase)

    approval_status: dict[str, Any] | None = None
    if include_approval and phase.requires_approval:
        approval = load_approval(root, plan.id, phase.id)
        if approval is not None:
            approval_status = approval.to_dict()

    recent_traces: list[dict[str, Any]] = []
    trace_truncated = False
    if include_traces:
        recent_traces = _collect_recent_plan_traces(root, plan.id, session_id=session_id)
        if max_context_chars > 0:
            trace_budget = max(0, int(max_context_chars * 0.15))
            while recent_traces and _serialized_length(recent_traces) > trace_budget:
                recent_traces.pop()
                trace_truncated = True

    phase_chars = _serialized_length(phase_section)
    failure_chars = _serialized_length(failure_summary)
    approval_chars = _serialized_length(approval_status) if approval_status is not None else 0
    trace_chars = _serialized_length(recent_traces)

    source_contents: list[dict[str, Any]] = []
    internal_sources: list[tuple[dict[str, Any], str]] = []
    if include_sources:
        for source in phase.sources:
            entry: dict[str, Any] = {
                "path": source.path,
                "type": source.type,
                "intent": source.intent,
            }
            if source.uri is not None:
                entry["uri"] = source.uri
            if source.mcp_server is not None:
                entry["mcp_server"] = source.mcp_server
            if source.mcp_tool is not None:
                entry["mcp_tool"] = source.mcp_tool
            if source.mcp_arguments is not None:
                entry["mcp_arguments"] = source.mcp_arguments

            if source.type != "internal":
                entry["content"] = None
                source_contents.append(entry)
                continue

            resolved = _resolve_verify_path(root, source.path)
            if resolved is None or not resolved.is_file():
                entry["content"] = None
                entry["error"] = "file not found"
                source_contents.append(entry)
                continue

            try:
                text = resolved.read_text(encoding="utf-8")
            except OSError as exc:
                entry["content"] = None
                entry["error"] = str(exc)
                source_contents.append(entry)
                continue

            internal_sources.append((entry, text))

        source_budget = 0
        if max_context_chars == 0:
            source_budgets = [len(text) for _, text in internal_sources]
        else:
            fixed_chars = phase_chars + failure_chars + approval_chars + trace_chars
            source_budget = max(max_context_chars - fixed_chars, 0)
            source_budgets = _allocate_source_budgets(
                [len(text) for _, text in internal_sources],
                source_budget,
            )

        for (entry, text), budget in zip(internal_sources, source_budgets, strict=False):
            content = text
            truncated = False
            if max_context_chars != 0:
                content, truncated = _truncate_briefing_text(text, budget)
            entry["content"] = content
            entry["full_length"] = len(text)
            entry["truncated"] = truncated
            source_contents.append(entry)

    source_chars = _serialized_length(source_contents)
    total_chars = phase_chars + failure_chars + approval_chars + trace_chars + source_chars
    truncated = trace_truncated or any(entry.get("truncated") for entry in source_contents)

    return {
        "plan_id": plan.id,
        "project_id": plan.project,
        "phase_id": phase.id,
        "phase": phase_section,
        "source_contents": source_contents,
        "failure_summary": failure_summary,
        "recent_traces": recent_traces,
        "approval_status": approval_status,
        "context_budget": {
            "max_context_chars": max_context_chars,
            "total_chars": total_chars,
            "estimated_tokens": (total_chars + 3) // 4,
            "truncated": truncated,
            "breakdown": {
                "phase": phase_chars,
                "source_contents": source_chars,
                "failure_summary": failure_chars,
                "recent_traces": trace_chars,
                "approval_status": approval_chars,
            },
        },
    }


_MAX_STAGED_EXTERNAL_CHARS = 500_000


def _project_root(root: Path, project_id: str) -> Path:
    project_slug = validate_slug(project_id, field_name="project_id")
    content_root = _resolve_content_root(root)
    return content_root / "memory" / "working" / "projects" / project_slug


def _sanitize_origin_url(source_url: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    if not isinstance(source_url, str) or not source_url.strip():
        raise ValidationError("source_url must be a non-empty string")
    parts = urlsplit(source_url.strip())
    if not parts.scheme:
        raise ValidationError("source_url must include a URI scheme")
    if parts.scheme != "file" and not parts.netloc:
        raise ValidationError("source_url must include a network location")
    sanitized = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    if not sanitized:
        raise ValidationError("source_url could not be sanitized")
    return sanitized


def _normalize_staged_filename(filename: str) -> str:
    if not isinstance(filename, str) or not filename.strip():
        raise ValidationError("filename must be a non-empty string")
    normalized = filename.replace("\\", "/").strip()
    if normalized in {".", ".."} or "/" in normalized:
        raise ValidationError("filename must not include directory segments")
    return normalized


def _staged_hash_registry_path(root: Path, project_id: str) -> Path:
    return _project_root(root, project_id) / ".staged-hashes.jsonl"


def _read_staged_hash_registry(root: Path, project_id: str) -> dict[str, str]:
    registry_path = _staged_hash_registry_path(root, project_id)
    if not registry_path.exists():
        return {}
    registry: dict[str, str] = {}
    try:
        lines = registry_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValidationError(f"Could not read staged hash registry: {exc}") from exc
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid staged hash registry entry: {exc}") from exc
        if not isinstance(entry, dict):
            continue
        content_hash = entry.get("hash")
        filename = entry.get("filename")
        if isinstance(content_hash, str) and isinstance(filename, str):
            registry[content_hash] = filename
    return registry


def stage_external_file(
    project: str,
    filename: str,
    content: str,
    source_url: str,
    fetched_date: str,
    source_label: str,
    *,
    root: Path,
    session_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Stage external content into a project IN/ folder with governed frontmatter."""
    import hashlib

    if not isinstance(content, str) or not content:
        raise ValidationError("content must be a non-empty string")
    if len(content) > _MAX_STAGED_EXTERNAL_CHARS:
        raise ValidationError(
            f"content exceeds maximum size of {_MAX_STAGED_EXTERNAL_CHARS} characters"
        )
    if not isinstance(fetched_date, str) or not _DATE_RE.match(fetched_date.strip()):
        raise ValidationError("fetched_date must be in YYYY-MM-DD format")
    if not isinstance(source_label, str) or not source_label.strip():
        raise ValidationError("source_label must be a non-empty string")
    if session_id is not None:
        validate_session_id(session_id)

    project_root = _project_root(root, project)
    if not project_root.exists():
        raise NotFoundError(f"Project not found: memory/working/projects/{project}")

    staged_filename = _normalize_staged_filename(filename)
    sanitized_url = _sanitize_origin_url(source_url)
    content_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"
    registry = _read_staged_hash_registry(root, project)
    if content_hash in registry:
        raise DuplicateContentError(
            f"Duplicate staged content already exists: {registry[content_hash]}",
            content_hash=content_hash,
            existing_filename=registry[content_hash],
        )

    target_path = project_root / "IN" / staged_filename
    if target_path.exists():
        raise ValidationError(f"target file already exists: {target_path.name}")

    frontmatter_preview: dict[str, Any] = {
        "source": "external-research",
        "trust": "low",
        "origin_url": sanitized_url,
        "fetched_date": fetched_date.strip(),
        "source_label": source_label.strip(),
        "created": date_type.today().isoformat(),
        "origin_session": session_id or "unknown",
        "staged_by": "memory_stage_external",
    }
    envelope = {
        "action": "stage_external",
        "project": validate_slug(project, field_name="project_id"),
        "target_path": target_path.relative_to(_resolve_content_root(root)).as_posix(),
        "frontmatter_preview": frontmatter_preview,
        "content_chars": len(content),
        "content_hash": content_hash,
        "duplicate": False,
        "staged": False,
    }
    if dry_run:
        return envelope

    target_path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter_text = yaml.dump(
        frontmatter_preview,
        Dumper=_PlanDumper,
        sort_keys=False,
        allow_unicode=False,
        width=88,
    )
    body = content if content.endswith("\n") else f"{content}\n"
    target_path.write_text(f"---\n{frontmatter_text}---\n\n{body}", encoding="utf-8")

    registry_path = _staged_hash_registry_path(root, project)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    staged_at = date_type.today().isoformat()
    with registry_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "hash": content_hash,
                    "filename": staged_filename,
                    "staged_at": staged_at,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    envelope["staged"] = True
    return envelope


def _read_watch_folders(root: Path) -> list[dict[str, Any]]:
    import tomllib

    repo_root = _resolve_repo_root(root)
    bootstrap_path = repo_root / "agent-bootstrap.toml"
    if not bootstrap_path.exists():
        return []
    try:
        raw = tomllib.loads(bootstrap_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValidationError(f"Could not load agent-bootstrap.toml: {exc}") from exc
    watch_folders = raw.get("watch_folders", [])
    if watch_folders is None:
        return []
    if not isinstance(watch_folders, list):
        raise ValidationError("watch_folders must be an array of tables")
    normalized: list[dict[str, Any]] = []
    for item in watch_folders:
        if not isinstance(item, dict):
            raise ValidationError("watch_folders entries must be mappings")
        normalized.append(item)
    return normalized


def _extract_pdf_text(abs_path: Path) -> tuple[str | None, str | None]:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(abs_path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if not text:
            return None, "PDF extraction produced no text"
        return text, None
    except ModuleNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001
        return None, f"PDF extraction failed: {exc}"

    try:
        from pdfminer.high_level import extract_text  # type: ignore[import-not-found]

        text = extract_text(str(abs_path)).strip()
        if not text:
            return None, "PDF extraction produced no text"
        return text, None
    except ModuleNotFoundError:
        return None, "PDF extraction unavailable; install pdfminer.six or pypdf"
    except Exception as exc:  # noqa: BLE001
        return None, f"PDF extraction failed: {exc}"


def scan_drop_zone(
    *,
    root: Path,
    project_filter: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Scan configured watch folders and stage new content into project inboxes."""
    repo_root = _resolve_repo_root(root)
    watch_folders = _read_watch_folders(root)
    if project_filter is not None:
        project_filter = validate_slug(project_filter, field_name="project_filter")

    items: list[dict[str, Any]] = []
    folders_scanned = 0
    files_found = 0
    staged_count = 0
    duplicate_count = 0
    error_count = 0

    for entry in watch_folders:
        target_project = validate_slug(
            str(entry.get("target_project", "")), field_name="target_project"
        )
        if project_filter is not None and target_project != project_filter:
            continue
        raw_path = str(entry.get("path", "")).strip()
        if not raw_path:
            error_count += 1
            items.append(
                {
                    "filename": "",
                    "target_project": target_project,
                    "outcome": "error",
                    "hash": None,
                    "error_message": "watch_folders entry is missing path",
                }
            )
            continue
        folder_path = Path(raw_path)
        if not folder_path.is_absolute():
            folder_path = (repo_root / folder_path).resolve()
        else:
            folder_path = folder_path.resolve()

        try:
            folder_path.relative_to(repo_root)
            inside_repo = True
        except ValueError:
            inside_repo = False
        if inside_repo:
            error_count += 1
            items.append(
                {
                    "filename": folder_path.name,
                    "target_project": target_project,
                    "outcome": "error",
                    "hash": None,
                    "error_message": "watch_folder cannot point inside the Engram repository",
                }
            )
            continue

        folders_scanned += 1
        if not folder_path.exists() or not folder_path.is_dir():
            error_count += 1
            items.append(
                {
                    "filename": folder_path.name,
                    "target_project": target_project,
                    "outcome": "error",
                    "hash": None,
                    "error_message": f"watch_folder not found: {folder_path}",
                }
            )
            continue

        source_label = str(entry.get("source_label", "")).strip() or folder_path.name
        recursive = bool(entry.get("recursive", False))
        extensions = entry.get("extensions") or [".md", ".txt", ".pdf"]
        if not isinstance(extensions, list):
            raise ValidationError("watch_folders.extensions must be a list when provided")
        normalized_extensions = {str(ext).lower() for ext in extensions}
        iterator = folder_path.rglob("*") if recursive else folder_path.glob("*")

        for abs_file in sorted(path for path in iterator if path.is_file()):
            if abs_file.suffix.lower() not in normalized_extensions:
                continue
            files_found += 1
            try:
                if abs_file.suffix.lower() == ".pdf":
                    content, error_message = _extract_pdf_text(abs_file)
                    if content is None:
                        error_count += 1
                        items.append(
                            {
                                "filename": abs_file.name,
                                "target_project": target_project,
                                "outcome": "error",
                                "hash": None,
                                "error_message": error_message,
                            }
                        )
                        continue
                    stage_filename = f"{abs_file.stem}.md"
                else:
                    content = abs_file.read_text(encoding="utf-8", errors="replace")
                    stage_filename = abs_file.name

                envelope = stage_external_file(
                    target_project,
                    stage_filename,
                    content,
                    abs_file.resolve().as_uri(),
                    date_type.fromtimestamp(abs_file.stat().st_mtime).isoformat(),
                    source_label,
                    root=root,
                    session_id=session_id,
                    dry_run=False,
                )
                staged_count += 1
                items.append(
                    {
                        "filename": abs_file.name,
                        "target_project": target_project,
                        "outcome": "staged",
                        "hash": envelope["content_hash"],
                        "error_message": None,
                    }
                )
            except DuplicateContentError as exc:
                duplicate_count += 1
                items.append(
                    {
                        "filename": abs_file.name,
                        "target_project": target_project,
                        "outcome": "duplicate",
                        "hash": exc.content_hash or None,
                        "error_message": exc.existing_filename or str(exc),
                    }
                )
            except (OSError, ValidationError, NotFoundError) as exc:
                error_count += 1
                items.append(
                    {
                        "filename": abs_file.name,
                        "target_project": target_project,
                        "outcome": "error",
                        "hash": None,
                        "error_message": str(exc),
                    }
                )

    return {
        "folders_scanned": folders_scanned,
        "files_found": files_found,
        "staged_count": staged_count,
        "duplicate_count": duplicate_count,
        "error_count": error_count,
        "items": items,
    }


def resolve_phase(plan: PlanDocument, phase_id: str | None = None) -> PlanPhase:
    if phase_id is not None:
        return _resolve_phase(plan, validate_slug(phase_id, field_name="phase_id"))
    phase = next_phase(plan)
    if phase is None:
        raise NotFoundError(f"Plan '{plan.id}' has no pending phases")
    return phase


def build_review_from_input(
    raw_review: dict[str, Any], completed: str, session_id: str
) -> PlanReview:
    return PlanReview(
        completed=completed,
        completed_session=session_id,
        outcome=str(raw_review.get("outcome", "completed")),
        purpose_assessment=str(raw_review.get("purpose_assessment", "")),
        unresolved=[dict(item) for item in raw_review.get("unresolved", []) or []],
        follow_up=(
            None if raw_review.get("follow_up") is None else str(raw_review.get("follow_up"))
        ),
    )


def coerce_phase_inputs(phases: list[dict[str, Any]]) -> list[PlanPhase]:
    return _coerce_phases(phases)


def coerce_budget_input(raw_budget: dict[str, Any] | None) -> PlanBudget | None:
    """Public wrapper for budget coercion from tool-layer dicts."""
    return _coerce_budget(raw_budget)


def exportable_artifacts(root: Path, plan: PlanDocument) -> list[str]:
    plan_path = project_plan_path(plan.project, plan.id)
    artifacts: list[str] = []
    seen: set[str] = set()
    for phase in plan.phases:
        for change in phase.changes:
            if change.path == plan_path or change.path.endswith("/SUMMARY.md"):
                continue
            if change.path in seen:
                continue
            abs_path = root / change.path
            if abs_path.is_file():
                artifacts.append(change.path)
                seen.add(change.path)
    return artifacts


# ── Postcondition verification ──────────────────────────────────────────

# Command prefixes considered safe for test-type postconditions.
# Each entry is a prefix: the target command (after whitespace normalization)
# must start with one of these strings.
VERIFY_TEST_ALLOWLIST: tuple[str, ...] = (
    "pre-commit run",
    "pytest",
    "python -m pytest",
    "ruff check",
    "ruff format --check",
    "mypy",
)

# Shell metacharacters that indicate command chaining / injection.
_SHELL_META_RE = re.compile(r"[;|&`$]")


def _resolve_verify_path(root: Path, target: str) -> Path | None:
    """Resolve a postcondition target path using the same fallback logic as SourceSpec."""
    candidate = root / target
    if candidate.exists():
        return candidate
    # Content-prefix fallback: path may include "core/" when root already is core/.
    first, _, rest = target.partition("/")
    if first and rest and root.name == first and (root / rest).exists():
        return root / rest
    # Repo-root fallback: when root is a content-prefix dir.
    if root.name in _CONTENT_PREFIXES and (root.parent / target).exists():
        return root.parent / target
    return None


def _validate_check(root: Path, target: str) -> dict[str, Any]:
    """Validate a 'check' postcondition (file exists)."""
    resolved = _resolve_verify_path(root, target)
    if resolved is not None and resolved.is_file():
        return {"status": "pass", "detail": None}
    return {"status": "fail", "detail": f"file not found: {target}"}


def _validate_grep(root: Path, target: str) -> dict[str, Any]:
    """Validate a 'grep' postcondition (pattern found in file)."""
    if "::" not in target:
        return {"status": "error", "detail": "grep target must use pattern::path format"}
    pattern, path = target.split("::", 1)
    resolved = _resolve_verify_path(root, path)
    if resolved is None or not resolved.is_file():
        return {"status": "error", "detail": f"grep target file not found: {path}"}
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return {"status": "error", "detail": f"invalid regex: {exc}"}
    try:
        contents = resolved.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"status": "error", "detail": f"cannot read file: {exc}"}
    if compiled.search(contents):
        return {"status": "pass", "detail": None}
    return {"status": "fail", "detail": f"pattern not found: {pattern}"}


def _validate_test(root: Path, target: str) -> dict[str, Any]:
    """Validate a 'test' postcondition (shell command exits 0).

    Requires ENGRAM_TIER2=1 and the command must match the allowlist.
    """
    import os
    import subprocess

    if os.environ.get("ENGRAM_TIER2", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return {
            "status": "error",
            "detail": "test-type postconditions require ENGRAM_TIER2=1",
        }
    normalized = " ".join(target.split())
    if not any(normalized.startswith(prefix) for prefix in VERIFY_TEST_ALLOWLIST):
        return {
            "status": "error",
            "detail": (
                f"command not in allowlist: {normalized!r}. "
                f"Allowed prefixes: {', '.join(VERIFY_TEST_ALLOWLIST)}"
            ),
        }
    # Reject shell metacharacters beyond the allowlisted prefix
    # to prevent injection like "pytest; rm -rf /"
    for prefix in VERIFY_TEST_ALLOWLIST:
        if normalized.startswith(prefix):
            suffix = normalized[len(prefix) :]
            if _SHELL_META_RE.search(suffix):
                return {
                    "status": "error",
                    "detail": f"shell metacharacters not allowed in command arguments: {normalized!r}",
                }
            break
    # Strip proxy env vars as defense-in-depth.
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.lower().startswith(("http_proxy", "https_proxy", "no_proxy"))
    }
    try:
        result = subprocess.run(
            normalized,
            shell=True,
            cwd=str(root),
            env=env,
            capture_output=True,
            timeout=30,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return {"status": "fail", "detail": "command timed out after 30 seconds"}
    except OSError as exc:
        return {"status": "error", "detail": f"command execution failed: {exc}"}
    if result.returncode == 0:
        return {"status": "pass", "detail": None}
    output = (result.stdout + result.stderr).strip()
    if len(output) > 2000:
        output = output[:2000] + "\n... (truncated)"
    return {"status": "fail", "detail": output or f"exit code {result.returncode}"}


def verify_postconditions(
    plan: PlanDocument,
    phase: PlanPhase,
    root: Path,
) -> dict[str, Any]:
    """Evaluate all postconditions on a phase.

    Returns a dict with verification_results, summary, and all_passed.
    Does not modify plan state.
    """
    results: list[dict[str, Any]] = []
    for pc in phase.postconditions:
        entry: dict[str, Any] = {
            "postcondition": pc.description,
            "type": pc.type,
        }
        if pc.type == "manual":
            entry["status"] = "skip"
            entry["detail"] = None
        elif pc.type == "check":
            outcome = _validate_check(root, pc.target or "")
            entry.update(outcome)
        elif pc.type == "grep":
            outcome = _validate_grep(root, pc.target or "")
            entry.update(outcome)
        elif pc.type == "test":
            outcome = _validate_test(root, pc.target or "")
            entry.update(outcome)
        else:
            entry["status"] = "error"
            entry["detail"] = f"unknown postcondition type: {pc.type}"
        results.append(entry)

    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skip")
    errors = sum(1 for r in results if r["status"] == "error")
    return {
        "verification_results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
        },
        "all_passed": failed == 0 and errors == 0,
    }


def append_operations_log(
    root: Path,
    project_id: str,
    *,
    session_id: str | None,
    action: str,
    plan_id: str,
    phase_id: str | None = None,
    commit: str | None = None,
    detail: str = "",
) -> tuple[str, str]:
    log_path = project_operations_log_path(project_id)
    abs_log = root / log_path
    abs_log.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "session": session_id,
        "actor": "agent",
        "action": action,
        "project": project_id,
        "plan": plan_id,
        "phase": phase_id,
        "commit": commit,
        "detail": detail,
    }
    line = json.dumps(payload, sort_keys=True)
    with abs_log.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return log_path, line


# ---------------------------------------------------------------------------
# Trace span schema and helpers
# ---------------------------------------------------------------------------

_TRACE_STR_MAX = 200
_TRACE_META_MAX_BYTES = 2048


def _sanitize_metadata(
    metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Sanitize trace span metadata per the finalized design decisions.

    Rules:
    - Strings > 200 chars are truncated with '[truncated]' suffix.
    - Field names matching credential patterns are replaced with '[redacted]'.
    - Objects nested beyond depth 2 are stringified.
    - Total JSON size > 2 KB is reduced to top-level scalar fields only.
    """
    if metadata is None:
        return None

    def _sanitize_value(key: str, val: Any, depth: int) -> Any:
        if _CREDENTIAL_FIELD_RE.search(key):
            return "[redacted]"
        if isinstance(val, dict):
            if depth >= 2:
                s = str(val)
                return s[:_TRACE_STR_MAX] + "[truncated]" if len(s) > _TRACE_STR_MAX else s
            return {k: _sanitize_value(k, v, depth + 1) for k, v in val.items()}
        if isinstance(val, str) and len(val) > _TRACE_STR_MAX:
            return val[:_TRACE_STR_MAX] + "[truncated]"
        return val

    sanitized: dict[str, Any] = {k: _sanitize_value(k, v, 0) for k, v in metadata.items()}
    try:
        if len(json.dumps(sanitized, ensure_ascii=False)) > _TRACE_META_MAX_BYTES:
            sanitized = {k: v for k, v in sanitized.items() if not isinstance(v, (dict, list))}
    except (TypeError, ValueError):
        sanitized = {}
    return sanitized or None


def _make_span_id() -> str:
    """Generate a 12-char lowercase hex span ID (first 12 hex chars of UUID4)."""
    import uuid

    return uuid.uuid4().hex[:12]


@dataclass(slots=True)
class TraceSpan:
    """A single trace span written to a session's TRACES.jsonl file."""

    span_id: str
    session_id: str
    timestamp: str
    span_type: str
    name: str
    status: str
    parent_span_id: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] | None = None
    cost: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.span_type not in TRACE_SPAN_TYPES:
            raise ValidationError(
                f"span_type must be one of {sorted(TRACE_SPAN_TYPES)}: {self.span_type!r}"
            )
        if self.status not in TRACE_STATUSES:
            raise ValidationError(
                f"status must be one of {sorted(TRACE_STATUSES)}: {self.status!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "span_id": self.span_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "span_type": self.span_type,
            "name": self.name,
            "status": self.status,
        }
        if self.parent_span_id is not None:
            d["parent_span_id"] = self.parent_span_id
        if self.duration_ms is not None:
            d["duration_ms"] = self.duration_ms
        if self.metadata is not None:
            d["metadata"] = self.metadata
        if self.cost is not None:
            d["cost"] = self.cost
        return d


@dataclass(slots=True)
class ToolDefinition:
    """Metadata and policy for an external tool.

    Stored in ``memory/skills/tool-registry/<provider>.yaml``.  Engram does not
    execute these tools; it stores metadata so agents and orchestrators can
    respect constraints before invoking them.
    """

    name: str
    description: str
    provider: str
    schema: dict[str, Any] | None = None
    approval_required: bool = False
    cost_tier: str = "free"
    rate_limit: str | None = None
    timeout_seconds: int = 30
    tags: list[str] = field(default_factory=list)
    notes: str | None = None

    def __post_init__(self) -> None:
        self.name = validate_slug(self.name, field_name="tool name")
        self.provider = validate_slug(self.provider, field_name="provider")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValidationError("tool description must be a non-empty string")
        self.description = self.description.strip()
        if self.cost_tier not in COST_TIERS:
            raise ValidationError(
                f"cost_tier must be one of {sorted(COST_TIERS)}: {self.cost_tier!r}"
            )
        if not isinstance(self.timeout_seconds, int) or self.timeout_seconds < 1:
            raise ValidationError("timeout_seconds must be an integer >= 1")
        if self.schema is not None and not isinstance(self.schema, dict):
            raise ValidationError("schema must be a dict or null")
        validated_tags: list[str] = []
        for tag in self.tags:
            if not isinstance(tag, str) or not tag.strip():
                raise ValidationError("tags must be non-empty strings")
            validated_tags.append(tag.strip())
        self.tags = validated_tags
        if self.notes is not None:
            self.notes = str(self.notes).strip() or None
        if self.rate_limit is not None:
            self.rate_limit = str(self.rate_limit).strip() or None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "approval_required": self.approval_required,
            "cost_tier": self.cost_tier,
            "timeout_seconds": self.timeout_seconds,
        }
        if self.schema is not None:
            payload["schema"] = self.schema
        if self.rate_limit is not None:
            payload["rate_limit"] = self.rate_limit
        if self.tags:
            payload["tags"] = list(self.tags)
        if self.notes is not None:
            payload["notes"] = self.notes
        return payload


# ── Tool Registry helpers ───────────────────────────────────────────────────


def registry_file_path(provider: str) -> str:
    """Content-relative path to a provider's YAML registry file."""
    validated = validate_slug(provider, field_name="provider")
    return f"memory/skills/tool-registry/{validated}.yaml"


def registry_summary_path() -> str:
    """Content-relative path to the tool registry SUMMARY.md."""
    return "memory/skills/tool-registry/SUMMARY.md"


def _find_registry_root(root: Path) -> Path:
    """Resolve the absolute path to memory/skills/tool-registry/, tolerating root variants."""
    direct = root / "memory/skills/tool-registry"
    if direct.exists():
        return direct
    for prefix in _CONTENT_PREFIXES:
        candidate = root / prefix / "memory/skills/tool-registry"
        if candidate.exists():
            return candidate
    return direct


def _coerce_tool(raw: Any, provider: str) -> ToolDefinition:
    if not isinstance(raw, dict):
        raise ValidationError(f"tool entry must be a mapping, got {type(raw).__name__}")
    tags_raw = raw.get("tags") or []
    if not isinstance(tags_raw, list):
        tags_raw = [str(tags_raw)]
    schema = raw.get("schema")
    if schema is not None and not isinstance(schema, dict):
        schema = None
    try:
        timeout = int(raw.get("timeout_seconds", 30))
    except (TypeError, ValueError):
        timeout = 30
    return ToolDefinition(
        name=str(raw.get("name", "")),
        description=str(raw.get("description", "")),
        provider=provider,
        schema=schema,
        approval_required=bool(raw.get("approval_required", False)),
        cost_tier=str(raw.get("cost_tier", "free")),
        rate_limit=str(raw["rate_limit"]) if raw.get("rate_limit") else None,
        timeout_seconds=timeout,
        tags=[str(t) for t in tags_raw],
        notes=str(raw["notes"]) if raw.get("notes") else None,
    )


def load_registry(root: Path, provider: str) -> list[ToolDefinition]:
    """Load all tool definitions for a provider. Returns [] if the file doesn't exist."""
    reg_root = _find_registry_root(root)
    abs_path = reg_root / f"{validate_slug(provider, field_name='provider')}.yaml"
    if not abs_path.exists():
        return []
    try:
        raw = yaml.safe_load(abs_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML registry file {abs_path.name}: {exc}") from exc
    if not isinstance(raw, dict):
        return []
    result: list[ToolDefinition] = []
    for entry in raw.get("tools") or []:
        result.append(_coerce_tool(entry, provider))
    return result


def save_registry(root: Path, provider: str, tools: list[ToolDefinition]) -> None:
    """Persist tool definitions for a provider to its YAML file."""
    reg_root = _find_registry_root(root)
    abs_path = reg_root / f"{validate_slug(provider, field_name='provider')}.yaml"
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "provider": provider,
        "tools": [t.to_dict() for t in tools],
    }
    text = yaml.dump(payload, Dumper=_PlanDumper, sort_keys=False, allow_unicode=False, width=88)
    abs_path.write_text(text, encoding="utf-8")


def _all_registry_tools(root: Path) -> list[ToolDefinition]:
    """Load all tool definitions from every provider YAML in the registry."""
    reg_root = _find_registry_root(root)
    if not reg_root.exists():
        return []
    tools: list[ToolDefinition] = []
    for yaml_file in sorted(reg_root.glob("*.yaml")):
        try:
            tools.extend(load_registry(root, yaml_file.stem))
        except Exception:  # noqa: BLE001
            continue
    return tools


def regenerate_registry_summary(root: Path) -> None:
    """Rewrite memory/skills/tool-registry/SUMMARY.md from all registered tools."""
    all_tools = _all_registry_tools(root)
    reg_root = _find_registry_root(root)
    reg_root.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Tool Registry",
        "",
        "External tool definitions and policies.",
        "Managed by `memory_register_tool`. Query with `memory_get_tool_policy`.",
        "",
    ]
    if not all_tools:
        lines.append("_No tools registered yet._")
    else:
        by_provider: dict[str, list[ToolDefinition]] = {}
        for t in sorted(all_tools, key=lambda t: (t.provider, t.name)):
            by_provider.setdefault(t.provider, []).append(t)
        for prov, ptools in sorted(by_provider.items()):
            lines += [
                f"## {prov}",
                "",
                "| Tool | Description | Approval | Cost | Timeout | Tags |",
                "|---|---|---|---|---|---|",
            ]
            for t in ptools:
                tags_str = ", ".join(t.tags) if t.tags else "—"
                approval = "yes" if t.approval_required else "no"
                lines.append(
                    f"| {t.name} | {t.description} | {approval} | {t.cost_tier}"
                    f" | {t.timeout_seconds}s | {tags_str} |"
                )
            lines.append("")
    summary_abs = reg_root / "SUMMARY.md"
    summary_abs.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _command_matches_tool(target: str, tool_name: str) -> bool:
    """Return True if a test postcondition target string likely invokes the named tool.

    Strategy:
    1. Direct substring match (slug or space-normalized form).
    2. Extract non-flag, non-path tokens from the target; try all prefix-length
       combinations as hyphenated slugs against the tool name.
    3. If the first segment of the tool name (before the first hyphen-verb) appears
       as a token, treat it as a match (e.g. "pytest" in target → "pytest-run").
    """
    if tool_name in target:
        return True
    if tool_name.replace("-", " ") in target:
        return True
    # Tokenize: keep words that are not flags and don't look like file paths
    tokens = [
        t
        for t in target.lower().split()
        if not t.startswith("-") and "/" not in t and "\\" not in t
    ]
    # Try slug combinations from longest prefix to shortest
    for n in range(len(tokens), 0, -1):
        candidate = "-".join(tokens[:n])
        if candidate == tool_name:
            return True
    # Single-segment prefix match: "pytest" in tokens → matches "pytest-run"
    first_segment = tool_name.split("-")[0]
    return first_segment in tokens


def _resolve_tool_policies(phase: "PlanPhase", root: Path) -> list[dict[str, Any]]:
    """Return tool policy dicts for test postconditions that match registered tools.

    Best-effort: unregistered tools are silently skipped, yielding an empty list.
    """
    test_targets = [pc.target for pc in phase.postconditions if pc.type == "test" and pc.target]
    if not test_targets:
        return []
    all_tools = _all_registry_tools(root)
    if not all_tools:
        return []
    policies: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool in sorted(all_tools, key=lambda t: t.name):
        if tool.name in seen:
            continue
        for target in test_targets:
            if _command_matches_tool(target, tool.name):
                policies.append(
                    {
                        "tool_name": tool.name,
                        "approval_required": tool.approval_required,
                        "cost_tier": tool.cost_tier,
                        "timeout_seconds": tool.timeout_seconds,
                    }
                )
                seen.add(tool.name)
                break
    return policies


def trace_file_path(session_id: str) -> str:
    """Derive the TRACES.jsonl repo-relative path from a session_id.

    Session IDs look like ``memory/activity/YYYY/MM/DD/chat-NNN``.
    Trace files live at ``memory/activity/YYYY/MM/DD/chat-NNN.traces.jsonl``.
    """
    return f"{session_id}.traces.jsonl"


def record_trace(
    root: Path,
    session_id: str | None,
    *,
    span_type: str,
    name: str,
    status: str = "ok",
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
    cost: dict[str, Any] | None = None,
    parent_span_id: str | None = None,
) -> str | None:
    """Append a trace span to the session's TRACES.jsonl file.

    Non-blocking: all exceptions are caught and swallowed.
    Returns the generated ``span_id`` on success, ``None`` on failure or when
    ``session_id`` is absent.
    """
    if not session_id:
        return None
    try:
        from datetime import datetime, timezone

        sanitized_metadata = _sanitize_metadata(metadata)
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        span = TraceSpan(
            span_id=_make_span_id(),
            session_id=session_id,
            timestamp=now_iso,
            span_type=span_type,
            name=name,
            status=status,
            parent_span_id=parent_span_id,
            duration_ms=duration_ms,
            metadata=sanitized_metadata,
            cost=cost,
        )
        abs_trace = root / trace_file_path(session_id)
        abs_trace.parent.mkdir(parents=True, exist_ok=True)
        with abs_trace.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(span.to_dict(), ensure_ascii=False) + "\n")
        return span.span_id
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Approval workflow schema and helpers
# ---------------------------------------------------------------------------


def approval_filename(plan_id: str, phase_id: str) -> str:
    """Return the filename (not path) for an approval document: {plan_id}--{phase_id}.yaml."""
    p = validate_slug(plan_id, field_name="plan_id")
    ph = validate_slug(phase_id, field_name="phase_id")
    return f"{p}--{ph}.yaml"


def approvals_summary_path() -> str:
    """Content-relative path to the approvals queue SUMMARY.md."""
    return "memory/working/approvals/SUMMARY.md"


def _find_approvals_root(root: Path) -> Path:
    """Resolve the absolute path to memory/working/approvals/, tolerating root variants."""
    direct = root / "memory/working/approvals"
    if direct.exists():
        return direct
    for prefix in _CONTENT_PREFIXES:
        candidate = root / prefix / "memory/working/approvals"
        if candidate.exists():
            return candidate
    return direct


@dataclass(slots=True)
class ApprovalDocument:
    """A pending or resolved human-in-the-loop approval request for a plan phase.

    Stored in ``memory/working/approvals/pending/{plan_id}--{phase_id}.yaml``
    while awaiting review, and moved to ``resolved/`` after resolution or expiry.
    """

    plan_id: str
    phase_id: str
    project_id: str
    status: str  # pending | approved | rejected | expired
    requested: str  # ISO-8601 UTC timestamp
    expires: str  # ISO-8601 UTC timestamp
    context: dict[str, Any] = field(default_factory=dict)
    resolution: str | None = None  # "approve" | "reject"
    reviewer: str | None = None
    resolved_at: str | None = None
    comment: str | None = None

    def __post_init__(self) -> None:
        self.plan_id = validate_slug(self.plan_id, field_name="plan_id")
        self.phase_id = validate_slug(self.phase_id, field_name="phase_id")
        self.project_id = validate_slug(self.project_id, field_name="project_id")
        if self.status not in APPROVAL_STATUSES:
            raise ValidationError(
                f"approval status must be one of {sorted(APPROVAL_STATUSES)}: {self.status!r}"
            )
        if not isinstance(self.requested, str) or not self.requested.strip():
            raise ValidationError("requested must be a non-empty ISO-8601 timestamp string")
        if not isinstance(self.expires, str) or not self.expires.strip():
            raise ValidationError("expires must be a non-empty ISO-8601 timestamp string")
        if self.resolution is not None and self.resolution not in APPROVAL_RESOLUTIONS:
            raise ValidationError(
                f"resolution must be one of {sorted(APPROVAL_RESOLUTIONS)}: {self.resolution!r}"
            )
        if not isinstance(self.context, dict):
            self.context = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "phase_id": self.phase_id,
            "project_id": self.project_id,
            "status": self.status,
            "requested": self.requested,
            "expires": self.expires,
            "context": self.context,
            "resolution": self.resolution,
            "reviewer": self.reviewer,
            "resolved_at": self.resolved_at,
            "comment": self.comment,
        }


def _coerce_approval(raw: dict[str, Any]) -> "ApprovalDocument":
    """Coerce a raw YAML mapping into an ApprovalDocument."""
    context = raw.get("context")
    if not isinstance(context, dict):
        context = {}
    return ApprovalDocument(
        plan_id=str(raw.get("plan_id", "")),
        phase_id=str(raw.get("phase_id", "")),
        project_id=str(raw.get("project_id", "")),
        status=str(raw.get("status", "pending")),
        requested=str(raw.get("requested", "")),
        expires=str(raw.get("expires", "")),
        context=context,
        resolution=str(raw["resolution"]) if raw.get("resolution") else None,
        reviewer=str(raw["reviewer"]) if raw.get("reviewer") else None,
        resolved_at=str(raw["resolved_at"]) if raw.get("resolved_at") else None,
        comment=str(raw["comment"]) if raw.get("comment") else None,
    )


def _check_approval_expiry(approval: "ApprovalDocument", root: Path) -> bool:
    """Check if a pending approval has passed its expiry; if so, transition it in-place.

    Mutates *approval* status to ``"expired"`` and moves its file from
    ``pending/`` to ``resolved/``.  Returns ``True`` if the approval was expired
    (and the caller should set the plan status to ``"blocked"``), ``False``
    otherwise.
    """
    if approval.status != "pending":
        return False
    try:
        from datetime import datetime, timezone

        expires_dt = datetime.fromisoformat(approval.expires.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if now <= expires_dt:
            return False
    except (ValueError, AttributeError):
        return False

    # Transition to expired and move file
    approval.status = "expired"
    approvals_root = _find_approvals_root(root)
    filename = approval_filename(approval.plan_id, approval.phase_id)
    pending_path = approvals_root / "pending" / filename
    resolved_dir = approvals_root / "resolved"
    resolved_dir.mkdir(parents=True, exist_ok=True)
    resolved_path = resolved_dir / filename
    text = yaml.dump(
        approval.to_dict(),
        Dumper=_PlanDumper,
        sort_keys=False,
        allow_unicode=False,
        width=88,
    )
    resolved_path.write_text(text, encoding="utf-8")
    if pending_path.exists():
        pending_path.unlink()
    return True


def load_approval(root: Path, plan_id: str, phase_id: str) -> "ApprovalDocument | None":
    """Load an approval document for a plan/phase pair.

    Checks ``pending/`` first, then ``resolved/``.  If the document is pending
    and past its expiry deadline, lazily transitions it to ``expired`` (file
    moved to ``resolved/``).  Returns ``None`` if no approval document exists.
    """
    approvals_root = _find_approvals_root(root)
    filename = approval_filename(plan_id, phase_id)

    pending_path = approvals_root / "pending" / filename
    if pending_path.exists():
        try:
            raw = yaml.safe_load(pending_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValidationError(f"Invalid approval YAML {filename}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValidationError(f"Approval file must be a mapping: {filename}")
        approval = _coerce_approval(raw)
        _check_approval_expiry(approval, root)
        return approval

    resolved_path = approvals_root / "resolved" / filename
    if resolved_path.exists():
        try:
            raw = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValidationError(f"Invalid approval YAML {filename}: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValidationError(f"Approval file must be a mapping: {filename}")
        return _coerce_approval(raw)

    return None


def save_approval(root: Path, approval: "ApprovalDocument") -> Path:
    """Persist an approval document to the correct subdirectory based on status.

    Pending approvals go to ``pending/``; all others go to ``resolved/``.
    Returns the absolute path where the document was saved.
    """
    approvals_root = _find_approvals_root(root)
    filename = approval_filename(approval.plan_id, approval.phase_id)

    if approval.status == "pending":
        target_dir = approvals_root / "pending"
    else:
        target_dir = approvals_root / "resolved"

    target_dir.mkdir(parents=True, exist_ok=True)
    abs_path = target_dir / filename
    text = yaml.dump(
        approval.to_dict(),
        Dumper=_PlanDumper,
        sort_keys=False,
        allow_unicode=False,
        width=88,
    )
    abs_path.write_text(text, encoding="utf-8")
    return abs_path


def regenerate_approvals_summary(root: Path) -> None:
    """Rewrite memory/working/approvals/SUMMARY.md from pending and resolved directories."""
    approvals_root = _find_approvals_root(root)
    approvals_root.mkdir(parents=True, exist_ok=True)

    pending_approvals: list[ApprovalDocument] = []
    resolved_approvals: list[ApprovalDocument] = []

    pending_dir = approvals_root / "pending"
    if pending_dir.exists():
        for yaml_file in sorted(pending_dir.glob("*.yaml")):
            try:
                raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    pending_approvals.append(_coerce_approval(raw))
            except Exception:  # noqa: BLE001
                continue

    resolved_dir = approvals_root / "resolved"
    if resolved_dir.exists():
        for yaml_file in sorted(resolved_dir.glob("*.yaml")):
            try:
                raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    resolved_approvals.append(_coerce_approval(raw))
            except Exception:  # noqa: BLE001
                continue

    lines: list[str] = [
        "# Approval Queue",
        "",
        "Human-in-the-loop approval requests. "
        "Managed by `memory_request_approval` and `memory_resolve_approval`.",
        "",
    ]

    lines += ["## Pending", ""]
    if not pending_approvals:
        lines.append("_No pending approvals._")
    else:
        lines += ["| Plan | Phase | Requested | Expires |", "|---|---|---|---|"]
        for ap in pending_approvals:
            title = (ap.context or {}).get("phase_title", ap.phase_id)
            lines.append(f"| {ap.plan_id} | {title} | {ap.requested[:10]} | {ap.expires[:10]} |")

    lines += ["", "## Resolved", ""]
    if not resolved_approvals:
        lines.append("_No resolved approvals._")
    else:
        lines += ["| Plan | Phase | Status | Resolved |", "|---|---|---|---|"]
        for ap in sorted(resolved_approvals, key=lambda a: a.resolved_at or "", reverse=True):
            title = (ap.context or {}).get("phase_title", ap.phase_id)
            resolved_str = (ap.resolved_at or "")[:10]
            lines.append(f"| {ap.plan_id} | {title} | {ap.status} | {resolved_str} |")

    lines.append("")
    summary_abs = approvals_root / "SUMMARY.md"
    summary_abs.write_text("\n".join(lines) + "\n", encoding="utf-8")


__all__ = [
    "APPROVAL_RESOLUTIONS",
    "APPROVAL_STATUSES",
    "CHANGE_ACTIONS",
    "COST_TIERS",
    "PLAN_STATUSES",
    "PHASE_STATUSES",
    "POSTCONDITION_TYPES",
    "SOURCE_TYPES",
    "TRACE_SPAN_TYPES",
    "TRACE_STATUSES",
    "ApprovalDocument",
    "ChangeSpec",
    "PhaseFailure",
    "PlanBudget",
    "PlanDocument",
    "PlanPhase",
    "PlanPurpose",
    "PlanReview",
    "PostconditionSpec",
    "SourceSpec",
    "ToolDefinition",
    "TraceSpan",
    "_all_registry_tools",
    "_check_approval_expiry",
    "append_operations_log",
    "approval_filename",
    "approvals_summary_path",
    "budget_status",
    "build_review_from_input",
    "coerce_budget_input",
    "coerce_phase_inputs",
    "exportable_artifacts",
    "load_approval",
    "load_plan",
    "load_registry",
    "next_action",
    "next_phase",
    "outbox_summary_path",
    "phase_blockers",
    "phase_change_class",
    "phase_payload",
    "plan_progress",
    "plan_title",
    "project_operations_log_path",
    "project_outbox_root",
    "project_plan_path",
    "record_trace",
    "regenerate_approvals_summary",
    "regenerate_registry_summary",
    "registry_file_path",
    "registry_summary_path",
    "resolve_phase",
    "save_approval",
    "save_plan",
    "save_registry",
    "trace_file_path",
    "unresolved_blockers",
    "validate_plan_references",
    "verify_postconditions",
    "VERIFY_TEST_ALLOWLIST",
]
