from __future__ import annotations

import copy
import unittest

from engram_mcp.agent_memory_mcp.cli.plan_help import (
    build_plan_create_help_text,
    format_alias_list,
    format_enum_list,
)
from engram_mcp.agent_memory_mcp.plan_utils import plan_create_input_schema


class PlanHelpFormattingTests(unittest.TestCase):
    def test_format_enum_list_joins_values(self) -> None:
        self.assertEqual(
            format_enum_list(["create", "update", "delete"]), "create | update | delete"
        )

    def test_format_alias_list_returns_none_for_empty_aliases(self) -> None:
        self.assertEqual(format_alias_list({}), "none")
        self.assertEqual(format_alias_list(None), "none")

    def test_build_help_includes_schema_backed_sections(self) -> None:
        help_text = build_plan_create_help_text(plan_create_input_schema())

        self.assertIn("Schema-backed help for plan creation.", help_text)
        self.assertIn("memory_plan_schema", help_text)
        self.assertIn("modify -> update", help_text)
        self.assertIn("check = file exists", help_text)

    def test_build_help_finds_postcondition_object_variant_without_oneof_order_assumption(
        self,
    ) -> None:
        schema = copy.deepcopy(plan_create_input_schema())
        one_of = schema["properties"]["phases"]["items"]["properties"]["postconditions"]["items"][
            "oneOf"
        ]
        schema["properties"]["phases"]["items"]["properties"]["postconditions"]["items"][
            "oneOf"
        ] = [one_of[1], one_of[0]]

        help_text = build_plan_create_help_text(schema)

        self.assertIn("file_check -> check", help_text)
        self.assertIn("target is required when type != manual", help_text)

    def test_build_help_handles_missing_aliases(self) -> None:
        schema = copy.deepcopy(plan_create_input_schema())
        del schema["properties"]["phases"]["items"]["properties"]["changes"]["items"]["properties"][
            "action"
        ]["x-aliases"]

        help_text = build_plan_create_help_text(schema)

        self.assertIn("Changes:", help_text)
        self.assertIn("- aliases: none", help_text)


if __name__ == "__main__":
    unittest.main()
