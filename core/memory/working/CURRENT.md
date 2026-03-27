# Agent working notes

Provisional, agent-authored. Not formal memory. Each entry is dated and linked to its originating session.

See `core/governance/scratchpad-guidelines.md` for the full write protocol, promotion criteria, and lifecycle rules.

---

## Active threads

- **Harness expansion** — Phases 1 and 2 complete. Phase 3 (Observability) active: `trace-schema-design` phase in-progress (requires_approval). Next step: finalize design decisions and get user approval before implementing `memory_record_trace`, `memory_query_traces`, and trace viewer UI. See `core/memory/working/projects/harness-expansion/plans/observability-phase-3.yaml`.
- **Codebase survey** — All 6 phases complete. All knowledge files at `trust: medium`. Pending human review for promotion from IN/ to `knowledge/codebase/` via OUT/. See `core/memory/working/projects/codebase-survey/plans/survey-plan.yaml`.

## Immediate next actions

- Finalize Phase 3 trace-schema-design: update design doc with decisions on opt-in/always-on, metadata sanitization, retention policy, trace viewer data source. Present for approval.
- After approval: implement trace-recording-impl (memory_record_trace + internal helper).

## Open questions

_None_

## Drill-down refs

- `core/memory/working/projects/SUMMARY.md` when active project context exists.
