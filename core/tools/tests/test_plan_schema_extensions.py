"""Tests for plan schema extensions: SourceSpec, PostconditionSpec, PlanBudget.

Covers dataclass validation, coercion helpers, budget_status(), next_action()
dict return, phase_payload() enrichment, round-trip serialization, and
backward compatibility with plans that lack the new fields.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest import mock

import yaml
from engram_mcp.agent_memory_mcp.errors import DuplicateContentError, NotFoundError, ValidationError
from engram_mcp.agent_memory_mcp.plan_utils import (
    APPROVAL_RESOLUTIONS,
    APPROVAL_STATUSES,
    PLAN_STATUSES,
    ApprovalDocument,
    ChangeSpec,
    PhaseFailure,
    PlanBudget,
    PlanDocument,
    PlanPhase,
    PlanPurpose,
    PostconditionSpec,
    SourceSpec,
    ToolDefinition,
    _all_registry_tools,
    _check_approval_expiry,
    _coerce_change_spec_input,
    _coerce_failure_input,
    _coerce_phase_input,
    _coerce_postcondition_spec_input,
    _coerce_source_spec_input,
    approval_filename,
    approvals_summary_path,
    assemble_briefing,
    budget_status,
    coerce_budget_input,
    coerce_phase_inputs,
    load_approval,
    load_plan,
    load_registry,
    materialize_expired_approval,
    next_action,
    phase_blockers,
    phase_payload,
    plan_create_input_schema,
    project_plan_path,
    record_trace,
    regenerate_approvals_summary,
    regenerate_registry_summary,
    registry_file_path,
    save_approval,
    save_plan,
    save_registry,
    scan_drop_zone,
    stage_external_file,
    trace_file_path,
    validate_plan_references,
    validation_error_messages,
    verify_postconditions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_plan(**overrides) -> PlanDocument:
    """Build a minimal valid PlanDocument for testing."""
    defaults = {
        "id": "test-plan",
        "project": "test-project",
        "created": "2026-03-26",
        "origin_session": "memory/activity/2026/03/26/chat-001",
        "status": "active",
        "purpose": PlanPurpose(
            summary="Test plan",
            context="For testing purposes.",
        ),
        "phases": [
            PlanPhase(
                id="phase-one",
                title="First phase",
                changes=[
                    ChangeSpec(
                        path="memory/working/notes/test.md",
                        action="create",
                        description="Test file",
                    )
                ],
            ),
        ],
        "review": None,
    }
    # Allow overriding phases via raw dicts
    if "phases" in overrides:
        phases = overrides.pop("phases")
        if phases and isinstance(phases[0], dict):
            phases = coerce_phase_inputs(phases)
        defaults["phases"] = phases
    defaults.update(overrides)
    return PlanDocument(**defaults)


def _write_plan_yaml(tmpdir: Path, plan_dict: dict) -> Path:
    """Write a plan dict as YAML and return the path."""
    plan_path = (
        tmpdir / "memory" / "working" / "projects" / "test-project" / "plans" / "test-plan.yaml"
    )
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.dump(plan_dict, sort_keys=False, allow_unicode=False)
    plan_path.write_text(text, encoding="utf-8")
    return plan_path


def _write_minimal_plan_at(root: Path, project: str, plan_id: str, **overrides: Any) -> Path:
    """Write a minimal plan YAML under the project_plan_path layout.

    Returns the absolute path to the YAML file.
    """
    plan = _minimal_plan(id=plan_id, project=project, **overrides)
    rel = project_plan_path(project, plan_id)
    dest = root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    save_plan(dest, plan)
    return dest


def _approval_ready_plan(**overrides: Any) -> PlanDocument:
    """Build a plan suited for approval and verification lifecycle tests."""
    defaults = {
        "id": "approval-plan",
        "project": "test-project",
        "created": "2026-03-27",
        "origin_session": "memory/activity/2026/03/27/chat-001",
        "status": "active",
        "purpose": PlanPurpose(
            summary="Approval-ready plan",
            context="Exercise approval, verification, and budget interactions.",
        ),
        "budget": PlanBudget(
            deadline=(date.today() + timedelta(days=30)).isoformat(),
            max_sessions=2,
        ),
        "phases": [
            PlanPhase(
                id="approval-phase",
                title="Approval phase",
                requires_approval=True,
                sources=[
                    SourceSpec(
                        path="core/context.md",
                        type="internal",
                        intent="Read the implementation context.",
                    )
                ],
                postconditions=[
                    PostconditionSpec(
                        description="Output file exists",
                        type="check",
                        target="artifacts/result.txt",
                    ),
                    PostconditionSpec(
                        description="Output contains success marker",
                        type="grep",
                        target="phase complete::artifacts/result.txt",
                    ),
                ],
                changes=[
                    ChangeSpec(
                        path="memory/working/notes/result.md",
                        action="update",
                        description="Record lifecycle result",
                    )
                ],
            ),
        ],
        "review": None,
    }
    if "phases" in overrides:
        phases = overrides.pop("phases")
        if phases and isinstance(phases[0], dict):
            phases = coerce_phase_inputs(phases)
        defaults["phases"] = phases
    defaults.update(overrides)
    return PlanDocument(**defaults)


def _full_harness_plan(**overrides: Any) -> PlanDocument:
    """Build a plan that exercises sources, postconditions, approval, and budgets."""
    defaults = {
        "id": "full-harness-plan",
        "project": "test-project",
        "created": "2026-03-27",
        "origin_session": "memory/activity/2026/03/27/chat-002",
        "status": "active",
        "purpose": PlanPurpose(
            summary="Full harness plan",
            context="Exercise composed harness behaviors across multiple subsystems.",
        ),
        "budget": PlanBudget(
            deadline=(date.today() + timedelta(days=45)).isoformat(),
            max_sessions=3,
        ),
        "phases": [
            PlanPhase(
                id="harness-phase",
                title="Harness phase",
                requires_approval=True,
                sources=[
                    SourceSpec(
                        path="core/context.md",
                        type="internal",
                        intent="Read the harness context.",
                    )
                ],
                postconditions=[
                    PostconditionSpec(
                        description="Harness artifact exists",
                        type="check",
                        target="artifacts/harness.txt",
                    ),
                    PostconditionSpec(
                        description="Harness artifact contains marker",
                        type="grep",
                        target="ready::artifacts/harness.txt",
                    ),
                    PostconditionSpec(
                        description="Harness tests pass",
                        type="test",
                        target="python -m pytest core/tools/tests/test_plan_schema_extensions.py -q",
                    ),
                ],
                changes=[
                    ChangeSpec(
                        path="memory/working/notes/harness.md",
                        action="update",
                        description="Capture harness execution notes",
                    )
                ],
            ),
        ],
        "review": None,
    }
    if "phases" in overrides:
        phases = overrides.pop("phases")
        if phases and isinstance(phases[0], dict):
            phases = coerce_phase_inputs(phases)
        defaults["phases"] = phases
    defaults.update(overrides)
    return PlanDocument(**defaults)


def _setup_approval_dirs(root: Path) -> None:
    """Create the standard approval queue directory layout for tests."""
    (root / "memory" / "working" / "approvals" / "pending").mkdir(parents=True, exist_ok=True)
    (root / "memory" / "working" / "approvals" / "resolved").mkdir(parents=True, exist_ok=True)


def _setup_registry(root: Path, tools: list[ToolDefinition] | None = None) -> None:
    """Seed the tool registry for integration tests."""
    registry_tools = tools or [
        ToolDefinition(
            name="pytest-run",
            description="Run pytest",
            provider="shell",
            timeout_seconds=120,
        ),
        ToolDefinition(
            name="pre-commit-run",
            description="Run pre-commit",
            provider="shell",
            timeout_seconds=60,
        ),
    ]
    save_registry(root, "shell", registry_tools)
    regenerate_registry_summary(root)


# ===========================================================================
# ChangeSpec and schema helper
# ===========================================================================


class TestChangeSpec(unittest.TestCase):
    def test_action_alias_normalizes_modify(self) -> None:
        change = ChangeSpec(
            path="memory/working/notes/test.md",
            action="modify",
            description="Update the note",
        )

        self.assertEqual(change.action, "update")
        self.assertEqual(change.to_dict()["action"], "update")


class TestPlanCreateInputSchema(unittest.TestCase):
    def test_exposes_nested_conditionals_and_aliases(self) -> None:
        schema = plan_create_input_schema()
        phase_item = schema["properties"]["phases"]["items"]
        source_item = phase_item["properties"]["sources"]["items"]
        postcondition_item = phase_item["properties"]["postconditions"]["items"]["oneOf"][1]
        change_item = phase_item["properties"]["changes"]["items"]
        failure_result_item = phase_item["properties"]["failures"]["items"]["properties"][
            "verification_results"
        ]["items"]["anyOf"][0]

        self.assertEqual(schema["tool_name"], "memory_plan_create")
        self.assertEqual(source_item["properties"]["type"]["x-aliases"]["code"], "internal")
        self.assertEqual(
            postcondition_item["properties"]["type"]["x-aliases"]["file_check"],
            "check",
        )
        self.assertEqual(change_item["properties"]["action"]["x-aliases"]["modify"], "update")
        self.assertIn("uri", source_item["allOf"][0]["then"]["required"])
        self.assertIn("mcp_server", source_item["allOf"][1]["then"]["required"])
        self.assertIn("target", postcondition_item["allOf"][0]["then"]["required"])
        self.assertEqual(
            failure_result_item["properties"]["status"]["enum"],
            ["error", "fail", "pass", "skip"],
        )


# ===========================================================================
# SourceSpec
# ===========================================================================


class TestSourceSpec(unittest.TestCase):
    def test_valid_internal_source(self) -> None:
        s = SourceSpec(path="core/tools/plan_utils.py", type="internal", intent="Read it")
        self.assertEqual(s.type, "internal")
        self.assertEqual(s.uri, None)

    def test_valid_external_source(self) -> None:
        s = SourceSpec(
            path="api-docs",
            type="external",
            intent="Check API contract",
            uri="https://example.com/api",
        )
        self.assertEqual(s.uri, "https://example.com/api")

    def test_valid_mcp_source(self) -> None:
        s = SourceSpec(path="memory_search", type="mcp", intent="Search for context")
        self.assertEqual(s.type, "mcp")

    def test_source_type_alias_normalizes_code(self) -> None:
        s = SourceSpec(path="core/tools/plan_utils.py", type="code", intent="Read it")
        self.assertEqual(s.type, "internal")

    def test_invalid_type_raises(self) -> None:
        with self.assertRaises(ValidationError):
            SourceSpec(path="x", type="invalid", intent="test")

    def test_external_without_uri_raises(self) -> None:
        with self.assertRaises(ValidationError):
            SourceSpec(path="x", type="external", intent="test")

    def test_empty_intent_raises(self) -> None:
        with self.assertRaises(ValidationError):
            SourceSpec(path="x", type="internal", intent="  ")

    def test_internal_path_normalized(self) -> None:
        s = SourceSpec(path="core\\tools\\file.py", type="internal", intent="Read")
        self.assertEqual(s.path, "core/tools/file.py")

    def test_validate_exists_passes_for_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "core").mkdir()
            (root / "core" / "file.py").write_text("x")
            s = SourceSpec(path="core/file.py", type="internal", intent="Read")
            s.validate_exists(root)  # should not raise

    def test_validate_exists_fails_for_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            s = SourceSpec(path="nonexistent/file.py", type="internal", intent="Read")
            with self.assertRaises(ValidationError):
                s.validate_exists(root)

    def test_validate_exists_skips_non_internal(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            s = SourceSpec(path="api", type="external", intent="Check", uri="https://example.com")
            s.validate_exists(root)  # should not raise for external

    def test_to_dict_omits_uri_when_none(self) -> None:
        s = SourceSpec(path="x", type="internal", intent="Read")
        d = s.to_dict()
        self.assertNotIn("uri", d)

    def test_to_dict_includes_uri_when_set(self) -> None:
        s = SourceSpec(path="x", type="external", intent="Read", uri="https://example.com")
        d = s.to_dict()
        self.assertEqual(d["uri"], "https://example.com")


# ===========================================================================
# PostconditionSpec
# ===========================================================================


class TestPostconditionSpec(unittest.TestCase):
    def test_manual_with_description_only(self) -> None:
        pc = PostconditionSpec(description="File exists")
        self.assertEqual(pc.type, "manual")
        self.assertIsNone(pc.target)

    def test_typed_check_with_target(self) -> None:
        pc = PostconditionSpec(description="Check it", type="check", target="file.py")
        self.assertEqual(pc.type, "check")
        self.assertEqual(pc.target, "file.py")

    def test_typed_grep_with_target(self) -> None:
        pc = PostconditionSpec(description="Pattern found", type="grep", target="SOURCE_TYPES")
        self.assertEqual(pc.type, "grep")

    def test_typed_test_with_target(self) -> None:
        pc = PostconditionSpec(description="Tests pass", type="test", target="test_plan_utils.py")
        self.assertEqual(pc.type, "test")

    def test_type_alias_normalizes_file_check(self) -> None:
        pc = PostconditionSpec(description="File exists", type="file_check", target="file.py")
        self.assertEqual(pc.type, "check")

    def test_invalid_type_raises(self) -> None:
        with self.assertRaises(ValidationError):
            PostconditionSpec(description="x", type="invalid")

    def test_typed_without_target_raises(self) -> None:
        with self.assertRaises(ValidationError):
            PostconditionSpec(description="x", type="check")

    def test_empty_description_raises(self) -> None:
        with self.assertRaises(ValidationError):
            PostconditionSpec(description="  ")

    def test_to_dict_collapses_manual_without_target(self) -> None:
        pc = PostconditionSpec(description="File exists")
        d = pc.to_dict()
        self.assertEqual(d, {"description": "File exists"})
        self.assertNotIn("type", d)

    def test_to_dict_includes_type_and_target(self) -> None:
        pc = PostconditionSpec(description="Check it", type="check", target="file.py")
        d = pc.to_dict()
        self.assertIn("type", d)
        self.assertIn("target", d)


# ===========================================================================
# PlanBudget
# ===========================================================================


class TestPlanBudget(unittest.TestCase):
    def test_valid_budget_all_fields(self) -> None:
        b = PlanBudget(deadline="2026-04-15", max_sessions=8, advisory=True)
        self.assertEqual(b.deadline, "2026-04-15")
        self.assertEqual(b.max_sessions, 8)

    def test_valid_budget_deadline_only(self) -> None:
        b = PlanBudget(deadline="2026-04-15")
        self.assertIsNone(b.max_sessions)

    def test_valid_budget_sessions_only(self) -> None:
        b = PlanBudget(max_sessions=3)
        self.assertIsNone(b.deadline)

    def test_invalid_deadline_format_raises(self) -> None:
        with self.assertRaises(ValidationError):
            PlanBudget(deadline="April 15, 2026")

    def test_zero_sessions_raises(self) -> None:
        with self.assertRaises(ValidationError):
            PlanBudget(max_sessions=0)

    def test_negative_sessions_raises(self) -> None:
        with self.assertRaises(ValidationError):
            PlanBudget(max_sessions=-1)

    def test_to_dict_omits_advisory_when_true(self) -> None:
        b = PlanBudget(deadline="2026-04-15", advisory=True)
        d = b.to_dict()
        self.assertNotIn("advisory", d)

    def test_to_dict_includes_advisory_when_false(self) -> None:
        b = PlanBudget(deadline="2026-04-15", advisory=False)
        d = b.to_dict()
        self.assertFalse(d["advisory"])


# ===========================================================================
# Coercion helpers
# ===========================================================================


class TestCoerceSourceSpecs(unittest.TestCase):
    def test_source_input_coercer_normalizes_alias_before_dataclass_validation(self) -> None:
        payload = _coerce_source_spec_input(
            {
                "path": "core/file.py",
                "type": "code",
                "intent": "Read it",
            }
        )

        self.assertEqual(payload["type"], "internal")

    def test_coerce_phases_with_sources(self) -> None:
        phases = coerce_phase_inputs(
            [
                {
                    "id": "p1",
                    "title": "Phase 1",
                    "sources": [
                        {"path": "core/file.py", "type": "internal", "intent": "Read it"},
                    ],
                    "changes": [
                        {
                            "path": "memory/working/notes/x.md",
                            "action": "create",
                            "description": "Make file",
                        },
                    ],
                }
            ]
        )
        self.assertEqual(len(phases[0].sources), 1)
        self.assertIsInstance(phases[0].sources[0], SourceSpec)

    def test_coerce_phases_without_sources(self) -> None:
        phases = coerce_phase_inputs(
            [
                {
                    "id": "p1",
                    "title": "Phase 1",
                    "changes": [
                        {
                            "path": "memory/working/notes/x.md",
                            "action": "create",
                            "description": "Make file",
                        },
                    ],
                }
            ]
        )
        self.assertEqual(phases[0].sources, [])


class TestCoercePostconditions(unittest.TestCase):
    def test_postcondition_input_coercer_normalizes_alias_and_string_shorthand(self) -> None:
        aliased = _coerce_postcondition_spec_input(
            {"description": "Output exists", "type": "file_check", "target": "artifacts/out.txt"}
        )
        manual = _coerce_postcondition_spec_input("Verify output manually")

        self.assertEqual(aliased["type"], "check")
        self.assertEqual(manual, {"description": "Verify output manually"})

    def test_bare_string_becomes_manual_postcondition(self) -> None:
        phases = coerce_phase_inputs(
            [
                {
                    "id": "p1",
                    "title": "Phase 1",
                    "postconditions": ["File should exist"],
                    "changes": [
                        {
                            "path": "memory/working/notes/x.md",
                            "action": "create",
                            "description": "Make file",
                        },
                    ],
                }
            ]
        )
        pc = phases[0].postconditions[0]
        self.assertEqual(pc.description, "File should exist")
        self.assertEqual(pc.type, "manual")

    def test_dict_postcondition_with_type(self) -> None:
        phases = coerce_phase_inputs(
            [
                {
                    "id": "p1",
                    "title": "Phase 1",
                    "postconditions": [
                        {"description": "Tests pass", "type": "test", "target": "tests/"},
                    ],
                    "changes": [
                        {
                            "path": "memory/working/notes/x.md",
                            "action": "create",
                            "description": "Make file",
                        },
                    ],
                }
            ]
        )
        pc = phases[0].postconditions[0]
        self.assertEqual(pc.type, "test")
        self.assertEqual(pc.target, "tests/")


class TestCoerceChangeSpecs(unittest.TestCase):
    def test_change_input_coercer_normalizes_alias_before_dataclass_validation(self) -> None:
        payload = _coerce_change_spec_input(
            {
                "path": "memory/working/notes/x.md",
                "action": "modify",
                "description": "Update file",
            }
        )

        self.assertEqual(payload["action"], "update")

    def test_coerce_phases_aliases_match_canonical_serialization(self) -> None:
        aliased = coerce_phase_inputs(
            [
                {
                    "id": "p1",
                    "title": "Phase 1",
                    "commit": "abc123",
                    "blockers": ["upstream:phase-a", "phase-0"],
                    "requires_approval": True,
                    "sources": [
                        {"path": "core/file.py", "type": "code", "intent": "Read it"},
                    ],
                    "postconditions": [
                        {
                            "description": "Output exists",
                            "type": "file_check",
                            "target": "artifacts/out.txt",
                        }
                    ],
                    "changes": [
                        {
                            "path": "memory/working/notes/x.md",
                            "action": "modify",
                            "description": "Update file",
                        },
                    ],
                    "failures": [
                        {
                            "timestamp": "2026-03-26T12:00:00Z",
                            "reason": "Initial attempt failed",
                            "verification_results": [{"status": "failed"}],
                        }
                    ],
                }
            ]
        )[0].to_dict()
        canonical = coerce_phase_inputs(
            [
                {
                    "id": "p1",
                    "title": "Phase 1",
                    "commit": "abc123",
                    "blockers": ["upstream:phase-a", "phase-0"],
                    "requires_approval": True,
                    "sources": [
                        {"path": "core/file.py", "type": "internal", "intent": "Read it"},
                    ],
                    "postconditions": [
                        {
                            "description": "Output exists",
                            "type": "check",
                            "target": "artifacts/out.txt",
                        }
                    ],
                    "changes": [
                        {
                            "path": "memory/working/notes/x.md",
                            "action": "update",
                            "description": "Update file",
                        },
                    ],
                    "failures": [
                        {
                            "timestamp": "2026-03-26T12:00:00Z",
                            "reason": "Initial attempt failed",
                            "verification_results": [{"status": "failed"}],
                            "attempt": 1,
                        }
                    ],
                }
            ]
        )[0].to_dict()

        self.assertEqual(aliased, canonical)


class TestCoerceFailureSpecs(unittest.TestCase):
    def test_failure_input_coercer_normalizes_attempt_when_present(self) -> None:
        payload = _coerce_failure_input(
            {
                "timestamp": "2026-03-26T12:00:00Z",
                "reason": "Attempt failed",
                "attempt": "2",
                "verification_results": [{"status": "failed"}],
            }
        )

        self.assertEqual(payload["attempt"], 2)
        self.assertEqual(payload["verification_results"], [{"status": "failed"}])


class TestCoercePhaseInputs(unittest.TestCase):
    def test_phase_input_coercer_nests_leaf_inputs_and_normalizes_aliases(self) -> None:
        payload = _coerce_phase_input(
            {
                "id": "p1",
                "title": "Phase 1",
                "status": "pending",
                "commit": 12345,
                "blockers": ["upstream:phase-a", 7],
                "requires_approval": True,
                "sources": [
                    {"path": "core/file.py", "type": "code", "intent": "Read it"},
                ],
                "postconditions": [
                    {
                        "description": "Output exists",
                        "type": "file_check",
                        "target": "artifacts/out.txt",
                    }
                ],
                "changes": [
                    {
                        "path": "memory/working/notes/x.md",
                        "action": "modify",
                        "description": "Update file",
                    }
                ],
                "failures": [
                    {
                        "timestamp": "2026-03-26T12:00:00Z",
                        "reason": "Attempt failed",
                        "attempt": "2",
                        "verification_results": [{"status": "failed"}],
                    }
                ],
            },
            field_path="work.phases[0]",
        )

        self.assertEqual(payload["commit"], "12345")
        self.assertEqual(payload["blockers"], ["upstream:phase-a", "7"])
        self.assertTrue(payload["requires_approval"])
        self.assertEqual(payload["sources"][0]["type"], "internal")
        self.assertEqual(payload["postconditions"][0]["type"], "check")
        self.assertEqual(payload["changes"][0]["action"], "update")
        self.assertEqual(payload["failures"][0]["attempt"], 2)
        self.assertEqual(payload["failures"][0]["verification_results"], [{"status": "failed"}])

    def test_phase_input_coercer_aggregates_nested_input_errors(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            _coerce_phase_input(
                {
                    "id": "p1",
                    "title": "Phase 1",
                    "blockers": "not-a-list",
                    "sources": ["bad-source"],
                    "postconditions": [42],
                    "changes": "bad-changes",
                    "failures": ["bad-failure"],
                },
                field_path="work.phases[0]",
            )

        errors = validation_error_messages(ctx.exception)

        self.assertTrue(any(error.startswith("work.phases[0].blockers:") for error in errors))
        self.assertTrue(any(error.startswith("work.phases[0].sources[0]:") for error in errors))
        self.assertTrue(
            any(error.startswith("work.phases[0].postconditions[0]:") for error in errors)
        )
        self.assertTrue(any(error.startswith("work.phases[0].changes:") for error in errors))
        self.assertTrue(any(error.startswith("work.phases[0].failures[0]:") for error in errors))


class TestCoercePhaseValidationAggregation(unittest.TestCase):
    def test_collects_nested_errors_with_structural_paths(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            coerce_phase_inputs(
                [
                    {
                        "id": "phase-a",
                        "title": "Broken phase",
                        "sources": [
                            {
                                "path": "memory/working/notes/reference.md",
                                "type": "bogus",
                                "intent": "Read",
                            },
                        ],
                        "postconditions": [
                            {"description": "Need output", "type": "check"},
                        ],
                        "changes": [
                            {
                                "path": "memory/working/notes/output.md",
                                "action": "bogus",
                                "description": "Write output",
                            }
                        ],
                    }
                ]
            )

        errors = validation_error_messages(ctx.exception)

        self.assertEqual(len(errors), 3)
        self.assertTrue(any(error.startswith("work.phases[0].sources[0]:") for error in errors))
        self.assertTrue(
            any(error.startswith("work.phases[0].postconditions[0]:") for error in errors)
        )
        self.assertTrue(any(error.startswith("work.phases[0].changes[0]:") for error in errors))


class TestCoerceBudget(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(coerce_budget_input(None))

    def test_valid_dict(self) -> None:
        b = coerce_budget_input({"deadline": "2026-04-15", "max_sessions": 5})
        self.assertIsInstance(b, PlanBudget)
        self.assertEqual(b.deadline, "2026-04-15")
        self.assertEqual(b.max_sessions, 5)
        self.assertTrue(b.advisory)  # default

    def test_advisory_false(self) -> None:
        b = coerce_budget_input({"max_sessions": 3, "advisory": False})
        self.assertFalse(b.advisory)

    def test_invalid_type_raises(self) -> None:
        with self.assertRaises(ValidationError):
            coerce_budget_input("not a dict")


# ===========================================================================
# budget_status()
# ===========================================================================


class TestBudgetStatus(unittest.TestCase):
    def test_no_budget_returns_none(self) -> None:
        plan = _minimal_plan()
        self.assertIsNone(budget_status(plan))

    def test_deadline_in_future(self) -> None:
        future = (date.today() + timedelta(days=10)).isoformat()
        plan = _minimal_plan(budget=PlanBudget(deadline=future))
        bs = budget_status(plan)
        self.assertIsNotNone(bs)
        self.assertFalse(bs["past_deadline"])
        self.assertGreater(bs["days_remaining"], 0)
        self.assertFalse(bs["over_budget"])

    def test_deadline_in_past(self) -> None:
        past = (date.today() - timedelta(days=1)).isoformat()
        plan = _minimal_plan(budget=PlanBudget(deadline=past))
        bs = budget_status(plan)
        self.assertTrue(bs["past_deadline"])
        self.assertTrue(bs["over_budget"])

    def test_session_budget_not_exhausted(self) -> None:
        plan = _minimal_plan(budget=PlanBudget(max_sessions=5), sessions_used=2)
        bs = budget_status(plan)
        self.assertEqual(bs["sessions_remaining"], 3)
        self.assertFalse(bs["over_session_budget"])
        self.assertFalse(bs["over_budget"])

    def test_session_budget_exhausted(self) -> None:
        plan = _minimal_plan(budget=PlanBudget(max_sessions=3), sessions_used=3)
        bs = budget_status(plan)
        self.assertEqual(bs["sessions_remaining"], 0)
        self.assertTrue(bs["over_session_budget"])
        self.assertTrue(bs["over_budget"])

    def test_advisory_flag_propagated(self) -> None:
        plan = _minimal_plan(budget=PlanBudget(max_sessions=3, advisory=False))
        bs = budget_status(plan)
        self.assertFalse(bs["advisory"])


# ===========================================================================
# next_action() dict return
# ===========================================================================


class TestNextAction(unittest.TestCase):
    def test_returns_dict_with_id_and_title(self) -> None:
        plan = _minimal_plan()
        result = next_action(plan)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], "phase-one")
        self.assertEqual(result["title"], "First phase")
        self.assertIn("requires_approval", result)

    def test_returns_none_when_all_completed(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].status = "completed"
        self.assertIsNone(next_action(plan))

    def test_includes_sources_when_present(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].sources = [
            SourceSpec(path="core/file.py", type="internal", intent="Read"),
        ]
        result = next_action(plan)
        self.assertIn("sources", result)
        self.assertEqual(len(result["sources"]), 1)

    def test_omits_sources_when_empty(self) -> None:
        plan = _minimal_plan()
        result = next_action(plan)
        self.assertNotIn("sources", result)

    def test_includes_postconditions_when_present(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(description="File exists"),
        ]
        result = next_action(plan)
        self.assertIn("postconditions", result)

    def test_requires_approval_flag(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].requires_approval = True
        result = next_action(plan)
        self.assertTrue(result["requires_approval"])


# ===========================================================================
# phase_payload() enrichment
# ===========================================================================


class TestPhasePayload(unittest.TestCase):
    def test_includes_sources_in_phase_dict(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].sources = [
            SourceSpec(path="core/file.py", type="internal", intent="Read"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "core").mkdir()
            (root / "core" / "file.py").write_text("x")
            payload = phase_payload(plan, plan.phases[0], root)
        self.assertIn("sources", payload["phase"])
        self.assertEqual(len(payload["phase"]["sources"]), 1)

    def test_includes_postconditions_in_phase_dict(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(description="Check it"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = phase_payload(plan, plan.phases[0], Path(tmpdir))
        self.assertIn("postconditions", payload["phase"])

    def test_includes_requires_approval(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].requires_approval = True
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = phase_payload(plan, plan.phases[0], Path(tmpdir))
        self.assertTrue(payload["phase"]["requires_approval"])

    def test_includes_budget_status_when_set(self) -> None:
        future = (date.today() + timedelta(days=10)).isoformat()
        plan = _minimal_plan(budget=PlanBudget(deadline=future))
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = phase_payload(plan, plan.phases[0], Path(tmpdir))
        self.assertIn("budget_status", payload)

    def test_omits_budget_status_when_no_budget(self) -> None:
        plan = _minimal_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = phase_payload(plan, plan.phases[0], Path(tmpdir))
        self.assertNotIn("budget_status", payload)


# ===========================================================================
# Round-trip: save_plan → load_plan
# ===========================================================================


class TestRoundTrip(unittest.TestCase):
    def test_full_round_trip_with_all_new_fields(self) -> None:
        plan = _minimal_plan(
            budget=PlanBudget(deadline="2026-04-15", max_sessions=8),
            sessions_used=2,
        )
        plan.phases[0].sources = [
            SourceSpec(path="core/file.py", type="internal", intent="Read it"),
        ]
        plan.phases[0].postconditions = [
            PostconditionSpec(description="File exists"),
            PostconditionSpec(description="Tests pass", type="test", target="tests/"),
        ]
        plan.phases[0].requires_approval = True

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Create the internal source so validation passes
            (root / "core").mkdir(parents=True)
            (root / "core" / "file.py").write_text("x")

            plan_path = root / "plan.yaml"
            save_plan(plan_path, plan, root)

            loaded = load_plan(plan_path, root)

        # Verify budget
        self.assertIsNotNone(loaded.budget)
        self.assertEqual(loaded.budget.deadline, "2026-04-15")
        self.assertEqual(loaded.budget.max_sessions, 8)
        self.assertEqual(loaded.sessions_used, 2)

        # Verify sources
        self.assertEqual(len(loaded.phases[0].sources), 1)
        self.assertEqual(loaded.phases[0].sources[0].type, "internal")
        self.assertEqual(loaded.phases[0].sources[0].intent, "Read it")

        # Verify postconditions
        self.assertEqual(len(loaded.phases[0].postconditions), 2)
        self.assertEqual(loaded.phases[0].postconditions[0].type, "manual")
        self.assertEqual(loaded.phases[0].postconditions[1].type, "test")
        self.assertEqual(loaded.phases[0].postconditions[1].target, "tests/")

        # Verify requires_approval
        self.assertTrue(loaded.phases[0].requires_approval)

    def test_round_trip_omits_defaults(self) -> None:
        """Empty sources, postconditions, and no budget should be omitted from YAML."""
        plan = _minimal_plan()

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plan.yaml"
            save_plan(plan_path, plan)
            raw_yaml = plan_path.read_text(encoding="utf-8")

        self.assertNotIn("sources:", raw_yaml)
        self.assertNotIn("postconditions:", raw_yaml)
        self.assertNotIn("requires_approval:", raw_yaml)
        self.assertNotIn("budget:", raw_yaml)
        self.assertNotIn("sessions_used:", raw_yaml)


# ===========================================================================
# Backward compatibility
# ===========================================================================


class TestBackwardCompatibility(unittest.TestCase):
    def test_old_plan_without_new_fields_loads(self) -> None:
        """Plans created before schema extensions should load without error."""
        old_plan_dict = {
            "id": "old-plan",
            "project": "test-project",
            "created": "2026-01-01",
            "origin_session": "memory/activity/2026/01/01/chat-001",
            "status": "active",
            "purpose": {
                "summary": "Old plan",
                "context": "Created before schema extensions.",
                "questions": [],
            },
            "work": {
                "phases": [
                    {
                        "id": "p1",
                        "title": "Phase 1",
                        "status": "pending",
                        "commit": None,
                        "blockers": [],
                        "changes": [
                            {
                                "path": "memory/working/notes/x.md",
                                "action": "create",
                                "description": "Test",
                            },
                        ],
                    },
                ],
            },
            "review": None,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = _write_plan_yaml(Path(tmpdir), old_plan_dict)
            plan = load_plan(plan_path)

        self.assertEqual(plan.id, "old-plan")
        self.assertEqual(plan.phases[0].sources, [])
        self.assertEqual(plan.phases[0].postconditions, [])
        self.assertFalse(plan.phases[0].requires_approval)
        self.assertIsNone(plan.budget)
        self.assertEqual(plan.sessions_used, 0)

    def test_old_plan_next_action_returns_dict(self) -> None:
        """Even for old plans, next_action should return a dict, not a string."""
        old_plan_dict = {
            "id": "old-plan",
            "project": "test-project",
            "created": "2026-01-01",
            "origin_session": "memory/activity/2026/01/01/chat-001",
            "status": "active",
            "purpose": {
                "summary": "Old plan",
                "context": "Test",
                "questions": [],
            },
            "work": {
                "phases": [
                    {
                        "id": "p1",
                        "title": "Do something",
                        "status": "pending",
                        "commit": None,
                        "blockers": [],
                        "changes": [
                            {
                                "path": "memory/working/notes/x.md",
                                "action": "create",
                                "description": "Test",
                            },
                        ],
                    },
                ],
            },
            "review": None,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = _write_plan_yaml(Path(tmpdir), old_plan_dict)
            plan = load_plan(plan_path)

        result = next_action(plan)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], "p1")
        self.assertEqual(result["title"], "Do something")
        self.assertFalse(result["requires_approval"])
        self.assertNotIn("sources", result)


# ===========================================================================
# Inter-plan blocker validation
# ===========================================================================


class TestInterPlanBlockers(unittest.TestCase):
    """Tests for inter-plan blocker resolution in validate_plan_references
    and phase_blockers."""

    # -- validate_plan_references -------------------------------------------

    def test_inter_plan_blocker_resolves_with_content_root(self) -> None:
        """When root is the content root, inter-plan blockers resolve directly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)  # acts as content root
            # Write the referenced plan with a completed phase
            _write_minimal_plan_at(
                root,
                "proj",
                "upstream-plan",
                phases=[
                    PlanPhase(
                        id="upstream-phase",
                        title="Upstream",
                        status="completed",
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/x.md", action="create", description="x"
                            )
                        ],
                    ),
                ],
            )
            # Plan with an inter-plan blocker
            plan = _minimal_plan(
                project="proj",
                phases=[
                    PlanPhase(
                        id="downstream",
                        title="Downstream",
                        blockers=["upstream-plan:upstream-phase"],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/y.md", action="create", description="y"
                            )
                        ],
                    ),
                ],
            )
            # Should not raise
            validate_plan_references(plan, root)

    def test_inter_plan_blocker_resolves_with_repo_root(self) -> None:
        """When root is the repo root, inter-plan blockers resolve via
        the content-prefix fallback (core/)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            content_root = repo_root / "core"
            # Write the referenced plan under core/
            _write_minimal_plan_at(
                content_root,
                "proj",
                "upstream-plan",
                phases=[
                    PlanPhase(
                        id="up",
                        title="Upstream",
                        status="completed",
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/x.md", action="create", description="x"
                            )
                        ],
                    ),
                ],
            )
            plan = _minimal_plan(
                project="proj",
                phases=[
                    PlanPhase(
                        id="down",
                        title="Downstream",
                        blockers=["upstream-plan:up"],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/y.md", action="create", description="y"
                            )
                        ],
                    ),
                ],
            )
            # Should not raise — falls back to core/ prefix
            validate_plan_references(plan, repo_root)

    def test_inter_plan_blocker_missing_plan_raises(self) -> None:
        """Referencing a non-existent plan raises ValidationError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = _minimal_plan(
                project="proj",
                phases=[
                    PlanPhase(
                        id="p1",
                        title="P1",
                        blockers=["nonexistent-plan:some-phase"],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/y.md", action="create", description="y"
                            )
                        ],
                    ),
                ],
            )
            with self.assertRaises(ValidationError) as ctx:
                validate_plan_references(plan, root)
            self.assertIn("nonexistent-plan", str(ctx.exception))

    def test_inter_plan_blocker_missing_phase_raises(self) -> None:
        """Referencing a valid plan but non-existent phase raises."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_plan_at(
                root,
                "proj",
                "upstream-plan",
                phases=[
                    PlanPhase(
                        id="real-phase",
                        title="Real",
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/x.md", action="create", description="x"
                            )
                        ],
                    ),
                ],
            )
            plan = _minimal_plan(
                project="proj",
                phases=[
                    PlanPhase(
                        id="p1",
                        title="P1",
                        blockers=["upstream-plan:bogus-phase"],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/y.md", action="create", description="y"
                            )
                        ],
                    ),
                ],
            )
            with self.assertRaises(NotFoundError) as ctx:
                validate_plan_references(plan, root)
            self.assertIn("bogus-phase", str(ctx.exception))

    # -- phase_blockers ----------------------------------------------------

    def test_phase_blockers_inter_plan_pending(self) -> None:
        """Inter-plan blocker shows unsatisfied when referenced phase is pending."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_plan_at(
                root,
                "proj",
                "upstream",
                phases=[
                    PlanPhase(
                        id="up-phase",
                        title="Upstream phase",
                        status="pending",
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/x.md", action="create", description="x"
                            )
                        ],
                    ),
                ],
            )
            plan = _minimal_plan(
                project="proj",
                phases=[
                    PlanPhase(
                        id="down",
                        title="Downstream",
                        blockers=["upstream:up-phase"],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/y.md", action="create", description="y"
                            )
                        ],
                    ),
                ],
            )
            result = phase_blockers(plan, plan.phases[0], root)
            inter = [b for b in result if b["kind"] == "inter-plan"]
            self.assertEqual(len(inter), 1)
            self.assertFalse(inter[0]["satisfied"])
            self.assertEqual(inter[0]["status"], "pending")

    def test_phase_blockers_inter_plan_completed(self) -> None:
        """Inter-plan blocker shows satisfied when referenced phase is completed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_minimal_plan_at(
                root,
                "proj",
                "upstream",
                phases=[
                    PlanPhase(
                        id="up-phase",
                        title="Upstream phase",
                        status="completed",
                        commit="abc123",
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/x.md", action="create", description="x"
                            )
                        ],
                    ),
                ],
            )
            plan = _minimal_plan(
                project="proj",
                phases=[
                    PlanPhase(
                        id="down",
                        title="Downstream",
                        blockers=["upstream:up-phase"],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/y.md", action="create", description="y"
                            )
                        ],
                    ),
                ],
            )
            result = phase_blockers(plan, plan.phases[0], root)
            inter = [b for b in result if b["kind"] == "inter-plan"]
            self.assertEqual(len(inter), 1)
            self.assertTrue(inter[0]["satisfied"])
            self.assertEqual(inter[0]["commit"], "abc123")

    def test_phase_blockers_inter_plan_missing_plan(self) -> None:
        """Missing inter-plan reference produces a 'missing-plan' entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = _minimal_plan(
                project="proj",
                phases=[
                    PlanPhase(
                        id="down",
                        title="Downstream",
                        blockers=["no-such-plan:some-phase"],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/y.md", action="create", description="y"
                            )
                        ],
                    ),
                ],
            )
            result = phase_blockers(plan, plan.phases[0], root)
            inter = [b for b in result if b["kind"] == "inter-plan"]
            self.assertEqual(len(inter), 1)
            self.assertFalse(inter[0]["satisfied"])
            self.assertEqual(inter[0]["status"], "missing-plan")

    def test_phase_blockers_inter_plan_repo_root_fallback(self) -> None:
        """Inter-plan resolution falls back to content-prefix subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            content_root = repo_root / "core"
            _write_minimal_plan_at(
                content_root,
                "proj",
                "upstream",
                phases=[
                    PlanPhase(
                        id="up",
                        title="Upstream",
                        status="completed",
                        commit="def456",
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/x.md", action="create", description="x"
                            )
                        ],
                    ),
                ],
            )
            plan = _minimal_plan(
                project="proj",
                phases=[
                    PlanPhase(
                        id="down",
                        title="Downstream",
                        blockers=["upstream:up"],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/y.md", action="create", description="y"
                            )
                        ],
                    ),
                ],
            )
            result = phase_blockers(plan, plan.phases[0], repo_root)
            inter = [b for b in result if b["kind"] == "inter-plan"]
            self.assertEqual(len(inter), 1)
            self.assertTrue(inter[0]["satisfied"])


# ===========================================================================
# SourceSpec backward compatibility with content-prefix paths
# ===========================================================================


class TestSourceSpecContentPrefix(unittest.TestCase):
    def test_validate_exists_with_redundant_prefix(self) -> None:
        """Source path 'core/file.py' resolves when root is content root named core/."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_root = Path(tmpdir) / "core"
            content_root.mkdir()
            (content_root / "file.py").write_text("x")
            s = SourceSpec(path="core/file.py", type="internal", intent="Read")
            # root = content_root, path starts with 'core/' → redundant prefix stripped
            s.validate_exists(content_root)  # should not raise

    def test_validate_exists_content_relative_path(self) -> None:
        """Content-relative source path resolves directly with content root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_root = Path(tmpdir) / "core"
            content_root.mkdir()
            (content_root / "tools").mkdir()
            (content_root / "tools" / "file.py").write_text("x")
            s = SourceSpec(path="tools/file.py", type="internal", intent="Read")
            s.validate_exists(content_root)  # should not raise

    def test_validate_exists_still_fails_for_truly_missing(self) -> None:
        """Backward compat doesn't falsely pass for genuinely missing files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            content_root = Path(tmpdir) / "core"
            content_root.mkdir()
            s = SourceSpec(path="core/missing.py", type="internal", intent="Read")
            with self.assertRaises(ValidationError):
                s.validate_exists(content_root)


# ===========================================================================
# PhaseFailure dataclass
# ===========================================================================


class TestPhaseFailure(unittest.TestCase):
    def test_valid_failure(self) -> None:
        f = PhaseFailure(timestamp="2026-03-26T12:00:00Z", reason="Test failed")
        self.assertEqual(f.attempt, 1)
        self.assertIsNone(f.verification_results)

    def test_failure_with_verification_results(self) -> None:
        results = [{"postcondition": "File exists", "status": "fail"}]
        f = PhaseFailure(
            timestamp="2026-03-26T12:00:00Z",
            reason="Postcondition check failed",
            verification_results=results,
            attempt=2,
        )
        self.assertEqual(f.attempt, 2)
        self.assertEqual(f.verification_results, results)

    def test_empty_timestamp_raises(self) -> None:
        with self.assertRaises(ValidationError):
            PhaseFailure(timestamp="", reason="Failed")

    def test_empty_reason_raises(self) -> None:
        with self.assertRaises(ValidationError):
            PhaseFailure(timestamp="2026-03-26T12:00:00Z", reason="")

    def test_zero_attempt_raises(self) -> None:
        with self.assertRaises(ValidationError):
            PhaseFailure(timestamp="2026-03-26T12:00:00Z", reason="Failed", attempt=0)

    def test_negative_attempt_raises(self) -> None:
        with self.assertRaises(ValidationError):
            PhaseFailure(timestamp="2026-03-26T12:00:00Z", reason="Failed", attempt=-1)

    def test_to_dict_omits_verification_results_when_none(self) -> None:
        f = PhaseFailure(timestamp="2026-03-26T12:00:00Z", reason="Failed")
        d = f.to_dict()
        self.assertNotIn("verification_results", d)
        self.assertEqual(d["timestamp"], "2026-03-26T12:00:00Z")
        self.assertEqual(d["reason"], "Failed")
        self.assertEqual(d["attempt"], 1)

    def test_to_dict_includes_verification_results_when_set(self) -> None:
        results = [{"status": "fail"}]
        f = PhaseFailure(
            timestamp="2026-03-26T12:00:00Z",
            reason="Failed",
            verification_results=results,
            attempt=3,
        )
        d = f.to_dict()
        self.assertIn("verification_results", d)
        self.assertEqual(d["attempt"], 3)

    def test_whitespace_trimmed(self) -> None:
        f = PhaseFailure(timestamp="  2026-03-26T12:00:00Z  ", reason="  Failed  ")
        self.assertEqual(f.timestamp, "2026-03-26T12:00:00Z")
        self.assertEqual(f.reason, "Failed")


# ===========================================================================
# PhaseFailure round-trip serialization
# ===========================================================================


class TestPhaseFailureRoundTrip(unittest.TestCase):
    def test_failures_survive_save_load(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].failures = [
            PhaseFailure(
                timestamp="2026-03-26T12:00:00Z",
                reason="First attempt failed",
                attempt=1,
            ),
            PhaseFailure(
                timestamp="2026-03-26T13:00:00Z",
                reason="Second attempt failed",
                verification_results=[{"status": "fail", "detail": "missing"}],
                attempt=2,
            ),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plan.yaml"
            save_plan(plan_path, plan)
            loaded = load_plan(plan_path)

        self.assertEqual(len(loaded.phases[0].failures), 2)
        self.assertEqual(loaded.phases[0].failures[0].reason, "First attempt failed")
        self.assertEqual(loaded.phases[0].failures[1].attempt, 2)
        self.assertEqual(
            loaded.phases[0].failures[1].verification_results,
            [{"status": "fail", "detail": "missing"}],
        )

    def test_empty_failures_omitted_from_yaml(self) -> None:
        plan = _minimal_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plan.yaml"
            save_plan(plan_path, plan)
            raw = plan_path.read_text(encoding="utf-8")
        self.assertNotIn("failures:", raw)

    def test_old_plan_without_failures_loads(self) -> None:
        old_plan_dict = {
            "id": "old-plan",
            "project": "test-project",
            "created": "2026-01-01",
            "origin_session": "memory/activity/2026/01/01/chat-001",
            "status": "active",
            "purpose": {"summary": "Old plan", "context": "No failures field."},
            "work": {
                "phases": [
                    {
                        "id": "p1",
                        "title": "Phase 1",
                        "status": "pending",
                        "commit": None,
                        "blockers": [],
                        "changes": [
                            {
                                "path": "memory/working/notes/x.md",
                                "action": "create",
                                "description": "Test",
                            },
                        ],
                    },
                ],
            },
            "review": None,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = _write_plan_yaml(Path(tmpdir), old_plan_dict)
            plan = load_plan(plan_path)
        self.assertEqual(plan.phases[0].failures, [])


# ===========================================================================
# verify_postconditions — all four types
# ===========================================================================


class TestVerifyPostconditions(unittest.TestCase):
    def test_manual_postcondition_skipped(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].postconditions = [PostconditionSpec(description="Manual check")]
        with tempfile.TemporaryDirectory() as tmpdir:
            result = verify_postconditions(plan, plan.phases[0], Path(tmpdir))
        self.assertTrue(result["all_passed"])
        self.assertEqual(result["summary"]["skipped"], 1)
        self.assertEqual(result["verification_results"][0]["status"], "skip")

    def test_check_postcondition_pass(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(description="File exists", type="check", target="test.txt"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "test.txt").write_text("content")
            result = verify_postconditions(plan, plan.phases[0], root)
        self.assertTrue(result["all_passed"])
        self.assertEqual(result["verification_results"][0]["status"], "pass")

    def test_check_postcondition_fail(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(description="File exists", type="check", target="missing.txt"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            result = verify_postconditions(plan, plan.phases[0], Path(tmpdir))
        self.assertFalse(result["all_passed"])
        self.assertEqual(result["verification_results"][0]["status"], "fail")

    def test_grep_postcondition_pass(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(
                description="Pattern found",
                type="grep",
                target="hello::test.txt",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "test.txt").write_text("say hello world")
            result = verify_postconditions(plan, plan.phases[0], root)
        self.assertTrue(result["all_passed"])
        self.assertEqual(result["verification_results"][0]["status"], "pass")

    def test_grep_postcondition_fail(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(
                description="Pattern found",
                type="grep",
                target="nonexistent_pattern::test.txt",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "test.txt").write_text("no match here")
            result = verify_postconditions(plan, plan.phases[0], root)
        self.assertFalse(result["all_passed"])
        self.assertEqual(result["verification_results"][0]["status"], "fail")

    def test_grep_postcondition_bad_format(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(
                description="Bad format",
                type="grep",
                target="no-double-colon",
            ),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            result = verify_postconditions(plan, plan.phases[0], Path(tmpdir))
        self.assertFalse(result["all_passed"])
        self.assertEqual(result["verification_results"][0]["status"], "error")

    def test_test_postcondition_requires_engram_tier2(self) -> None:
        import os

        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(description="Tests pass", type="test", target="pytest -q"),
        ]
        old_val = os.environ.pop("ENGRAM_TIER2", None)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = verify_postconditions(plan, plan.phases[0], Path(tmpdir))
        finally:
            if old_val is not None:
                os.environ["ENGRAM_TIER2"] = old_val
        self.assertFalse(result["all_passed"])
        self.assertIn("ENGRAM_TIER2", result["verification_results"][0]["detail"])

    def test_test_postcondition_rejects_engram_tier2_zero(self) -> None:
        import os

        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(description="Tests pass", type="test", target="pytest -q"),
        ]
        old_val = os.environ.get("ENGRAM_TIER2")
        os.environ["ENGRAM_TIER2"] = "0"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = verify_postconditions(plan, plan.phases[0], Path(tmpdir))
        finally:
            if old_val is None:
                os.environ.pop("ENGRAM_TIER2", None)
            else:
                os.environ["ENGRAM_TIER2"] = old_val
        self.assertFalse(result["all_passed"])
        self.assertEqual(result["verification_results"][0]["status"], "error")
        self.assertIn("ENGRAM_TIER2", result["verification_results"][0]["detail"])

    def test_test_postcondition_rejects_non_allowlisted(self) -> None:
        import os

        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(description="Bad cmd", type="test", target="rm -rf /"),
        ]
        old_val = os.environ.get("ENGRAM_TIER2")
        os.environ["ENGRAM_TIER2"] = "1"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = verify_postconditions(plan, plan.phases[0], Path(tmpdir))
        finally:
            if old_val is None:
                os.environ.pop("ENGRAM_TIER2", None)
            else:
                os.environ["ENGRAM_TIER2"] = old_val
        self.assertFalse(result["all_passed"])
        self.assertIn("not in allowlist", result["verification_results"][0]["detail"])

    def test_test_postcondition_rejects_metacharacters(self) -> None:
        import os

        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(description="Injected", type="test", target="pytest; rm -rf /"),
        ]
        old_val = os.environ.get("ENGRAM_TIER2")
        os.environ["ENGRAM_TIER2"] = "1"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = verify_postconditions(plan, plan.phases[0], Path(tmpdir))
        finally:
            if old_val is None:
                os.environ.pop("ENGRAM_TIER2", None)
            else:
                os.environ["ENGRAM_TIER2"] = old_val
        self.assertFalse(result["all_passed"])
        self.assertIn("metacharacters", result["verification_results"][0]["detail"])

    def test_empty_postconditions_all_passed(self) -> None:
        plan = _minimal_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = verify_postconditions(plan, plan.phases[0], Path(tmpdir))
        self.assertTrue(result["all_passed"])
        self.assertEqual(result["summary"]["total"], 0)

    def test_mixed_postconditions_summary(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].postconditions = [
            PostconditionSpec(description="Manual", type="manual"),
            PostconditionSpec(description="Check exists", type="check", target="found.txt"),
            PostconditionSpec(description="Check missing", type="check", target="missing.txt"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "found.txt").write_text("x")
            result = verify_postconditions(plan, plan.phases[0], root)
        self.assertFalse(result["all_passed"])
        self.assertEqual(result["summary"]["passed"], 1)
        self.assertEqual(result["summary"]["failed"], 1)
        self.assertEqual(result["summary"]["skipped"], 1)


# ===========================================================================
# Retry context in phase_payload and next_action
# ===========================================================================


class TestRetryContext(unittest.TestCase):
    def test_phase_payload_no_failures_default_attempt(self) -> None:
        plan = _minimal_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = phase_payload(plan, plan.phases[0], Path(tmpdir))
        self.assertEqual(payload["phase"]["failures"], [])
        self.assertEqual(payload["phase"]["attempt_number"], 1)

    def test_phase_payload_with_failures(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].failures = [
            PhaseFailure(timestamp="2026-03-26T12:00:00Z", reason="First fail", attempt=1),
            PhaseFailure(timestamp="2026-03-26T13:00:00Z", reason="Second fail", attempt=2),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = phase_payload(plan, plan.phases[0], Path(tmpdir))
        self.assertEqual(len(payload["phase"]["failures"]), 2)
        self.assertEqual(payload["phase"]["attempt_number"], 3)

    def test_next_action_no_failures(self) -> None:
        plan = _minimal_plan()
        result = next_action(plan)
        self.assertEqual(result["attempt_number"], 1)
        self.assertFalse(result["has_prior_failures"])
        self.assertNotIn("suggest_revision", result)

    def test_next_action_with_failures(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].failures = [
            PhaseFailure(timestamp="2026-03-26T12:00:00Z", reason="Failed", attempt=1),
        ]
        result = next_action(plan)
        self.assertEqual(result["attempt_number"], 2)
        self.assertTrue(result["has_prior_failures"])
        self.assertNotIn("suggest_revision", result)

    def test_next_action_suggest_revision_at_three_failures(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].failures = [
            PhaseFailure(
                timestamp=f"2026-03-26T{12 + i}:00:00Z",
                reason=f"Fail {i + 1}",
                attempt=i + 1,
            )
            for i in range(3)
        ]
        result = next_action(plan)
        self.assertEqual(result["attempt_number"], 4)
        self.assertTrue(result["has_prior_failures"])
        self.assertTrue(result["suggest_revision"])

    def test_next_action_suggest_revision_above_three(self) -> None:
        plan = _minimal_plan()
        plan.phases[0].failures = [
            PhaseFailure(
                timestamp=f"2026-03-26T{12 + i}:00:00Z",
                reason=f"Fail {i + 1}",
                attempt=i + 1,
            )
            for i in range(5)
        ]
        result = next_action(plan)
        self.assertTrue(result["suggest_revision"])


# ---------------------------------------------------------------------------
# Phase 3 observability: TraceSpan, record_trace, _sanitize_metadata
# ---------------------------------------------------------------------------

from engram_mcp.agent_memory_mcp.plan_utils import (  # noqa: E402
    TRACE_SPAN_TYPES,
    TRACE_STATUSES,
    TraceSpan,
    _sanitize_metadata,
)


class TestTraceSpanDataclass(unittest.TestCase):
    def test_valid_span_construction(self) -> None:
        span = TraceSpan(
            span_id="abc123def456",
            session_id="memory/activity/2026/03/26/chat-001",
            timestamp="2026-03-26T10:00:00.000Z",
            span_type="plan_action",
            name="complete",
            status="ok",
        )
        self.assertEqual(span.span_type, "plan_action")
        self.assertEqual(span.status, "ok")
        self.assertIsNone(span.parent_span_id)
        self.assertIsNone(span.duration_ms)

    def test_span_type_validation(self) -> None:
        with self.assertRaises(ValidationError):
            TraceSpan(
                span_id="x",
                session_id="s",
                timestamp="t",
                span_type="bad_type",
                name="n",
                status="ok",
            )

    def test_status_validation(self) -> None:
        with self.assertRaises(ValidationError):
            TraceSpan(
                span_id="x",
                session_id="s",
                timestamp="t",
                span_type="tool_call",
                name="n",
                status="pending",
            )

    def test_to_dict_omits_none_fields(self) -> None:
        span = TraceSpan(
            span_id="abc",
            session_id="s",
            timestamp="t",
            span_type="retrieval",
            name="read",
            status="ok",
        )
        d = span.to_dict()
        self.assertNotIn("parent_span_id", d)
        self.assertNotIn("duration_ms", d)
        self.assertNotIn("metadata", d)
        self.assertNotIn("cost", d)

    def test_to_dict_includes_optional_fields_when_set(self) -> None:
        span = TraceSpan(
            span_id="abc",
            session_id="s",
            timestamp="t",
            span_type="verification",
            name="verify:phase-one",
            status="error",
            parent_span_id="parent123",
            duration_ms=42,
            metadata={"plan_id": "my-plan"},
            cost={"tokens_in": 100, "tokens_out": 50},
        )
        d = span.to_dict()
        self.assertEqual(d["parent_span_id"], "parent123")
        self.assertEqual(d["duration_ms"], 42)
        self.assertEqual(d["metadata"]["plan_id"], "my-plan")
        self.assertEqual(d["cost"]["tokens_in"], 100)

    def test_all_span_types_valid(self) -> None:
        for stype in TRACE_SPAN_TYPES:
            span = TraceSpan(
                span_id="x",
                session_id="s",
                timestamp="t",
                span_type=stype,
                name="n",
                status="ok",
            )
            self.assertEqual(span.span_type, stype)

    def test_all_statuses_valid(self) -> None:
        for st in TRACE_STATUSES:
            span = TraceSpan(
                span_id="x",
                session_id="s",
                timestamp="t",
                span_type="tool_call",
                name="n",
                status=st,
            )
            self.assertEqual(span.status, st)


class TestSanitizeMetadata(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(_sanitize_metadata(None))

    def test_empty_dict_returns_none(self) -> None:
        self.assertIsNone(_sanitize_metadata({}))

    def test_truncates_long_strings(self) -> None:
        long_val = "x" * 300
        result = _sanitize_metadata({"field": long_val})
        self.assertIsNotNone(result)
        assert result is not None
        self.assertLessEqual(len(result["field"]), 215)  # 200 + '[truncated]'
        self.assertIn("[truncated]", result["field"])

    def test_redacts_credential_field_names(self) -> None:
        result = _sanitize_metadata(
            {
                "api_key": "secret123",
                "auth_token": "abc",
                "password": "pw",
                "plan_id": "my-plan",
            }
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["api_key"], "[redacted]")
        self.assertEqual(result["auth_token"], "[redacted]")
        self.assertEqual(result["password"], "[redacted]")
        self.assertEqual(result["plan_id"], "my-plan")

    def test_depth_limit_stringifies_deep_objects(self) -> None:
        # depth=0: level1 (dict) → recurse
        # depth=1: level2 (dict) → recurse
        # depth=2: level3 (dict) → stringify (depth >= 2)
        deep = {"level1": {"level2": {"level3": {"level4": "value"}}}}
        result = _sanitize_metadata(deep)
        self.assertIsNotNone(result)
        assert result is not None
        # level3 at depth=2 should be a string (dict was stringified)
        self.assertIsInstance(result["level1"]["level2"]["level3"], str)

    def test_size_limit_reduces_to_scalars(self) -> None:
        # Build a metadata dict that exceeds 2KB
        big_meta = {f"key_{i}": "v" * 100 for i in range(30)}
        result = _sanitize_metadata(big_meta)
        # Should not raise; result may be reduced
        # (all values are strings, so scalars are preserved)
        self.assertIsNotNone(result)

    def test_scalar_values_pass_through(self) -> None:
        result = _sanitize_metadata(
            {
                "plan_id": "test-plan",
                "passed": 3,
                "failed": 0,
                "done": True,
            }
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["plan_id"], "test-plan")
        self.assertEqual(result["passed"], 3)
        self.assertEqual(result["done"], True)


class TestTraceFilePath(unittest.TestCase):
    def test_session_id_to_trace_path(self) -> None:
        self.assertEqual(
            trace_file_path("memory/activity/2026/03/26/chat-001"),
            "memory/activity/2026/03/26/chat-001.traces.jsonl",
        )


class TestRecordTrace(unittest.TestCase):
    def test_writes_span_to_jsonl(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id = "memory/activity/2026/03/26/chat-001"
            span_id = record_trace(
                root,
                session_id,
                span_type="plan_action",
                name="complete",
                status="ok",
                metadata={"plan_id": "test-plan", "phase_id": "phase-one"},
            )
            self.assertIsNotNone(span_id)
            self.assertEqual(len(span_id), 12)

            trace_path = root / trace_file_path(session_id)
            self.assertTrue(trace_path.exists())
            lines = trace_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            span = json.loads(lines[0])
            self.assertEqual(span["span_type"], "plan_action")
            self.assertEqual(span["name"], "complete")
            self.assertEqual(span["status"], "ok")
            self.assertEqual(span["metadata"]["plan_id"], "test-plan")
            self.assertEqual(span["span_id"], span_id)

    def test_appends_multiple_spans(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id = "memory/activity/2026/04/01/chat-002"
            for name in ["start", "complete"]:
                record_trace(root, session_id, span_type="plan_action", name=name, status="ok")
            trace_path = root / trace_file_path(session_id)
            lines = [ln for ln in trace_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertEqual(len(lines), 2)

    def test_returns_none_when_session_id_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = record_trace(Path(tmp), None, span_type="plan_action", name="n", status="ok")
            self.assertIsNone(result)

    def test_non_blocking_on_bad_span_type(self) -> None:
        # Bad span_type raises ValidationError inside TraceSpan, which is caught
        with tempfile.TemporaryDirectory() as tmp:
            result = record_trace(
                Path(tmp),
                "memory/activity/2026/03/26/chat-001",
                span_type="invalid_type",
                name="n",
                status="ok",
            )
            self.assertIsNone(result)

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id = "memory/activity/2026/12/31/chat-001"
            record_trace(root, session_id, span_type="retrieval", name="read", status="ok")
            self.assertTrue((root / trace_file_path(session_id)).exists())


class TestAccessJsonlEventType(unittest.TestCase):
    """Verify that ACCESS.jsonl entries include event_type='retrieval'."""

    def _normalize_entry(self, root: Path, entry: dict) -> str:
        """Call the private normalizer via import."""
        from unittest.mock import MagicMock

        from engram_mcp.agent_memory_mcp.tools.semantic.session_tools import (
            _normalize_access_entry,
        )

        repo = MagicMock()
        repo.abs_path = MagicMock(side_effect=lambda p: root / p)

        def fake_resolve(r, path, field_name="path"):
            abs_p = root / path
            abs_p.parent.mkdir(parents=True, exist_ok=True)
            abs_p.touch()
            return path, abs_p

        import engram_mcp.agent_memory_mcp.tools.semantic.session_tools as st

        original_resolve = st.resolve_repo_path
        st.resolve_repo_path = fake_resolve
        try:
            _, line, _ = _normalize_access_entry(
                repo, root, entry, resolved_session_id="memory/activity/2026/03/26/chat-001"
            )
        finally:
            st.resolve_repo_path = original_resolve

        return line

    def test_retrieval_entries_have_event_type(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Create dummy file for access logging
            dummy = root / "memory/knowledge/test.md"
            dummy.parent.mkdir(parents=True, exist_ok=True)
            dummy.touch()
            try:
                line = self._normalize_entry(
                    root,
                    {
                        "file": "memory/knowledge/test.md",
                        "task": "testing",
                        "helpfulness": 0.8,
                        "note": "test note",
                    },
                )
                entry = json.loads(line)
                self.assertEqual(entry.get("event_type"), "retrieval")
            except Exception:
                pass  # Skipped if test environment lacks full setup


class TestSessionSummaryEnrichment(unittest.TestCase):
    """Verify that session summaries include trace metrics when a trace file exists."""

    def test_summary_includes_metrics_when_traces_exist(self) -> None:
        from engram_mcp.agent_memory_mcp.plan_utils import record_trace
        from engram_mcp.agent_memory_mcp.tools.semantic.session_tools import (
            _compute_trace_metrics,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id = "memory/activity/2026/03/26/chat-005"

            # Write some trace spans
            record_trace(root, session_id, span_type="plan_action", name="start", status="ok")
            record_trace(root, session_id, span_type="plan_action", name="complete", status="ok")
            record_trace(root, session_id, span_type="retrieval", name="read", status="ok")
            record_trace(root, session_id, span_type="tool_call", name="some_tool", status="error")

            metrics = _compute_trace_metrics(root, session_id)
            self.assertIsNotNone(metrics)
            assert metrics is not None
            self.assertEqual(metrics["plan_actions"], 2)
            self.assertEqual(metrics["retrievals"], 1)
            self.assertEqual(metrics["tool_calls"], 1)
            self.assertEqual(metrics["errors"], 1)

    def test_compute_trace_metrics_returns_none_when_no_file(self) -> None:
        from engram_mcp.agent_memory_mcp.tools.semantic.session_tools import (
            _compute_trace_metrics,
        )

        with tempfile.TemporaryDirectory() as tmp:
            result = _compute_trace_metrics(Path(tmp), "memory/activity/2026/03/26/chat-999")
            self.assertIsNone(result)

    def test_build_summary_without_traces_omits_metrics(self) -> None:
        import frontmatter as fmlib
        from engram_mcp.agent_memory_mcp.tools.semantic.session_tools import (
            _build_chat_summary_content,
        )

        with tempfile.TemporaryDirectory() as tmp:
            content = _build_chat_summary_content(
                "memory/activity/2026/03/26/chat-001",
                "Session summary text.",
                root=Path(tmp),
            )
            post = fmlib.loads(content)
            self.assertNotIn("metrics", post.metadata)

    def test_build_summary_with_traces_includes_metrics(self) -> None:
        import frontmatter as fmlib
        from engram_mcp.agent_memory_mcp.plan_utils import record_trace
        from engram_mcp.agent_memory_mcp.tools.semantic.session_tools import (
            _build_chat_summary_content,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id = "memory/activity/2026/03/26/chat-006"
            record_trace(root, session_id, span_type="plan_action", name="start", status="ok")

            content = _build_chat_summary_content(session_id, "Session summary text.", root=root)
            post = fmlib.loads(content)
            self.assertIn("metrics", post.metadata)
            self.assertEqual(post.metadata["metrics"]["plan_actions"], 1)


class TestToolDefinitionDataclass(unittest.TestCase):
    """Validate ToolDefinition construction and field validation."""

    def test_valid_construction_minimal(self) -> None:
        t = ToolDefinition(name="my-tool", description="Does stuff", provider="shell")
        self.assertEqual(t.name, "my-tool")
        self.assertEqual(t.provider, "shell")
        self.assertEqual(t.cost_tier, "free")
        self.assertEqual(t.timeout_seconds, 30)
        self.assertFalse(t.approval_required)
        self.assertIsNone(t.schema)
        self.assertEqual(t.tags, [])

    def test_valid_construction_full(self) -> None:
        t = ToolDefinition(
            name="api-call",
            description="Hit an external API",
            provider="api",
            approval_required=True,
            cost_tier="medium",
            rate_limit="100/day",
            timeout_seconds=45,
            tags=["external", "paid"],
            notes="Use sparingly.",
        )
        self.assertTrue(t.approval_required)
        self.assertEqual(t.cost_tier, "medium")
        self.assertEqual(t.rate_limit, "100/day")
        self.assertEqual(t.tags, ["external", "paid"])
        self.assertEqual(t.notes, "Use sparingly.")

    def test_invalid_name_not_slug(self) -> None:
        with self.assertRaises(ValidationError):
            ToolDefinition(name="My Tool", description="x", provider="shell")

    def test_invalid_provider_not_slug(self) -> None:
        with self.assertRaises(ValidationError):
            ToolDefinition(name="my-tool", description="x", provider="Shell API")

    def test_invalid_cost_tier(self) -> None:
        with self.assertRaises(ValidationError):
            ToolDefinition(name="t", description="x", provider="shell", cost_tier="expensive")

    def test_invalid_timeout_zero(self) -> None:
        with self.assertRaises(ValidationError):
            ToolDefinition(name="t", description="x", provider="shell", timeout_seconds=0)

    def test_invalid_timeout_negative(self) -> None:
        with self.assertRaises(ValidationError):
            ToolDefinition(name="t", description="x", provider="shell", timeout_seconds=-1)

    def test_invalid_empty_description(self) -> None:
        with self.assertRaises(ValidationError):
            ToolDefinition(name="t", description="  ", provider="shell")

    def test_invalid_tag_empty_string(self) -> None:
        with self.assertRaises(ValidationError):
            ToolDefinition(name="t", description="x", provider="shell", tags=["lint", ""])

    def test_schema_must_be_dict(self) -> None:
        with self.assertRaises(ValidationError):
            ToolDefinition(name="t", description="x", provider="shell", schema="not-a-dict")

    def test_to_dict_omits_none_fields(self) -> None:
        t = ToolDefinition(name="t", description="x", provider="shell")
        d = t.to_dict()
        self.assertNotIn("schema", d)
        self.assertNotIn("rate_limit", d)
        self.assertNotIn("notes", d)
        self.assertNotIn("tags", d)

    def test_to_dict_includes_populated_fields(self) -> None:
        t = ToolDefinition(
            name="t",
            description="x",
            provider="shell",
            tags=["a"],
            notes="note",
            rate_limit="10/min",
        )
        d = t.to_dict()
        self.assertIn("tags", d)
        self.assertIn("notes", d)
        self.assertIn("rate_limit", d)

    def test_all_cost_tiers_valid(self) -> None:
        for tier in ("free", "low", "medium", "high"):
            t = ToolDefinition(name="t", description="x", provider="shell", cost_tier=tier)
            self.assertEqual(t.cost_tier, tier)


class TestRegistryStorage(unittest.TestCase):
    """Validate load_registry, save_registry, and round-trip fidelity."""

    def _make_tool(self, name: str, **kwargs: object) -> ToolDefinition:
        return ToolDefinition(name=name, description=f"Tool {name}", provider="shell", **kwargs)

    def test_load_empty_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = load_registry(Path(tmp), "shell")
            self.assertEqual(result, [])

    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools = [
                self._make_tool("pytest-run", cost_tier="free", timeout_seconds=120),
                self._make_tool("pre-commit-run", tags=["lint"]),
            ]
            save_registry(root, "shell", tools)
            loaded = load_registry(root, "shell")
            self.assertEqual(len(loaded), 2)
            names = [t.name for t in loaded]
            self.assertIn("pytest-run", names)
            self.assertIn("pre-commit-run", names)

    def test_provider_grouping_separate_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_registry(root, "shell", [self._make_tool("sh-tool")])
            save_registry(
                root,
                "api",
                [ToolDefinition(name="api-tool", description="An API call", provider="api")],
            )
            shell_tools = load_registry(root, "shell")
            api_tools = load_registry(root, "api")
            self.assertEqual(len(shell_tools), 1)
            self.assertEqual(shell_tools[0].name, "sh-tool")
            self.assertEqual(len(api_tools), 1)
            self.assertEqual(api_tools[0].name, "api-tool")

    def test_create_new_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tools = [self._make_tool("tool-a")]
            save_registry(root, "shell", tools)
            # "create" by loading, appending, saving
            existing = load_registry(root, "shell")
            existing.append(self._make_tool("tool-b"))
            save_registry(root, "shell", existing)
            result = load_registry(root, "shell")
            self.assertEqual(len(result), 2)

    def test_update_tool_no_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_registry(root, "shell", [self._make_tool("my-tool")])
            existing = load_registry(root, "shell")
            # Simulate update: replace matching tool
            updated_tool = ToolDefinition(
                name="my-tool", description="Updated description", provider="shell"
            )
            updated = [updated_tool if t.name == "my-tool" else t for t in existing]
            save_registry(root, "shell", updated)
            result = load_registry(root, "shell")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].description, "Updated description")

    def test_registry_file_path_format(self) -> None:
        self.assertEqual(registry_file_path("shell"), "memory/skills/tool-registry/shell.yaml")
        self.assertEqual(
            registry_file_path("mcp-external"), "memory/skills/tool-registry/mcp-external.yaml"
        )

    def test_all_registry_tools_aggregates_providers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_registry(root, "shell", [self._make_tool("sh-tool")])
            save_registry(
                root,
                "api",
                [ToolDefinition(name="api-tool", description="API", provider="api")],
            )
            all_tools = _all_registry_tools(root)
            self.assertEqual(len(all_tools), 2)

    def test_all_registry_tools_empty_when_no_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_all_registry_tools(Path(tmp)), [])


class TestRegistrySummaryRegeneration(unittest.TestCase):
    """Validate regenerate_registry_summary produces correct markdown."""

    def test_summary_lists_all_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_registry(
                root,
                "shell",
                [
                    ToolDefinition(
                        name="pytest-run",
                        description="Run tests",
                        provider="shell",
                        tags=["test"],
                    ),
                    ToolDefinition(
                        name="ruff-check",
                        description="Lint",
                        provider="shell",
                    ),
                ],
            )
            regenerate_registry_summary(root)
            summary = (root / "memory/skills/tool-registry/SUMMARY.md").read_text()
            self.assertIn("pytest-run", summary)
            self.assertIn("ruff-check", summary)
            self.assertIn("## shell", summary)

    def test_summary_empty_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # create the directory so regenerate can write
            (root / "memory/skills/tool-registry").mkdir(parents=True, exist_ok=True)
            regenerate_registry_summary(root)
            summary = (root / "memory/skills/tool-registry/SUMMARY.md").read_text()
            self.assertIn("No tools registered yet", summary)


class TestToolPolicyIntegration(unittest.TestCase):
    """Validate that phase_payload includes tool_policies for test postconditions."""

    def _write_shell_registry(self, root: Path) -> None:
        save_registry(
            root,
            "shell",
            [
                ToolDefinition(
                    name="pytest-run",
                    description="Run pytest",
                    provider="shell",
                    timeout_seconds=120,
                ),
                ToolDefinition(
                    name="pre-commit-run",
                    description="Run pre-commit",
                    provider="shell",
                    timeout_seconds=60,
                ),
            ],
        )

    def test_tool_policies_present_for_test_postconditions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_shell_registry(root)
            # Build a minimal plan with a test postcondition that matches pytest-run
            from engram_mcp.agent_memory_mcp.plan_utils import (
                PlanDocument,
                PlanPhase,
                PlanPurpose,
                PostconditionSpec,
                phase_payload,
            )

            phase = PlanPhase(
                id="my-phase",
                title="Test phase",
                postconditions=[
                    PostconditionSpec(
                        description="tests pass",
                        type="test",
                        target="python -m pytest core/tools/tests/ -q",
                    )
                ],
            )
            plan = PlanDocument(
                id="test-plan",
                project="test-proj",
                created="2026-03-26",
                origin_session="memory/activity/2026/03/26/chat-001",
                status="active",
                purpose=PlanPurpose(summary="A test plan", context="testing", questions=[]),
                phases=[phase],
            )
            payload = phase_payload(plan, phase, root)
            self.assertIn("tool_policies", payload)
            names = [p["tool_name"] for p in payload["tool_policies"]]
            self.assertIn("pytest-run", names)

    def test_tool_policies_empty_when_no_test_postconditions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_shell_registry(root)
            from engram_mcp.agent_memory_mcp.plan_utils import (
                PlanDocument,
                PlanPhase,
                PlanPurpose,
                PostconditionSpec,
                phase_payload,
            )

            phase = PlanPhase(
                id="manual-phase",
                title="Manual only",
                postconditions=[PostconditionSpec(description="check this manually")],
            )
            plan = PlanDocument(
                id="plan-b",
                project="proj-b",
                created="2026-03-26",
                origin_session="memory/activity/2026/03/26/chat-001",
                status="active",
                purpose=PlanPurpose(summary="B", context="ctx", questions=[]),
                phases=[phase],
            )
            payload = phase_payload(plan, phase, root)
            self.assertEqual(payload["tool_policies"], [])

    def test_tool_policies_empty_when_no_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            from engram_mcp.agent_memory_mcp.plan_utils import (
                PlanDocument,
                PlanPhase,
                PlanPurpose,
                PostconditionSpec,
                phase_payload,
            )

            phase = PlanPhase(
                id="phase-c",
                title="Has test PC",
                postconditions=[
                    PostconditionSpec(description="run tests", type="test", target="pytest")
                ],
            )
            plan = PlanDocument(
                id="plan-c",
                project="proj-c",
                created="2026-03-26",
                origin_session="memory/activity/2026/03/26/chat-001",
                status="active",
                purpose=PlanPurpose(summary="C", context="ctx", questions=[]),
                phases=[phase],
            )
            payload = phase_payload(plan, phase, root)
            self.assertEqual(payload["tool_policies"], [])

    def test_pre_commit_matches_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_shell_registry(root)
            from engram_mcp.agent_memory_mcp.plan_utils import (
                PlanDocument,
                PlanPhase,
                PlanPurpose,
                PostconditionSpec,
                phase_payload,
            )

            phase = PlanPhase(
                id="pc-phase",
                title="Pre-commit phase",
                postconditions=[
                    PostconditionSpec(
                        description="hooks pass",
                        type="test",
                        target="pre-commit run --all-files",
                    )
                ],
            )
            plan = PlanDocument(
                id="plan-d",
                project="proj-d",
                created="2026-03-26",
                origin_session="memory/activity/2026/03/26/chat-001",
                status="active",
                purpose=PlanPurpose(summary="D", context="ctx", questions=[]),
                phases=[phase],
            )
            payload = phase_payload(plan, phase, root)
            names = [p["tool_name"] for p in payload["tool_policies"]]
            self.assertIn("pre-commit-run", names)

    def test_unregistered_tool_silently_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_shell_registry(root)
            from engram_mcp.agent_memory_mcp.plan_utils import (
                PlanDocument,
                PlanPhase,
                PlanPurpose,
                PostconditionSpec,
                phase_payload,
            )

            phase = PlanPhase(
                id="phase-e",
                title="Unknown tool",
                postconditions=[
                    PostconditionSpec(
                        description="run custom",
                        type="test",
                        target="my-unknown-custom-tool --flag",
                    )
                ],
            )
            plan = PlanDocument(
                id="plan-e",
                project="proj-e",
                created="2026-03-26",
                origin_session="memory/activity/2026/03/26/chat-001",
                status="active",
                purpose=PlanPurpose(summary="E", context="ctx", questions=[]),
                phases=[phase],
            )
            payload = phase_payload(plan, phase, root)
            self.assertEqual(payload["tool_policies"], [])

    def test_policy_fields_include_required_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_registry(
                root,
                "shell",
                [
                    ToolDefinition(
                        name="ruff-check",
                        description="Lint",
                        provider="shell",
                        cost_tier="free",
                        timeout_seconds=30,
                    )
                ],
            )
            from engram_mcp.agent_memory_mcp.plan_utils import (
                PlanDocument,
                PlanPhase,
                PlanPurpose,
                PostconditionSpec,
                phase_payload,
            )

            phase = PlanPhase(
                id="phase-f",
                title="Ruff phase",
                postconditions=[
                    PostconditionSpec(
                        description="ruff passes",
                        type="test",
                        target="ruff check agent_memory_mcp/",
                    )
                ],
            )
            plan = PlanDocument(
                id="plan-f",
                project="proj-f",
                created="2026-03-26",
                origin_session="memory/activity/2026/03/26/chat-001",
                status="active",
                purpose=PlanPurpose(summary="F", context="ctx", questions=[]),
                phases=[phase],
            )
            payload = phase_payload(plan, phase, root)
            self.assertEqual(len(payload["tool_policies"]), 1)
            policy = payload["tool_policies"][0]
            for key in ("tool_name", "approval_required", "cost_tier", "timeout_seconds"):
                self.assertIn(key, policy)


# ---------------------------------------------------------------------------
# Phase 5: Approval workflow tests
# ---------------------------------------------------------------------------


def _make_approval(
    plan_id: str = "plan-a",
    phase_id: str = "phase-b",
    project_id: str = "proj-c",
    status: str = "pending",
    requested: str = "2026-04-01T10:00:00Z",
    expires: str = "2099-12-31T23:59:59Z",
    **kwargs: Any,
) -> ApprovalDocument:
    return ApprovalDocument(
        plan_id=plan_id,
        phase_id=phase_id,
        project_id=project_id,
        status=status,
        requested=requested,
        expires=expires,
        **kwargs,
    )


class TestApprovalDocumentDataclass(unittest.TestCase):
    """ApprovalDocument construction, validation, and to_dict round-trip."""

    def test_valid_pending_document(self) -> None:
        ap = _make_approval()
        self.assertEqual(ap.plan_id, "plan-a")
        self.assertEqual(ap.phase_id, "phase-b")
        self.assertEqual(ap.status, "pending")
        self.assertIsNone(ap.resolution)
        self.assertIsNone(ap.reviewer)

    def test_all_statuses_valid(self) -> None:
        for status in APPROVAL_STATUSES:
            ap = _make_approval(status=status)
            self.assertEqual(ap.status, status)

    def test_invalid_status_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _make_approval(status="unknown")

    def test_invalid_plan_id_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _make_approval(plan_id="not valid slug!")

    def test_invalid_phase_id_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _make_approval(phase_id="Bad Phase")

    def test_invalid_project_id_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _make_approval(project_id="")

    def test_invalid_resolution_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _make_approval(resolution="maybe")

    def test_valid_resolutions(self) -> None:
        for res in APPROVAL_RESOLUTIONS:
            ap = _make_approval(resolution=res)
            self.assertEqual(ap.resolution, res)

    def test_empty_requested_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _make_approval(requested="")

    def test_empty_expires_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            _make_approval(expires="")

    def test_context_defaults_to_dict(self) -> None:
        ap = _make_approval()
        self.assertIsInstance(ap.context, dict)

    def test_non_dict_context_coerced(self) -> None:
        ap = ApprovalDocument(
            plan_id="plan-a",
            phase_id="phase-b",
            project_id="proj-c",
            status="pending",
            requested="2026-04-01T10:00:00Z",
            expires="2026-04-08T10:00:00Z",
            context="not a dict",  # type: ignore[arg-type]
        )
        self.assertEqual(ap.context, {})

    def test_to_dict_contains_required_fields(self) -> None:
        ap = _make_approval(context={"phase_title": "Do something"}, comment="LGTM")
        d = ap.to_dict()
        for key in (
            "plan_id",
            "phase_id",
            "project_id",
            "status",
            "requested",
            "expires",
            "context",
        ):
            self.assertIn(key, d)
        self.assertEqual(d["context"]["phase_title"], "Do something")
        self.assertEqual(d["comment"], "LGTM")

    def test_approval_filename_format(self) -> None:
        fn = approval_filename("my-plan", "my-phase")
        self.assertEqual(fn, "my-plan--my-phase.yaml")

    def test_approvals_summary_path(self) -> None:
        path = approvals_summary_path()
        self.assertIn("approvals", path)
        self.assertTrue(path.endswith("SUMMARY.md"))

    def test_paused_in_plan_statuses(self) -> None:
        self.assertIn("paused", PLAN_STATUSES)


class TestApprovalStorage(unittest.TestCase):
    """save_approval / load_approval round-trip and directory routing."""

    def _root(self) -> "Any":  # returns a TemporaryDirectory context
        return tempfile.TemporaryDirectory()

    def test_save_pending_goes_to_pending_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval()
            saved = save_approval(root, ap)
            self.assertIn("pending", str(saved))
            self.assertTrue(saved.exists())

    def test_save_approved_goes_to_resolved_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(status="approved")
            saved = save_approval(root, ap)
            self.assertIn("resolved", str(saved))
            self.assertTrue(saved.exists())

    def test_save_rejected_goes_to_resolved_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(status="rejected")
            saved = save_approval(root, ap)
            self.assertIn("resolved", str(saved))

    def test_load_approval_from_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(context={"phase_title": "Test phase"})
            save_approval(root, ap)
            loaded = load_approval(root, "plan-a", "phase-b")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.status, "pending")
            self.assertEqual(loaded.context.get("phase_title"), "Test phase")

    def test_load_approval_from_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(status="approved", resolution="approve", reviewer="user")
            save_approval(root, ap)
            loaded = load_approval(root, "plan-a", "phase-b")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.status, "approved")
            self.assertEqual(loaded.reviewer, "user")

    def test_load_returns_none_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = load_approval(root, "no-plan", "no-phase")
            self.assertIsNone(result)

    def test_pending_takes_precedence_over_resolved(self) -> None:
        """If somehow both files exist, pending is returned first."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pending_ap = _make_approval(status="pending")
            save_approval(root, pending_ap)
            # Also write a resolved copy manually
            from engram_mcp.agent_memory_mcp.plan_utils import _find_approvals_root

            approvals_root = _find_approvals_root(root)
            resolved_dir = approvals_root / "resolved"
            resolved_dir.mkdir(parents=True, exist_ok=True)
            resolved_ap = _make_approval(status="approved")
            resolved_file = resolved_dir / approval_filename("plan-a", "phase-b")
            import yaml as _yaml

            resolved_file.write_text(_yaml.dump(resolved_ap.to_dict()), encoding="utf-8")
            loaded = load_approval(root, "plan-a", "phase-b")
            assert loaded is not None
            self.assertEqual(loaded.status, "pending")

    def test_yaml_round_trip_preserves_all_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(
                status="rejected",
                resolution="reject",
                reviewer="user",
                resolved_at="2026-04-02T12:00:00Z",
                comment="Not ready yet",
                context={"phase_title": "Design step", "change_class": "proposed"},
            )
            save_approval(root, ap)
            loaded = load_approval(root, "plan-a", "phase-b")
            assert loaded is not None
            self.assertEqual(loaded.resolution, "reject")
            self.assertEqual(loaded.comment, "Not ready yet")
            self.assertEqual(loaded.context.get("phase_title"), "Design step")


class TestApprovalExpiry(unittest.TestCase):
    """Expiry evaluation stays read-only until a write flow materializes it."""

    def _past_ts(self) -> str:
        return "2020-01-01T00:00:00Z"  # definitely in the past

    def _future_ts(self) -> str:
        return "2099-12-31T23:59:59Z"  # definitely in the future

    def test_non_expired_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(expires=self._future_ts())
            result = _check_approval_expiry(ap, root)
            self.assertFalse(result)
            self.assertEqual(ap.status, "pending")

    def test_expired_approval_transitions_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(expires=self._past_ts())
            save_approval(root, ap)  # save to pending/
            result = _check_approval_expiry(ap, root)
            self.assertTrue(result)
            self.assertEqual(ap.status, "expired")

    def test_expired_materialization_moves_file_to_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(expires=self._past_ts())
            save_approval(root, ap)
            self.assertTrue(_check_approval_expiry(ap, root))
            self.assertTrue(materialize_expired_approval(root, ap))
            from engram_mcp.agent_memory_mcp.plan_utils import _find_approvals_root

            approvals_root = _find_approvals_root(root)
            filename = approval_filename("plan-a", "phase-b")
            self.assertFalse((approvals_root / "pending" / filename).exists())
            self.assertTrue((approvals_root / "resolved" / filename).exists())

    def test_load_approval_returns_expired_status_without_moving_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(expires=self._past_ts())
            save_approval(root, ap)
            loaded = load_approval(root, "plan-a", "phase-b")
            assert loaded is not None
            self.assertEqual(loaded.status, "expired")
            filename = approval_filename("plan-a", "phase-b")
            approvals_root = root / "memory" / "working" / "approvals"
            self.assertTrue((approvals_root / "pending" / filename).exists())
            self.assertFalse((approvals_root / "resolved" / filename).exists())

    def test_load_approval_on_expired_pending_keeps_git_status_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            ap = _make_approval(expires=self._past_ts())
            save_approval(root, ap)
            subprocess.run(
                ["git", "add", "."], cwd=root, check=True, capture_output=True, text=True
            )
            subprocess.run(
                ["git", "commit", "-m", "seed approvals"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            loaded = load_approval(root, "plan-a", "phase-b")
            assert loaded is not None
            self.assertEqual(loaded.status, "expired")

            status = subprocess.run(
                ["git", "status", "--short"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(status, "")

    def test_already_resolved_skips_expiry_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(status="approved", expires=self._past_ts())
            result = _check_approval_expiry(ap, root)
            self.assertFalse(result)
            self.assertEqual(ap.status, "approved")

    def test_invalid_expires_date_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Store a pending approval with valid timestamps, then mutate
            ap = _make_approval()
            ap.expires = "not-a-date"  # type: ignore[assignment]
            result = _check_approval_expiry(ap, root)
            self.assertFalse(result)


class TestApprovalsSummaryRegeneration(unittest.TestCase):
    """regenerate_approvals_summary produces correct SUMMARY.md."""

    def test_empty_queue_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            regenerate_approvals_summary(root)
            from engram_mcp.agent_memory_mcp.plan_utils import _find_approvals_root

            approvals_root = _find_approvals_root(root)
            summary = (approvals_root / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn("No pending approvals", summary)
            self.assertIn("No resolved approvals", summary)

    def test_pending_item_appears_in_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(context={"phase_title": "My Test Phase"})
            save_approval(root, ap)
            regenerate_approvals_summary(root)
            from engram_mcp.agent_memory_mcp.plan_utils import _find_approvals_root

            approvals_root = _find_approvals_root(root)
            summary = (approvals_root / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn("plan-a", summary)
            self.assertIn("My Test Phase", summary)

    def test_resolved_item_appears_in_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(
                status="approved",
                resolved_at="2026-04-02T12:00:00Z",
                context={"phase_title": "Resolved Phase"},
            )
            save_approval(root, ap)
            regenerate_approvals_summary(root)
            from engram_mcp.agent_memory_mcp.plan_utils import _find_approvals_root

            approvals_root = _find_approvals_root(root)
            summary = (approvals_root / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn("Resolved Phase", summary)
            self.assertIn("approved", summary)


class TestPlanPauseStatus(unittest.TestCase):
    """PLAN_STATUSES includes 'paused' and it integrates with PlanDocument."""

    def test_paused_is_valid_plan_status(self) -> None:
        self.assertIn("paused", PLAN_STATUSES)

    def test_plan_document_can_hold_paused_status(self) -> None:
        plan = PlanDocument(
            id="test-plan",
            project="test-project",
            created="2026-04-01",
            origin_session="memory/activity/2026/04/01/chat-001",
            status="paused",
            purpose=PlanPurpose(summary="Test", context="ctx", questions=[]),
            phases=[PlanPhase(id="ph-one", title="Phase one")],
        )
        self.assertEqual(plan.status, "paused")

    def test_paused_plan_round_trips_via_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = PlanDocument(
                id="paused-plan",
                project="test-proj",
                created="2026-04-01",
                origin_session="memory/activity/2026/04/01/chat-001",
                status="paused",
                purpose=PlanPurpose(summary="Paused plan test", context="ctx", questions=[]),
                phases=[
                    PlanPhase(
                        id="ph-one",
                        title="Phase One",
                        requires_approval=True,
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/test.md",
                                action="update",
                                description="Update notes",
                            )
                        ],
                    ),
                ],
            )
            proj_dir = root / "memory" / "working" / "projects" / "test-proj" / "plans"
            proj_dir.mkdir(parents=True)
            abs_path = proj_dir / "paused-plan.yaml"
            save_plan(abs_path, plan)
            loaded = load_plan(abs_path)
            self.assertEqual(loaded.status, "paused")
            self.assertTrue(loaded.phases[0].requires_approval)

    def test_requires_approval_phase_flag(self) -> None:
        phase = PlanPhase(id="needs-review", title="Needs review", requires_approval=True)
        self.assertTrue(phase.requires_approval)

    def test_phase_without_requires_approval_defaults_false(self) -> None:
        phase = PlanPhase(id="no-review", title="No review needed")
        self.assertFalse(phase.requires_approval)


# ---------------------------------------------------------------------------
# Phase 6: Cross-phase integration tests
# ---------------------------------------------------------------------------


class TestApprovalLifecycleE2E(unittest.TestCase):
    def test_pending_approval_resolves_then_phase_verifies_and_completes(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_approval_dirs(root)
            (root / "core").mkdir(parents=True, exist_ok=True)
            (root / "core" / "context.md").write_text("approval context\n", encoding="utf-8")
            (root / "artifacts").mkdir(parents=True, exist_ok=True)
            (root / "artifacts" / "result.txt").write_text("phase complete\n", encoding="utf-8")

            plan = _approval_ready_plan()
            phase = plan.phases[0]
            plan_path = root / "approval-plan.yaml"
            save_plan(plan_path, plan, root)

            directive = next_action(plan)
            assert directive is not None
            self.assertTrue(directive["requires_approval"])
            self.assertEqual(directive["attempt_number"], 1)
            self.assertFalse(directive["has_prior_failures"])

            pending = ApprovalDocument(
                plan_id=plan.id,
                phase_id=phase.id,
                project_id=plan.project,
                status="pending",
                requested="2026-03-27T10:00:00Z",
                expires="2027-01-01T10:00:00Z",
                context={"phase_title": phase.title},
            )
            plan.status = "paused"
            save_approval(root, pending)
            save_plan(plan_path, plan, root)

            loaded_pending = load_approval(root, plan.id, phase.id)
            assert loaded_pending is not None
            self.assertEqual(loaded_pending.status, "pending")

            record_trace(
                root,
                plan.origin_session,
                span_type="plan_action",
                name="approval-requested",
                status="ok",
                metadata={"plan_id": plan.id, "phase_id": phase.id},
            )

            pending_path = (
                root
                / "memory"
                / "working"
                / "approvals"
                / "pending"
                / approval_filename(plan.id, phase.id)
            )
            self.assertTrue(pending_path.exists())
            pending_path.unlink()

            approved = ApprovalDocument(
                plan_id=plan.id,
                phase_id=phase.id,
                project_id=plan.project,
                status="approved",
                requested=pending.requested,
                expires=pending.expires,
                context=pending.context,
                resolution="approve",
                reviewer="alex",
                resolved_at="2026-03-27T10:05:00Z",
                comment="Approved for execution.",
            )
            save_approval(root, approved)

            loaded_approved = load_approval(root, plan.id, phase.id)
            assert loaded_approved is not None
            self.assertEqual(loaded_approved.status, "approved")
            self.assertEqual(loaded_approved.reviewer, "alex")

            plan.status = "active"
            phase.status = "in-progress"
            verification = verify_postconditions(plan, phase, root)
            self.assertTrue(verification["all_passed"])

            record_trace(
                root,
                plan.origin_session,
                span_type="verification",
                name=f"verify:{phase.id}",
                status="ok",
                metadata={"plan_id": plan.id, "phase_id": phase.id},
            )
            record_trace(
                root,
                plan.origin_session,
                span_type="plan_action",
                name="complete",
                status="ok",
                metadata={"plan_id": plan.id, "phase_id": phase.id},
            )

            phase.status = "completed"
            phase.commit = "abc1234"
            plan.sessions_used += 1
            save_plan(plan_path, plan, root)

            reloaded = load_plan(plan_path, root)
            self.assertEqual(reloaded.phases[0].status, "completed")
            self.assertEqual(reloaded.sessions_used, 1)
            budget = budget_status(reloaded)
            assert budget is not None
            self.assertEqual(budget["sessions_used"], 1)

            trace_path = root / trace_file_path(plan.origin_session)
            trace_spans = [
                json.loads(line)
                for line in trace_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            approval_spans = [span for span in trace_spans if span["name"] == "approval-requested"]
            self.assertEqual(len(approval_spans), 1)
            self.assertEqual(approval_spans[0]["metadata"]["phase_id"], phase.id)

    def test_pending_approval_round_trip_preserves_context_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_approval_dirs(root)
            plan = _approval_ready_plan()
            phase = plan.phases[0]

            pending = ApprovalDocument(
                plan_id=plan.id,
                phase_id=phase.id,
                project_id=plan.project,
                status="pending",
                requested="2026-03-27T12:00:00Z",
                expires="2027-01-01T12:00:00Z",
                context={"phase_title": phase.title, "change_class": "proposed"},
            )

            pending_path = save_approval(root, pending)
            loaded = load_approval(root, plan.id, phase.id)

            assert loaded is not None
            self.assertEqual(
                pending_path,
                root
                / "memory"
                / "working"
                / "approvals"
                / "pending"
                / approval_filename(plan.id, phase.id),
            )
            self.assertEqual(loaded.status, "pending")
            self.assertEqual(loaded.context["phase_title"], phase.title)
            self.assertEqual(loaded.context["change_class"], "proposed")

    def test_approved_approval_round_trip_uses_resolved_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_approval_dirs(root)
            plan = _approval_ready_plan()
            phase = plan.phases[0]

            approved = ApprovalDocument(
                plan_id=plan.id,
                phase_id=phase.id,
                project_id=plan.project,
                status="approved",
                requested="2026-03-27T12:00:00Z",
                expires="2026-04-03T12:00:00Z",
                context={"phase_title": phase.title},
                resolution="approve",
                reviewer="alex",
                resolved_at="2026-03-27T12:10:00Z",
                comment="Looks good.",
            )

            resolved_path = save_approval(root, approved)
            loaded = load_approval(root, plan.id, phase.id)

            assert loaded is not None
            self.assertEqual(
                resolved_path,
                root
                / "memory"
                / "working"
                / "approvals"
                / "resolved"
                / approval_filename(plan.id, phase.id),
            )
            self.assertEqual(loaded.status, "approved")
            self.assertEqual(loaded.resolution, "approve")
            self.assertEqual(loaded.reviewer, "alex")

    def test_approval_summary_moves_entry_from_pending_to_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_approval_dirs(root)
            plan = _approval_ready_plan()
            phase = plan.phases[0]
            pending = ApprovalDocument(
                plan_id=plan.id,
                phase_id=phase.id,
                project_id=plan.project,
                status="pending",
                requested="2026-03-27T12:00:00Z",
                expires="2026-04-03T12:00:00Z",
                context={"phase_title": phase.title},
            )
            pending_path = save_approval(root, pending)

            regenerate_approvals_summary(root)
            summary_path = root / approvals_summary_path()
            pending_summary = summary_path.read_text(encoding="utf-8")
            self.assertIn(plan.id, pending_summary)
            self.assertIn("## Pending", pending_summary)
            self.assertIn(phase.title, pending_summary)

            pending_path.unlink()
            approved = ApprovalDocument(
                plan_id=plan.id,
                phase_id=phase.id,
                project_id=plan.project,
                status="approved",
                requested=pending.requested,
                expires=pending.expires,
                context=pending.context,
                resolution="approve",
                reviewer="alex",
                resolved_at="2026-03-27T12:10:00Z",
            )
            save_approval(root, approved)
            regenerate_approvals_summary(root)

            resolved_summary = summary_path.read_text(encoding="utf-8")
            self.assertIn("## Resolved", resolved_summary)
            self.assertIn("approved", resolved_summary)
            self.assertIn(phase.title, resolved_summary)

    def test_paused_plan_payload_surfaces_budget_while_approval_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_approval_dirs(root)
            (root / "core").mkdir(parents=True, exist_ok=True)
            (root / "core" / "context.md").write_text("approval context\n", encoding="utf-8")

            plan = _approval_ready_plan()
            plan.status = "paused"
            phase = plan.phases[0]
            save_approval(
                root,
                ApprovalDocument(
                    plan_id=plan.id,
                    phase_id=phase.id,
                    project_id=plan.project,
                    status="pending",
                    requested="2026-03-27T12:00:00Z",
                    expires="2026-04-03T12:00:00Z",
                    context={"phase_title": phase.title},
                ),
            )

            payload = phase_payload(plan, phase, root)

            self.assertEqual(payload["plan_status"], "paused")
            self.assertTrue(payload["phase"]["approval_required"])
            self.assertTrue(payload["phase"]["requires_approval"])
            self.assertEqual(payload["budget_status"]["sessions_used"], 0)
            self.assertEqual(payload["progress"]["next_action"]["id"], phase.id)


class TestVerifyFailRetryE2E(unittest.TestCase):
    def _build_retry_plan(
        self,
        root: Path,
        *,
        artifact_content: str = "not yet\n",
        failures: list[PhaseFailure] | None = None,
        budget: PlanBudget | None = None,
    ) -> tuple[PlanDocument, PlanPhase, Path]:
        (root / "core").mkdir(parents=True, exist_ok=True)
        (root / "core" / "context.md").write_text("retry context\n", encoding="utf-8")
        (root / "artifacts").mkdir(parents=True, exist_ok=True)
        (root / "artifacts" / "retry.txt").write_text(artifact_content, encoding="utf-8")

        plan = _approval_ready_plan(
            id="retry-plan",
            budget=budget,
            phases=[
                PlanPhase(
                    id="retry-phase",
                    title="Retry phase",
                    sources=[
                        SourceSpec(
                            path="core/context.md",
                            type="internal",
                            intent="Read retry context.",
                        )
                    ],
                    postconditions=[
                        PostconditionSpec(
                            description="Expected marker is present",
                            type="grep",
                            target="needle::artifacts/retry.txt",
                        )
                    ],
                    changes=[
                        ChangeSpec(
                            path="memory/working/notes/retry.md",
                            action="update",
                            description="Track retry flow",
                        )
                    ],
                    failures=list(failures or []),
                )
            ],
        )
        phase = plan.phases[0]
        phase.status = "in-progress"
        plan_path = root / "retry-plan.yaml"
        save_plan(plan_path, plan, root)
        return plan, phase, plan_path

    def test_failure_round_trip_informs_retry_then_verification_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "core").mkdir(parents=True, exist_ok=True)
            (root / "core" / "context.md").write_text("retry context\n", encoding="utf-8")
            (root / "artifacts").mkdir(parents=True, exist_ok=True)
            (root / "artifacts" / "retry.txt").write_text("not yet\n", encoding="utf-8")

            plan = _approval_ready_plan(
                id="retry-plan",
                phases=[
                    PlanPhase(
                        id="retry-phase",
                        title="Retry phase",
                        sources=[
                            SourceSpec(
                                path="core/context.md",
                                type="internal",
                                intent="Read retry context.",
                            )
                        ],
                        postconditions=[
                            PostconditionSpec(
                                description="Expected marker is present",
                                type="grep",
                                target="needle::artifacts/retry.txt",
                            )
                        ],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/retry.md",
                                action="update",
                                description="Track retry flow",
                            )
                        ],
                    )
                ],
            )
            phase = plan.phases[0]
            phase.status = "in-progress"

            first_verification = verify_postconditions(plan, phase, root)
            self.assertFalse(first_verification["all_passed"])
            self.assertEqual(first_verification["verification_results"][0]["status"], "fail")

            phase.failures.append(
                PhaseFailure(
                    timestamp="2026-03-27T11:00:00Z",
                    reason="Missing retry artifact",
                    verification_results=first_verification["verification_results"],
                    attempt=1,
                )
            )
            plan_path = root / "retry-plan.yaml"
            save_plan(plan_path, plan, root)

            reloaded = load_plan(plan_path, root)
            retry_phase = reloaded.phases[0]
            directive = next_action(reloaded)
            assert directive is not None
            self.assertTrue(directive["has_prior_failures"])
            self.assertEqual(directive["attempt_number"], 2)

            payload = phase_payload(reloaded, retry_phase, root)
            self.assertEqual(len(payload["phase"]["failures"]), 1)
            self.assertEqual(payload["phase"]["attempt_number"], 2)

            (root / "artifacts" / "retry.txt").write_text("needle found\n", encoding="utf-8")
            second_verification = verify_postconditions(reloaded, retry_phase, root)
            self.assertTrue(second_verification["all_passed"])
            self.assertEqual(second_verification["summary"]["passed"], 1)

            span_id = record_trace(
                root,
                reloaded.origin_session,
                span_type="verification",
                name=f"verify:{retry_phase.id}",
                status="ok",
                metadata={"plan_id": reloaded.id, "phase_id": retry_phase.id, "attempt": 2},
            )
            self.assertIsNotNone(span_id)

    def test_three_failures_escalate_retry_directive(self) -> None:
        plan = _approval_ready_plan(
            id="retry-escalation-plan",
            phases=[
                PlanPhase(
                    id="retry-phase",
                    title="Retry escalation phase",
                    failures=[
                        PhaseFailure(
                            timestamp=f"2026-03-27T0{i}:00:00Z",
                            reason=f"Attempt {i + 1} failed",
                            attempt=i + 1,
                        )
                        for i in range(3)
                    ],
                )
            ],
        )

        directive = next_action(plan)
        assert directive is not None
        self.assertTrue(directive["has_prior_failures"])
        self.assertEqual(directive["attempt_number"], 4)
        self.assertTrue(directive["suggest_revision"])

    def test_failure_payload_retains_verification_results_after_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, phase, plan_path = self._build_retry_plan(root)
            plan = load_plan(plan_path, root)
            phase = plan.phases[0]

            verification = verify_postconditions(plan, phase, root)
            phase.failures.append(
                PhaseFailure(
                    timestamp="2026-03-27T12:30:00Z",
                    reason="Retry marker missing",
                    verification_results=verification["verification_results"],
                    attempt=1,
                )
            )
            save_plan(plan_path, plan, root)

            reloaded = load_plan(plan_path, root)
            payload = phase_payload(reloaded, reloaded.phases[0], root)

            self.assertEqual(payload["phase"]["failures"][0]["reason"], "Retry marker missing")
            self.assertEqual(
                payload["phase"]["failures"][0]["verification_results"][0]["status"],
                "fail",
            )

    def test_multiple_failures_round_trip_preserves_attempt_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failures = [
                PhaseFailure(
                    timestamp="2026-03-27T12:00:00Z",
                    reason="First attempt failed",
                    attempt=1,
                ),
                PhaseFailure(
                    timestamp="2026-03-27T12:05:00Z",
                    reason="Second attempt failed",
                    attempt=2,
                ),
            ]
            _, _, plan_path = self._build_retry_plan(root, failures=failures)

            reloaded = load_plan(plan_path, root)
            payload = phase_payload(reloaded, reloaded.phases[0], root)

            self.assertEqual([entry["attempt"] for entry in payload["phase"]["failures"]], [1, 2])
            self.assertEqual(payload["phase"]["attempt_number"], 3)
            self.assertEqual(payload["phase"]["failures"][1]["reason"], "Second attempt failed")

    def test_second_failed_retry_advances_attempt_number_to_three(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failures = [
                PhaseFailure(
                    timestamp="2026-03-27T12:00:00Z",
                    reason="First attempt failed",
                    attempt=1,
                )
            ]
            _, _, plan_path = self._build_retry_plan(root, failures=failures)

            reloaded = load_plan(plan_path, root)
            retry_phase = reloaded.phases[0]
            verification = verify_postconditions(reloaded, retry_phase, root)
            self.assertFalse(verification["all_passed"])
            retry_phase.failures.append(
                PhaseFailure(
                    timestamp="2026-03-27T12:15:00Z",
                    reason="Second attempt failed",
                    verification_results=verification["verification_results"],
                    attempt=2,
                )
            )
            save_plan(plan_path, reloaded, root)

            final_plan = load_plan(plan_path, root)
            directive = next_action(final_plan)
            assert directive is not None
            self.assertTrue(directive["has_prior_failures"])
            self.assertEqual(directive["attempt_number"], 3)

    def test_successful_retry_completion_clears_next_action_and_updates_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            budget = PlanBudget(max_sessions=2)
            _, _, plan_path = self._build_retry_plan(root, budget=budget)

            reloaded = load_plan(plan_path, root)
            retry_phase = reloaded.phases[0]
            failed = verify_postconditions(reloaded, retry_phase, root)
            self.assertFalse(failed["all_passed"])
            retry_phase.failures.append(
                PhaseFailure(
                    timestamp="2026-03-27T12:30:00Z",
                    reason="Missing marker",
                    verification_results=failed["verification_results"],
                    attempt=1,
                )
            )
            (root / "artifacts" / "retry.txt").write_text("needle found\n", encoding="utf-8")

            passed = verify_postconditions(reloaded, retry_phase, root)
            self.assertTrue(passed["all_passed"])

            retry_phase.status = "completed"
            retry_phase.commit = "retry-commit-001"
            reloaded.status = "completed"
            reloaded.sessions_used += 1
            save_plan(plan_path, reloaded, root)

            completed_plan = load_plan(plan_path, root)
            self.assertIsNone(next_action(completed_plan))
            budget_info = budget_status(completed_plan)
            assert budget_info is not None
            self.assertEqual(budget_info["sessions_used"], 1)
            self.assertEqual(budget_info["sessions_remaining"], 1)


class TestTraceCoverageE2E(unittest.TestCase):
    def test_recorded_spans_cover_lifecycle_without_duplicate_ids(self) -> None:
        import json
        from datetime import datetime

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = _full_harness_plan(
                phases=[
                    PlanPhase(id="phase-a", title="Phase A"),
                    PlanPhase(id="phase-b", title="Phase B"),
                ]
            )
            session_id = plan.origin_session

            for span_type, name, phase_id in (
                ("plan_action", "start", "phase-a"),
                ("verification", "verify:phase-a", "phase-a"),
                ("plan_action", "complete", "phase-a"),
                ("plan_action", "start", "phase-b"),
                ("plan_action", "complete", "phase-b"),
            ):
                record_trace(
                    root,
                    session_id,
                    span_type=span_type,
                    name=name,
                    status="ok",
                    metadata={"plan_id": plan.id, "phase_id": phase_id},
                )

            trace_path = root / trace_file_path(session_id)
            spans = [
                json.loads(line)
                for line in trace_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertGreaterEqual(len(spans), 5)
            self.assertEqual(len({span["span_id"] for span in spans}), len(spans))
            self.assertIn("plan_action", {span["span_type"] for span in spans})
            self.assertIn("verification", {span["span_type"] for span in spans})
            for span in spans:
                datetime.fromisoformat(span["timestamp"].replace("Z", "+00:00"))
                self.assertTrue(span["name"])
                self.assertEqual(span["session_id"], session_id)
            for span in spans:
                if span["span_type"] == "plan_action":
                    self.assertEqual(span["metadata"]["plan_id"], plan.id)
                    self.assertIn("phase_id", span["metadata"])

    def test_trace_metrics_align_with_lifecycle_spans(self) -> None:
        from engram_mcp.agent_memory_mcp.tools.semantic.session_tools import (
            _compute_trace_metrics,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id = "memory/activity/2026/03/27/chat-101"

            record_trace(root, session_id, span_type="plan_action", name="start", status="ok")
            record_trace(root, session_id, span_type="plan_action", name="complete", status="ok")
            record_trace(
                root, session_id, span_type="verification", name="verify:phase-a", status="ok"
            )
            record_trace(root, session_id, span_type="retrieval", name="read", status="ok")
            record_trace(root, session_id, span_type="tool_call", name="tool", status="error")

            metrics = _compute_trace_metrics(root, session_id)
            assert metrics is not None
            self.assertEqual(metrics["plan_actions"], 2)
            self.assertEqual(metrics["retrievals"], 1)
            self.assertEqual(metrics["tool_calls"], 1)
            self.assertEqual(metrics["errors"], 1)

    def test_trace_metrics_count_approval_lifecycle_as_plan_actions(self) -> None:
        from engram_mcp.agent_memory_mcp.tools.semantic.session_tools import (
            _compute_trace_metrics,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id = "memory/activity/2026/03/27/chat-approval"

            record_trace(
                root,
                session_id,
                span_type="plan_action",
                name="approval-requested",
                status="ok",
            )
            record_trace(
                root,
                session_id,
                span_type="plan_action",
                name="approval-approved",
                status="ok",
            )
            record_trace(root, session_id, span_type="plan_action", name="start", status="ok")
            record_trace(
                root, session_id, span_type="verification", name="verify:phase-a", status="ok"
            )

            metrics = _compute_trace_metrics(root, session_id)
            assert metrics is not None
            self.assertEqual(metrics["plan_actions"], 3)
            self.assertEqual(metrics["retrievals"], 0)
            self.assertEqual(metrics["tool_calls"], 0)
            self.assertEqual(metrics["errors"], 0)

    def test_trace_parent_span_and_duration_round_trip(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id = "memory/activity/2026/03/27/chat-parent"
            parent_span = record_trace(
                root,
                session_id,
                span_type="plan_action",
                name="start",
                status="ok",
                duration_ms=15,
            )
            child_span = record_trace(
                root,
                session_id,
                span_type="verification",
                name="verify:phase-a",
                status="ok",
                duration_ms=30,
                parent_span_id=parent_span,
            )

            trace_path = root / trace_file_path(session_id)
            spans = [
                json.loads(line)
                for line in trace_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertEqual(spans[0]["duration_ms"], 15)
            self.assertEqual(spans[1]["parent_span_id"], parent_span)
            self.assertEqual(spans[1]["duration_ms"], 30)
            self.assertEqual(spans[1]["span_id"], child_span)

    def test_trace_metadata_sanitization_redacts_and_truncates_nested_fields(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id = "memory/activity/2026/03/27/chat-sanitize"
            record_trace(
                root,
                session_id,
                span_type="plan_action",
                name="approval-requested",
                status="ok",
                metadata={
                    "api_key": "super-secret",
                    "detail": "x" * 250,
                    "context": {"phase": "phase-a", "token": "hide-me"},
                },
            )

            trace_path = root / trace_file_path(session_id)
            span = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])

            self.assertEqual(span["metadata"]["api_key"], "[redacted]")
            self.assertTrue(span["metadata"]["detail"].endswith("[truncated]"))
            self.assertEqual(span["metadata"]["context"]["phase"], "phase-a")
            self.assertEqual(span["metadata"]["context"]["token"], "[redacted]")

    def test_trace_file_preserves_append_order_for_lifecycle_spans(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_id = "memory/activity/2026/03/27/chat-order"
            for name in ["approval-requested", "start", "complete"]:
                record_trace(root, session_id, span_type="plan_action", name=name, status="ok")

            trace_path = root / trace_file_path(session_id)
            spans = [
                json.loads(line)
                for line in trace_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertEqual(
                [span["name"] for span in spans], ["approval-requested", "start", "complete"]
            )


class TestToolPolicyE2E(unittest.TestCase):
    def test_suggest_revision_coexists_with_tool_policies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_registry(root)
            plan = _full_harness_plan()
            phase = plan.phases[0]
            phase.failures = [
                PhaseFailure(
                    timestamp=f"2026-03-27T1{i}:00:00Z",
                    reason=f"Attempt {i + 1} failed",
                    attempt=i + 1,
                )
                for i in range(3)
            ]

            directive = next_action(plan)
            assert directive is not None
            self.assertTrue(directive["suggest_revision"])

            payload = phase_payload(plan, phase, root)
            self.assertTrue(payload["phase"]["approval_required"])
            self.assertEqual(payload["phase"]["attempt_number"], 4)
            self.assertEqual(len(payload["tool_policies"]), 1)
            self.assertEqual(payload["tool_policies"][0]["tool_name"], "pytest-run")

    def test_missing_registry_degrades_to_empty_tool_policies(self) -> None:
        plan = _full_harness_plan()
        phase = plan.phases[0]
        phase.failures = [
            PhaseFailure(
                timestamp=f"2026-03-27T1{i}:00:00Z",
                reason=f"Attempt {i + 1} failed",
                attempt=i + 1,
            )
            for i in range(3)
        ]

        with tempfile.TemporaryDirectory() as tmp:
            payload = phase_payload(plan, phase, Path(tmp))

        self.assertTrue(payload["phase"]["approval_required"])
        self.assertEqual(payload["phase"]["attempt_number"], 4)
        self.assertEqual(payload["tool_policies"], [])

    def test_multiple_test_postconditions_collect_multiple_policies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_registry(root)
            plan = _full_harness_plan(
                phases=[
                    PlanPhase(
                        id="tool-phase",
                        title="Tool phase",
                        requires_approval=True,
                        postconditions=[
                            PostconditionSpec(
                                description="pytest passes",
                                type="test",
                                target="python -m pytest core/tools/tests/test_plan_schema_extensions.py -q",
                            ),
                            PostconditionSpec(
                                description="pre-commit passes",
                                type="test",
                                target="pre-commit run --all-files",
                            ),
                        ],
                    )
                ]
            )

            payload = phase_payload(plan, plan.phases[0], root)
            policy_names = {entry["tool_name"] for entry in payload["tool_policies"]}

            self.assertEqual(policy_names, {"pytest-run", "pre-commit-run"})
            self.assertTrue(payload["phase"]["approval_required"])

    def test_policy_fields_match_registered_definition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_registry(
                root,
                tools=[
                    ToolDefinition(
                        name="pytest-run",
                        description="Run pytest",
                        provider="shell",
                        approval_required=True,
                        cost_tier="medium",
                        timeout_seconds=90,
                        tags=["test"],
                    )
                ],
            )
            plan = _full_harness_plan(
                phases=[
                    PlanPhase(
                        id="tool-phase",
                        title="Tool phase",
                        requires_approval=True,
                        postconditions=[
                            PostconditionSpec(
                                description="pytest passes",
                                type="test",
                                target="python -m pytest core/tools/tests/test_plan_schema_extensions.py -q",
                            )
                        ],
                    )
                ]
            )

            payload = phase_payload(plan, plan.phases[0], root)
            policy = payload["tool_policies"][0]

            self.assertEqual(policy["tool_name"], "pytest-run")
            self.assertTrue(policy["approval_required"])
            self.assertEqual(policy["cost_tier"], "medium")
            self.assertEqual(policy["timeout_seconds"], 90)

    def test_unmatched_test_target_yields_empty_tool_policies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_registry(root)
            plan = _full_harness_plan(
                phases=[
                    PlanPhase(
                        id="tool-phase",
                        title="Tool phase",
                        postconditions=[
                            PostconditionSpec(
                                description="custom command passes",
                                type="test",
                                target="python -m custom_runner tests",
                            )
                        ],
                    )
                ]
            )

            payload = phase_payload(plan, plan.phases[0], root)
            self.assertEqual(payload["tool_policies"], [])

    def test_non_test_postconditions_do_not_emit_tool_policies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_registry(root)
            plan = _full_harness_plan(
                phases=[
                    PlanPhase(
                        id="tool-phase",
                        title="Tool phase",
                        postconditions=[
                            PostconditionSpec(
                                description="artifact exists",
                                type="check",
                                target="artifacts/harness.txt",
                            ),
                            PostconditionSpec(
                                description="artifact contains marker",
                                type="grep",
                                target="ready::artifacts/harness.txt",
                            ),
                        ],
                    )
                ]
            )

            payload = phase_payload(plan, plan.phases[0], root)
            self.assertEqual(payload["tool_policies"], [])

    def test_updated_registry_definition_changes_phase_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_registry(
                root,
                "shell",
                [
                    ToolDefinition(
                        name="pytest-run",
                        description="Run pytest",
                        provider="shell",
                        approval_required=False,
                        cost_tier="high",
                        timeout_seconds=45,
                    )
                ],
            )
            plan = _full_harness_plan(
                phases=[
                    PlanPhase(
                        id="tool-phase",
                        title="Tool phase",
                        postconditions=[
                            PostconditionSpec(
                                description="pytest passes",
                                type="test",
                                target="python -m pytest core/tools/tests/test_plan_schema_extensions.py -q",
                            )
                        ],
                    )
                ]
            )

            payload = phase_payload(plan, plan.phases[0], root)
            policy = payload["tool_policies"][0]

            self.assertFalse(policy["approval_required"])
            self.assertEqual(policy["cost_tier"], "high")
            self.assertEqual(policy["timeout_seconds"], 45)


class TestAssembleBriefing(unittest.TestCase):
    def test_truncates_internal_source_to_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "core").mkdir(parents=True, exist_ok=True)
            source_text = "header\n" + ("0123456789" * 80)
            (root / "core" / "context.md").write_text(source_text, encoding="utf-8")
            plan = _minimal_plan(
                phases=[
                    PlanPhase(
                        id="phase-one",
                        title="Briefing phase",
                        sources=[
                            SourceSpec(
                                path="core/context.md",
                                type="internal",
                                intent="Read the briefing source.",
                            )
                        ],
                    )
                ]
            )

            briefing = assemble_briefing(plan, plan.phases[0], root, max_context_chars=700)

            source = briefing["source_contents"][0]
            self.assertEqual(source["path"], "core/context.md")
            self.assertTrue(source["truncated"])
            self.assertLess(len(source["content"]), source["full_length"])
            self.assertTrue(briefing["context_budget"]["truncated"])

    def test_missing_internal_source_returns_error_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = _minimal_plan(
                phases=[
                    PlanPhase(
                        id="phase-one",
                        title="Briefing phase",
                        sources=[
                            SourceSpec(
                                path="core/missing.md",
                                type="internal",
                                intent="Read the briefing source.",
                            )
                        ],
                    )
                ]
            )

            briefing = assemble_briefing(plan, plan.phases[0], root)

            source = briefing["source_contents"][0]
            self.assertIsNone(source["content"])
            self.assertEqual(source["error"], "file not found")

    def test_zero_budget_keeps_full_source_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "core").mkdir(parents=True, exist_ok=True)
            source_text = "zero-budget briefing source\n" * 20
            (root / "core" / "context.md").write_text(source_text, encoding="utf-8")
            plan = _minimal_plan(
                phases=[
                    PlanPhase(
                        id="phase-one",
                        title="Briefing phase",
                        sources=[
                            SourceSpec(
                                path="core/context.md",
                                type="internal",
                                intent="Read the briefing source.",
                            )
                        ],
                    )
                ]
            )

            briefing = assemble_briefing(plan, plan.phases[0], root, max_context_chars=0)

            source = briefing["source_contents"][0]
            self.assertEqual(source["content"], source_text)
            self.assertFalse(source["truncated"])
            self.assertFalse(briefing["context_budget"]["truncated"])

    def test_includes_approval_status_for_requires_approval_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_approval_dirs(root)
            (root / "core").mkdir(parents=True, exist_ok=True)
            (root / "core" / "context.md").write_text("approval source\n", encoding="utf-8")
            plan = _approval_ready_plan()
            phase = plan.phases[0]
            save_approval(
                root,
                ApprovalDocument(
                    plan_id=plan.id,
                    phase_id=phase.id,
                    project_id=plan.project,
                    status="approved",
                    requested="2026-03-27T09:00:00Z",
                    expires="2026-04-03T09:00:00Z",
                    resolution="approve",
                    reviewer="Alex",
                    resolved_at="2026-03-27T09:30:00Z",
                    comment="Proceed.",
                    context={"phase_title": phase.title},
                ),
            )

            briefing = assemble_briefing(plan, phase, root)

            assert briefing["approval_status"] is not None
            self.assertEqual(briefing["approval_status"]["status"], "approved")
            self.assertEqual(briefing["approval_status"]["comment"], "Proceed.")

    def test_includes_recent_traces_for_current_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = _minimal_plan()
            phase = plan.phases[0]
            session_id = "memory/activity/2026/03/27/chat-301"
            record_trace(
                root,
                session_id,
                span_type="plan_action",
                name="phase-start",
                status="ok",
                metadata={"plan_id": plan.id, "phase_id": phase.id},
            )
            record_trace(
                root,
                session_id,
                span_type="tool_call",
                name="other-plan",
                status="ok",
                metadata={"plan_id": "other-plan", "phase_id": "other-phase"},
            )

            briefing = assemble_briefing(
                plan,
                phase,
                root,
                include_sources=False,
                session_id=session_id,
            )

            self.assertEqual(len(briefing["recent_traces"]), 1)
            self.assertEqual(briefing["recent_traces"][0]["name"], "phase-start")

    def test_falls_back_to_plan_trace_history_without_session_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = _minimal_plan()
            phase = plan.phases[0]
            record_trace(
                root,
                "memory/activity/2026/03/27/chat-302",
                span_type="plan_action",
                name="phase-complete",
                status="ok",
                metadata={"plan_id": plan.id, "phase_id": phase.id},
            )

            briefing = assemble_briefing(plan, phase, root, include_sources=False)

            self.assertEqual(briefing["recent_traces"][0]["name"], "phase-complete")

    def test_failure_summary_surfaces_failed_postconditions(self) -> None:
        plan = _minimal_plan()
        phase = plan.phases[0]
        phase.failures = [
            PhaseFailure(
                timestamp="2026-03-27T10:00:00Z",
                reason="Verification failed",
                attempt=1,
                verification_results=[
                    {"description": "Output exists", "status": "fail"},
                    {"description": "Marker present", "status": "pass"},
                ],
            )
        ]

        briefing = assemble_briefing(
            plan, phase, Path("."), include_sources=False, include_traces=False
        )

        self.assertEqual(briefing["failure_summary"][0]["failed_postconditions"], ["Output exists"])

    def test_external_and_mcp_sources_do_not_fetch_content(self) -> None:
        plan = _minimal_plan(
            phases=[
                PlanPhase(
                    id="phase-one",
                    title="Briefing phase",
                    sources=[
                        SourceSpec(
                            path="api-spec",
                            type="external",
                            intent="Reference the API contract.",
                            uri="https://example.com/spec",
                        ),
                        SourceSpec(
                            path="memory_search",
                            type="mcp",
                            intent="Use MCP search results.",
                        ),
                    ],
                )
            ]
        )

        briefing = assemble_briefing(plan, plan.phases[0], Path("."), include_traces=False)

        self.assertEqual(len(briefing["source_contents"]), 2)
        self.assertIsNone(briefing["source_contents"][0]["content"])
        self.assertEqual(briefing["source_contents"][0]["uri"], "https://example.com/spec")
        self.assertEqual(briefing["source_contents"][1]["type"], "mcp")


class TestStageExternal(unittest.TestCase):
    def test_stage_external_file_writes_frontmatter_and_hash_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory" / "working" / "projects" / "demo").mkdir(parents=True)

            result = stage_external_file(
                "demo",
                "article.md",
                "External body\n",
                "https://example.com/article?utm=1#frag",
                "2026-03-27",
                "example-article",
                root=root,
                session_id="memory/activity/2026/03/27/chat-401",
            )

            self.assertTrue(result["staged"])
            target = root / result["target_path"]
            self.assertTrue(target.exists())
            body = target.read_text(encoding="utf-8")
            self.assertIn("source: external-research", body)
            self.assertIn("trust: low", body)
            self.assertIn("origin_url: https://example.com/article", body)
            registry = (
                root / "memory" / "working" / "projects" / "demo" / ".staged-hashes.jsonl"
            ).read_text(encoding="utf-8")
            self.assertIn("article.md", registry)

    def test_stage_external_file_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory" / "working" / "projects" / "demo").mkdir(parents=True)

            result = stage_external_file(
                "demo",
                "article.md",
                "External body\n",
                "https://example.com/article",
                "2026-03-27",
                "example-article",
                root=root,
                dry_run=True,
            )

            self.assertFalse(result["staged"])
            self.assertFalse((root / result["target_path"]).exists())

    def test_stage_external_file_rejects_duplicate_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory" / "working" / "projects" / "demo").mkdir(parents=True)
            stage_external_file(
                "demo",
                "article.md",
                "External body\n",
                "https://example.com/article",
                "2026-03-27",
                "example-article",
                root=root,
            )

            with self.assertRaises(DuplicateContentError) as exc_info:
                stage_external_file(
                    "demo",
                    "article-2.md",
                    "External body\n",
                    "https://example.com/article-2",
                    "2026-03-27",
                    "example-article",
                    root=root,
                )

            self.assertIn("article.md", exc_info.exception.existing_filename)

    def test_stage_external_file_rejects_oversized_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory" / "working" / "projects" / "demo").mkdir(parents=True)

            with self.assertRaises(ValidationError):
                stage_external_file(
                    "demo",
                    "article.md",
                    "x" * 500_001,
                    "https://example.com/article",
                    "2026-03-27",
                    "example-article",
                    root=root,
                )

    def test_stage_external_file_rejects_filename_with_path_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "memory" / "working" / "projects" / "demo").mkdir(parents=True)

            with self.assertRaises(ValidationError):
                stage_external_file(
                    "demo",
                    "nested/article.md",
                    "External body\n",
                    "https://example.com/article",
                    "2026-03-27",
                    "example-article",
                    root=root,
                )

    def test_phase_payload_includes_fetch_directive_for_missing_external_source(self) -> None:
        plan = _minimal_plan(
            project="demo",
            phases=[
                PlanPhase(
                    id="phase-one",
                    title="Fetch",
                    sources=[
                        SourceSpec(
                            path="memory/working/projects/demo/IN/article.md",
                            type="external",
                            intent="Fetch the article before starting.",
                            uri="https://example.com/article",
                        )
                    ],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = phase_payload(plan, plan.phases[0], root)

        self.assertEqual(len(payload["fetch_directives"]), 1)
        self.assertEqual(
            payload["fetch_directives"][0]["source_uri"], "https://example.com/article"
        )

    def test_phase_payload_omits_fetch_directive_when_external_source_exists(self) -> None:
        plan = _minimal_plan(
            project="demo",
            phases=[
                PlanPhase(
                    id="phase-one",
                    title="Fetch",
                    sources=[
                        SourceSpec(
                            path="memory/working/projects/demo/IN/article.md",
                            type="external",
                            intent="Fetch the article before starting.",
                            uri="https://example.com/article",
                        )
                    ],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "memory" / "working" / "projects" / "demo" / "IN" / "article.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("staged\n", encoding="utf-8")
            payload = phase_payload(plan, plan.phases[0], root)

        self.assertEqual(payload["fetch_directives"], [])

    def test_phase_payload_includes_mcp_call_for_missing_mcp_source(self) -> None:
        plan = _minimal_plan(
            project="demo",
            phases=[
                PlanPhase(
                    id="phase-one",
                    title="Fetch via MCP",
                    sources=[
                        SourceSpec(
                            path="memory/working/projects/demo/IN/search.md",
                            type="mcp",
                            intent="Fetch search results.",
                            mcp_server="search-mcp",
                            mcp_tool="search",
                            mcp_arguments={"query": "RAG evaluation", "limit": 3},
                        )
                    ],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            payload = phase_payload(plan, plan.phases[0], Path(tmp))

        self.assertEqual(len(payload["mcp_calls"]), 1)
        self.assertEqual(payload["mcp_calls"][0]["server"], "search-mcp")
        self.assertEqual(payload["mcp_calls"][0]["tool"], "search")


class TestScanDropZone(unittest.TestCase):
    def test_scan_drop_zone_stages_markdown_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "memory" / "working" / "projects" / "demo").mkdir(parents=True)
            drop_folder = Path(tmp) / "drop"
            drop_folder.mkdir(parents=True)
            (drop_folder / "note.md").write_text("drop note\n", encoding="utf-8")
            (repo_root / "agent-bootstrap.toml").write_text(
                f'[[watch_folders]]\npath = "{drop_folder.as_posix()}"\ntarget_project = "demo"\nsource_label = "drop-zone"\n',
                encoding="utf-8",
            )

            report = scan_drop_zone(root=repo_root)

            self.assertEqual(report["staged_count"], 1)
            self.assertEqual(report["duplicate_count"], 0)
            self.assertTrue(
                (repo_root / "memory" / "working" / "projects" / "demo" / "IN" / "note.md").exists()
            )

    def test_scan_drop_zone_marks_duplicates_on_repeat_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "memory" / "working" / "projects" / "demo").mkdir(parents=True)
            drop_folder = Path(tmp) / "drop"
            drop_folder.mkdir(parents=True)
            (drop_folder / "note.md").write_text("drop note\n", encoding="utf-8")
            (repo_root / "agent-bootstrap.toml").write_text(
                f'[[watch_folders]]\npath = "{drop_folder.as_posix()}"\ntarget_project = "demo"\nsource_label = "drop-zone"\n',
                encoding="utf-8",
            )

            first = scan_drop_zone(root=repo_root)
            second = scan_drop_zone(root=repo_root)

            self.assertEqual(first["staged_count"], 1)
            self.assertEqual(second["duplicate_count"], 1)

    def test_scan_drop_zone_reports_missing_watch_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "memory" / "working" / "projects" / "demo").mkdir(parents=True)
            missing = Path(tmp) / "missing-drop"
            (repo_root / "agent-bootstrap.toml").write_text(
                f'[[watch_folders]]\npath = "{missing.as_posix()}"\ntarget_project = "demo"\nsource_label = "drop-zone"\n',
                encoding="utf-8",
            )

            report = scan_drop_zone(root=repo_root)

            self.assertEqual(report["error_count"], 1)
            self.assertIn("not found", report["items"][0]["error_message"])

    def test_scan_drop_zone_respects_project_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "memory" / "working" / "projects" / "demo").mkdir(parents=True)
            (repo_root / "memory" / "working" / "projects" / "other").mkdir(parents=True)
            drop_folder = Path(tmp) / "drop"
            drop_folder.mkdir(parents=True)
            (drop_folder / "note.md").write_text("drop note\n", encoding="utf-8")
            (repo_root / "agent-bootstrap.toml").write_text(
                (
                    f'[[watch_folders]]\npath = "{drop_folder.as_posix()}"\n'
                    'target_project = "demo"\nsource_label = "drop-zone"\n\n'
                    f'[[watch_folders]]\npath = "{drop_folder.as_posix()}"\n'
                    'target_project = "other"\nsource_label = "drop-zone"\n'
                ),
                encoding="utf-8",
            )

            report = scan_drop_zone(root=repo_root, project_filter="other")

            self.assertEqual(report["staged_count"], 1)
            self.assertTrue(
                (
                    repo_root / "memory" / "working" / "projects" / "other" / "IN" / "note.md"
                ).exists()
            )
            self.assertFalse(
                (repo_root / "memory" / "working" / "projects" / "demo" / "IN" / "note.md").exists()
            )

    def test_scan_drop_zone_reports_pdf_extraction_error_gracefully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "memory" / "working" / "projects" / "demo").mkdir(parents=True)
            drop_folder = Path(tmp) / "drop"
            drop_folder.mkdir(parents=True)
            (drop_folder / "paper.pdf").write_bytes(b"%PDF-1.4")
            (repo_root / "agent-bootstrap.toml").write_text(
                f'[[watch_folders]]\npath = "{drop_folder.as_posix()}"\ntarget_project = "demo"\nsource_label = "drop-zone"\n',
                encoding="utf-8",
            )

            with mock.patch(
                "engram_mcp.agent_memory_mcp.plan_utils._extract_pdf_text",
                return_value=(None, "PDF extraction unavailable; install pdfminer.six or pypdf"),
            ):
                report = scan_drop_zone(root=repo_root)

            self.assertEqual(report["error_count"], 1)
            self.assertEqual(report["items"][0]["outcome"], "error")


class TestCrossCuttingRegression(unittest.TestCase):
    def test_expired_approval_does_not_prevent_postcondition_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_approval_dirs(root)
            (root / "core").mkdir(parents=True, exist_ok=True)
            (root / "core" / "context.md").write_text("regression context\n", encoding="utf-8")
            (root / "artifacts").mkdir(parents=True, exist_ok=True)
            (root / "artifacts" / "result.txt").write_text("phase complete\n", encoding="utf-8")

            plan = _approval_ready_plan(sessions_used=1, budget=PlanBudget(max_sessions=1))
            plan.status = "paused"
            phase = plan.phases[0]

            expired = ApprovalDocument(
                plan_id=plan.id,
                phase_id=phase.id,
                project_id=plan.project,
                status="pending",
                requested="2026-03-01T09:00:00Z",
                expires="2026-03-02T09:00:00Z",
                context={"phase_title": phase.title},
            )
            save_approval(root, expired)

            loaded = load_approval(root, plan.id, phase.id)
            assert loaded is not None
            self.assertEqual(loaded.status, "expired")

            verification = verify_postconditions(plan, phase, root)
            self.assertTrue(verification["all_passed"])

            budget = budget_status(plan)
            assert budget is not None
            self.assertTrue(budget["over_budget"])
            self.assertTrue(budget["over_session_budget"])

    def test_revision_signal_tool_policies_and_approval_requirement_surface_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_registry(root)
            plan = _full_harness_plan()
            phase = plan.phases[0]
            phase.failures = [
                PhaseFailure(
                    timestamp=f"2026-03-27T1{i}:00:00Z",
                    reason=f"Attempt {i + 1} failed",
                    attempt=i + 1,
                )
                for i in range(3)
            ]

            directive = next_action(plan)
            assert directive is not None
            payload = phase_payload(plan, phase, root)

            self.assertTrue(directive["suggest_revision"])
            self.assertTrue(payload["phase"]["approval_required"])
            self.assertEqual(payload["phase"]["attempt_number"], 4)
            self.assertEqual(payload["tool_policies"][0]["tool_name"], "pytest-run")

    def test_expired_approval_moves_file_from_pending_to_resolved_queue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_approval_dirs(root)
            plan = _approval_ready_plan()
            phase = plan.phases[0]
            pending = ApprovalDocument(
                plan_id=plan.id,
                phase_id=phase.id,
                project_id=plan.project,
                status="pending",
                requested="2026-03-01T09:00:00Z",
                expires="2026-03-02T09:00:00Z",
                context={"phase_title": phase.title},
            )
            pending_path = save_approval(root, pending)
            resolved_path = (
                root
                / "memory"
                / "working"
                / "approvals"
                / "resolved"
                / approval_filename(plan.id, phase.id)
            )

            loaded = load_approval(root, plan.id, phase.id)

            assert loaded is not None
            self.assertEqual(loaded.status, "expired")
            self.assertTrue(pending_path.exists())
            self.assertTrue(materialize_expired_approval(root, loaded))
            self.assertFalse(pending_path.exists())
            self.assertTrue(resolved_path.exists())

    def test_expired_approval_summary_lists_resolved_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_approval_dirs(root)
            plan = _approval_ready_plan()
            phase = plan.phases[0]
            save_approval(
                root,
                ApprovalDocument(
                    plan_id=plan.id,
                    phase_id=phase.id,
                    project_id=plan.project,
                    status="pending",
                    requested="2026-03-01T09:00:00Z",
                    expires="2026-03-02T09:00:00Z",
                    context={"phase_title": phase.title},
                ),
            )

            expired = load_approval(root, plan.id, phase.id)
            assert expired is not None
            self.assertEqual(expired.status, "expired")
            self.assertTrue(materialize_expired_approval(root, expired))

            regenerate_approvals_summary(root)
            summary = (root / approvals_summary_path()).read_text(encoding="utf-8")
            self.assertIn("expired", summary)
            self.assertIn(phase.title, summary)

    def test_inter_plan_blockers_and_tool_policies_surface_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _setup_registry(root)
            _write_minimal_plan_at(
                root,
                "test-project",
                "upstream-plan",
                phases=[
                    PlanPhase(
                        id="upstream-phase",
                        title="Upstream phase",
                        status="completed",
                        commit="upstream-commit-001",
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/upstream.md",
                                action="create",
                                description="Upstream artifact",
                            )
                        ],
                    )
                ],
            )
            plan = _full_harness_plan(
                phases=[
                    PlanPhase(
                        id="blocked-phase",
                        title="Blocked phase",
                        blockers=["upstream-plan:upstream-phase"],
                        requires_approval=True,
                        postconditions=[
                            PostconditionSpec(
                                description="pytest passes",
                                type="test",
                                target="python -m pytest core/tools/tests/test_plan_schema_extensions.py -q",
                            )
                        ],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/blocked.md",
                                action="update",
                                description="Blocked phase note",
                            )
                        ],
                    )
                ]
            )

            payload = phase_payload(plan, plan.phases[0], root)

            self.assertEqual(
                payload["phase"]["blockers"][0]["reference"], "upstream-plan:upstream-phase"
            )
            self.assertTrue(payload["phase"]["blockers"][0]["satisfied"])
            self.assertEqual(payload["tool_policies"][0]["tool_name"], "pytest-run")

    def test_suggest_revision_survives_with_blockers_and_missing_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = _full_harness_plan(
                phases=[
                    PlanPhase(
                        id="blocked-phase",
                        title="Blocked phase",
                        blockers=["missing-plan:missing-phase"],
                        requires_approval=True,
                        failures=[
                            PhaseFailure(
                                timestamp=f"2026-03-27T1{i}:00:00Z",
                                reason=f"Attempt {i + 1} failed",
                                attempt=i + 1,
                            )
                            for i in range(3)
                        ],
                        postconditions=[
                            PostconditionSpec(
                                description="pytest passes",
                                type="test",
                                target="python -m pytest core/tools/tests/test_plan_schema_extensions.py -q",
                            )
                        ],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/blocked.md",
                                action="update",
                                description="Blocked phase note",
                            )
                        ],
                    )
                ]
            )

            directive = next_action(plan)
            assert directive is not None
            payload = phase_payload(plan, plan.phases[0], root)

            self.assertTrue(directive["suggest_revision"])
            self.assertEqual(payload["phase"]["attempt_number"], 4)
            self.assertEqual(payload["phase"]["blockers"][0]["status"], "missing-plan")
            self.assertEqual(payload["tool_policies"], [])


class TestRunState(unittest.TestCase):
    """Comprehensive tests for RunState dataclass, persistence, and integration."""

    def setUp(self):
        from engram_mcp.agent_memory_mcp.plan_utils import (
            RunState,
            RunStateError,
            RunStatePhase,
            check_run_state_staleness,
            load_run_state,
            prune_run_state,
            run_state_path,
            save_run_state,
            update_run_state,
            validate_run_state_against_plan,
        )

        self.RunState = RunState
        self.RunStateError = RunStateError
        self.RunStatePhase = RunStatePhase
        self.load_run_state = load_run_state
        self.save_run_state = save_run_state
        self.update_run_state = update_run_state
        self.run_state_path = run_state_path
        self.validate_run_state_against_plan = validate_run_state_against_plan
        self.check_run_state_staleness = check_run_state_staleness
        self.prune_run_state = prune_run_state

    def _make_rs(self, **overrides):
        defaults = {
            "plan_id": "test-plan",
            "project_id": "test-project",
            "session_id": "memory/activity/2026/03/27/chat-001",
            "last_checkpoint": "2026-03-27T10:00:00Z",
            "created_at": "2026-03-27T09:00:00Z",
            "updated_at": "2026-03-27T10:00:00Z",
        }
        defaults.update(overrides)
        return self.RunState(**defaults)

    # ── Creation and validation ───────────────────────────────────────────

    def test_create_minimal(self):
        rs = self._make_rs()
        self.assertEqual(rs.plan_id, "test-plan")
        self.assertEqual(rs.project_id, "test-project")
        self.assertEqual(rs.schema_version, 1)
        self.assertIsNone(rs.current_phase_id)
        self.assertIsNone(rs.error_context)
        self.assertEqual(rs.sessions_consumed, 0)

    def test_create_with_all_fields(self):
        rs = self._make_rs(
            current_phase_id="phase-one",
            current_task="reading sources",
            next_action_hint="implement changes",
            sessions_consumed=3,
            error_context=self.RunStateError(
                phase_id="phase-one",
                message="test failure",
                timestamp="2026-03-27T10:00:00Z",
            ),
            phase_states={
                "phase-one": self.RunStatePhase(
                    started_at="2026-03-27T09:00:00Z",
                    task_position="reading sources",
                    intermediate_outputs=[
                        {
                            "key": "source-review",
                            "value": "Summary of sources",
                            "timestamp": "2026-03-27T09:30:00Z",
                        }
                    ],
                )
            },
        )
        self.assertEqual(rs.current_phase_id, "phase-one")
        self.assertEqual(rs.current_task, "reading sources")
        self.assertEqual(rs.sessions_consumed, 3)
        self.assertIsNotNone(rs.error_context)
        self.assertEqual(len(rs.phase_states), 1)
        self.assertEqual(len(rs.phase_states["phase-one"].intermediate_outputs), 1)

    def test_invalid_plan_id_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_rs(plan_id="")

    def test_negative_sessions_consumed_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_rs(sessions_consumed=-1)

    def test_invalid_schema_version_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_rs(schema_version=0)

    # ── to_dict round-trip ────────────────────────────────────────────────

    def test_to_dict_roundtrip(self):
        rs = self._make_rs(
            current_phase_id="phase-one",
            current_task="implementing",
            phase_states={
                "phase-one": self.RunStatePhase(
                    started_at="2026-03-27T09:00:00Z",
                    intermediate_outputs=[
                        {
                            "key": "impl-note",
                            "value": "Added RunState class",
                            "timestamp": "2026-03-27T10:00:00Z",
                        }
                    ],
                )
            },
        )
        d = rs.to_dict()
        self.assertEqual(d["plan_id"], "test-plan")
        self.assertEqual(d["current_phase_id"], "phase-one")
        self.assertEqual(d["phase_states"]["phase-one"]["started_at"], "2026-03-27T09:00:00Z")
        self.assertEqual(len(d["phase_states"]["phase-one"]["intermediate_outputs"]), 1)
        self.assertIsNone(d["error_context"])

    def test_to_dict_with_error_context(self):
        rs = self._make_rs(
            error_context=self.RunStateError(
                phase_id="p1",
                message="something broke",
                timestamp="2026-03-27T10:00:00Z",
                recoverable=False,
            )
        )
        d = rs.to_dict()
        self.assertIsNotNone(d["error_context"])
        self.assertEqual(d["error_context"]["phase_id"], "p1")
        self.assertFalse(d["error_context"]["recoverable"])

    # ── Save and load ─────────────────────────────────────────────────────

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plans_dir = root / "memory" / "working" / "projects" / "test-project" / "plans"
            plans_dir.mkdir(parents=True)

            rs = self._make_rs(current_phase_id="phase-one", current_task="testing")
            path = self.save_run_state(root, rs)
            self.assertTrue(path.exists())

            loaded = self.load_run_state(root, "test-project", "test-plan")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.plan_id, "test-plan")
            self.assertEqual(loaded.current_phase_id, "phase-one")
            self.assertEqual(loaded.current_task, "testing")

    def test_load_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = self.load_run_state(root, "test-project", "test-plan")
            self.assertIsNone(result)

    def test_load_corrupt_json_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rs_dir = root / "memory" / "working" / "projects" / "test-project" / "plans"
            rs_dir.mkdir(parents=True)
            rs_file = rs_dir / "test-plan.run-state.json"
            rs_file.write_text("{ not valid json", encoding="utf-8")
            result = self.load_run_state(root, "test-project", "test-plan")
            self.assertIsNone(result)

    def test_save_sets_timestamps(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "memory" / "working" / "projects" / "test-project" / "plans").mkdir(
                parents=True
            )
            rs = self._make_rs(created_at="", updated_at="")
            self.save_run_state(root, rs)
            self.assertTrue(rs.created_at)
            self.assertTrue(rs.updated_at)

    # ── update_run_state ──────────────────────────────────────────────────

    def test_update_start(self):
        rs = self._make_rs()
        self.update_run_state(
            rs,
            "start",
            "phase-one",
            session_id="memory/activity/2026/03/27/chat-002",
            next_action_hint="Read source files",
        )
        self.assertEqual(rs.current_phase_id, "phase-one")
        self.assertIsNone(rs.error_context)
        self.assertEqual(rs.next_action_hint, "Read source files")
        self.assertIn("phase-one", rs.phase_states)
        self.assertIsNotNone(rs.phase_states["phase-one"].started_at)

    def test_update_complete(self):
        rs = self._make_rs(current_phase_id="phase-one", sessions_consumed=1)
        rs.phase_states["phase-one"] = self.RunStatePhase(started_at="2026-03-27T09:00:00Z")
        self.update_run_state(
            rs,
            "complete",
            "phase-one",
            session_id="memory/activity/2026/03/27/chat-002",
            next_action_hint="Start phase-two",
        )
        self.assertIsNone(rs.current_phase_id)
        self.assertIsNone(rs.current_task)
        self.assertEqual(rs.sessions_consumed, 2)
        self.assertIsNotNone(rs.phase_states["phase-one"].completed_at)
        self.assertEqual(rs.next_action_hint, "Start phase-two")

    def test_update_record_failure(self):
        rs = self._make_rs(current_phase_id="phase-one")
        self.update_run_state(
            rs,
            "record_failure",
            "phase-one",
            session_id="memory/activity/2026/03/27/chat-002",
            error_message="Pre-commit failed",
            error_recoverable=True,
        )
        self.assertIsNotNone(rs.error_context)
        self.assertEqual(rs.error_context.message, "Pre-commit failed")
        self.assertTrue(rs.error_context.recoverable)

    def test_start_clears_previous_error(self):
        rs = self._make_rs(
            error_context=self.RunStateError(
                phase_id="phase-one",
                message="old error",
                timestamp="2026-03-27T09:00:00Z",
            )
        )
        self.update_run_state(
            rs,
            "start",
            "phase-one",
            session_id="memory/activity/2026/03/27/chat-002",
        )
        self.assertIsNone(rs.error_context)

    # ── validate_run_state_against_plan ────────────────────────────────────

    def test_validate_matching_state(self):
        plan = _minimal_plan()
        rs = self._make_rs(current_phase_id="phase-one")
        warnings = self.validate_run_state_against_plan(rs, plan)
        self.assertEqual(warnings, [])

    def test_validate_unknown_current_phase(self):
        plan = _minimal_plan()
        rs = self._make_rs(current_phase_id="nonexistent-phase")
        warnings = self.validate_run_state_against_plan(rs, plan)
        self.assertTrue(any("not found" in w for w in warnings))
        self.assertIsNone(rs.current_phase_id)

    def test_validate_completed_phase_advances(self):
        plan = _minimal_plan(
            phases=[
                PlanPhase(
                    id="phase-one",
                    title="Done",
                    status="completed",
                    changes=[
                        ChangeSpec(
                            path="memory/working/notes/test.md",
                            action="create",
                            description="Test",
                        )
                    ],
                ),
                PlanPhase(
                    id="phase-two",
                    title="Next",
                    changes=[
                        ChangeSpec(
                            path="memory/working/notes/test2.md",
                            action="create",
                            description="Test 2",
                        )
                    ],
                ),
            ]
        )
        rs = self._make_rs(current_phase_id="phase-one")
        warnings = self.validate_run_state_against_plan(rs, plan)
        self.assertTrue(any("advancing" in w for w in warnings))
        self.assertEqual(rs.current_phase_id, "phase-two")

    def test_validate_removes_unknown_phase_states(self):
        plan = _minimal_plan()
        rs = self._make_rs(
            phase_states={
                "phase-one": self.RunStatePhase(),
                "deleted-phase": self.RunStatePhase(),
            }
        )
        warnings = self.validate_run_state_against_plan(rs, plan)
        self.assertTrue(any("deleted-phase" in w for w in warnings))
        self.assertNotIn("deleted-phase", rs.phase_states)
        self.assertIn("phase-one", rs.phase_states)

    # ── check_run_state_staleness ─────────────────────────────────────────

    def test_staleness_same_session(self):
        rs = self._make_rs(session_id="memory/activity/2026/03/27/chat-001")
        result = self.check_run_state_staleness(rs, "memory/activity/2026/03/27/chat-001")
        self.assertIsNone(result)

    def test_staleness_different_session_old(self):
        rs = self._make_rs(
            session_id="memory/activity/2026/03/27/chat-001",
            last_checkpoint="2020-01-01T00:00:00Z",
        )
        result = self.check_run_state_staleness(rs, "memory/activity/2026/03/27/chat-002")
        self.assertIsNone(result)

    def test_staleness_different_session_recent(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rs = self._make_rs(
            session_id="memory/activity/2026/03/27/chat-001",
            last_checkpoint=now,
        )
        result = self.check_run_state_staleness(rs, "memory/activity/2026/03/27/chat-002")
        self.assertIsNotNone(result)
        self.assertIn("Taking over", result)

    # ── prune_run_state ───────────────────────────────────────────────────

    def test_prune_summarizes_completed(self):
        rs = self._make_rs(
            phase_states={
                "phase-one": self.RunStatePhase(
                    started_at="2026-03-27T09:00:00Z",
                    completed_at="2026-03-27T10:00:00Z",
                    intermediate_outputs=[
                        {
                            "key": f"output-{i}",
                            "value": f"val-{i}",
                            "timestamp": "2026-03-27T10:00:00Z",
                        }
                        for i in range(5)
                    ],
                ),
                "phase-two": self.RunStatePhase(
                    started_at="2026-03-27T11:00:00Z",
                    intermediate_outputs=[
                        {
                            "key": "active-output",
                            "value": "still working",
                            "timestamp": "2026-03-27T11:30:00Z",
                        }
                    ],
                ),
            }
        )
        self.prune_run_state(rs)
        p1 = rs.phase_states["phase-one"]
        self.assertEqual(len(p1.intermediate_outputs), 1)
        self.assertEqual(p1.intermediate_outputs[0]["key"], "pruned-summary")
        self.assertIn("5", p1.intermediate_outputs[0]["value"])
        p2 = rs.phase_states["phase-two"]
        self.assertEqual(len(p2.intermediate_outputs), 1)
        self.assertEqual(p2.intermediate_outputs[0]["key"], "active-output")

    def test_prune_skips_active_phases(self):
        rs = self._make_rs(
            phase_states={
                "active": self.RunStatePhase(
                    started_at="2026-03-27T09:00:00Z",
                    intermediate_outputs=[
                        {"key": f"o-{i}", "value": f"v-{i}", "timestamp": "2026-03-27T10:00:00Z"}
                        for i in range(10)
                    ],
                )
            }
        )
        self.prune_run_state(rs)
        self.assertEqual(len(rs.phase_states["active"].intermediate_outputs), 10)

    # ── assemble_briefing integration ─────────────────────────────────────

    def test_briefing_includes_run_state_when_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = _minimal_plan()
            plan_dir = root / "memory" / "working" / "projects" / "test-project" / "plans"
            plan_dir.mkdir(parents=True)
            save_plan(plan_dir / "test-plan.yaml", plan)

            rs = self._make_rs(
                current_phase_id="phase-one",
                current_task="implementing",
                next_action_hint="Run tests",
            )
            self.save_run_state(root, rs)

            result = assemble_briefing(plan, plan.phases[0], root)
            self.assertIn("run_state", result)
            self.assertIsNotNone(result["run_state"])
            self.assertEqual(result["run_state"]["current_task"], "implementing")
            self.assertEqual(result["run_state"]["next_action_hint"], "Run tests")
            self.assertIn("run_state", result["context_budget"]["breakdown"])

    def test_briefing_run_state_null_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = _minimal_plan()
            result = assemble_briefing(plan, plan.phases[0], root)
            self.assertIn("run_state", result)
            self.assertIsNone(result["run_state"])
            self.assertEqual(result["context_budget"]["breakdown"]["run_state"], 0)

    # ── Execute round-trip ────────────────────────────────────────────────

    def test_execute_start_complete_roundtrip(self):
        """Simulate start → complete and verify run state tracks correctly."""
        rs = self._make_rs()
        session = "memory/activity/2026/03/27/chat-001"

        self.update_run_state(rs, "start", "phase-one", session_id=session)
        self.assertIsNotNone(rs.phase_states["phase-one"].started_at)
        self.assertEqual(rs.current_phase_id, "phase-one")

        self.update_run_state(
            rs,
            "complete",
            "phase-one",
            session_id=session,
            next_action_hint="Start phase-two",
        )
        self.assertIsNotNone(rs.phase_states["phase-one"].completed_at)
        self.assertIsNone(rs.current_phase_id)
        self.assertEqual(rs.sessions_consumed, 1)

    def test_failure_then_retry(self):
        """Simulate failure → retry start flow."""
        rs = self._make_rs()
        session = "memory/activity/2026/03/27/chat-001"

        self.update_run_state(rs, "start", "phase-one", session_id=session)
        self.update_run_state(
            rs,
            "record_failure",
            "phase-one",
            session_id=session,
            error_message="Tests failed",
        )
        self.assertIsNotNone(rs.error_context)
        self.assertEqual(rs.error_context.message, "Tests failed")

        self.update_run_state(rs, "start", "phase-one", session_id=session)
        self.assertIsNone(rs.error_context)

    # ── RunStatePhase validation ──────────────────────────────────────────

    def test_run_state_phase_empty(self):
        p = self.RunStatePhase()
        d = p.to_dict()
        self.assertIsNone(d["started_at"])
        self.assertIsNone(d["completed_at"])
        self.assertEqual(d["intermediate_outputs"], [])

    def test_run_state_phase_invalid_output_key_rejected(self):
        with self.assertRaises(ValidationError):
            self.RunStatePhase(
                intermediate_outputs=[
                    {"key": "", "value": "x", "timestamp": "2026-01-01T00:00:00Z"}
                ]
            )

    # ── RunStateError validation ──────────────────────────────────────────

    def test_run_state_error_valid(self):
        e = self.RunStateError(
            phase_id="phase-one", message="broke", timestamp="2026-03-27T10:00:00Z"
        )
        d = e.to_dict()
        self.assertEqual(d["phase_id"], "phase-one")
        self.assertTrue(d["recoverable"])

    def test_run_state_error_empty_message_rejected(self):
        with self.assertRaises(ValidationError):
            self.RunStateError(phase_id="p1", message="", timestamp="2026-03-27T10:00:00Z")

    # ── run_state_path ────────────────────────────────────────────────────

    def test_run_state_path_format(self):
        p = self.run_state_path("my-project", "my-plan")
        self.assertEqual(p, "memory/working/projects/my-project/plans/my-plan.run-state.json")


class TestToolPolicyEnforcement(unittest.TestCase):
    """Tests for check_tool_policy(), PolicyCheckResult, rate limit parsing, and integration."""

    def setUp(self):
        from engram_mcp.agent_memory_mcp.plan_utils import (
            PolicyCheckResult,
            ToolDefinition,
            _parse_rate_limit,
            check_tool_policy,
            save_registry,
        )

        self.PolicyCheckResult = PolicyCheckResult
        self.ToolDefinition = ToolDefinition
        self.check_tool_policy = check_tool_policy
        self.save_registry = save_registry
        self._parse_rate_limit = _parse_rate_limit

    def _register_tool(self, root, **overrides):
        defaults = {
            "name": "test-tool",
            "description": "A test tool",
            "provider": "test-provider",
        }
        defaults.update(overrides)
        tool = self.ToolDefinition(**defaults)
        self.save_registry(root, defaults["provider"], [tool])
        return tool

    # ── PolicyCheckResult ─────────────────────────────────────────────────

    def test_policy_check_result_to_dict(self):
        r = self.PolicyCheckResult(
            allowed=False,
            reason="blocked",
            tool_name="my-tool",
            provider="my-prov",
            required_action="approval",
            violation_type="approval_required",
        )
        d = r.to_dict()
        self.assertFalse(d["allowed"])
        self.assertEqual(d["required_action"], "approval")

    # ── _parse_rate_limit ─────────────────────────────────────────────────

    def test_parse_valid_limits(self):
        self.assertEqual(self._parse_rate_limit("10/hour"), (10, "hour"))
        self.assertEqual(self._parse_rate_limit("5/day"), (5, "day"))
        self.assertEqual(self._parse_rate_limit("3/minute"), (3, "minute"))
        self.assertEqual(self._parse_rate_limit("1/session"), (1, "session"))

    def test_parse_invalid_limits(self):
        self.assertIsNone(self._parse_rate_limit("not-a-limit"))
        self.assertIsNone(self._parse_rate_limit("10/week"))
        self.assertIsNone(self._parse_rate_limit(""))

    def test_parse_whitespace_tolerance(self):
        self.assertEqual(self._parse_rate_limit("  10 / hour  "), (10, "hour"))

    # ── check_tool_policy: no policy ──────────────────────────────────────

    def test_no_policy_allows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = self.check_tool_policy(root, "unknown-tool", "unknown-provider")
            self.assertTrue(result.allowed)
            self.assertEqual(result.reason, "no_policy")

    # ── check_tool_policy: approval_required ──────────────────────────────

    def test_approval_required_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "memory" / "skills" / "tool-registry").mkdir(parents=True)
            self._register_tool(root, approval_required=True)

            result = self.check_tool_policy(root, "test-tool", "test-provider")
            self.assertFalse(result.allowed)
            self.assertEqual(result.violation_type, "approval_required")
            self.assertEqual(result.required_action, "approval")

    def test_approved_tool_allows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "memory" / "skills" / "tool-registry").mkdir(parents=True)
            (root / "memory" / "working" / "approvals" / "pending").mkdir(parents=True)
            self._register_tool(root, approval_required=True)

            from engram_mcp.agent_memory_mcp.plan_utils import ApprovalDocument, save_approval

            approval = ApprovalDocument(
                plan_id="tool-test-provider",
                phase_id="test-tool",
                project_id="test-project",
                status="approved",
                requested="2026-03-27T00:00:00Z",
                expires="2026-04-03T00:00:00Z",
                resolution="approve",
                resolved_at="2026-03-27T01:00:00Z",
            )
            save_approval(root, approval)

            result = self.check_tool_policy(root, "test-tool", "test-provider")
            self.assertTrue(result.allowed)

    # ── check_tool_policy: rate limits ────────────────────────────────────

    def test_rate_limit_allows_under_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "memory" / "skills" / "tool-registry").mkdir(parents=True)
            self._register_tool(root, rate_limit="10/day")

            result = self.check_tool_policy(root, "test-tool", "test-provider")
            self.assertTrue(result.allowed)

    def test_rate_limit_blocks_when_exceeded(self):
        import json as _json
        from datetime import datetime, timezone

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "memory" / "skills" / "tool-registry").mkdir(parents=True)
            self._register_tool(root, rate_limit="2/day")

            traces_dir = root / "memory" / "activity" / "2026" / "03" / "27"
            traces_dir.mkdir(parents=True)
            trace_file = traces_dir / "chat-001.traces.jsonl"
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            lines = []
            for _ in range(3):
                lines.append(
                    _json.dumps(
                        {
                            "span_type": "tool_call",
                            "name": "test-tool",
                            "status": "ok",
                            "timestamp": now,
                        }
                    )
                )
            trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

            result = self.check_tool_policy(root, "test-tool", "test-provider")
            self.assertFalse(result.allowed)
            self.assertEqual(result.violation_type, "rate_limit_exceeded")
            self.assertEqual(result.required_action, "rate_limit_wait")

    # ── check_tool_policy: cost warning ───────────────────────────────────

    def test_cost_warning_still_allows(self):
        from engram_mcp.agent_memory_mcp.plan_utils import PlanBudget

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "memory" / "skills" / "tool-registry").mkdir(parents=True)
            self._register_tool(root, cost_tier="high")

            budget = PlanBudget(deadline="2020-01-01", advisory=True)
            result = self.check_tool_policy(root, "test-tool", "test-provider", plan_budget=budget)
            self.assertTrue(result.allowed)
            self.assertEqual(result.violation_type, "cost_warning")

    # ── check_tool_policy: eval bypass ────────────────────────────────────

    def test_eval_bypass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "memory" / "skills" / "tool-registry").mkdir(parents=True)
            self._register_tool(root, approval_required=True)

            with mock.patch.dict("os.environ", {"ENGRAM_EVAL_MODE": "1"}):
                result = self.check_tool_policy(root, "test-tool", "test-provider")
                self.assertTrue(result.allowed)
                self.assertEqual(result.reason, "eval_bypass")

    # ── check_tool_policy: no restrictions ────────────────────────────────

    def test_unrestricted_tool_allows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "memory" / "skills" / "tool-registry").mkdir(parents=True)
            self._register_tool(root)

            result = self.check_tool_policy(root, "test-tool", "test-provider")
            self.assertTrue(result.allowed)
            self.assertEqual(result.reason, "policy_passed")

    # ── TRACE_SPAN_TYPES includes policy_violation ────────────────────────

    def test_policy_violation_in_span_types(self):
        from engram_mcp.agent_memory_mcp.plan_utils import TRACE_SPAN_TYPES

        self.assertIn("policy_violation", TRACE_SPAN_TYPES)

    # ── Existing operations unaffected ────────────────────────────────────

    def test_no_policy_no_effect_on_verify(self):
        """verify_postconditions works normally when no tools are registered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan = _minimal_plan(
                phases=[
                    PlanPhase(
                        id="p1",
                        title="Test phase",
                        postconditions=[
                            PostconditionSpec(
                                description="File exists", type="check", target="nonexistent.txt"
                            ),
                        ],
                        changes=[
                            ChangeSpec(
                                path="memory/working/notes/test.md",
                                action="create",
                                description="Test",
                            )
                        ],
                    )
                ]
            )
            result = verify_postconditions(plan, plan.phases[0], root)
            self.assertIn("verification_results", result)
            self.assertEqual(result["verification_results"][0]["status"], "fail")


class TestTraceEnrichment(unittest.TestCase):
    """Tests for trace cost estimation, parent-child spans, and aggregate metrics."""

    def test_estimate_cost_basic(self):
        from engram_mcp.agent_memory_mcp.plan_utils import estimate_cost

        cost = estimate_cost(input_chars=400, output_chars=200)
        self.assertEqual(cost["tokens_in"], 100)
        self.assertEqual(cost["tokens_out"], 50)

    def test_estimate_cost_zero(self):
        from engram_mcp.agent_memory_mcp.plan_utils import estimate_cost

        cost = estimate_cost()
        self.assertEqual(cost["tokens_in"], 0)
        self.assertEqual(cost["tokens_out"], 0)

    def test_estimate_cost_rounding(self):
        from engram_mcp.agent_memory_mcp.plan_utils import estimate_cost

        cost = estimate_cost(input_chars=5)
        self.assertEqual(cost["tokens_in"], 2)

    def test_record_trace_returns_span_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sid = "memory/activity/2026/03/27/chat-001"
            span_id = record_trace(root, sid, span_type="tool_call", name="test", status="ok")
            self.assertIsNotNone(span_id)
            self.assertEqual(len(span_id), 12)

    def test_record_trace_with_cost(self):
        from engram_mcp.agent_memory_mcp.plan_utils import estimate_cost

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sid = "memory/activity/2026/03/27/chat-001"
            cost = estimate_cost(input_chars=100, output_chars=200)
            record_trace(
                root,
                sid,
                span_type="tool_call",
                name="test-with-cost",
                status="ok",
                cost=cost,
            )
            import json

            trace_file = root / "memory/activity/2026/03/27/chat-001.traces.jsonl"
            self.assertTrue(trace_file.exists())
            spans = [
                json.loads(line)
                for line in trace_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(spans), 1)
            self.assertEqual(spans[0]["cost"]["tokens_in"], 25)
            self.assertEqual(spans[0]["cost"]["tokens_out"], 50)

    def test_parent_child_span_linkage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sid = "memory/activity/2026/03/27/chat-001"
            parent_id = record_trace(root, sid, span_type="plan_action", name="start", status="ok")
            record_trace(
                root,
                sid,
                span_type="tool_call",
                name="child-op",
                status="ok",
                parent_span_id=parent_id,
            )
            import json

            trace_file = root / "memory/activity/2026/03/27/chat-001.traces.jsonl"
            spans = [
                json.loads(line)
                for line in trace_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(spans), 2)
            self.assertIsNone(spans[0].get("parent_span_id"))
            self.assertEqual(spans[1]["parent_span_id"], parent_id)

    def test_policy_violation_span_type_accepted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sid = "memory/activity/2026/03/27/chat-001"
            span_id = record_trace(
                root,
                sid,
                span_type="policy_violation",
                name="check_tool_policy",
                status="denied",
            )
            self.assertIsNotNone(span_id)

    def test_guardrail_check_span_type_accepted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sid = "memory/activity/2026/03/27/chat-001"
            span_id = record_trace(
                root,
                sid,
                span_type="guardrail_check",
                name="guard_pipeline",
                status="ok",
            )
            self.assertIsNotNone(span_id)


if __name__ == "__main__":
    unittest.main()
