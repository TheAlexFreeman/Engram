---
source: agent-generated
trust: medium
created: 2026-03-26
origin_session: memory/activity/2026/03/26/chat-002
title: "Phase 2 Design: Inline Verification"
---

# Phase 2 Design: Inline Verification

## Motivation

Phase 1 added `PostconditionSpec` to plan phases — typed success criteria with `check`, `grep`, `test`, and `manual` validators. But postconditions are currently **documentation only**: `memory_plan_execute` surfaces them in responses so the agent can self-check, but no tool automates the verification. The agent harness report identifies tool-grounded checkpoints as the #1 reliability recommendation: "interleave reasoning with actions; verify before proceeding."

This phase closes the loop by:

1. Adding a `memory_plan_verify` tool that evaluates non-manual postconditions automatically.
2. Wiring verification into the plan-complete flow so agents get structured pass/fail results.
3. Recording failures with enough context for informed retry.
4. Surfacing failure history so agents can reason about what went wrong on previous attempts.

---

## Extension 1: `memory_plan_verify` — Automated postcondition evaluation

### Problem

An agent completing a phase must currently interpret each postcondition string and manually check whether it holds. For `check` (file exists), `grep` (pattern in file), and `test` (command passes) types, this is automatable.

### Design

New MCP tool: `memory_plan_verify`

```
Parameters:
  plan_id: str       — plan to verify
  phase_id: str      — phase to verify (must be in-progress or completed)
  project_id: str    — project scope (optional, inferred from plan if unambiguous)

Returns: MemoryWriteResult with new_state containing:
  verification_results: list[dict]
    - postcondition: str (description text)
      type: str (manual|check|grep|test)
      status: str (pass|fail|skip|error)
      detail: str | null (error message or match context)
  summary:
    total: int
    passed: int
    failed: int
    skipped: int (manual postconditions)
    errors: int (postcondition that couldn't be evaluated)
  all_passed: bool (true only if failed == 0 and errors == 0)
```

### Validator implementations

| Type | `target` format | Evaluation logic | Pass condition |
|---|---|---|---|
| `manual` | (none) | Not evaluated; status = `skip` | Always skipped |
| `check` | Repo-relative file path | `(root / target).exists()` | File exists |
| `grep` | `pattern::path` | `re.search(pattern, file_contents)` | Pattern found |
| `test` | Shell command | `subprocess.run(target, shell=True, cwd=root, timeout=30)` | Exit code 0 |

### Security constraints for `test` type

The `test` postcondition type executes shell commands. To prevent abuse:

- **Command allowlist:** Only commands matching a configurable allowlist pattern are executed. Default: `pre-commit run`, `pytest`, `python -m pytest`, `ruff check`, `ruff format --check`, `mypy`. Configurable via `core/governance/` policy file.
- **Timeout:** Hard 30-second timeout per command. Non-configurable.
- **No network access:** Commands run with `env` stripped of proxy variables (defense in depth, not bulletproof).
- **Cwd is repo root:** Commands cannot escape the repository directory.
- **Stderr/stdout captured:** Output included in `detail` on failure, truncated to 2000 chars.
- **Tier 2 only:** `memory_plan_verify` with `test`-type postconditions is gated behind `ENGRAM_TIER2=1` environment flag, consistent with other execution-capable tools.

### Behavioral contract

- The tool does not modify plan state. It is a read-only evaluation.
- Results are returned to the calling agent, which decides whether to proceed with `complete` or retry.
- If no postconditions exist on the phase, the tool returns a summary with `total: 0, all_passed: true`.
- If the phase has only `manual` postconditions, all are skipped and `all_passed: true` (manual checks are the agent's responsibility).

---

## Extension 2: Verification integration with `memory_plan_execute`

### Problem

Currently `memory_plan_execute` with `action: "complete"` blindly marks the phase as completed. There's no structured way to verify postconditions as part of completion.

### Design

Add an optional `verify` parameter to the `complete` action:

```
memory_plan_execute(
  plan_id: str,
  action: "complete",
  verify: bool = false,    # NEW: run postcondition checks before completing
  commit_sha: str | null,
  ...
)
```

When `verify=true`:

1. Run all non-manual postconditions (same logic as `memory_plan_verify`).
2. If all pass: complete phase normally, include `verification_results` in response.
3. If any fail: **do not complete the phase**. Return the verification results with `status: "verification_failed"` in `new_state`. Phase stays `in-progress`.

When `verify=false` (default, backward-compatible): current behavior, no checks.

### Behavioral contract

- `verify=true` is opt-in. Existing workflows are unaffected.
- The agent can call `memory_plan_verify` standalone (read-only) before deciding to complete.
- Or the agent can call `complete` with `verify=true` for atomic verify-and-complete.
- Failed verification does not create a failure record automatically — that's Extension 3.

---

## Extension 3: Failure recording

### Problem

When a phase fails (verification or otherwise), there's no structured record of what went wrong. On retry, the agent has no history to learn from. The harness report calls this "reflection-style memory for learning from failures."

### Design

Add a `failures` list to `PlanPhase`:

```python
@dataclass(slots=True)
class PhaseFailure:
    """Record of a failed attempt on a phase."""
    timestamp: str          # ISO 8601
    reason: str             # What went wrong (free text)
    verification_results: list[dict] | None = None  # From memory_plan_verify if applicable
    attempt: int = 1        # Which attempt this was

@dataclass(slots=True)
class PlanPhase:
    # ... existing fields ...
    failures: list[PhaseFailure] = field(default_factory=list)
```

### Recording mechanism

New MCP tool parameter or standalone tool:

```
memory_plan_execute(
  plan_id: str,
  action: "record_failure",   # NEW action
  phase_id: str,
  reason: str,                # What went wrong
  verification_results: list[dict] | null,  # Optional: attach verify results
)
```

Behavior:
- Appends a `PhaseFailure` to the phase's `failures` list.
- Sets `attempt` to `len(failures) + 1`.
- Phase stays `in-progress` (failure doesn't change status).
- Commits to git for audit trail.

### YAML representation

```yaml
phases:
  - id: implement-feature
    title: Implement the feature
    status: in-progress
    failures:
      - timestamp: '2026-04-02T14:30:00Z'
        reason: "grep postcondition failed: pattern 'class SourceSpec' not found in plan_utils.py"
        attempt: 1
        verification_results:
          - postcondition: "SourceSpec dataclass exists"
            type: grep
            status: fail
            detail: "pattern not found"
      - timestamp: '2026-04-02T15:10:00Z'
        reason: "test postcondition failed: pre-commit hooks found formatting issues"
        attempt: 2
```

### Backward compatibility

- `failures` defaults to empty list.
- Empty `failures` lists are omitted from YAML output (same pattern as `sources`, `postconditions`).
- Existing plans load without modification.

---

## Extension 4: Retry with context

### Problem

When an agent retries a failed phase, it needs to know what was tried before and what went wrong. Currently `phase_payload()` provides sources, changes, and postconditions — but no failure history.

### Design

Extend `phase_payload()` to include failure history:

```python
def phase_payload(plan, phase, root):
    payload = {
        # ... existing fields ...
        "failures": [f.to_dict() for f in phase.failures],
        "attempt_number": len(phase.failures) + 1,
    }
    return payload
```

Extend `next_action()` similarly:

```python
def next_action(plan):
    # ... existing logic ...
    return {
        "id": phase.id,
        "title": phase.title,
        # ... existing fields ...
        "has_prior_failures": bool(phase.failures),
        "attempt_number": len(phase.failures) + 1,
    }
```

### Behavioral contract

- Failure history is always included when present — no opt-in needed.
- Agents can use failure history to adjust their approach (e.g., "the grep check failed because the class was named differently — check the actual name before retrying").
- `attempt_number` provides a simple counter for budget-aware retry limits.

---

## Interaction model

A complete verification cycle:

```
1. Agent executes phase changes

2. Agent calls memory_plan_verify(plan_id, phase_id)
   → Returns: verification_results with pass/fail per postcondition

3a. If all pass:
    Agent calls memory_plan_execute(action="complete", commit_sha=...)
    → Phase marked completed; next phase available

3b. If some fail:
    Agent calls memory_plan_execute(action="record_failure", reason="...", verification_results=...)
    → Failure recorded; phase stays in-progress
    Agent reads failure history from phase_payload()
    Agent adjusts approach and retries from step 1

Alternative (atomic):
1. Agent executes phase changes
2. Agent calls memory_plan_execute(action="complete", verify=true, commit_sha=...)
   → If pass: phase completed
   → If fail: phase stays in-progress; verification_results in response
```

---

## What this phase does NOT include

- **Automated retry loops.** The agent decides when and how to retry. The plan system records state; it doesn't drive behavior.
- **Test execution sandbox.** The `test` validator runs in the repo directory with a timeout and allowlist. Full sandboxing (containers, network isolation) is out of scope.
- **Postcondition editing.** Postconditions are set at plan-create time. If they need to change, the plan is edited directly.
- **Cross-phase verification.** Each phase's postconditions are checked independently. Verifying that a later phase didn't break an earlier one is an orchestration concern (future work).
