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
    ChangeSpec,
    PlanBudget,
    PlanDocument,
    PlanPhase,
    PlanPurpose,
    PostconditionSpec,
    SourceSpec,
    budget_status,
    coerce_budget_input,
    coerce_phase_inputs,
    load_plan,
    next_action,
    phase_blockers,
    phase_payload,
    project_plan_path,
    save_plan,
    validate_plan_references,
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


if __name__ == "__main__":
    unittest.main()
