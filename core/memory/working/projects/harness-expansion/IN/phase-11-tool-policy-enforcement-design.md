---
source: agent-generated
trust: medium
origin_session: memory/activity/2026/03/27/chat-003
created: 2026-03-27
title: "Phase 11: Tool Policy Enforcement Design"
---

# Phase 11: Tool Policy Enforcement Design

## Motivation

Phase 4 built a tool registry with `ToolDefinition` storing `approval_required`, `cost_tier`, and `rate_limit` metadata — but these fields are informational only. No runtime path enforces them. The deep research report emphasizes: "enforce a tool policy layer that can block or require approval based on tool + args + context" and "assume every tool output is untrusted input."

This phase makes tool policies enforceable by adding `check_tool_policy()` and wiring it into execution paths.

## Design Constraints

1. **Additive.** Existing behavior is unchanged when no tool definition exists in the registry. Policy enforcement only activates for registered tools.
2. **Fail-open for reads.** Tier 0 (read-only) operations are never gated by policy. Only Tier 1/2 write paths invoke policy checks.
3. **Separable from phase approval.** Tool policy approval is distinct from plan phase approval. A phase may not require approval, but a tool invoked during that phase might.
4. **Observable.** Every policy violation produces a trace span for auditability.

## PolicyCheckResult Schema

```python
@dataclass(slots=True)
class PolicyCheckResult:
    """Result of a tool policy evaluation."""
    allowed: bool
    reason: str
    tool_name: str = ""
    provider: str = ""
    required_action: str | None = None
    violation_type: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
```

| Field | Type | Description |
|---|---|---|
| `allowed` | bool | Whether the tool invocation should proceed. |
| `reason` | str | Human-readable explanation (e.g., "approved", "rate_limit_exceeded"). |
| `tool_name` | str | The tool that was checked. |
| `provider` | str | The tool's provider. |
| `required_action` | str \| None | What must happen before the tool can proceed: `"approval"`, `"rate_limit_wait"`, or `None`. |
| `violation_type` | str \| None | Category: `"approval_required"`, `"rate_limit_exceeded"`, `"cost_warning"`, or `None`. |
| `details` | dict | Type-specific metadata (rate limit counts, cost info, approval expiry). |

## check_tool_policy() Function

```python
def check_tool_policy(
    root: Path,
    tool_name: str,
    provider: str,
    *,
    session_id: str | None = None,
    plan_budget: PlanBudget | None = None,
) -> PolicyCheckResult:
```

### Evaluation order

1. **Tool lookup.** Load the tool definition from the registry. If not found, return `PolicyCheckResult(allowed=True, reason="no_policy")`.

2. **Eval bypass.** If `ENGRAM_EVAL_MODE=1` environment variable is set, return `PolicyCheckResult(allowed=True, reason="eval_bypass")`. This lets eval scenarios test tool behavior without being blocked.

3. **Approval check.** If `approval_required=True`, check for an active approval for this tool+provider combination in the approvals directory. If no approved document exists, return `allowed=False` with `required_action="approval"`.

4. **Rate limit check.** If `rate_limit` is set, parse the limit string, count recent invocations from trace spans, and compare. If exceeded, return `allowed=False` with `required_action="rate_limit_wait"`.

5. **Cost awareness.** If `cost_tier` is `"high"` and `plan_budget` indicates tight constraints (past deadline or over session budget), return `allowed=True` but include `violation_type="cost_warning"` in the result so the caller can emit a warning.

6. **Default allow.** Return `PolicyCheckResult(allowed=True, reason="policy_passed")`.

## Rate Limit Counting

### Rate limit string format

The existing `ToolDefinition.rate_limit` field is a freeform string. This design standardizes parsing:

```
<count>/<period>
```

Where:
- `count` is a positive integer
- `period` is one of: `minute`, `hour`, `day`, `session`

Examples: `"10/hour"`, `"100/day"`, `"5/session"`, `"3/minute"`

### Counting strategy: sliding window from trace spans

Rate limits are counted by querying trace spans (`span_type="tool_call"`) where the span `name` matches the tool name, within the appropriate time window.

| Period | Window |
|---|---|
| `minute` | Last 60 seconds |
| `hour` | Last 3600 seconds |
| `day` | Last 86400 seconds |
| `session` | Spans matching current `session_id` |

### Why trace spans (not a separate counter)

1. **No new storage.** Traces already exist and carry timestamps.
2. **Consistent.** The same data that provides observability also enforces policy.
3. **Resilient.** If traces are missing, the count is conservatively low (fail-open, not fail-closed). This matches the "additive enforcement" constraint.

### Parser function

```python
def _parse_rate_limit(rate_limit: str) -> tuple[int, str] | None:
    """Parse 'N/period' into (count, period). Returns None if unparseable."""
```

### Counting function

```python
def _count_recent_invocations(
    root: Path,
    tool_name: str,
    period: str,
    *,
    session_id: str | None = None,
) -> int:
```

Scans trace files in reverse chronological order. Stops scanning once the time window is exceeded to avoid reading the entire trace history.

## Enforcement Tiers

| Check | Result when violated | Severity |
|---|---|---|
| `approval_required` | **Hard block.** Returns `allowed=False`. Caller must create approval and wait. | Blocking |
| `rate_limit` exceeded | **Hard block.** Returns `allowed=False` with retry-after information. | Blocking |
| `cost_tier="high"` + tight budget | **Soft warning.** Returns `allowed=True` with `violation_type="cost_warning"`. | Advisory |
| No policy registered | **Allow.** No enforcement. | None |

There is no blanket override flag. Approval-required tools must go through the approval workflow. Rate-limited tools must wait for the window to pass.

## Approval Integration for Tools

Tool-level approval is similar to but separate from phase-level approval:

- **Approval scope:** `tool:{provider}/{tool_name}` — stored in the same approvals directory but with a different filename convention: `tool--{provider}--{tool_name}.yaml`.
- **Expiry:** Tool approvals default to a 24-hour expiry (shorter than phase approvals) since tool usage is more frequent and granular.
- **Reuse:** An approved tool stays approved until its approval expires. Multiple invocations within the window don't require re-approval.

### Approval check flow

```
check_tool_policy(tool_name, provider)
  → load_approval(root, f"tool-{provider}", tool_name)
  → if approved: allow
  → if pending: block with "awaiting approval"
  → if expired/rejected/missing: block with required_action="approval"
```

The caller (plan tool or semantic tool) is responsible for creating the approval document when `required_action="approval"` is returned. This keeps `check_tool_policy()` pure (read-only) and lets callers decide on context-specific approval messages.

## policy_violation Trace Span Type

A new trace span type `policy_violation` is added to `TRACE_SPAN_TYPES`.

Every policy check failure (hard block) emits a trace span:

```json
{
  "span_type": "policy_violation",
  "name": "check_tool_policy",
  "status": "denied",
  "metadata": {
    "tool_name": "<name>",
    "provider": "<provider>",
    "violation_type": "<approval_required|rate_limit_exceeded>",
    "rate_limit": "<original string if applicable>",
    "current_count": 10,
    "limit": 5
  }
}
```

This enables querying violations via `memory_query_traces` with `span_type="policy_violation"`.

## Integration Points

### 1. Plan postcondition verification

`verify_postconditions()` already runs test-type postconditions. When a postcondition target matches a registered tool (via `_command_matches_tool()`), `check_tool_policy()` is called first. If the policy check fails, the postcondition result is `"error"` with the policy violation as detail.

### 2. Plan phase execution

`_resolve_tool_policies()` already returns tool policy metadata in `phase_payload()`. This data is informational for agents. The actual enforcement happens when tools are invoked, not when policies are inspected.

### 3. Future: direct tool call gating

Individual MCP tool implementations that perform external operations (e.g., a future tool that calls an external API) can call `check_tool_policy()` at the start of their implementation. This is opt-in per tool, not a blanket middleware.

## Eval Scenario Interaction

When `ENGRAM_EVAL_MODE=1` is set:

- `check_tool_policy()` returns `allowed=True` with `reason="eval_bypass"` for all tools.
- No policy violation traces are emitted.
- Rate limit counters are not incremented.

This lets eval scenarios exercise tool paths without accumulating policy state or being blocked by rate limits.

## Open Questions (Resolved)

### Q: Should policy checks apply to all tiers or only Tier 1/2 writes?

**Decision:** Tier 1 and Tier 2 only. Tier 0 is read-only and cannot cause damage. The tool registry itself is about external tools that perform actions, which are inherently write-tier.

### Q: How should rate limits be counted?

**Decision:** Sliding window using trace spans as the timestamp source. Periods: `minute`, `hour`, `day`, `session`. This reuses existing infrastructure without new storage.

### Q: Should policy violations be hard blocks or soft warnings?

**Decision:** Two-tier. Approval and rate limits are hard blocks (the tool cannot proceed). Cost tier is a soft warning (the tool proceeds but the caller is informed). No blanket override mechanism — approval-required tools must be approved, rate-limited tools must wait.

### Q: How should policy checks interact with eval scenarios?

**Decision:** `ENGRAM_EVAL_MODE=1` bypasses all policy checks. Evals should test tool logic, not policy enforcement. Policy enforcement is tested in dedicated unit tests.

## Implementation Sequence

1. Add `PolicyCheckResult` dataclass to `plan_utils.py`
2. Add `_parse_rate_limit()` and `_count_recent_invocations()` helpers
3. Add `check_tool_policy()` main function
4. Add `policy_violation` to `TRACE_SPAN_TYPES`
5. Wire `check_tool_policy()` into `verify_postconditions()` for test-type postconditions
6. Add trace emission on policy violations
7. Write tests, documentation
