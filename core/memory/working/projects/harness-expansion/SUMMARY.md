---
active_plans: 6
cognitive_mode: completed
created: 2026-03-26
current_focus: 'All 15 phases complete. Engram evolved from memory layer to full agent harness.'
last_activity: '2026-03-27'
open_questions: 6
origin_session: memory/activity/2026/03/26/chat-001
plans: 15
source: agent-generated
status: completed
trust: medium
type: project
---

# Project: Harness Expansion

## Description
Evolve Engram from a memory-and-governance layer into a full agent harness by incrementally extending the plan system with execution affordances. Grounded in the deep research analysis of LLM agent harness best practices (2026-03-26) and a comprehensive gap analysis (2026-03-27), the project has completed nine foundation phases and has six new phases drafted to close the remaining harness gaps.

## Cognitive mode
Completed. All 15 phases implemented and verified. Phases 1-9 built the foundation (schema, verification, traces, registry, approvals, integration tests, evals, context assembly, external ingestion). Phases 10-15 closed the remaining harness gaps (run state, tool policy enforcement, runtime guardrails, eval hardening, trace enrichment, git reliability).

## Artifact flow
- IN/: design documents for each phase
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
| context-assembly-phase-8 | 8: Context Assembly | completed | 5/5 | 1/5 sessions |
| external-ingestion-phase-9 | 9: External Ingestion | completed | 6/6 | 1/6 sessions |
| run-state-phase-10 | 10: Durable Run State | completed | 7/7 | 1/10 sessions |
| tool-policy-enforcement-phase-11 | 11: Tool Policy Enforcement | completed | 7/7 | 1/8 sessions |
| runtime-guardrails-phase-12 | 12: Runtime Guardrails | completed | 9/9 | 1/8 sessions |
| eval-hardening-phase-13 | 13: Eval Hardening | completed | 6/6 | 1/6 sessions |
| trace-enrichment-phase-14 | 14: Trace Enrichment | completed | 5/5 | 1/5 sessions |
| git-reliability-phase-15 | 15: Git Reliability | completed | 5/5 | 1/3 sessions |

## Inter-plan dependencies

### Phases 1-9 (completed)
- Phase 3 (`trace-recording-impl`) blocks on Phase 2 (`verify-integration`) so verification spans are traceable.
- Phase 5 (`approval-workflow-design`) blocks on Phases 2 and 3.
- Phase 4 is fully independent.
- Phase 6 is independent once the earlier phases exist.
- Phase 7 depends on Phase 3 traces and benefits from Phase 6 fixtures.
- Phase 8 assembles outputs from all prior phases and degrades gracefully if some data is absent.
- Phase 9 depends on the Phase 1 `SourceSpec.type` vocabulary and benefits from the Phase 5 preview-envelope pattern.

### Phases 10-15 (draft)
- **Phase 15 (Git Reliability)** has no dependencies and should be completed first — git reliability is foundational to all other work.
- **Phase 10 (Run State)** builds on Phases 1, 2, 3, 8 (all complete). No blockers.
- **Phase 11 (Tool Policy Enforcement)** builds on Phases 4, 5, 3 (all complete). No blockers. Can run in parallel with Phase 10.
- **Phase 12 (Runtime Guardrails)** benefits from Phase 11's enforcement pattern as a model. Soft dependency.
- **Phase 13 (Eval Hardening)** depends on Phase 7 (complete). New scenario writing benefits from Phases 10-12 being complete, but scenario design can start from the plan specs.
- **Phase 14 (Trace Enrichment)** depends on Phase 3 (complete). Integrating Phase 11/12 trace types can happen incrementally.

### Recommended execution order
```
Phase 15 (Git Reliability)           ← start immediately, short
Phase 10 (Run State)        ┐
Phase 11 (Tool Policy)      ├─────── can run in parallel
Phase 14 (Trace Enrichment) ┘
Phase 12 (Runtime Guardrails)        ← after 11
Phase 13 (Eval Hardening)           ← after 10, 11, 12 for full scenario coverage
```

## Resolved questions
1. **Sources validated at create time?** Yes — enforced via `save_plan` and `validate_plan_references`.
2. **Postconditions free-text or typed?** Both — bare strings coerce to `manual`; typed specs support `check`, `grep`, `test`, and `manual`.
3. **`requires_approval` + change-class interaction?** Composed — `approval_required` is true if either flag is set.
4. **Budget enforced or advisory?** Advisory by default; enforced budgets remain a future option.

## Phase outcomes

### Phase 1 outcome (completed 2026-03-26)
All four schema extensions are implemented and tested: `SourceSpec`, `PostconditionSpec`, `requires_approval`, and `PlanBudget`. The MCP tool surface (`memory_plan_create`, `memory_plan_execute`) surfaces all new fields. Documentation updated in DESIGN.md, MCP.md, and CHANGELOG.md.

### Phase 2 outcome (completed 2026-03-26)
Inline verification, failure recording, and retry context landed via `memory_plan_verify`, `verify=true` completion blocking, `PhaseFailure`, and richer `phase_payload()` / `next_action()` retry state.

### Phase 3 outcome (completed 2026-03-26)
Structured observability landed via `TraceSpan`, `memory_record_trace`, `memory_query_traces`, automatic plan instrumentation, trace-backed session metrics, and the `traces.html` viewer.

### Phase 4 outcome (completed 2026-03-26)
The external tool-registry layer landed with `ToolDefinition`, registry storage helpers, `memory_register_tool`, `memory_get_tool_policy`, and `phase_payload()` policy resolution.

### Phase 5 outcome (completed 2026-03-26)
Structured HITL landed with approval documents, pause/resume lifecycle, `memory_request_approval`, `memory_resolve_approval`, approval summaries, and the `approvals.html` UI.

### Phase 6 outcome (completed 2026-03-27)
Cross-phase integration coverage landed across approval lifecycle, retry escalation, trace fidelity, tool-policy resolution, and regression scenarios.

### Phase 7 outcome (completed 2026-03-27)
Offline evaluation landed with `eval_utils.py`, `memory_run_eval`, `memory_eval_report`, seeded eval scenarios, and trace-backed historical reporting.

### Phase 8 outcome (completed 2026-03-27)
Context assembly landed with `assemble_briefing()` and `memory_plan_briefing`, including budgeted source excerpts, failure summaries, approval state, and recent traces.

### Phase 9 outcome (completed 2026-03-27)
External content ingestion landed with `stage_external_file()`, `scan_drop_zone()`, `memory_stage_external`, `memory_scan_drop_zone`, `SourceSpec` MCP metadata (`mcp_server`, `mcp_tool`, `mcp_arguments`), and `phase_payload()` intake hints (`fetch_directives`, `mcp_calls`). Staged content lands in `projects/{project}/IN/` with enforced `source: external-research`, `trust: low`, sanitized `origin_url`, per-project SHA-256 deduplication, and optional PDF extraction via `pypdf` or `pdfminer.six`.

### Phase 10 outcome (completed 2026-03-27)
Durable run state landed with `RunState` JSON schema, auto-save on plan execution steps, `memory_plan_resume` MCP tool, and `assemble_briefing()` integration.

### Phase 11 outcome (completed 2026-03-27)
Tool policy enforcement landed with `check_tool_policy()`, approval gating, rate limit enforcement, cost tier awareness, and `policy_violation` trace spans.

### Phase 12 outcome (completed 2026-03-27)
Runtime guardrails landed with `GuardPipeline`, four built-in guards (PathGuard, ContentSizeGuard, FrontmatterGuard, TrustBoundaryGuard), and `guardrail_check` trace spans.

### Phase 13 outcome (completed 2026-03-27)
Eval hardening landed with isolated execution, pytest CI runner, result history tracking, regression detection, and four new eval scenarios for phases 10-12.

### Phase 14 outcome (completed 2026-03-27)
Trace enrichment landed with cost estimation, parent-child span chaining, and aggregated cost reporting in `memory_query_traces`.

### Phase 15 outcome (completed 2026-03-27)
Git reliability landed with retry/backoff on transient failures, stale lock cleanup, `health_check()` diagnostics, and `memory_git_health` MCP tool.

## Key Project Documents
- SUMMARY.md: project overview, plan status table, inter-plan dependencies, resolved questions
- IN/phase-1-schema-design.md through IN/phase-9-external-ingestion-design.md: per-phase design records
- plans/: per-phase implementation plans
- operations.jsonl: project operations log

## Root Analysis
File: `core/memory/working/notes/harness-expansion-analysis.md`

The project started from seven identified harness gaps spanning orchestration, tool interfaces, verification loops, evaluation, observability, and HITL. Engram already covered memory/state, governance, and safety; the nine phases filled in the missing execution-layer affordances.

## Recent Activity (2026-03-27)
- Phase 9 completed: external staging helper, drop-zone scan helper, SourceSpec MCP metadata, and phase_payload fetch hints landed with focused helper and MCP integration coverage.
- Docs and capability metadata were updated so the new intake surface is discoverable by MCP hosts and human operators.
- Workflow note: pre-commit hooks use `language: system`, so Ruff results follow the system Python installation rather than the workspace `.venv`; if format checks disagree, reproduce with system `python -m ruff ...`.
- All nine phase plans are now synchronized with implementation status.

## Phase 10-15 summary

### Phase 10: Durable Run State
Introduces a RunState JSON schema persisted per-plan, auto-saved after each plan execution step, enabling checkpoint/resume across sessions without re-deriving progress. Addresses the deep research report's strongest recommendation: "run state is for correctness and resumability; memory is for recall and personalization."

### Phase 11: Tool Policy Enforcement
Makes the Phase 4 tool registry's metadata (approval_required, cost_tier, rate_limits) enforceable at runtime via a check_tool_policy() middleware. Adds automatic approval gating, rate limit enforcement, and policy_violation trace spans.

### Phase 12: Runtime Guardrails
Centralizes scattered validation into a GuardPipeline with pluggable guards: PathGuard (migrated from path_policy.py), FrontmatterGuard, ContentSizeGuard, TrustBoundaryGuard. Runs on every write operation; emits guardrail_check trace spans.

### Phase 13: Eval Hardening
Hardens the Phase 7 eval framework with isolated execution environments (temporary git worktrees), pytest CI integration, result history with regression detection, and new scenarios covering Phases 10-12 features.

### Phase 14: Trace Enrichment
Fills observability gaps: cost field population on trace spans, parent-child span hierarchy for call-tree reconstruction, aggregate metrics dashboard for periodic reviews, and integration with Phase 11/12 trace types.

### Phase 15: Git Reliability
Addresses the immediate review queue item (stale HEAD.lock in FUSE environments) and adds broader resilience: retry with exponential backoff, filesystem health diagnostics. Prioritized first because git reliability is foundational.

## Next Steps
1. Activate Phase 15 (Git Reliability) first — it's short, has no dependencies, and unblocks all other work.
2. Activate Phases 10, 11, and 14 in parallel — they have no inter-dependencies and cover the three biggest harness gaps.
3. Activate Phase 12 after Phase 11 establishes the enforcement pattern.
4. Activate Phase 13 last — it validates all other phases and benefits from having Phases 10-12 complete.
5. Extend the harness only through new phases rather than re-opening completed contracts.
6. Revisit cross-phase regression coverage whenever a future change touches plan execution, approval, or external-intake behavior.
