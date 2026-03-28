"""Run-state schema and helpers for plan execution tracking."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .errors import ValidationError
from .path_policy import validate_slug

if TYPE_CHECKING:
    from .plan_utils import PlanDocument

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RUN_STATE_SCHEMA_VERSION = 1
_RUN_STATE_MAX_BYTES = 50_000
_RUN_STATE_OUTPUT_MAX_CHARS = 2048
_RUN_STATE_PHASE_OUTPUTS_MAX_CHARS = 10_000
_RUN_STATE_MAX_OUTPUTS_PER_PHASE = 20
_RUN_STATE_STALENESS_MINUTES = 60

_CONTENT_PREFIXES = ("core",)


def _resolve_content_root(root: Path) -> Path:
    if (root / "memory").exists():
        return root
    for prefix in _CONTENT_PREFIXES:
        candidate = root / prefix
        if (candidate / "memory").exists():
            return candidate
    return root


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RunStateError:
    """Structured error context from the last failed action."""

    phase_id: str
    message: str
    timestamp: str
    recoverable: bool = True

    def __post_init__(self) -> None:
        self.phase_id = validate_slug(self.phase_id, field_name="error phase_id")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValidationError("error message must be a non-empty string")
        if not isinstance(self.timestamp, str) or not self.timestamp.strip():
            raise ValidationError("error timestamp must be a non-empty string")
        self.message = self.message.strip()
        self.timestamp = self.timestamp.strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "message": self.message,
            "timestamp": self.timestamp,
            "recoverable": self.recoverable,
        }


@dataclass(slots=True)
class RunStatePhase:
    """Per-phase execution detail within a RunState."""

    started_at: str | None = None
    completed_at: str | None = None
    task_position: str | None = None
    intermediate_outputs: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.started_at is not None:
            if not isinstance(self.started_at, str) or not self.started_at.strip():
                raise ValidationError("phase started_at must be a non-empty string or null")
            self.started_at = self.started_at.strip()
        if self.completed_at is not None:
            if not isinstance(self.completed_at, str) or not self.completed_at.strip():
                raise ValidationError("phase completed_at must be a non-empty string or null")
            self.completed_at = self.completed_at.strip()
        if self.task_position is not None:
            if not isinstance(self.task_position, str):
                raise ValidationError("task_position must be a string or null")
            self.task_position = self.task_position.strip() or None
        validated: list[dict[str, Any]] = []
        for output in self.intermediate_outputs:
            if not isinstance(output, dict):
                raise ValidationError("intermediate_outputs entries must be mappings")
            key = output.get("key")
            if not isinstance(key, str) or not key.strip():
                raise ValidationError("intermediate_output key must be a non-empty string")
            value = output.get("value")
            if not isinstance(value, str):
                raise ValidationError("intermediate_output value must be a string")
            ts = output.get("timestamp")
            if not isinstance(ts, str) or not ts.strip():
                raise ValidationError("intermediate_output timestamp must be a non-empty string")
            validated.append({"key": key.strip(), "value": value, "timestamp": ts.strip()})
        self.intermediate_outputs = validated

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "task_position": self.task_position,
            "intermediate_outputs": list(self.intermediate_outputs),
        }


@dataclass(slots=True)
class RunState:
    """Execution state for a plan, persisted as JSON alongside the plan YAML.

    Plan YAML remains authoritative for phase status.  RunState adds
    execution-level detail: task position within a phase, intermediate
    outputs, resumption hints, and error context.
    """

    plan_id: str
    project_id: str
    schema_version: int = _RUN_STATE_SCHEMA_VERSION
    current_phase_id: str | None = None
    current_task: str | None = None
    next_action_hint: str | None = None
    last_checkpoint: str = ""
    session_id: str = ""
    sessions_consumed: int = 0
    error_context: RunStateError | None = None
    phase_states: dict[str, RunStatePhase] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        self.plan_id = validate_slug(self.plan_id, field_name="run_state plan_id")
        self.project_id = validate_slug(self.project_id, field_name="run_state project_id")
        if not isinstance(self.schema_version, int) or self.schema_version < 1:
            raise ValidationError("schema_version must be an integer >= 1")
        if self.current_phase_id is not None:
            self.current_phase_id = validate_slug(
                self.current_phase_id, field_name="current_phase_id"
            )
        if self.current_task is not None:
            if not isinstance(self.current_task, str):
                raise ValidationError("current_task must be a string or null")
            self.current_task = self.current_task.strip() or None
        if self.next_action_hint is not None:
            if not isinstance(self.next_action_hint, str):
                raise ValidationError("next_action_hint must be a string or null")
            self.next_action_hint = self.next_action_hint.strip() or None
        if not isinstance(self.sessions_consumed, int) or self.sessions_consumed < 0:
            raise ValidationError("sessions_consumed must be an integer >= 0")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "project_id": self.project_id,
            "current_phase_id": self.current_phase_id,
            "current_task": self.current_task,
            "next_action_hint": self.next_action_hint,
            "last_checkpoint": self.last_checkpoint,
            "session_id": self.session_id,
            "sessions_consumed": self.sessions_consumed,
            "error_context": (None if self.error_context is None else self.error_context.to_dict()),
            "phase_states": {k: v.to_dict() for k, v in self.phase_states.items()},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------


def _coerce_run_state_error(raw: Any) -> RunStateError | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    return RunStateError(
        phase_id=str(raw.get("phase_id", "")),
        message=str(raw.get("message", "")),
        timestamp=str(raw.get("timestamp", "")),
        recoverable=bool(raw.get("recoverable", True)),
    )


def _coerce_run_state_phase(raw: Any) -> RunStatePhase:
    if not isinstance(raw, dict):
        raise ValidationError("phase_states entry must be a mapping")
    outputs = raw.get("intermediate_outputs") or []
    if not isinstance(outputs, list):
        outputs = []
    return RunStatePhase(
        started_at=str(raw["started_at"]) if raw.get("started_at") else None,
        completed_at=str(raw["completed_at"]) if raw.get("completed_at") else None,
        task_position=str(raw["task_position"]) if raw.get("task_position") else None,
        intermediate_outputs=[dict(o) for o in outputs if isinstance(o, dict)],
    )


def _coerce_run_state(raw: dict[str, Any]) -> RunState:
    phase_states_raw = raw.get("phase_states") or {}
    if not isinstance(phase_states_raw, dict):
        phase_states_raw = {}
    phase_states: dict[str, RunStatePhase] = {}
    for key, val in phase_states_raw.items():
        phase_states[str(key)] = _coerce_run_state_phase(val)
    return RunState(
        plan_id=str(raw.get("plan_id", "")),
        project_id=str(raw.get("project_id", "")),
        schema_version=int(raw.get("schema_version", _RUN_STATE_SCHEMA_VERSION)),
        current_phase_id=(str(raw["current_phase_id"]) if raw.get("current_phase_id") else None),
        current_task=str(raw["current_task"]) if raw.get("current_task") else None,
        next_action_hint=(str(raw["next_action_hint"]) if raw.get("next_action_hint") else None),
        last_checkpoint=str(raw.get("last_checkpoint", "")),
        session_id=str(raw.get("session_id", "")),
        sessions_consumed=int(raw.get("sessions_consumed", 0)),
        error_context=_coerce_run_state_error(raw.get("error_context")),
        phase_states=phase_states,
        created_at=str(raw.get("created_at", "")),
        updated_at=str(raw.get("updated_at", "")),
    )


# ---------------------------------------------------------------------------
# Load / save / update
# ---------------------------------------------------------------------------


def run_state_path(project_id: str, plan_id: str) -> str:
    """Content-relative path to a plan's run-state JSON file."""
    return (
        f"memory/working/projects/{validate_slug(project_id, field_name='project_id')}"
        f"/plans/{validate_slug(plan_id, field_name='plan_id')}.run-state.json"
    )


def load_run_state(root: Path, project_id: str, plan_id: str) -> RunState | None:
    """Load a plan's run state from JSON.  Returns ``None`` if the file is missing or corrupt."""
    rel = run_state_path(project_id, plan_id)
    abs_path = root / rel
    if not abs_path.exists():
        for prefix in _CONTENT_PREFIXES:
            candidate = root / prefix / rel
            if candidate.exists():
                abs_path = candidate
                break
        else:
            return None
    try:
        raw = json.loads(abs_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return _coerce_run_state(raw)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


def save_run_state(root: Path, run_state: RunState) -> Path:
    """Validate and write run state to disk as JSON.  Returns the absolute path."""
    run_state.updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not run_state.created_at:
        run_state.created_at = run_state.updated_at

    rel = run_state_path(run_state.project_id, run_state.plan_id)
    content_root = _resolve_content_root(root)
    abs_path = content_root / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    data = run_state.to_dict()
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    if len(text.encode("utf-8")) > _RUN_STATE_MAX_BYTES:
        run_state = prune_run_state(run_state)
        data = run_state.to_dict()
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    abs_path.write_text(text, encoding="utf-8")
    return abs_path


def update_run_state(
    run_state: RunState,
    action: str,
    phase_id: str,
    *,
    session_id: str,
    next_action_hint: str | None = None,
    task_position: str | None = None,
    error_message: str | None = None,
    error_recoverable: bool = True,
) -> RunState:
    """Apply a plan execution action's effects to *run_state* (mutates in place)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_state.last_checkpoint = now
    run_state.session_id = session_id

    if phase_id not in run_state.phase_states:
        run_state.phase_states[phase_id] = RunStatePhase()

    ps = run_state.phase_states[phase_id]

    if action == "start":
        run_state.current_phase_id = phase_id
        run_state.current_task = task_position
        run_state.next_action_hint = next_action_hint
        run_state.error_context = None
        if ps.started_at is None:
            ps.started_at = now
        ps.task_position = task_position

    elif action == "complete":
        ps.completed_at = now
        ps.task_position = None
        run_state.sessions_consumed += 1
        run_state.current_task = None
        run_state.error_context = None
        run_state.next_action_hint = next_action_hint
        run_state.current_phase_id = None

    elif action == "record_failure":
        run_state.error_context = RunStateError(
            phase_id=phase_id,
            message=error_message or "Unknown failure",
            timestamp=now,
            recoverable=error_recoverable,
        )
        run_state.next_action_hint = next_action_hint
        ps.task_position = task_position

    return run_state


# ---------------------------------------------------------------------------
# Validation / maintenance
# ---------------------------------------------------------------------------


def validate_run_state_against_plan(
    run_state: RunState,
    plan: "PlanDocument",
) -> list[str]:
    """Check consistency between run state and plan YAML.  Returns warnings.

    Corrects ``run_state`` in place when the plan YAML disagrees (plan wins).
    """
    from .plan_utils import next_phase

    warnings: list[str] = []

    if run_state.plan_id != plan.id:
        warnings.append(f"Run state plan_id '{run_state.plan_id}' != plan '{plan.id}'")
    if run_state.project_id != plan.project:
        warnings.append(
            f"Run state project_id '{run_state.project_id}' != plan project '{plan.project}'"
        )

    if run_state.current_phase_id is not None:
        phase_ids = {p.id for p in plan.phases}
        if run_state.current_phase_id not in phase_ids:
            warnings.append(
                f"Run state current_phase_id '{run_state.current_phase_id}' "
                "not found in plan; clearing"
            )
            run_state.current_phase_id = None
        else:
            for p in plan.phases:
                if p.id == run_state.current_phase_id and p.status == "completed":
                    warnings.append(
                        f"Run state current_phase_id '{run_state.current_phase_id}' "
                        "refers to a completed phase; advancing"
                    )
                    nxt = next_phase(plan)
                    run_state.current_phase_id = nxt.id if nxt else None
                    break

    plan_phase_ids = {p.id for p in plan.phases}
    for phase_id in list(run_state.phase_states.keys()):
        if phase_id not in plan_phase_ids:
            warnings.append(f"Run state has unknown phase '{phase_id}'; removing")
            del run_state.phase_states[phase_id]

    return warnings


def check_run_state_staleness(
    run_state: RunState,
    current_session_id: str,
) -> str | None:
    """Return a warning if run state was recently updated by a different session."""
    if run_state.session_id == current_session_id:
        return None
    if not run_state.last_checkpoint:
        return None
    try:
        last = datetime.fromisoformat(run_state.last_checkpoint.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        minutes = (now - last).total_seconds() / 60
        if minutes <= _RUN_STATE_STALENESS_MINUTES:
            return (
                f"Run state was last updated by session '{run_state.session_id}' "
                f"{int(minutes)} minutes ago. Taking over."
            )
    except (ValueError, AttributeError):
        pass
    return None


def prune_run_state(run_state: RunState) -> RunState:
    """Summarize completed phase entries to reduce size (mutates in place)."""
    for phase_state in run_state.phase_states.values():
        if phase_state.completed_at is None:
            continue
        if not phase_state.intermediate_outputs:
            continue
        count = len(phase_state.intermediate_outputs)
        phase_state.intermediate_outputs = [
            {
                "key": "pruned-summary",
                "value": f"Summarized {count} outputs from completed phase",
                "timestamp": phase_state.completed_at,
            }
        ]
        phase_state.task_position = None
    return run_state
