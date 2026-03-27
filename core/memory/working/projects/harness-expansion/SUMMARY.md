---
active_plans: 0
cognitive_mode: implementation
created: 2026-03-26
current_focus: 'All 5 phases complete. Harness expansion project finished (commit daa3c50).'
last_activity: '2026-03-26'
open_questions: 0
origin_session: memory/activity/2026/03/26/chat-001
plans: 5
source: agent-generated
status: ongoing
trust: medium
type: project
---

# Project: Harness Expansion

## Description
Evolve Engram from a memory-and-governance layer into a minimal agent harness by incrementally extending the plan system with execution affordances. Grounded in the deep research analysis of LLM agent harness best practices (2026-03-26), which identified five expansion phases.

## Cognitive mode
Implementation mode. Phase 1 (schema extensions) is complete. Phases 2–5 have detailed plans and design documents. Each phase begins with reading the design doc and affected source files, then implements changes with postcondition verification.

## Artifact flow
- IN/: design documents for each phase (phase-1 through phase-5)
- plans/: implementation plan YAMLs (one per phase)
- notes in `working/notes/harness-expansion-analysis.md`: the grounding analysis from the deep research report

## Plans

| Plan | Phase | Status | Phases | Budget |
|---|---|---|---|---|
| active-plans-phase-1 | 1: Active Plans | completed | 7/7 | 5/8 sessions |
| verification-phase-2 | 2: Inline Verification | completed | 7/7 | 7/6 sessions |
| observability-phase-3 | 3: Observability | completed | 8/8 | 2/8 sessions |
| tool-registry-phase-4 | 4: External Tool Registry | completed | 7/7 | 1/5 sessions |
| hitl-phase-5 | 5: Structured HITL | completed | 8/8 | 1/8 sessions |

## Inter-plan dependencies
- Phase 3 (`trace-recording-impl`) blocks on Phase 2 (`verify-integration`) — verification spans should be traceable
- Phase 5 (`approval-workflow-design`) blocks on Phase 2 (`verify-integration`) and Phase 3 (`trace-recording-impl`)
- Phase 4 is fully independent — can start in parallel with any other phase

## Phase 1 outcome (completed 2026-03-26)
All four schema extensions are implemented and tested: `SourceSpec`, `PostconditionSpec`, `requires_approval`, and `PlanBudget`. The MCP tool surface (`memory_plan_create`, `memory_plan_execute`) surfaces all new fields. 64 tests pass. Documentation updated in DESIGN.md, MCP.md, and CHANGELOG.md.

## Resolved questions
1. **Sources validated at create time?** Yes — enforced via `save_plan`/`validate_plan_references`.
2. **Postconditions free-text or typed?** Both — bare strings coerce to `manual`; typed specs support `check`/`grep`/`test`/`manual`.
3. **`requires_approval` + change-class interaction?** Composed — `approval_required` is true if either flag is set.
4. **Budget enforced or advisory?** Advisory model now; enforced budgets deferred to a future harness phase.

## Phase 2 outcome (completed 2026-03-26)
All four verification extensions implemented: `memory_plan_verify` tool (check/grep/test/manual validators), `verify=true` parameter on `memory_plan_execute` complete action (blocking), `PhaseFailure` dataclass + `record_failure` action, and retry context in `phase_payload`/`next_action`. 7 sessions used (1 over budget). Documentation updated in DESIGN.md, MCP.md, CHANGELOG.md.

## Phase 4 outcome (completed 2026-03-26)
All 7 sub-phases implemented in a single commit (ce466aa): `ToolDefinition` dataclass, `load_registry`/`save_registry`/`_all_registry_tools`/`regenerate_registry_summary` helpers, `memory_register_tool` and `memory_get_tool_policy` MCP tools, `_resolve_tool_policies` + `phase_payload` integration, seed registry (`shell.yaml` with `pre-commit-run`/`pytest-run`/`ruff-check`), 29 new tests (152 total). Ruff clean. Design decisions: immediate writes (no async approval gate), provider-grouped YAML files, `approval_required` describes invocation policy, `tool_policies` in `phase_payload` uses slug-normalized command matching.

## Phase 3 outcome (completed 2026-03-26)
All 8 observability sub-phases implemented in a single commit (15ca0d8): `TraceSpan` dataclass + `record_trace()` helper, `memory_record_trace` and `memory_query_traces` MCP tools, internal plan instrumentation (create/execute/verify emit spans automatically), `event_type: retrieval` on ACCESS.jsonl entries, `_compute_trace_metrics()` for session summary enrichment, `traces.html` viewer with timeline/waterfall layout, 25 new tests (123 total). Ruff clean. Design decisions: always-on tracing, field-level credential redaction + 200-char string truncation + 2KB metadata cap, retention follows session summaries, trace viewer reads files directly (no server).

## Phase 5 outcome (completed 2026-03-26)
All 8 sub-phases implemented in a single commit (daa3c50): `ApprovalDocument` dataclass + `APPROVAL_STATUSES`/`APPROVAL_RESOLUTIONS` constants, `load_approval()`/`save_approval()`/`regenerate_approvals_summary()` helpers with lazy expiry, `memory_request_approval` and `memory_resolve_approval` MCP tools, `paused` status added to `PLAN_STATUSES`, auto-pause logic in `memory_plan_execute` start action (handles all approval states), paused-plan guard blocking start/complete, `working/approvals/` directory structure, `approvals.html` UI (File System Access API, no server), 38 new tests (190 total). Ruff clean. Design decisions: auto-create on start, 7-day default expiry with lazy evaluation, rejection allows re-request, UI writes directly via File System Access API, `{plan_id}--{phase_id}.yaml` double-dash naming convention.