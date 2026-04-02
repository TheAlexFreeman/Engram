from __future__ import annotations

import importlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_server_main_module() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    return importlib.import_module("engram_mcp.agent_memory_mcp.server_main")


class ServerMainCliTests(unittest.TestCase):
    module: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_server_main_module()

    def test_main_without_args_runs_server(self) -> None:
        with mock.patch.object(self.module.mcp, "run") as run_mock:
            result = self.module.main([])

        self.assertEqual(result, 0)
        run_mock.assert_called_once_with()

    def test_serve_subcommand_runs_server(self) -> None:
        with mock.patch.object(self.module.mcp, "run") as run_mock:
            result = self.module.main(["serve"])

        self.assertEqual(result, 0)
        run_mock.assert_called_once_with()

    def test_plan_create_help_mentions_schema_backing(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as ctx:
            self.module.main(["plan", "create", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        output = stdout.getvalue()
        self.assertIn("Schema-backed help for plan creation.", output)
        self.assertIn("memory_plan_schema", output)
        self.assertIn("modify -> update", output)
        self.assertIn("--json-schema", output)

    def test_plan_create_json_schema_outputs_raw_schema(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            result = self.module.main(["plan", "create", "--json-schema"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(result, 0)
        self.assertEqual(payload["tool_name"], "memory_plan_create")
        self.assertIn("phases", payload["properties"])
        self.assertEqual(
            payload["properties"]["phases"]["items"]["properties"]["changes"]["items"][
                "properties"
            ]["action"]["x-aliases"]["modify"],
            "update",
        )


if __name__ == "__main__":
    unittest.main()
