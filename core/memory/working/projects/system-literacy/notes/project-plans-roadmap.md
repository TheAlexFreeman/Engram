---
source: agent-generated
origin_session: memory/activity/2026/03/22/chat-001
created: 2026-03-22
trust: medium
type: design-doc
---

# Project Plans Roadmap

Design document for migrating the Engram project/plan system from prose-based
markdown plans to formally structured YAML plans with tool-enforced lifecycle
management and eidetic activity logging.

This document captures decisions made during the 2026-03-22 brainstorming
session and spells out the migration path from the current system to the target
architecture.


## Context and motivation

The current project system was built during the initial architectural overhaul
(2026-03-21) and introduced project folders, a navigator table, open questions,
and plan files. Plans are markdown documents with YAML frontmatter and checkbox
items parsed positionally by `memory_mark_plan_item_complete`. This served as
scaffolding for the overhaul itself, but it has several limitations as the
system prepares for broader use:

**Plans lack formal structure.** The old `onboarding-redesign/plans/build-plan.md`
was a 17KB narrative document. The tooling parses checkbox items by positional
index (`phase_index`, `item_index`), but has no model of what a phase *is*,
what a file change *is*, or how phases relate to each other. The plan file
conflates design rationale, implementation specification, and progress tracking
into a single prose document.

**No execution workflow.** There is no tool that orchestrates plan execution —
checking blockers, requesting approval for protected writes, tracking which
phase is active, or recording commit hashes when phases complete. The agent
manually marks items complete one by one.

**No export/review workflow.** The `projects/OUT/` outbox exists but has no
tooling. There is no process for reviewing completed project artifacts and
promoting them to the outbox.

**Activity logging is unreliable.** Chat session recording depends on the agent
calling `memory_record_session` at session end — a behavioral convention that
has proven fragile. There is no operations-level audit trail of system mutations
(writes, promotions, governance actions), and no formal connection between
session activity and the plan/phase context that motivated it.

**The cognitive context hierarchy is implicit.** Day-to-day work nests naturally
into sessions → projects → plans → phases → file changes, but the current
system doesn't represent this hierarchy in a way that logging or summarization
pipelines can traverse.


## Design principles

These principles emerged from the brainstorming session and should guide all
implementation decisions:

**Path of least resistance.** The system should make it easiest to do things
the right way. Tool-enforced logging, structured plan schemas, and approval
gates should be built into the MCP tools themselves, not delegated to
behavioral conventions that agents may forget.

**Formality where machines read; prose where humans read.** Plan metadata, phase
structure, blocker references, and change specifications need schema-level
formality because tools operate on them. Purpose descriptions, review
reflections, and change descriptions are prose because their value comes from
contextual judgment.

**Plans are work specifications, not design documents.** A plan file should be a
machine-operable definition of what work to do and why. Design rationale,
research notes, and extended analysis belong in the project's notes or knowledge
files, referenced from the plan's purpose section.

**Projects are open-ended.** Plans provide structure for deliberate work, but
projects should allow unstructured exploration, ad hoc research, and note-taking
outside of any plan. The only constraint is that results stay within the project
folder.


## Plan file schema

Plan files move from markdown (`.md`) to YAML (`.yaml`), stored at
`memory/working/projects/{project-id}/plans/{plan-id}.yaml`.

### Why YAML instead of markdown

Plans are primarily machine-operated: tools create them, track phase status,
check blockers, record commits, and enforce approval gates. Markdown-with-
frontmatter forces either cramming nested structures into frontmatter (unwieldy)
or parsing structure from markdown body conventions (fragile — as the current
checkbox approach demonstrates).

Pure YAML makes the structured parts native data (`yaml.safe_load()` returns
dicts and lists directly) while accommodating prose via block scalar syntax
(`|`), which preserves line breaks and reads naturally. Plan files are the one
place in the system where human editing should be discouraged — the MCP tools
are the primary write path, and YAML reinforces that.

### Schema definition

A plan file has three top-level sections — **Purpose**, **Work**, and
**Review** — plus flat metadata at the root:

```yaml
# ── Metadata ──────────────────────────────────────────────
id: build-plan
project: onboarding-redesign
created: 2026-03-22
origin_session: 2026/03/22/chat-001
status: active          # draft | active | blocked | completed | abandoned

# ── Purpose ───────────────────────────────────────────────
#
# Written at creation. Reviewed by the agent before executing each phase.
# Evaluated against results when the plan completes.
#
purpose:
  summary: >
    One-line description of what this plan accomplishes.
  context: |
    Multi-paragraph prose explaining why this plan exists in the context
    of its project. What questions motivated it, what design constraints
    apply, what prior work it builds on.

    This section is the reference point that the review section evaluates
    against. It should be specific enough that a future agent can judge
    whether the plan accomplished what it set out to do.
  questions: [Q1, Q3]   # references to project question IDs

# ── Work ──────────────────────────────────────────────────
#
# Phases are ordered by array position (implicit linear dependency).
# Use `blockers` only for non-linear dependencies or cross-plan refs.
#
work:
  phases:
    - id: phase-id
      title: Human-readable phase title
      status: pending    # pending | blocked | in-progress | completed | skipped
      commit: null       # SHA populated on completion
      blockers: []       # intra-plan: "phase-id", inter-plan: "plan-id:phase-id"
      changes:
        - path: memory/skills/onboarding/SKILL.md
          action: rewrite  # create | rewrite | update | delete | rename
          description: >
            Prose context for this change — what it does and why.
        - path: governance/first-run.md
          action: update
          description: >
            Adjust silent setup sequence for new interactive phase.

# ── Review ────────────────────────────────────────────────
#
# Null until the plan reaches a terminal status (completed or abandoned).
# Written by the agent at plan completion; evaluates work against purpose.
#
review: null
# When populated:
#   review:
#     completed: 2026-03-25
#     completed_session: 2026/03/25/chat-002
#     outcome: completed     # completed | partial | abandoned
#     purpose_assessment: |
#       Prose reflection on whether and how well the plan accomplished
#       what its purpose section described. References specific questions
#       from purpose.questions and evaluates whether they were answered.
#     unresolved:
#       - question: Q3
#         note: "Read-only export path works but needs more testing."
#     follow_up: null        # plan-id of successor plan, if any
```

### The change spec triad

The lowest-level formal unit is a **change spec**: a `path`/`action`/
`description` triad. `path` and `action` are formally specified (the path must
be a valid repo-relative path, the action must be one of the enum values).
`description` is free-form prose giving context for why this change is needed
and what it should accomplish. This mirrors the system's general pattern of
mixing formality and informality at every level.

Valid actions:

| Action    | Meaning                                           |
|-----------|---------------------------------------------------|
| `create`  | File does not exist; this phase creates it.       |
| `rewrite` | File exists; this phase replaces its content.     |
| `update`  | File exists; this phase modifies part of it.      |
| `delete`  | File exists; this phase removes it.               |
| `rename`  | File exists; this phase moves/renames it.         |

### Phase ordering and dependencies

Phases are ordered by their position in the `work.phases` array. By default,
phase N depends on phase N-1 (implicit linear ordering). The `blockers` field
is only needed to express:

- **Non-linear intra-plan dependencies.** A phase that can start before the
  previous one finishes (empty `blockers` on a non-first phase), or a phase
  that depends on a non-adjacent earlier phase.
- **Inter-plan dependencies.** A phase in this plan that is blocked until a
  phase in another plan completes. Syntax: `"other-plan-id:their-phase-id"`.
  Cross-references must resolve to plans within the same project (no
  inter-project dependencies for now).

### One-off plans

A single-phase plan is the degenerate case — no special handling needed. A
quick "research this question and write findings" plan has one phase with one
or two changes. The schema accommodates this naturally.

### Plan status lifecycle

```
draft → active → completed
                → abandoned
         active → blocked (when a blocker is unsatisfied)
        blocked → active  (when blockers resolve)
```

`draft` is for plans that have been created but not yet approved for execution.
`active` means the plan is ready for work. `blocked` is set automatically when
a phase's blockers include an incomplete phase. `completed` and `abandoned` are
terminal states that trigger review population.


## Three core MCP tools

The project workflow is driven by three path-of-least-resistance tools that
correspond to the three core project operations.

### `memory_plan_create`

Replaces the current `memory_create_plan`. Takes structured input matching the
plan schema and writes a validated `.yaml` file.

**Key behaviors:**
- Validates that `purpose.context` is non-empty (plans must have a reason).
- Validates that all blocker references resolve to existing plans/phases within
  the same project.
- Validates change spec paths and actions.
- Registers the plan in the project's navigation surfaces (project SUMMARY.md
  frontmatter `active_plans` count, navigator table regeneration).
- Logs creation to the operations log with full context (session, project,
  plan ID).
- Change class: `proposed` (requires user awareness before write).

### `memory_plan_execute`

New tool. Manages the phase lifecycle for plan execution.

**Key behaviors:**
- Takes a plan ID and phase ID (or defaults to the next pending phase).
- Checks that all blockers are satisfied (referenced phases have
  `status: completed` and a non-null `commit`).
- Presents the phase's change list to the agent.
- **Reads `purpose.context` and surfaces it** so the agent reviews the plan's
  reason before making changes. This ensures purpose is not just stored at
  creation but actively consulted during execution.
- For changes targeting paths outside `core/memory/`, requires explicit user
  approval before the agent proceeds. This is the approval gate.
- Does NOT make file changes itself — it orchestrates the agent making changes
  using existing write tools. The execute tool is a state machine, not a file
  editor.
- After the agent completes all changes and commits, updates the phase status
  to `completed` and records the commit SHA.
- If all phases are now complete, transitions the plan status to `completed`
  and prompts the agent to populate the `review` section.
- Logs each lifecycle transition to the operations log (blocker check, approval
  request, approval granted, phase started, phase completed, plan completed).
- Change class: varies by phase content. Phases touching only `core/memory/`
  paths are `proposed`; phases touching governance or external paths are
  `protected`.

### `memory_plan_review`

New tool. Manages the export/review workflow for completed project work.

**Key behaviors:**
- Takes a project ID.
- Scans for completed plans whose outputs haven't been exported to
  `projects/OUT/`.
- Presents a summary of exportable artifacts for review.
- On approval, copies or links artifacts to the project's OUT contributions
  and updates `projects/OUT/SUMMARY.md`.
- Logs the export to the operations log.
- Change class: `proposed`.

**Open design question:** What makes content "ready for export"? Current
thinking: plan completion is the trigger, but not all plan outputs are
export-worthy. The review tool should present completed plan outputs and let the
agent (with user input) decide what to export. The plan's `review` section
(particularly `purpose_assessment`) informs this judgment.


## Activity logging integration

The plan formalization enables structured activity logging at every level of
the cognitive context hierarchy.

### Two activity streams

**Stream 1: Session activity log (external).** One markdown file per session
in the existing `activity/YYYY/MM/DD/chat-NNN/` tree. Frontmatter carries
machine-parseable metadata (session_id, actor, timestamp, key_topics). Body
is narrative prose. Records what engagement occurred and what project/governance
work was done.

**Stream 2: Operations log (internal).** JSONL, tool-written, append-only.
Records every system mutation with its cognitive context address:

```jsonl
{"ts":"2026-03-22T14:23:01Z","session":"2026/03/22/chat-003","actor":"agent","trigger":"user-request","action":"phase-complete","project":"onboarding-redesign","plan":"build-plan","phase":"core-rewrite","commit":"abc1234","detail":"3 files changed"}
```

Every operations log entry can be addressed to its position in the
session → project → plan → phase → change hierarchy. This structure
enables hierarchical summarization: file changes roll up into phase outcomes,
phase outcomes into plan progress, plan progress into project status, and
project status feeds the session summary.

### Tool-enforced logging

The three core plan tools (create, execute, review) log their operations as a
side effect of execution, not as a separate step. The operations log append
happens inside the tool implementation, so logging is guaranteed as long as the
tool is used — which the path-of-least-resistance design encourages.

### Consolidation protocol

- **Operations log:** Roll up per-session. Keep raw entries for a configurable
  window (tied to maturity stage thresholds). Beyond that window, archive raw
  entries and retain the aggregated summary.
- **Session activity log:** Summarize at day/month/year cadence per the
  existing curation policy. Leaf-node session entries persist longer than raw
  operations entries.


## Migration plan

### Phase 1: Schema and parser

1. Define the YAML plan schema as a Python dataclass or TypedDict for
   validation.
2. Write a `load_plan` utility that reads `.yaml` plan files and returns
   validated plan objects.
3. Write a `save_plan` utility that serializes plan objects back to `.yaml`
   with consistent field ordering and block scalar formatting.
4. Update `frontmatter_utils.py`: retire `parse_plan_items`,
   `mark_plan_item_complete`, and `_split_into_phases`. These are the
   markdown-checkbox parsing functions that the YAML schema replaces.

### Phase 2: Tool migration

1. Rewrite `memory_create_plan` → `memory_plan_create` to accept structured
   phase/change definitions and write `.yaml` files.
2. Implement `memory_plan_execute` as a new tool in `plan_tools.py`.
3. Implement `memory_plan_review` as a new tool (possibly in a new
   `export_tools.py` or within `plan_tools.py`).
4. Retire `memory_mark_plan_item_complete` (replaced by execute tool's phase
   lifecycle management).
5. Update `memory_update_plan_next_action` or retire it (the plan schema
   tracks active phase implicitly via phase statuses).
6. Update `memory_list_plans` to parse `.yaml` files.

### Phase 3: Operations log infrastructure

1. Define the operations log JSONL schema.
2. Implement append-only logging in the plan tools as a side effect of
   execution.
3. Decide on log file location: per-project
   (`projects/{id}/operations.jsonl`) or centralized
   (`activity/operations.jsonl`). Per-project is more natural for
   project-scoped queries; centralized is simpler for cross-project
   aggregation. Consider both: per-project for the hot path, with a
   centralized index or aggregation step.

### Phase 4: Existing plan migration

1. Convert `onboarding-redesign/plans/build-plan.yaml` to the new YAML
   schema. Move its design narrative to project notes; extract phase structure
   into formal phases.
2. Verify the converted plan round-trips through `load_plan`/`save_plan`.
3. Delete the old `.md` plan file once the `.yaml` replacement is validated.
4. Since this is a single-user system with no backwards compatibility
   requirement, the migration can be done in one pass.

### Phase 5: Navigator and routing updates

1. Update `_sync_project_navigation` to look for `.yaml` plan files in
   addition to (and eventually instead of) `.md` plan files.
2. Update `memory_list_plans` to report phase-level progress from the
   structured schema (e.g., "3/5 phases complete") instead of checkbox counts.
3. Update the project SUMMARY.md frontmatter to include a `plans` count that
   reflects `.yaml` files.

### Phase 6: Session activity log improvements

1. Make `memory_record_session` more reliable by having it pull structured
   context from the operations log (what plans were advanced, what phases
   completed) rather than relying on the agent's end-of-session recall.
2. Add a session activity log template that includes project/plan context
   automatically.
3. Consider whether session recording should be triggered by an MCP tool
   hook rather than a behavioral convention.


## Open questions

1. **Operations log location.** Per-project, centralized, or both? Per-project
   keeps project context local; centralized enables cross-project queries
   without scanning multiple files.

2. **Approval gate UX.** The execute tool needs to request user approval for
   changes outside `core/memory/`. How does this interact with the existing
   `change_classes` and `approval_ux` system in `agent-memory-capabilities.toml`?
   The plan's change specs provide enough information for the preview contract
   (target files, action types, reasoning from the change description).

3. **Draft vs. active.** Should `memory_plan_create` produce plans in `draft`
   status by default (requiring a separate activation step), or `active` status
   (immediately ready for execution)? Draft status adds a deliberate approval
   step; active status reduces friction for simple plans.

4. **Phase granularity.** How granular should phases be? The design says each
   phase corresponds to a commit, but should a phase with 10 file changes
   really be a single commit? Or should the system allow sub-phase commits
   while still treating the phase as the unit of blocker resolution?

5. **Unstructured work tracking.** Projects allow work outside of plans, and
   results stay in the project folder. Should the operations log track
   unstructured writes to project folders (so the session summary captures
   them), or only track plan-driven operations? Tracking everything gives a
   complete audit trail; tracking only plans keeps the log focused.

6. **Review trigger.** When a plan completes, should the review section be
   populated immediately (blocking further work until reflection is done),
   or queued for a later reflection pass? Immediate review captures context
   while it's fresh; deferred review avoids interrupting flow.
