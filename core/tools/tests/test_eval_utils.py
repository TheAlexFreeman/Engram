from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml
from engram_mcp.agent_memory_mcp.errors import ValidationError
from engram_mcp.agent_memory_mcp.eval_utils import (
    EvalAssertion,
    EvalScenario,
    EvalStep,
    compute_eval_metrics,
    eval_scenarios_dir,
    load_scenario,
    load_suite,
    run_scenario,
    run_suite,
    select_scenarios,
)
from engram_mcp.agent_memory_mcp.plan_utils import PlanDocument, PlanPhase, PlanPurpose


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def _basic_scenario_dict() -> dict:
    return {
        "id": "basic-plan-lifecycle",
        "description": "Run a basic lifecycle scenario.",
        "setup": {
            "plan": {
                "id": "eval-basic",
                "project": "eval-suite",
                "phases": [
                    {
                        "id": "phase-one",
                        "title": "Create output",
                        "postconditions": [
                            {
                                "description": "Output exists",
                                "type": "check",
                                "target": "memory/working/notes/eval.txt",
                            }
                        ],
                        "changes": [
                            {
                                "path": "memory/working/notes/eval.txt",
                                "action": "create",
                                "description": "Create eval file",
                            }
                        ],
                    }
                ],
            },
            "files": [
                {
                    "path": "memory/working/notes/eval.txt",
                    "content": "hello from eval\n",
                }
            ],
        },
        "steps": [
            {
                "action": "start_phase",
                "phase_id": "phase-one",
                "expect": {"phase_status": "in-progress"},
            },
            {"action": "verify_phase", "phase_id": "phase-one", "expect": {"all_passed": True}},
            {
                "action": "complete_phase",
                "phase_id": "phase-one",
                "commit_sha": "eval-001",
                "verify": True,
                "expect": {"phase_status": "completed", "plan_status": "completed"},
            },
        ],
        "assertions": [
            {"type": "plan_status", "expected": "completed"},
            {"type": "phase_status", "phase_id": "phase-one", "expected": "completed"},
            {"type": "file_exists", "path": "memory/working/notes/eval.txt"},
            {"type": "metric", "name": "task_success", "expected": 1.0},
        ],
    }


class TestEvalSchema(unittest.TestCase):
    def test_eval_step_rejects_unknown_action(self) -> None:
        with self.assertRaises(ValidationError):
            EvalStep(action="explode")

    def test_eval_assertion_rejects_unknown_type(self) -> None:
        with self.assertRaises(ValidationError):
            EvalAssertion(type="explode")

    def test_load_scenario_parses_valid_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, _basic_scenario_dict())

            scenario = load_scenario(scenario_path)

        self.assertEqual(scenario.id, "basic-plan-lifecycle")
        self.assertEqual(len(scenario.steps), 3)
        self.assertEqual(scenario.steps[0].action, "start_phase")
        self.assertEqual(scenario.assertions[0].type, "plan_status")

    def test_load_scenario_rejects_unknown_step_phase(self) -> None:
        payload = _basic_scenario_dict()
        payload["steps"][0]["phase_id"] = "missing-phase"
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, payload)
            with self.assertRaises(ValidationError):
                load_scenario(scenario_path)

    def test_load_scenario_rejects_unknown_metric_name(self) -> None:
        payload = _basic_scenario_dict()
        payload["assertions"].append({"type": "metric", "name": "mystery", "expected": 1.0})
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, payload)
            with self.assertRaises(ValidationError):
                load_scenario(scenario_path)

    def test_load_suite_returns_sorted_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _basic_scenario_dict()
            second = _basic_scenario_dict()
            first["id"] = "b-scenario"
            second["id"] = "a-scenario"
            _write_yaml(root / "b.yaml", first)
            _write_yaml(root / "a.yaml", second)

            loaded = load_suite(root)

        self.assertEqual([scenario.id for scenario in loaded], ["a-scenario", "b-scenario"])

    def test_load_scenario_requires_complete_phase_commit_sha(self) -> None:
        payload = _basic_scenario_dict()
        payload["steps"][2].pop("commit_sha")
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, payload)
            with self.assertRaises(ValidationError):
                load_scenario(scenario_path)

    def test_load_scenario_requires_resolve_approval_resolution(self) -> None:
        payload = _basic_scenario_dict()
        payload["setup"]["plan"]["phases"][0]["requires_approval"] = True
        payload["steps"] = [
            {"action": "resolve_approval", "phase_id": "phase-one"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, payload)
            with self.assertRaises(ValidationError):
                load_scenario(scenario_path)


class TestEvalRunner(unittest.TestCase):
    def test_run_scenario_passes_basic_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, _basic_scenario_dict())
            scenario = load_scenario(scenario_path)

            result = run_scenario(
                scenario, Path(tmp) / "run", "memory/activity/2026/03/27/chat-101"
            )

        self.assertEqual(result.status, "pass")
        self.assertEqual(result.metrics["task_success"], 1.0)
        self.assertTrue(all(step.status == "pass" for step in result.step_results))

    def test_run_scenario_handles_verification_failure_then_retry(self) -> None:
        payload = _basic_scenario_dict()
        payload["setup"]["files"] = []
        payload["steps"] = [
            {
                "action": "start_phase",
                "phase_id": "phase-one",
                "expect": {"phase_status": "in-progress"},
            },
            {"action": "verify_phase", "phase_id": "phase-one", "expect": {"all_passed": False}},
            {"action": "record_failure", "phase_id": "phase-one", "reason": "missing output"},
            {
                "action": "create_file",
                "path": "memory/working/notes/eval.txt",
                "content": "hello\n",
            },
            {"action": "verify_phase", "phase_id": "phase-one", "expect": {"all_passed": True}},
            {"action": "complete_phase", "phase_id": "phase-one", "commit_sha": "eval-002"},
        ]
        payload["assertions"] = [
            {"type": "metric", "name": "retry_rate", "expected": 0.5},
            {"type": "plan_status", "expected": "completed"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, payload)
            scenario = load_scenario(scenario_path)

            result = run_scenario(
                scenario, Path(tmp) / "run", "memory/activity/2026/03/27/chat-102"
            )

        self.assertEqual(result.status, "pass")
        self.assertEqual(result.metrics["retry_rate"], 0.5)

    def test_run_scenario_supports_approval_pause_resume(self) -> None:
        payload = _basic_scenario_dict()
        payload["setup"]["plan"]["phases"][0]["requires_approval"] = True
        payload["steps"] = [
            {
                "action": "start_phase",
                "phase_id": "phase-one",
                "expect": {"plan_status": "paused", "approval_status": "pending"},
            },
            {
                "action": "resolve_approval",
                "phase_id": "phase-one",
                "resolution": "approve",
                "expect": {"approval_status": "approved", "plan_status": "active"},
            },
            {
                "action": "start_phase",
                "phase_id": "phase-one",
                "expect": {"phase_status": "in-progress"},
            },
            {
                "action": "complete_phase",
                "phase_id": "phase-one",
                "commit_sha": "eval-003",
                "verify": True,
            },
        ]
        payload["assertions"] = [
            {"type": "approval_status", "phase_id": "phase-one", "expected": "approved"},
            {"type": "metric", "name": "human_intervention_count", "min": 2.0},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, payload)
            scenario = load_scenario(scenario_path)

            result = run_scenario(
                scenario, Path(tmp) / "run", "memory/activity/2026/03/27/chat-103"
            )

        self.assertEqual(result.status, "pass")
        self.assertGreaterEqual(result.metrics["human_intervention_count"], 2.0)

    def test_run_scenario_reports_failed_assertions(self) -> None:
        payload = _basic_scenario_dict()
        payload["assertions"] = [
            {"type": "trace_span_count", "filter": {"span_type": "plan_action"}, "exact": 99}
        ]
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, payload)
            scenario = load_scenario(scenario_path)

            result = run_scenario(
                scenario, Path(tmp) / "run", "memory/activity/2026/03/27/chat-104"
            )

        self.assertEqual(result.status, "fail")
        self.assertEqual(result.assertion_results[0].status, "fail")

    def test_run_scenario_reports_step_errors(self) -> None:
        payload = _basic_scenario_dict()
        payload["steps"] = [
            {"action": "resolve_approval", "phase_id": "phase-one", "resolution": "approve"}
        ]
        payload["assertions"] = []
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, payload)
            scenario = load_scenario(scenario_path)

            result = run_scenario(
                scenario, Path(tmp) / "run", "memory/activity/2026/03/27/chat-105"
            )

        self.assertEqual(result.status, "error")
        self.assertEqual(result.step_results[0].status, "error")

    def test_run_scenario_supports_file_contains_assertion(self) -> None:
        payload = _basic_scenario_dict()
        payload["assertions"].append(
            {
                "type": "file_contains",
                "path": "memory/working/notes/eval.txt",
                "pattern": "hello from eval",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, payload)
            scenario = load_scenario(scenario_path)

            result = run_scenario(
                scenario, Path(tmp) / "run", "memory/activity/2026/03/27/chat-106"
            )

        self.assertEqual(result.status, "pass")

    def test_run_suite_executes_multiple_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first_payload = _basic_scenario_dict()
            second_payload = _basic_scenario_dict()
            second_payload["id"] = "second-scenario"
            _write_yaml(Path(tmp) / "a.yaml", first_payload)
            _write_yaml(Path(tmp) / "b.yaml", second_payload)
            scenarios = load_suite(Path(tmp))

            results = run_suite(
                scenarios, Path(tmp) / "suite", "memory/activity/2026/03/27/chat-107"
            )

        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.status == "pass" for result in results))


class TestEvalMetrics(unittest.TestCase):
    def test_compute_eval_metrics_counts_trace_signals(self) -> None:
        scenario = EvalScenario(
            id="fake-scenario",
            description="Fake",
            setup={
                "plan": {
                    "id": "fake",
                    "project": "fake",
                    "phases": [
                        {
                            "id": "phase-one",
                            "title": "Phase one",
                            "changes": [
                                {
                                    "path": "memory/working/notes/fake.md",
                                    "action": "create",
                                    "description": "Create fake file",
                                }
                            ],
                        }
                    ],
                }
            },
            steps=[EvalStep(action="create_file", params={"path": "memory/working/notes/fake.md"})],
            assertions=[],
        )
        plan = PlanDocument(
            id="eval-plan",
            project="eval-suite",
            created="2026-03-27",
            origin_session="memory/activity/2026/03/27/chat-108",
            status="completed",
            purpose=PlanPurpose(summary="Eval plan", context="Metrics test."),
            phases=[PlanPhase(id="phase-one", title="Phase one")],
        )
        traces = [
            {"span_type": "plan_action", "name": "start", "status": "ok"},
            {
                "span_type": "verification",
                "name": "verify:phase-one",
                "status": "ok",
                "metadata": {"passed": 1, "failed": 0},
            },
            {"span_type": "plan_action", "name": "approval-requested", "status": "ok"},
            {"span_type": "plan_action", "name": "approval-approved", "status": "ok"},
            {"span_type": "tool_call", "name": "tool", "status": "error"},
        ]
        metrics = compute_eval_metrics(scenario, plan, traces)
        self.assertEqual(metrics["task_success"], 1.0)
        self.assertEqual(metrics["verification_pass_rate"], 1.0)
        self.assertEqual(metrics["error_rate"], 0.2)
        self.assertEqual(metrics["human_intervention_count"], 2.0)

    def test_run_scenario_writes_trace_metadata_for_assertions(self) -> None:
        payload = _basic_scenario_dict()
        payload["assertions"] = [
            {
                "type": "trace_metadata",
                "filter": {"span_type": "verification"},
                "key": "passed",
                "expected": 1,
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            scenario_path = Path(tmp) / "scenario.yaml"
            _write_yaml(scenario_path, payload)
            scenario = load_scenario(scenario_path)

            result = run_scenario(
                scenario, Path(tmp) / "run", "memory/activity/2026/03/27/chat-109"
            )

        self.assertEqual(result.status, "pass")


class TestSeedEvalScenarios(unittest.TestCase):
    def test_seed_suite_exposes_expected_scenarios(self) -> None:
        root = Path(__file__).resolve().parents[2]
        scenarios = load_suite(eval_scenarios_dir(root))

        expected_ids = {
            "approval-pause-resume",
            "basic-plan-lifecycle",
            "guard-pipeline-blocking",
            "policy-enforcement-eval",
            "run-state-checkpoint-resume",
            "run-state-failure-recovery",
            "tool-policy-integration",
            "trace-recording-validation",
            "verification-failure-retry",
        }
        self.assertEqual({scenario.id for scenario in scenarios}, expected_ids)
        approval_only = select_scenarios(root, tag="approval")
        self.assertEqual([scenario.id for scenario in approval_only], ["approval-pause-resume"])

    def test_seed_suite_runs_successfully(self) -> None:
        root = Path(__file__).resolve().parents[2]
        scenarios = load_suite(eval_scenarios_dir(root))

        with tempfile.TemporaryDirectory() as tmp:
            results = run_suite(
                scenarios,
                Path(tmp) / "seed-suite",
                "memory/activity/2026/03/27/chat-110",
            )

        self.assertEqual(len(results), 9)
        self.assertTrue(all(result.status == "pass" for result in results))


if __name__ == "__main__":
    unittest.main()
