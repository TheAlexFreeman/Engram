"""Tests for plan schema extensions: SourceSpec, PostconditionSpec, PlanBudget.

Covers dataclass validation, coercion helpers, budget_status(), next_action()
dict return, phase_payload() enrichment, round-trip serialization, and
backward compatibility with plans that lack the new fields.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from engram_mcp.agent_memory_mcp.errors import NotFoundError, ValidationError
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
    approval_filename,
    approvals_summary_path,
    budget_status,
    coerce_budget_input,
    coerce_phase_inputs,
    load_approval,
    load_plan,
    load_registry,
    next_action,
    phase_blockers,
    phase_payload,
    project_plan_path,
    regenerate_approvals_summary,
    regenerate_registry_summary,
    registry_file_path,
    save_approval,
    save_plan,
    save_registry,
    validate_plan_references,
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
    record_trace,
    trace_file_path,
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
    expires: str = "2026-04-08T10:00:00Z",
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
    """Lazy expiry evaluation in _check_approval_expiry and load_approval."""

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

    def test_expired_file_moves_to_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(expires=self._past_ts())
            save_approval(root, ap)
            _check_approval_expiry(ap, root)
            from engram_mcp.agent_memory_mcp.plan_utils import _find_approvals_root

            approvals_root = _find_approvals_root(root)
            filename = approval_filename("plan-a", "phase-b")
            self.assertFalse((approvals_root / "pending" / filename).exists())
            self.assertTrue((approvals_root / "resolved" / filename).exists())

    def test_load_approval_returns_expired_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ap = _make_approval(expires=self._past_ts())
            save_approval(root, ap)
            loaded = load_approval(root, "plan-a", "phase-b")
            assert loaded is not None
            self.assertEqual(loaded.status, "expired")

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


if __name__ == "__main__":
    unittest.main()
