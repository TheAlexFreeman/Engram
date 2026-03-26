---
active_plans: 1
cognitive_mode: exploration
created: 2026-03-26
current_focus: 'Phase 1 design: extend plan schema with sources, postconditions, approval
  gates, and budgets to support orchestration-lite.'
last_activity: '2026-03-26'
open_questions: 4
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

## Open questions
1. Should `sources` be validated at plan-create time (check that internal paths exist)?
2. Should `postconditions` be free-text or structured (with a validator type field)?
3. How should `requires_approval` interact with the existing change-class system?
4. Should budget fields be enforced by the MCP server or advisory-only?