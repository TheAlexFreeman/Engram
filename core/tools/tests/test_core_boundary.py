from __future__ import annotations

import importlib
import sys
import unittest


class AgentMemoryCoreBoundaryTests(unittest.TestCase):
    def test_package_root_does_not_import_server_eagerly(self) -> None:
        sys.modules.pop("engram_mcp.agent_memory_mcp", None)
        sys.modules.pop("engram_mcp.agent_memory_mcp.server", None)

        package = importlib.import_module("engram_mcp.agent_memory_mcp")

        self.assertNotIn("engram_mcp.agent_memory_mcp.server", sys.modules)
        self.assertIn("core", dir(package))

    def test_core_namespace_reexports_format_layer_modules(self) -> None:
        core = importlib.import_module("engram_mcp.agent_memory_mcp.core")
        errors = importlib.import_module("engram_mcp.agent_memory_mcp.errors")
        frontmatter_utils = importlib.import_module("engram_mcp.agent_memory_mcp.frontmatter_utils")
        git_repo = importlib.import_module("engram_mcp.agent_memory_mcp.git_repo")
        models = importlib.import_module("engram_mcp.agent_memory_mcp.models")
        path_policy = importlib.import_module("engram_mcp.agent_memory_mcp.path_policy")

        self.assertIs(core.errors.AgentMemoryError, errors.AgentMemoryError)
        self.assertIs(
            core.frontmatter_utils.read_with_frontmatter, frontmatter_utils.read_with_frontmatter
        )
        self.assertIs(core.git_repo.GitRepo, git_repo.GitRepo)
        self.assertIs(core.models.MemoryWriteResult, models.MemoryWriteResult)
        self.assertIs(core.path_policy.validate_session_id, path_policy.validate_session_id)


if __name__ == "__main__":
    unittest.main()
