"""Project plan-oriented semantic tools."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ...path_policy import validate_session_id, validate_slug
from ...plan_utils import (
    APPROVAL_RESOLUTIONS,
    COST_TIERS,
    TRACE_SPAN_TYPES,
    TRACE_STATUSES,
    ApprovalDocument,
    PlanDocument,
    RunState,
    ToolDefinition,
    _all_registry_tools,
    append_operations_log,
    approval_filename,
    approvals_summary_path,
    assemble_briefing,
    build_plan_document_from_create_input,
    budget_status,
    build_review_from_input,
    check_run_state_staleness,
    estimate_cost,
    exportable_artifacts,
    load_approval,
    load_plan,
    load_registry,
    load_run_state,
    materialize_expired_approval,
    next_action,
    outbox_summary_path,
    phase_change_class,
    phase_payload,
    plan_progress,
    plan_title,
    project_outbox_root,
    project_plan_path,
    record_trace,
    regenerate_approvals_summary,
    regenerate_registry_summary,
    registry_file_path,
    registry_summary_path,
    resolve_phase,
    run_state_path,
    save_approval,
    save_plan,
    save_registry,
    save_run_state,
    scan_drop_zone,
    stage_external_file,
    trace_file_path,
    unresolved_blockers,
    update_run_state,
    validate_run_state_against_plan,
    raise_collected_validation_errors,
    validation_error_messages,
    verify_postconditions,
)
from ...preview_contract import (
    attach_approval_requirement,
    build_governed_preview,
    preview_target,
    require_approval_token,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _tool_annotations(**kwargs: object) -> Any:
    return cast(Any, kwargs)


def _persist_run_state(
    root: Path,
    repo: Any,
    plan: "PlanDocument",
    phase_id: str,
    action: str,
    session_id: str,
    files_changed: list[str],
    *,
    commit_to_git: bool = True,
    next_action_hint: str | None = None,
    error_message: str | None = None,
) -> None:
    """Load-or-create run state, apply an action, save, and optionally stage for git."""
    rs = load_run_state(root, plan.project, plan.id)
    if rs is None:
        rs = RunState(plan_id=plan.id, project_id=plan.project)
    update_run_state(
        rs,
        action,
        phase_id,
        session_id=session_id,
        next_action_hint=next_action_hint,
        error_message=error_message,
    )
    save_run_state(root, rs)
    rs_rel = run_state_path(plan.project, plan.id)
    if commit_to_git and repo is not None:
        repo.add(rs_rel)
        if rs_rel not in files_changed:
            files_changed.append(rs_rel)


def _project_summary_path(project_id: str) -> str:
    project_slug = validate_slug(project_id, field_name="project_id")
    return f"memory/working/projects/{project_slug}/SUMMARY.md"


def _find_project_plan_matches(root: Path, plan_id: str) -> list[tuple[str, str]]:
    plan_slug = validate_slug(plan_id, field_name="plan_id")
    projects_root = root / "memory" / "working" / "projects"
    if not projects_root.is_dir():
        return []

    matches: list[tuple[str, str]] = []
    for abs_path in sorted(projects_root.glob(f"*/plans/{plan_slug}.yaml")):
        project_id = abs_path.parents[1].name
        matches.append((abs_path.relative_to(root).as_posix(), project_id))
    return matches


def _resolve_existing_plan_path(
    root: Path,
    plan_id: str,
    project_id: str | None,
) -> tuple[str, str]:
    from ...errors import NotFoundError, ValidationError

    if project_id is not None:
        project_slug = validate_slug(project_id, field_name="project_id")
        plan_path = project_plan_path(project_slug, plan_id)
        if not (root / plan_path).exists():
            raise NotFoundError(f"Plan not found: {plan_path}")
        return plan_path, project_slug

    project_matches = _find_project_plan_matches(root, plan_id)
    if len(project_matches) == 1:
        return project_matches[0]
    if len(project_matches) > 1:
        match_ids = ", ".join(project for _, project in project_matches)
        raise ValidationError(
            f"Plan '{plan_id}' exists in multiple projects ({match_ids}); specify project_id."
        )
    raise NotFoundError(f"Plan not found: {plan_id}")


def _resolve_new_plan_path(root: Path, plan_id: str, project_id: str) -> tuple[str, str]:
    from ...errors import NotFoundError, ValidationError

    project_slug = validate_slug(project_id, field_name="project_id")
    project_summary = root / _project_summary_path(project_slug)
    if not project_summary.exists():
        raise NotFoundError(f"Project not found: memory/working/projects/{project_slug}")

    plan_path = project_plan_path(project_slug, plan_id)
    if (root / plan_path).exists():
        raise ValidationError(f"Plan already exists: {plan_path}")
    return plan_path, project_slug


def _sync_project_navigation(root: Path, repo, project_id: str, files_changed: list[str]) -> None:
    from ...frontmatter_utils import (
        collect_project_entries,
        count_active_project_plans,
        count_project_plans,
        read_with_frontmatter,
        render_projects_navigator,
        today_str,
        write_with_frontmatter,
    )

    project_summary_path = _project_summary_path(project_id)
    abs_project_summary = root / project_summary_path
    if abs_project_summary.exists():
        project_fm, project_body = read_with_frontmatter(abs_project_summary)
        project_fm["active_plans"] = count_active_project_plans(root, project_id)
        project_fm["plans"] = count_project_plans(root, project_id)
        project_fm["last_activity"] = today_str()
        write_with_frontmatter(abs_project_summary, project_fm, project_body)
        repo.add(project_summary_path)
        if project_summary_path not in files_changed:
            files_changed.append(project_summary_path)

    navigator_path = "memory/working/projects/SUMMARY.md"
    abs_navigator = root / navigator_path
    if abs_navigator.exists():
        navigator_content = render_projects_navigator(collect_project_entries(root))
        abs_navigator.write_text(navigator_content, encoding="utf-8")
        repo.add(navigator_path)
        if navigator_path not in files_changed:
            files_changed.append(navigator_path)


def _create_preview(
    *,
    mode: str,
    change_class: str,
    summary: str,
    reasoning: str,
    target_files: list[tuple[str, str]],
    invariant_effects: list[str],
    commit_message: str | None,
    resulting_state: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    return build_governed_preview(
        mode=mode,
        change_class=change_class,
        summary=summary,
        reasoning=reasoning,
        target_files=[preview_target(path, action) for path, action in target_files],
        invariant_effects=invariant_effects,
        commit_message=commit_message,
        resulting_state=resulting_state,
        warnings=warnings,
    )


def _stage_trace_file_if_present(
    root: Path,
    repo,
    session_id: str | None,
    files_changed: list[str],
) -> None:
    if session_id is None:
        return

    trace_path = trace_file_path(session_id)
    if (root / trace_path).exists():
        repo.add(trace_path)
        if trace_path not in files_changed:
            files_changed.append(trace_path)


def create_plan_write_result(
    *,
    repo: Any,
    root: Path,
    plan_id: str,
    project_id: str,
    purpose_summary: str,
    purpose_context: str,
    phases: list[dict[str, Any]],
    session_id: str,
    questions: list[str] | None = None,
    budget: dict[str, Any] | None = None,
    status: str = "active",
    preview: bool = False,
):
    """Create a plan using the shared governed write path used by MCP and CLI flows."""
    from ...errors import NotFoundError, ValidationError
    from ...frontmatter_utils import today_str
    from ...models import MemoryWriteResult

    warnings: list[str] = []

    try:
        validation_errors: list[str] = []
        path_resolution_error: NotFoundError | None = None

        resolved_project_id = project_id
        plan_path = ""
        try:
            plan_path, resolved_project_id = _resolve_new_plan_path(root, plan_id, project_id)
        except ValidationError as exc:
            validation_errors.extend(validation_error_messages(exc))
        except NotFoundError as exc:
            path_resolution_error = exc

        plan = None
        try:
            plan = build_plan_document_from_create_input(
                plan_id=plan_id,
                project_id=resolved_project_id,
                created=today_str(),
                session_id=session_id,
                status=status,
                purpose_summary=purpose_summary,
                purpose_context=purpose_context,
                questions=questions,
                phases=phases,
                budget=budget,
            )
        except ValidationError as exc:
            validation_errors.extend(validation_error_messages(exc))

        if path_resolution_error is not None and validation_errors:
            validation_errors.append(str(path_resolution_error))
            path_resolution_error = None

        raise_collected_validation_errors(validation_errors)
        if path_resolution_error is not None:
            raise path_resolution_error

        assert plan is not None
        assert plan_path
    except ValidationError as exc:
        if not preview:
            raise
        validation_errors = validation_error_messages(exc)
        invalid_warnings = list(warnings) + [
            "Plan input is invalid; call memory_plan_schema for the nested contract."
        ]
        invalid_state = {
            "valid": False,
            "errors": validation_errors,
            "schema_tool": "memory_plan_schema",
        }
        preview_payload = _create_preview(
            mode="preview",
            change_class="proposed",
            summary="Plan creation request is invalid; no files would be written.",
            reasoning=(
                "preview=True downgrades plan-input validation failures into structured feedback "
                "so callers can fix all surfaced issues before retrying."
            ),
            target_files=[],
            invariant_effects=[
                "No files would be created or updated until validation errors are fixed."
            ],
            commit_message=None,
            resulting_state=invalid_state,
            warnings=invalid_warnings,
        )
        return MemoryWriteResult(
            files_changed=[],
            commit_sha=None,
            commit_message=None,
            new_state=invalid_state,
            warnings=invalid_warnings,
            preview=preview_payload,
        )

    files_changed = [
        plan_path,
        _project_summary_path(resolved_project_id),
        "memory/working/projects/SUMMARY.md",
        f"memory/working/projects/{resolved_project_id}/operations.jsonl",
    ]
    new_state: dict[str, Any] = {
        "plan_path": plan_path,
        "project_id": resolved_project_id,
        "status": plan.status,
        "phase_count": len(plan.phases),
        "next_action": next_action(plan),
    }
    bs = budget_status(plan)
    if bs is not None:
        new_state["budget_status"] = bs
    commit_msg = f"[plan] Create {plan_id}"
    preview_payload = _create_preview(
        mode="preview" if preview else "apply",
        change_class="proposed",
        summary=f"Create YAML plan {plan_id} in project {resolved_project_id}.",
        reasoning=(
            "Structured YAML plans are the governed execution surface for multi-phase work, "
            "so creation also refreshes project routing metadata and initializes operations logging."
        ),
        target_files=[
            (plan_path, "create"),
            (_project_summary_path(resolved_project_id), "update"),
            ("memory/working/projects/SUMMARY.md", "update"),
            (f"memory/working/projects/{resolved_project_id}/operations.jsonl", "append"),
        ],
        invariant_effects=[
            "Creates a machine-validated YAML plan with structured purpose, phases, and change specs.",
            "Refreshes project routing counters so active plan navigation stays accurate.",
            "Initializes a project-scoped operations log entry for plan creation.",
        ],
        commit_message=commit_msg,
        resulting_state=new_state,
        warnings=warnings,
    )
    if preview:
        return MemoryWriteResult(
            files_changed=files_changed,
            commit_sha=None,
            commit_message=None,
            new_state=new_state,
            warnings=warnings,
            preview=preview_payload,
        )

    abs_plan = repo.abs_path(plan_path)
    save_plan(abs_plan, plan, root)
    repo.add(plan_path)
    _append_plan_log(
        root,
        repo,
        resolved_project_id,
        files_changed,
        session_id=session_id,
        action="plan-created",
        plan_id=plan.id,
        detail=plan_title(plan),
    )
    _sync_project_navigation(root, repo, resolved_project_id, files_changed)
    record_trace(
        root,
        session_id,
        span_type="plan_action",
        name="create",
        status="ok",
        metadata={"plan_id": plan.id, "project_id": resolved_project_id, "action": "create"},
    )
    _stage_trace_file_if_present(root, repo, session_id, files_changed)
    commit_result = repo.commit(commit_msg)
    return MemoryWriteResult.from_commit(
        files_changed=files_changed,
        commit_result=commit_result,
        commit_message=commit_msg,
        new_state=new_state,
        warnings=warnings,
        preview=preview_payload,
    )


def execute_plan_action_result(
    *,
    repo: Any,
    root: Path,
    plan_id: str,
    project_id: str | None = None,
    phase_id: str | None = None,
    action: str = "inspect",
    session_id: str | None = None,
    commit_sha: str | None = None,
    review: dict[str, Any] | None = None,
    verify: bool = False,
    reason: str | None = None,
    verification_results: list[dict[str, Any]] | None = None,
    preview: bool = False,
) -> dict[str, Any]:
    """Inspect, start, complete, or record failure on a plan phase."""
    from ...errors import AlreadyDoneError, ValidationError
    from ...frontmatter_utils import today_str
    from ...models import MemoryWriteResult

    warnings: list[str] = []

    plan_path, resolved_project_id = _resolve_existing_plan_path(root, plan_id, project_id)
    abs_plan = repo.abs_path(plan_path)
    plan = load_plan(abs_plan, root)
    phase = resolve_phase(plan, phase_id)
    blockers = unresolved_blockers(plan, phase, root)
    payload = phase_payload(plan, phase, root)
    payload["unresolved_blockers"] = blockers

    if action == "inspect":
        return payload

    if action not in {"start", "complete", "record_failure"}:
        raise ValidationError("action must be one of: inspect, start, complete, record_failure")
    if session_id is None:
        raise ValidationError(
            "session_id is required for start, complete, and record_failure actions"
        )
    validate_session_id(session_id)

    change_class = phase_change_class(phase)
    files_changed = [
        plan_path,
        _project_summary_path(resolved_project_id),
        "memory/working/projects/SUMMARY.md",
        f"memory/working/projects/{resolved_project_id}/operations.jsonl",
    ]

    if plan.status == "paused" and action in {"start", "complete"}:
        paused_msg = (
            f"Plan is paused, awaiting approval for phase '{phase.id}'. "
            "Use `memory_resolve_approval` to approve or reject."
        )
        return {"plan_status": "paused", "phase_id": phase.id, "message": paused_msg}

    if action == "start" and blockers:
        plan.status = "blocked"
        if phase.status == "pending":
            phase.status = "blocked"
        commit_msg = f"[plan] Block {plan.id}:{phase.id}"
        blocked_state: dict[str, Any] = {
            "plan_status": plan.status,
            "phase_status": phase.status,
            "phase_id": phase.id,
            "blocked_by": blockers,
            "next_action": next_action(plan),
        }
        bs = budget_status(plan)
        if bs is not None:
            blocked_state["budget_status"] = bs
        preview_payload = _create_preview(
            mode="preview" if preview else "apply",
            change_class=change_class,
            summary=f"Mark plan {plan.id} blocked on phase {phase.id} until blockers resolve.",
            reasoning=(
                "The execute flow records blocker state inside the plan so future sessions and "
                "summaries can see why work paused."
            ),
            target_files=[
                (plan_path, "update"),
                (_project_summary_path(resolved_project_id), "update"),
                ("memory/working/projects/SUMMARY.md", "update"),
                (f"memory/working/projects/{resolved_project_id}/operations.jsonl", "append"),
            ],
            invariant_effects=[
                "Transitions the plan into blocked status when a phase cannot legally start.",
                "Records the blocker event in the project operations log.",
            ],
            commit_message=commit_msg,
            resulting_state=blocked_state,
            warnings=warnings,
        )
        if preview:
            return MemoryWriteResult(
                files_changed=files_changed,
                commit_sha=None,
                commit_message=None,
                new_state=blocked_state,
                warnings=warnings,
                preview=preview_payload,
            ).to_dict()

        save_plan(abs_plan, plan, root)
        repo.add(plan_path)
        _append_plan_log(
            root,
            repo,
            resolved_project_id,
            files_changed,
            session_id=session_id,
            action="phase-blocked",
            plan_id=plan.id,
            phase_id=phase.id,
            detail=f"Blocked by {len(blockers)} dependency references",
        )
        _sync_project_navigation(root, repo, resolved_project_id, files_changed)
        commit_result = repo.commit(commit_msg)
        return MemoryWriteResult.from_commit(
            files_changed=files_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=blocked_state,
            warnings=warnings,
            preview=preview_payload,
        ).to_dict()

    if action == "start":
        if phase.status == "completed":
            raise AlreadyDoneError(f"Phase '{phase.id}' is already complete")
        if phase.status == "in-progress":
            raise AlreadyDoneError(f"Phase '{phase.id}' is already in progress")

        if phase.requires_approval:
            from datetime import datetime, timedelta, timezone

            existing_approval = load_approval(root, plan.id, phase.id)

            if existing_approval is not None and existing_approval.status == "approved":
                pass

            elif existing_approval is not None and existing_approval.status == "pending":
                return {
                    "plan_status": "paused",
                    "phase_id": phase.id,
                    "message": (
                        f"Awaiting approval for phase '{phase.id}'. "
                        "Use `memory_resolve_approval` to approve or reject."
                    ),
                    "approval": existing_approval.to_dict(),
                }

            elif existing_approval is not None and existing_approval.status in {
                "rejected",
                "expired",
            }:
                plan.status = "blocked"
                approval_transition_files = list(files_changed)
                approval_filename_rel = approval_filename(plan.id, phase.id)
                approval_pending_file = f"memory/working/approvals/pending/{approval_filename_rel}"
                approval_resolved_file = (
                    f"memory/working/approvals/resolved/{approval_filename_rel}"
                )
                if existing_approval.status == "expired":
                    approval_transition_files.extend(
                        [
                            approval_pending_file,
                            approval_resolved_file,
                            approvals_summary_path(),
                        ]
                    )
                commit_msg_rejected = (
                    f"[plan] Block {plan.id}:{phase.id} (approval {existing_approval.status})"
                )
                rejected_state: dict[str, Any] = {
                    "plan_status": plan.status,
                    "phase_id": phase.id,
                    "approval_status": existing_approval.status,
                    "message": (
                        f"Approval for phase '{phase.id}' was {existing_approval.status}. "
                        "Call `memory_request_approval` to re-request or abandon the plan."
                    ),
                    "approval": existing_approval.to_dict(),
                }
                if preview:
                    return rejected_state

                if existing_approval.status == "expired":
                    materialize_expired_approval(root, existing_approval)
                    regenerate_approvals_summary(root)
                    if repo.is_tracked(approval_pending_file):
                        repo.add(approval_pending_file)
                    repo.add(approval_resolved_file)
                    repo.add(approvals_summary_path())
                save_plan(abs_plan, plan, root)
                repo.add(plan_path)
                _append_plan_log(
                    root,
                    repo,
                    resolved_project_id,
                    approval_transition_files,
                    session_id=session_id,
                    action="phase-blocked",
                    plan_id=plan.id,
                    phase_id=phase.id,
                    detail=f"Approval {existing_approval.status}",
                )
                _sync_project_navigation(root, repo, resolved_project_id, approval_transition_files)
                commit_result_rejected = repo.commit(commit_msg_rejected)
                return MemoryWriteResult.from_commit(
                    files_changed=approval_transition_files,
                    commit_result=commit_result_rejected,
                    commit_message=commit_msg_rejected,
                    new_state=rejected_state,
                    warnings=warnings,
                ).to_dict()

            else:
                now_dt = datetime.now(timezone.utc)
                now_str = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                expires_str = (now_dt + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
                bs_ctx = budget_status(plan)
                approval_context: dict[str, Any] = {
                    "phase_title": phase.title,
                    "phase_summary": (
                        f"Phase '{phase.id}' requires human approval before execution. "
                        f"Sources: {len(phase.sources)}, Changes: {len(phase.changes)}"
                    ),
                    "sources": [source.path for source in phase.sources],
                    "changes": [change.to_dict() for change in phase.changes],
                    "change_class": change_class,
                }
                if bs_ctx is not None:
                    approval_context["budget_status"] = bs_ctx
                new_approval = ApprovalDocument(
                    plan_id=plan.id,
                    phase_id=phase.id,
                    project_id=resolved_project_id,
                    status="pending",
                    requested=now_str,
                    expires=expires_str,
                    context=approval_context,
                )
                plan.status = "paused"
                approval_file = (
                    f"memory/working/approvals/pending/{approval_filename(plan.id, phase.id)}"
                )
                approval_files_changed = list(files_changed) + [
                    approval_file,
                    approvals_summary_path(),
                ]
                commit_msg_pause = f"[plan] Pause {plan.id}:{phase.id} pending approval"
                paused_state: dict[str, Any] = {
                    "plan_status": "paused",
                    "phase_id": phase.id,
                    "approval_file": approval_file,
                    "expires": expires_str,
                    "message": (
                        f"Phase '{phase.id}' requires human approval. "
                        "Approval request created. Use `memory_resolve_approval` "
                        "to approve or reject."
                    ),
                }
                if preview:
                    return paused_state

                save_approval(root, new_approval)
                regenerate_approvals_summary(root)
                save_plan(abs_plan, plan, root)
                repo.add(plan_path)
                repo.add(approval_file)
                repo.add(approvals_summary_path())
                _append_plan_log(
                    root,
                    repo,
                    resolved_project_id,
                    approval_files_changed,
                    session_id=session_id,
                    action="approval-requested",
                    plan_id=plan.id,
                    phase_id=phase.id,
                    detail=f"Auto-paused: approval required for {phase.id}",
                )
                _sync_project_navigation(root, repo, resolved_project_id, approval_files_changed)
                record_trace(
                    root,
                    session_id,
                    span_type="plan_action",
                    name="approval-requested",
                    status="ok",
                    metadata={
                        "plan_id": plan.id,
                        "phase_id": phase.id,
                        "expires": expires_str,
                    },
                )
                _stage_trace_file_if_present(root, repo, session_id, approval_files_changed)
                commit_result_pause = repo.commit(commit_msg_pause)
                return MemoryWriteResult.from_commit(
                    files_changed=approval_files_changed,
                    commit_result=commit_result_pause,
                    commit_message=commit_msg_pause,
                    new_state=paused_state,
                    warnings=warnings,
                ).to_dict()

        plan.status = "active"
        phase.status = "in-progress"
        commit_msg = f"[plan] Start {plan.id}:{phase.id}"
        start_state: dict[str, Any] = {
            "plan_status": plan.status,
            "phase_status": phase.status,
            "phase_id": phase.id,
            "next_action": phase.title,
            "change_class": change_class,
            "requires_approval": phase.requires_approval,
            "approval_required": (
                phase.requires_approval or change_class in {"proposed", "protected"}
            ),
        }
        if phase.sources:
            start_state["sources"] = [source.to_dict() for source in phase.sources]
        if phase.postconditions:
            start_state["postconditions"] = [pc.to_dict() for pc in phase.postconditions]
        bs = budget_status(plan)
        if bs is not None:
            start_state["budget_status"] = bs
        preview_payload = _create_preview(
            mode="preview" if preview else "apply",
            change_class=change_class,
            summary=f"Start phase {phase.id} in plan {plan.id}.",
            reasoning=(
                "Starting a phase records the active execution context so later writes and summaries "
                "can tie file mutations back to the plan that authorized them."
            ),
            target_files=[
                (plan_path, "update"),
                (_project_summary_path(resolved_project_id), "update"),
                ("memory/working/projects/SUMMARY.md", "update"),
                (f"memory/working/projects/{resolved_project_id}/operations.jsonl", "append"),
            ],
            invariant_effects=[
                "Transitions the selected phase to in-progress after blocker validation succeeds.",
                "Records the phase-start event in the project operations log.",
            ],
            commit_message=commit_msg,
            resulting_state=start_state,
            warnings=warnings,
        )
        if preview:
            return MemoryWriteResult(
                files_changed=files_changed,
                commit_sha=None,
                commit_message=None,
                new_state=start_state,
                warnings=warnings,
                preview=preview_payload,
            ).to_dict()

        save_plan(abs_plan, plan, root)
        repo.add(plan_path)
        _persist_run_state(
            root,
            repo,
            plan,
            phase.id,
            "start",
            session_id,
            files_changed,
            next_action_hint=phase.title,
        )
        _append_plan_log(
            root,
            repo,
            resolved_project_id,
            files_changed,
            session_id=session_id,
            action="phase-started",
            plan_id=plan.id,
            phase_id=phase.id,
            detail=phase.title,
        )
        _sync_project_navigation(root, repo, resolved_project_id, files_changed)
        record_trace(
            root,
            session_id,
            span_type="plan_action",
            name="start",
            status="ok",
            metadata={"plan_id": plan.id, "phase_id": phase.id, "action": "start"},
            cost=estimate_cost(
                input_chars=len(json.dumps(start_state)),
                output_chars=len(json.dumps(start_state)),
            ),
        )
        _stage_trace_file_if_present(root, repo, session_id, files_changed)
        commit_result = repo.commit(commit_msg)
        return MemoryWriteResult.from_commit(
            files_changed=files_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=start_state,
            warnings=warnings,
            preview=preview_payload,
        ).to_dict()

    if action == "record_failure":
        from datetime import datetime, timezone

        from ...plan_utils import PhaseFailure

        if not reason or not reason.strip():
            raise ValidationError("reason is required when recording a failure")
        if phase.status not in {"in-progress", "pending"}:
            raise ValidationError(
                f"Cannot record failure on phase '{phase.id}' with status '{phase.status}'"
            )
        failure = PhaseFailure(
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=reason.strip(),
            verification_results=verification_results,
            attempt=len(phase.failures) + 1,
        )
        phase.failures.append(failure)

        commit_msg = f"[plan] Record failure {plan.id}:{phase.id} (attempt {failure.attempt})"
        failure_state: dict[str, Any] = {
            "plan_status": plan.status,
            "phase_status": phase.status,
            "phase_id": phase.id,
            "failure_recorded": failure.to_dict(),
            "total_failures": len(phase.failures),
            "attempt_number": len(phase.failures) + 1,
        }
        preview_payload = _create_preview(
            mode="preview" if preview else "apply",
            change_class=change_class,
            summary=f"Record failure on phase {phase.id} in plan {plan.id}.",
            reasoning=(
                "Recording failures provides structured context for retry "
                "attempts and enables agents to learn from prior mistakes."
            ),
            target_files=[
                (plan_path, "update"),
                (_project_summary_path(resolved_project_id), "update"),
                ("memory/working/projects/SUMMARY.md", "update"),
                (f"memory/working/projects/{resolved_project_id}/operations.jsonl", "append"),
            ],
            invariant_effects=[
                "Appends a PhaseFailure record to the phase.",
                "Logs the failure event in the project operations log.",
            ],
            commit_message=commit_msg,
            resulting_state=failure_state,
            warnings=warnings,
        )
        if preview:
            return MemoryWriteResult(
                files_changed=files_changed,
                commit_sha=None,
                commit_message=None,
                new_state=failure_state,
                warnings=warnings,
                preview=preview_payload,
            ).to_dict()

        save_plan(abs_plan, plan, root)
        repo.add(plan_path)
        _persist_run_state(
            root,
            repo,
            plan,
            phase.id,
            "record_failure",
            session_id,
            files_changed,
            commit_to_git=False,
            error_message=reason.strip(),
        )
        _append_plan_log(
            root,
            repo,
            resolved_project_id,
            files_changed,
            session_id=session_id,
            action="phase-failure",
            plan_id=plan.id,
            phase_id=phase.id,
            detail=reason.strip(),
        )
        _sync_project_navigation(root, repo, resolved_project_id, files_changed)
        record_trace(
            root,
            session_id,
            span_type="plan_action",
            name="record_failure",
            status="ok",
            metadata={
                "plan_id": plan.id,
                "phase_id": phase.id,
                "action": "record_failure",
                "attempt": failure.attempt,
            },
            cost=estimate_cost(
                input_chars=len(reason.strip()),
                output_chars=len(json.dumps(failure_state)),
            ),
        )
        _stage_trace_file_if_present(root, repo, session_id, files_changed)
        commit_result = repo.commit(commit_msg)
        return MemoryWriteResult.from_commit(
            files_changed=files_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=failure_state,
            warnings=warnings,
            preview=preview_payload,
        ).to_dict()

    if not commit_sha or not commit_sha.strip():
        raise ValidationError("commit_sha is required when completing a phase")
    if blockers:
        raise ValidationError(
            f"Phase '{phase.id}' is blocked by unresolved dependencies: "
            + ", ".join(entry["reference"] for entry in blockers)
        )
    if phase.status == "completed":
        raise AlreadyDoneError(f"Phase '{phase.id}' is already complete")

    if verify:
        verification = verify_postconditions(plan, phase, root)
        if not verification["all_passed"]:
            verification_state: dict[str, Any] = {
                "status": "verification_failed",
                "plan_status": plan.status,
                "phase_status": phase.status,
                "phase_id": phase.id,
                **verification,
            }
            return verification_state
        warnings.append(
            f"Verification passed: {verification['summary']['passed']} passed, "
            f"{verification['summary']['skipped']} skipped"
        )

    phase.status = "completed"
    phase.commit = commit_sha.strip()
    plan.sessions_used += 1
    done, total = plan_progress(plan)
    all_done = done == total

    bs = budget_status(plan)
    if bs is not None:
        if bs.get("past_deadline"):
            warnings.append(
                f"Budget warning: past deadline ({bs['deadline']})"
                + (" [advisory]" if bs.get("advisory") else " [ENFORCED]")
            )
        if bs.get("over_session_budget"):
            warnings.append(
                f"Budget warning: session budget exhausted "
                f"({bs['sessions_used']}/{bs['max_sessions']})"
                + (" [advisory]" if bs.get("advisory") else " [ENFORCED]")
            )
    if all_done:
        plan.status = "completed"
        if review is not None:
            plan.review = build_review_from_input(review, today_str(), session_id)
        else:
            warnings.append(
                "Final phase completed without a supplied review; wrote a placeholder purpose assessment."
            )
            plan.review = build_review_from_input(
                {
                    "outcome": "completed",
                    "purpose_assessment": (
                        "Execution completed; a detailed purpose assessment still needs to be written."
                    ),
                    "unresolved": [],
                    "follow_up": None,
                },
                today_str(),
                session_id,
            )
    else:
        plan.status = "active"

    commit_msg = f"[plan] Complete {plan.id}:{phase.id}"
    completion_state: dict[str, Any] = {
        "plan_status": plan.status,
        "phase_status": phase.status,
        "phase_id": phase.id,
        "phase_commit": phase.commit,
        "plan_progress": [done, total],
        "sessions_used": plan.sessions_used,
        "next_action": next_action(plan),
        "review_written": plan.review is not None,
    }
    if bs is not None:
        completion_state["budget_status"] = bs
    preview_payload = _create_preview(
        mode="preview" if preview else "apply",
        change_class=change_class,
        summary=f"Complete phase {phase.id} in plan {plan.id} and record commit metadata.",
        reasoning=(
            "Phase completion seals the plan state machine by attaching the implementation commit, "
            "advancing progress, and closing the plan when all phases are done."
        ),
        target_files=[
            (plan_path, "update"),
            (_project_summary_path(resolved_project_id), "update"),
            ("memory/working/projects/SUMMARY.md", "update"),
            (f"memory/working/projects/{resolved_project_id}/operations.jsonl", "append"),
        ],
        invariant_effects=[
            "Marks the phase complete and stores the commit SHA that produced the work.",
            "Transitions the plan to completed and populates review data when the last phase finishes.",
            "Logs the phase-complete event and, when applicable, the plan-complete event.",
        ],
        commit_message=commit_msg,
        resulting_state=completion_state,
        warnings=warnings,
    )
    if preview:
        return MemoryWriteResult(
            files_changed=files_changed,
            commit_sha=None,
            commit_message=None,
            new_state=completion_state,
            warnings=warnings,
            preview=preview_payload,
        ).to_dict()

    save_plan(abs_plan, plan, root)
    repo.add(plan_path)
    next_step = next_action(plan)
    _persist_run_state(
        root,
        repo,
        plan,
        phase.id,
        "complete",
        session_id,
        files_changed,
        next_action_hint=next_step["title"] if next_step else None,
    )
    _append_plan_log(
        root,
        repo,
        resolved_project_id,
        files_changed,
        session_id=session_id,
        action="phase-completed",
        plan_id=plan.id,
        phase_id=phase.id,
        commit=phase.commit,
        detail=phase.title,
    )
    if all_done:
        _append_plan_log(
            root,
            repo,
            resolved_project_id,
            files_changed,
            session_id=session_id,
            action="plan-completed",
            plan_id=plan.id,
            commit=phase.commit,
            detail=plan_title(plan),
        )
    _sync_project_navigation(root, repo, resolved_project_id, files_changed)
    record_trace(
        root,
        session_id,
        span_type="plan_action",
        name="complete",
        status="ok",
        metadata={
            "plan_id": plan.id,
            "phase_id": phase.id,
            "action": "complete",
            "commit": phase.commit,
            "plan_done": all_done,
        },
        cost=estimate_cost(
            input_chars=len(json.dumps(completion_state)),
            output_chars=len(json.dumps(completion_state)),
        ),
    )
    _stage_trace_file_if_present(root, repo, session_id, files_changed)
    commit_result = repo.commit(commit_msg)
    return MemoryWriteResult.from_commit(
        files_changed=files_changed,
        commit_result=commit_result,
        commit_message=commit_msg,
        new_state=completion_state,
        warnings=warnings,
        preview=preview_payload,
    ).to_dict()


def resolve_approval_action_result(
    *,
    repo: Any,
    root: Path,
    plan_id: str,
    phase_id: str,
    resolution: str,
    comment: str | None = None,
    preview: bool = False,
) -> dict[str, Any]:
    """Approve or reject a pending plan approval using the shared governed write path."""
    from datetime import datetime, timezone

    from ...errors import NotFoundError, ValidationError
    from ...models import MemoryWriteResult

    warnings: list[str] = []

    if resolution not in APPROVAL_RESOLUTIONS:
        raise ValidationError(
            f"resolution must be one of {sorted(APPROVAL_RESOLUTIONS)}: {resolution!r}"
        )

    existing = load_approval(root, plan_id, phase_id)
    if existing is None:
        raise NotFoundError(f"No approval document found for plan '{plan_id}' phase '{phase_id}'")
    if existing.status == "expired":
        raise ValidationError(
            f"Approval for phase '{phase_id}' has expired and can no longer be resolved"
        )
    if existing.status != "pending":
        raise ValidationError(
            f"Approval for phase '{phase_id}' is already resolved (status: {existing.status!r})"
        )

    plan_path_r, resolved_project_id = _resolve_existing_plan_path(
        root, plan_id, existing.project_id
    )
    abs_plan = repo.abs_path(plan_path_r)
    plan = load_plan(abs_plan, root)
    phase = resolve_phase(plan, phase_id)
    change_class = phase_change_class(phase)

    filename_r = approval_filename(plan.id, phase.id)
    approval_id = filename_r.removesuffix(".yaml")
    approval_pending_file = f"memory/working/approvals/pending/{filename_r}"
    approval_resolved_file = f"memory/working/approvals/resolved/{filename_r}"
    operations_log_path = f"memory/working/projects/{resolved_project_id}/operations.jsonl"
    files_res = [
        plan_path_r,
        approval_pending_file,
        approval_resolved_file,
        _project_summary_path(resolved_project_id),
        "memory/working/projects/SUMMARY.md",
        operations_log_path,
        approvals_summary_path(),
    ]

    resolved_status = "approved" if resolution == "approve" else "rejected"
    resulting_plan_status = "active" if resolution == "approve" else "blocked"
    normalized_comment = comment.strip() if comment and comment.strip() else None
    commit_msg_res = (
        f"[plan] {'Approve' if resolution == 'approve' else 'Reject'} {plan.id}:{phase.id}"
    )
    result_res: dict[str, Any] = {
        "approval_id": approval_id,
        "approval_file": approval_resolved_file,
        "plan_id": plan.id,
        "project_id": resolved_project_id,
        "phase_id": phase.id,
        "status": resolved_status,
        "plan_status": resulting_plan_status,
        "resolution": resolution,
        "comment": normalized_comment,
        "message": (
            "Approval recorded; the plan can resume."
            if resolution == "approve"
            else "Approval rejected; the plan remains blocked until work is revised or re-requested."
        ),
    }
    preview_payload = _create_preview(
        mode="preview" if preview else "apply",
        change_class=change_class,
        summary=f"Resolve approval {approval_id} with decision {resolution}.",
        reasoning=(
            "Approval resolution moves the queue entry into the resolved archive and updates the "
            "plan status so subsequent execution respects the human decision."
        ),
        target_files=[
            (plan_path_r, "update"),
            (approval_pending_file, "delete"),
            (approval_resolved_file, "create"),
            (_project_summary_path(resolved_project_id), "update"),
            ("memory/working/projects/SUMMARY.md", "update"),
            (operations_log_path, "append"),
            (approvals_summary_path(), "update"),
        ],
        invariant_effects=[
            "Moves the approval request from pending to resolved with reviewer metadata.",
            "Returns the plan to active status on approval or blocked status on rejection.",
            "Records the decision in the project operations log and refreshes approval navigation.",
        ],
        commit_message=commit_msg_res,
        resulting_state=result_res,
        warnings=warnings,
    )
    if preview:
        return MemoryWriteResult(
            files_changed=files_res,
            commit_sha=None,
            commit_message=None,
            new_state=result_res,
            warnings=warnings,
            preview=preview_payload,
        ).to_dict()

    existing.resolution = resolution
    existing.reviewer = "user"
    existing.resolved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing.comment = normalized_comment
    existing.status = resolved_status

    from ...plan_utils import _find_approvals_root

    approvals_root = _find_approvals_root(root)
    pending_path_r = approvals_root / "pending" / filename_r
    (approvals_root / "resolved").mkdir(parents=True, exist_ok=True)
    save_approval(root, existing)
    if pending_path_r.exists():
        pending_path_r.unlink()

    plan.status = resulting_plan_status

    regenerate_approvals_summary(root)
    save_plan(abs_plan, plan, root)
    repo.add(plan_path_r)
    if repo.is_tracked(approval_pending_file):
        repo.add(approval_pending_file)
    repo.add(approval_resolved_file)
    repo.add(approvals_summary_path())

    resolution_event = "approved" if resolution == "approve" else "rejected"
    _append_plan_log(
        root,
        repo,
        resolved_project_id,
        files_res,
        session_id=None,
        action=f"approval-{resolution_event}",
        plan_id=plan.id,
        phase_id=phase.id,
        detail=normalized_comment or "",
    )
    _sync_project_navigation(root, repo, resolved_project_id, files_res)
    record_trace(
        root,
        None,
        span_type="plan_action",
        name=f"approval-{resolution_event}",
        status="ok",
        metadata={"plan_id": plan.id, "phase_id": phase.id, "resolution": resolution},
    )
    commit_result_res = repo.commit(commit_msg_res)
    return MemoryWriteResult.from_commit(
        files_changed=files_res,
        commit_result=commit_result_res,
        commit_message=commit_msg_res,
        new_state=result_res,
        warnings=warnings,
        preview=preview_payload,
    ).to_dict()


def _append_plan_log(
    root: Path,
    repo,
    project_id: str,
    files_changed: list[str],
    *,
    session_id: str | None,
    action: str,
    plan_id: str,
    phase_id: str | None = None,
    commit: str | None = None,
    detail: str = "",
) -> None:
    log_path, _ = append_operations_log(
        root,
        project_id,
        session_id=session_id,
        action=action,
        plan_id=plan_id,
        phase_id=phase_id,
        commit=commit,
        detail=detail,
    )
    repo.add(log_path)
    if log_path not in files_changed:
        files_changed.append(log_path)


def _render_outbox_summary(
    existing: str, project_id: str, plan_id: str, artifacts: list[str]
) -> str:
    heading = f"## {project_id}"
    lines = existing.splitlines()
    entry_lines = [
        f"### {plan_id}",
        f"- Exported artifacts: {len(artifacts)}",
        f"- Outbox folder: memory/working/projects/OUT/{project_id}/{plan_id}",
    ]
    entry_lines.extend(f"- Artifact: {artifact}" for artifact in artifacts)

    if heading not in existing:
        updated = existing.rstrip() + "\n\n" + heading + "\n\n" + "\n".join(entry_lines) + "\n"
        return updated

    section_start = lines.index(heading)
    next_heading = len(lines)
    for index in range(section_start + 1, len(lines)):
        if lines[index].startswith("## "):
            next_heading = index
            break
    section = lines[section_start:next_heading]
    filtered: list[str] = []
    skip = False
    for line in section:
        if line == f"### {plan_id}":
            skip = True
            continue
        if skip and line.startswith("### "):
            skip = False
        if not skip:
            filtered.append(line)
    replacement = filtered + ([""] if filtered and filtered[-1] else []) + entry_lines
    merged = lines[:section_start] + replacement + lines[next_heading:]
    return "\n".join(merged).rstrip() + "\n"


def register_tools(mcp: "FastMCP", get_repo, get_root) -> dict[str, object]:
    """Register plan-oriented semantic tools."""

    @mcp.tool(
        name="memory_plan_create",
        annotations=_tool_annotations(
            title="Create Structured Plan",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_plan_create(
        plan_id: str,
        project_id: str,
        purpose_summary: str,
        purpose_context: str,
        phases: list[dict[str, Any]],
        session_id: str,
        questions: list[str] | None = None,
        budget: dict[str, Any] | None = None,
        status: str = "active",
        preview: bool = False,
    ) -> str:
        """Create a structured YAML plan file inside a project.

        Required top-level fields:
        - plan_id, project_id: kebab-case slugs
        - purpose_summary, purpose_context: non-empty strings
        - phases: non-empty list of phase mappings
        - session_id: canonical memory/activity/YYYY/MM/DD/chat-NNN id

        Each phase requires id, title, and changes. Optional phase fields:
        - status: "pending" | "blocked" | "in-progress" | "completed" | "skipped"
        - blockers: list[str]
        - sources: list of {path, type, intent, uri?, mcp_server?, mcp_tool?, mcp_arguments?}
          type: "internal" | "external" | "mcp"
          uri: required when type="external"
          mcp_server + mcp_tool: required when type="mcp"
        - postconditions: list of strings (shorthand manual checks) or
          {description, type?, target?}
          type: "check" | "grep" | "test" | "manual" (default "manual")
          check: file exists
          grep: regex::path match
          test: allowlisted command behind ENGRAM_TIER2=1
          target: required when type != "manual"
        - requires_approval: bool
        - failures: list of {timestamp, reason, verification_results?, attempt?}

        changes is a non-empty list of {path, action, description} where action is
        "create" | "rewrite" | "update" | "delete" | "rename".

        budget is an optional dict with keys: deadline (YYYY-MM-DD),
        max_sessions (int >= 1), advisory (bool, default true).

        preview=True returns the standard preview for valid input. Invalid preview
        calls return structured validation feedback without writing; use
        memory_plan_schema to inspect the nested contract programmatically.
        """
        repo = get_repo()
        root = get_root()
        result = create_plan_write_result(
            repo=repo,
            root=root,
            plan_id=plan_id,
            project_id=project_id,
            purpose_summary=purpose_summary,
            purpose_context=purpose_context,
            phases=phases,
            session_id=session_id,
            questions=questions,
            budget=budget,
            status=status,
            preview=preview,
        )
        return result.to_json()

    @mcp.tool(
        name="memory_plan_execute",
        annotations=_tool_annotations(
            title="Execute Structured Plan",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_plan_execute(
        plan_id: str,
        project_id: str | None = None,
        phase_id: str | None = None,
        action: str = "inspect",
        session_id: str | None = None,
        commit_sha: str | None = None,
        review: dict[str, Any] | None = None,
        verify: bool = False,
        reason: str | None = None,
        verification_results: list[dict[str, Any]] | None = None,
        preview: bool = False,
    ) -> str:
        """Inspect, start, complete, or record failure on a plan phase.

            action must be one of "inspect", "start", "complete", or
                    "record_failure". "blocked" is a plan state set automatically when
                    unresolved blockers or rejected approvals prevent progress; it is not a
                    caller-selectable action.

                    Conditional requirements:
                    - session_id is required for start, complete, and record_failure, but
                        not inspect
                    - commit_sha is required when action="complete"
                    - reason is required when action="record_failure"
                    - review is only consumed when the final phase completes

                    The caller-facing review object supports:
            - outcome: "completed" | "partial" | "abandoned" (default "completed")
            - purpose_assessment: non-empty string
            - unresolved: optional list of {question, note}
            - follow_up: optional kebab-case follow-up plan id

            verification_results is an optional list of verification result objects
            attached to failure records or returned by verify flows. Tool-generated
            items carry:
            - postcondition: original postcondition description
            - type: "check" | "grep" | "test" | "manual"
            - status: "pass" | "fail" | "error" | "skip"
            - detail: optional diagnostic string or null
            - policy_result: optional policy block details for denied test commands

            When action="complete" and verify=True, postconditions are evaluated
            before completion. If any fail or error, the phase stays in-progress and
        the verification payload is returned instead. preview=True returns the
        governed preview envelope for the requested state transition without
        mutating the plan or approval state.

            Use memory_tool_schema or memory_plan_schema for the machine-readable
            contract.
        """
        payload = execute_plan_action_result(
            repo=get_repo(),
            root=get_root(),
            plan_id=plan_id,
            project_id=project_id,
            phase_id=phase_id,
            action=action,
            session_id=session_id,
            commit_sha=commit_sha,
            review=review,
            verify=verify,
            reason=reason,
            verification_results=verification_results,
            preview=preview,
        )
        return json.dumps(payload, indent=2)

    @mcp.tool(
        name="memory_plan_review",
        annotations=_tool_annotations(
            title="Review Completed Plan Outputs",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_plan_review(
        project_id: str,
        plan_id: str | None = None,
        artifact_paths: list[str] | None = None,
        session_id: str | None = None,
        preview: bool = False,
    ) -> str:
        """List completed plans or export selected artifacts to the project outbox.

        When plan_id is omitted, the tool returns a read-only list of completed
        plans for the project. When plan_id is supplied, session_id becomes
        required and artifact_paths must be a subset of the plan's exportable
        outputs. Call memory_tool_schema with tool_name="memory_plan_review"
        for the full list-versus-export contract.
        """
        from ...errors import ValidationError
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()
        project_slug = validate_slug(project_id, field_name="project_id")

        project_plans_dir = root / "memory" / "working" / "projects" / project_slug / "plans"
        if plan_id is None:
            completed: list[dict[str, Any]] = []
            if project_plans_dir.is_dir():
                for plan_file in sorted(project_plans_dir.glob("*.yaml")):
                    plan = load_plan(plan_file, root)
                    if plan.status != "completed":
                        continue
                    completed.append(
                        {
                            "plan_id": plan.id,
                            "title": plan_title(plan),
                            "status": plan.status,
                            "exportable_artifacts": exportable_artifacts(root, plan),
                            "outbox_root": project_outbox_root(project_slug, plan.id),
                        }
                    )
            return json.dumps(
                {
                    "project_id": project_slug,
                    "completed_plans": completed,
                    "outbox_summary": outbox_summary_path(),
                },
                indent=2,
            )

        if session_id is None:
            raise ValidationError("session_id is required when exporting reviewed artifacts")
        validate_session_id(session_id)

        plan_path, resolved_project_id = _resolve_existing_plan_path(root, plan_id, project_slug)
        abs_plan = repo.abs_path(plan_path)
        plan = load_plan(abs_plan, root)
        if plan.status != "completed":
            raise ValidationError(f"Plan '{plan.id}' must be completed before review/export")

        candidates = exportable_artifacts(root, plan)
        selected = list(dict.fromkeys(artifact_paths or candidates))
        if not selected:
            raise ValidationError(f"Plan '{plan.id}' has no exportable artifacts")
        if any(path not in candidates for path in selected):
            invalid = [path for path in selected if path not in candidates]
            raise ValidationError(
                "artifact_paths must be a subset of the plan's existing outputs: "
                + ", ".join(invalid)
            )

        out_root = project_outbox_root(resolved_project_id, plan.id)
        outbox_summary = outbox_summary_path()
        files_changed = [
            outbox_summary,
            f"memory/working/projects/{resolved_project_id}/operations.jsonl",
        ]
        export_targets: list[tuple[str, str]] = []
        for artifact in selected:
            dest = f"{out_root}/artifacts/{artifact}"
            export_targets.append((dest, "create"))
            files_changed.append(dest)

        new_state = {
            "plan_id": plan.id,
            "project_id": resolved_project_id,
            "outbox_root": out_root,
            "exported_artifacts": selected,
        }
        commit_msg = f"[plan] Review exports for {plan.id}"
        preview_payload = _create_preview(
            mode="preview" if preview else "apply",
            change_class="proposed",
            summary=f"Export reviewed outputs from completed plan {plan.id} to the project outbox.",
            reasoning=(
                "Plan review promotes selected completed artifacts into the OUT workflow so human review "
                "and downstream reuse can happen without scanning the project tree manually."
            ),
            target_files=export_targets
            + [
                (outbox_summary, "update"),
                (f"memory/working/projects/{resolved_project_id}/operations.jsonl", "append"),
            ],
            invariant_effects=[
                "Copies selected completed-plan artifacts into the project outbox.",
                "Refreshes the OUT summary so exported work is discoverable.",
                "Logs the export event in the project operations log.",
            ],
            commit_message=commit_msg,
            resulting_state=new_state,
            warnings=[],
        )
        if preview:
            return MemoryWriteResult(
                files_changed=files_changed,
                commit_sha=None,
                commit_message=None,
                new_state=new_state,
                warnings=[],
                preview=preview_payload,
            ).to_json()

        for artifact in selected:
            source_abs = root / artifact
            dest_rel = f"{out_root}/artifacts/{artifact}"
            dest_abs = root / dest_rel
            dest_abs.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_abs, dest_abs)
            repo.add(dest_rel)

        abs_summary = root / outbox_summary
        existing_summary = (
            abs_summary.read_text(encoding="utf-8")
            if abs_summary.exists()
            else "# Projects Outbox\n"
        )
        updated_summary = _render_outbox_summary(
            existing_summary, resolved_project_id, plan.id, selected
        )
        abs_summary.parent.mkdir(parents=True, exist_ok=True)
        abs_summary.write_text(updated_summary, encoding="utf-8")
        repo.add(outbox_summary)

        _append_plan_log(
            root,
            repo,
            resolved_project_id,
            files_changed,
            session_id=session_id,
            action="plan-exported",
            plan_id=plan.id,
            detail=f"Exported {len(selected)} artifacts to OUT",
        )
        commit_result = repo.commit(commit_msg)
        return MemoryWriteResult.from_commit(
            files_changed=files_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=new_state,
            warnings=[],
            preview=preview_payload,
        ).to_json()

    @mcp.tool(
        name="memory_list_plans",
        annotations=_tool_annotations(
            title="List Plans",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_list_plans(
        status: str | None = None,
        project_id: str | None = None,
    ) -> str:
        """List YAML plans with phase-level progress and next actions.

        status is an exact plan-status filter and project_id narrows the scan
        to one project slug. Call memory_tool_schema with
        tool_name="memory_list_plans" for the machine-readable filter contract.
        """
        import json as _json

        root = get_root()
        plans: list[dict[str, Any]] = []
        projects_root = root / "memory" / "working" / "projects"
        if not projects_root.is_dir():
            return _json.dumps(plans, indent=2)

        project_glob = (
            f"{validate_slug(project_id, field_name='project_id')}/plans/*.yaml"
            if project_id is not None
            else "*/plans/*.yaml"
        )
        for plan_file in sorted(projects_root.glob(project_glob)):
            if not plan_file.is_file():
                continue
            plan = load_plan(plan_file, root)
            if status is not None and plan.status != status:
                continue
            done, total = plan_progress(plan)
            entry: dict[str, Any] = {
                "plan_id": plan.id,
                "project_id": plan.project,
                "path": plan_file.relative_to(root).as_posix(),
                "title": plan_title(plan),
                "status": plan.status,
                "next_action": next_action(plan),
                "created": plan.created,
                "phase_progress": {"done": done, "total": total},
            }
            bs = budget_status(plan)
            if bs is not None:
                entry["budget_status"] = bs
            plans.append(entry)

        return _json.dumps(plans, indent=2)

    @mcp.tool(
        name="memory_plan_verify",
        annotations=_tool_annotations(
            title="Verify Plan Postconditions",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_plan_verify(
        plan_id: str,
        phase_id: str,
        project_id: str | None = None,
    ) -> str:
        """Evaluate postconditions on a plan phase without modifying plan state.

        Returns structured pass/fail/skip/error results for each postcondition.
        Manual postconditions are skipped. check/grep/test types are evaluated
        automatically. test-type evaluation requires ENGRAM_TIER2=1. Call
        memory_tool_schema with tool_name="memory_plan_verify" for the
        plan/phase/project lookup contract.
        """
        import json as _json

        root = get_root()

        plan_path, resolved_project_id = _resolve_existing_plan_path(root, plan_id, project_id)
        abs_plan = root / plan_path
        plan = load_plan(abs_plan, root)
        phase = resolve_phase(plan, phase_id)
        verification = verify_postconditions(plan, phase, root)
        verification["plan_id"] = plan.id
        verification["project_id"] = resolved_project_id
        verification["phase_id"] = phase.id

        return _json.dumps(verification, indent=2)

    @mcp.tool(
        name="memory_record_trace",
        annotations=_tool_annotations(
            title="Record Trace Span",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_record_trace(
        session_id: str,
        span_type: str,
        name: str,
        status: str,
        duration_ms: int | None = None,
        metadata: dict | None = None,
        cost: dict | None = None,
        parent_span_id: str | None = None,
    ) -> str:
        """Append a trace span to the session's TRACES.jsonl file.

        Spans are append-only and do not modify plan state.  Recording is
        non-blocking — the tool returns a failed status rather than raising if
        writing fails for any reason.

        metadata is sanitized before write: credential-like keys are redacted,
        long strings are truncated, deeply nested objects are stringified, and
        oversized payloads are reduced to top-level scalar fields.
        cost is optional usage metadata; tool-generated spans typically use
        {tokens_in, tokens_out} from estimate_cost(). Use memory_tool_schema
        for the machine-readable contract.

        span_type must be one of: tool_call, plan_action, retrieval,
        verification, guardrail_check.
        status must be one of: ok, error, denied.
        """
        import json as _json

        from ...errors import ValidationError

        validate_session_id(session_id)

        if span_type not in TRACE_SPAN_TYPES:
            raise ValidationError(
                f"span_type must be one of {sorted(TRACE_SPAN_TYPES)}: {span_type!r}"
            )
        if status not in TRACE_STATUSES:
            raise ValidationError(f"status must be one of {sorted(TRACE_STATUSES)}: {status!r}")

        root = get_root()
        span_id = record_trace(
            root,
            session_id,
            span_type=span_type,
            name=name,
            status=status,
            duration_ms=duration_ms,
            metadata=metadata,
            cost=cost,
            parent_span_id=parent_span_id,
        )

        result = {
            "span_id": span_id,
            "trace_file": trace_file_path(session_id),
            "status": "recorded" if span_id else "failed",
        }
        return _json.dumps(result, indent=2)

    @mcp.tool(
        name="memory_query_traces",
        annotations=_tool_annotations(
            title="Query Trace Spans",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_query_traces(
        session_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        span_type: str | None = None,
        plan_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> str:
        """Query trace spans from TRACES.jsonl files.

        Filter by session_id (exact match), date range (YYYY-MM-DD), span_type,
        plan_id (matched against metadata.plan_id), or status.  Returns spans
        newest-first up to ``limit``, plus aggregates: total_duration_ms,
        by_type counts, by_status counts, error_rate. Call memory_tool_schema
        with tool_name="memory_query_traces" for the filter contract.
        """
        import json as _json
        import re as _re

        from ...errors import ValidationError

        if span_type is not None and span_type not in TRACE_SPAN_TYPES:
            raise ValidationError(
                f"span_type must be one of {sorted(TRACE_SPAN_TYPES)}: {span_type!r}"
            )
        if status is not None and status not in TRACE_STATUSES:
            raise ValidationError(f"status must be one of {sorted(TRACE_STATUSES)}: {status!r}")

        _date_pat = _re.compile(r"^\d{4}-\d{2}-\d{2}$")
        if date_from is not None and not _date_pat.match(date_from):
            raise ValidationError("date_from must be in YYYY-MM-DD format")
        if date_to is not None and not _date_pat.match(date_to):
            raise ValidationError("date_to must be in YYYY-MM-DD format")

        root = get_root()
        activity_root = root / "memory" / "activity"
        trace_files: list[Any] = []

        if session_id is not None:
            validate_session_id(session_id)
            candidate = root / trace_file_path(session_id)
            if candidate.exists():
                trace_files = [candidate]
        else:
            if activity_root.is_dir():
                for tf in sorted(activity_root.rglob("*.traces.jsonl"), reverse=True):
                    parts = tf.relative_to(activity_root).parts
                    if len(parts) >= 4:
                        year, month, day = parts[0], parts[1], parts[2]
                        file_date = f"{year}-{month}-{day}"
                        if date_from is not None and file_date < date_from:
                            continue
                        if date_to is not None and file_date > date_to:
                            continue
                    trace_files.append(tf)

        all_spans: list[dict[str, Any]] = []
        for tf in trace_files:
            try:
                for raw_line in tf.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        span = _json.loads(line)
                        if not isinstance(span, dict):
                            continue
                        if span_type is not None and span.get("span_type") != span_type:
                            continue
                        if status is not None and span.get("status") != status:
                            continue
                        if plan_id is not None:
                            meta = span.get("metadata") or {}
                            if meta.get("plan_id") != plan_id:
                                continue
                        all_spans.append(span)
                    except (_json.JSONDecodeError, KeyError):
                        continue
            except OSError:
                continue

        all_spans.sort(key=lambda s: s.get("timestamp", ""), reverse=True)
        total_matched = len(all_spans)
        limited_spans = all_spans[: max(1, limit)]

        total_duration_ms = sum(s.get("duration_ms") or 0 for s in all_spans)
        total_tokens_in = 0
        total_tokens_out = 0
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        error_count = 0
        for span in all_spans:
            st = span.get("span_type", "unknown")
            by_type[st] = by_type.get(st, 0) + 1
            ss = span.get("status", "unknown")
            by_status[ss] = by_status.get(ss, 0) + 1
            if ss == "error":
                error_count += 1
            span_cost = span.get("cost")
            if isinstance(span_cost, dict):
                total_tokens_in += int(span_cost.get("tokens_in", 0))
                total_tokens_out += int(span_cost.get("tokens_out", 0))

        result: dict[str, Any] = {
            "spans": limited_spans,
            "total_matched": total_matched,
            "aggregates": {
                "total_duration_ms": total_duration_ms,
                "total_cost": {
                    "tokens_in": total_tokens_in,
                    "tokens_out": total_tokens_out,
                },
                "by_type": by_type,
                "by_status": by_status,
                "error_rate": round(error_count / total_matched, 3) if total_matched > 0 else 0.0,
            },
        }

        return _json.dumps(result, indent=2)

    @mcp.tool(
        name="memory_plan_briefing",
        annotations=_tool_annotations(
            title="Read Plan Briefing",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_plan_briefing(
        plan_id: str,
        phase_id: str | None = None,
        project_id: str | None = None,
        max_context_chars: int = 8000,
        include_sources: bool = True,
        include_traces: bool = True,
        include_approval: bool = True,
    ) -> str:
        """Return a single-call briefing packet for a plan phase.

        phase_id is optional and defaults to the next actionable phase.
        max_context_chars must coerce to an integer >= 0. Call
        memory_tool_schema with tool_name="memory_plan_briefing" for the full
        briefing contract.
        """
        import json as _json
        import os as _os

        from ...errors import ValidationError

        if isinstance(include_sources, str):
            include_sources = include_sources.lower() not in {"", "0", "false", "no"}
        if isinstance(include_traces, str):
            include_traces = include_traces.lower() not in {"", "0", "false", "no"}
        if isinstance(include_approval, str):
            include_approval = include_approval.lower() not in {"", "0", "false", "no"}

        try:
            max_chars = int(max_context_chars)
        except (TypeError, ValueError) as exc:
            raise ValidationError("max_context_chars must be an integer >= 0") from exc
        if max_chars < 0:
            raise ValidationError("max_context_chars must be >= 0")

        root = get_root()
        plan_path, resolved_project_id = _resolve_existing_plan_path(root, plan_id, project_id)
        abs_plan = root / plan_path
        plan = load_plan(abs_plan, root)

        env_session_id = _os.environ.get("MEMORY_SESSION_ID", "").strip() or None
        if env_session_id is not None:
            validate_session_id(env_session_id)

        if phase_id is None:
            directive = next_action(plan)
            if directive is None:
                result: dict[str, Any] = {
                    "plan_id": plan.id,
                    "project_id": resolved_project_id,
                    "plan_status": plan.status,
                    "purpose": plan.purpose.to_dict(),
                    "progress": {
                        "done": plan_progress(plan)[0],
                        "total": plan_progress(plan)[1],
                        "next_action": None,
                    },
                    "phase": None,
                    "message": "Plan has no actionable phase.",
                }
                plan_budget = budget_status(plan)
                if plan_budget is not None:
                    result["budget_status"] = plan_budget
                return _json.dumps(result, indent=2)
            phase = resolve_phase(plan, str(directive["id"]))
        else:
            phase = resolve_phase(plan, phase_id)

        result = assemble_briefing(
            plan,
            phase,
            root,
            max_context_chars=max_chars,
            include_sources=bool(include_sources),
            include_traces=bool(include_traces),
            include_approval=bool(include_approval),
            session_id=env_session_id,
        )

        return _json.dumps(result, indent=2)

    @mcp.tool(
        name="memory_plan_resume",
        annotations=_tool_annotations(
            title="Resume Plan Execution",
            readOnlyHint=True,
            idempotentHint=True,
        ),
    )
    async def memory_plan_resume(
        plan_id: str,
        session_id: str,
        project_id: str | None = None,
        max_context_chars: int = 8000,
    ) -> str:
        """Load run state and assemble minimal restart context for resuming a plan.

        Returns the current resumption point (phase, task, outputs, errors) plus
        a phase briefing. Degrades gracefully when no run state exists. Call
        memory_tool_schema with tool_name="memory_plan_resume" for the
        machine-readable contract.
        """
        import json as _json

        from ...errors import ValidationError

        try:
            max_chars = int(max_context_chars)
        except (TypeError, ValueError) as exc:
            raise ValidationError("max_context_chars must be an integer >= 0") from exc
        if max_chars < 0:
            raise ValidationError("max_context_chars must be >= 0")

        validate_session_id(session_id)
        root = get_root()
        plan_path, resolved_project_id = _resolve_existing_plan_path(root, plan_id, project_id)
        abs_plan = root / plan_path
        plan = load_plan(abs_plan, root)

        rs = load_run_state(root, plan.project, plan.id)
        has_run_state = rs is not None
        resume_warnings: list[str] = []

        resumption: dict[str, Any]
        intermediate_outputs: list[dict[str, Any]] = []

        if rs is not None:
            plan_warnings = validate_run_state_against_plan(rs, plan)
            resume_warnings.extend(plan_warnings)
            staleness_warning = check_run_state_staleness(rs, session_id)
            if staleness_warning:
                resume_warnings.append(staleness_warning)

            resumption = {
                "current_phase_id": rs.current_phase_id,
                "current_task": rs.current_task,
                "next_action_hint": rs.next_action_hint,
                "error_context": (None if rs.error_context is None else rs.error_context.to_dict()),
                "sessions_consumed": rs.sessions_consumed,
                "last_checkpoint": rs.last_checkpoint,
                "previous_session": rs.session_id,
            }

            target_phase_id = rs.current_phase_id
            if target_phase_id and target_phase_id in rs.phase_states:
                intermediate_outputs = rs.phase_states[target_phase_id].intermediate_outputs
        else:
            nxt = next_action(plan)
            resumption = {
                "current_phase_id": nxt["id"] if nxt else None,
                "current_task": None,
                "next_action_hint": nxt["title"] if nxt else None,
                "error_context": None,
                "sessions_consumed": plan.sessions_used,
                "last_checkpoint": None,
                "previous_session": None,
            }

        target_phase_id = resumption["current_phase_id"]
        phase_briefing: dict[str, Any] | None = None
        if target_phase_id is not None:
            phase = resolve_phase(plan, target_phase_id)
            phase_briefing = assemble_briefing(
                plan,
                phase,
                root,
                max_context_chars=max_chars,
                session_id=session_id,
            )

        result: dict[str, Any] = {
            "plan_id": plan.id,
            "project_id": resolved_project_id,
            "plan_status": plan.status,
            "resumption": resumption,
            "phase_briefing": phase_briefing,
            "intermediate_outputs": intermediate_outputs,
            "warnings": resume_warnings,
            "has_run_state": has_run_state,
        }
        bs = budget_status(plan)
        if bs is not None:
            result["budget_status"] = bs

        return _json.dumps(result, indent=2)

    @mcp.tool(
        name="memory_stage_external",
        annotations=_tool_annotations(
            title="Stage External Content",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_stage_external(
        project: str,
        filename: str,
        content: str,
        source_url: str,
        fetched_date: str,
        source_label: str,
        dry_run: bool = False,
    ) -> str:
        """Stage external content into a project's IN/ directory.

        content must be non-empty, fetched_date must be YYYY-MM-DD, and dry_run
        returns the staging envelope without writing files. Call
        memory_tool_schema with tool_name="memory_stage_external" for the full
        input contract.
        """
        import json as _json
        import os as _os

        root = get_root()
        env_session_id = _os.environ.get("MEMORY_SESSION_ID", "").strip() or None
        result = stage_external_file(
            project,
            filename,
            content,
            source_url,
            fetched_date,
            source_label,
            root=root,
            session_id=env_session_id,
            dry_run=bool(dry_run),
        )
        if env_session_id is not None:
            record_trace(
                root,
                env_session_id,
                span_type="tool_call",
                name="memory_stage_external",
                status="ok",
                metadata={
                    "project_id": result.get("project"),
                    "target_path": result.get("target_path"),
                    "dry_run": bool(dry_run),
                    "staged": result.get("staged", False),
                },
            )
        return _json.dumps(result, indent=2)

    @mcp.tool(
        name="memory_scan_drop_zone",
        annotations=_tool_annotations(
            title="Scan Drop Zone",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_scan_drop_zone(project_filter: str | None = None) -> str:
        """Scan configured watch folders and stage newly discovered content.

        project_filter optionally restricts the scan to one configured project
        slug. When MEMORY_SESSION_ID is set, the runtime also records a
        tool_call trace for the scan. Call memory_tool_schema with
        tool_name="memory_scan_drop_zone" for the input contract.
        """
        import json as _json
        import os as _os

        root = get_root()
        env_session_id = _os.environ.get("MEMORY_SESSION_ID", "").strip() or None
        result = scan_drop_zone(root=root, project_filter=project_filter, session_id=env_session_id)
        if env_session_id is not None:
            record_trace(
                root,
                env_session_id,
                span_type="tool_call",
                name="memory_scan_drop_zone",
                status="ok",
                metadata={
                    "project_filter": project_filter,
                    "staged_count": result.get("staged_count", 0),
                    "duplicate_count": result.get("duplicate_count", 0),
                    "error_count": result.get("error_count", 0),
                },
            )
        return _json.dumps(result, indent=2)

    @mcp.tool(
        name="memory_run_eval",
        annotations=_tool_annotations(
            title="Run Eval Scenarios",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_run_eval(
        session_id: str,
        scenario_id: str | None = None,
        tag: str | None = None,
    ) -> str:
        """Run offline eval scenarios and record compact summary spans.

        Scenarios are loaded from memory/skills/eval-scenarios/. Execution is
        isolated in temporary directories; only eval summary spans are recorded
        back into the live session trace.

        Requires ENGRAM_TIER2=1 because scenarios may invoke verification on
        test-type postconditions. Call memory_tool_schema with
        tool_name="memory_run_eval" for the filter and environment contract.
        """
        import json as _json
        import os as _os
        import tempfile as _tempfile

        from ...errors import NotFoundError, ValidationError
        from ...eval_utils import (
            aggregate_results,
            run_suite,
            scenario_result_trace_metadata,
            select_scenarios,
        )

        validate_session_id(session_id)
        if _os.environ.get("ENGRAM_TIER2", "").strip().lower() not in {"1", "true", "yes", "on"}:
            raise ValidationError("memory_run_eval requires ENGRAM_TIER2=1")

        root = get_root()
        scenarios = select_scenarios(root, scenario_id=scenario_id, tag=tag)
        if not scenarios:
            target = (
                f"scenario_id={scenario_id!r}"
                if scenario_id
                else f"tag={tag!r}"
                if tag
                else "all scenarios"
            )
            raise NotFoundError(f"No eval scenarios matched {target}")

        with _tempfile.TemporaryDirectory(prefix="engram-eval-") as tmp:
            results = run_suite(scenarios, Path(tmp), session_id)

        aggregated = aggregate_results(results)
        for scenario_result in results:
            record_trace(
                root,
                session_id,
                span_type="verification",
                name=f"eval:{scenario_result.scenario_id}",
                status="ok" if scenario_result.status == "pass" else "error",
                metadata=scenario_result_trace_metadata(scenario_result),
            )

        payload: dict[str, Any] = {
            "results": [result.to_dict() for result in results],
            "summary": aggregated["summary"],
            "metrics": aggregated["metrics"],
        }
        if scenario_id is not None:
            payload["scenario_id"] = scenario_id
        if tag is not None:
            payload["tag"] = tag
        return _json.dumps(payload, indent=2)

    @mcp.tool(
        name="memory_eval_report",
        annotations=_tool_annotations(
            title="Read Eval Report",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_eval_report(
        date_from: str | None = None,
        date_to: str | None = None,
        scenario_id: str | None = None,
    ) -> str:
        """Return historical eval runs and aggregate trends from trace spans.

        date_from and date_to, when provided, must be YYYY-MM-DD. Call
        memory_tool_schema with tool_name="memory_eval_report" for the report
        filter contract.
        """
        import json as _json
        import re as _re

        from ...errors import ValidationError
        from ...eval_utils import build_eval_report

        _date_pat = _re.compile(r"^\d{4}-\d{2}-\d{2}$")
        if date_from is not None and not _date_pat.match(date_from):
            raise ValidationError("date_from must be in YYYY-MM-DD format")
        if date_to is not None and not _date_pat.match(date_to):
            raise ValidationError("date_to must be in YYYY-MM-DD format")

        root = get_root()
        result = build_eval_report(
            root,
            date_from=date_from,
            date_to=date_to,
            scenario_id=scenario_id,
        )
        if scenario_id is not None:
            result["scenario_id"] = scenario_id
        return _json.dumps(result, indent=2)

    # ── Approval workflow MCP tools ──────────────────────────────────────────

    @mcp.tool(
        name="memory_request_approval",
        annotations=_tool_annotations(
            title="Request Plan Approval",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_request_approval(
        plan_id: str,
        phase_id: str,
        project_id: str | None = None,
        context: str | None = None,
        expires_days: int = 7,
    ) -> str:
        """Request human approval for a plan phase.

        Creates a pending approval document in ``working/approvals/pending/`` and
        transitions the plan status to ``paused``.  If an approval already exists for
        this phase and is still pending, returns the existing document without creating
        a duplicate.

        project_id is optional and only needed when plan ids are ambiguous across
        projects. context adds freeform reviewer context to the approval document.
        expires_days is a positive number of days before the pending approval expires
        (default 7). The phase must currently be pending or in-progress.

        Returns JSON with ``approval_file``, ``status``, ``expires``,
        and ``plan_status``.
        """
        import json as _json
        from datetime import datetime, timedelta, timezone

        from ...errors import ValidationError as _VE
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()

        plan_path_r, resolved_project_id = _resolve_existing_plan_path(root, plan_id, project_id)
        abs_plan = repo.abs_path(plan_path_r)
        plan = load_plan(abs_plan, root)
        phase = resolve_phase(plan, phase_id)

        if phase.status not in {"pending", "in-progress"}:
            raise _VE(
                f"Phase '{phase.id}' must be pending or in-progress to request approval "
                f"(current status: {phase.status!r})"
            )

        # Check for existing pending approval
        existing = load_approval(root, plan.id, phase.id)
        if existing is not None and existing.status == "pending":
            return _json.dumps(
                {
                    "approval_file": (
                        f"memory/working/approvals/pending/{approval_filename(plan.id, phase.id)}"
                    ),
                    "status": "pending",
                    "expires": existing.expires,
                    "plan_status": plan.status,
                    "message": "Approval already pending; returning existing document.",
                },
                indent=2,
            )
        approval_filename_rel = approval_filename(plan.id, phase.id)
        approval_file_req = f"memory/working/approvals/pending/{approval_filename_rel}"
        files_req = [
            plan_path_r,
            approval_file_req,
            _project_summary_path(resolved_project_id),
            "memory/working/projects/SUMMARY.md",
            f"memory/working/projects/{resolved_project_id}/operations.jsonl",
            approvals_summary_path(),
        ]
        if existing is not None and existing.status == "expired":
            files_req.append(f"memory/working/approvals/resolved/{approval_filename_rel}")

        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            days = max(1, int(expires_days))
        except (TypeError, ValueError):
            days = 7
        expires_str = (now_dt + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        change_class_val = phase_change_class(phase)
        bs_ctx = budget_status(plan)
        approval_context: dict[str, Any] = {
            "phase_title": phase.title,
            "phase_summary": (
                f"Phase '{phase.id}' requires human approval before execution. "
                f"Sources: {len(phase.sources)}, Changes: {len(phase.changes)}"
            ),
            "sources": [s.path for s in phase.sources],
            "changes": [c.to_dict() for c in phase.changes],
            "change_class": change_class_val,
        }
        if bs_ctx is not None:
            approval_context["budget_status"] = bs_ctx
        if context:
            approval_context["additional_context"] = context.strip()

        new_approval = ApprovalDocument(
            plan_id=plan.id,
            phase_id=phase.id,
            project_id=resolved_project_id,
            status="pending",
            requested=now_str,
            expires=expires_str,
            context=approval_context,
        )
        plan.status = "paused"
        if existing is not None and existing.status == "expired":
            materialize_expired_approval(root, existing)
        save_approval(root, new_approval)
        regenerate_approvals_summary(root)
        save_plan(abs_plan, plan, root)
        repo.add(plan_path_r)
        repo.add(approval_file_req)
        if existing is not None and existing.status == "expired":
            repo.add(f"memory/working/approvals/resolved/{approval_filename_rel}")
        repo.add(approvals_summary_path())
        _append_plan_log(
            root,
            repo,
            resolved_project_id,
            files_req,
            session_id=None,
            action="approval-requested",
            plan_id=plan.id,
            phase_id=phase.id,
            detail=f"Expires {expires_str}",
        )
        _sync_project_navigation(root, repo, resolved_project_id, files_req)
        record_trace(
            root,
            None,
            span_type="plan_action",
            name="approval-requested",
            status="ok",
            metadata={"plan_id": plan.id, "phase_id": phase.id, "expires": expires_str},
        )
        commit_msg_req = f"[plan] Request approval {plan.id}:{phase.id}"
        commit_result_req = repo.commit(commit_msg_req)
        result_req: dict[str, Any] = {
            "approval_file": (
                f"memory/working/approvals/pending/{approval_filename(plan.id, phase.id)}"
            ),
            "status": "pending",
            "expires": expires_str,
            "plan_status": "paused",
        }
        return MemoryWriteResult.from_commit(
            files_changed=files_req,
            commit_result=commit_result_req,
            commit_message=commit_msg_req,
            new_state=result_req,
            warnings=[],
        ).to_json()

    @mcp.tool(
        name="memory_resolve_approval",
        annotations=_tool_annotations(
            title="Resolve Plan Approval",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_resolve_approval(
        plan_id: str,
        phase_id: str,
        resolution: str,
        comment: str | None = None,
    ) -> str:
        """Resolve a pending approval request (approve or reject).

        Moves the approval document from ``pending/`` to ``resolved/`` and updates
        the plan status: ``active`` on approval, ``blocked`` on rejection.

        ``resolution`` must be ``"approve"`` or ``"reject"``.
        ``comment`` is an optional reviewer note stored on the resolved
        approval document.

        Returns JSON with ``approval_file``, ``status``, ``plan_status``, and
        the resolved ``phase_id``.
        """
        repo = get_repo()
        root = get_root()
        payload = resolve_approval_action_result(
            repo=repo,
            root=root,
            plan_id=plan_id,
            phase_id=phase_id,
            resolution=resolution,
            comment=comment,
        )
        return json.dumps(payload, indent=2)

    # ── Tool Registry MCP tools ──────────────────────────────────────────────

    @mcp.tool(
        name="memory_register_tool",
        annotations=_tool_annotations(
            title="Register External Tool",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def memory_register_tool(
        name: str,
        description: str,
        provider: str,
        approval_required: bool = False,
        cost_tier: str = "free",
        schema: dict[str, Any] | None = None,
        rate_limit: str | None = None,
        timeout_seconds: int = 30,
        tags: list[str] | None = None,
        notes: str | None = None,
        preview: bool = False,
        approval_token: str | None = None,
    ) -> str:
        """Register or update an external tool definition in the tool registry.

        Creates a new entry if the tool name is unknown for this provider, or
        replaces the existing entry if it already exists. SUMMARY.md is
        regenerated after every call.

        schema stores optional provider-specific parameter metadata and must be
        a JSON object when supplied. Use memory_tool_schema for the
        machine-readable contract.

        Returns JSON with ``tool_name``, ``provider``, ``registry_file``,
        and ``action`` ("created" or "updated").
        """
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()
        # MCP framework may pass booleans as strings
        if isinstance(approval_required, str):
            approval_required = approval_required.lower() not in {"false", "0", "no", ""}
        try:
            timeout_int = int(timeout_seconds)
        except (TypeError, ValueError):
            timeout_int = 30

        tool = ToolDefinition(
            name=name,
            description=description,
            provider=provider,
            schema=schema if isinstance(schema, dict) else None,
            approval_required=bool(approval_required),
            cost_tier=cost_tier,
            rate_limit=rate_limit,
            timeout_seconds=timeout_int,
            tags=list(tags or []),
            notes=notes,
        )

        existing = load_registry(root, provider)
        action = "created"
        updated: list[ToolDefinition] = []
        for existing_tool in existing:
            if existing_tool.name == tool.name:
                action = "updated"
                updated.append(tool)
            else:
                updated.append(existing_tool)
        if action == "created":
            updated.append(tool)

        registry_path = registry_file_path(provider)
        summary_path = registry_summary_path()
        abs_registry = root / registry_path
        abs_summary = root / summary_path
        commit_msg = (
            f"[skill] {'Update' if action == 'updated' else 'Register'} tool {provider}:{tool.name}"
        )

        result: dict[str, Any] = {
            "tool_name": tool.name,
            "provider": provider,
            "registry_file": registry_path,
            "action": action,
        }
        operation_arguments = {
            "name": name,
            "description": description,
            "provider": provider,
            "approval_required": bool(approval_required),
            "cost_tier": cost_tier,
            "schema": schema if isinstance(schema, dict) else None,
            "rate_limit": rate_limit,
            "timeout_seconds": timeout_int,
            "tags": list(tags or []),
            "notes": notes,
        }
        preview_payload = build_governed_preview(
            mode="preview" if preview else "apply",
            change_class="protected",
            summary=f"{action.title()} tool registry entry for {provider}:{tool.name}.",
            reasoning="Tool registry updates are protected because they shape external-tool policy and live under the governed skills surface.",
            target_files=[
                preview_target(registry_path, "update" if abs_registry.exists() else "create"),
                preview_target(summary_path, "update" if abs_summary.exists() else "create"),
            ],
            invariant_effects=[
                "Writes the provider registry YAML and regenerates the registry summary in one governed change.",
                "Protected apply mode requires the approval_token returned by preview mode.",
            ],
            commit_message=commit_msg,
            resulting_state=result,
        )
        preview_payload, protected_token = attach_approval_requirement(
            preview_payload,
            repo,
            tool_name="memory_register_tool",
            operation_arguments=operation_arguments,
        )

        if preview:
            return MemoryWriteResult(
                files_changed=[registry_path, summary_path],
                commit_sha=None,
                commit_message=None,
                new_state={**result, "approval_token": protected_token},
                preview=preview_payload,
            ).to_json()

        require_approval_token(
            repo,
            tool_name="memory_register_tool",
            operation_arguments=operation_arguments,
            approval_token=approval_token,
        )

        save_registry(root, provider, updated)
        regenerate_registry_summary(root)
        repo.add(registry_path)
        repo.add(summary_path)
        commit_result = repo.commit(commit_msg, paths=[registry_path, summary_path])

        return MemoryWriteResult.from_commit(
            files_changed=[registry_path, summary_path],
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=result,
            preview=preview_payload,
        ).to_json()

    @mcp.tool(
        name="memory_get_tool_policy",
        annotations=_tool_annotations(
            title="Get Tool Policy",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_get_tool_policy(
        tool_name: str | None = None,
        provider: str | None = None,
        tags: list[str] | None = None,
        cost_tier: str | None = None,
    ) -> str:
        """Query the tool registry for matching tool policies.

        At least one filter parameter must be provided. When ``tool_name`` is
        given, returns at most one result. All other filters return all matching
        tools. An empty result is not an error. Call memory_tool_schema with
        tool_name="memory_get_tool_policy" for the filter requirements.

        Returns JSON with ``tools`` (list of tool dicts) and ``count``.
        """
        import json as _json

        from ...errors import ValidationError as _VE

        if not any([tool_name, provider, tags, cost_tier]):
            raise _VE(
                "at least one filter parameter is required: tool_name, provider, tags, or cost_tier"
            )
        if cost_tier is not None and cost_tier not in COST_TIERS:
            raise _VE(f"cost_tier must be one of {sorted(COST_TIERS)}: {cost_tier!r}")

        root = get_root()
        all_tools = _all_registry_tools(root)

        filtered: list[ToolDefinition] = []
        for tool in all_tools:
            if tool_name is not None and tool.name != tool_name:
                continue
            if provider is not None and tool.provider != provider:
                continue
            if cost_tier is not None and tool.cost_tier != cost_tier:
                continue
            if tags is not None:
                tool_tag_set = set(tool.tags)
                if not any(t in tool_tag_set for t in tags):
                    continue
            filtered.append(tool)

        if tool_name is not None:
            filtered = filtered[:1]

        result: dict[str, Any] = {
            "tools": [{"provider": t.provider, **t.to_dict()} for t in filtered],
            "count": len(filtered),
        }
        return _json.dumps(result, indent=2)

    return {
        "memory_plan_create": memory_plan_create,
        "memory_plan_execute": memory_plan_execute,
        "memory_plan_briefing": memory_plan_briefing,
        "memory_stage_external": memory_stage_external,
        "memory_scan_drop_zone": memory_scan_drop_zone,
        "memory_plan_review": memory_plan_review,
        "memory_list_plans": memory_list_plans,
        "memory_plan_verify": memory_plan_verify,
        "memory_run_eval": memory_run_eval,
        "memory_eval_report": memory_eval_report,
        "memory_record_trace": memory_record_trace,
        "memory_query_traces": memory_query_traces,
        "memory_register_tool": memory_register_tool,
        "memory_get_tool_policy": memory_get_tool_policy,
        "memory_request_approval": memory_request_approval,
        "memory_resolve_approval": memory_resolve_approval,
        "memory_plan_resume": memory_plan_resume,
    }


__all__ = [
    "register_tools",
    "create_plan_write_result",
    "execute_plan_action_result",
    "resolve_approval_action_result",
]
