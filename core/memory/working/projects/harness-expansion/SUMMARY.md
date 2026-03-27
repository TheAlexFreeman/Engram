---
active_plans: 0
cognitive_mode: implementation
created: 2026-03-26
current_focus: 'Phases 2-5 planned. Next: Phase 2 (inline verification) — add memory_plan_verify,
  failure recording, retry-with-context.'
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
| verification-phase-2 | 2: Inline Verification | draft | 0/7 | 0/6 sessions |
| observability-phase-3 | 3: Observability | draft | 0/8 | 0/8 sessions |
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

## Open questions
_None. All Phase 1 questions resolved._