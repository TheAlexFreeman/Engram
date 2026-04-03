from __future__ import annotations

import unittest
from typing import Any, cast

from engram_mcp.agent_memory_mcp.errors import ValidationError
from engram_mcp.agent_memory_mcp.plan_utils import (
    PlanDocument,
    build_plan_document_from_create_input,
    validation_error_messages,
)


class TestPlanCreateValidationAggregation(unittest.TestCase):
    def test_build_plan_document_from_create_input_returns_plan_document(self) -> None:
        plan = build_plan_document_from_create_input(
            plan_id="test-plan",
            project_id="test-project",
            created="2026-04-03",
            session_id="memory/activity/2026/04/03/chat-001",
            status="active",
            purpose_summary="Test plan",
            purpose_context="Exercise aggregated plan validation.",
            questions=["What should ship first?"],
            phases=[
                {
                    "id": "phase-a",
                    "title": "Do the work",
                    "changes": [
                        {
                            "path": "memory/working/projects/test-project/notes/out.md",
                            "action": "create",
                            "description": "Create the output note.",
                        }
                    ],
                }
            ],
            budget={"deadline": "2026-05-01", "max_sessions": 3},
        )

        self.assertIsInstance(plan, PlanDocument)
        self.assertEqual(plan.status, "active")
        self.assertEqual(plan.budget.deadline if plan.budget else None, "2026-05-01")
        self.assertEqual(len(plan.phases), 1)

    def test_build_plan_document_from_create_input_aggregates_top_level_errors(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            build_plan_document_from_create_input(
                plan_id="test-plan",
                project_id="test-project",
                created="2026-04-03",
                session_id="chat-001",
                status="paused",
                purpose_summary="   ",
                purpose_context="",
                questions=cast(Any, "not-a-list"),
                phases=[
                    {
                        "id": "phase-a",
                        "title": "Do the work",
                        "changes": [
                            {
                                "path": "memory/working/projects/test-project/notes/out.md",
                                "action": "create",
                                "description": "Create the output note.",
                            }
                        ],
                    }
                ],
                budget={"deadline": "April 3, 2026", "max_sessions": "zero"},
            )

        errors = validation_error_messages(ctx.exception)

        self.assertGreaterEqual(len(errors), 7)
        self.assertTrue(any("session_id" in error for error in errors))
        self.assertTrue(any("memory_plan_create status" in error for error in errors))
        self.assertTrue(any("purpose.summary" in error for error in errors))
        self.assertTrue(any("purpose.context" in error for error in errors))
        self.assertTrue(any("purpose.questions must be a list" in error for error in errors))
        self.assertTrue(any("budget.deadline" in error for error in errors))
        self.assertTrue(any("budget.max_sessions" in error for error in errors))

    def test_build_plan_document_aggregates_errors_across_multiple_phases(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            build_plan_document_from_create_input(
                plan_id="test-plan",
                project_id="test-project",
                created="2026-04-03",
                session_id="memory/activity/2026/04/03/chat-001",
                status="active",
                purpose_summary="Multi-phase invalid changes",
                purpose_context="Each phase has an empty change description.",
                questions=None,
                phases=[
                    {
                        "id": "phase-a",
                        "title": "First",
                        "changes": [
                            {
                                "path": "memory/working/projects/test-project/notes/a.md",
                                "action": "create",
                                "description": "   ",
                            }
                        ],
                    },
                    {
                        "id": "phase-b",
                        "title": "Second",
                        "changes": [
                            {
                                "path": "memory/working/projects/test-project/notes/b.md",
                                "action": "create",
                                "description": "",
                            }
                        ],
                    },
                ],
                budget=None,
            )

        errors = validation_error_messages(ctx.exception)
        p0 = "work.phases[0].changes[0]"
        p1 = "work.phases[1].changes[0]"
        self.assertTrue(any(p0 in error for error in errors))
        self.assertTrue(any(p1 in error for error in errors))
