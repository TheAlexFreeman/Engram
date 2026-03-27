---
source: agent-generated
trust: medium
created: 2026-03-27
title: "Phase 8 Design: Context Assembly (Briefing Packet)"
---

# Phase 8 Design: Context Assembly (Briefing Packet)

## Motivation

The deep research report emphasizes context engineering as a first-class concern: *"Summarizing and compressing history while preserving decisions, constraints, unresolved issues, and other load-bearing facts."*

Currently, when an agent begins work on a plan phase, it must:

1. Call `memory_plan_execute` with `action=inspect` to get `phase_payload()` data
2. Manually read each source file listed in `phase.sources`
3. Check `next_action()` for failure history and retry context
4. Optionally query traces for prior session activity on this plan
5. Optionally check approval status for `requires_approval` phases
6. Note tool policies from `phase_payload()["tool_policies"]`

This typically requires 3-6 sequential tool calls before the agent can begin actual work. Each call consumes latency and context tokens. A single `memory_plan_briefing` tool that assembles all relevant context into one response would:

- Reduce tool-call overhead from 3-6 calls to 1
- Ensure agents always see failure history and tool policies (no accidental omission)
- Make the report's "plan-then-execute with continuous tool-grounded checkpoints" pattern automatic
- Provide a natural integration point for context budgeting

---

## Extension 1: `assemble_briefing()` helper

### Problem

`phase_payload()` returns structured metadata about the phase, but not the *content* the agent needs to do the work: source file text, recent traces, approval status details.

### Design

Add to `plan_utils.py`:

```python
def assemble_briefing(
    plan: PlanDocument,
    phase: PlanPhase,
    root: Path,
    *,
    max_context_chars: int = 8000,
    include_sources: bool = True,
    include_traces: bool = True,
    include_approval: bool = True,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Assemble a comprehensive context package for a plan phase.

    Returns a dict containing:
    - phase: enriched phase_payload()
    - source_contents: truncated text of each source file
    - failure_summary: compact summary of prior failures
    - recent_traces: relevant trace spans for this plan
    - approval_status: current approval document if applicable
    - tool_policies: registered tool policies for phase postconditions
    - context_budget: estimated character/token usage
    """
```

### Assembly algorithm

1. **Start with phase_payload()** — this is the structural foundation (phase metadata, blockers, postconditions, sources list, failures, budget_status, tool_policies)

2. **Read source contents** (if `include_sources`):
   - For each `SourceSpec` with type `internal`:
     - Resolve path against `root`
     - Read file contents, truncate to budget share
     - Include `intent` alongside the content
   - For `external` and `mcp` sources: include URI/path only (no fetching)
   - Budget allocation: distribute `max_context_chars` across sources proportionally, reserving space for other sections

3. **Summarize failures** (always included when present):
   - Extract from `phase.failures`: timestamp, reason, attempt number
   - If verification_results exist, include failed postconditions only
   - Compact format: one line per failure, most recent first

4. **Include recent traces** (if `include_traces` and `session_id` provided):
   - Read TRACES.jsonl for the current session (or most recent session for this plan)
   - Filter to spans with `metadata.plan_id` matching
   - Limit to last 10 spans
   - Include: span_type, name, status, duration_ms

5. **Check approval status** (if `include_approval` and phase has `requires_approval`):
   - Call `load_approval()` for the plan/phase pair
   - Include approval status, expiry, and any resolution comment

6. **Compute context budget metadata**:
   - Total chars assembled
   - Estimated token count (chars / 4 as rough estimate)
   - Whether truncation was applied
   - Breakdown by section

### Return schema

```json
{
  "plan_id": "my-plan",
  "phase_id": "phase-one",
  "phase": { /* full phase_payload() output */ },
  "source_contents": [
    {
      "path": "some/file.md",
      "type": "internal",
      "intent": "Read design decisions",
      "content": "# File contents...[truncated at 2000 chars]",
      "full_length": 5432,
      "truncated": true
    }
  ],
  "failure_summary": [
    {
      "attempt": 1,
      "timestamp": "2026-03-27T10:00:00Z",
      "reason": "Postcondition failed: file not found",
      "failed_postconditions": ["check: memory/working/notes/test.md"]
    }
  ],
  "recent_traces": [
    {
      "span_type": "plan_action",
      "name": "phase-start",
      "status": "ok",
      "duration_ms": 150,
      "timestamp": "2026-03-27T10:05:00Z"
    }
  ],
  "approval_status": {
    "status": "approved",
    "reviewer": "Alex",
    "resolved_at": "2026-03-27T09:00:00Z",
    "comment": "Looks good, proceed."
  },
  "context_budget": {
    "total_chars": 6543,
    "estimated_tokens": 1636,
    "truncated": true,
    "breakdown": {
      "phase_payload": 1200,
      "source_contents": 4000,
      "failure_summary": 343,
      "recent_traces": 800,
      "approval_status": 200
    }
  }
}
```

### Context budgeting strategy

The `max_context_chars` parameter (default 8000) controls total output size. Budget is allocated with priorities:

1. **Phase payload** — always included in full (typically 500-1500 chars). This is non-negotiable structural data.
2. **Failure summary** — always included in full when present (typically 200-500 chars). Critical for retry reasoning.
3. **Approval status** — always included in full when applicable (typically 100-300 chars). Small and decision-critical.
4. **Source contents** — allocated remaining budget minus trace reservation. Distributed proportionally across sources. Each source gets at minimum 200 chars even if budget is tight.
5. **Recent traces** — allocated 10-15% of total budget. Traces are compact but lower priority than source content.

If `max_context_chars` is set to 0, no truncation is applied (unlimited).

---

## Extension 2: `memory_plan_briefing` MCP tool

### Problem

Agents need a single tool call to get all phase context.

### Design

```
Tool: memory_plan_briefing

Parameters:
  plan_id: str              — plan to brief on
  phase_id: str | None      — specific phase (default: next actionable phase)
  project_id: str | None    — project scope (auto-resolved if omitted)
  max_context_chars: int    — context budget (default: 8000, 0 = unlimited)
  include_sources: bool     — include source file contents (default: true)
  include_traces: bool      — include recent trace spans (default: true)

Returns: JSON from assemble_briefing()

Annotations:
  readOnlyHint: true        — reads files but does not modify plan state
  destructiveHint: false
  idempotentHint: true
  openWorldHint: false

Self-instrumentation:
  Emits a trace span: span_type="tool_call", name="memory_plan_briefing"
  with metadata: plan_id, phase_id, context_chars, truncated
```

### Behavioral contract

- If `phase_id` is not provided, briefs on the next actionable phase (from `next_action()`)
- If no actionable phase exists, returns the plan summary with progress info
- Source files that don't exist are reported with `content: null, error: "file not found"` (graceful degradation, no exceptions)
- The tool does not modify plan state — it is purely a read operation
- Session_id is inferred from `MEMORY_SESSION_ID` env var (same pattern as `memory_plan_verify`)

---

## Implementation notes

- `assemble_briefing()` goes in `plan_utils.py` (~80-120 lines) — it's a pure function that composes existing helpers
- The MCP tool in `plan_tools.py` is thin (~40 lines) — resolve plan, find phase, call `assemble_briefing()`, emit trace, return JSON
- Source file reading uses `Path.read_text()` with try/except for missing files
- Token estimation is deliberately simple (chars / 4) — not trying to be exact, just providing a useful signal
- No new dataclasses needed: the briefing is a plain dict assembled from existing structures
- Tests should cover: missing sources, all-truncated output, zero-budget (unlimited), approval-included, traces-included, no-failures, multi-failure phases
