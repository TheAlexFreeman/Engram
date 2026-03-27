---
source: agent-generated
trust: medium
created: 2026-03-27
title: "Phase 7 Design: Offline Evaluation Framework"
---

# Phase 7 Design: Offline Evaluation Framework

## Motivation

The deep research report identifies evaluation as the clearest remaining gap: *"Eval value compounds over the lifecycle of an agent and prevents reactive production firefighting."* Phase 3 added structured traces (TRACES.jsonl) and a query tool (`memory_query_traces`), but there is no mechanism to:

1. Define **expected behavior** for specific plan/tool/memory interactions
2. Measure **outcome metrics** (task success rate, steps-to-success, retry rate)
3. Detect **regression** when prompts, tools, or models change
4. Compute **process metrics** from trace data over time

This phase adds a lightweight eval framework that uses the existing plan and trace infrastructure as its foundation — not a general-purpose benchmarking system, but one tailored to evaluating Engram's harness behavior.

## Design principles

1. **Eval scenarios run against plan_utils helpers directly** — not via MCP server. This keeps tests fast, hermetic, and parallelizable. The MCP layer is thin enough that testing the underlying functions covers the critical logic.
2. **Scenarios are YAML-defined** — declarative, versionable, reviewable. Each scenario specifies setup (plan fixture), a sequence of operations, and assertions on the resulting state and traces.
3. **Metrics derive from existing trace data** — `memory_query_traces` aggregation is already implemented; the eval framework adds structured metric computation and trend tracking on top.
4. **Eval execution gated behind ENGRAM_TIER2** — eval operations call `verify_postconditions()` which may execute shell commands, so the same security gate applies.

---

## Extension 1: Eval scenario schema

### Problem

There is no standardized way to define "this sequence of plan operations should produce this outcome and these traces."

### Design

Eval scenarios stored as YAML files in `core/memory/skills/eval-scenarios/`:

```yaml
id: basic-plan-lifecycle
description: Create a plan, start a phase, verify postconditions, complete.
tags: [lifecycle, verification]

setup:
  plan:
    id: eval-basic
    project: eval-suite
    phases:
      - id: phase-one
        title: Create a test file
        postconditions:
          - type: check
            target: memory/working/notes/eval-test.md
            description: Test file exists
        changes:
          - path: memory/working/notes/eval-test.md
            action: create
            description: Test marker file
  files:
    - path: memory/working/notes/eval-test.md
      content: "# Eval test\nThis file was created by the eval scenario."

steps:
  - action: start_phase
    phase_id: phase-one
    expect:
      phase_status: in-progress
  - action: verify_phase
    phase_id: phase-one
    expect:
      all_passed: true
  - action: complete_phase
    phase_id: phase-one
    commit_sha: eval-test-001
    expect:
      phase_status: completed
      plan_status: completed

assertions:
  - type: plan_status
    expected: completed
  - type: trace_span_count
    filter: {span_type: plan_action}
    min: 2
  - type: trace_span_count
    filter: {span_type: verification}
    min: 1
  - type: metric
    name: verification_pass_rate
    expected: 1.0
```

### EvalScenario fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Unique scenario identifier (slug format) |
| `description` | string | yes | Human-readable description |
| `tags` | list[str] | no | Categorization tags for filtering |
| `setup` | object | yes | Initial state: plan fixture and optional files to create |
| `setup.plan` | object | yes | Plan definition (same format as `memory_plan_create` input) |
| `setup.files` | list | no | Files to pre-create (path + content) |
| `setup.registry_tools` | list | no | Tool definitions to register before running |
| `steps` | list | yes | Ordered operations to execute |
| `assertions` | list | yes | Post-execution checks |

### Step actions

| Action | Parameters | Description |
|---|---|---|
| `start_phase` | phase_id | Set phase to in-progress |
| `complete_phase` | phase_id, commit_sha, verify? | Complete (optionally with inline verify) |
| `verify_phase` | phase_id | Run postcondition verification |
| `record_failure` | phase_id, reason | Record a failure attempt |
| `request_approval` | phase_id, expires_days? | Create approval request |
| `resolve_approval` | phase_id, resolution, comment? | Approve or reject |
| `create_file` | path, content | Create a file mid-scenario (for retry scenarios) |
| `delete_file` | path | Remove a file (to set up failure conditions) |

Each step has an optional `expect` block with key-value assertions on the operation result.

### Assertion types

| Type | Parameters | Checks |
|---|---|---|
| `plan_status` | expected | Final plan status matches |
| `phase_status` | phase_id, expected | Specific phase status matches |
| `trace_span_count` | filter, min?, max?, exact? | Span count in filtered set |
| `trace_metadata` | filter, key, expected | Metadata field value on matching span |
| `metric` | name, expected?, min?, max? | Computed metric within range |
| `file_exists` | path | File exists in workspace |
| `file_contains` | path, pattern | File content matches regex |
| `approval_status` | phase_id, expected | Approval document status |

---

## Extension 2: EvalScenario dataclass and loader

### Problem

Scenario YAMLs need parsing, validation, and standardized loading.

### Design

Add to `plan_utils.py`:

```python
@dataclass
class EvalStep:
    action: str
    phase_id: str | None = None
    expect: dict[str, Any] | None = None
    # Action-specific params stored as extra fields
    params: dict[str, Any] = field(default_factory=dict)

@dataclass
class EvalAssertion:
    type: str
    params: dict[str, Any] = field(default_factory=dict)

@dataclass
class EvalScenario:
    id: str
    description: str
    setup: dict[str, Any]
    steps: list[EvalStep]
    assertions: list[EvalAssertion]
    tags: list[str] = field(default_factory=list)
```

Loader functions:
- `load_eval_scenario(path: Path) -> EvalScenario` — parse and validate a single YAML file
- `load_eval_suite(directory: Path) -> list[EvalScenario]` — load all `.yaml` files in directory
- `validate_eval_scenario(scenario: EvalScenario)` — check that referenced phase_ids exist in setup plan, step actions are valid, assertion types are known

---

## Extension 3: Eval runner

### Problem

Need a way to execute scenarios in isolated environments and collect results.

### Design

New module: `core/tools/agent_memory_mcp/eval_utils.py`

```python
@dataclass
class StepResult:
    step_index: int
    action: str
    status: str  # "pass", "fail", "error"
    detail: str | None = None
    duration_ms: int | None = None

@dataclass
class AssertionResult:
    assertion_index: int
    type: str
    status: str  # "pass", "fail"
    expected: Any = None
    actual: Any = None

@dataclass
class ScenarioResult:
    scenario_id: str
    status: str  # "pass", "fail", "error"
    step_results: list[StepResult]
    assertion_results: list[AssertionResult]
    metrics: dict[str, float]
    duration_ms: int
    timestamp: str

def run_scenario(scenario: EvalScenario, root: Path, session_id: str) -> ScenarioResult:
    """Execute a scenario in the given root directory.

    Uses plan_utils functions directly (not MCP tools) for speed.
    Each step calls the corresponding plan_utils function, checks expect
    blocks, and records traces.
    """
    ...

def run_suite(scenarios: list[EvalScenario], root: Path, session_id: str) -> list[ScenarioResult]:
    """Run all scenarios, each in its own temp subdirectory."""
    ...
```

### Execution model

1. For each scenario, create a temporary subdirectory under `root`
2. Set up the plan by constructing and saving a `PlanDocument` from `setup.plan`
3. Create any `setup.files` and register `setup.registry_tools`
4. Execute each step sequentially, calling `plan_utils` helpers directly:
   - `start_phase` → find phase, set `status="in-progress"`, save
   - `complete_phase` → set commit, increment sessions_used, optionally verify
   - `verify_phase` → call `verify_postconditions()`
   - `record_failure` → append `PhaseFailure` to phase
   - `request_approval` / `resolve_approval` → create/load/save approval docs
   - `create_file` / `delete_file` → direct filesystem operations
5. After each step, check `expect` block and record `StepResult`
6. After all steps, evaluate `assertions` against final state
7. Compute metrics from trace data and plan state

### Metrics computation

```python
def compute_eval_metrics(
    scenario: EvalScenario,
    plan: PlanDocument,
    traces: list[dict],
) -> dict[str, float]:
    """Compute standard metrics for a completed scenario run."""
    return {
        "task_success": 1.0 if plan.status == "completed" else 0.0,
        "steps_to_success": ...,
        "retry_rate": total_failures / total_attempts,
        "verification_pass_rate": passed / (passed + failed),
        "tool_call_count": len([t for t in traces if t["span_type"] == "tool_call"]),
        "error_rate": errors / total_spans,
        "human_intervention_count": len([t for t in traces if "approval" in t.get("name", "")]),
    }
```

---

## Extension 4: MCP tools

### `memory_run_eval`

```
Parameters:
  - scenario_id: str | None  — run a specific scenario (by id)
  - tag: str | None           — run all scenarios matching a tag
  - session_id: str           — session for trace recording

Returns:
  - results: list of ScenarioResult dicts
  - summary: {total, passed, failed, errors}
  - metrics: aggregated metrics across all scenarios

Security: Gated behind ENGRAM_TIER2 (calls verify_postconditions which may execute shell commands).
```

### `memory_eval_report`

```
Parameters:
  - date_from: str | None   — YYYY-MM-DD
  - date_to: str | None
  - scenario_id: str | None — filter to specific scenario

Returns:
  - runs: historical results (from eval TRACES or a results log)
  - trends: metric trends over time (if multiple runs exist)
```

---

## Extension 5: Seed scenarios

Five initial scenarios covering each of the five completed phases:

1. **basic-plan-lifecycle** — create plan, start/complete phases, verify postconditions (Phases 1, 2)
2. **verification-failure-retry** — fail verification, record failure, fix, re-verify (Phase 2)
3. **trace-recording-validation** — execute plan operations, validate trace span coverage (Phase 3)
4. **tool-policy-integration** — register tool, create plan with matching postcondition, verify phase_payload includes policy (Phase 4)
5. **approval-pause-resume** — start requires_approval phase, auto-pause, resolve, resume, complete (Phase 5)

Optional additional scenarios:
6. **budget-exhaustion** — exceed session budget, verify warnings
7. **approval-expiry** — create approval, simulate expiry, verify plan blocked
8. **multi-phase-pipeline** — plan with 3+ phases, dependencies, mixed postcondition types

---

## Storage

```
core/memory/skills/eval-scenarios/
├── SUMMARY.md
├── basic-plan-lifecycle.yaml
├── verification-failure-retry.yaml
├── trace-recording-validation.yaml
├── tool-policy-integration.yaml
└── approval-pause-resume.yaml
```

Eval results are recorded as trace spans (span_type: `verification`, name: `eval:{scenario_id}`) in TRACES.jsonl, not in a separate log. This keeps the observability story unified.

---

## Implementation notes

- `eval_utils.py` is a new module (~200-300 lines), not an addition to `plan_utils.py` (which is already 1277 lines)
- The runner does NOT use the MCP server — it calls `plan_utils` functions directly. This avoids async complexity and git repo requirements in test environments
- Scenarios operate on `tempfile.TemporaryDirectory()` roots, completely isolated
- The `memory_run_eval` MCP tool wraps the runner with proper root/session_id context
- Metric names are standardized: `task_success`, `steps_to_success`, `retry_rate`, `verification_pass_rate`, `error_rate`, `human_intervention_count`
