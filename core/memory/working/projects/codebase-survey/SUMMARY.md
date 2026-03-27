---
source: agent-generated
origin_session: manual
created: 2026-03-23
trust: medium
type: project
status: ongoing
cognitive_mode: exploration
open_questions: 3
active_plans: 1
last_activity: 2026-03-26
current_focus: "All 6 survey phases complete. Awaiting human review for promotion from IN/ to knowledge/codebase/."
---

# Project: Codebase Survey

## Description
Build a compact, maintainable knowledge base for the Engram repository so future sessions can answer architecture, data-model, operational, and historical questions without re-reading the entire host repository. This project replaces ad-hoc codebase exploration with a structured, plan-driven survey that produces durable, cross-referenced knowledge files.

## Cognitive mode
Exploration mode means the agent should follow the survey plan phase-by-phase, replacing low-trust template stubs with verified notes grounded in concrete source paths.

## Artifact flow
- IN/knowledge/codebase/: low-trust template stubs being filled by each survey phase
- OUT/: verified summaries and cross-referenced knowledge files ready for promotion to `knowledge/`
- plans/: the survey plan YAML that sequences the work

## Notes
This project is seeded from the `codebase-survey-plan.yaml` template. Each phase targets a specific knowledge file under `IN/knowledge/codebase/`. The skill definition at `skills/codebase-survey.md` governs the workflow. Progress is tracked by advancing phase statuses in the plan YAML and promoting trust levels in the knowledge files. Once a file reaches medium trust, it should be promoted from IN/ to `knowledge/codebase/` via OUT/.
