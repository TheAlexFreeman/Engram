---
source: agent-generated
trust: medium
created: 2026-03-27
title: "Phase 6 Design: Cross-Phase Integration Tests"
---

# Phase 6 Design: Cross-Phase Integration Tests

## Motivation

Phases 1–5 each shipped with unit tests scoped to their own subsystem: `TestSourceSpec`, `TestVerifyPostconditions`, `TestTraceSpanDataclass`, `TestToolDefinitionDataclass`, `TestApprovalDocumentDataclass`, etc. Each subsystem works in isolation — but the harness's value comes from subsystem *composition*: a plan that verifies postconditions, emits traces for each lifecycle event, auto-pauses for approval on sensitive phases, and includes tool policies in context.

No existing test validates these cross-cutting paths. The deep research report warns about "emergent failure modes" in coupled systems and emphasizes that "agent behavior emerges from the coupled system (model + tools + state + control flow + feedback)." This phase closes that gap.

## What's untested

| Cross-cutting path | Subsystems involved | Risk without testing |
|---|---|---|
| Start → auto-pause → trace emitted → resolve → resume → complete with verify | Phases 1, 2, 3, 5 | Approval creates trace but trace metadata may be stale after resume |
| Verify failure → record_failure → next_action with retry context → re-verify | Phases 1, 2 | Failure history may not serialize/deserialize correctly across attempts |
| Phase with test postcondition → tool_policies in phase_payload → verify | Phases 1, 2, 4 | Tool policy resolution may not handle postcondition targets that don't match any registered tool |
| Full lifecycle → query traces → assert complete span coverage | Phases 1, 2, 3 | Trace instrumentation may miss some plan_action events or emit wrong metadata |
| Approval expiry on paused plan → budget status while paused | Phases 1, 5 | Budget accounting during pause/expire/block transitions is untested |
| Plan with 3+ failures → suggest_revision + tool policies + approval | Phases 1, 2, 4, 5 | Edge case where all subsystems interact simultaneously |

## Test fixture strategy

### Extending existing helpers

The current test file uses `_minimal_plan()` and `_write_minimal_plan_at()` as base fixtures. Integration tests need richer variants:

```python
def _approval_ready_plan(**overrides) -> PlanDocument:
    """Plan with a requires_approval phase, sources, postconditions, and changes."""
    ...

def _full_harness_plan(**overrides) -> PlanDocument:
    """Plan with all subsystem features: sources, postconditions (check/grep/test),
    requires_approval, budget, changes — suitable for end-to-end lifecycle tests."""
    ...

def _setup_approval_dirs(root: Path) -> None:
    """Create working/approvals/pending/ and resolved/ directories."""
    ...

def _setup_registry(root: Path, tools: list[ToolDefinition] | None = None) -> None:
    """Create skills/tool-registry/ with optional seed tools."""
    ...
```

### Test class organization

All integration tests go in `test_plan_schema_extensions.py` (consistent with existing patterns, shared imports):

```
class TestApprovalLifecycleE2E(unittest.TestCase)     # approval → pause → resume → complete
class TestVerifyFailRetryE2E(unittest.TestCase)        # verify fail → record_failure → retry → pass
class TestTraceCoverageE2E(unittest.TestCase)           # lifecycle events → query traces
class TestToolPolicyE2E(unittest.TestCase)              # registry → phase_payload → verify
class TestCrossCuttingRegression(unittest.TestCase)     # edge cases across subsystems
```

## Test scenario designs

### 1. Approval lifecycle end-to-end

**Setup:** Plan with `requires_approval: true` phase, check/grep postconditions, budget.

**Steps:**
1. Call `next_action(plan)` → verify `requires_approval: true` in directive
2. Simulate `start` action logic: detect `requires_approval`, check no existing approval
3. Create `ApprovalDocument` (pending), set plan status to `paused`
4. Save plan and approval; verify `load_approval()` returns pending document
5. Call `record_trace()` with `plan_action` / `approval-requested` span
6. Verify plan blocked for `start` and `complete` while paused
7. Resolve approval (approve); verify plan status transitions to `active`
8. Move approval file from `pending/` to `resolved/`
9. Re-run `start` logic: approval is now `approved`, proceed to normal start
10. Set phase to `in-progress`, call `verify_postconditions()` (should pass)
11. Complete phase; verify `budget_status()` increments `sessions_used`
12. Query traces: verify `approval-requested` span exists with correct metadata

**Assertions:**
- Plan transitions: `active → paused → active → active` (with phase in-progress → completed)
- Approval transitions: `(none) → pending → approved`
- At least one trace span with `span_type: plan_action`, `name: approval-requested`
- Budget `sessions_used` incremented by 1

### 2. Verification failure → retry → success

**Setup:** Plan with grep postcondition against a file that doesn't exist yet.

**Steps:**
1. Start phase (set to `in-progress`)
2. Call `verify_postconditions()` → expect `all_passed: false` (grep target missing)
3. Record failure via `PhaseFailure` with verification results
4. Save plan; reload; verify failure persisted
5. Check `next_action()` returns `has_prior_failures: true`, `attempt_number: 2`
6. Check `phase_payload()` includes `failures` list with 1 entry
7. Create the missing file with the expected pattern
8. Call `verify_postconditions()` again → expect `all_passed: true`
9. Complete phase with verified postconditions
10. Record trace for verification pass

**Assertions:**
- `phase.failures` has exactly 1 entry after first attempt
- `next_action()["attempt_number"]` == 2
- Second `verify_postconditions()` returns `all_passed: true`
- Failure history survives save/load round-trip

### 3. Trace coverage across lifecycle

**Setup:** Plan with two phases; session_id set.

**Steps:**
1. Call `record_trace()` for `plan_action` / `plan-create`
2. Start first phase → `record_trace()` for `plan_action` / `phase-start`
3. Verify first phase → `record_trace()` for `verification` / `verify:phase-id`
4. Complete first phase → `record_trace()` for `plan_action` / `phase-complete`
5. Start and complete second phase similarly
6. Read the TRACES.jsonl file directly
7. Parse all spans; verify no duplicate `span_id` values
8. Verify span_types include both `plan_action` and `verification`
9. Verify all spans have valid `session_id`, `timestamp`, non-empty `name`
10. Verify metadata contains `plan_id` and `phase_id` on all plan_action spans

**Assertions:**
- At least 5 spans recorded (create + 2×start + verify + 2×complete)
- All `span_id` values unique
- All timestamps ISO 8601 formatted
- No `None` values for required fields

### 4. Tool policy → phase_payload integration

**Setup:** Plan with test-type postcondition targeting `pytest-run`; registry with matching tool.

**Steps:**
1. Create tool registry with `ToolDefinition(name="pytest-run", provider="shell", ...)`
2. Save registry via `save_registry()`
3. Create plan with phase having `postconditions=[PostconditionSpec(type="test", target="python -m pytest ...", description="...")]`
4. Call `phase_payload(plan, phase, root)` → check `tool_policies` field
5. Verify tool_policies contains entry with `tool_name: pytest-run`
6. Verify `approval_required`, `cost_tier`, `timeout_seconds` from the registered definition
7. Remove the tool from registry; call `phase_payload()` again → `tool_policies` should be empty
8. Register a tool with different name → `tool_policies` should still be empty (no match)

**Assertions:**
- `phase_payload()["tool_policies"]` has 1 entry when matching tool is registered
- Policy entry fields match the registered `ToolDefinition` values
- Empty list when no matching tool exists

### 5. Cross-cutting regression

Individual tests for edge cases:

- **Expired approval + verify:** Load a plan with expired approval → verify plan is blocked → verify postconditions still returns results (not blocked by plan status)
- **Budget warning while paused:** Plan with budget near exhaustion, status=paused → `budget_status()` reports `over_budget: true` correctly
- **suggest_revision + tool policies:** Plan with 3+ failures on a phase with test postconditions → `next_action()` has `suggest_revision: true` AND `phase_payload()` includes `tool_policies`
- **Backward compat:** Load a plan YAML written with Phase 1 schema only (no failures, no tool_policies) → all Phase 2-5 features work with defaults

## Implementation notes

- All tests operate on `tempfile.TemporaryDirectory()` with `_write_minimal_plan_at()` or the new fixture helpers
- Tests call `plan_utils` functions directly (not via MCP server) for speed and hermeticity
- For approval tests, manually create the `working/approvals/pending/` and `resolved/` dirs
- For trace tests, use `record_trace()` directly and read back from TRACES.jsonl
- For registry tests, use `save_registry()` / `load_registry()` directly
- Target: 30-40 new tests bringing total to 220+
