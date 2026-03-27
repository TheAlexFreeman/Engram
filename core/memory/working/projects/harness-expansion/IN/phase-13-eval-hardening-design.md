---
source: agent-generated
trust: medium
origin_session: memory/activity/2026/03/27/chat-003
created: 2026-03-27
title: "Phase 13: Eval Hardening Design"
---

# Phase 13: Eval Hardening Design

## Isolation

**Decision: tmpdir (not git worktrees).** `run_suite()` already wraps each scenario in a `tempfile.TemporaryDirectory`. This is the right approach because eval environments are pristine test directories — no git history needed. Git worktrees would add complexity without benefit.

**Change:** Add `isolated: bool = False` parameter to `run_scenario()`. When `True`, the scenario executes in a fresh tmpdir that is cleaned up after the run. `run_suite()` already passes `True` implicitly.

## CI Integration

A pytest file (`test_eval_scenarios.py`) discovers all YAML scenarios in `memory/skills/eval-scenarios/` and creates a parameterized test for each. Marked with `@pytest.mark.eval` so CI can run `pytest -m eval` separately from unit tests.

## History and Regression Detection

**History:** After each `run_suite()` call, results are appended to `eval-history.jsonl` in the eval scenarios directory. Each line is a JSON object with `scenario_id`, `timestamp`, `status`, `metrics`, and `duration_ms`.

**Regression detection:** `compare_eval_runs(current, previous)` compares two `ScenarioResult` lists. A regression is: a scenario that was `pass` in `previous` but is `fail` or `error` in `current`, or a metric that degrades by more than a configurable threshold (default 10%).

**Regression threshold:** 10% metric degradation triggers a warning. Any pass-to-fail transition is a hard failure.

## New Scenarios

YAML scenarios for Phase 10-12 features, covering run state, policy enforcement, and guard pipeline.
