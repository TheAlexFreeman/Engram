---
active_plans: 0
cognitive_mode: implementation
created: 2026-03-26
current_focus: 'All nine harness-expansion phases are complete.'
last_activity: '2026-03-27'
open_questions: 0
origin_session: memory/activity/2026/03/26/chat-001
plans: 9
source: agent-generated
status: completed
trust: medium
type: project
---

# Project: Harness Expansion

## Description
Evolve Engram from a memory-and-governance layer into a minimal agent harness by incrementally extending the plan system with execution affordances. Grounded in the deep research analysis of LLM agent harness best practices (2026-03-26), the project now stands as a completed reference implementation across nine phases.

## Cognitive mode
Implementation complete. All nine phases have been landed, documented, and validated. The harness-expansion project now serves as the reference record for the plan-system extension work.

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

## Inter-plan dependencies
- Phase 3 (`trace-recording-impl`) blocks on Phase 2 (`verify-integration`) so verification spans are traceable.
- Phase 5 (`approval-workflow-design`) blocks on Phases 2 and 3.
- Phase 4 is fully independent.
- Phase 6 is independent once the earlier phases exist.
- Phase 7 depends on Phase 3 traces and benefits from Phase 6 fixtures.
- Phase 8 assembles outputs from all prior phases and degrades gracefully if some data is absent.
- Phase 9 depends on the Phase 1 `SourceSpec.type` vocabulary and benefits from the Phase 5 preview-envelope pattern.

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

## Next Steps
1. Use the Phase 7 eval scenarios, Phase 8 briefing packets, and Phase 9 ingestion affordances as the validation baseline for future harness work.
2. Extend the harness only through new phases or successor projects rather than re-opening the completed Phase 1-9 contracts opportunistically.
3. Revisit cross-phase regression coverage whenever a future change touches plan execution, approval, or external-intake behavior.
