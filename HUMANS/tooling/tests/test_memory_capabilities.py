from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from importlib import import_module
from pathlib import Path
from unittest import mock

try:
    tomllib = import_module("tomllib")
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = import_module("tomli")


REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "HUMANS" / "tooling" / "agent-memory-capabilities.toml"
RESOLVER_PATH = REPO_ROOT / "HUMANS" / "tooling" / "scripts" / "resolve_memory_capabilities.py"
HIGH_LEVEL_MCP_DOCS = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "HUMANS" / "docs" / "CORE.md",
    REPO_ROOT / "HUMANS" / "docs" / "DESIGN.md",
)
HIGH_LEVEL_MCP_COUNT_PATTERNS = (
    re.compile(r"\b\d+\s+(?:governed\s+)?(?:MCP\s+)?tools\b", re.IGNORECASE),
    re.compile(r"Tier\s+[012][^\n]*\(\d+\s+(?:read-only|semantic|write)", re.IGNORECASE),
)

SPEC = importlib.util.spec_from_file_location("resolve_memory_capabilities", RESOLVER_PATH)
assert SPEC is not None
resolver = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = resolver
SPEC.loader.exec_module(resolver)


class MemoryCapabilitiesTests(unittest.TestCase):
    def test_current_seed_manifest_resolves_against_runtime(self) -> None:
        resolution = resolver.resolve_capabilities(REPO_ROOT)
        self.assertEqual(resolution["errors"], [], "\n".join(resolution["errors"]))

    def test_default_runtime_matches_declared_default_surface(self) -> None:
        resolution = resolver.resolve_capabilities(REPO_ROOT)
        declared_default_surface = set(resolution["tool_sets"]["read_support"]) | set(
            resolution["tool_sets"]["semantic_extensions"]
        )
        discovery = resolution["capability_discovery"]

        self.assertEqual(set(resolution["runtime_tools"]), declared_default_surface)
        self.assertEqual(discovery["undeclared_runtime_tools"], [])
        self.assertEqual(discovery["public_mutating_tools_without_contract"], [])
        self.assertEqual(discovery["unsafe_read_only_profile_tools"], [])

    def test_manifest_declares_expected_desktop_gaps(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        declared_gaps = manifest["tool_sets"]["declared_gaps"]

        self.assertEqual(declared_gaps, [])
        self.assertEqual(
            manifest["desktop_operations"]["append_access_entry"]["status"],
            "implemented",
        )
        self.assertEqual(
            manifest["desktop_operations"]["record_session_reflection"]["status"],
            "implemented",
        )
        self.assertEqual(
            manifest["desktop_operations"]["append_access_entry"]["change_class"],
            "automatic",
        )

    def test_semantic_operations_own_required_contract_fields(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        raw_fallback = set(manifest["tool_sets"]["raw_fallback"])
        change_classes = set(manifest["change_classes"])
        allowed_commit_models = {"auto_commit", "auto_commit_exception_direct_write", "none"}
        staged_semantic_operations = {"memory_checkpoint"}

        for tool_name in manifest["tool_sets"]["semantic_extensions"]:
            operation = manifest["operations"][tool_name]
            self.assertEqual(operation["tier"], "semantic")
            self.assertIn(operation["change_class"], change_classes)
            self.assertIsInstance(operation["writes"], list)
            self.assertIsInstance(operation["commit_model"], str)
            if operation["writes"]:
                self.assertIn(operation["commit_model"], allowed_commit_models)
                if operation["commit_model"] == "none":
                    self.assertIn(tool_name, staged_semantic_operations)
            else:
                self.assertEqual(operation["commit_model"], "none")
            self.assertIsInstance(operation["owns_frontmatter"], list)
            self.assertIsInstance(operation["owns_summaries"], list)
            self.assertIsInstance(operation["owns_access_logs"], list)
            self.assertIsInstance(operation["owns_review_queue"], list)
            self.assertIsInstance(operation["result_fields"], list)
            self.assertTrue(set(operation["fallback_tools"]).issubset(raw_fallback))

    def test_high_level_docs_defer_exact_tool_counts_to_mcp_reference(self) -> None:
        for path in HIGH_LEVEL_MCP_DOCS:
            text = path.read_text(encoding="utf-8")
            self.assertIn("MCP.md", text, f"{path} should point readers to MCP.md")
            for pattern in HIGH_LEVEL_MCP_COUNT_PATTERNS:
                self.assertIsNone(
                    pattern.search(text),
                    f"{path} should not hardcode MCP tool counts; defer live inventory details to MCP.md",
                )

    def test_mcp_docs_tool_counts_match_manifest(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        mcp_docs = (REPO_ROOT / "HUMANS" / "docs" / "MCP.md").read_text(encoding="utf-8")
        read_count = len(manifest["tool_sets"]["read_support"])
        semantic_count = len(manifest["tool_sets"]["semantic_extensions"])
        raw_count = len(manifest["tool_sets"]["raw_fallback"])
        default_total = read_count + semantic_count
        full_total = default_total + raw_count
        expected = (
            f"The MCP server exposes **{default_total} tools by default**: "
            f"{read_count} Tier 0 read-only tools plus {semantic_count} Tier 1 semantic tools. "
            f"Enabling `MEMORY_ENABLE_RAW_WRITE_TOOLS=1` adds **{raw_count} Tier 2** raw fallback "
            f"tools for a full surface of **{full_total}**."
        )

        self.assertIn(expected, mcp_docs)

    def test_manifest_declares_change_classes_and_raw_fallback_policy(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        change_classes = manifest["change_classes"]
        raw_fallback_policy = manifest["raw_fallback_policy"]

        self.assertEqual(
            sorted(change_classes),
            ["automatic", "proposed", "protected"],
        )
        self.assertEqual(
            change_classes["automatic"]["read_only_behavior"],
            "defer_and_emit_summary",
        )
        self.assertEqual(raw_fallback_policy["policy"], "inherit_operation_change_class")
        self.assertEqual(raw_fallback_policy["runtime_export"], "opt_in")
        self.assertEqual(
            raw_fallback_policy["opt_in_env_var"],
            "MEMORY_ENABLE_RAW_WRITE_TOOLS",
        )
        self.assertTrue(raw_fallback_policy["requires_change_class"])
        self.assertEqual(
            raw_fallback_policy["preview_required_for"],
            ["proposed", "protected"],
        )

    def test_default_runtime_reports_raw_fallback_as_unavailable(self) -> None:
        resolution = resolver.resolve_capabilities(REPO_ROOT)

        self.assertEqual(resolution["errors"], [], "\n".join(resolution["errors"]))
        runtime = resolution["capability_discovery"]
        self.assertEqual(runtime["mode"], "semantic")
        self.assertFalse(runtime["raw_fallback_available"])
        self.assertEqual(runtime["available_raw_tools"], [])
        self.assertEqual(
            runtime["unavailable_opt_in_raw_tools"],
            [
                "memory_commit",
                "memory_delete",
                "memory_edit",
                "memory_move",
                "memory_update_frontmatter",
                "memory_update_frontmatter_bulk",
                "memory_write",
            ],
        )

    def test_manifest_declares_hybrid_integration_boundary(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        boundary = manifest["integration_boundary"]

        self.assertEqual(boundary["model"], "hybrid")
        self.assertEqual(boundary["prefer"], "repo_local_semantic_mcp")
        self.assertEqual(boundary["native_semantic_scope"], "generic_only")
        self.assertTrue(boundary["manifest_required_for_repo_specific_semantics"])
        self.assertEqual(
            boundary["degradation_order"],
            [
                "repo_local_semantic_mcp",
                "codex_native_preview_and_policy",
                "raw_fallback_or_defer",
            ],
        )
        self.assertTrue(
            {
                "approval_ux",
                "change_class_enforcement",
                "capability_discovery",
                "preview_rendering",
                "result_presentation",
                "fallback_selection",
            }.issubset(boundary["desktop_owns"])
        )
        self.assertTrue(
            {
                "semantic_execution",
                "repo_specific_invariants",
                "schema_validation",
                "authoritative_mutation",
                "structured_result_state",
            }.issubset(boundary["repo_local_mcp_owns"])
        )
        self.assertEqual(
            boundary["native_fallback_owns"],
            [
                "generic_preview",
                "raw_tool_orchestration",
                "deferred_action_summary",
            ],
        )

    def test_manifest_declares_capability_discovery_contract(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        discovery = manifest["capability_discovery"]

        self.assertEqual(
            discovery["well_known_paths"],
            ["HUMANS/tooling/agent-memory-capabilities.toml"],
        )
        self.assertEqual(discovery["requires_kind"], "agent-memory-capabilities")
        self.assertEqual(discovery["supported_versions"], [1])
        self.assertTrue(discovery["requires_mcp_entrypoint"])
        self.assertEqual(
            discovery["minimum_read_tools"],
            [
                "memory_read_file",
                "memory_list_folder",
                "memory_search",
                "memory_validate",
            ],
        )
        self.assertEqual(
            discovery["minimum_semantic_tools"],
            [
                "memory_plan_create",
                "memory_plan_execute",
                "memory_add_knowledge_file",
            ],
        )
        self.assertTrue(discovery["read_only_runtime_allowed"])
        self.assertEqual(
            discovery["semantic_detection"],
            "manifest_and_minimum_semantic_tools",
        )
        self.assertEqual(
            discovery["read_only_detection"],
            "minimum_read_tools_without_write_tools",
        )
        self.assertEqual(discovery["semantic_result"], "repo_local_semantic_mcp")
        self.assertEqual(
            discovery["read_only_result"],
            "codex_native_preview_and_policy",
        )
        self.assertEqual(
            discovery["incompatible_result"],
            "raw_fallback_or_defer",
        )

    def test_manifest_declares_memory_get_capabilities_in_read_support(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertIn("memory_get_capabilities", manifest["tool_sets"]["read_support"])
        self.assertIn("memory_plan_schema", manifest["tool_sets"]["read_support"])
        self.assertIn("memory_check_cross_references", manifest["tool_sets"]["read_support"])
        self.assertIn("memory_generate_summary", manifest["tool_sets"]["read_support"])
        self.assertIn("memory_access_analytics", manifest["tool_sets"]["read_support"])
        self.assertIn("memory_diff_branch", manifest["tool_sets"]["read_support"])
        self.assertEqual(
            manifest["contract_versions"],
            {
                "frontmatter": 1,
                "access": 1,
                "mcp": 1,
                "capabilities": 1,
                "preview": 1,
                "resources": 1,
                "prompts": 1,
                "provenance": 1,
                "structured_read": 1,
            },
        )

    def test_manifest_declares_ui_feedback_contract(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        ui_feedback = manifest["ui_feedback"]

        self.assertEqual(ui_feedback["panel_title"], "Governed Memory Writes")
        self.assertEqual(
            ui_feedback["manifest_action_label"],
            "Open Capability Manifest",
        )
        self.assertEqual(
            ui_feedback["status_labels"],
            {
                "semantic": "Repo-local semantic MCP ready",
                "read_only": "Read-only governed preview",
                "fallback": "Fallback or defer",
                "manifest_only": "Manifest loaded",
            },
        )
        self.assertEqual(
            ui_feedback["preview_section_labels"]["target_files"],
            "Changed Files",
        )
        self.assertEqual(
            ui_feedback["result_field_labels"]["next_action"],
            "Next Action",
        )
        self.assertEqual(
            ui_feedback["result_field_labels"]["plan_progress"],
            "Plan Progress",
        )

    def test_manifest_declares_fallback_behavior_profiles_for_raw_and_deferred_paths(
        self,
    ) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        fallback_behavior = manifest["fallback_behavior"]
        desktop_operations = manifest["desktop_operations"]

        self.assertEqual(
            sorted(fallback_behavior),
            ["preview_only", "read_only", "semantic_gap", "uninterpretable_target"],
        )
        self.assertTrue(fallback_behavior["semantic_gap"]["raw_tools_allowed"])
        self.assertTrue(fallback_behavior["semantic_gap"]["requires_contract_preservation"])
        self.assertFalse(fallback_behavior["uninterpretable_target"]["raw_tools_allowed"])
        self.assertEqual(
            fallback_behavior["preview_only"]["result"],
            "return_preview_without_writing",
        )
        self.assertEqual(
            fallback_behavior["read_only"]["result"],
            "return_deferred_action_summary",
        )
        self.assertEqual(
            desktop_operations["append_access_entry"]["tool"],
            "memory_log_access",
        )
        self.assertEqual(
            desktop_operations["record_session_reflection"]["tool"],
            "memory_record_reflection",
        )

    def test_manifest_declares_approval_preview_and_confirmation_flows(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        approval_ux = manifest["approval_ux"]

        self.assertEqual(
            approval_ux["preview"]["required_for"],
            ["proposed", "protected"],
        )
        self.assertEqual(
            approval_ux["preview"]["sections"],
            [
                "summary",
                "reasoning",
                "target_files",
                "invariant_effects",
                "commit_suggestion",
                "fallback_behavior",
            ],
        )
        self.assertTrue(approval_ux["preview"]["show_resulting_state"])
        self.assertTrue(approval_ux["preview"]["show_warnings"])
        self.assertEqual(approval_ux["proposed"]["trigger"], "before_write")
        self.assertEqual(
            approval_ux["proposed"]["primary_action"],
            "apply_after_confirmation",
        )
        self.assertEqual(
            approval_ux["protected"]["primary_action"],
            "approve_and_apply",
        )
        self.assertEqual(
            approval_ux["protected"]["secondary_actions"],
            ["open_files", "defer", "cancel"],
        )

    def test_desktop_operation_change_classes_match_semantic_tools(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        desktop_operations = manifest["desktop_operations"]
        operations = manifest["operations"]

        self.assertEqual(
            operations["memory_plan_create"]["change_class"],
            "proposed",
        )
        self.assertEqual(
            operations["memory_plan_execute"]["change_class"],
            "proposed",
        )
        self.assertEqual(
            operations["memory_update_user_trait"]["change_class"],
            "proposed",
        )
        self.assertEqual(
            operations["memory_flag_for_review"]["change_class"],
            "automatic",
        )
        self.assertEqual(
            operations["memory_record_periodic_review"]["change_class"],
            "protected",
        )
        self.assertEqual(
            desktop_operations["create_plan"]["change_class"],
            operations["memory_plan_create"]["change_class"],
        )
        self.assertEqual(
            desktop_operations["flag_for_review"]["change_class"],
            operations["memory_flag_for_review"]["change_class"],
        )
        self.assertEqual(
            desktop_operations["record_periodic_review"]["change_class"],
            operations["memory_record_periodic_review"]["change_class"],
        )

    def test_semantic_operations_declare_commit_category_hints(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        operations = manifest["operations"]

        self.assertEqual(
            operations["memory_plan_create"]["commit_category_hint"],
            "plan",
        )
        self.assertEqual(
            operations["memory_add_knowledge_file"]["commit_category_hint"],
            "knowledge",
        )
        self.assertEqual(
            operations["memory_update_user_trait"]["commit_category_hint"],
            "identity",
        )
        self.assertEqual(
            operations["memory_record_chat_summary"]["commit_category_hint"],
            "chat",
        )
        self.assertEqual(
            operations["memory_log_access_batch"]["commit_category_hint"],
            "chat",
        )
        self.assertEqual(
            operations["memory_flag_for_review"]["commit_category_hint"],
            "curation",
        )
        self.assertEqual(
            operations["memory_record_periodic_review"]["commit_category_hint"],
            "system",
        )

    def test_error_taxonomy_marks_already_done_as_declared_but_not_emitted(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        errors = manifest["error_taxonomy"]

        self.assertEqual(errors["ConflictError"]["status"], "implemented")
        self.assertEqual(errors["ValidationError"]["status"], "implemented")
        self.assertEqual(errors["AlreadyDoneError"]["status"], "defined_not_currently_emitted")

    def test_resolver_returns_integration_boundary(self) -> None:
        resolution = resolver.resolve_capabilities(REPO_ROOT, include_runtime=False)
        boundary = resolution["integration_boundary"]

        self.assertEqual(boundary["model"], "hybrid")
        self.assertEqual(boundary["prefer"], "repo_local_semantic_mcp")
        self.assertEqual(
            boundary["degradation_order"],
            [
                "repo_local_semantic_mcp",
                "codex_native_preview_and_policy",
                "raw_fallback_or_defer",
            ],
        )

    def test_resolver_reports_semantic_discovery_for_current_runtime(self) -> None:
        resolution = resolver.resolve_capabilities(REPO_ROOT)
        discovery = resolution["capability_discovery"]

        self.assertTrue(discovery["contract_compatible"])
        self.assertTrue(discovery["entrypoint_exists"])
        self.assertEqual(discovery["mode"], "semantic")
        self.assertEqual(discovery["selected_strategy"], "repo_local_semantic_mcp")
        self.assertEqual(discovery["missing_minimum_read_tools"], [])
        self.assertEqual(discovery["missing_minimum_semantic_tools"], [])

    def test_manifest_declares_batch_access_logging_operation(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertIn("memory_log_access_batch", manifest["tool_sets"]["semantic_extensions"])
        self.assertEqual(
            manifest["operations"]["memory_log_access_batch"]["result_fields"],
            ["access_jsonls", "entry_count", "scan_entry_count"],
        )

    def test_manifest_declares_batch_knowledge_promotion_operation(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertIn(
            "memory_promote_knowledge_batch",
            manifest["tool_sets"]["semantic_extensions"],
        )
        self.assertEqual(
            manifest["operations"]["memory_promote_knowledge_batch"]["result_fields"],
            [
                "promoted_count",
                "target_folder",
                "trust",
                "promoted_files",
                "summary_updates",
            ],
        )
        self.assertEqual(
            manifest["desktop_operations"]["promote_knowledge_batch"]["tool"],
            "memory_promote_knowledge_batch",
        )

    def test_manifest_declares_access_scan_result_fields_and_notes(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            manifest["ui_feedback"]["result_field_labels"]["scan_entry_count"],
            "Scan Entry Count",
        )
        self.assertIn(
            "ACCESS_SCANS.jsonl",
            manifest["operations"]["memory_log_access"]["notes"],
        )
        self.assertIn(
            "min_helpfulness",
            manifest["operations"]["memory_log_access_batch"]["notes"],
        )

    def test_manifest_declares_access_logging_task_id_vocabulary(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            manifest["access_logging"]["task_ids"],
            ["plan-review", "research-write", "validation", "health-check"],
        )
        self.assertEqual(
            manifest["ui_feedback"]["result_field_labels"]["access_density_by_task_id"],
            "Access Density by Task ID",
        )

    def test_manifest_declares_hot_log_aggregation_result_fields(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            manifest["ui_feedback"]["result_field_labels"]["hot_access_targets"],
            "Hot ACCESS Targets",
        )
        self.assertEqual(
            manifest["operations"]["memory_run_aggregation"]["result_fields"],
            [
                "entries_processed",
                "session_groups_processed",
                "legacy_fallback_entries",
                "summary_update_targets",
                "summary_materialization_targets",
                "hot_access_targets",
                "hot_access_reset_targets",
                "archive_targets",
            ],
        )
        self.assertIn(
            "materialized summary views",
            manifest["operations"]["memory_run_aggregation"]["notes"],
        )

    def test_manifest_declares_session_flush_and_reset_as_semantic_operations(self) -> None:
        manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

        self.assertNotIn("memory_reset_session_state", manifest["tool_sets"]["read_support"])
        self.assertIn(
            "memory_reset_session_state",
            manifest["tool_sets"]["semantic_extensions"],
        )
        self.assertIn("memory_session_flush", manifest["tool_sets"]["semantic_extensions"])
        self.assertEqual(
            manifest["operations"]["memory_reset_session_state"]["result_fields"],
            ["reset", "identity_updates_this_session"],
        )
        self.assertEqual(
            manifest["operations"]["memory_session_flush"]["result_fields"],
            ["session_id", "checkpoint_path", "entry_count", "trigger"],
        )
        self.assertEqual(
            manifest["ui_feedback"]["result_field_labels"]["checkpoint_path"],
            "Checkpoint Path",
        )
        self.assertEqual(
            manifest["ui_feedback"]["result_field_labels"]["trigger"],
            "Trigger",
        )

    def test_resolver_returns_structured_ui_feedback_for_semantic_mode(self) -> None:
        resolution = resolver.resolve_capabilities(REPO_ROOT)
        ui_feedback = resolution["ui_feedback"]
        create_plan = next(op for op in ui_feedback["operations"] if op["id"] == "create_plan")
        execute_plan = next(op for op in ui_feedback["operations"] if op["id"] == "execute_plan")

        self.assertEqual(ui_feedback["title"], "Governed Memory Writes")
        self.assertEqual(ui_feedback["status"], "ready")
        self.assertEqual(
            ui_feedback["status_label"],
            "Repo-local semantic MCP ready",
        )
        self.assertEqual(
            ui_feedback["primary_action"]["path"],
            "HUMANS/tooling/agent-memory-capabilities.toml",
        )
        self.assertEqual(
            ui_feedback["preview"]["sections"],
            [
                {"id": "summary", "label": "Change Summary"},
                {"id": "reasoning", "label": "Why This Change"},
                {"id": "target_files", "label": "Changed Files"},
                {"id": "invariant_effects", "label": "Invariant Effects"},
                {"id": "commit_suggestion", "label": "Commit Suggestion"},
                {"id": "fallback_behavior", "label": "Fallback Behavior"},
            ],
        )
        self.assertTrue(
            ui_feedback["preview"]["change_class_flows"]["proposed"]["preview_required"]
        )
        self.assertFalse(
            ui_feedback["preview"]["change_class_flows"]["automatic"]["preview_required"]
        )
        self.assertTrue(create_plan["preview_required"])
        self.assertEqual(
            create_plan["changed_files"],
            [
                "memory/working/projects/{project_id}/plans/{plan_id}.yaml",
                "memory/working/projects/{project_id}/SUMMARY.md",
                "memory/working/projects/SUMMARY.md",
                "memory/working/projects/{project_id}/operations.jsonl",
            ],
        )
        self.assertEqual(
            create_plan["highlighted_result_labels"],
            ["Status", "Plan File"],
        )
        self.assertTrue(execute_plan["preview_required"])
        self.assertEqual(
            execute_plan["highlighted_result_labels"],
            ["Plan Status", "Phase Id"],
        )

    def test_resolver_degrades_to_read_only_when_runtime_exports_only_read_tools(
        self,
    ) -> None:
        read_only_runtime = {
            "memory_read_file",
            "memory_list_folder",
            "memory_search",
            "memory_validate",
        }

        with mock.patch.object(resolver, "runtime_tools", return_value=read_only_runtime):
            resolution = resolver.resolve_capabilities(REPO_ROOT)

        discovery = resolution["capability_discovery"]
        ui_feedback = resolution["ui_feedback"]
        self.assertEqual(resolution["errors"], [], "\n".join(resolution["errors"]))
        self.assertEqual(discovery["mode"], "read_only")
        self.assertEqual(
            discovery["selected_strategy"],
            "codex_native_preview_and_policy",
        )
        self.assertEqual(discovery["available_semantic_tools"], [])
        self.assertEqual(ui_feedback["status"], "attention")
        self.assertEqual(
            ui_feedback["status_label"],
            "Read-only governed preview",
        )


if __name__ == "__main__":
    unittest.main()
