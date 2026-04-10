# Skill Trigger Specification

> **Change tier:** Protected  
> **Load:** On-demand — when defining skill behavior, evaluating trigger activations, or implementing skill lifecycle management.

This document specifies how skills are triggered (activated) during agent execution. It defines a trigger event taxonomy, frontmatter schema extensions, matcher syntax, and priority rules for deterministic and auditable skill dispatch.

---

## Background

Currently, skills are discovered through catalog matching — the agent reads the `SKILLS.yaml` manifest and evaluates implicit conditions in skill descriptions and frontmatter. This approach is fragile:

- Conditions are implicit and scattered across files, making them hard to audit.
- Multiple skills may match the same situation, with unclear precedence.
- Skills intended for specific lifecycle events (session start, end, checkpoints) compete with on-demand skills.
- No explicit mechanism for time-based or event-driven triggers.

This specification introduces an explicit **trigger** field in skill frontmatter and manifest entries, allowing skills to declare *when* they should activate and *under what conditions*.

---

## Trigger event taxonomy

The trigger system recognizes eight core events that span the agent's lifecycle:

| Event | When it fires | Example use |
|---|---|---|
| `session-start` | Beginning of a new session (first message from user) | Load context, surface open questions, start checkpoint tracking |
| `session-end` | User ends the session, or context is running low before hard limit | Final checkpoint, write reflection, commit ACCESS logs |
| `session-checkpoint` | Mid-session sync point, either user-requested or automatic | Flush accumulated context, save plan progress, surface opportunities |
| `pre-tool-use` | Before an MCP tool is invoked (before the tool call) | Validate inputs, log tool intent, apply guardrails |
| `post-tool-use` | After an MCP tool completes and returns (success or error) | Validate outputs, update state, trigger follow-on analysis |
| `on-demand` | Explicitly requested by user or agent (`/skill-name`) | Run user-initiated procedures, trace flows, audit systems |
| `periodic` | Time-based interval (daily, weekly, etc.) or agent-driven probe | Periodic review, daily standup, maintenance checks |
| `project-active` | A specific project is active and its conditions are met | Project-specific workflows (codebase survey when project is open) |

---

## Frontmatter schema extension

Every skill SKILL.md file and every entry in `SKILLS.yaml` may include a `trigger` field. The field supports three forms:

### Simple form — event name only

The most common case: a skill activates on a single event with no additional filtering.

```yaml
---
name: session-start
trigger: session-start
---
```

This is shorthand for: "This skill should activate whenever the `session-start` event fires."

### Complex form — event with matcher

For skills that should activate only under specific conditions, provide an object with `event`, `matcher`, and optionally `priority`:

```yaml
---
name: codebase-survey
trigger:
  event: project-active
  matcher:
    project_id: codebase-survey
  priority: 10
---
```

The matcher filters the event. The skill activates only if:
1. The event fires (project becomes active), AND
2. The matcher conditions are satisfied (the project_id matches)

### List form — multiple triggers

A skill may activate on multiple events:

```yaml
---
name: multi-event-skill
trigger:
  - event: session-start
    priority: 5
  - event: session-checkpoint
    matcher:
      condition: context_pressure_high
    priority: 8
---
```

This skill activates on both `session-start` (always) and `session-checkpoint` (only when context pressure is high). Each entry in the list can have its own matcher and priority.

### Backward compatibility

Skills without a `trigger` field continue to work through catalog matching. The trigger system is **additive** — if a skill has no explicit trigger, the agent may infer activation through catalog rules or user request. This allows gradual migration.

---

## Matcher syntax

The `matcher` object filters *when* an event should activate a skill. The matcher succeeds if **all** conditions match (AND semantics).

### Standard matchers

These matchers apply across multiple event types:

| Matcher | Type | Usage | Example |
|---|---|---|---|
| `tool_name` | string or regex | Matches pre/post-tool-use events by tool name | `tool_name: "memory_.*"` activates for any memory tool |
| `tool_name` | string or regex | Matches pre/post-tool-use events by tool name | `tool_name: "memory_read_file"` activates only for that tool |
| `project_id` | string | Matches project-active events by project slug | `project_id: "codebase-survey"` |
| `condition` | string | Matches custom system predicates | `condition: "first_session"` |
| `interval` | string | For periodic triggers: cron expression or duration | `interval: "0 9 * * *"` (daily at 9am) or `"7 days"` |

### Custom conditions

The `condition` matcher accepts predefined system conditions that the agent can evaluate:

| Condition | When true | Use case |
|---|---|---|
| `first_session` | This is the user's first session (no activity/ folder) | Trigger onboarding |
| `returning_session` | Session history exists | Load home context |
| `context_pressure_high` | Token usage is >75% of model limit | Trigger checkpoint flush |
| `context_pressure_critical` | Token usage is >90% of model limit | Trigger emergency session-end |
| `periodic_review_due` | 30+ days since last review in `core/INIT.md` | Trigger governance audit |
| `has_open_plans` | Projects exist with status ≠ completed/skipped | Trigger plan-specific workflows |
| `project_has_questions` | Active project has open questions | Surface questions at session start |
| `trust_audit_overdue` | Trust decay audit not run this session | Trigger security check |

Additional custom conditions may be defined in `core/governance/skill-trigger-conditions.md` (to be created as needed).

### Matcher combination rules

- Matchers **AND** together (all must match for the skill to activate)
- Omitting a matcher means "match any value for this dimension"
- If a matcher is not applicable to the event (e.g., `tool_name` on `session-start`), the matcher is skipped (treated as always true for that dimension)

**Examples:**

```yaml
# Activate on session-start for returning users only
trigger:
  event: session-start
  matcher:
    condition: returning_session

# Activate on post-tool-use only for memory-write tools
trigger:
  event: post-tool-use
  matcher:
    tool_name: "memory_.*"

# Activate on project-active only for a specific project, high priority
trigger:
  event: project-active
  matcher:
    project_id: "codebase-survey"
  priority: 15
```

---

## Priority rules

When multiple skills have triggers that match the same event, priority determines dispatch order and which skill runs.

### Priority tiers (highest first)

1. **Explicit trigger** (skill has a `trigger` field) — beats catalog match
2. **Custom matcher match** (trigger with non-empty `matcher`) — beats simple event-only trigger
3. **Catalog match** (skill discovered via manifest without trigger) — lowest priority

**Within a tier,** use the numeric `priority` field:

- Higher number wins (e.g., priority 10 runs before priority 5)
- Default priority is 0
- Trust level is the final tiebreaker: `high` > `medium` > `low`

### Dispatch algorithm

```
When event E fires:
  candidates = all skills with trigger.event == E
  candidates += all skills matched by catalog (implicit)
  
  for each candidate:
    if trigger.event and matcher do not match:
      skip this candidate
  
  sort candidates by:
    1. tier (explicit trigger > catalog match)
    2. priority (descending)
    3. trust level (high > medium > low)
  
  run the first candidate
  (or, for session-lifecycle events, run the top N in order per policy)
```

**Special case — session lifecycle:** On `session-start`, `session-checkpoint`, and `session-end`, **all matching skills may run** (in priority order) rather than just the first one. This allows multiple contextual setup/teardown flows. For other events, the highest-priority match runs.

---

## Built-in skill triggers

These are the core system skills and their recommended trigger configurations:

| Skill | Event | Matcher | Priority | Trust | Rationale |
|---|---|---|---|---|---|
| `onboarding` | `session-start` | `condition: first_session` | 100 | high | Must run before any returning logic |
| `session-start` | `session-start` | `condition: returning_session` | 50 | high | Load context for returning users |
| `session-checkpoint` | `session-checkpoint` | none | 50 | high | Mid-session sync point |
| `session-wrapup` | `session-end` | none | 50 | high | Final checkpoint and reflection |
| `codebase-survey` | `project-active` | `project_id: codebase-survey` | 30 | medium | Activate survey project |
| `flow-trace` | `on-demand` | none | 0 | low | Manual invocation only |

---

## Integration with SKILLS.yaml manifest

The `SKILLS.yaml` manifest may also specify triggers at the catalog level:

```yaml
skills:
  - id: session-start
    name: session-start
    file: core/memory/skills/session-start/SKILL.md
    trigger:
      event: session-start
      matcher:
        condition: returning_session
      priority: 50
    
  - id: on-demand-audit
    name: on-demand-audit
    file: core/memory/skills/audit/SKILL.md
    trigger:
      event: on-demand
      priority: 0
```

When a skill appears in both the SKILL.md frontmatter and SKILLS.yaml, the frontmatter takes precedence. The manifest entry serves as a fallback and discovery aid.

---

## Event lifecycle reference

### Session startup (`session-start` event)

Fires once at the very beginning of the session, after the agent has read `core/INIT.md`.

**Matching skills run in priority order:**
1. `onboarding` (if first_session)
2. `session-start` (if returning_session)
3. Any project-specific startup hooks

**Order matters:** onboarding must complete before home context is loaded.

### Mid-session checkpoint (`session-checkpoint` event)

Fires when:
- User explicitly types `/checkpoint` or "checkpoint"
- Agent detects context pressure > 75% and proactively suggests a flush
- 10+ minutes have passed since the last checkpoint in a long session (optional, configurable)

**All matching skills run in priority order** (additive, not exclusive). Common flows:
1. Flush recent ACCESS logs
2. Commit plan progress
3. Summarize working notes

### Session end (`session-end` event)

Fires when:
- User types `/exit`, `bye`, or closes the session
- Context pressure reaches 90% (critical)
- Session timeout (configurable)

**All matching skills run in priority order:**
1. Final checkpoint
2. Write reflection
3. Clean up temporary state

### Tool events (`pre-tool-use`, `post-tool-use`)

Fire immediately before and after an MCP tool is called.

**`pre-tool-use`:**
- Matcher: `tool_name` regex, `condition` for state-based guards
- Use case: validate inputs, log intent, check permissions

**`post-tool-use`:**
- Matcher: `tool_name` regex, check for errors via matcher conditions
- Use case: validate outputs, update derived state, trigger follow-on actions

**At most one skill runs per event** (highest priority).

### Project lifecycle (`project-active` event)

Fires when:
- A project becomes the active focus (e.g., user navigates to `projects/my-project/`)
- Agent loads a plan and begins work on it

**Matcher:** `project_id` must match the active project slug.

**Use case:** Activate project-specific workflows (codebase survey, feature planning, etc.).

### On-demand (`on-demand` event)

Fires when:
- User explicitly requests a skill via `/skill-name` or voice command
- Agent decides to run a skill procedurally (e.g., for debugging or auditing)

**No matcher** — the skill name itself identifies the dispatch target.

### Periodic (`periodic` event)

Fires on a schedule defined by the skill's `interval` matcher.

**Matcher:** `interval` must be:
- A cron expression (e.g., `"0 9 * * *"` = daily at 9am in local time), OR
- A duration string (e.g., `"7 days"`, `"6 hours"`)

**Use case:** Daily standups, weekly reviews, monthly audits.

The agent's scheduler is responsible for checking periodic triggers at session start and at configurable intervals.

---

## Behavioral rules and guarantees

### Deterministic dispatch

Given the same event and state, the trigger system always selects the same skill(s). This is essential for audit trails and reproducibility.

### No implicit side effects

Triggers are **declarative only** — they specify when a skill should run, not what it does. The skill's body determines behavior. This separation prevents "trigger surprise" where a skill does something unexpected.

### Skill isolation

Skills triggered by different events do not assume they have run in a particular order. For example, a `post-tool-use` skill should not assume that a `session-start` skill has already run. If ordering is required, use priorities or create a compound skill.

### Fallback to catalog

If no explicit trigger is defined, the agent may still invoke a skill through:
- Manifest discovery (reading SKILLS.yaml)
- User request (`/skill-name`)
- Programmatic selection (e.g., in a plan)

This preserves backward compatibility.

### Event queuing and replay

In high-load scenarios (e.g., many tools called in rapid succession), events may queue. The trigger system processes them in order, running matching skills sequentially. Events are not dropped or coalesced.

---

## Examples

### Example 1: Periodic review trigger

```yaml
---
name: periodic-review
description: >-
  Deep system review on a 30-day cadence.
trigger:
  event: periodic
  matcher:
    interval: "30 days"
  priority: 100
trust: high
---
```

This skill runs automatically every 30 days (or when explicitly requested via `/periodic-review`).

### Example 2: Project-specific survey

```yaml
---
name: codebase-survey
description: >-
  Host-repo exploration for new worktree setups.
trigger:
  event: project-active
  matcher:
    project_id: codebase-survey
  priority: 30
trust: medium
---
```

This skill activates when the user opens the `codebase-survey` project.

### Example 3: Guardrail on tool use

```yaml
---
name: tool-safety-check
description: >-
  Validate tool inputs before memory writes.
trigger:
  event: pre-tool-use
  matcher:
    tool_name: "memory_write_file|memory_delete"
  priority: 100
trust: high
---
```

This skill runs before any memory write or delete tool, validating that the operation is safe.

### Example 4: Multi-event emergency flush

```yaml
---
name: emergency-context-flush
description: >-
  Save all state immediately when context is critical.
trigger:
  - event: session-checkpoint
    matcher:
      condition: context_pressure_critical
    priority: 200
  - event: session-end
    matcher:
      condition: context_pressure_critical
    priority: 200
trust: high
---
```

This skill runs at high priority whenever context pressure is critical, on either checkpoint or session-end events.

---

## Migration guide

### For existing skills

1. Identify the intended trigger event(s) from the skill's description and use cases.
2. Add a `trigger` field to the SKILL.md frontmatter.
3. If the skill has no special conditions, use the simple form (e.g., `trigger: session-start`).
4. If the skill applies only to specific situations, add a `matcher`.
5. Test with the agent to ensure the skill activates as expected.

**Example migration:**

**Before:**
```yaml
---
name: codebase-survey
description: >-
  Systematic host-repo exploration. Use when
  projects/codebase-survey/SUMMARY.md is active...
---
```

**After:**
```yaml
---
name: codebase-survey
description: >-
  Systematic host-repo exploration for active codebase-survey projects.
trigger:
  event: project-active
  matcher:
    project_id: codebase-survey
  priority: 30
---
```

### For new skills

Always include a `trigger` field. Choose the appropriate event and matcher. This makes the skill's lifecycle explicit and discoverable.

---

## Future extensions

This specification is designed for extension:

- **Composite triggers:** Boolean combinations of matchers (AND, OR, NOT).
- **Conditional execution:** Triggers that fire based on user profile or preference.
- **Trigger guards:** Safety checks that prevent a skill from running under dangerous conditions.
- **Async triggers:** Background skills that run without blocking the session.
- **Skill ordering constraints:** Explicit before/after dependencies between skills on the same event.

These are left for future versions. File proposals in `core/governance/review-queue.md` if needed.

---

## References

- **Skill files:** `core/memory/skills/*/SKILL.md`
- **Manifest:** `SKILLS.yaml` (when present)
- **Related governance:**
  - `core/governance/update-guidelines.md` § "Change categories" (protected-tier changes for skills)
  - `core/governance/content-boundaries.md` § "Instruction containment" (skill behavior rules)
  - `core/governance/skill-trigger-conditions.md` (custom condition definitions; to be created)
- **Session lifecycle:** `core/governance/session-checklists.md`
- **Event source code:** Agent implementation of trigger dispatch (see platform documentation)
