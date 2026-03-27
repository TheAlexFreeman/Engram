"""Structured YAML plan schema helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .errors import NotFoundError, ValidationError
from .path_policy import validate_session_id, validate_slug

PLAN_STATUSES = {"draft", "active", "blocked", "completed", "abandoned"}
PHASE_STATUSES = {"pending", "blocked", "in-progress", "completed", "skipped"}
PLAN_OUTCOMES = {"completed", "partial", "abandoned"}
CHANGE_ACTIONS = {"create", "rewrite", "update", "delete", "rename"}
SOURCE_TYPES = {"internal", "external", "mcp"}
POSTCONDITION_TYPES = {"check", "grep", "test", "manual"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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

    def validate_exists(self, root: Path) -> None:
        """Raise if this is an internal source and the file does not exist.

        Handles both conventions: paths may be content-relative (relative to
        the content root, e.g. ``tools/file.py``) or git-relative (including
        the content prefix, e.g. ``core/tools/file.py``).  When *root* is the
        content root and the path redundantly starts with the content-prefix
        directory name we strip the prefix before checking.
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
        raise ValidationError(f"internal source does not exist: {self.path}")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "type": self.type,
            "intent": self.intent,
        }
        if self.uri is not None:
            payload["uri"] = self.uri
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
    return result


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


__all__ = [
    "CHANGE_ACTIONS",
    "PLAN_STATUSES",
    "PHASE_STATUSES",
    "POSTCONDITION_TYPES",
    "SOURCE_TYPES",
    "ChangeSpec",
    "PlanBudget",
    "PlanDocument",
    "PlanPhase",
    "PlanPurpose",
    "PlanReview",
    "PostconditionSpec",
    "SourceSpec",
    "append_operations_log",
    "budget_status",
    "build_review_from_input",
    "coerce_budget_input",
    "coerce_phase_inputs",
    "exportable_artifacts",
    "load_plan",
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
    "resolve_phase",
    "save_plan",
    "unresolved_blockers",
    "validate_plan_references",
]
