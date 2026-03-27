---
active_plans: 0
cognitive_mode: exploration
created: 2026-03-26
current_focus: 'Phase 1 complete. Next: Phase 2 (enforced budget, postcondition automation, or agent-loop integration).'
last_activity: '2026-03-26'
open_questions: 0
origin_session: memory/activity/2026/03/26/chat-001
plans: 1
source: agent-generated
status: ongoing
trust: medium
type: project
---

# Project: Harness Expansion

## Description
Evolve Engram from a memory-and-governance layer into a minimal agent harness by incrementally extending the plan system with execution affordances. Grounded in the deep research analysis of LLM agent harness best practices (2026-03-26), which identified five expansion phases. This project covers Phase 1: making plans active — adding research/analysis source declarations, postcondition verification, human approval gates, and execution budgets to the existing plan schema.

## Cognitive mode
Exploration mode. The schema extensions are design-first: each implementation phase begins with reading the affected source files and the harness analysis, then proposes changes for review before committing.

## Artifact flow
- IN/: design documents and schema specifications drafted during this project
- plans/: the implementation plan YAML that sequences the work
- notes in `working/notes/harness-expansion-analysis.md`: the grounding analysis from the deep research report

## Phase 1 outcome (completed 2026-03-26)
All four schema extensions are implemented and tested: `SourceSpec`, `PostconditionSpec`, `requires_approval`, and `PlanBudget`. The MCP tool surface (`memory_plan_create`, `memory_plan_execute`) surfaces all new fields. 64 tests pass. Documentation updated in DESIGN.md, MCP.md, and CHANGELOG.md.

## Resolved questions
1. **Sources validated at create time?** Yes — enforced via `save_plan`/`validate_plan_references`.
2. **Postconditions free-text or typed?** Both — bare strings coerce to `manual`; typed specs support `check`/`grep`/`test`/`manual`.
3. **`requires_approval` + change-class interaction?** Composed — `approval_required` is true if either flag is set.
4. **Budget enforced or advisory?** Advisory model now; enforced budgets deferred to a future harness phase.

## Open questions
_None. All Phase 1 questions resolved._