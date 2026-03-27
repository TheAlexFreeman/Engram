# Eval Scenarios

Declarative offline evaluation fixtures consumed by `memory_run_eval` and summarized by `memory_eval_report`.

These files are not conversational skills. They are scenario definitions used to exercise the harness workflow end-to-end against isolated temporary roots.

## Included scenarios

| Scenario | Tags | Coverage |
|---|---|---|
| `basic-plan-lifecycle` | `core`, `lifecycle` | Start, verify, and complete a simple one-phase plan. |
| `verification-failure-retry` | `core`, `verification`, `retry` | Fail verification, record failure context, repair state, and retry successfully. |
| `trace-recording-validation` | `core`, `observability`, `traces` | Validate expected `plan_action` and `verification` span coverage. |
| `tool-policy-integration` | `core`, `tool-policy`, `registry` | Seed registry policy data during setup and verify registry artifacts are available to the run. |
| `approval-pause-resume` | `core`, `approval`, `hitl` | Pause on approval, resolve it, resume execution, and complete the phase. |

## Usage

- Run the full suite with `memory_run_eval(session_id=...)`.
- Filter a single scenario with `scenario_id`.
- Filter a subset with `tag`.

All results are recorded as compact `verification` spans named `eval:{scenario_id}` in the session trace.
