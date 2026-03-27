"""Pytest-based eval scenario runner for CI integration.

Discovers all YAML scenarios in memory/skills/eval-scenarios/ and runs each
as a parameterized test case.  Use ``pytest -m eval`` to run eval scenarios
separately from unit tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from engram_mcp.agent_memory_mcp.eval_utils import (
    eval_scenarios_dir,
    load_suite,
    run_scenario,
)

_EVAL_SESSION_ID = "memory/activity/2026/03/27/chat-000"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _discover_scenarios():
    scenarios_dir = eval_scenarios_dir(_REPO_ROOT)
    if not scenarios_dir.exists():
        return []
    return load_suite(scenarios_dir)


_SCENARIOS = _discover_scenarios()


@pytest.mark.eval
@pytest.mark.parametrize(
    "scenario",
    _SCENARIOS,
    ids=[s.id for s in _SCENARIOS],
)
def test_eval_scenario(scenario, tmp_path):
    result = run_scenario(scenario, tmp_path, _EVAL_SESSION_ID)
    failures = []
    for step_result in result.step_results:
        if step_result.status == "error":
            failures.append(
                f"Step {step_result.step_index} ({step_result.action}): {step_result.detail}"
            )
    for assertion_result in result.assertion_results:
        if assertion_result.status == "fail":
            failures.append(
                f"Assertion {assertion_result.assertion_index} ({assertion_result.type}): "
                f"expected={assertion_result.expected}, actual={assertion_result.actual}"
            )
    assert result.status == "pass", f"Scenario {scenario.id} failed:\n" + "\n".join(failures)
