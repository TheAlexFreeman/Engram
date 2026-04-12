from __future__ import annotations

import asyncio
import importlib.util
import json
import os
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

    def _load_tool_payload(self, raw: str) -> Any:
        payload = cast(dict[str, Any], json.loads(raw))
        if "_session" in payload and "result" in payload:
            return payload["result"]
        return payload

    def _load_resource_payload(self, resource_blocks: list[Any]) -> dict[str, Any]:
        self.assertEqual(len(resource_blocks), 1)
        return cast(dict[str, Any], json.loads(cast(str, resource_blocks[0].content)))

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
        payload = json.loads(raw)
        output = payload["result"]

        self.assertIn("_session", payload)
        self.assertTrue(output["inline"])
        self.assertIn("Human-Focused Documentation", output["content"])
        self.assertIn("version_token", output)

    def test_read_file_returns_structured_payload(self) -> None:
        raw = asyncio.run(self.module.memory_read_file(path="INIT.md"))
        envelope = json.loads(raw)
        payload = envelope["result"]

        self.assertIn("_session", envelope)
        self.assertEqual(payload["path"], "INIT.md")
        self.assertTrue(payload["inline"])
        self.assertGreater(payload["size_bytes"], 0)
        self.assertIn("version_token", payload)
        self.assertIsNone(payload["frontmatter"])
        self.assertIn("# Session Init", payload["content"])
        self.assertNotIn("temp_file", payload)

    def test_get_capabilities_returns_structured_payload(self) -> None:
        raw = asyncio.run(self.module.memory_get_capabilities())
        envelope = json.loads(raw)
        payload = envelope["result"]

        self.assertIn("_session", envelope)
        self.assertEqual(payload["kind"], "agent-memory-capabilities")
        self.assertEqual(payload["contract_versions"]["capabilities"], 1)
        self.assertEqual(payload["contract_versions"]["resources"], 1)
        self.assertEqual(payload["contract_versions"]["prompts"], 1)
        self.assertEqual(payload["contract_versions"]["provenance"], 1)
        self.assertEqual(payload["contract_versions"]["structured_read"], 1)
        self.assertIn("memory_get_capabilities", payload["tool_sets"]["read_support"])
        self.assertIn("memory_tool_schema", payload["tool_sets"]["read_support"])
        self.assertIn("memory_plan_schema", payload["tool_sets"]["read_support"])
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
        self.assertIn("memory_skill_install", payload["tool_sets"]["semantic_extensions"])
        self.assertIn("memory_skill_route", payload["tool_sets"]["semantic_extensions"])
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
            payload = self._load_tool_payload(raw)
            listed = await self.module.mcp.list_tools()
            return payload, len(listed)

        payload, registered_count = asyncio.run(run_call())
        self.assertEqual(payload["summary"]["total_tools"], registered_count)
        self.assertEqual(payload["summary"]["runtime_total_tools"], registered_count)
        self.assertEqual(payload["summary"]["runtime_not_in_manifest_count"], 0)
        self.assertEqual(payload["summary"]["runtime_not_in_manifest"], [])
        raw_enabled = os.environ.get("MEMORY_ENABLE_RAW_WRITE_TOOLS", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        declared_missing = list(payload["summary"]["declared_not_in_runtime"])
        if not raw_enabled:
            raw_fb = {
                t
                for t in cast(list[Any], payload.get("tool_sets", {}).get("raw_fallback", []))
                if isinstance(t, str)
            }
            declared_missing = [t for t in declared_missing if t not in raw_fb]
        self.assertEqual(
            declared_missing,
            [],
            msg="Manifest lists tools with no MCP registration (excluding raw_fallback when Tier 2 is disabled).",
        )

    def test_get_tool_profiles_returns_expanded_advisory_profiles(self) -> None:
        raw = asyncio.run(self.module.memory_get_tool_profiles())
        envelope = json.loads(raw)
        payload = envelope["result"]

        self.assertIn("_session", envelope)
        self.assertEqual(payload["default_profile"], "guided_write")
        self.assertFalse(payload["dynamic_runtime_switching"])
        self.assertFalse(payload["list_changed_supported"])
        self.assertIn("full", payload["profiles"])
        self.assertIn("guided_write", payload["profiles"])
        self.assertIn("read_only", payload["profiles"])
        self.assertIn("memory_get_capabilities", payload["profiles"]["read_only"]["tools"])
        self.assertNotIn("memory_reset_session_state", payload["profiles"]["read_only"]["tools"])
        self.assertNotIn("memory_session_flush", payload["profiles"]["read_only"]["tools"])
        self.assertIn("memory_reset_session_state", payload["profiles"]["guided_write"]["tools"])
        self.assertIn("memory_session_flush", payload["profiles"]["guided_write"]["tools"])
        self.assertNotIn("memory_write", payload["profiles"]["guided_write"]["tools"])
        self.assertIn("memory_write", payload["profiles"]["full"]["tools"])
        self.assertIn("memory_reset_session_state", payload["profiles"]["full"]["tools"])
        self.assertIn("memory_session_flush", payload["profiles"]["full"]["tools"])

    def test_plan_schema_returns_structured_payload(self) -> None:
        raw = asyncio.run(self.module.memory_plan_schema())
        envelope = json.loads(raw)
        payload = envelope["result"]

        self.assertIn("_session", envelope)
        self.assertEqual(payload["tool_name"], "memory_plan_create")
        self.assertIn("phases", payload["properties"])
        self.assertEqual(
            payload["properties"]["phases"]["items"]["properties"]["postconditions"]["items"][
                "oneOf"
            ][1]["properties"]["type"]["x-aliases"]["file_check"],
            "check",
        )

    def test_tool_schema_returns_structured_payload(self) -> None:
        raw = asyncio.run(self.module.memory_tool_schema(tool_name="memory_log_access_batch"))
        envelope = json.loads(raw)
        payload = envelope["result"]

        self.assertIn("_session", envelope)
        self.assertEqual(payload["tool_name"], "memory_log_access_batch")
        self.assertIn("access_entries", payload["properties"])
        self.assertEqual(
            payload["properties"]["access_entries"]["items"]["properties"]["mode"]["enum"],
            ["create", "read", "update", "write"],
        )

    def test_tool_schema_registry_includes_read_and_context_tools(self) -> None:
        read_payload = self._load_tool_payload(
            asyncio.run(self.module.memory_tool_schema(tool_name="memory_read_file"))
        )
        self.assertEqual(read_payload["tool_name"], "memory_read_file")
        self.assertIn("path", read_payload["properties"])

        search_payload = self._load_tool_payload(
            asyncio.run(self.module.memory_tool_schema(tool_name="memory_search"))
        )
        self.assertEqual(search_payload["tool_name"], "memory_search")
        self.assertIn("freshness_weight", search_payload["properties"])

        home_payload = self._load_tool_payload(
            asyncio.run(self.module.memory_tool_schema(tool_name="memory_context_home"))
        )
        self.assertEqual(home_payload["tool_name"], "memory_context_home")
        self.assertIn("max_context_chars", home_payload["properties"])

    def test_tool_schema_types_plan_execute_and_approval_inputs(self) -> None:
        execute_raw = asyncio.run(self.module.memory_tool_schema(tool_name="memory_plan_execute"))
        execute_payload = self._load_tool_payload(execute_raw)
        verification_item = execute_payload["properties"]["verification_results"]["oneOf"][0][
            "items"
        ]["anyOf"][0]

        self.assertEqual(execute_payload["tool_name"], "memory_plan_execute")
        self.assertEqual(
            verification_item["properties"]["status"]["enum"],
            ["error", "fail", "pass", "skip"],
        )
        self.assertIn("policy_result", verification_item["properties"])

        approval_raw = asyncio.run(
            self.module.memory_tool_schema(tool_name="memory_request_approval")
        )
        approval_payload = self._load_tool_payload(approval_raw)

        self.assertEqual(approval_payload["tool_name"], "memory_request_approval")
        self.assertEqual(approval_payload["properties"]["expires_days"]["minimum"], 1)

    def test_read_only_profile_contains_only_runtime_read_only_tools(self) -> None:
        async def run_call() -> tuple[dict[str, Any], dict[str, object | None]]:
            raw = await self.module.memory_get_tool_profiles()
            payload = self._load_tool_payload(raw)
            listed = await self.module.mcp.list_tools()
            hints = {
                str(tool.name): getattr(getattr(tool, "annotations", None), "readOnlyHint", None)
                for tool in listed
            }
            return payload, hints

        payload, hints = asyncio.run(run_call())
        unsafe = sorted(
            name for name in payload["profiles"]["read_only"]["tools"] if hints.get(name) is False
        )

        self.assertEqual(unsafe, [])

    def test_policy_state_covers_session_maintenance_tools(self) -> None:
        async def run_call() -> tuple[dict[str, Any], dict[str, Any]]:
            flush = cast(
                dict[str, Any],
                self._load_tool_payload(
                    await self.module.memory_get_policy_state(operation="memory_session_flush")
                ),
            )
            reset = cast(
                dict[str, Any],
                self._load_tool_payload(
                    await self.module.memory_get_policy_state(
                        operation="memory_reset_session_state"
                    )
                ),
            )
            return flush, reset

        flush, reset = asyncio.run(run_call())

        for payload, tool_name in (
            (flush, "memory_session_flush"),
            (reset, "memory_reset_session_state"),
        ):
            self.assertEqual(payload["operation"], tool_name)
            self.assertEqual(payload["tool"], tool_name)
            self.assertEqual(payload["tier"], "semantic")
            self.assertEqual(payload["change_class"], "automatic")
            self.assertEqual(payload["warnings"], [])

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
                    return cast(dict[str, object], self._load_tool_payload(text_block.text))

        payload = anyio.run(run_call)

        self.assertTrue(cast(bool, payload["inline"]))
        self.assertIn("# Session Init", cast(str, payload["content"]))
        self.assertIn("version_token", payload)

    def test_native_resources_enumerate_and_read(self) -> None:
        async def run_call() -> tuple[
            list[tuple[str, str]], list[Any], list[Any], list[Any], list[Any]
        ]:
            resources = await self.module.mcp.list_resources()
            resource_pairs = [(str(resource.name), str(resource.uri)) for resource in resources]
            capability_summary = await self.module.mcp.read_resource(
                "memory://capabilities/summary"
            )
            policy_summary = await self.module.mcp.read_resource("memory://policy/summary")
            session_health = await self.module.mcp.read_resource("memory://session/health")
            active_plans = await self.module.mcp.read_resource("memory://plans/active")
            return resource_pairs, capability_summary, policy_summary, session_health, active_plans

        (
            resource_pairs,
            capability_summary,
            policy_summary,
            session_health,
            active_plans,
        ) = asyncio.run(run_call())

        capability_payload = self._load_resource_payload(capability_summary)
        policy_payload = self._load_resource_payload(policy_summary)
        session_payload = self._load_resource_payload(session_health)
        active_payload = self._load_resource_payload(active_plans)

        self.assertIn(
            ("memory_capability_summary", "memory://capabilities/summary"), resource_pairs
        )
        self.assertIn(("memory_policy_summary", "memory://policy/summary"), resource_pairs)
        self.assertIn(("memory_session_health_resource", "memory://session/health"), resource_pairs)
        self.assertIn(("memory_active_plans_resource", "memory://plans/active"), resource_pairs)
        self.assertIn("summary", capability_payload)
        self.assertIn("tool_profiles", capability_payload)
        self.assertIn("full", capability_payload["tool_profiles"]["profiles"])
        self.assertIn("change_classes", policy_payload)
        self.assertIn("resources_vs_tools", policy_payload)
        self.assertIn("tool_profiles", policy_payload)
        self.assertIn("aggregation_due", session_payload)
        self.assertIn("review_queue_pending", session_payload)
        self.assertIn("periodic_review_due", session_payload)
        self.assertIn("generated_at", active_payload)
        self.assertIn("active_plan_count", active_payload)
        self.assertIn("plans", active_payload)

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
