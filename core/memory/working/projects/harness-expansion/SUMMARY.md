---
active_plans: 0
cognitive_mode: implementation
created: 2026-03-26
current_focus: 'Phases 1-7 are complete; Phases 8-9 remain planned.'
last_activity: '2026-03-27'
open_questions: 0
origin_session: memory/activity/2026/03/26/chat-001
plans: 9
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
| integration-tests-phase-6 | 6: Integration Tests | completed | 6/6 | 2/6 sessions |
| eval-framework-phase-7 | 7: Eval Framework | completed | 7/7 | 3/8 sessions |
| context-assembly-phase-8 | 8: Context Assembly | draft | 0/5 | 0/5 sessions |
| external-ingestion-phase-9 | 9: External Ingestion | draft | 0/6 | 0/6 sessions |

## Inter-plan dependencies
- Phase 3 (`trace-recording-impl`) blocks on Phase 2 (`verify-integration`) — verification spans should be traceable
- Phase 5 (`approval-workflow-design`) blocks on Phase 2 (`verify-integration`) and Phase 3 (`trace-recording-impl`)
- Phase 4 is fully independent — can start in parallel with any other phase
- Phase 6 (integration tests) is independent — all prior phases are complete
- Phase 7 (eval framework) depends on Phase 3 traces; benefits from Phase 6 fixtures but not blocked
- Phase 8 (context assembly) assembles outputs from all prior phases; degrades gracefully if data absent
- Phase 9 (external ingestion) depends on Phase 1 SourceSpec `type` field (external/mcp vocabulary); benefits from Phase 5 preview-envelope pattern; independent of Phases 6-8

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

## Phase 6 outcome (completed 2026-03-27)
Cross-phase integration tests. Design doc: IN/phase-6-integration-tests-design.md. Plan: plans/integration-tests-phase-6.yaml. The shared schema test module now includes the rich lifecycle helpers plus full direct integration classes for approval lifecycle, verify-fail-retry, trace coverage, tool-policy resolution, and cross-cutting regression cases. This batch expanded coverage for approval queue transitions, approval summary regeneration, paused-plan budget visibility, failure serialization round-trips, retry escalation, completion after retry, trace append order, trace metadata sanitization, parent/child span linkage, registry field propagation, unmatched command degradation, expired-approval queue moves, and inter-plan blockers combined with tool policies. Combined with the earlier write-tool E2E tests, `test_plan_schema_extensions.py` now passes at 220 tests and the Phase 6 plan is complete.

## Phase 7 outcome (completed 2026-03-27)
Offline evaluation framework. Design doc: IN/phase-7-eval-framework-design.md. Plan: plans/eval-framework-phase-7.yaml. `eval_utils.py` now provides EvalScenario/EvalStep/EvalAssertion plus StepResult/AssertionResult/ScenarioResult dataclasses, YAML loading/validation, a direct plan-utils runner (`run_scenario` / `run_suite`), standard metrics computation, scenario selection helpers, aggregated reporting, and trace-backed history loading. The semantic tool layer exposes `memory_run_eval` (Tier 2 gated, scenario/tag selection, summary trace emission) and `memory_eval_report` (historical runs and trends from eval trace spans). The seeded suite now lives under `skills/eval-scenarios/` with five scenarios covering lifecycle, verification/retry, trace coverage, tool-registry bootstrap, and approval pause/resume. Documentation and changelog wiring are complete, and the eval test suite now validates the real seeded scenarios end to end.

## Phase 8 outcome (pending)
Context assembly briefing tool. Design doc: IN/phase-8-context-assembly-design.md. Plan: plans/context-assembly-phase-8.yaml. assemble_briefing() helper + memory_plan_briefing MCP tool. Single-call context packet with source file contents, failure summaries, traces, approval status, tool policies, and configurable budget (default ~8000 chars).

## Phase 9 outcome (pending)
External content ingestion affordances. Design doc: IN/phase-9-external-ingestion-design.md. Plan: plans/external-ingestion-phase-9.yaml. Three affordances: (1) memory_stage_external MCP tool — agents call after fetching content externally; stages to projects/{project}/IN/ with auto-generated trust frontmatter (source: external-research, trust: low, origin_url with query strings stripped) and SHA-256 deduplication; (2) fetch_directives and mcp_calls lists added to phase_payload() response for phases with type: external or type: mcp sources that do not yet exist on disk; (3) memory_scan_drop_zone MCP tool — reads [[watch_folders]] entries from agent-bootstrap.toml, bulk-stages new files with dedup, emits scan report with staged/duplicate/error counts. PDF extraction optional via pdfminer.six/pypdf subprocess.
