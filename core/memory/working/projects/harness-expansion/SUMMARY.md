---
active_plans: 1
cognitive_mode: implementation
created: 2026-03-26
current_focus: 'Phase 3 active: trace-schema-design in-progress (requires_approval).
  Finalizing opt-in/always-on, metadata sanitization, retention policy decisions.'
last_activity: '2026-03-26'
open_questions: 4
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
| observability-phase-3 | 3: Observability | active | 0/8 | 1/8 sessions |
| tool-registry-phase-4 | 4: External Tool Registry | draft | 0/7 | 0/5 sessions |
| hitl-phase-5 | 5: Structured HITL | draft | 0/8 | 0/8 sessions |

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

## Open questions (Phase 3)
1. Should trace recording be opt-in per session or always-on?
2. How much metadata should be included in spans (balance detail vs size)?
3. Should the trace viewer read files directly or go through MCP tools?
4. What retention policy should apply to trace files?