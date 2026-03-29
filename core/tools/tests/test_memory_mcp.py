from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, ClassVar, cast

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "core" / "tools" / "memory_mcp.py"
VENV_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"


def load_memory_mcp_module():
    spec = importlib.util.spec_from_file_location("memory_mcp", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"memory_mcp dependencies unavailable: {exc.name}")
    return module


class MemoryMCPTests(unittest.TestCase):
    module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_memory_mcp_module()

    def test_root_listing_hides_humans_by_default(self) -> None:
        output = asyncio.run(self.module.memory_list_folder(path="."))

        self.assertNotIn("HUMANS/", output)
        self.assertIn("memory/", output)

    def test_root_listing_can_include_humans(self) -> None:
        output = asyncio.run(self.module.memory_list_folder(path=".", include_humans=True))

        self.assertIn("HUMANS/", output)

    def test_explicit_humans_listing_still_works(self) -> None:
        output = asyncio.run(self.module.memory_list_folder(path="HUMANS"))

        self.assertIn("docs/", output)
        self.assertIn("tooling/", output)

    def test_search_hides_humans_by_default(self) -> None:
        output = asyncio.run(
            self.module.memory_search(query="Human-Focused Documentation", path=".")
        )

        self.assertIn("No matches", output)

    def test_search_can_include_humans(self) -> None:
        output = asyncio.run(
            self.module.memory_search(
                query="Human-Focused Documentation",
                path=".",
                include_humans=True,
            )
        )

        self.assertIn("HUMANS/README.md", output)

    def test_explicit_humans_read_still_works(self) -> None:
        raw = asyncio.run(self.module.memory_read_file(path="HUMANS/README.md"))
        output = json.loads(raw)

        self.assertTrue(output["inline"])
        self.assertIn("Human-Focused Documentation", output["content"])
        self.assertIn("version_token", output)

    def test_read_file_returns_structured_payload(self) -> None:
        raw = asyncio.run(self.module.memory_read_file(path="INIT.md"))
        payload = json.loads(raw)

        self.assertEqual(payload["path"], "INIT.md")
        self.assertTrue(payload["inline"])
        self.assertGreater(payload["size_bytes"], 0)
        self.assertIn("version_token", payload)
        self.assertIsNone(payload["frontmatter"])
        self.assertIn("# Session Init", payload["content"])
        self.assertNotIn("temp_file", payload)

    def test_get_capabilities_returns_structured_payload(self) -> None:
        raw = asyncio.run(self.module.memory_get_capabilities())
        payload = json.loads(raw)

        self.assertEqual(payload["kind"], "agent-memory-capabilities")
        self.assertEqual(payload["contract_versions"]["capabilities"], 1)
        self.assertEqual(payload["contract_versions"]["resources"], 1)
        self.assertEqual(payload["contract_versions"]["prompts"], 1)
        self.assertEqual(payload["contract_versions"]["provenance"], 1)
        self.assertEqual(payload["contract_versions"]["structured_read"], 1)
        self.assertIn("memory_get_capabilities", payload["tool_sets"]["read_support"])
        self.assertIn("memory_resolve_link", payload["tool_sets"]["read_support"])
        self.assertIn("memory_find_references", payload["tool_sets"]["read_support"])
        self.assertIn("memory_scan_frontmatter_health", payload["tool_sets"]["read_support"])
        self.assertIn("memory_validate_links", payload["tool_sets"]["read_support"])
        self.assertIn("memory_suggest_links", payload["tool_sets"]["read_support"])
        self.assertIn("memory_cross_domain_links", payload["tool_sets"]["read_support"])
        self.assertIn("memory_link_delta", payload["tool_sets"]["read_support"])
        self.assertIn("memory_reorganize_preview", payload["tool_sets"]["read_support"])
        self.assertIn("memory_suggest_structure", payload["tool_sets"]["read_support"])
        self.assertIn("memory_reorganize_path", payload["tool_sets"]["semantic_extensions"])
        self.assertIn("memory_update_names_index", payload["tool_sets"]["semantic_extensions"])
        self.assertIn("memory_extract_file", payload["tool_sets"]["read_support"])
        self.assertIn("memory_generate_names_index", payload["tool_sets"]["read_support"])
        self.assertEqual(payload["summary"]["contract_versions"]["mcp"], 1)
        self.assertGreaterEqual(payload["summary"]["total_tools"], 1)
        self.assertGreaterEqual(payload["summary"]["tool_profile_count"], 1)
        self.assertIn("full", payload["summary"]["tool_profiles"])
        self.assertEqual(payload["summary"]["default_tool_profile"], "guided_write")
        self.assertFalse(payload["summary"]["dynamic_profile_switching"])
        self.assertFalse(payload["summary"]["list_changed_supported"])
        self.assertGreaterEqual(payload["summary"]["resource_count"], 4)
        self.assertGreaterEqual(payload["summary"]["prompt_count"], 4)

    def test_get_capabilities_summary_reports_registered_tool_count(self) -> None:
        async def run_call() -> tuple[dict[str, Any], int]:
            raw = await self.module.memory_get_capabilities()
            payload = cast(dict[str, Any], json.loads(raw))
            listed = await self.module.mcp.list_tools()
            return payload, len(listed)

        payload, registered_count = asyncio.run(run_call())
        self.assertEqual(payload["summary"]["total_tools"], registered_count)
        self.assertEqual(payload["summary"]["runtime_total_tools"], registered_count)

    def test_get_tool_profiles_returns_expanded_advisory_profiles(self) -> None:
        raw = asyncio.run(self.module.memory_get_tool_profiles())
        payload = json.loads(raw)

        self.assertEqual(payload["default_profile"], "guided_write")
        self.assertFalse(payload["dynamic_runtime_switching"])
        self.assertFalse(payload["list_changed_supported"])
        self.assertIn("full", payload["profiles"])
        self.assertIn("guided_write", payload["profiles"])
        self.assertIn("read_only", payload["profiles"])
        self.assertIn("memory_get_capabilities", payload["profiles"]["read_only"]["tools"])
        self.assertNotIn("memory_write", payload["profiles"]["guided_write"]["tools"])
        self.assertIn("memory_write", payload["profiles"]["full"]["tools"])

    def test_mcp_registration_includes_approval_and_registry_tools(self) -> None:
        async def run_call() -> set[str]:
            listed = await self.module.mcp.list_tools()
            return {str(tool.name) for tool in listed}

        names = asyncio.run(run_call())
        for tool_name in (
            "memory_request_approval",
            "memory_resolve_approval",
            "memory_register_tool",
            "memory_get_tool_policy",
        ):
            self.assertIn(tool_name, names)

    def test_memory_validate_finds_validator_from_content_prefix_root(self) -> None:
        output = asyncio.run(self.module.memory_validate())
        self.assertNotEqual(
            output, "Validator not found at HUMANS/tooling/scripts/validate_memory_repo.py"
        )

    def test_readme_profile_contract_matches_advisory_runtime(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("advisory host-side narrowing metadata", readme)
        self.assertNotIn("`MEMORY_TOOL_PROFILE`", readme)

    def test_read_file_works_over_stdio_transport(self) -> None:
        if not VENV_PYTHON.exists():
            raise unittest.SkipTest(f"venv interpreter not found: {VENV_PYTHON}")

        server = StdioServerParameters(
            command=str(VENV_PYTHON),
            args=[str(SCRIPT_PATH)],
            cwd=str(REPO_ROOT),
            env={"MEMORY_REPO_ROOT": str(REPO_ROOT)},
        )

        async def run_call() -> dict[str, object]:
            async with stdio_client(server) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "memory_read_file",
                        {"path": "INIT.md"},
                    )
                    text_block = cast(Any, result.content[0])
                    return cast(dict[str, object], json.loads(text_block.text))

        payload = anyio.run(run_call)

        self.assertTrue(cast(bool, payload["inline"]))
        self.assertIn("# Session Init", cast(str, payload["content"]))
        self.assertIn("version_token", payload)

    def test_native_resources_enumerate_and_read(self) -> None:
        async def run_call() -> tuple[list[tuple[str, str]], list[Any], dict[str, Any]]:
            resources = await self.module.mcp.list_resources()
            resource_pairs = [(str(resource.name), str(resource.uri)) for resource in resources]
            capability_summary = await self.module.mcp.read_resource(
                "memory://capabilities/summary"
            )
            capability_payload = json.loads(cast(str, capability_summary[0].content))
            return resource_pairs, capability_summary, capability_payload

        resource_pairs, capability_summary, capability_payload = asyncio.run(run_call())

        self.assertIn(
            ("memory_capability_summary", "memory://capabilities/summary"), resource_pairs
        )
        self.assertIn(("memory_policy_summary", "memory://policy/summary"), resource_pairs)
        self.assertIn(("memory_session_health_resource", "memory://session/health"), resource_pairs)
        self.assertIn(("memory_active_plans_resource", "memory://plans/active"), resource_pairs)
        self.assertEqual(len(capability_summary), 1)
        self.assertIn("summary", capability_payload)
        self.assertIn("tool_profiles", capability_payload)
        self.assertIn("full", capability_payload["tool_profiles"]["profiles"])

    def test_native_prompts_enumerate_and_render(self) -> None:
        async def run_call() -> tuple[list[str], Any, Any]:
            prompts = await self.module.mcp.list_prompts()
            prompt_names = [str(prompt.name) for prompt in prompts]
            review_prompt = await self.module.mcp.get_prompt(
                "memory_prepare_unverified_review_prompt",
                {
                    "folder_path": "memory/knowledge/_unverified",
                    "max_files": 2,
                    "max_extract_words": 20,
                },
            )
            wrap_up_prompt = await self.module.mcp.get_prompt(
                "memory_session_wrap_up_prompt",
                {"session_id": "session-123", "key_topics": "routing,preview"},
            )
            return prompt_names, review_prompt, wrap_up_prompt

        prompt_names, review_prompt, wrap_up_prompt = asyncio.run(run_call())

        self.assertIn("memory_prepare_unverified_review_prompt", prompt_names)
        self.assertIn("memory_governed_promotion_preview_prompt", prompt_names)
        self.assertIn("memory_prepare_periodic_review_prompt", prompt_names)
        self.assertIn("memory_session_wrap_up_prompt", prompt_names)
        self.assertEqual(len(review_prompt.messages), 1)
        self.assertIn("Review Bundle", cast(str, review_prompt.messages[0].content.text))
        self.assertIn("memory_promote_knowledge", cast(str, review_prompt.messages[0].content.text))
        self.assertEqual(len(wrap_up_prompt.messages), 1)
        self.assertIn("Session Wrap-Up Context", cast(str, wrap_up_prompt.messages[0].content.text))
        self.assertIn("memory_record_session", cast(str, wrap_up_prompt.messages[0].content.text))

    def test_new_tools_are_exported(self) -> None:
        for name in (
            "memory_context_home",
            "memory_context_project",
            "memory_git_log",
            "memory_get_capabilities",
            "memory_get_tool_profiles",
            "memory_check_cross_references",
            "memory_resolve_link",
            "memory_find_references",
            "memory_scan_frontmatter_health",
            "memory_validate_links",
            "memory_suggest_links",
            "memory_cross_domain_links",
            "memory_link_delta",
            "memory_reorganize_preview",
            "memory_suggest_structure",
            "memory_reorganize_path",
            "memory_generate_summary",
            "memory_generate_names_index",
            "memory_update_names_index",
            "memory_access_analytics",
            "memory_diff_branch",
            "memory_check_knowledge_freshness",
            "memory_check_aggregation_triggers",
            "memory_aggregate_access",
            "memory_run_periodic_review",
            "memory_get_file_provenance",
            "memory_extract_file",
            "memory_inspect_commit",
            "memory_record_periodic_review",
            "memory_plan_execute",
            "memory_plan_create",
            "memory_plan_review",
            "memory_request_approval",
            "memory_resolve_approval",
            "memory_register_tool",
            "memory_get_tool_policy",
        ):
            self.assertTrue(callable(getattr(self.module, name)))
        self.assertFalse(hasattr(self.module, "memory_write"))
        self.assertFalse(hasattr(self.module, "memory_commit"))


if __name__ == "__main__":
    unittest.main()
