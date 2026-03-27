"""Offline evaluation helpers for harness scenarios."""

from __future__ import annotations

import json
import re
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .errors import NotFoundError, ValidationError
from .path_policy import validate_session_id, validate_slug
from .plan_utils import (
    ApprovalDocument,
    PhaseFailure,
    PlanBudget,
    PlanDocument,
    PlanPhase,
    PlanPurpose,
    ToolDefinition,
    approval_filename,
    coerce_phase_inputs,
    load_approval,
    load_plan,
    record_trace,
    resolve_phase,
    save_approval,
    save_plan,
    save_registry,
    trace_file_path,
    verify_postconditions,
)

EVAL_STEP_ACTIONS = frozenset(
    {
        "start_phase",
        "complete_phase",
        "verify_phase",
        "record_failure",
        "request_approval",
        "resolve_approval",
        "create_file",
        "delete_file",
    }
)
EVAL_ASSERTION_TYPES = frozenset(
    {
        "plan_status",
        "phase_status",
        "trace_span_count",
        "trace_metadata",
        "metric",
        "file_exists",
        "file_contains",
        "approval_status",
    }
)
METRIC_NAMES = frozenset(
    {
        "task_success",
        "steps_to_success",
        "retry_rate",
        "verification_pass_rate",
        "error_rate",
        "human_intervention_count",
    }
)
_DEFAULT_SCENARIO_SESSION_ID = "memory/activity/2026/03/27/chat-000"


def eval_scenarios_dir(root: Path) -> Path:
    return root / "memory" / "skills" / "eval-scenarios"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _match_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(
            key in actual and _match_subset(value, actual[key]) for key, value in expected.items()
        )
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) > len(actual):
            return False
        return all(_match_subset(item, actual[index]) for index, item in enumerate(expected))
    return actual == expected


def _get_nested_value(payload: dict[str, Any], key: str) -> Any:
    current: Any = payload
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _load_trace_spans(root: Path, session_id: str) -> list[dict[str, Any]]:
    abs_trace = root / trace_file_path(session_id)
    if not abs_trace.exists():
        return []
    spans: list[dict[str, Any]] = []
    for line in abs_trace.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            spans.append(payload)
    return spans


def _filter_spans(
    spans: list[dict[str, Any]], filter_spec: dict[str, Any] | None
) -> list[dict[str, Any]]:
    if not filter_spec:
        return list(spans)
    return [span for span in spans if _match_subset(filter_spec, span)]


def _build_plan_document(
    scenario: "EvalScenario", plan_raw: dict[str, Any], session_id: str
) -> PlanDocument:
    if not isinstance(plan_raw, dict):
        raise ValidationError("scenario setup.plan must be a mapping")
    phases_raw = plan_raw.get("phases")
    if phases_raw is None:
        work = plan_raw.get("work")
        if isinstance(work, dict):
            phases_raw = work.get("phases")
    if not isinstance(phases_raw, list):
        raise ValidationError("scenario setup.plan must define a phases list")
    phases = coerce_phase_inputs(phases_raw)

    purpose_raw = plan_raw.get("purpose") or {}
    if purpose_raw is None:
        purpose_raw = {}
    if not isinstance(purpose_raw, dict):
        raise ValidationError("scenario setup.plan.purpose must be a mapping when provided")

    budget_raw = plan_raw.get("budget")
    budget = None
    if budget_raw is not None:
        if not isinstance(budget_raw, dict):
            raise ValidationError("scenario setup.plan.budget must be a mapping when provided")
        deadline = budget_raw.get("deadline")
        max_sessions = budget_raw.get("max_sessions")
        advisory = budget_raw.get("advisory", True)
        budget = PlanBudget(
            deadline=None if deadline is None else str(deadline),
            max_sessions=int(max_sessions) if max_sessions is not None else None,
            advisory=bool(advisory),
        )

    return PlanDocument(
        id=str(plan_raw.get("id", scenario.id)),
        project=str(plan_raw.get("project", "eval-suite")),
        created=str(plan_raw.get("created", datetime.now(timezone.utc).date().isoformat())),
        origin_session=str(plan_raw.get("origin_session", session_id)),
        status=str(plan_raw.get("status", "active")),
        purpose=PlanPurpose(
            summary=str(purpose_raw.get("summary", scenario.description)),
            context=str(purpose_raw.get("context", f"Eval scenario: {scenario.id}")),
            questions=[str(item) for item in purpose_raw.get("questions", []) or []],
        ),
        phases=phases,
        budget=budget,
        sessions_used=int(plan_raw.get("sessions_used", 0)),
        review=None,
    )


def _plan_file_path(root: Path, plan: PlanDocument) -> Path:
    return root / "memory" / "working" / "projects" / plan.project / "plans" / f"{plan.id}.yaml"


def _write_setup_files(root: Path, files: list[dict[str, Any]]) -> None:
    for entry in files:
        path_raw = entry.get("path")
        if not isinstance(path_raw, str) or not path_raw.strip():
            raise ValidationError("setup.files entries must include non-empty path values")
        content = entry.get("content", "")
        abs_path = root / path_raw.replace("\\", "/")
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(str(content), encoding="utf-8")


def _write_registry_tools(root: Path, tools: list[dict[str, Any]]) -> None:
    if not tools:
        return
    by_provider: dict[str, list[ToolDefinition]] = {}
    for raw_tool in tools:
        if not isinstance(raw_tool, dict):
            raise ValidationError("setup.registry_tools must contain mapping items")
        provider = str(raw_tool.get("provider", "shell"))
        by_provider.setdefault(provider, []).append(
            ToolDefinition(
                name=str(raw_tool.get("name", "")),
                description=str(raw_tool.get("description", "")),
                provider=provider,
                schema=raw_tool.get("schema") if isinstance(raw_tool.get("schema"), dict) else None,
                approval_required=bool(raw_tool.get("approval_required", False)),
                cost_tier=str(raw_tool.get("cost_tier", "free")),
                rate_limit=(
                    None if raw_tool.get("rate_limit") is None else str(raw_tool.get("rate_limit"))
                ),
                timeout_seconds=int(raw_tool.get("timeout_seconds", 30)),
                tags=[str(tag) for tag in raw_tool.get("tags", []) or []],
                notes=None if raw_tool.get("notes") is None else str(raw_tool.get("notes")),
            )
        )
    for provider, definitions in by_provider.items():
        save_registry(root, provider, definitions)


def _create_pending_approval(
    root: Path, plan: PlanDocument, phase: PlanPhase, expires_days: int
) -> ApprovalDocument:
    requested = datetime.now(timezone.utc)
    approval = ApprovalDocument(
        plan_id=plan.id,
        phase_id=phase.id,
        project_id=plan.project,
        status="pending",
        requested=requested.strftime("%Y-%m-%dT%H:%M:%SZ"),
        expires=(requested + timedelta(days=expires_days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        context={"phase_title": phase.title},
    )
    save_approval(root, approval)
    return approval


def _remove_pending_approval(root: Path, plan_id: str, phase_id: str) -> None:
    pending_path = (
        root / "memory" / "working" / "approvals" / "pending" / approval_filename(plan_id, phase_id)
    )
    if pending_path.exists():
        pending_path.unlink()


@dataclass(slots=True)
class EvalStep:
    action: str
    phase_id: str | None = None
    expect: dict[str, Any] | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.action not in EVAL_STEP_ACTIONS:
            raise ValidationError(
                f"eval step action must be one of {sorted(EVAL_STEP_ACTIONS)}: {self.action!r}"
            )
        if self.phase_id is not None:
            self.phase_id = validate_slug(self.phase_id, field_name="phase_id")
        if self.expect is not None and not isinstance(self.expect, dict):
            raise ValidationError("eval step expect must be a mapping when provided")
        if not isinstance(self.params, dict):
            raise ValidationError("eval step params must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"action": self.action}
        if self.phase_id is not None:
            payload["phase_id"] = self.phase_id
        payload.update(self.params)
        if self.expect is not None:
            payload["expect"] = dict(self.expect)
        return payload


@dataclass(slots=True)
class EvalAssertion:
    type: str
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.type not in EVAL_ASSERTION_TYPES:
            raise ValidationError(
                f"eval assertion type must be one of {sorted(EVAL_ASSERTION_TYPES)}: {self.type!r}"
            )
        if not isinstance(self.params, dict):
            raise ValidationError("eval assertion params must be a mapping")

    def to_dict(self) -> dict[str, Any]:
        payload = {"type": self.type}
        payload.update(self.params)
        return payload


@dataclass(slots=True)
class EvalScenario:
    id: str
    description: str
    setup: dict[str, Any]
    steps: list[EvalStep]
    assertions: list[EvalAssertion]
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.id = validate_slug(self.id, field_name="scenario_id")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValidationError("scenario description must be a non-empty string")
        self.description = self.description.strip()
        if not isinstance(self.setup, dict):
            raise ValidationError("scenario setup must be a mapping")
        if "plan" not in self.setup:
            raise ValidationError("scenario setup must include a plan mapping")
        normalized_tags: list[str] = []
        for tag in self.tags:
            if not isinstance(tag, str) or not tag.strip():
                raise ValidationError("scenario tags must contain non-empty strings")
            normalized_tags.append(tag.strip())
        self.tags = normalized_tags
        if not self.steps:
            raise ValidationError("scenario must define at least one step")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "setup": self.setup,
            "steps": [step.to_dict() for step in self.steps],
            "assertions": [assertion.to_dict() for assertion in self.assertions],
        }
        if self.tags:
            payload["tags"] = list(self.tags)
        return payload


@dataclass(slots=True)
class StepResult:
    step_index: int
    action: str
    status: str
    detail: str | None = None
    duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "step_index": self.step_index,
            "action": self.action,
            "status": self.status,
        }
        if self.detail is not None:
            payload["detail"] = self.detail
        if self.duration_ms is not None:
            payload["duration_ms"] = self.duration_ms
        return payload


@dataclass(slots=True)
class AssertionResult:
    assertion_index: int
    type: str
    status: str
    expected: Any = None
    actual: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "assertion_index": self.assertion_index,
            "type": self.type,
            "status": self.status,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass(slots=True)
class ScenarioResult:
    scenario_id: str
    status: str
    step_results: list[StepResult]
    assertion_results: list[AssertionResult]
    metrics: dict[str, float]
    duration_ms: int
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "status": self.status,
            "step_results": [result.to_dict() for result in self.step_results],
            "assertion_results": [result.to_dict() for result in self.assertion_results],
            "metrics": dict(self.metrics),
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


def load_scenario(path: Path) -> EvalScenario:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid eval scenario YAML {path.name}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValidationError(f"Eval scenario must be a top-level mapping: {path.name}")

    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list):
        raise ValidationError("eval scenario steps must be a list")
    assertions_raw = raw.get("assertions")
    if not isinstance(assertions_raw, list):
        raise ValidationError("eval scenario assertions must be a list")

    steps: list[EvalStep] = []
    for raw_step in steps_raw:
        if not isinstance(raw_step, dict):
            raise ValidationError("eval scenario steps must contain mapping items")
        params = dict(raw_step)
        action = str(params.pop("action", ""))
        phase_id_raw = params.pop("phase_id", None)
        expect = params.pop("expect", None)
        steps.append(
            EvalStep(
                action=action,
                phase_id=None if phase_id_raw is None else str(phase_id_raw),
                expect=expect,
                params=params,
            )
        )

    assertions: list[EvalAssertion] = []
    for raw_assertion in assertions_raw:
        if not isinstance(raw_assertion, dict):
            raise ValidationError("eval scenario assertions must contain mapping items")
        params = dict(raw_assertion)
        assertion_type = str(params.pop("type", ""))
        assertions.append(EvalAssertion(type=assertion_type, params=params))

    scenario = EvalScenario(
        id=str(raw.get("id", "")),
        description=str(raw.get("description", "")),
        setup=raw.get("setup", {}),
        steps=steps,
        assertions=assertions,
        tags=[str(tag) for tag in raw.get("tags", []) or []],
    )
    return validate_scenario(scenario)


def load_suite(directory: Path) -> list[EvalScenario]:
    if not directory.exists():
        return []
    scenarios = [load_scenario(path) for path in sorted(directory.glob("*.yaml"))]
    return scenarios


def validate_scenario(scenario: EvalScenario) -> EvalScenario:
    plan = _build_plan_document(scenario, scenario.setup["plan"], _DEFAULT_SCENARIO_SESSION_ID)
    phase_ids = {phase.id for phase in plan.phases}
    for step in scenario.steps:
        if step.action in {
            "start_phase",
            "complete_phase",
            "verify_phase",
            "record_failure",
            "request_approval",
            "resolve_approval",
        }:
            if step.phase_id is None:
                raise ValidationError(f"eval step {step.action!r} requires phase_id")
            if step.phase_id not in phase_ids:
                raise ValidationError(f"eval step references unknown phase_id {step.phase_id!r}")
        if step.action == "resolve_approval":
            resolution = step.params.get("resolution")
            if resolution not in {"approve", "reject"}:
                raise ValidationError("resolve_approval steps require resolution=approve|reject")
        if step.action == "complete_phase" and "commit_sha" not in step.params:
            raise ValidationError("complete_phase steps require commit_sha")
        if step.action in {"create_file", "delete_file"} and "path" not in step.params:
            raise ValidationError(f"{step.action} steps require path")

    for assertion in scenario.assertions:
        if assertion.type in {"phase_status", "approval_status"}:
            phase_id = assertion.params.get("phase_id")
            if phase_id not in phase_ids:
                raise ValidationError(f"eval assertion references unknown phase_id {phase_id!r}")
        if assertion.type == "metric":
            name = assertion.params.get("name")
            if name not in METRIC_NAMES:
                raise ValidationError(
                    f"eval metric assertion must name one of {sorted(METRIC_NAMES)}"
                )
    return scenario


def compute_eval_metrics(
    scenario: EvalScenario,
    plan: PlanDocument,
    traces: list[dict[str, Any]],
) -> dict[str, float]:
    total_failures = sum(len(phase.failures) for phase in plan.phases)
    total_attempts = total_failures + len(plan.phases)
    verification_passes = 0
    verification_failures = 0
    error_count = 0
    step_like_spans = 0
    human_interventions = 0
    for span in traces:
        span_type = span.get("span_type")
        if span.get("status") == "error":
            error_count += 1
        if span_type in {"plan_action", "verification"}:
            step_like_spans += 1
        if span_type == "verification":
            metadata = span.get("metadata") or {}
            verification_passes += int(metadata.get("passed", 0))
            verification_failures += int(metadata.get("failed", 0))
        if "approval" in str(span.get("name", "")):
            human_interventions += 1
    verification_total = verification_passes + verification_failures
    return {
        "task_success": 1.0 if plan.status == "completed" else 0.0,
        "steps_to_success": float(step_like_spans if plan.status == "completed" else 0),
        "retry_rate": float(total_failures / total_attempts) if total_attempts else 0.0,
        "verification_pass_rate": (
            float(verification_passes / verification_total) if verification_total else 0.0
        ),
        "error_rate": float(error_count / len(traces)) if traces else 0.0,
        "human_intervention_count": float(human_interventions),
    }


def _execute_step(
    step: EvalStep,
    *,
    root: Path,
    plan_path: Path,
    session_id: str,
) -> dict[str, Any]:
    plan = load_plan(plan_path, root)
    if step.phase_id is not None:
        phase = resolve_phase(plan, step.phase_id)
    else:
        phase = None

    if step.action == "start_phase":
        assert phase is not None
        if plan.status == "paused":
            return {
                "plan_status": "paused",
                "phase_status": phase.status,
                "message": f"Plan is paused, awaiting approval for phase '{phase.id}'.",
            }

        approval = load_approval(root, plan.id, phase.id)
        if phase.requires_approval:
            if approval is None:
                pending = _create_pending_approval(
                    root, plan, phase, int(step.params.get("expires_days", 7))
                )
                plan.status = "paused"
                save_plan(plan_path, plan, root)
                record_trace(
                    root,
                    session_id,
                    span_type="plan_action",
                    name="approval-requested",
                    status="ok",
                    metadata={"plan_id": plan.id, "phase_id": phase.id},
                )
                return {
                    "plan_status": plan.status,
                    "phase_status": phase.status,
                    "approval_status": pending.status,
                }
            if approval.status == "pending":
                plan.status = "paused"
                save_plan(plan_path, plan, root)
                return {
                    "plan_status": plan.status,
                    "phase_status": phase.status,
                    "approval_status": approval.status,
                }
            if approval.status in {"rejected", "expired"}:
                plan.status = "blocked"
                if phase.status == "pending":
                    phase.status = "blocked"
                save_plan(plan_path, plan, root)
                return {
                    "plan_status": plan.status,
                    "phase_status": phase.status,
                    "approval_status": approval.status,
                }

        plan.status = "active"
        phase.status = "in-progress"
        save_plan(plan_path, plan, root)
        record_trace(
            root,
            session_id,
            span_type="plan_action",
            name="start",
            status="ok",
            metadata={"plan_id": plan.id, "phase_id": phase.id},
        )
        return {"plan_status": plan.status, "phase_status": phase.status}

    if step.action == "complete_phase":
        assert phase is not None
        if plan.status == "paused":
            return {
                "plan_status": "paused",
                "phase_status": phase.status,
                "message": f"Plan is paused, awaiting approval for phase '{phase.id}'.",
            }
        if bool(step.params.get("verify", False)):
            verification = verify_postconditions(plan, phase, root)
            summary = verification["summary"]
            record_trace(
                root,
                session_id,
                span_type="verification",
                name=f"verify:{phase.id}",
                status="ok" if verification["all_passed"] else "error",
                metadata={
                    "plan_id": plan.id,
                    "phase_id": phase.id,
                    "passed": summary["passed"],
                    "failed": summary["failed"],
                },
            )
            if not verification["all_passed"]:
                return {
                    "status": "verification_failed",
                    "plan_status": plan.status,
                    "phase_status": phase.status,
                    **verification,
                }
        phase.status = "completed"
        phase.commit = str(step.params["commit_sha"])
        plan.sessions_used += 1
        if all(candidate.status == "completed" for candidate in plan.phases):
            plan.status = "completed"
        else:
            plan.status = "active"
        save_plan(plan_path, plan, root)
        record_trace(
            root,
            session_id,
            span_type="plan_action",
            name="complete",
            status="ok",
            metadata={"plan_id": plan.id, "phase_id": phase.id},
        )
        return {
            "plan_status": plan.status,
            "phase_status": phase.status,
            "sessions_used": plan.sessions_used,
        }

    if step.action == "verify_phase":
        assert phase is not None
        verification = verify_postconditions(plan, phase, root)
        summary = verification["summary"]
        record_trace(
            root,
            session_id,
            span_type="verification",
            name=f"verify:{phase.id}",
            status="ok" if verification["all_passed"] else "error",
            metadata={
                "plan_id": plan.id,
                "phase_id": phase.id,
                "passed": summary["passed"],
                "failed": summary["failed"],
            },
        )
        return verification

    if step.action == "record_failure":
        assert phase is not None
        phase.failures.append(
            PhaseFailure(
                timestamp=_now_iso(),
                reason=str(step.params.get("reason", "Eval failure recorded")),
                verification_results=step.params.get("verification_results"),
                attempt=len(phase.failures) + 1,
            )
        )
        save_plan(plan_path, plan, root)
        attempt_number = len(phase.failures)
        record_trace(
            root,
            session_id,
            span_type="plan_action",
            name="record-failure",
            status="ok",
            metadata={"plan_id": plan.id, "phase_id": phase.id},
        )
        return {"phase_status": phase.status, "attempt_number": attempt_number}

    if step.action == "request_approval":
        assert phase is not None
        approval = load_approval(root, plan.id, phase.id)
        if approval is None or approval.status != "pending":
            approval = _create_pending_approval(
                root, plan, phase, int(step.params.get("expires_days", 7))
            )
        plan.status = "paused"
        save_plan(plan_path, plan, root)
        record_trace(
            root,
            session_id,
            span_type="plan_action",
            name="approval-requested",
            status="ok",
            metadata={"plan_id": plan.id, "phase_id": phase.id},
        )
        return {"plan_status": plan.status, "approval_status": approval.status}

    if step.action == "resolve_approval":
        assert phase is not None
        approval = load_approval(root, plan.id, phase.id)
        if approval is None:
            raise NotFoundError(f"No approval found for phase {phase.id!r}")
        if approval.status != "pending":
            raise ValidationError(
                f"Approval for phase '{phase.id}' is already resolved (status: {approval.status!r})"
            )
        resolution = str(step.params["resolution"])
        approval.resolution = resolution
        approval.reviewer = "eval"
        approval.resolved_at = _now_iso()
        approval.comment = (
            None if step.params.get("comment") is None else str(step.params.get("comment"))
        )
        approval.status = "approved" if resolution == "approve" else "rejected"
        save_approval(root, approval)
        _remove_pending_approval(root, plan.id, phase.id)
        plan.status = "active" if approval.status == "approved" else "blocked"
        save_plan(plan_path, plan, root)
        record_trace(
            root,
            session_id,
            span_type="plan_action",
            name=f"approval-{resolution}d",
            status="ok",
            metadata={"plan_id": plan.id, "phase_id": phase.id},
        )
        return {"plan_status": plan.status, "approval_status": approval.status}

    if step.action == "create_file":
        abs_path = root / str(step.params["path"])
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(str(step.params.get("content", "")), encoding="utf-8")
        return {"path": str(step.params["path"]), "exists": True}

    if step.action == "delete_file":
        abs_path = root / str(step.params["path"])
        if abs_path.exists():
            abs_path.unlink()
        return {"path": str(step.params["path"]), "exists": abs_path.exists()}

    raise ValidationError(f"Unsupported eval step action: {step.action}")


def _evaluate_expectation(step: EvalStep, result: dict[str, Any]) -> tuple[bool, str | None]:
    if not step.expect:
        return True, None
    for key, expected in step.expect.items():
        actual = result.get(key)
        if not _match_subset(expected, actual):
            return False, f"Expected {key}={expected!r}, got {actual!r}"
    return True, None


def _evaluate_assertion(
    assertion: EvalAssertion,
    *,
    root: Path,
    plan: PlanDocument,
    traces: list[dict[str, Any]],
    metrics: dict[str, float],
) -> tuple[str, Any, Any]:
    if assertion.type == "plan_status":
        expected = assertion.params.get("expected")
        actual: Any = plan.status
        return ("pass" if actual == expected else "fail", expected, actual)

    if assertion.type == "phase_status":
        phase = resolve_phase(plan, str(assertion.params.get("phase_id")))
        expected = assertion.params.get("expected")
        actual = phase.status
        return ("pass" if actual == expected else "fail", expected, actual)

    if assertion.type == "trace_span_count":
        matching = _filter_spans(traces, assertion.params.get("filter"))
        actual_count = len(matching)
        if "exact" in assertion.params:
            expected = assertion.params.get("exact")
            return ("pass" if actual_count == expected else "fail", expected, actual_count)
        minimum = assertion.params.get("min")
        maximum = assertion.params.get("max")
        status = "pass"
        if minimum is not None and actual_count < minimum:
            status = "fail"
        if maximum is not None and actual_count > maximum:
            status = "fail"
        return (status, {"min": minimum, "max": maximum}, actual_count)

    if assertion.type == "trace_metadata":
        matching = _filter_spans(traces, assertion.params.get("filter"))
        key = str(assertion.params.get("key", ""))
        expected = assertion.params.get("expected")
        actual_value: Any = None
        if matching:
            candidate = matching[0]
            actual_value = _get_nested_value(candidate, key)
            if actual_value is None and "metadata" in candidate:
                actual_value = _get_nested_value(candidate["metadata"], key)
        return ("pass" if actual_value == expected else "fail", expected, actual_value)

    if assertion.type == "metric":
        name = str(assertion.params.get("name"))
        actual_metric = metrics.get(name)
        if "expected" in assertion.params:
            expected = assertion.params.get("expected")
            return ("pass" if actual_metric == expected else "fail", expected, actual_metric)
        minimum = assertion.params.get("min")
        maximum = assertion.params.get("max")
        status = "pass"
        if minimum is not None and (actual_metric is None or actual_metric < minimum):
            status = "fail"
        if maximum is not None and (actual_metric is None or actual_metric > maximum):
            status = "fail"
        return (status, {"min": minimum, "max": maximum}, actual_metric)

    if assertion.type == "file_exists":
        path = str(assertion.params.get("path"))
        exists = (root / path).exists()
        return ("pass" if exists else "fail", True, exists)

    if assertion.type == "file_contains":
        path = str(assertion.params.get("path"))
        pattern = str(assertion.params.get("pattern", ""))
        abs_path = root / path
        contains = False
        if abs_path.exists():
            contains = (
                re.search(pattern, abs_path.read_text(encoding="utf-8"), re.MULTILINE) is not None
            )
        return ("pass" if contains else "fail", pattern, contains)

    if assertion.type == "approval_status":
        phase_id = str(assertion.params.get("phase_id"))
        approval = load_approval(root, plan.id, phase_id)
        approval_status = None if approval is None else approval.status
        expected = assertion.params.get("expected")
        return ("pass" if approval_status == expected else "fail", expected, approval_status)

    raise ValidationError(f"Unsupported eval assertion type: {assertion.type}")


def run_scenario(
    scenario: EvalScenario,
    root: Path,
    session_id: str,
    *,
    isolated: bool = False,
) -> ScenarioResult:
    validate_session_id(session_id)
    scenario = validate_scenario(scenario)

    if isolated:
        with tempfile.TemporaryDirectory() as tmpdir:
            return run_scenario(scenario, Path(tmpdir), session_id, isolated=False)

    started_at = time.perf_counter()
    root.mkdir(parents=True, exist_ok=True)

    setup = scenario.setup
    files = setup.get("files") or []
    if not isinstance(files, list):
        raise ValidationError("scenario setup.files must be a list when provided")
    registry_tools = setup.get("registry_tools") or []
    if not isinstance(registry_tools, list):
        raise ValidationError("scenario setup.registry_tools must be a list when provided")

    _write_setup_files(root, [dict(entry) for entry in files])
    _write_registry_tools(root, [dict(entry) for entry in registry_tools])

    plan = _build_plan_document(scenario, setup["plan"], session_id)
    plan_path = _plan_file_path(root, plan)
    save_plan(plan_path, plan, root)

    step_results: list[StepResult] = []
    encountered_error = False
    for index, step in enumerate(scenario.steps):
        step_started = time.perf_counter()
        try:
            result = _execute_step(step, root=root, plan_path=plan_path, session_id=session_id)
            ok, detail = _evaluate_expectation(step, result)
            status = "pass" if ok else "fail"
        except Exception as exc:  # noqa: BLE001
            status = "error"
            detail = str(exc)
            encountered_error = True
        duration_ms = int((time.perf_counter() - step_started) * 1000)
        step_results.append(
            StepResult(
                step_index=index,
                action=step.action,
                status=status,
                detail=detail,
                duration_ms=duration_ms,
            )
        )
        if encountered_error:
            break

    plan = load_plan(plan_path, root)
    traces = _load_trace_spans(root, session_id)
    metrics = compute_eval_metrics(scenario, plan, traces)

    assertion_results: list[AssertionResult] = []
    for index, assertion in enumerate(scenario.assertions):
        status, expected, actual = _evaluate_assertion(
            assertion,
            root=root,
            plan=plan,
            traces=traces,
            metrics=metrics,
        )
        assertion_results.append(
            AssertionResult(
                assertion_index=index,
                type=assertion.type,
                status=status,
                expected=expected,
                actual=actual,
            )
        )

    overall_status = "pass"
    if encountered_error or any(result.status == "error" for result in step_results):
        overall_status = "error"
    elif any(result.status == "fail" for result in step_results) or any(
        result.status == "fail" for result in assertion_results
    ):
        overall_status = "fail"

    return ScenarioResult(
        scenario_id=scenario.id,
        status=overall_status,
        step_results=step_results,
        assertion_results=assertion_results,
        metrics=metrics,
        duration_ms=int((time.perf_counter() - started_at) * 1000),
        timestamp=_now_iso(),
    )


def run_suite(scenarios: list[EvalScenario], root: Path, session_id: str) -> list[ScenarioResult]:
    validate_session_id(session_id)
    results: list[ScenarioResult] = []
    root.mkdir(parents=True, exist_ok=True)
    for scenario in scenarios:
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            results.append(run_scenario(scenario, Path(tmp), session_id))
    return results


def select_scenarios(
    root: Path,
    *,
    scenario_id: str | None = None,
    tag: str | None = None,
) -> list[EvalScenario]:
    selected_id = (
        None if scenario_id is None else validate_slug(scenario_id, field_name="scenario_id")
    )
    selected_tag = None if tag is None else tag.strip()
    scenarios = load_suite(eval_scenarios_dir(root))
    if selected_id is not None:
        scenarios = [scenario for scenario in scenarios if scenario.id == selected_id]
    if selected_tag is not None:
        scenarios = [scenario for scenario in scenarios if selected_tag in scenario.tags]
    return scenarios


def aggregate_results(results: list[ScenarioResult]) -> dict[str, Any]:
    summary = {
        "total": len(results),
        "passed": sum(1 for result in results if result.status == "pass"),
        "failed": sum(1 for result in results if result.status == "fail"),
        "errors": sum(1 for result in results if result.status == "error"),
    }
    metric_totals = {name: 0.0 for name in METRIC_NAMES}
    metric_counts = {name: 0 for name in METRIC_NAMES}
    for result in results:
        for name, value in result.metrics.items():
            if name in metric_totals:
                metric_totals[name] += float(value)
                metric_counts[name] += 1
    metrics = {
        name: (metric_totals[name] / metric_counts[name] if metric_counts[name] else 0.0)
        for name in METRIC_NAMES
    }
    return {"summary": summary, "metrics": metrics}


def scenario_result_trace_metadata(result: ScenarioResult) -> dict[str, Any]:
    return {
        "scenario_id": result.scenario_id,
        "eval_status": result.status,
        "duration_ms": result.duration_ms,
        "step_counts": {
            "pass": sum(1 for step in result.step_results if step.status == "pass"),
            "fail": sum(1 for step in result.step_results if step.status == "fail"),
            "error": sum(1 for step in result.step_results if step.status == "error"),
        },
        "assertion_counts": {
            "pass": sum(1 for assertion in result.assertion_results if assertion.status == "pass"),
            "fail": sum(1 for assertion in result.assertion_results if assertion.status == "fail"),
        },
        "metrics": result.metrics,
    }


def load_eval_runs(
    root: Path,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    scenario_id: str | None = None,
) -> list[dict[str, Any]]:
    selected_id = (
        None if scenario_id is None else validate_slug(scenario_id, field_name="scenario_id")
    )
    activity_root = root / "memory" / "activity"
    runs: list[dict[str, Any]] = []
    if not activity_root.exists():
        return runs

    for trace_path in sorted(activity_root.rglob("*.traces.jsonl")):
        try:
            lines = trace_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                span = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(span, dict):
                continue
            if span.get("span_type") != "verification":
                continue
            name = str(span.get("name", ""))
            if not name.startswith("eval:"):
                continue
            span_scenario_id = name.split(":", 1)[1]
            if selected_id is not None and span_scenario_id != selected_id:
                continue
            timestamp = str(span.get("timestamp", ""))
            run_date = timestamp[:10]
            if date_from is not None and run_date < date_from:
                continue
            if date_to is not None and run_date > date_to:
                continue
            metadata = span.get("metadata") or {}
            runs.append(
                {
                    "scenario_id": span_scenario_id,
                    "timestamp": timestamp,
                    "status": metadata.get("eval_status", span.get("status")),
                    "session_id": span.get("session_id"),
                    "metrics": metadata.get("metrics", {}),
                    "duration_ms": metadata.get("duration_ms"),
                    "step_counts": metadata.get("step_counts", {}),
                    "assertion_counts": metadata.get("assertion_counts", {}),
                }
            )
    runs.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    return runs


def build_eval_report(
    root: Path,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    runs = load_eval_runs(root, date_from=date_from, date_to=date_to, scenario_id=scenario_id)
    metric_totals = {name: 0.0 for name in METRIC_NAMES}
    metric_counts = {name: 0 for name in METRIC_NAMES}
    for run in runs:
        metrics = run.get("metrics", {}) or {}
        if not isinstance(metrics, dict):
            continue
        for name in METRIC_NAMES:
            if name in metrics:
                metric_totals[name] += float(metrics[name])
                metric_counts[name] += 1

    summary = {
        "total": len(runs),
        "passed": sum(1 for run in runs if run.get("status") == "pass"),
        "failed": sum(1 for run in runs if run.get("status") == "fail"),
        "errors": sum(1 for run in runs if run.get("status") == "error"),
    }
    metrics = {
        name: (metric_totals[name] / metric_counts[name] if metric_counts[name] else 0.0)
        for name in METRIC_NAMES
    }

    trends: dict[str, dict[str, float]] = {}
    ordered_runs = list(reversed(runs))
    if len(ordered_runs) >= 2:
        for name in METRIC_NAMES:
            first = ordered_runs[0].get("metrics", {}).get(name)
            last = ordered_runs[-1].get("metrics", {}).get(name)
            if first is None or last is None:
                continue
            first_value = float(first)
            last_value = float(last)
            trends[name] = {
                "first": first_value,
                "last": last_value,
                "delta": last_value - first_value,
            }
    return {"runs": runs, "summary": summary, "metrics": metrics, "trends": trends}


_REGRESSION_THRESHOLD = 0.10


def eval_history_path(root: Path) -> Path:
    """Return the absolute path to the eval history JSONL file."""
    return eval_scenarios_dir(root) / "eval-history.jsonl"


def append_eval_history(root: Path, results: list[ScenarioResult]) -> Path:
    """Append scenario results to the eval history file.  Returns the file path."""
    history_path = eval_history_path(root)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        for result in results:
            entry = {
                "scenario_id": result.scenario_id,
                "timestamp": result.timestamp,
                "status": result.status,
                "metrics": result.metrics,
                "duration_ms": result.duration_ms,
            }
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return history_path


def load_eval_history(root: Path) -> list[dict[str, Any]]:
    """Load all entries from the eval history file."""
    history_path = eval_history_path(root)
    if not history_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def compare_eval_runs(
    current: list[ScenarioResult],
    previous: list[ScenarioResult],
    *,
    threshold: float = _REGRESSION_THRESHOLD,
) -> dict[str, Any]:
    """Compare two sets of scenario results and detect regressions.

    A regression is:
    - A scenario that was pass in *previous* but fail/error in *current*.
    - A metric that degrades by more than *threshold* (fraction, default 10%).

    Returns ``{regressions, metric_deltas, summary}``.
    """
    prev_by_id = {r.scenario_id: r for r in previous}
    regressions: list[dict[str, Any]] = []
    metric_deltas: list[dict[str, Any]] = []

    for cur in current:
        prev = prev_by_id.get(cur.scenario_id)
        if prev is None:
            continue
        if prev.status == "pass" and cur.status in {"fail", "error"}:
            regressions.append(
                {
                    "scenario_id": cur.scenario_id,
                    "previous_status": prev.status,
                    "current_status": cur.status,
                    "type": "status_regression",
                }
            )
        for name in METRIC_NAMES:
            prev_val = prev.metrics.get(name)
            cur_val = cur.metrics.get(name)
            if prev_val is None or cur_val is None:
                continue
            if prev_val == 0:
                continue
            delta = cur_val - prev_val
            pct = abs(delta / prev_val)
            if delta < 0 and pct > threshold:
                metric_deltas.append(
                    {
                        "scenario_id": cur.scenario_id,
                        "metric": name,
                        "previous": prev_val,
                        "current": cur_val,
                        "delta": delta,
                        "pct_change": round(pct * 100, 1),
                    }
                )

    return {
        "regressions": regressions,
        "metric_deltas": metric_deltas,
        "summary": {
            "status_regressions": len(regressions),
            "metric_regressions": len(metric_deltas),
            "has_regressions": bool(regressions) or bool(metric_deltas),
        },
    }


__all__ = [
    "AssertionResult",
    "EVAL_ASSERTION_TYPES",
    "EVAL_STEP_ACTIONS",
    "EvalAssertion",
    "EvalScenario",
    "EvalStep",
    "METRIC_NAMES",
    "ScenarioResult",
    "StepResult",
    "append_eval_history",
    "compare_eval_runs",
    "compute_eval_metrics",
    "aggregate_results",
    "build_eval_report",
    "eval_history_path",
    "eval_scenarios_dir",
    "load_scenario",
    "load_eval_history",
    "load_eval_runs",
    "load_suite",
    "run_scenario",
    "run_suite",
    "scenario_result_trace_metadata",
    "select_scenarios",
    "validate_scenario",
]
