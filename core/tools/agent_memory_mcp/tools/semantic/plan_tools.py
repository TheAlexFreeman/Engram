"""Project plan-oriented semantic tools."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ...path_policy import validate_session_id, validate_slug
from ...plan_utils import (
    TRACE_SPAN_TYPES,
    TRACE_STATUSES,
    PlanDocument,
    PlanPurpose,
    append_operations_log,
    budget_status,
    build_review_from_input,
    coerce_budget_input,
    coerce_phase_inputs,
    exportable_artifacts,
    load_plan,
    next_action,
    outbox_summary_path,
    phase_change_class,
    phase_payload,
    plan_progress,
    plan_title,
    project_outbox_root,
    project_plan_path,
    record_trace,
    resolve_phase,
    save_plan,
    trace_file_path,
    unresolved_blockers,
    verify_postconditions,
)
from ...preview_contract import build_governed_preview, preview_target

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _tool_annotations(**kwargs: object) -> Any:
    return cast(Any, kwargs)


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
    commit_message: str,
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

        Phases may include sources (list of {path, type, intent, uri?}),
        postconditions (list of strings or {description, type?, target?}),
        and requires_approval (bool). These flow through to the plan schema
        and are surfaced in execution directives.

        budget is an optional dict with keys: deadline (YYYY-MM-DD),
        max_sessions (int >= 1), advisory (bool, default true).
        """
        from ...errors import ValidationError
        from ...frontmatter_utils import today_str
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()
        warnings: list[str] = []

        validate_session_id(session_id)
        if status not in {"draft", "active"}:
            raise ValidationError("memory_plan_create status must be 'draft' or 'active'")

        plan_path, resolved_project_id = _resolve_new_plan_path(root, plan_id, project_id)
        coerced_budget = coerce_budget_input(budget)
        plan = PlanDocument(
            id=plan_id,
            project=resolved_project_id,
            created=today_str(),
            origin_session=session_id,
            status=status,
            purpose=PlanPurpose(
                summary=purpose_summary,
                context=purpose_context,
                questions=list(questions or []),
            ),
            phases=coerce_phase_inputs(phases),
            review=None,
            budget=coerced_budget,
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
            ).to_json()

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
        commit_result = repo.commit(commit_msg)
        return MemoryWriteResult.from_commit(
            files_changed=files_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=new_state,
            warnings=warnings,
            preview=preview_payload,
        ).to_json()

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
        """Inspect, start, block, complete, or record failure on a plan phase.

        When action="complete" and verify=True, postconditions are evaluated
        before completion. If any fail or error, the phase stays in-progress
        and verification_results are returned instead.

        When action="record_failure", appends a PhaseFailure to the phase.
        Requires reason (free text). Optional verification_results to attach.
        """
        from ...errors import AlreadyDoneError, ValidationError
        from ...frontmatter_utils import today_str
        from ...models import MemoryWriteResult

        repo = get_repo()
        root = get_root()
        warnings: list[str] = []

        plan_path, resolved_project_id = _resolve_existing_plan_path(root, plan_id, project_id)
        abs_plan = repo.abs_path(plan_path)
        plan = load_plan(abs_plan, root)
        phase = resolve_phase(plan, phase_id)
        blockers = unresolved_blockers(plan, phase, root)
        payload = phase_payload(plan, phase, root)
        payload["unresolved_blockers"] = blockers

        if action == "inspect":
            return json.dumps(payload, indent=2)

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
                ).to_json()

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
            ).to_json()

        if action == "start":
            if phase.status == "completed":
                raise AlreadyDoneError(f"Phase '{phase.id}' is already complete")
            if phase.status == "in-progress":
                raise AlreadyDoneError(f"Phase '{phase.id}' is already in progress")
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
                start_state["sources"] = [s.to_dict() for s in phase.sources]
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
                ).to_json()

            save_plan(abs_plan, plan, root)
            repo.add(plan_path)
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
            )
            commit_result = repo.commit(commit_msg)
            return MemoryWriteResult.from_commit(
                files_changed=files_changed,
                commit_result=commit_result,
                commit_message=commit_msg,
                new_state=start_state,
                warnings=warnings,
                preview=preview_payload,
            ).to_json()

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
                    (
                        _project_summary_path(resolved_project_id),
                        "update",
                    ),
                    ("memory/working/projects/SUMMARY.md", "update"),
                    (
                        f"memory/working/projects/{resolved_project_id}/operations.jsonl",
                        "append",
                    ),
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
                ).to_json()

            save_plan(abs_plan, plan, root)
            repo.add(plan_path)
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
            )
            commit_result = repo.commit(commit_msg)
            return MemoryWriteResult.from_commit(
                files_changed=files_changed,
                commit_result=commit_result,
                commit_message=commit_msg,
                new_state=failure_state,
                warnings=warnings,
                preview=preview_payload,
            ).to_json()

        if not commit_sha or not commit_sha.strip():
            raise ValidationError("commit_sha is required when completing a phase")
        if blockers:
            raise ValidationError(
                f"Phase '{phase.id}' is blocked by unresolved dependencies: "
                + ", ".join(entry["reference"] for entry in blockers)
            )
        if phase.status == "completed":
            raise AlreadyDoneError(f"Phase '{phase.id}' is already complete")

        # Optional inline verification before completing
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
                return json.dumps(verification_state, indent=2)
            # Verification passed — include results in completion response
            warnings.append(
                f"Verification passed: {verification['summary']['passed']} passed, "
                f"{verification['summary']['skipped']} skipped"
            )

        phase.status = "completed"
        phase.commit = commit_sha.strip()
        plan.sessions_used += 1
        done, total = plan_progress(plan)
        all_done = done == total

        # Budget warnings
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
                        "purpose_assessment": "Execution completed; a detailed purpose assessment still needs to be written.",
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
            ).to_json()

        save_plan(abs_plan, plan, root)
        repo.add(plan_path)
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
        )
        commit_result = repo.commit(commit_msg)
        return MemoryWriteResult.from_commit(
            files_changed=files_changed,
            commit_result=commit_result,
            commit_message=commit_msg,
            new_state=completion_state,
            warnings=warnings,
            preview=preview_payload,
        ).to_json()

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
        """Scan completed plans or export selected completed-plan artifacts to the outbox."""
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
        """List YAML plans with phase-level progress and next actions."""
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
        automatically. test-type evaluation requires ENGRAM_TIER2=1.
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

        # Emit a verification span when a session_id is available via env.
        import os as _os

        _env_sid = _os.environ.get("MEMORY_SESSION_ID", "").strip()
        if _env_sid:
            summary = verification.get("summary", {})
            record_trace(
                root,
                _env_sid,
                span_type="verification",
                name=f"verify:{phase.id}",
                status="ok" if verification.get("all_passed") else "error",
                metadata={
                    "plan_id": plan.id,
                    "phase_id": phase.id,
                    "passed": summary.get("passed", 0),
                    "failed": summary.get("failed", 0),
                    "skipped": summary.get("skipped", 0),
                    "errors": summary.get("errors", 0),
                },
            )

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
        by_type counts, by_status counts, error_rate.
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

        result: dict[str, Any] = {
            "spans": limited_spans,
            "total_matched": total_matched,
            "aggregates": {
                "total_duration_ms": total_duration_ms,
                "by_type": by_type,
                "by_status": by_status,
                "error_rate": round(error_count / total_matched, 3) if total_matched > 0 else 0.0,
            },
        }
        return _json.dumps(result, indent=2)

    return {
        "memory_plan_create": memory_plan_create,
        "memory_plan_execute": memory_plan_execute,
        "memory_plan_review": memory_plan_review,
        "memory_list_plans": memory_list_plans,
        "memory_plan_verify": memory_plan_verify,
        "memory_record_trace": memory_record_trace,
        "memory_query_traces": memory_query_traces,
    }


__all__ = ["register_tools"]
