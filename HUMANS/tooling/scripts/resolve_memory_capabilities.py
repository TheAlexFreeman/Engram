#!/usr/bin/env python3
"""Resolve the governed-write capability manifest against the MCP runtime."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any, cast

try:
    tomllib = cast(ModuleType, import_module("tomllib"))
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = cast(ModuleType, import_module("tomli"))


MANIFEST_PATH = Path("HUMANS/tooling/agent-memory-capabilities.toml")
REQUIRED_TOOL_SET_KEYS = (
    "read_support",
    "raw_fallback",
    "semantic_extensions",
    "declared_gaps",
)
REQUIRED_INTEGRATION_BOUNDARY_KEYS = (
    "model",
    "prefer",
    "native_semantic_scope",
    "manifest_required_for_repo_specific_semantics",
    "degradation_order",
    "desktop_owns",
    "repo_local_mcp_owns",
    "native_fallback_owns",
)
REQUIRED_CAPABILITY_DISCOVERY_KEYS = (
    "well_known_paths",
    "requires_kind",
    "supported_versions",
    "requires_mcp_entrypoint",
    "minimum_read_tools",
    "minimum_semantic_tools",
    "read_only_runtime_allowed",
    "semantic_detection",
    "read_only_detection",
    "semantic_result",
    "read_only_result",
    "incompatible_result",
)
REQUIRED_UI_FEEDBACK_KEYS = (
    "panel_title",
    "manifest_action_label",
    "manifest_action_reason",
    "status_labels",
    "preview_section_labels",
    "result_field_labels",
)
REQUIRED_UI_FEEDBACK_STATUS_KEYS = (
    "semantic",
    "read_only",
    "fallback",
    "manifest_only",
)
REQUIRED_CHANGE_CLASS_KEYS = (
    "approval",
    "user_awareness",
    "ui_affordance",
    "read_only_behavior",
    "notes",
)
REQUIRED_OPERATION_KEYS = (
    "group",
    "tier",
    "change_class",
    "commit_model",
    "commit_category_hint",
    "writes",
    "owns_frontmatter",
    "owns_summaries",
    "owns_access_logs",
    "owns_review_queue",
    "result_fields",
    "fallback_tools",
    "error_kinds",
)
REQUIRED_RAW_FALLBACK_POLICY_KEYS = (
    "policy",
    "runtime_export",
    "opt_in_env_var",
    "requires_change_class",
    "preview_required_for",
    "read_only_mode",
)
REQUIRED_FALLBACK_PROFILE_KEYS = (
    "trigger",
    "raw_tools_allowed",
    "requires_change_class",
    "requires_contract_preservation",
    "result",
)
REQUIRED_FALLBACK_PROFILES = (
    "semantic_gap",
    "uninterpretable_target",
    "preview_only",
    "read_only",
)
REQUIRED_APPROVAL_PREVIEW_KEYS = (
    "required_for",
    "sections",
    "show_resulting_state",
    "show_warnings",
)
REQUIRED_APPROVAL_FLOW_KEYS = (
    "trigger",
    "primary_action",
    "secondary_actions",
    "deferred_outcome",
    "copy_style",
)
REQUIRED_APPROVAL_PREVIEW_SECTIONS = (
    "summary",
    "reasoning",
    "target_files",
    "invariant_effects",
    "commit_suggestion",
    "fallback_behavior",
)
ALLOWED_COMMIT_CATEGORY_HINTS = {
    "chat",
    "curation",
    "identity",
    "knowledge",
    "plan",
    "skill",
    "scratchpad",
    "system",
}
REQUIRED_DEGRADATION_ORDER = (
    "repo_local_semantic_mcp",
    "codex_native_preview_and_policy",
    "raw_fallback_or_defer",
)
REQUIRED_DESKTOP_OWNERSHIP = {
    "approval_ux",
    "change_class_enforcement",
    "capability_discovery",
    "preview_rendering",
    "result_presentation",
    "fallback_selection",
}
REQUIRED_REPO_LOCAL_MCP_OWNERSHIP = {
    "semantic_execution",
    "repo_specific_invariants",
    "schema_validation",
    "authoritative_mutation",
    "structured_result_state",
}
REQUIRED_NATIVE_FALLBACK_OWNERSHIP = {
    "generic_preview",
    "raw_tool_orchestration",
    "deferred_action_summary",
}
EXPECTED_SEMANTIC_DETECTION = "manifest_and_minimum_semantic_tools"
EXPECTED_READ_ONLY_DETECTION = "minimum_read_tools_without_write_tools"
RESULT_HIGHLIGHT_PRIORITY = (
    "plan_status",
    "phase_id",
    "next_action",
    "plan_progress",
    "phase_progress",
    "status",
    "new_path",
    "trust",
    "archive_path",
    "plan_path",
    "session_id",
    "flagged_path",
    "priority",
    "version_token",
    "target",
    "section",
    "key",
    "mode",
    "item_id",
    "identity_updates_this_session",
)


def load_manifest(repo_root: Path) -> dict[str, Any]:
    manifest_text = (repo_root / MANIFEST_PATH).read_text(encoding="utf-8")
    return tomllib.loads(manifest_text)


def runtime_tools(repo_root: Path) -> set[str]:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from engram_mcp.agent_memory_mcp.server import create_mcp

    _, tools, _, _ = create_mcp(repo_root=repo_root)
    return set(tools)


def runtime_tool_readonly_hints(
    repo_root: Path, tool_names: set[str] | None = None
) -> dict[str, bool | None]:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from engram_mcp.agent_memory_mcp.server import create_mcp

    mcp, _, _, _ = create_mcp(repo_root=repo_root)

    async def _collect() -> dict[str, bool | None]:
        listed = await mcp.list_tools()
        hints: dict[str, bool | None] = {}
        for tool in listed:
            name = str(tool.name)
            if tool_names is not None and name not in tool_names:
                continue
            annotations = getattr(tool, "annotations", None)
            hints[name] = cast(bool | None, getattr(annotations, "readOnlyHint", None))
        return hints

    return asyncio.run(_collect())


def _ensure_string_list(errors: list[str], label: str, value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"{label} must be an array of strings")
        return []
    return value


def _expand_profile_tools(manifest: dict[str, Any], profile_name: str) -> list[str]:
    raw_tool_sets = manifest.get("tool_sets")
    tool_sets = raw_tool_sets if isinstance(raw_tool_sets, dict) else {}
    raw_profiles = manifest.get("tool_profiles")
    profiles = raw_profiles if isinstance(raw_profiles, dict) else {}
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        return []

    tools: list[str] = []
    for tool_set_name in _ensure_string_list(
        [], "tool_profile.tool_sets", profile.get("tool_sets")
    ):
        tools.extend(
            _ensure_string_list([], f"tool_sets.{tool_set_name}", tool_sets.get(tool_set_name))
        )
    tools.extend(_ensure_string_list([], "tool_profile.tools", profile.get("tools")))
    excluded_tools = set(
        _ensure_string_list([], "tool_profile.exclude_tools", profile.get("exclude_tools"))
    )
    return sorted({tool for tool in tools if tool not in excluded_tools})


def _ensure_bool(errors: list[str], label: str, value: Any) -> bool:
    if not isinstance(value, bool):
        errors.append(f"{label} must be a boolean")
        return False
    return value


def _ensure_int_list(errors: list[str], label: str, value: Any) -> list[int]:
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        errors.append(f"{label} must be an array of integers")
        return []
    return value


def _humanize_identifier(value: str) -> str:
    return value.replace("_", " ").title()


def _pick_highlight_fields(result_fields: list[str]) -> list[str]:
    prioritized = [field for field in RESULT_HIGHLIGHT_PRIORITY if field in result_fields]
    if prioritized:
        return prioritized[:2]
    return result_fields[:1]


def resolve_capabilities(repo_root: Path, *, include_runtime: bool = True) -> dict[str, Any]:
    manifest = load_manifest(repo_root)
    errors: list[str] = []
    warnings: list[str] = []

    if manifest.get("version") != 1:
        errors.append(f"{MANIFEST_PATH}: version must be 1")

    tool_sets = manifest.get("tool_sets")
    if not isinstance(tool_sets, dict):
        errors.append(f"{MANIFEST_PATH}: tool_sets must be a TOML table")
        tool_sets = {}

    tool_lists = {
        key: _ensure_string_list(errors, f"tool_sets.{key}", tool_sets.get(key))
        for key in REQUIRED_TOOL_SET_KEYS
    }

    read_support = set(tool_lists["read_support"])
    raw_fallback = set(tool_lists["raw_fallback"])
    semantic_extensions = set(tool_lists["semantic_extensions"])
    declared_gaps = set(tool_lists["declared_gaps"])

    integration_boundary = manifest.get("integration_boundary")
    if not isinstance(integration_boundary, dict):
        errors.append(f"{MANIFEST_PATH}: integration_boundary must be a TOML table")
        integration_boundary = {}
    for key in REQUIRED_INTEGRATION_BOUNDARY_KEYS:
        if key not in integration_boundary:
            errors.append(f"{MANIFEST_PATH}: integration_boundary missing {key}")
    if integration_boundary.get("model") != "hybrid":
        errors.append(f"{MANIFEST_PATH}: integration_boundary.model must be 'hybrid'")
    if integration_boundary.get("prefer") != "repo_local_semantic_mcp":
        errors.append(
            f"{MANIFEST_PATH}: integration_boundary.prefer must be 'repo_local_semantic_mcp'"
        )
    if integration_boundary.get("native_semantic_scope") != "generic_only":
        errors.append(
            f"{MANIFEST_PATH}: integration_boundary.native_semantic_scope must be 'generic_only'"
        )
    if integration_boundary.get("manifest_required_for_repo_specific_semantics") is not True:
        errors.append(
            f"{MANIFEST_PATH}: integration_boundary.manifest_required_for_repo_specific_semantics must be true"
        )
    degradation_order = _ensure_string_list(
        errors,
        "integration_boundary.degradation_order",
        integration_boundary.get("degradation_order"),
    )
    if degradation_order != list(REQUIRED_DEGRADATION_ORDER):
        errors.append(
            f"{MANIFEST_PATH}: integration_boundary.degradation_order must match the hybrid fallback sequence"
        )
    ownership_specs = (
        (
            "desktop_owns",
            REQUIRED_DESKTOP_OWNERSHIP,
        ),
        (
            "repo_local_mcp_owns",
            REQUIRED_REPO_LOCAL_MCP_OWNERSHIP,
        ),
        (
            "native_fallback_owns",
            REQUIRED_NATIVE_FALLBACK_OWNERSHIP,
        ),
    )
    for key, required_items in ownership_specs:
        value = _ensure_string_list(
            errors,
            f"integration_boundary.{key}",
            integration_boundary.get(key),
        )
        missing_items = sorted(required_items - set(value))
        if missing_items:
            errors.append(
                f"{MANIFEST_PATH}: integration_boundary.{key} is missing required ownership markers {missing_items!r}"
            )

    capability_discovery = manifest.get("capability_discovery")
    if not isinstance(capability_discovery, dict):
        errors.append(f"{MANIFEST_PATH}: capability_discovery must be a TOML table")
        capability_discovery = {}
    for key in REQUIRED_CAPABILITY_DISCOVERY_KEYS:
        if key not in capability_discovery:
            errors.append(f"{MANIFEST_PATH}: capability_discovery missing {key}")

    well_known_paths = _ensure_string_list(
        errors,
        "capability_discovery.well_known_paths",
        capability_discovery.get("well_known_paths"),
    )
    if MANIFEST_PATH.as_posix() not in well_known_paths:
        errors.append(
            f"{MANIFEST_PATH}: capability_discovery.well_known_paths must include {MANIFEST_PATH.as_posix()!r}"
        )

    requires_kind = capability_discovery.get("requires_kind")
    if not isinstance(requires_kind, str):
        errors.append(f"{MANIFEST_PATH}: capability_discovery.requires_kind must be a string")
        requires_kind = ""
    if manifest.get("kind") != requires_kind:
        errors.append(
            f"{MANIFEST_PATH}: capability_discovery.requires_kind must match manifest kind"
        )

    supported_versions = _ensure_int_list(
        errors,
        "capability_discovery.supported_versions",
        capability_discovery.get("supported_versions"),
    )
    if manifest.get("version") not in supported_versions:
        errors.append(
            f"{MANIFEST_PATH}: capability_discovery.supported_versions must include the current manifest version"
        )

    requires_mcp_entrypoint = _ensure_bool(
        errors,
        "capability_discovery.requires_mcp_entrypoint",
        capability_discovery.get("requires_mcp_entrypoint"),
    )
    entrypoint = manifest.get("mcp_entrypoint")
    entrypoint_exists = False
    if requires_mcp_entrypoint:
        if not isinstance(entrypoint, str):
            errors.append(f"{MANIFEST_PATH}: mcp_entrypoint must be a string")
        else:
            entrypoint_exists = (repo_root / entrypoint).is_file()
            if not entrypoint_exists:
                errors.append(f"{MANIFEST_PATH}: mcp_entrypoint does not exist at {entrypoint!r}")
    elif isinstance(entrypoint, str):
        entrypoint_exists = (repo_root / entrypoint).is_file()

    minimum_read_tools = _ensure_string_list(
        errors,
        "capability_discovery.minimum_read_tools",
        capability_discovery.get("minimum_read_tools"),
    )
    unknown_minimum_read_tools = sorted(set(minimum_read_tools) - read_support)
    if unknown_minimum_read_tools:
        errors.append(
            f"{MANIFEST_PATH}: capability_discovery.minimum_read_tools references undeclared read tools {unknown_minimum_read_tools!r}"
        )

    minimum_semantic_tools = _ensure_string_list(
        errors,
        "capability_discovery.minimum_semantic_tools",
        capability_discovery.get("minimum_semantic_tools"),
    )
    unknown_minimum_semantic_tools = sorted(set(minimum_semantic_tools) - semantic_extensions)
    if unknown_minimum_semantic_tools:
        errors.append(
            f"{MANIFEST_PATH}: capability_discovery.minimum_semantic_tools references undeclared semantic tools {unknown_minimum_semantic_tools!r}"
        )

    read_only_runtime_allowed = _ensure_bool(
        errors,
        "capability_discovery.read_only_runtime_allowed",
        capability_discovery.get("read_only_runtime_allowed"),
    )

    if capability_discovery.get("semantic_detection") != EXPECTED_SEMANTIC_DETECTION:
        errors.append(
            f"{MANIFEST_PATH}: capability_discovery.semantic_detection must be {EXPECTED_SEMANTIC_DETECTION!r}"
        )
    if capability_discovery.get("read_only_detection") != EXPECTED_READ_ONLY_DETECTION:
        errors.append(
            f"{MANIFEST_PATH}: capability_discovery.read_only_detection must be {EXPECTED_READ_ONLY_DETECTION!r}"
        )

    expected_discovery_results = {
        "semantic_result": REQUIRED_DEGRADATION_ORDER[0],
        "read_only_result": REQUIRED_DEGRADATION_ORDER[1],
        "incompatible_result": REQUIRED_DEGRADATION_ORDER[2],
    }
    for key, expected_value in expected_discovery_results.items():
        if capability_discovery.get(key) != expected_value:
            errors.append(f"{MANIFEST_PATH}: capability_discovery.{key} must be {expected_value!r}")

    for left_name, left, right_name, right in (
        ("read_support", read_support, "raw_fallback", raw_fallback),
        ("read_support", read_support, "semantic_extensions", semantic_extensions),
        ("raw_fallback", raw_fallback, "semantic_extensions", semantic_extensions),
    ):
        overlap = sorted(left & right)
        if overlap:
            errors.append(
                f"{MANIFEST_PATH}: tool_sets.{left_name} and tool_sets.{right_name} overlap: {overlap!r}"
            )

    shared_result = manifest.get("shared_result")
    if not isinstance(shared_result, dict):
        errors.append(f"{MANIFEST_PATH}: shared_result must be a TOML table")
        shared_result = {}
    shared_fields = _ensure_string_list(errors, "shared_result.fields", shared_result.get("fields"))
    if shared_fields != [
        "files_changed",
        "commit_sha",
        "commit_message",
        "new_state",
        "warnings",
        "preview",
    ]:
        errors.append(
            f"{MANIFEST_PATH}: shared_result.fields must match the MemoryWriteResult contract"
        )

    change_classes = manifest.get("change_classes")
    if not isinstance(change_classes, dict):
        errors.append(f"{MANIFEST_PATH}: change_classes must be a TOML table")
        change_classes = {}
    for class_name, config in change_classes.items():
        if not isinstance(config, dict):
            errors.append(f"{MANIFEST_PATH}: change_classes.{class_name} must be a TOML table")
            continue
        for key in REQUIRED_CHANGE_CLASS_KEYS:
            if not isinstance(config.get(key), str):
                errors.append(
                    f"{MANIFEST_PATH}: change_classes.{class_name}.{key} must be a string"
                )

    raw_fallback_policy = manifest.get("raw_fallback_policy")
    if not isinstance(raw_fallback_policy, dict):
        errors.append(f"{MANIFEST_PATH}: raw_fallback_policy must be a TOML table")
        raw_fallback_policy = {}
    for key in REQUIRED_RAW_FALLBACK_POLICY_KEYS:
        if key not in raw_fallback_policy:
            errors.append(f"{MANIFEST_PATH}: raw_fallback_policy missing {key}")
    if raw_fallback_policy.get("policy") != "inherit_operation_change_class":
        errors.append(
            f"{MANIFEST_PATH}: raw_fallback_policy.policy must be 'inherit_operation_change_class'"
        )
    if raw_fallback_policy.get("runtime_export") != "opt_in":
        errors.append(f"{MANIFEST_PATH}: raw_fallback_policy.runtime_export must be 'opt_in'")
    if not isinstance(raw_fallback_policy.get("opt_in_env_var"), str):
        errors.append(f"{MANIFEST_PATH}: raw_fallback_policy.opt_in_env_var must be a string")
    if raw_fallback_policy.get("requires_change_class") is not True:
        errors.append(f"{MANIFEST_PATH}: raw_fallback_policy.requires_change_class must be true")
    preview_required_for = _ensure_string_list(
        errors,
        "raw_fallback_policy.preview_required_for",
        raw_fallback_policy.get("preview_required_for"),
    )
    for class_name in preview_required_for:
        if class_name not in change_classes:
            errors.append(
                f"{MANIFEST_PATH}: raw_fallback_policy.preview_required_for references unknown class {class_name!r}"
            )
    if not isinstance(raw_fallback_policy.get("read_only_mode"), str):
        errors.append(f"{MANIFEST_PATH}: raw_fallback_policy.read_only_mode must be a string")

    fallback_behavior = manifest.get("fallback_behavior")
    if not isinstance(fallback_behavior, dict):
        errors.append(f"{MANIFEST_PATH}: fallback_behavior must be a TOML table")
        fallback_behavior = {}
    for profile_name in REQUIRED_FALLBACK_PROFILES:
        profile = fallback_behavior.get(profile_name)
        if not isinstance(profile, dict):
            errors.append(f"{MANIFEST_PATH}: fallback_behavior.{profile_name} must be a TOML table")
            continue
        for key in REQUIRED_FALLBACK_PROFILE_KEYS:
            if key not in profile:
                errors.append(f"{MANIFEST_PATH}: fallback_behavior.{profile_name} missing {key}")
        if not isinstance(profile.get("trigger"), str):
            errors.append(
                f"{MANIFEST_PATH}: fallback_behavior.{profile_name}.trigger must be a string"
            )
        _ensure_bool(
            errors,
            f"fallback_behavior.{profile_name}.raw_tools_allowed",
            profile.get("raw_tools_allowed"),
        )
        if profile.get("requires_change_class") is not True:
            errors.append(
                f"{MANIFEST_PATH}: fallback_behavior.{profile_name}.requires_change_class must be true"
            )
        _ensure_bool(
            errors,
            f"fallback_behavior.{profile_name}.requires_contract_preservation",
            profile.get("requires_contract_preservation"),
        )
        if not isinstance(profile.get("result"), str):
            errors.append(
                f"{MANIFEST_PATH}: fallback_behavior.{profile_name}.result must be a string"
            )

    expected_fallback_flags = {
        "semantic_gap": {"raw_tools_allowed": True, "requires_contract_preservation": True},
        "uninterpretable_target": {
            "raw_tools_allowed": False,
            "requires_contract_preservation": True,
        },
        "preview_only": {
            "raw_tools_allowed": False,
            "requires_contract_preservation": False,
        },
        "read_only": {
            "raw_tools_allowed": False,
            "requires_contract_preservation": False,
        },
    }
    for profile_name, expectations in expected_fallback_flags.items():
        profile = fallback_behavior.get(profile_name)
        if not isinstance(profile, dict):
            continue
        for key, expected in expectations.items():
            if profile.get(key) != expected:
                errors.append(
                    f"{MANIFEST_PATH}: fallback_behavior.{profile_name}.{key} must be {expected!r}"
                )

    approval_ux = manifest.get("approval_ux")
    if not isinstance(approval_ux, dict):
        errors.append(f"{MANIFEST_PATH}: approval_ux must be a TOML table")
        approval_ux = {}

    preview = approval_ux.get("preview")
    if not isinstance(preview, dict):
        errors.append(f"{MANIFEST_PATH}: approval_ux.preview must be a TOML table")
        preview = {}
    for key in REQUIRED_APPROVAL_PREVIEW_KEYS:
        if key not in preview:
            errors.append(f"{MANIFEST_PATH}: approval_ux.preview missing {key}")
    preview_required_for = _ensure_string_list(
        errors,
        "approval_ux.preview.required_for",
        preview.get("required_for"),
    )
    for class_name in preview_required_for:
        if class_name not in change_classes:
            errors.append(
                f"{MANIFEST_PATH}: approval_ux.preview.required_for references unknown class {class_name!r}"
            )
    for class_name in ("proposed", "protected"):
        if class_name not in preview_required_for:
            errors.append(
                f"{MANIFEST_PATH}: approval_ux.preview.required_for must include {class_name!r}"
            )
    preview_sections = _ensure_string_list(
        errors,
        "approval_ux.preview.sections",
        preview.get("sections"),
    )
    for section_name in REQUIRED_APPROVAL_PREVIEW_SECTIONS:
        if section_name not in preview_sections:
            errors.append(
                f"{MANIFEST_PATH}: approval_ux.preview.sections must include {section_name!r}"
            )
    _ensure_bool(
        errors,
        "approval_ux.preview.show_resulting_state",
        preview.get("show_resulting_state"),
    )
    _ensure_bool(
        errors,
        "approval_ux.preview.show_warnings",
        preview.get("show_warnings"),
    )

    approval_flows: dict[str, dict[str, Any]] = {}
    for class_name in ("proposed", "protected"):
        flow = approval_ux.get(class_name)
        if not isinstance(flow, dict):
            errors.append(f"{MANIFEST_PATH}: approval_ux.{class_name} must be a TOML table")
            flow = {}
        approval_flows[class_name] = flow
        for key in REQUIRED_APPROVAL_FLOW_KEYS:
            if key not in flow:
                errors.append(f"{MANIFEST_PATH}: approval_ux.{class_name} missing {key}")
        if not isinstance(flow.get("trigger"), str):
            errors.append(f"{MANIFEST_PATH}: approval_ux.{class_name}.trigger must be a string")
        if not isinstance(flow.get("primary_action"), str):
            errors.append(
                f"{MANIFEST_PATH}: approval_ux.{class_name}.primary_action must be a string"
            )
        _ensure_string_list(
            errors,
            f"approval_ux.{class_name}.secondary_actions",
            flow.get("secondary_actions"),
        )
        if not isinstance(flow.get("deferred_outcome"), str):
            errors.append(
                f"{MANIFEST_PATH}: approval_ux.{class_name}.deferred_outcome must be a string"
            )
        if not isinstance(flow.get("copy_style"), str):
            errors.append(f"{MANIFEST_PATH}: approval_ux.{class_name}.copy_style must be a string")

    ui_feedback = manifest.get("ui_feedback")
    if not isinstance(ui_feedback, dict):
        errors.append(f"{MANIFEST_PATH}: ui_feedback must be a TOML table")
        ui_feedback = {}
    for key in REQUIRED_UI_FEEDBACK_KEYS:
        if key not in ui_feedback:
            errors.append(f"{MANIFEST_PATH}: ui_feedback missing {key}")

    for key in ("panel_title", "manifest_action_label", "manifest_action_reason"):
        if not isinstance(ui_feedback.get(key), str):
            errors.append(f"{MANIFEST_PATH}: ui_feedback.{key} must be a string")

    status_labels = ui_feedback.get("status_labels")
    if not isinstance(status_labels, dict):
        errors.append(f"{MANIFEST_PATH}: ui_feedback.status_labels must be a TOML table")
        status_labels = {}
    for key in REQUIRED_UI_FEEDBACK_STATUS_KEYS:
        if not isinstance(status_labels.get(key), str):
            errors.append(f"{MANIFEST_PATH}: ui_feedback.status_labels.{key} must be a string")

    preview_section_labels = ui_feedback.get("preview_section_labels")
    if not isinstance(preview_section_labels, dict):
        errors.append(f"{MANIFEST_PATH}: ui_feedback.preview_section_labels must be a TOML table")
        preview_section_labels = {}
    for section_name in preview_sections:
        if not isinstance(preview_section_labels.get(section_name), str):
            errors.append(
                f"{MANIFEST_PATH}: ui_feedback.preview_section_labels.{section_name} must be a string"
            )

    result_field_labels = ui_feedback.get("result_field_labels")
    if not isinstance(result_field_labels, dict):
        errors.append(f"{MANIFEST_PATH}: ui_feedback.result_field_labels must be a TOML table")
        result_field_labels = {}

    error_taxonomy = manifest.get("error_taxonomy")
    if not isinstance(error_taxonomy, dict):
        errors.append(f"{MANIFEST_PATH}: error_taxonomy must be a TOML table")
        error_taxonomy = {}

    operations = manifest.get("operations")
    if not isinstance(operations, dict):
        errors.append(f"{MANIFEST_PATH}: operations must be a TOML table")
        operations = {}

    for tool_name in semantic_extensions:
        op = operations.get(tool_name)
        if not isinstance(op, dict):
            errors.append(f"{MANIFEST_PATH}: missing operations.{tool_name} table")
            continue
        for key in REQUIRED_OPERATION_KEYS:
            if key not in op:
                errors.append(f"{MANIFEST_PATH}: operations.{tool_name} missing {key}")
        if op.get("tier") != "semantic":
            errors.append(f"{MANIFEST_PATH}: operations.{tool_name}.tier must be 'semantic'")
        commit_category_hint = op.get("commit_category_hint")
        if commit_category_hint not in ALLOWED_COMMIT_CATEGORY_HINTS:
            errors.append(
                f"{MANIFEST_PATH}: operations.{tool_name}.commit_category_hint must be one of {sorted(ALLOWED_COMMIT_CATEGORY_HINTS)!r}"
            )
        change_class = op.get("change_class")
        if change_class not in change_classes:
            errors.append(
                f"{MANIFEST_PATH}: operations.{tool_name}.change_class references unknown class {change_class!r}"
            )
        fallback_tools = _ensure_string_list(
            errors,
            f"operations.{tool_name}.fallback_tools",
            op.get("fallback_tools"),
        )
        for fallback_tool in fallback_tools:
            if fallback_tool not in raw_fallback:
                errors.append(
                    f"{MANIFEST_PATH}: operations.{tool_name}.fallback_tools references unknown raw tool {fallback_tool!r}"
                )
        error_kinds = _ensure_string_list(
            errors,
            f"operations.{tool_name}.error_kinds",
            op.get("error_kinds"),
        )
        result_fields = _ensure_string_list(
            errors,
            f"operations.{tool_name}.result_fields",
            op.get("result_fields"),
        )
        for result_field in result_fields:
            if not isinstance(result_field_labels.get(result_field), str):
                errors.append(
                    f"{MANIFEST_PATH}: ui_feedback.result_field_labels.{result_field} must be a string"
                )
        for error_kind in error_kinds:
            if error_kind not in error_taxonomy:
                errors.append(
                    f"{MANIFEST_PATH}: operations.{tool_name}.error_kinds references unknown error {error_kind!r}"
                )

    desktop_operations = manifest.get("desktop_operations")
    if not isinstance(desktop_operations, dict):
        errors.append(f"{MANIFEST_PATH}: desktop_operations must be a TOML table")
        desktop_operations = {}

    implemented_desktop_ops: dict[str, str] = {}
    gap_ops: list[str] = []
    for operation_name, config in desktop_operations.items():
        if not isinstance(config, dict):
            errors.append(
                f"{MANIFEST_PATH}: desktop_operations.{operation_name} must be a TOML table"
            )
            continue
        status = config.get("status")
        change_class = config.get("change_class")
        if change_class not in change_classes:
            errors.append(
                f"{MANIFEST_PATH}: desktop_operations.{operation_name}.change_class references unknown class {change_class!r}"
            )
        if status == "implemented":
            tool_name_value = config.get("tool")
            if not isinstance(tool_name_value, str):
                errors.append(
                    f"{MANIFEST_PATH}: desktop_operations.{operation_name}.tool must be a string"
                )
                continue
            tool_name = tool_name_value
            if tool_name not in semantic_extensions:
                errors.append(
                    f"{MANIFEST_PATH}: desktop_operations.{operation_name} references non-semantic tool {tool_name!r}"
                )
            if operations.get(tool_name, {}).get("change_class") != change_class:
                errors.append(
                    f"{MANIFEST_PATH}: desktop_operations.{operation_name}.change_class must match operations.{tool_name}.change_class"
                )
            implemented_desktop_ops[operation_name] = tool_name
        elif status == "gap":
            gap_ops.append(operation_name)
            fallback_profile = config.get("fallback_profile")
            if not isinstance(fallback_profile, str):
                errors.append(
                    f"{MANIFEST_PATH}: desktop_operations.{operation_name}.fallback_profile must be a string for gap operations"
                )
            elif fallback_profile not in fallback_behavior:
                errors.append(
                    f"{MANIFEST_PATH}: desktop_operations.{operation_name}.fallback_profile references unknown fallback profile {fallback_profile!r}"
                )
            if operation_name not in declared_gaps:
                warnings.append(
                    f"{MANIFEST_PATH}: desktop gap {operation_name!r} is not listed in tool_sets.declared_gaps"
                )
        else:
            errors.append(
                f"{MANIFEST_PATH}: desktop_operations.{operation_name}.status must be 'implemented' or 'gap'"
            )

    runtime_tool_names: set[str] = set()
    available_read_tools: list[str] = []
    available_raw_tools: list[str] = []
    available_semantic_tools: list[str] = []
    missing_declared_tools: dict[str, list[str]] = {
        "read_support": [],
        "raw_fallback": [],
        "semantic_extensions": [],
    }
    unavailable_opt_in_raw_tools: list[str] = []
    missing_minimum_read_tools: list[str] = []
    missing_minimum_semantic_tools: list[str] = []
    undeclared_runtime_tools: list[str] = []
    public_mutating_tools_without_contract: list[str] = []
    unsafe_read_only_profile_tools: list[str] = []
    contract_compatible = (
        manifest.get("kind") == requires_kind
        and manifest.get("version") in supported_versions
        and (not requires_mcp_entrypoint or entrypoint_exists)
    )
    discovery_mode = "manifest_only"
    selected_strategy = capability_discovery.get("semantic_result")
    discovery_reason = "Runtime inspection was skipped."
    if include_runtime:
        runtime_tool_names = runtime_tools(repo_root)
        runtime_readonly_hints = runtime_tool_readonly_hints(repo_root, runtime_tool_names)
        available_read_tools = sorted(read_support & runtime_tool_names)
        available_raw_tools = sorted(raw_fallback & runtime_tool_names)
        available_semantic_tools = sorted(semantic_extensions & runtime_tool_names)
        raw_fallback_export_mode = raw_fallback_policy.get("runtime_export")
        raw_fallback_is_opt_in = raw_fallback_export_mode == "opt_in"
        raw_fallback_missing = sorted(raw_fallback - runtime_tool_names)
        if raw_fallback_is_opt_in and not available_raw_tools:
            unavailable_opt_in_raw_tools = raw_fallback_missing
        missing_declared_tools = {
            "read_support": sorted(read_support - runtime_tool_names),
            "raw_fallback": [] if unavailable_opt_in_raw_tools else raw_fallback_missing,
            "semantic_extensions": sorted(semantic_extensions - runtime_tool_names),
        }
        missing_minimum_read_tools = sorted(set(minimum_read_tools) - runtime_tool_names)
        missing_minimum_semantic_tools = sorted(set(minimum_semantic_tools) - runtime_tool_names)

        write_tools_present = bool((raw_fallback | semantic_extensions) & runtime_tool_names)
        read_only_runtime = (
            read_only_runtime_allowed and not write_tools_present and not missing_minimum_read_tools
        )
        declared_runtime_tools = set(read_support) | set(semantic_extensions)
        if available_raw_tools or not raw_fallback_is_opt_in:
            declared_runtime_tools |= set(raw_fallback)
        undeclared_runtime_tools = sorted(runtime_tool_names - declared_runtime_tools)
        if undeclared_runtime_tools:
            errors.append(
                f"{MANIFEST_PATH}: MCP runtime exports undeclared tools {undeclared_runtime_tools!r}"
            )

        operation_tool_names = {
            name
            for name, value in operations.items()
            if isinstance(name, str) and isinstance(value, dict)
        }
        public_mutating_tools_without_contract = sorted(
            name
            for name, read_only_hint in runtime_readonly_hints.items()
            if read_only_hint is False
            and name not in raw_fallback
            and name not in operation_tool_names
        )
        if public_mutating_tools_without_contract:
            errors.append(
                f"{MANIFEST_PATH}: public non-read-only tools lack operations metadata {public_mutating_tools_without_contract!r}"
            )

        read_only_profile_tools = _expand_profile_tools(manifest, "read_only")
        unsafe_read_only_profile_tools = sorted(
            name for name in read_only_profile_tools if runtime_readonly_hints.get(name) is False
        )
        if unsafe_read_only_profile_tools:
            errors.append(
                f"{MANIFEST_PATH}: read_only profile contains non-read-only runtime tools {unsafe_read_only_profile_tools!r}"
            )

        if write_tools_present:
            expected_runtime_tools = set(declared_runtime_tools)
            for tool_name in sorted(expected_runtime_tools):
                if tool_name not in runtime_tool_names:
                    errors.append(
                        f"{MANIFEST_PATH}: declared tool {tool_name!r} is not exported by the MCP runtime"
                    )
        else:
            for tool_name in missing_minimum_read_tools:
                errors.append(
                    f"{MANIFEST_PATH}: required read-only tool {tool_name!r} is not exported by the MCP runtime"
                )
            optional_read_tools = sorted(
                read_support - set(minimum_read_tools) - runtime_tool_names
            )
            if optional_read_tools:
                warnings.append(
                    f"{MANIFEST_PATH}: runtime is read-only and omits optional read tools {optional_read_tools!r}"
                )
        if unavailable_opt_in_raw_tools:
            warnings.append(
                f"{MANIFEST_PATH}: raw fallback tools are not exported by default; enable {raw_fallback_policy.get('opt_in_env_var')!r} for unmanaged fallback mode"
            )

        partial_semantic_runtime = bool(available_semantic_tools) and bool(
            missing_minimum_semantic_tools
        )

        if (
            contract_compatible
            and not missing_minimum_read_tools
            and not missing_minimum_semantic_tools
        ):
            discovery_mode = "semantic"
            selected_strategy = capability_discovery.get("semantic_result")
            discovery_reason = (
                "Manifest is compatible and the runtime exports the minimum semantic tool set."
            )
        elif contract_compatible and read_only_runtime:
            discovery_mode = "read_only"
            selected_strategy = capability_discovery.get("read_only_result")
            discovery_reason = "Manifest is compatible and the runtime exports the minimum read tool set without write tools."
        else:
            discovery_mode = "fallback"
            selected_strategy = capability_discovery.get("incompatible_result")
            reason_parts: list[str] = []
            if not contract_compatible:
                reason_parts.append("manifest compatibility checks failed")
            if missing_minimum_read_tools:
                reason_parts.append(
                    f"minimum read tools are missing: {missing_minimum_read_tools!r}"
                )
            if missing_minimum_semantic_tools and write_tools_present:
                reason_parts.append(
                    f"minimum semantic tools are missing: {missing_minimum_semantic_tools!r}"
                )
            if partial_semantic_runtime:
                warnings.append(
                    f"{MANIFEST_PATH}: runtime exports a partial semantic tool set; degrading to {selected_strategy!r}"
                )
            if not reason_parts:
                reason_parts.append("runtime does not satisfy the capability discovery contract")
            discovery_reason = "; ".join(reason_parts)

    ui_status_by_mode = {
        "semantic": "ready",
        "read_only": "attention",
        "fallback": "attention",
        "manifest_only": "info",
    }
    preview_required_set = set(preview_required_for)
    ui_preview_sections = [
        {
            "id": section_name,
            "label": preview_section_labels.get(
                section_name,
                _humanize_identifier(section_name),
            ),
        }
        for section_name in preview.get("sections", [])
        if isinstance(section_name, str)
    ]
    ui_change_class_flows: dict[str, dict[str, Any]] = {}
    for class_name in ("automatic", "proposed", "protected"):
        if class_name not in change_classes:
            continue
        flow = approval_flows.get(class_name, {})
        change_class_config = change_classes[class_name]
        ui_change_class_flows[class_name] = {
            "preview_required": class_name in preview_required_set,
            "ui_affordance": change_class_config.get("ui_affordance"),
            "read_only_behavior": change_class_config.get("read_only_behavior"),
            "primary_action": flow.get("primary_action"),
            "secondary_actions": flow.get("secondary_actions", []),
            "deferred_outcome": flow.get("deferred_outcome"),
        }

    ui_operation_summaries: list[dict[str, Any]] = []
    implemented_operation_count = 0
    gap_operation_count = 0
    for operation_name, config in desktop_operations.items():
        if not isinstance(config, dict):
            continue
        operation_summary: dict[str, Any] = {
            "id": operation_name,
            "title": _humanize_identifier(operation_name),
            "status": config.get("status"),
            "group": config.get("operation_group"),
            "change_class": config.get("change_class"),
            "preview_required": config.get("change_class") in preview_required_set,
        }

        if config.get("status") == "implemented":
            implemented_operation_count += 1
            tool_name_value = config.get("tool")
            implemented_tool_name = tool_name_value if isinstance(tool_name_value, str) else None
            operation_config = (
                operations.get(implemented_tool_name, {})
                if isinstance(implemented_tool_name, str)
                else {}
            )
            changed_files = [
                path for path in operation_config.get("writes", []) if isinstance(path, str)
            ]
            result_fields = [
                field
                for field in operation_config.get("result_fields", [])
                if isinstance(field, str)
            ]
            highlighted_result_fields = _pick_highlight_fields(result_fields)
            operation_summary.update(
                {
                    "tool": implemented_tool_name,
                    "commit_category_hint": operation_config.get("commit_category_hint"),
                    "changed_files": changed_files,
                    "changed_file_count": len(changed_files),
                    "result_fields": [
                        {
                            "id": field,
                            "label": result_field_labels.get(
                                field,
                                _humanize_identifier(field),
                            ),
                            "highlight": field in highlighted_result_fields,
                        }
                        for field in result_fields
                    ],
                    "highlighted_result_fields": highlighted_result_fields,
                    "highlighted_result_labels": [
                        result_field_labels.get(field, _humanize_identifier(field))
                        for field in highlighted_result_fields
                    ],
                }
            )
        elif config.get("status") == "gap":
            gap_operation_count += 1
            operation_summary.update(
                {
                    "fallback_profile": config.get("fallback_profile"),
                    "notes": config.get("notes"),
                }
            )

        ui_operation_summaries.append(operation_summary)

    ui_feedback_summary = {
        "title": ui_feedback.get("panel_title"),
        "status": ui_status_by_mode.get(discovery_mode, "attention"),
        "status_label": status_labels.get(
            discovery_mode,
            _humanize_identifier(discovery_mode),
        ),
        "strategy": selected_strategy,
        "reason": discovery_reason,
        "primary_action": {
            "label": ui_feedback.get("manifest_action_label"),
            "path": MANIFEST_PATH.as_posix(),
            "reason": ui_feedback.get("manifest_action_reason"),
        },
        "preview": {
            "required_for": preview_required_for,
            "sections": ui_preview_sections,
            "show_resulting_state": preview.get("show_resulting_state"),
            "show_warnings": preview.get("show_warnings"),
            "change_class_flows": ui_change_class_flows,
        },
        "operations": ui_operation_summaries,
        "implemented_operation_count": implemented_operation_count,
        "gap_operation_count": gap_operation_count,
        "warning_count": len(warnings),
        "warnings": warnings,
    }

    return {
        "manifest_path": str(repo_root / MANIFEST_PATH),
        "change_classes": change_classes,
        "tool_sets": {
            "read_support": sorted(read_support),
            "raw_fallback": sorted(raw_fallback),
            "semantic_extensions": sorted(semantic_extensions),
            "declared_gaps": sorted(declared_gaps),
        },
        "integration_boundary": integration_boundary,
        "capability_discovery": {
            "well_known_paths": well_known_paths,
            "requires_kind": requires_kind,
            "supported_versions": supported_versions,
            "requires_mcp_entrypoint": requires_mcp_entrypoint,
            "mcp_entrypoint": entrypoint,
            "entrypoint_exists": entrypoint_exists,
            "minimum_read_tools": minimum_read_tools,
            "minimum_semantic_tools": minimum_semantic_tools,
            "read_only_runtime_allowed": read_only_runtime_allowed,
            "semantic_detection": capability_discovery.get("semantic_detection"),
            "read_only_detection": capability_discovery.get("read_only_detection"),
            "contract_compatible": contract_compatible,
            "available_read_tools": available_read_tools,
            "available_raw_tools": available_raw_tools,
            "available_semantic_tools": available_semantic_tools,
            "raw_fallback_available": bool(available_raw_tools),
            "unavailable_opt_in_raw_tools": unavailable_opt_in_raw_tools,
            "missing_declared_tools": missing_declared_tools,
            "missing_minimum_read_tools": missing_minimum_read_tools,
            "missing_minimum_semantic_tools": missing_minimum_semantic_tools,
            "undeclared_runtime_tools": undeclared_runtime_tools,
            "public_mutating_tools_without_contract": public_mutating_tools_without_contract,
            "unsafe_read_only_profile_tools": unsafe_read_only_profile_tools,
            "mode": discovery_mode,
            "selected_strategy": selected_strategy,
            "reason": discovery_reason,
        },
        "ui_feedback": ui_feedback_summary,
        "raw_fallback_policy": raw_fallback_policy,
        "fallback_behavior": fallback_behavior,
        "approval_ux": {
            "preview": preview,
            "proposed": approval_flows.get("proposed", {}),
            "protected": approval_flows.get("protected", {}),
        },
        "implemented_desktop_operations": implemented_desktop_ops,
        "gap_operations": sorted(gap_ops),
        "gap_operation_fallback_profiles": {
            operation_name: desktop_operations[operation_name]["fallback_profile"]
            for operation_name in sorted(gap_ops)
            if isinstance(desktop_operations.get(operation_name), dict)
            and "fallback_profile" in desktop_operations[operation_name]
        },
        "operation_change_classes": {
            tool_name: operations[tool_name]["change_class"]
            for tool_name in sorted(semantic_extensions)
            if isinstance(operations.get(tool_name), dict)
            and "change_class" in operations[tool_name]
        },
        "operation_commit_categories": {
            tool_name: operations[tool_name]["commit_category_hint"]
            for tool_name in sorted(semantic_extensions)
            if isinstance(operations.get(tool_name), dict)
            and "commit_category_hint" in operations[tool_name]
        },
        "runtime_tools": sorted(runtime_tool_names),
        "errors": errors,
        "warnings": warnings,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve the agent-memory capability manifest against the MCP runtime."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        default=".",
        help="Path to the memory repo root.",
    )
    parser.add_argument(
        "--skip-runtime",
        action="store_true",
        help="Only validate manifest structure; do not import the MCP runtime.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation level for output.",
    )
    return parser.parse_args(argv[1:])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv)
    repo_root = Path(args.repo_root).resolve()
    resolution = resolve_capabilities(repo_root, include_runtime=not args.skip_runtime)
    json.dump(resolution, sys.stdout, indent=args.indent)
    sys.stdout.write("\n")
    return 1 if resolution["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
