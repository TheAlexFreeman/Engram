---
source: agent-generated
trust: medium
created: 2026-03-26
origin_session: memory/activity/2026/03/26/chat-001
title: "Phase 1 Schema Design: Active Plans"
---

# Phase 1 Schema Design: Active Plans

## Motivation

The deep research report on agent harnesses (2026-03-26) identifies orchestration as the critical gap between Engram's current memory system and a full agent harness. The report's central recommendation: "represent the agent run as steps with saved state; resume without repeating completed work; support human inspection/modification of state."

Engram's plan system already stores phases and tasks with status tracking. The gap is that plans are **passive documents** — they record what should happen but provide no structured affordance for:

1. **What to read before acting.** Agents currently decide ad-hoc which files to read before executing a phase. This means the plan author's knowledge of *which sources matter* is lost between sessions.
2. **What must be true after acting.** There's no way to declare success criteria for a phase beyond "the files in `changes` were modified."
3. **When to pause for human input.** The change-class system (automatic/proposed/protected) determines approval at the *file* level, but some phases need approval at the *decision* level regardless of which files they touch.
4. **When to stop.** Plans have no budget constraints — no max sessions, no deadline, no cost ceiling.

This document specifies four schema extensions that address these gaps.

---

## Extension 1: `sources` — Research before action

### Problem

A phase currently declares only its *outputs* (`changes`). But reliable execution requires *inputs* too — the files, documents, and external references the agent must read and analyze before making changes. Without this:

- Agents in new sessions don't know what the plan author considered important context.
- There's no way to verify the agent actually consulted the right material.
- External information sources (URLs, API docs, upstream repos) have no formal place in the plan.

### Design

Add an optional `sources` list to `PlanPhase`, parallel to `changes`:

```yaml
phases:
  - id: implement-source-spec
    title: Add SourceSpec dataclass to plan_utils.py
    sources:
      - path: core/tools/agent_memory_mcp/plan_utils.py
        type: internal
        intent: Understand current PlanPhase dataclass and serialization patterns.
      - path: core/memory/working/notes/harness-expansion-analysis.md
        type: internal
        intent: Ground the implementation in the gap analysis recommendations.
      - uri: https://spec.modelcontextprotocol.io/specification/2025-03-26/
        type: external
        intent: Check whether MCP spec has conventions for declaring tool input dependencies.
    changes:
      - path: core/tools/agent_memory_mcp/plan_utils.py
        action: update
        description: Add SourceSpec dataclass and sources field to PlanPhase.
```

### Schema

```python
SOURCE_TYPES = {"internal", "external", "mcp"}

@dataclass(slots=True)
class SourceSpec:
    """A source to read/analyze before executing phase changes."""
    path: str       # repo-relative path (internal) or descriptive label (external/mcp)
    type: str       # "internal" | "external" | "mcp"
    intent: str     # Why this source matters for this phase
    uri: str | None = None  # Full URI for external sources

    def __post_init__(self) -> None:
        if self.type not in SOURCE_TYPES:
            raise ValidationError(
                f"source type must be one of {sorted(SOURCE_TYPES)}: {self.type!r}"
            )
        if not isinstance(self.intent, str) or not self.intent.strip():
            raise ValidationError("source intent must be a non-empty string")
        self.intent = self.intent.strip()
        if self.type == "internal":
            self.path = _normalize_repo_relative_path(self.path, field_name="source path")
        elif self.type == "external" and not self.uri:
            raise ValidationError("external sources must include a uri")
```

### Source types

| Type | `path` contains | `uri` contains | When to use |
|---|---|---|---|
| `internal` | Repo-relative file path | (omitted) | Files within the Engram repo that should be read before changes |
| `external` | Human-readable label | Full URL | Web resources, upstream docs, API references |
| `mcp` | MCP tool name or resource URI | (optional) | Data to fetch via MCP tools (e.g., `memory_search`, `memory_access_analytics`) |

### Validation rules

- `internal` sources: validate that the path matches the repo-relative path format (same as `ChangeSpec.path`). **Do not** require the file to exist at plan-create time — the file may be created by an earlier phase.
- `external` sources: require a non-empty `uri`. No reachability check at plan time.
- `mcp` sources: `path` should be a tool name or `memory://` resource URI. No runtime validation at plan time.

### Behavioral contract

When an agent calls `memory_plan_execute` with `action: "start"`, the response's `resulting_state` should include a `sources` array so the agent knows what to read. When the agent calls with `action: "inspect"`, the phase payload should include `sources` alongside `changes`.

**Sources are advisory, not enforced.** The plan system does not verify that the agent actually read the listed sources. Enforcement would require tracing infrastructure (Phase 3 of the harness expansion). For now, sources serve as structured documentation that survives across sessions.

---

## Extension 2: `postconditions` — Verify after action

### Problem

A phase is currently "complete" when the agent says it is and provides a commit SHA. There's no structured way to express *what should be true* after execution, which means:

- Verification is ad-hoc and session-dependent.
- The plan author's success criteria are implicit in the phase title, not machine-inspectable.
- The report's "tool-grounded checkpoints" pattern has no schema support.

### Design

Add an optional `postconditions` list to `PlanPhase`:

```yaml
phases:
  - id: implement-source-spec
    title: Add SourceSpec dataclass to plan_utils.py
    postconditions:
      - "SourceSpec dataclass exists in plan_utils.py with path, type, intent, uri fields"
      - "PlanPhase.sources field serializes to/from YAML correctly"
      - "pre-commit hooks pass (ruff check, ruff format, validate_memory_repo)"
    changes:
      - path: core/tools/agent_memory_mcp/plan_utils.py
        action: update
        description: Add SourceSpec dataclass and sources field to PlanPhase.
```

### Schema

```python
@dataclass(slots=True)
class PlanPhase:
    # ... existing fields ...
    sources: list[SourceSpec] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    requires_approval: bool = False
```

Postconditions are free-text strings for now. A future iteration (Phase 2 of the harness expansion) could introduce typed postconditions with validator references, but that adds complexity without clear near-term value.

### Behavioral contract

- `memory_plan_execute` with `action: "inspect"` includes postconditions in the phase payload.
- `memory_plan_execute` with `action: "complete"` does **not** automatically verify postconditions (no execution engine yet). Instead, it includes them in the response so the calling agent can self-verify.
- A future `memory_plan_verify` tool could check postconditions against repo state.

---

## Extension 3: `requires_approval` — Phase-level approval gates

### Problem

The current change-class system determines approval requirements from file paths: changes to `governance/` or `skills/` are "protected" and need approval. But some phases need human sign-off for *decisional* reasons:

- A phase that chooses between two architectural approaches.
- A phase that deletes or archives significant content.
- A phase that modifies external-facing behavior.

These are approval needs that can't be derived from which files are touched.

### Design

Add an optional `requires_approval` boolean to `PlanPhase` (default: `false`):

```yaml
phases:
  - id: choose-validation-strategy
    title: Decide whether postconditions should be free-text or typed
    requires_approval: true
    sources:
      - path: core/tools/agent_memory_mcp/plan_utils.py
        type: internal
        intent: Assess current validation patterns to inform the decision.
    changes:
      - path: core/memory/working/projects/harness-expansion/IN/phase-1-schema-design.md
        action: update
        description: Record the decision and rationale for postcondition format.
```

### Behavioral contract

- When `requires_approval: true`, `memory_plan_execute` with `action: "start"` returns a response that includes `"approval_required": true` in the resulting state. The agent should present the phase context to the user and wait for confirmation before proceeding.
- This is **additive** to the change-class system. A phase touching `governance/` files is protected regardless of `requires_approval`. The flag adds approval to phases that wouldn't otherwise require it.
- `memory_plan_execute` with `action: "complete"` on an approval-gated phase should require `session_id` to come from an interactive session (not automation), as a lightweight verification that a human was present.

---

## Extension 4: `budget` — Plan-level execution constraints

### Problem

Plans currently have no stopping conditions beyond "all phases complete." The report emphasizes: "always encode explicit stopping conditions (max iterations, time budget, max tool calls)." Without budgets:

- Long-running plans can drift indefinitely.
- There's no way to express "this should be done by Friday" in machine-readable form.
- Cost awareness is entirely absent.

### Design

Add an optional `budget` mapping to `PlanDocument`:

```yaml
id: active-plans-implementation
project: harness-expansion
budget:
  deadline: 2026-04-15
  max_sessions: 8
  advisory: true
# ...
```

### Schema

```python
@dataclass(slots=True)
class PlanBudget:
    deadline: str | None = None      # YYYY-MM-DD
    max_sessions: int | None = None  # session count cap
    advisory: bool = True            # if false, plan_execute refuses to start new phases past budget

    def __post_init__(self) -> None:
        if self.deadline is not None:
            # validate date format
            ...
        if self.max_sessions is not None and self.max_sessions < 1:
            raise ValidationError("max_sessions must be >= 1")
```

### Behavioral contract

- **Advisory mode** (default): `memory_plan_execute` includes budget status in the response (days remaining, sessions used) but does not block execution. The agent and user decide whether to continue.
- **Enforced mode** (`advisory: false`): `memory_plan_execute` with `action: "start"` returns an error if the deadline has passed or session count is exceeded. The plan must be explicitly extended or abandoned.
- Session counting: increment a `sessions_used` counter each time a new `session_id` calls `start` on any phase. Store this in the plan YAML alongside `budget`.

---

## Interaction model: how these extensions compose

A phase execution cycle with all four extensions:

```
1. Agent calls memory_plan_execute(action="inspect")
   → Response includes: sources, changes, postconditions, requires_approval, budget_status

2. Agent reads each source listed in sources[]
   → Internal: memory_read_file or direct file read
   → External: web fetch or documented reference
   → MCP: tool call or resource read

3. If requires_approval: agent presents phase summary to user, waits for confirmation

4. Agent executes the changes

5. Agent self-checks against postconditions[]

6. Agent calls memory_plan_execute(action="complete", commit_sha=...)
   → Plan state advances; budget counters update; next phase sources become available
```

---

## Migration and backward compatibility

All new fields are optional with sensible defaults:
- `sources`: defaults to `[]` (empty list)
- `postconditions`: defaults to `[]` (empty list)
- `requires_approval`: defaults to `false`
- `budget`: defaults to `null` (no budget)

Existing plans load and operate without modification. The `load_plan` function should silently accept plans missing these fields. The `save_plan` function should omit empty/default fields to keep YAML clean.

---

## What this does NOT include (deferred to later phases)

- **Execution engine**: No runtime that automatically sequences phases. The agent still drives the loop.
- **Source verification**: No check that the agent actually read the sources. Requires tracing (Phase 3).
- **Postcondition automation**: No automatic verification. Requires a `memory_plan_verify` tool (Phase 2).
- **Cost tracking**: Budget counts sessions but not tokens or compute cost. Requires observability (Phase 3).
- **Notification**: No mechanism to alert users when approval is needed. Requires HITL workflow (Phase 5).
