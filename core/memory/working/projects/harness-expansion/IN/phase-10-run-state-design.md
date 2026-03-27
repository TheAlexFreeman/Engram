---
source: agent-generated
trust: medium
origin_session: memory/activity/2026/03/27/chat-003
created: 2026-03-27
title: "Phase 10: Run State Design — Schema, Persistence, and Resumption"
---

# Phase 10: Run State Design

## Motivation

The deep research report's strongest recommendation for long-horizon reliability:

> "Run state is for correctness and resumability; memory is for recall and personalization. Mixing them tends to cause state drift."

Currently, plan execution state is distributed across:

- **Plan YAML** — phase status fields (`pending`, `in-progress`, `completed`)
- **Git commits** — phase commit SHAs
- **operations.jsonl** — session/action log entries

When an agent resumes a multi-session plan, it must re-read the entire plan document and infer where it was. There is no explicit checkpoint carrying intermediate outputs, the current task position within a phase, budget consumption, or a resumption hint. This makes resumption fragile and context-expensive.

This design introduces a **RunState** JSON document persisted per-plan, auto-saved after each successful `memory_plan_execute` action, and loadable via a new `memory_plan_resume` tool that assembles minimal restart context.

## Design Constraints

1. **Run state must not duplicate or contradict the plan YAML.** Phase status remains authoritative in the plan file; run state adds execution-level detail.
2. **Run state is additive.** All existing plan execution behavior is unchanged. Run state is a parallel artifact that enhances resumability.
3. **Run state is best-effort.** A missing or corrupted run-state file degrades gracefully — the system falls back to plan-only context (current behavior).
4. **Run state is cheap to read.** It must be a single JSON file loadable in one operation, small enough to include in briefing context.

## RunState JSON Schema

### File location

```
memory/working/projects/{project_id}/plans/{plan_id}.run-state.json
```

Sibling to the plan YAML file. This makes association unambiguous and keeps plan-related artifacts co-located.

### Schema (version 1)

```json
{
  "schema_version": 1,
  "plan_id": "<slug>",
  "project_id": "<slug>",

  "current_phase_id": "<slug> | null",
  "current_task": "<free-text description of position within phase> | null",
  "next_action_hint": "<what the agent should do next> | null",

  "last_checkpoint": "<ISO-8601 UTC timestamp>",
  "session_id": "<session ID of the last write>",
  "sessions_consumed": 0,

  "error_context": null,

  "phase_states": {
    "<phase_id>": {
      "started_at": "<ISO-8601 UTC> | null",
      "completed_at": "<ISO-8601 UTC> | null",
      "task_position": "<free-text> | null",
      "intermediate_outputs": []
    }
  },

  "created_at": "<ISO-8601 UTC>",
  "updated_at": "<ISO-8601 UTC>"
}
```

### Field definitions

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | int | yes | Schema version for forward compatibility. Current: `1`. |
| `plan_id` | string (slug) | yes | Must match the associated plan YAML `id`. |
| `project_id` | string (slug) | yes | Must match the associated plan YAML `project`. |
| `current_phase_id` | string \| null | yes | The phase currently being executed. Null when no phase is active. |
| `current_task` | string \| null | no | Free-text description of position within the current phase (e.g., "reading sources", "implementing changes", "running verification"). |
| `next_action_hint` | string \| null | no | Resumption hint for the next agent. Describes what should happen next. |
| `last_checkpoint` | string (ISO-8601) | yes | Timestamp of the most recent run-state save. |
| `session_id` | string | yes | Session ID of the agent that last wrote this state. |
| `sessions_consumed` | int >= 0 | yes | Number of sessions that have worked on this plan (mirrors `PlanDocument.sessions_used` but tracked independently for cross-validation). |
| `error_context` | object \| null | no | If the last action was a failure, structured error info. |
| `phase_states` | object | yes | Per-phase execution detail, keyed by phase ID. |
| `created_at` | string (ISO-8601) | yes | When this run-state file was first created. |
| `updated_at` | string (ISO-8601) | yes | When this run-state file was last modified. |

### `error_context` schema

```json
{
  "phase_id": "<slug>",
  "message": "<human-readable error description>",
  "timestamp": "<ISO-8601 UTC>",
  "recoverable": true
}
```

Set on `record_failure`; cleared on the next successful `start` or `complete`.

### `phase_states[<id>]` schema

```json
{
  "started_at": "<ISO-8601 UTC> | null",
  "completed_at": "<ISO-8601 UTC> | null",
  "task_position": "<free-text> | null",
  "intermediate_outputs": [
    {
      "key": "<short label>",
      "value": "<content or file reference>",
      "timestamp": "<ISO-8601 UTC>"
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `started_at` | string \| null | When the phase transitioned to `in-progress`. |
| `completed_at` | string \| null | When the phase transitioned to `completed`. |
| `task_position` | string \| null | Free-text cursor within the phase. Updated by the agent as work progresses. |
| `intermediate_outputs` | array | Ordered list of sub-task outputs produced during the phase. |

### `intermediate_outputs[n]` constraints

- `key`: slug-like label (e.g., `source-review`, `impl-summary`, `test-results`).
- `value`: inline content string (preferred) or a `file:` reference (e.g., `file:IN/phase-10-run-state-design.md`) for large outputs.
- **Inline size limit**: 2 KB per entry, 10 KB total per phase.
- **Maximum entries**: 20 per phase. If exceeded, the oldest entries are summarized into a single `summary` entry before new ones are appended.

## Persistence Contract

### When state is saved

Run state is saved to disk (JSON write) after every successful `memory_plan_execute` action:

| Action | Run state update |
|---|---|
| `start` | Set `current_phase_id`, `started_at` in phase_states, clear `error_context`, update `session_id` and `last_checkpoint`. |
| `complete` | Set `completed_at` in phase_states, advance `current_phase_id` to next pending phase (or null), increment `sessions_consumed`, update `last_checkpoint`. |
| `record_failure` | Set `error_context` with failure details, update `last_checkpoint`. |

### Git commit policy

- **On disk**: Run state is written after every action (crash recovery).
- **Git committed**: Only at phase boundaries — when `start` or `complete` actions occur. The run-state file is added to the same commit that updates the plan YAML.
- **Not committed on**: `record_failure` (the failure is already recorded in the plan YAML's failures array; the run-state disk write provides crash recovery until the next boundary commit).

This keeps git history clean while providing on-disk persistence for crash recovery.

### File lifecycle

1. **Created**: On the first `start` action for any phase in the plan.
2. **Updated**: On every subsequent `start`, `complete`, or `record_failure`.
3. **Preserved after plan completion**: The final run state remains as a historical artifact. It is not deleted when the plan completes.
4. **Not created for `inspect`**: Read-only operations do not create or modify run state.

## Relationship to Plan YAML

The separation of concerns:

| Aspect | Authoritative source | Run state role |
|---|---|---|
| Phase status (pending/in-progress/completed) | Plan YAML | Mirrors for convenience; plan YAML wins on conflict |
| Phase commit SHA | Plan YAML | Not stored in run state |
| Failure records | Plan YAML (failures array) | Stores lightweight `error_context` for resumption hint |
| Current task position within phase | Run state | Not available in plan YAML |
| Intermediate outputs | Run state | Not available in plan YAML |
| Next action hint | Run state | `next_action()` in plan YAML provides phase-level; run state provides task-level |
| Session tracking | Both | `sessions_used` in plan YAML is authoritative; `sessions_consumed` in run state is a cross-check |

### Conflict resolution

If run state disagrees with plan YAML (e.g., run state says phase X is current but plan YAML shows it as completed):

1. **Plan YAML wins.** The run state's `current_phase_id` is corrected to match reality.
2. A warning is emitted in the response.
3. The corrected run state is saved.

This can happen if the plan is manually edited or if a session modifies the plan without updating run state (e.g., a session that predates run-state support).

## Concurrency Policy

### Scenario

Two sessions could reference the same plan if:
- An agent session crashes and a new session picks up the plan.
- Two agents in different platforms work on the same plan simultaneously.

### Policy: last-writer-wins with staleness detection

1. On load, check `session_id` and `last_checkpoint` in the existing run state.
2. If `session_id` differs from the current session AND `last_checkpoint` is within the past 60 minutes, emit a **warning**: "Run state was last updated by a different session {session_id} at {last_checkpoint}. Taking over."
3. The current session takes over by updating `session_id`.
4. No file locking. No distributed coordination.

### Rationale

- Engram plans are designed for sequential execution (one phase at a time, with blockers).
- True concurrent execution of the same phase is not supported by the plan schema.
- The staleness window (60 minutes) catches accidental overlap without blocking legitimate handoffs.
- This is consistent with Engram's existing patterns (operations.jsonl is append-only, plan YAML uses last-writer-wins via git).

## Pruning Policy

### Maximum file size

**50 KB**. This keeps run state well within comfortable context-loading bounds (roughly 12K tokens).

### Pruning strategy

When `updated_at` write would push the file past 50 KB:

1. Identify all `phase_states` entries where `completed_at` is set.
2. For each completed phase, replace the full entry with a **summary entry**:
   ```json
   {
     "started_at": "<preserved>",
     "completed_at": "<preserved>",
     "task_position": null,
     "intermediate_outputs": [
       {
         "key": "pruned-summary",
         "value": "<one-line summary of N pruned outputs>",
         "timestamp": "<completed_at>"
       }
     ]
   }
   ```
3. Active phase entries are never pruned.
4. If still over limit after pruning completed phases, truncate `intermediate_outputs` on the active phase (oldest first).

### Projected sizes

- Empty run state: ~300 bytes
- Typical mid-plan (3 phases, moderate outputs): ~3–8 KB
- Large plan (10+ phases, many outputs): ~15–30 KB
- Pruning threshold should rarely be hit in practice.

## `memory_plan_resume` Tool Design

### Purpose

Provide a single-call resumption entry point that loads run state and plan context together, producing a minimal restart packet.

### Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `plan_id` | string | yes | — | Plan to resume. |
| `project_id` | string | no | auto-detect | Project containing the plan. |
| `session_id` | string | yes | — | Current session ID (for staleness check and takeover). |
| `max_context_chars` | int | no | 8000 | Context budget for source content assembly. |

### Return schema

```json
{
  "plan_id": "<slug>",
  "project_id": "<slug>",
  "plan_status": "<status>",
  "resumption": {
    "current_phase_id": "<slug> | null",
    "current_task": "<string> | null",
    "next_action_hint": "<string> | null",
    "error_context": "<object> | null",
    "sessions_consumed": 0,
    "last_checkpoint": "<ISO-8601>",
    "previous_session": "<session_id>"
  },
  "phase_briefing": {
    "...assembled by assemble_briefing()..."
  },
  "intermediate_outputs": [
    {"key": "...", "value": "...", "timestamp": "..."}
  ],
  "warnings": [],
  "has_run_state": true
}
```

### Behavior

1. Load plan YAML.
2. Attempt to load run state. If missing, set `has_run_state: false` and fall back to plan-only context (equivalent to current `memory_plan_briefing`).
3. If run state exists, validate against plan YAML (fix conflicts, emit warnings).
4. Check concurrency (staleness detection).
5. Identify resumption point from run state.
6. Call `assemble_briefing()` for the current phase with source context.
7. Include intermediate outputs from the current phase's run state.
8. Return the assembled packet.

### Annotations

- `readOnlyHint: true` — does not modify plan state (but may update run-state session_id).
- `idempotentHint: true` — safe to call multiple times.

## Integration with `assemble_briefing()`

When run state exists for a plan, `assemble_briefing()` includes an additional `run_state` section in its output:

```json
{
  "...existing briefing fields...",
  "run_state": {
    "current_task": "<string> | null",
    "next_action_hint": "<string> | null",
    "last_checkpoint": "<ISO-8601>",
    "error_context": "<object> | null",
    "intermediate_outputs": [...]
  }
}
```

When no run state exists, the `run_state` field is `null` (graceful degradation).

The run-state section is accounted for in the context budget under a new `run_state` key in `context_budget.breakdown`.

## Implementation Plan

### Dataclass (`plan_utils.py`)

```python
@dataclass(slots=True)
class RunStatePhase:
    started_at: str | None = None
    completed_at: str | None = None
    task_position: str | None = None
    intermediate_outputs: list[dict[str, Any]] = field(default_factory=list)

@dataclass(slots=True)
class RunStateError:
    phase_id: str
    message: str
    timestamp: str
    recoverable: bool = True

@dataclass(slots=True)
class RunState:
    plan_id: str
    project_id: str
    schema_version: int = 1
    current_phase_id: str | None = None
    current_task: str | None = None
    next_action_hint: str | None = None
    last_checkpoint: str = ""
    session_id: str = ""
    sessions_consumed: int = 0
    error_context: RunStateError | None = None
    phase_states: dict[str, RunStatePhase] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
```

### Helper functions (`plan_utils.py`)

- `run_state_path(project_id, plan_id) -> str` — content-relative path.
- `load_run_state(root, project_id, plan_id) -> RunState | None` — load from JSON, return None if missing.
- `save_run_state(root, run_state) -> Path` — validate and write to disk.
- `update_run_state(run_state, action, phase, **kwargs) -> RunState` — apply an action's effects.
- `prune_run_state(run_state) -> RunState` — apply pruning if over size limit.
- `validate_run_state_against_plan(run_state, plan) -> list[str]` — check consistency, return warnings.

### File path function

```python
def run_state_path(project_id: str, plan_id: str) -> str:
    return (
        f"memory/working/projects/{validate_slug(project_id)}"
        f"/plans/{validate_slug(plan_id)}.run-state.json"
    )
```

## Open Questions (Resolved)

### Q: Should run state be committed to git on every update, or only at phase boundaries?

**Decision**: Phase boundaries only (`start` and `complete`). The run-state file is saved to disk on every action for crash recovery, but only added to git commits at phase transitions. This balances durability with git history cleanliness.

### Q: How should run state handle concurrent access?

**Decision**: Last-writer-wins with a 60-minute staleness warning. No file locking. Consistent with Engram's existing append-only and git-based patterns.

### Q: Should intermediate_outputs be stored inline or as file references?

**Decision**: Inline by default (2 KB per entry, 10 KB per phase). `file:` prefix references for larger outputs. This keeps the common case simple while supporting exceptional large outputs.

### Q: What is the maximum reasonable run-state file size before it needs pruning?

**Decision**: 50 KB. Completed phase entries are summarized to reclaim space. Active phases are never pruned.
