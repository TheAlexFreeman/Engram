"""Read tools — shared helpers and constants used by all read-tool submodules."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import date, datetime
from importlib import import_module
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, cast

from ...identity_paths import is_working_scratchpad_path, normalize_user_id
from ...path_policy import KNOWN_COMMIT_PREFIXES  # noqa: F401 — re-exported for callers
from ..reference_extractor import (
    build_connectivity_graph,
    resolve_link_diagnostics,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def _tool_annotations(**kwargs: object) -> Any:
    """Return MCP tool annotations with a relaxed runtime-only type surface."""
    return cast(Any, kwargs)


# Trust decay thresholds (days) — defaults; runtime reads from core/INIT.md
_DEFAULT_LOW_THRESHOLD = 120
_DEFAULT_MEDIUM_THRESHOLD = 180
_IGNORED_NAMES = frozenset(
    {
        ".git",
        ".claude",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)
_HUMANS_DIRNAME = "HUMANS"
_DEFAULT_AGGREGATION_TRIGGER = 15
_NEAR_TRIGGER_WINDOW = 3
_PERIODIC_REVIEW_DAYS = 30
_STAGE_ORDER = ("Exploration", "Calibration", "Consolidation")
_CAPABILITIES_MANIFEST_PATH = Path("HUMANS/tooling/agent-memory-capabilities.toml")
_MARKDOWN_LINK_RE = re.compile(r"(?<!\!)\[[^\]]+\]\(([^)]+)\)")
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_CURATION_HIGH_ACCESS_THRESHOLD = 5
_CURATION_RETIREMENT_THRESHOLD = 3
_CURATION_HIGH_HELPFULNESS_THRESHOLD = 0.5
_CURATION_NEAR_MISS_MIN = 0.2
_CURATION_NEAR_MISS_MAX = 0.4
_CURATION_FALSE_POSITIVE_MAX = 0.1
_CURATION_RETIREMENT_MAX = 0.3
_READ_FILE_INLINE_THRESHOLD_BYTES = 64_000
_READ_FILE_DEFAULT_LIMIT_BYTES = 64_000
_READ_FILE_MAX_LIMIT_BYTES = 256_000


def _cross_filesystem_sandbox_detected() -> bool:
    """Return True when the deployment indicates the MCP server and agent sandbox
    sit on different filesystems.

    Detection is explicit-only: reads ``AGENT_MEMORY_CROSS_FILESYSTEM`` from the
    environment. Anything that parses as a truthy flag (``1``, ``true``, ``yes``,
    ``on``) suppresses ``temp_file`` returns even when a caller asks for them,
    because a temp path minted server-side is not resolvable from the sandbox.
    """
    import os as _os

    raw = _os.environ.get("AGENT_MEMORY_CROSS_FILESYSTEM", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


try:
    tomllib = cast(Any, import_module("tomllib"))
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = cast(Any, import_module("tomli"))


def _parse_trust_thresholds(repo_root: Path) -> tuple[int, int]:
    """Try to read low/medium trust thresholds from core/INIT.md (or legacy HOME.md)."""
    qr_path = _resolve_live_router_path(repo_root)
    if not qr_path.exists():
        return _DEFAULT_LOW_THRESHOLD, _DEFAULT_MEDIUM_THRESHOLD
    text = qr_path.read_text(encoding="utf-8")
    low = _DEFAULT_LOW_THRESHOLD
    medium = _DEFAULT_MEDIUM_THRESHOLD
    # Look for patterns like "low: 120 days" or "120-day" near "low trust"
    low_m = re.search(r"low.*?(\d+)[- ]day", text, re.IGNORECASE)
    medium_m = re.search(r"medium.*?(\d+)[- ]day", text, re.IGNORECASE)
    if low_m:
        low = int(low_m.group(1))
    if medium_m:
        medium = int(medium_m.group(1))
    return low, medium


def _resolve_live_router_path(repo_root: Path) -> Path:
    """Return the current live router path, falling back to legacy locations."""
    for candidate in (
        repo_root / "core" / "INIT.md",
        repo_root / "INIT.md",
        repo_root / "core" / "HOME.md",
        repo_root / "HOME.md",
    ):
        if candidate.exists():
            return candidate
    return repo_root / "core" / "INIT.md"


def _resolve_governance_path(repo_root: Path, relative_path: str) -> Path:
    """Return a governance file path, preferring the current layout."""
    normalized = relative_path.replace("\\", "/").lstrip("/")
    legacy_name = normalized.split("/", 1)[-1]
    for candidate in (
        repo_root / "governance" / legacy_name,
        repo_root / "meta" / legacy_name,
    ):
        if candidate.exists():
            return candidate
    return repo_root / "governance" / legacy_name


def _resolve_capabilities_manifest_path(root: Path) -> Path:
    """Return the capabilities manifest path for content-rooted or repo-rooted layouts."""
    for candidate in (
        root / _CAPABILITIES_MANIFEST_PATH,
        root.parent / _CAPABILITIES_MANIFEST_PATH,
    ):
        if candidate.exists():
            return candidate
    return root / _CAPABILITIES_MANIFEST_PATH


def _resolve_memory_subpath(root: Path, current_rel: str, legacy_rel: str) -> Path:
    """Return a content path, preferring the current memory layout with legacy fallback."""
    for candidate in (root / current_rel, root / legacy_rel):
        if candidate.exists():
            return candidate
    return root / current_rel


def _normalize_access_folder_prefixes(raw_folder: str) -> tuple[str, ...]:
    """Map ACCESS folder filters to current and legacy content prefixes."""
    normalized = raw_folder.replace("\\", "/").strip().rstrip("/")
    if not normalized:
        return ()

    alias_map = {
        "knowledge": ("memory/knowledge", "knowledge"),
        "plans": ("memory/working/projects", "plans"),
        "identity": ("memory/users", "identity"),
        "skills": ("memory/skills", "skills"),
    }
    return alias_map.get(normalized, (normalized,))


def _resolve_category_prefixes(raw_category: str) -> tuple[str, ...]:
    """Map category names to current and legacy content directories."""
    normalized = raw_category.replace("\\", "/").strip().rstrip("/")
    if not normalized:
        return ()

    alias_map = {
        "knowledge": ("memory/knowledge", "knowledge"),
        "plans": ("memory/working/projects", "plans"),
        "identity": ("memory/users", "identity"),
        "skills": ("memory/skills", "skills"),
    }
    return alias_map.get(normalized, (normalized,))


def _content_folder_for_file(file_path: str) -> str:
    """Return the governed folder containing a file path."""
    parent = PurePosixPath(file_path).parent.as_posix()
    return "" if parent == "." else parent


def _is_access_log_in_scope(rel_path: PurePosixPath) -> bool:
    """Return True when an ACCESS log belongs to governed content, not meta/governance."""
    normalized = rel_path.as_posix()
    return normalized.startswith(
        (
            "memory/",
            "knowledge/",
            "plans/",
            "identity/",
            "skills/",
        )
    )


def _resolve_humans_root(root: Path) -> Path:
    """Return the human-facing tree, supporting both repo-rooted and content-rooted layouts."""
    for candidate in (root / _HUMANS_DIRNAME, root.parent / _HUMANS_DIRNAME):
        if candidate.exists():
            return candidate
    return root.parent / _HUMANS_DIRNAME


def _resolve_visible_path(root: Path, raw_path: str) -> Path:
    """Resolve a repo-visible path, including sibling HUMANS/ content when exposed."""
    normalized = raw_path.replace("\\", "/").strip()
    if normalized in {"", "."}:
        return root.resolve()

    rel_path = Path(normalized)
    if rel_path.is_absolute():
        return rel_path.resolve()

    parts = rel_path.parts
    if parts and parts[0] == _HUMANS_DIRNAME:
        humans_root = _resolve_humans_root(root)
        remainder = parts[1:]
        return (humans_root.joinpath(*remainder) if remainder else humans_root).resolve()

    direct_path = (root / rel_path).resolve()
    if direct_path.exists() or not parts:
        return direct_path

    alias_prefixes = _resolve_category_prefixes(parts[0])
    if alias_prefixes and alias_prefixes != (parts[0],):
        remainder = parts[1:]
        for prefix in alias_prefixes:
            candidate = (root / Path(prefix).joinpath(*remainder)).resolve()
            if candidate.exists():
                return candidate
        primary = alias_prefixes[0]
        return (root / Path(primary).joinpath(*remainder)).resolve()

    return direct_path


def _display_rel_path(path: Path, root: Path) -> str:
    """Return the visible repo-relative path for content-rooted and sibling HUMANS paths."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        humans_root = _resolve_humans_root(root)
        humans_rel = path.relative_to(humans_root).as_posix()
        return f"{_HUMANS_DIRNAME}/{humans_rel}" if humans_rel not in {"", "."} else _HUMANS_DIRNAME


def _build_capabilities_summary(
    manifest: dict[str, Any],
    *,
    runtime_tool_names: set[str] | None = None,
) -> dict[str, Any]:
    tool_sets = manifest.get("tool_sets") if isinstance(manifest.get("tool_sets"), dict) else {}
    read_support = tool_sets.get("read_support") if isinstance(tool_sets, dict) else []
    raw_fallback = tool_sets.get("raw_fallback") if isinstance(tool_sets, dict) else []
    semantic_extensions = (
        tool_sets.get("semantic_extensions") if isinstance(tool_sets, dict) else []
    )
    declared_gaps = tool_sets.get("declared_gaps") if isinstance(tool_sets, dict) else []
    read_tools = read_support if isinstance(read_support, list) else []
    raw_tools = raw_fallback if isinstance(raw_fallback, list) else []
    semantic_tools = semantic_extensions if isinstance(semantic_extensions, list) else []
    gaps = declared_gaps if isinstance(declared_gaps, list) else []
    contract_versions = manifest.get("contract_versions")
    if not isinstance(contract_versions, dict):
        contract_versions = {}
    desktop_ops = _desktop_operations(manifest)
    tool_profile_contract = _tool_profile_contract(manifest)
    tool_profiles = _tool_profile_definitions(manifest)
    resources = _native_surface_section(manifest, "resources")
    prompts = _native_surface_section(manifest, "prompts")
    preview_capable_operations = sorted(
        key
        for key, value in desktop_ops.items()
        if value.get("preview_support") is True or isinstance(value.get("preview_mode"), str)
    )

    declared_tools = {
        *[tool for tool in read_tools if isinstance(tool, str)],
        *[tool for tool in raw_tools if isinstance(tool, str)],
        *[tool for tool in semantic_tools if isinstance(tool, str)],
    }
    runtime_tools = set(runtime_tool_names or set())
    runtime_not_in_manifest = sorted(runtime_tools - declared_tools)
    declared_not_in_runtime = sorted(declared_tools - runtime_tools) if runtime_tools else []
    total_tools = len(runtime_tools) if runtime_tools else len(declared_tools)

    return {
        "total_tools": total_tools,
        "declared_total_tools": len(declared_tools),
        "runtime_total_tools": len(runtime_tools) if runtime_tools else None,
        "read_tools": len([tool for tool in read_tools if isinstance(tool, str)]),
        "raw_tools": len([tool for tool in raw_tools if isinstance(tool, str)]),
        "semantic_tools": len([tool for tool in semantic_tools if isinstance(tool, str)]),
        "declared_gaps": len([gap for gap in gaps if isinstance(gap, str)]),
        "contract_versions": contract_versions,
        "preview_capable_operation_count": len(preview_capable_operations),
        "preview_capable_operations": preview_capable_operations,
        "tool_profile_count": len(tool_profiles),
        "tool_profiles": sorted(tool_profiles),
        "default_tool_profile": tool_profile_contract.get("default_profile"),
        "profile_selection_mode": tool_profile_contract.get("selection_mode"),
        "dynamic_profile_switching": tool_profile_contract.get("dynamic_runtime_switching") is True,
        "list_changed_supported": tool_profile_contract.get("list_changed_supported") is True,
        "resource_count": len(resources),
        "prompt_count": len(prompts),
        "runtime_not_in_manifest_count": len(runtime_not_in_manifest),
        "runtime_not_in_manifest": runtime_not_in_manifest[:25],
        "declared_not_in_runtime_count": len(declared_not_in_runtime),
        "declared_not_in_runtime": declared_not_in_runtime[:25],
    }


async def _list_registered_tool_names(mcp: "FastMCP") -> set[str]:
    """Best-effort registered tool listing for capability-summary reconciliation."""
    try:
        tools = await mcp.list_tools()
    except Exception:
        return set()
    return {str(tool.name) for tool in tools}


def _capability_manifest_error_payload(root: Path, message: str, raw: str | None) -> dict[str, Any]:
    return {
        "error": message,
        "path": _CAPABILITIES_MANIFEST_PATH.as_posix(),
        "raw": raw,
        "repo_root": root.as_posix(),
    }


def _load_capabilities_manifest(root: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    manifest_path = _resolve_capabilities_manifest_path(root)
    try:
        raw_manifest = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, _capability_manifest_error_payload(
            root,
            f"Could not read capability manifest: {exc}",
            None,
        )

    try:
        parsed = tomllib.loads(raw_manifest)
    except Exception as exc:
        return None, _capability_manifest_error_payload(
            root,
            f"Could not parse capability manifest: {exc}",
            raw_manifest,
        )

    if not isinstance(parsed, dict):
        return None, _capability_manifest_error_payload(
            root,
            "Capability manifest did not parse to a TOML table",
            raw_manifest,
        )
    return dict(parsed), None


def _normalize_repo_relative_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    if not normalized:
        return normalized
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        raise ValueError("path must be a repo-relative path")
    if re.match(r"^[A-Za-z]:[/\\]", normalized):
        raise ValueError("path must be a repo-relative path")
    return normalized.rstrip("/") if normalized != "." else normalized


def _desktop_operations(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_ops = manifest.get("desktop_operations")
    if not isinstance(raw_ops, dict):
        return {}
    return {key: value for key, value in raw_ops.items() if isinstance(value, dict)}


def _tool_profile_definitions(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_profiles = manifest.get("tool_profiles")
    if not isinstance(raw_profiles, dict):
        return {}
    return {key: value for key, value in raw_profiles.items() if isinstance(value, dict)}


def _tool_profile_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    raw_contract = manifest.get("tool_profile_contract")
    if not isinstance(raw_contract, dict):
        return {}
    return dict(raw_contract)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _manifest_tool_sets(manifest: dict[str, Any]) -> dict[str, list[str]]:
    raw_tool_sets = manifest.get("tool_sets")
    if not isinstance(raw_tool_sets, dict):
        return {}
    return {
        name: _string_list(value) for name, value in raw_tool_sets.items() if isinstance(name, str)
    }


def _expand_tool_profile(
    manifest: dict[str, Any], profile_name: str, profile_definition: dict[str, Any]
) -> dict[str, Any]:
    tool_sets = _manifest_tool_sets(manifest)
    selected_tool_sets = _string_list(profile_definition.get("tool_sets"))
    tools: list[str] = []
    for tool_set_name in selected_tool_sets:
        tools.extend(tool_sets.get(tool_set_name, []))
    tools.extend(_string_list(profile_definition.get("tools")))
    excluded_tools = set(_string_list(profile_definition.get("exclude_tools")))
    unique_tools = sorted(
        {tool for tool in tools if isinstance(tool, str) and tool not in excluded_tools}
    )

    return {
        "name": profile_name,
        "label": profile_definition.get("label", profile_name.replace("_", " ").title()),
        "description": profile_definition.get("description"),
        "default": profile_definition.get("default") is True,
        "tool_sets": selected_tool_sets,
        "tools": unique_tools,
        "tool_count": len(unique_tools),
    }


def _build_tool_profile_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    contract = _tool_profile_contract(manifest)
    profiles = _tool_profile_definitions(manifest)
    expanded_profiles = {
        name: _expand_tool_profile(manifest, name, definition)
        for name, definition in sorted(profiles.items())
    }
    return {
        "contract": contract,
        "default_profile": contract.get("default_profile"),
        "dynamic_runtime_switching": contract.get("dynamic_runtime_switching") is True,
        "list_changed_supported": contract.get("list_changed_supported") is True,
        "profiles": expanded_profiles,
    }


def _native_surface_section(manifest: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    native_surface = manifest.get("mcp_native_surface")
    if not isinstance(native_surface, dict):
        return {}
    raw_section = native_surface.get(key)
    if not isinstance(raw_section, dict):
        return {}
    return {name: value for name, value in raw_section.items() if isinstance(value, dict)}


def _build_policy_summary_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    change_classes = manifest.get("change_classes")
    if not isinstance(change_classes, dict):
        change_classes = {}
    raw_fallback_policy = manifest.get("raw_fallback_policy")
    if not isinstance(raw_fallback_policy, dict):
        raw_fallback_policy = {}
    integration_boundary = manifest.get("integration_boundary")
    if not isinstance(integration_boundary, dict):
        integration_boundary = {}
    tool_profile_contract = _tool_profile_contract(manifest)

    summarized_classes = {
        name: {
            "approval": value.get("approval"),
            "user_awareness": value.get("user_awareness"),
            "read_only_behavior": value.get("read_only_behavior"),
            "notes": value.get("notes"),
        }
        for name, value in change_classes.items()
        if isinstance(name, str) and isinstance(value, dict)
    }

    return {
        "change_classes": summarized_classes,
        "raw_fallback_policy": dict(raw_fallback_policy),
        "integration_boundary": {
            "model": integration_boundary.get("model"),
            "prefer": integration_boundary.get("prefer"),
            "degradation_order": integration_boundary.get("degradation_order"),
            "desktop_owns": integration_boundary.get("desktop_owns"),
            "repo_local_mcp_owns": integration_boundary.get("repo_local_mcp_owns"),
            "native_fallback_owns": integration_boundary.get("native_fallback_owns"),
        },
        "tool_profiles": {
            "default_profile": tool_profile_contract.get("default_profile"),
            "selection_mode": tool_profile_contract.get("selection_mode"),
            "dynamic_runtime_switching": tool_profile_contract.get("dynamic_runtime_switching")
            is True,
            "list_changed_supported": tool_profile_contract.get("list_changed_supported") is True,
        },
        "resources_vs_tools": {
            "resources_for": [
                "stable summaries",
                "navigation snapshots",
                "read-mostly repo state",
            ],
            "prompts_for": [
                "workflow scaffolding",
                "host-side UX guidance",
                "reusable governed conversations",
            ],
            "tools_for": [
                "authoritative mutations",
                "path-specific policy compilation",
                "parameterized read operations",
            ],
        },
    }


def _build_active_plan_summary_payload(root: Path) -> dict[str, Any]:
    active_plans = _collect_plan_entries(root, status="active")
    top_plan = active_plans[0] if active_plans else None
    return {
        "generated_at": str(date.today()),
        "active_plan_count": len(active_plans),
        "top_plan": top_plan,
        "plans": active_plans,
    }


def _compact_plan_next_action(next_action_info: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(next_action_info, dict):
        return None

    compact: dict[str, Any] = {}
    for key in (
        "id",
        "title",
        "requires_approval",
        "attempt_number",
        "has_prior_failures",
        "suggest_revision",
    ):
        if key not in next_action_info or next_action_info[key] is None:
            continue
        compact[key] = next_action_info[key]
    return compact or None


def _prompt_json_section(title: str, payload: dict[str, Any]) -> str:
    return f"## {title}\n\n```json\n{json.dumps(payload, indent=2)}\n```"


def _manifest_operations(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_ops = manifest.get("operations")
    if not isinstance(raw_ops, dict):
        return {}
    return {key: value for key, value in raw_ops.items() if isinstance(value, dict)}


def _resolve_operation_entry(
    manifest: dict[str, Any], operation: str
) -> tuple[str | None, dict[str, Any] | None]:
    desktop_ops = _desktop_operations(manifest)
    operations = _manifest_operations(manifest)
    candidate = operation.strip()
    if not candidate:
        return None, None

    if candidate in desktop_ops:
        return candidate, desktop_ops[candidate]

    for key, value in desktop_ops.items():
        if value.get("tool") == candidate:
            return key, value

    if candidate in operations:
        return candidate, operations[candidate]

    return None, None


def _path_policy_state(root: Path, rel_path: str | None) -> dict[str, Any]:
    update_guidelines_text = ""
    curation_policy_text = ""
    update_guidelines_path = _resolve_governance_path(root, "update-guidelines.md")
    curation_policy_path = _resolve_governance_path(root, "curation-policy.md")
    if update_guidelines_path.exists():
        update_guidelines_text = update_guidelines_path.read_text(encoding="utf-8")
    if curation_policy_path.exists():
        curation_policy_text = curation_policy_path.read_text(encoding="utf-8")

    if not rel_path:
        return {
            "path": None,
            "exists": None,
            "top_level_root": None,
            "protected_surface": False,
            "path_change_class": None,
            "reasons": [],
            "trust_constraints": [],
            "governance_sources_loaded": {
                "update_guidelines": bool(update_guidelines_text),
                "curation_policy": bool(curation_policy_text),
            },
        }

    normalized = _normalize_repo_relative_path(rel_path)
    abs_path = root / normalized
    top_level_root = normalized.split("/", 1)[0] if "/" in normalized else normalized
    reasons: list[str] = []
    trust_constraints: list[str] = []
    protected_surface = False
    path_change_class: str | None = None

    meta_protected = "Any modification to files in `governance/`" in update_guidelines_text
    skills_protected = (
        "Creating, modifying, or removing files in `memory/skills/`." in update_guidelines_text
    )
    users_proposed = (
        "Adding, modifying, or removing files in `memory/users/`." in update_guidelines_text
    )
    unverified_inform_only = (
        "Inform only" in curation_policy_text and "never instruct" in curation_policy_text.lower()
    )

    if normalized in {"INIT.md", "HOME.md", "README.md", "CHANGELOG.md"} or (
        normalized.startswith("governance/") and meta_protected
    ):
        protected_surface = True
        path_change_class = "protected"
        reasons.append("Governance and top-level architecture files require explicit approval.")
    elif normalized.startswith("memory/skills/") and skills_protected:
        protected_surface = True
        path_change_class = "protected"
        reasons.append("Skill files are protected because they can directly shape agent procedure.")
    elif normalized.startswith("memory/users/") and users_proposed:
        path_change_class = "proposed"
        reasons.append(
            "User profile changes require explicit user awareness before durable writes."
        )
    elif normalized.startswith("memory/knowledge/_unverified/"):
        if unverified_inform_only:
            trust_constraints.append(
                "Unverified knowledge is low-trust by default and should inform, not instruct."
            )
    elif normalized.startswith("memory/knowledge/"):
        trust_constraints.append(
            "Verified knowledge is usable context, but promotion or archival changes remain governed operations."
        )

    if normalized.startswith("memory/skills/"):
        trust_constraints.append(
            "Protected skill surfaces require explicit approval before mutation."
        )
    if normalized.startswith("governance/"):
        trust_constraints.append(
            "Governance surfaces are protected files; machine-generated exceptions are narrow."
        )

    return {
        "path": normalized,
        "exists": abs_path.exists(),
        "top_level_root": top_level_root,
        "protected_surface": protected_surface,
        "path_change_class": path_change_class,
        "reasons": reasons,
        "trust_constraints": trust_constraints,
        "governance_sources_loaded": {
            "update_guidelines": bool(update_guidelines_text),
            "curation_policy": bool(curation_policy_text),
        },
    }


def _class_details(manifest: dict[str, Any], change_class: str | None) -> dict[str, Any] | None:
    if not change_class:
        return None
    change_classes = manifest.get("change_classes")
    if not isinstance(change_classes, dict):
        return None
    details = change_classes.get(change_class)
    return dict(details) if isinstance(details, dict) else None


def _preview_required(manifest: dict[str, Any], change_class: str | None) -> bool:
    raw_fallback_policy = manifest.get("raw_fallback_policy")
    if not isinstance(raw_fallback_policy, dict) or change_class is None:
        return False
    required_for = raw_fallback_policy.get("preview_required_for")
    return isinstance(required_for, list) and change_class in required_for


def _build_policy_state_payload(
    root: Path,
    manifest: dict[str, Any],
    operation: str | None,
    rel_path: str | None,
) -> dict[str, Any]:
    operation_key, operation_entry = _resolve_operation_entry(manifest, operation or "")
    path_state = _path_policy_state(root, rel_path)
    change_class = None
    tool_name = None
    operation_group = None
    tier = None
    notes = None
    fallback_tools: list[str] = []
    preview_available = False
    preview_mode = None
    preview_argument = None
    if operation_entry is not None:
        change_class = (
            operation_entry.get("change_class")
            if isinstance(operation_entry.get("change_class"), str)
            else None
        )
        tool_name = (
            operation_entry.get("tool") if isinstance(operation_entry.get("tool"), str) else None
        ) or operation_key
        operation_group = (
            operation_entry.get("operation_group")
            if isinstance(operation_entry.get("operation_group"), str)
            else operation_entry.get("group")
            if isinstance(operation_entry.get("group"), str)
            else None
        )
        tier = operation_entry.get("tier") if isinstance(operation_entry.get("tier"), str) else None
        notes = (
            operation_entry.get("notes") if isinstance(operation_entry.get("notes"), str) else None
        )
        preview_available = operation_entry.get("preview_support") is True or isinstance(
            operation_entry.get("preview_mode"), str
        )
        preview_mode = (
            operation_entry.get("preview_mode")
            if isinstance(operation_entry.get("preview_mode"), str)
            else None
        )
        preview_argument = (
            operation_entry.get("preview_argument")
            if isinstance(operation_entry.get("preview_argument"), str)
            else None
        )
        raw_fallback_tools = operation_entry.get("fallback_tools")
        if isinstance(raw_fallback_tools, list):
            fallback_tools = [tool for tool in raw_fallback_tools if isinstance(tool, str)]

    effective_change_class = change_class or path_state["path_change_class"]
    class_details = _class_details(manifest, effective_change_class)
    read_only_behavior = None
    if class_details and isinstance(class_details.get("read_only_behavior"), str):
        read_only_behavior = class_details["read_only_behavior"]

    fallback_behavior = manifest.get("fallback_behavior")
    if not isinstance(fallback_behavior, dict):
        fallback_behavior = {}
    preview_only: dict[str, Any] = cast(
        dict[str, Any],
        fallback_behavior.get("preview_only")
        if isinstance(fallback_behavior.get("preview_only"), dict)
        else {},
    )
    read_only_fallback: dict[str, Any] = cast(
        dict[str, Any],
        fallback_behavior.get("read_only")
        if isinstance(fallback_behavior.get("read_only"), dict)
        else {},
    )
    uninterpretable_target: dict[str, Any] = cast(
        dict[str, Any],
        fallback_behavior.get("uninterpretable_target")
        if isinstance(fallback_behavior.get("uninterpretable_target"), dict)
        else {},
    )

    semantic_target_supported = operation_entry is not None or not bool(rel_path)
    if rel_path and operation_entry is None:
        semantic_target_supported = not (
            path_state["path"]
            and not path_state["protected_surface"]
            and not any(
                path_state["path"].startswith(prefix) for prefix in ("memory/", "governance/")
            )
        )

    warnings: list[str] = []
    if operation and operation_entry is None:
        warnings.append(f"Unknown governed operation: {operation}")
    if rel_path and not semantic_target_supported:
        warnings.append("Target path is outside the current semantic memory model.")

    return {
        "operation": operation_key or operation or None,
        "tool": tool_name,
        "operation_group": operation_group,
        "tier": tier,
        "change_class": effective_change_class,
        "change_class_details": class_details,
        "approval_required": effective_change_class in {"proposed", "protected"},
        "preview_required": _preview_required(manifest, effective_change_class),
        "preview_available": preview_available,
        "preview_mode": preview_mode,
        "preview_argument": preview_argument,
        "read_only_behavior": read_only_behavior or read_only_fallback.get("result"),
        "preview_behavior": preview_only.get("result"),
        "semantic_target_supported": semantic_target_supported,
        "uninterpretable_target_behavior": uninterpretable_target.get("result"),
        "fallback_tools": fallback_tools,
        "notes": notes,
        "path_policy": path_state,
        "policy_sources": [
            _CAPABILITIES_MANIFEST_PATH.as_posix(),
            _resolve_governance_path(root, "update-guidelines.md").relative_to(root).as_posix(),
            _resolve_governance_path(root, "curation-policy.md").relative_to(root).as_posix(),
        ],
        "warnings": warnings,
    }


def _list_known_project_ids(root: Path) -> list[str]:
    """Enumerate project folders under ``memory/working/projects/``.

    Used for cold-start intent routing to match a project name referenced in a
    natural-language intent. Kept as a thin, duplicate-free helper rather than
    importing ``_context._list_project_ids`` to avoid a cyclic dependency.
    """
    projects_root = root / "memory" / "working" / "projects"
    if not projects_root.is_dir():
        return []
    return sorted(
        entry.name
        for entry in projects_root.iterdir()
        if entry.is_dir() and entry.name != "OUT" and not entry.name.startswith("_")
    )


_COLD_START_PROJECT_PHRASES = (
    "brief me on",
    "briefing on",
    "briefing for",
    "summary of",
    "summarise",
    "summarize",
    "get me up to speed on",
    "onboard me to",
    "onboard me on",
    "cold start on",
    "cold-start on",
    "cold starting on",
    "cold-starting on",
    "start work on",
    "starting work on",
    "pick up work on",
    "picking up",
    "ramp up on",
)
_COLD_START_LIST_PHRASES = (
    "what projects are active",
    "list projects",
    "list all projects",
    "what projects",
    "what am i working on",
    "which projects",
    "show me projects",
    "show projects",
)
_COLD_START_RESUME_PHRASES = (
    "resume work",
    "resume where i left off",
    "continue where i left off",
    "continue my work",
    "pick up where i left off",
)


def _match_cold_start_project(intent_lower: str, root: Path) -> str | None:
    """Return the project ID referenced by a cold-start intent, if any."""
    known = _list_known_project_ids(root)
    if not known:
        return None
    # Prefer longer names first so "rate-my-set" wins over a hypothetical "rate".
    for project_id in sorted(known, key=len, reverse=True):
        candidate = project_id.lower()
        if candidate and candidate in intent_lower:
            return project_id
    return None


def _route_intent_candidates(intent: str, rel_path: str | None, root: Path) -> list[dict[str, Any]]:
    intent_lower = intent.lower()
    normalized_path = _normalize_repo_relative_path(rel_path) if rel_path else None
    abs_path = (root / normalized_path) if normalized_path else None
    path_is_dir = bool(abs_path and abs_path.exists() and abs_path.is_dir())
    plural_signal = any(word in intent_lower for word in ("batch", "multiple", "many", "several"))
    nested_signal = any(word in intent_lower for word in ("subtree", "tree", "recursive", "nested"))

    candidates: list[dict[str, Any]] = []

    def add(
        operation: str,
        score: float,
        reason: str,
        *,
        arguments: dict[str, Any] | None = None,
    ) -> None:
        entry: dict[str, Any] = {"operation": operation, "score": score, "reason": reason}
        if arguments:
            entry["arguments"] = arguments
        candidates.append(entry)

    if "create" in intent_lower and "plan" in intent_lower:
        add("create_plan", 0.98, "Intent explicitly requests creating a plan.")
    if "plan" in intent_lower and any(
        word in intent_lower
        for word in ("complete", "check off", "mark done", "start", "execute", "advance")
    ):
        add("execute_plan", 0.95, "Intent sounds like starting or completing structured plan work.")
    if any(word in intent_lower for word in ("export", "review")) and "plan" in intent_lower:
        add(
            "review_plan", 0.93, "Intent sounds like reviewing or exporting completed plan outputs."
        )

    if "promote" in intent_lower and (
        "knowledge" in intent_lower
        or (normalized_path and normalized_path.startswith("memory/knowledge/_unverified/"))
    ):
        if path_is_dir and nested_signal:
            add(
                "promote_knowledge_subtree",
                0.98,
                "Directory target plus nested/subtree wording suggests preserving subpaths.",
            )
        elif path_is_dir or plural_signal:
            add(
                "promote_knowledge_batch",
                0.96,
                "Directory or multi-file wording suggests batched promotion.",
            )
        else:
            add(
                "promote_knowledge",
                0.97,
                "Single-file promotion intent matches the one-file semantic tool.",
            )

    if any(word in intent_lower for word in ("demote", "move back to unverified")) and (
        "knowledge" in intent_lower
        or (normalized_path and normalized_path.startswith("memory/knowledge/"))
    ):
        add("demote_knowledge", 0.95, "Intent asks to move verified knowledge back into review.")

    if "archive" in intent_lower and (
        "knowledge" in intent_lower
        or (normalized_path and normalized_path.startswith("memory/knowledge/"))
    ):
        add("archive_knowledge", 0.95, "Intent explicitly asks to archive knowledge content.")

    if (
        any(word in intent_lower for word in ("add", "create", "write"))
        and "knowledge" in intent_lower
        and (
            "unverified" in intent_lower
            or (normalized_path and normalized_path.startswith("memory/knowledge/_unverified/"))
        )
    ):
        add("add_knowledge_file", 0.93, "Intent matches writing a new unverified knowledge file.")

    if any(word in intent_lower for word in ("access", "retrieval")) and any(
        word in intent_lower for word in ("log", "record", "append")
    ):
        add(
            "append_access_entry" if not plural_signal else "memory_log_access_batch",
            0.91,
            "Intent matches ACCESS logging rather than content mutation.",
        )

    if "periodic review" in intent_lower and any(
        word in intent_lower for word in ("record", "apply", "save")
    ):
        add(
            "record_periodic_review",
            0.92,
            "Intent targets persisting approved periodic-review outputs.",
        )

    if "review queue" in intent_lower and any(
        word in intent_lower for word in ("resolve", "close", "clear")
    ):
        add("resolve_review_item", 0.92, "Intent sounds like resolving a queued review item.")
    if "review queue" in intent_lower and any(
        word in intent_lower for word in ("flag", "add", "queue")
    ):
        add("flag_for_review", 0.9, "Intent sounds like adding a new review-queue entry.")

    if "skill" in intent_lower and any(
        word in intent_lower for word in ("update", "edit", "change", "create")
    ):
        add("update_skill", 0.93, "Intent targets a protected skill mutation.")

    if "identity" in intent_lower and any(
        word in intent_lower for word in ("update", "edit", "change")
    ):
        add("update_user_trait", 0.92, "User trait update intent.")

    if "session" in intent_lower and any(
        word in intent_lower for word in ("record", "wrap up", "summarize")
    ):
        add("record_session", 0.9, "Intent sounds like session wrap-up or persistence.")

    # --- Cold-start intents ------------------------------------------------
    # An agent asked to pick up work on a project needs three primitives: the
    # per-project context bundle (context_project), the projects navigator
    # (projects SUMMARY.md), and the session entry point (session_bootstrap).
    # The routing table below maps natural-language cold-start phrasings onto
    # whichever primitive best serves the question. See cold-start roadmap
    # (P0-C) for rationale.
    cold_start_project = _match_cold_start_project(intent_lower, root)
    briefing_phrase_hit = any(phrase in intent_lower for phrase in _COLD_START_PROJECT_PHRASES)
    list_phrase_hit = any(phrase in intent_lower for phrase in _COLD_START_LIST_PHRASES)
    resume_phrase_hit = any(phrase in intent_lower for phrase in _COLD_START_RESUME_PHRASES)

    if cold_start_project and briefing_phrase_hit:
        add(
            "memory_context_project",
            0.95,
            (
                f"Cold-start briefing request for '{cold_start_project}' — load the "
                "enriched project bundle."
            ),
            arguments={"project": cold_start_project},
        )
    elif briefing_phrase_hit and not cold_start_project:
        # Phrase looks cold-start but no project was named — fall through to
        # bootstrap so the agent gets a list of active work.
        add(
            "memory_session_bootstrap",
            0.85,
            (
                "Cold-start phrasing without a recognized project — session_bootstrap "
                "returns active plans with resume_context pointers."
            ),
        )
    elif cold_start_project:
        # Project name surfaced on its own (e.g., "rate-my-set") — still the
        # right target for the project bundle but with a slightly lower score
        # because the intent is less specific.
        add(
            "memory_context_project",
            0.88,
            f"Intent references project '{cold_start_project}' — load the project bundle.",
            arguments={"project": cold_start_project},
        )

    if list_phrase_hit:
        add(
            "memory_read_file",
            0.92,
            (
                "Listing active projects — read the navigator at "
                "memory/working/projects/SUMMARY.md for status, focus, and last activity."
            ),
            arguments={"path": "memory/working/projects/SUMMARY.md"},
        )

    if resume_phrase_hit:
        add(
            "memory_session_bootstrap",
            0.9,
            (
                "Resume-work intent — session_bootstrap surfaces active plans with "
                "resume_context pointers ready to dereference."
            ),
        )

    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        existing = deduped.get(candidate["operation"])
        if existing is None or candidate["score"] > existing["score"]:
            deduped[candidate["operation"]] = candidate
    return sorted(
        deduped.values(),
        key=lambda item: (-cast(float, item["score"]), cast(str, item["operation"])),
    )


def _route_workflow_hint(operation: str | None, rel_path: str | None, root: Path) -> str | None:
    """Return a compact next-step hint for governed workflows."""
    if operation is None:
        return None

    normalized_operation = operation.removeprefix("memory_")

    normalized_path = _normalize_repo_relative_path(rel_path) if rel_path else None
    abs_path = (root / normalized_path) if normalized_path else None
    path_is_dir = bool(abs_path and abs_path.exists() and abs_path.is_dir())
    default_folder = normalized_path or "memory/knowledge/_unverified"

    if normalized_operation == "promote_knowledge":
        return (
            f"Inspect context with memory_prepare_unverified_review(folder_path='{default_folder}') if needed, "
            "then preview with memory_promote_knowledge(..., preview=True) before applying."
        )
    if normalized_operation == "promote_knowledge_batch":
        if path_is_dir:
            return (
                f"List candidates with memory_prepare_promotion_batch(folder_path='{default_folder}'), "
                "then promote the selected flat file list with memory_promote_knowledge_batch(...)."
            )
        return "Promote the selected flat file list with memory_promote_knowledge_batch(...)."
    if normalized_operation == "promote_knowledge_subtree":
        target_folder = (
            default_folder.replace("memory/knowledge/_unverified/", "memory/knowledge/", 1)
            if default_folder.startswith("memory/knowledge/_unverified/")
            else "memory/knowledge/<target-folder>"
        )
        return (
            f"Review the folder with memory_prepare_unverified_review(folder_path='{default_folder}'), "
            f"dry-run memory_promote_knowledge_subtree(source_folder='{default_folder}', dest_folder='{target_folder}', dry_run=True), "
            "then rerun with dry_run=False to apply."
        )
    return None


def _preview_file_entry(entry: Path, root: Path, preview_chars: int) -> dict[str, Any]:
    from ...frontmatter_utils import read_with_frontmatter

    rel_path = _display_rel_path(entry, root)
    item: dict[str, Any] = {
        "name": entry.name,
        "path": rel_path,
        "kind": "file",
        "size_bytes": entry.stat().st_size,
    }
    if preview_chars <= 0 or entry.suffix.lower() != ".md":
        return item

    frontmatter, body = read_with_frontmatter(entry)
    item["frontmatter"] = frontmatter or None
    body_preview = body.strip()[:preview_chars].rstrip()
    if body_preview:
        item["preview"] = body_preview
    return item


def _extract_preview_words(body: str, max_words: int) -> str:
    if max_words <= 0:
        return ""
    words = body.split()
    return " ".join(words[:max_words])


def _review_expiry_threshold_days(
    trust: str | None, low_threshold: int, medium_threshold: int
) -> int | None:
    if trust == "low":
        return low_threshold
    if trust == "medium":
        return medium_threshold
    if trust == "high":
        return 365
    return None


def _parse_expires_date(fm: dict) -> date | None:
    """Return the explicit expiration date from frontmatter, or None."""
    val = fm.get("expires")
    if not val:
        return None
    try:
        if isinstance(val, date):
            return val
        return datetime.strptime(str(val), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_aggregation_trigger(repo_root: Path) -> int:
    """Read the active ACCESS aggregation trigger from the live router file."""
    qr_path = _resolve_live_router_path(repo_root)
    if not qr_path.exists():
        return _DEFAULT_AGGREGATION_TRIGGER

    text = qr_path.read_text(encoding="utf-8")
    match = re.search(
        r"aggregation trigger\s*\|\s*(\d+)\s+entries",
        text,
        re.IGNORECASE,
    )
    if match is not None:
        return int(match.group(1))

    fallback = re.search(r"aggregate when .*?reach\s*\*\*(\d+)\*\*", text, re.IGNORECASE)
    if fallback is not None:
        return int(fallback.group(1))

    return _DEFAULT_AGGREGATION_TRIGGER


def _effective_date(fm: dict) -> date | None:
    """Return last_verified if present, else created, else None."""
    for key in ("last_verified", "created"):
        val = fm.get(key)
        if val:
            try:
                if isinstance(val, date):
                    return val
                return datetime.strptime(str(val), "%Y-%m-%d").date()
            except ValueError:
                pass
    return None


def _iter_live_access_files(root: Path) -> list[Path]:
    """Return tracked hot ACCESS.jsonl files, excluding archives and dot-dirs."""
    access_files: list[Path] = []
    for access_file in root.rglob("ACCESS.jsonl"):
        try:
            rel = access_file.relative_to(root)
        except ValueError:
            continue
        if rel.parts and rel.parts[0].startswith("."):
            continue
        if rel.parts and rel.parts[0] == "meta":
            continue
        if not _is_access_log_in_scope(PurePosixPath(rel.as_posix())):
            continue
        access_files.append(access_file)
    return sorted(access_files)


def _parse_access_entry(raw_line: str) -> dict[str, Any] | None:
    """Parse a JSONL ACCESS entry, returning None for blank or invalid lines."""
    raw_line = raw_line.strip()
    if not raw_line:
        return None
    try:
        parsed = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return cast(dict[str, Any], parsed)


def _parse_iso_date(raw_date: object) -> date | None:
    """Parse YYYY-MM-DD strings used in ACCESS.jsonl dates."""
    if raw_date is None:
        return None
    try:
        return datetime.strptime(str(raw_date), "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_git_log_path_filter(path_filter: str) -> str:
    """Validate and normalize an optional git-log path filter."""
    from ...errors import ValidationError

    normalized = path_filter.strip().replace("\\", "/")
    if not normalized:
        raise ValidationError("path_filter must be a non-empty repo-relative path or glob")
    if normalized.startswith(("/", "../")) or "/../" in normalized:
        raise ValidationError("path_filter must be a repo-relative path or glob")
    if re.match(r"^[A-Za-z]:[/\\]", normalized):
        raise ValidationError("path_filter must be a repo-relative path or glob")
    top_level, _, remainder = normalized.partition("/")
    category_prefixes = _resolve_category_prefixes(top_level)
    if category_prefixes and category_prefixes != (top_level,):
        primary_prefix = category_prefixes[0]
        normalized = f"{primary_prefix}/{remainder}" if remainder else primary_prefix
    return normalized


def _visible_top_level_category(path: str) -> str:
    normalized = path.replace("\\", "/").strip().lstrip("/")
    if normalized.startswith("core/"):
        normalized = normalized[len("core/") :]
    if normalized.startswith(("memory/knowledge/", "knowledge/")):
        return "knowledge"
    if normalized.startswith(("memory/working/projects/", "plans/")):
        return "plans"
    if normalized.startswith(("memory/users/", "identity/")):
        return "identity"
    if normalized.startswith(("memory/skills/", "skills/")):
        return "skills"
    if normalized.startswith("memory/activity/"):
        return "chats"
    if is_working_scratchpad_path(normalized):
        return "scratchpad"
    if normalized.startswith(("governance/", "meta/", "HUMANS/")):
        return "meta"
    if normalized.startswith(("tools/", "core/tools/")):
        return "tools"
    return normalized.split("/", 1)[0] if "/" in normalized else normalized or "other"


def _load_access_entries(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return parsed hot ACCESS entries and per-file counts for reporting."""
    entries: list[dict[str, Any]] = []
    counts: list[dict[str, Any]] = []

    for access_file in _iter_live_access_files(root):
        try:
            text = access_file.read_text(encoding="utf-8")
        except OSError:
            continue

        live_count = 0
        invalid_count = 0
        for raw_line in text.splitlines():
            if not raw_line.strip():
                continue
            entry = _parse_access_entry(raw_line)
            if entry is None:
                invalid_count += 1
                continue
            entry["_access_file"] = access_file.relative_to(root).as_posix()
            entries.append(entry)
            live_count += 1

        counts.append(
            {
                "access_file": access_file.relative_to(root).as_posix(),
                "folder": access_file.parent.relative_to(root).as_posix(),
                "entries": live_count,
                "invalid_lines": invalid_count,
            }
        )

    return entries, counts


def _iter_access_history_files(root: Path) -> list[Path]:
    access_files: list[Path] = []
    for access_file in root.rglob("*.jsonl"):
        try:
            rel = access_file.relative_to(root)
        except ValueError:
            continue
        if rel.parts and rel.parts[0].startswith("."):
            continue
        if rel.parts and rel.parts[0] == "meta":
            continue
        if not _is_access_log_in_scope(PurePosixPath(rel.as_posix())):
            continue
        if access_file.name == "ACCESS.jsonl" or re.match(
            r"ACCESS\.archive\.\d{4}-\d{2}\.jsonl$",
            access_file.name,
        ):
            access_files.append(access_file)
    return sorted(access_files)


def _load_access_history_entries(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for access_file in _iter_access_history_files(root):
        try:
            text = access_file.read_text(encoding="utf-8")
        except OSError:
            continue

        rel_access_file = access_file.relative_to(root).as_posix()
        for raw_line in text.splitlines():
            entry = _parse_access_entry(raw_line)
            if entry is None:
                continue
            entry["_access_file"] = rel_access_file
            entries.append(entry)
    return entries


def _access_user_matches(entry: dict[str, Any], resolved_user_id: str | None) -> bool:
    if resolved_user_id is None:
        return True
    return str(entry.get("user_id", "")).strip() == resolved_user_id


def _list_tracked_markdown_files(root: Path, scope: str) -> list[Path]:
    git_root = root if (root / ".git").exists() else root.parent
    cmd = ["git", "ls-files"]

    result = subprocess.run(
        cmd,
        cwd=str(git_root),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "git ls-files failed"
        raise RuntimeError(stderr)

    normalized_scope = scope.strip().replace("\\", "/")
    scope_path = _resolve_visible_path(root, normalized_scope or ".")
    tracked_files: list[Path] = []
    for raw_path in result.stdout.splitlines():
        git_rel_path = raw_path.strip().replace("\\", "/")
        if not git_rel_path.lower().endswith(".md"):
            continue
        visible_rel_path = git_rel_path
        if git_root != root and git_rel_path.startswith(f"{root.name}/"):
            visible_rel_path = git_rel_path[len(root.name) + 1 :]

        abs_path = _resolve_visible_path(root, visible_rel_path)
        if abs_path.exists() and abs_path.is_file():
            try:
                abs_path.relative_to(scope_path)
            except ValueError:
                continue
            tracked_files.append(abs_path)
    return sorted(set(tracked_files))


def _normalize_markdown_link_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if not target:
        return None
    if target.startswith("<"):
        closing = target.find(">")
        if closing != -1:
            target = target[1:closing].strip()
    else:
        target = target.split(maxsplit=1)[0].strip()

    if not target or target.startswith("#"):
        return None
    if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE):
        return None

    if "#" in target:
        target = target.split("#", 1)[0].strip()
    if not target:
        return None
    return target


def _iter_markdown_links(text: str) -> list[tuple[int, str]]:
    links: list[tuple[int, str]] = []
    for match in _MARKDOWN_LINK_RE.finditer(text):
        target = _normalize_markdown_link_target(match.group(1))
        if target is None:
            continue
        line_no = text.count("\n", 0, match.start()) + 1
        links.append((line_no, target))
    return links


def _resolve_repo_relative_target(
    root: Path, source_file: Path, target: str
) -> tuple[str | None, str | None]:
    resolved = (source_file.parent / target).resolve()
    try:
        rel_target = resolved.relative_to(root).as_posix()
    except ValueError:
        return None, "target escapes repository root"
    if not resolved.exists():
        return rel_target, "target not found"
    return rel_target, None


def _format_summary_folder_title(folder_name: str) -> str:
    return folder_name.replace("-", " ").replace("_", " ").strip().title() or "Repository"


def _extract_heading_and_paragraph(body: str, fallback_title: str) -> tuple[str, str]:
    lines = body.splitlines()
    heading = fallback_title
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            heading = stripped[2:].strip() or fallback_title
            break

    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        if not stripped:
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current).strip())

    description = paragraphs[0] if paragraphs else "Description pending review."
    return heading, description


def _normalize_heading_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _build_markdown_sections(body: str) -> list[dict[str, Any]]:
    lines = body.splitlines()
    headings: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        match = _MARKDOWN_HEADING_RE.match(line)
        if match is None:
            continue
        headings.append(
            {
                "level": len(match.group(1)),
                "title": match.group(2).strip(),
                "line": index + 1,
                "index": index,
            }
        )

    sections: list[dict[str, Any]] = []
    for position, heading in enumerate(headings):
        start_index = cast(int, heading["index"])
        end_index = len(lines)
        for next_heading in headings[position + 1 :]:
            if cast(int, next_heading["level"]) <= cast(int, heading["level"]):
                end_index = cast(int, next_heading["index"])
                break
        section_content = "\n".join(lines[start_index:end_index]).strip()
        sections.append(
            {
                "heading": heading["title"],
                "level": heading["level"],
                "start_line": heading["line"],
                "end_line": end_index,
                "anchor": re.sub(
                    r"[^a-z0-9]+", "-", _normalize_heading_key(cast(str, heading["title"]))
                ).strip("-"),
                "content": section_content,
            }
        )
    return sections


def _match_requested_sections(
    sections: list[dict[str, Any]], requested_headings: list[str]
) -> list[dict[str, Any]]:
    if not requested_headings:
        return sections

    normalized_requests = [_normalize_heading_key(item) for item in requested_headings]
    matched: list[dict[str, Any]] = []
    for section in sections:
        normalized_heading = _normalize_heading_key(cast(str, section["heading"]))
        if any(
            normalized_heading == request or normalized_heading.startswith(request)
            for request in normalized_requests
        ):
            matched.append(section)
    return matched


def _build_summary_metadata(fm_dict: dict[str, Any]) -> str:
    parts: list[str] = []
    trust = fm_dict.get("trust")
    if trust:
        parts.append(f"trust: {trust}")
    source = fm_dict.get("source")
    if source:
        parts.append(f"source: {source}")
    verified = fm_dict.get("last_verified") or fm_dict.get("created")
    if verified:
        parts.append(f"verified: {verified}")
    return "; ".join(parts)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _resolve_default_base_branch(root: Path, requested_base: str) -> str:
    candidate = requested_base.strip() or "core"
    bootstrap_path = root / "agent-bootstrap.toml"
    if not bootstrap_path.exists() or candidate != "core":
        return candidate

    try:
        parsed = tomllib.loads(bootstrap_path.read_text(encoding="utf-8"))
    except Exception:
        return candidate

    if not isinstance(parsed, dict):
        return candidate

    direct = parsed.get("default_branch")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    repository = parsed.get("repository")
    if isinstance(repository, dict):
        nested = repository.get("default_branch")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()

    return candidate


def _filter_access_entries(
    entries: list[dict[str, Any]],
    *,
    folder: str = "",
    file_prefix: str = "",
    start_date: str = "",
    end_date: str = "",
    user_id: str | None = None,
    min_helpfulness: float | None = None,
    max_helpfulness: float | None = None,
) -> list[dict[str, Any]]:
    """Filter ACCESS entries by folder, file prefix, date range, and helpfulness."""
    start = _parse_iso_date(start_date) if start_date else None
    end = _parse_iso_date(end_date) if end_date else None
    folder_prefixes = _normalize_access_folder_prefixes(folder) if folder else ()
    resolved_user_id = normalize_user_id(user_id)

    filtered: list[dict[str, Any]] = []
    for entry in entries:
        access_file = str(entry.get("_access_file", ""))
        file_path = str(entry.get("file", ""))

        if not _access_user_matches(entry, resolved_user_id):
            continue

        if folder_prefixes and not any(
            file_path == prefix
            or file_path.startswith(f"{prefix}/")
            or access_file == f"{prefix}/ACCESS.jsonl"
            or access_file.startswith(f"{prefix}/")
            for prefix in folder_prefixes
        ):
            continue
        if file_prefix and not file_path.startswith(file_prefix):
            continue

        entry_date = _parse_iso_date(entry.get("date"))
        if start is not None and (entry_date is None or entry_date < start):
            continue
        if end is not None and (entry_date is None or entry_date > end):
            continue

        raw_helpfulness = entry.get("helpfulness")
        if isinstance(raw_helpfulness, (int, float, str)):
            try:
                helpfulness = float(raw_helpfulness)
            except ValueError:
                helpfulness = None  # type: ignore[assignment]
        else:
            helpfulness = None  # type: ignore[assignment]

        if min_helpfulness is not None and (helpfulness is None or helpfulness < min_helpfulness):
            continue
        if max_helpfulness is not None and (helpfulness is None or helpfulness > max_helpfulness):
            continue

        filtered.append(entry)

    return filtered


def _summarize_access_by_file(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize ACCESS entries per file for aggregation reports."""
    per_file: dict[str, dict[str, Any]] = {}

    for entry in entries:
        file_path = str(entry.get("file", ""))
        if not file_path:
            continue
        bucket = per_file.setdefault(
            file_path,
            {
                "file": file_path,
                "folder": _content_folder_for_file(file_path),
                "entry_count": 0,
                "helpfulness_values": [],
                "session_ids": set(),
                "last_access_date": None,
                "source_access_logs": set(),
            },
        )
        bucket["entry_count"] += 1

        raw_helpfulness = entry.get("helpfulness")
        if isinstance(raw_helpfulness, (int, float, str)):
            try:
                bucket["helpfulness_values"].append(float(raw_helpfulness))
            except ValueError:
                pass

        session_id = entry.get("session_id")
        if session_id:
            bucket["session_ids"].add(str(session_id))

        access_file = entry.get("_access_file")
        if access_file:
            bucket["source_access_logs"].add(str(access_file))

        entry_date = _parse_iso_date(entry.get("date"))
        if entry_date is not None:
            last_access = bucket["last_access_date"]
            if last_access is None or entry_date > last_access:
                bucket["last_access_date"] = entry_date

    summaries: list[dict[str, Any]] = []
    for bucket in per_file.values():
        helpfulness_values = cast(list[float], bucket.pop("helpfulness_values"))
        session_ids = sorted(cast(set[str], bucket.pop("session_ids")))
        source_access_logs = sorted(cast(set[str], bucket.pop("source_access_logs")))
        last_access_date = cast(date | None, bucket["last_access_date"])
        mean_helpfulness = (
            round(sum(helpfulness_values) / len(helpfulness_values), 3)
            if helpfulness_values
            else None
        )
        summaries.append(
            {
                **bucket,
                "mean_helpfulness": mean_helpfulness,
                "session_count": len(session_ids),
                "session_ids": session_ids,
                "last_access_date": str(last_access_date) if last_access_date is not None else None,
                "source_access_logs": source_access_logs,
            }
        )

    summaries.sort(key=lambda item: (-int(item["entry_count"]), str(item["file"])))
    return summaries


def _detect_co_retrieval_clusters(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect same-session pairwise co-retrieval clusters."""
    session_files: dict[str, set[str]] = {}
    for entry in entries:
        session_id = entry.get("session_id")
        file_path = entry.get("file")
        if not session_id or not file_path:
            continue
        session_files.setdefault(str(session_id), set()).add(str(file_path))

    pair_counts: dict[tuple[str, str], set[str]] = {}
    for session_id, files in session_files.items():
        ordered_files = sorted(files)
        for idx, left in enumerate(ordered_files):
            for right in ordered_files[idx + 1 :]:
                pair_counts.setdefault((left, right), set()).add(session_id)

    clusters: list[dict[str, Any]] = []
    for (left, right), sessions in pair_counts.items():
        if len(sessions) < 3:
            continue
        folders = sorted(
            {
                folder
                for folder in (_content_folder_for_file(left), _content_folder_for_file(right))
                if folder
            }
        )
        clusters.append(
            {
                "files": [left, right],
                "folders": folders,
                "co_retrieval_count": len(sessions),
                "session_ids": sorted(sessions),
            }
        )

    clusters.sort(key=lambda item: (-int(item["co_retrieval_count"]), item["files"]))
    return clusters


def _parse_last_periodic_review(repo_root: Path) -> date | None:
    """Read the last periodic review date from the live router file."""
    qr_path = _resolve_live_router_path(repo_root)
    if not qr_path.exists():
        return None

    text = qr_path.read_text(encoding="utf-8")
    match = re.search(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", text)
    if match is None:
        return None
    return _parse_iso_date(match.group(1))


def _parse_periodic_review_window(repo_root: Path) -> int:
    """Read the periodic-review cadence from the live router file when present."""
    qr_path = _resolve_live_router_path(repo_root)
    if not qr_path.exists():
        return _PERIODIC_REVIEW_DAYS

    text = qr_path.read_text(encoding="utf-8")
    match = re.search(r"periodic review[^\n]*?(\d+)-day cadence", text, re.IGNORECASE)
    if match is None:
        match = re.search(r"(\d+)-day cadence", text, re.IGNORECASE)
    if match is None:
        return _PERIODIC_REVIEW_DAYS
    return int(match.group(1))


def _parse_current_stage(repo_root: Path) -> str:
    """Read the active maturity stage from the live router file."""
    qr_path = _resolve_live_router_path(repo_root)
    if not qr_path.exists():
        return "Exploration"

    text = qr_path.read_text(encoding="utf-8")
    match = re.search(r"## Current active stage:\s*([^\n]+)", text)
    if match is None:
        return "Exploration"

    stage = match.group(1).strip()
    if stage not in _STAGE_ORDER:
        return "Exploration"
    return stage


def _load_content_files(root: Path) -> set[str]:
    """Return repo-relative content files covered by maturity and review rules."""
    content_files: set[str] = set()
    for dirname in (
        "memory/knowledge",
        "memory/working/projects",
        "memory/users",
        "memory/skills",
        "knowledge",
        "plans",
        "identity",
        "skills",
    ):
        dir_path = root / dirname
        if not dir_path.is_dir():
            continue
        for md in dir_path.rglob("*.md"):
            try:
                content_files.add(md.relative_to(root).as_posix())
            except ValueError:
                continue
    return content_files


def _compute_maturity_signals(
    root: Path,
    repo: Any,
    all_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute the maturity signals used during periodic review."""
    import statistics

    from ...frontmatter_utils import read_with_frontmatter

    if all_entries is None:
        all_entries, _ = _load_access_entries(root)

    session_ids: set[str] = set()
    access_entries_with_session_id = 0
    write_session_ids: set[str] = set()
    access_density_by_task_id: dict[str, int] = {}
    proxy_session_keys: set[tuple[str, str]] = set()
    for entry in all_entries:
        sid = entry.get("session_id")
        if sid:
            sid_str = str(sid)
            session_ids.add(sid_str)
            access_entries_with_session_id += 1
            mode_value = entry.get("mode")
            if isinstance(mode_value, str) and mode_value in {"write", "update", "create"}:
                write_session_ids.add(sid_str)
        task_id_value = entry.get("task_id")
        task_bucket = str(task_id_value).strip() if task_id_value else "unspecified"
        access_density_by_task_id[task_bucket] = access_density_by_task_id.get(task_bucket, 0) + 1
        date_value = str(entry.get("date", "")).strip()
        proxy_task_value = (
            str(task_id_value).strip() if task_id_value else str(entry.get("task", "")).strip()
        )
        if date_value and proxy_task_value:
            proxy_session_keys.add((date_value, proxy_task_value))
    total_sessions = len(session_ids)
    write_sessions = len(write_session_ids)

    access_density = len(all_entries)
    session_id_coverage_pct = (
        round(100.0 * access_entries_with_session_id / access_density, 1) if access_density else 0.0
    )

    content_files = _load_content_files(root)
    total_content_files = len(content_files)

    accessed_files: set[str] = set()
    for entry in all_entries:
        file_path = entry.get("file")
        if file_path and file_path in content_files:
            accessed_files.add(str(file_path))
    files_accessed = len(accessed_files)
    file_coverage_pct = (
        round(100.0 * files_accessed / total_content_files, 1) if total_content_files else 0.0
    )

    high_trust_count = 0
    for rel_str in content_files:
        fp = root / rel_str
        try:
            fm, _ = read_with_frontmatter(fp)
        except Exception:
            continue
        if fm and fm.get("trust") == "high":
            high_trust_count += 1
    confirmation_ratio = (
        round(high_trust_count / total_content_files, 3) if total_content_files else 0.0
    )

    identity_stability: int | None = None
    try:
        proc = repo._run(
            [
                "git",
                "log",
                "-1",
                "--format=%ad",
                "--date=short",
                "--",
                "memory/users/profile.md",
            ],
            check=False,
        )
        last_change_str = proc.stdout.strip()
        if last_change_str:
            last_change = datetime.strptime(last_change_str, "%Y-%m-%d").date()
            session_dates: dict[str, date] = {}
            for entry in all_entries:
                sid = entry.get("session_id")
                date_str = entry.get("date")
                if not sid or not date_str:
                    continue
                try:
                    entry_date = datetime.strptime(str(date_str), "%Y-%m-%d").date()
                except ValueError:
                    continue
                sid_str = str(sid)
                if sid_str not in session_dates or entry_date < session_dates[sid_str]:
                    session_dates[sid_str] = entry_date
            identity_stability = sum(
                1 for entry_date in session_dates.values() if entry_date > last_change
            )
    except Exception:
        identity_stability = None

    helpfulness_values: list[float] = []
    for entry in all_entries:
        helpfulness = entry.get("helpfulness")
        if helpfulness is None:
            continue
        try:
            helpfulness_values.append(float(helpfulness))
        except (TypeError, ValueError):
            continue
    mean_helpfulness = round(statistics.mean(helpfulness_values), 3) if helpfulness_values else 0.0

    result = {
        "access_scope": "hot_only",
        "total_sessions": total_sessions,
        "session_id_coverage_pct": session_id_coverage_pct,
        "access_density": access_density,
        "file_coverage_pct": file_coverage_pct,
        "files_accessed": files_accessed,
        "total_content_files": total_content_files,
        "confirmation_ratio": confirmation_ratio,
        "high_trust_files": high_trust_count,
        "identity_stability": identity_stability,
        "write_sessions": write_sessions,
        "access_density_by_task_id": dict(sorted(access_density_by_task_id.items())),
        "mean_helpfulness": mean_helpfulness,
        "helpfulness_sample_size": len(helpfulness_values),
        "computed_at": str(date.today()),
    }
    if access_density and session_id_coverage_pct < 50.0:
        result["proxy_sessions"] = len(proxy_session_keys)
        result["proxy_session_note"] = (
            "session_id coverage below 50%; proxy_sessions estimates sessions using distinct "
            "(date, task_id or task) pairs."
        )
    return result


def _classify_signal_stage(metric: str, value: object) -> str | None:
    """Map a maturity signal value to its typical stage bucket."""
    if value is None:
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        numeric = float(value)
    except ValueError:
        return None
    if metric == "total_sessions":
        if numeric < 20:
            return "Exploration"
        if numeric <= 80:
            return "Calibration"
        return "Consolidation"
    if metric == "access_density":
        if numeric < 50:
            return "Exploration"
        if numeric <= 200:
            return "Calibration"
        return "Consolidation"
    if metric == "file_coverage_pct":
        if numeric < 30:
            return "Exploration"
        if numeric <= 60:
            return "Calibration"
        return "Consolidation"
    if metric == "confirmation_ratio":
        if numeric < 0.3:
            return "Exploration"
        if numeric <= 0.6:
            return "Calibration"
        return "Consolidation"
    if metric == "identity_stability":
        if numeric < 5:
            return "Exploration"
        if numeric <= 20:
            return "Calibration"
        return "Consolidation"
    if metric == "mean_helpfulness":
        if numeric < 0.5:
            return "Exploration"
        if numeric <= 0.75:
            return "Calibration"
        return "Consolidation"
    return None


def _assess_maturity_stage(signals: dict[str, Any], current_stage: str) -> dict[str, Any]:
    """Assess the recommended maturity stage from the six periodic-review signals."""
    metrics = (
        "total_sessions",
        "access_density",
        "file_coverage_pct",
        "confirmation_ratio",
        "identity_stability",
        "mean_helpfulness",
    )
    votes = {stage: 0 for stage in _STAGE_ORDER}
    signal_votes: dict[str, str] = {}
    for metric in metrics:
        stage = _classify_signal_stage(metric, signals.get(metric))
        if stage is None:
            continue
        votes[stage] += 1
        signal_votes[metric] = stage

    majority_stage: str | None = None
    for stage in reversed(_STAGE_ORDER):
        if votes[stage] >= 4:
            majority_stage = stage
            break

    recommended_stage = current_stage
    transition_recommended = False
    regression_flag = False
    rationale = "Retain current stage; no later-stage majority reached."

    current_index = _STAGE_ORDER.index(current_stage)
    if majority_stage is not None:
        majority_index = _STAGE_ORDER.index(majority_stage)
        if majority_index > current_index:
            recommended_stage = majority_stage
            transition_recommended = True
            rationale = f"Advance to {majority_stage}; {votes[majority_stage]} of 6 signals favor the later stage."
        elif majority_index < current_index:
            regression_flag = True
            rationale = f"{votes[majority_stage]} of 6 signals favor an earlier stage; flag for reassessment rather than auto-regressing."
        else:
            rationale = f"Retain {current_stage}; current stage still has majority support."

    return {
        "current_stage": current_stage,
        "recommended_stage": recommended_stage,
        "transition_recommended": transition_recommended,
        "regression_flag": regression_flag,
        "vote_counts": votes,
        "signal_votes": signal_votes,
        "rationale": rationale,
    }


def _parse_review_queue_entries(root: Path) -> list[dict[str, str]]:
    """Parse review-queue markdown entries into structured metadata."""
    queue_path = _resolve_governance_path(root, "review-queue.md")
    if not queue_path.exists():
        return []

    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_code_block = False
    for raw_line in queue_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        match = re.match(r"### \[(\d{4}-\d{2}-\d{2})\] (.+)", line)
        if match is not None:
            if current is not None:
                entries.append(current)
            current = {
                "date": match.group(1),
                "title": match.group(2),
            }
            continue
        if current is None:
            continue
        field_match = re.match(r"\*\*(.+?):\*\*\s*(.+)", line)
        if field_match is not None:
            key = field_match.group(1).strip().lower().replace(" ", "_")
            current[key] = field_match.group(2).strip()
    if current is not None:
        entries.append(current)
    return entries


def _find_conflict_tags(root: Path) -> list[str]:
    """Return files in memory/users or memory/knowledge that still contain [CONFLICT]."""
    matches: list[str] = []
    for dirname in (
        "memory/users",
        "memory/knowledge",
        "identity",
        "knowledge",
    ):
        dir_path = root / dirname
        if not dir_path.is_dir():
            continue
        for md_file in dir_path.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
            except OSError:
                continue
            if "[CONFLICT]" in text:
                matches.append(md_file.relative_to(root).as_posix())
    return sorted(matches)


def _scan_unverified_content(root: Path, low_threshold: int) -> dict[str, Any]:
    """Summarize low-trust files in knowledge/_unverified/ for periodic review."""
    from ...frontmatter_utils import read_with_frontmatter

    folder = _resolve_memory_subpath(root, "memory/knowledge/_unverified", "knowledge/_unverified")
    files: list[dict[str, Any]] = []
    overdue: list[dict[str, Any]] = []
    if not folder.is_dir():
        return {"files": files, "overdue": overdue}

    today = date.today()
    for md_file in folder.rglob("*.md"):
        if md_file.name == "SUMMARY.md":
            continue
        try:
            fm_dict, _ = read_with_frontmatter(md_file)
        except Exception:
            continue
        eff_date = _effective_date(fm_dict)
        age_days = (today - eff_date).days if eff_date is not None else None
        item = {
            "path": md_file.relative_to(root).as_posix(),
            "trust": fm_dict.get("trust") if fm_dict else None,
            "source": fm_dict.get("source") if fm_dict else None,
            "effective_date": str(eff_date) if eff_date is not None else None,
            "age_days": age_days,
        }
        files.append(item)
        if item["trust"] == "low" and age_days is not None and age_days > low_threshold:
            overdue.append(item)

    files.sort(key=lambda item: (-(item["age_days"] or -1), str(item["path"])))
    overdue.sort(key=lambda item: (-(item["age_days"] or -1), str(item["path"])))
    return {"files": files, "overdue": overdue}


def _collect_plan_entries(root: Path, status: str | None = None) -> list[dict[str, Any]]:
    from ...plan_utils import load_plan, next_action, plan_progress, plan_title

    entries: list[dict[str, Any]] = []

    plan_files: list[tuple[Path, str | None]] = []
    projects_root = _resolve_memory_subpath(root, "memory/working/projects", "projects")
    if projects_root.is_dir():
        for plan_file in sorted(projects_root.glob("*/plans/*.yaml")):
            if plan_file.is_file():
                plan_files.append((plan_file, plan_file.parents[1].name))

    for plan_file, project_id in plan_files:
        try:
            plan = load_plan(plan_file, root)
        except Exception:
            continue
        plan_status = plan.status
        if status is not None and plan_status != status:
            continue
        plan_done, plan_total = plan_progress(plan)
        normalized_project_id = plan.project if project_id is None else project_id
        next_action_info = _compact_plan_next_action(next_action(plan))
        entries.append(
            {
                "plan_id": plan.id,
                "project_id": normalized_project_id,
                "path": plan_file.relative_to(root).as_posix(),
                "title": plan_title(plan),
                "status": plan_status,
                "trust": "medium",
                "next_action": next_action_info,
                "resume_context": {
                    "tool": "memory_context_project",
                    "arguments": {"project": normalized_project_id},
                },
                "progress": {
                    "done": plan_done,
                    "total": plan_total,
                },
            }
        )

    entries.sort(
        key=lambda item: (
            0 if item["status"] == "active" else 1,
            cast(str, item.get("project_id") or ""),
            cast(str, item["plan_id"]),
        )
    )
    return entries


def _truncate_items(
    items: list[dict[str, Any]], limit: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized_limit = max(limit, 0)
    if len(items) <= normalized_limit:
        return items, {"returned": len(items), "total": len(items), "truncated": False}
    return items[:normalized_limit], {
        "returned": normalized_limit,
        "total": len(items),
        "truncated": True,
        "omitted": len(items) - normalized_limit,
    }


def _summarize_access_by_folder(file_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate file-level ACCESS summaries to top-level folder summaries."""
    folder_totals: dict[str, dict[str, Any]] = {}
    for item in file_summaries:
        folder = str(item.get("folder", ""))
        if not folder:
            continue
        bucket = folder_totals.setdefault(
            folder,
            {
                "folder": folder,
                "entry_count": 0,
                "files": 0,
                "high_value_files": 0,
                "low_value_files": 0,
            },
        )
        bucket["entry_count"] += int(item.get("entry_count", 0))
        bucket["files"] += 1
        mean_helpfulness = item.get("mean_helpfulness")
        if mean_helpfulness is not None and float(mean_helpfulness) >= 0.7:
            bucket["high_value_files"] += 1
        if mean_helpfulness is not None and float(mean_helpfulness) <= 0.3:
            bucket["low_value_files"] += 1

    summaries = list(folder_totals.values())
    summaries.sort(key=lambda item: (-int(item["entry_count"]), str(item["folder"])))
    return summaries


def _detect_access_anomalies(
    root: Path,
    entries: list[dict[str, Any]],
    staleness_days: int,
) -> list[dict[str, Any]]:
    """Detect read-only anomaly candidates for periodic review."""
    from ...frontmatter_utils import read_with_frontmatter

    by_file: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        file_path = str(entry.get("file", ""))
        if not file_path:
            continue
        by_file.setdefault(file_path, []).append(entry)

    anomalies: list[dict[str, Any]] = []
    for file_path, file_entries in by_file.items():
        try:
            fm_dict, _ = read_with_frontmatter(root / file_path)
        except Exception:
            fm_dict = {}

        if (
            len(file_entries) >= 5
            and not fm_dict.get("last_verified")
            and fm_dict.get("source") != "user-stated"
        ):
            anomalies.append(
                {
                    "type": "never_approved_high_retrieval",
                    "file": file_path,
                    "entry_count": len(file_entries),
                    "recommended_action": "Review provenance",
                }
            )

        dated_entries: list[tuple[date, str | None]] = []
        for entry in file_entries:
            entry_date = _parse_iso_date(entry.get("date"))
            if entry_date is None:
                continue
            session_id = str(entry.get("session_id")) if entry.get("session_id") else None
            dated_entries.append((entry_date, session_id))
        if not dated_entries:
            continue
        dated_entries.sort(key=lambda item: (item[0], item[1] or ""))
        latest_date = dated_entries[-1][0]
        window_start = latest_date.fromordinal(latest_date.toordinal() - staleness_days)
        recent_session_counts: dict[str, int] = {}
        prior_recent = 0
        for entry_date, session_id in dated_entries:
            if entry_date < window_start:
                continue
            if session_id is None:
                prior_recent += 1
                continue
            recent_session_counts[session_id] = recent_session_counts.get(session_id, 0) + 1
        if prior_recent == 0:
            for session_id, count in recent_session_counts.items():
                if count >= 3:
                    anomalies.append(
                        {
                            "type": "dormant_file_spike",
                            "file": file_path,
                            "session_id": session_id,
                            "entry_count": count,
                            "recommended_action": "Investigate access pattern",
                        }
                    )
                    break

    anomalies.sort(key=lambda item: (str(item["type"]), str(item["file"])))
    return anomalies


def _collect_recent_reflections(root: Path, limit: int = 5) -> list[dict[str, str]]:
    """Collect recent reflection files with a short preview line."""
    reflections: list[dict[str, str]] = []
    seen: set[str] = set()
    for pattern in ("memory/activity/**/reflection.md", "chats/**/reflection.md"):
        for reflection_path in sorted(root.glob(pattern), reverse=True):
            rel_path = reflection_path.relative_to(root).as_posix()
            if rel_path in seen:
                continue
            seen.add(rel_path)
            try:
                text = reflection_path.read_text(encoding="utf-8")
            except OSError:
                continue
            preview = ""
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                preview = stripped
                break
            reflections.append(
                {
                    "path": rel_path,
                    "preview": preview,
                }
            )
            if len(reflections) >= limit:
                return reflections
    return reflections


def _git_changed_files_since(repo: Any, since_date: date | None) -> list[str]:
    """Return repo-relative files touched since the given review date."""
    if since_date is None:
        return []
    try:
        proc = repo._run(
            ["git", "log", "--since", since_date.isoformat(), "--name-only", "--format="],
            check=False,
        )
    except Exception:
        return []

    files = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    return sorted(files)


def _build_access_summary_for_file(
    entries: list[dict[str, Any]],
    rel_path: str,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Return file-level ACCESS summary for a single repo-relative path."""
    resolved_user_id = normalize_user_id(user_id)
    summaries = _summarize_access_by_file(
        [
            entry
            for entry in entries
            if str(entry.get("file", "")) == rel_path
            and _access_user_matches(entry, resolved_user_id)
        ]
    )
    if summaries:
        return summaries[0]
    return {
        "file": rel_path,
        "folder": rel_path.split("/", 1)[0] if "/" in rel_path else rel_path,
        "entry_count": 0,
        "mean_helpfulness": None,
        "session_count": 0,
        "session_ids": [],
        "last_access_date": None,
        "source_access_logs": [],
    }


def _iter_frontmatter_health_files(root: Path, requested_path: str) -> list[str]:
    scope_path = _resolve_visible_path(root, requested_path or "memory/knowledge")
    if not scope_path.exists():
        return []
    if scope_path.is_file():
        try:
            return [scope_path.relative_to(root).as_posix()]
        except ValueError:
            return []

    files: list[str] = []
    for md_file in sorted(scope_path.rglob("*.md")):
        if md_file.name == "NAMES.md":
            continue
        try:
            files.append(md_file.relative_to(root).as_posix())
        except ValueError:
            continue
    return files


def _invalid_date_string(value: Any) -> bool:
    if value is None or isinstance(value, (date, datetime)):
        return False
    if not isinstance(value, str):
        return True
    candidate = value.strip()
    if not candidate:
        return True
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            datetime.strptime(candidate, fmt)
            return False
        except ValueError:
            continue
    return True


def _detect_malformed_frontmatter_close(text: str) -> int | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line_number, line in enumerate(lines[1:], start=2):
        stripped = line.strip()
        if stripped == "---":
            return None
        if line.startswith("---") and stripped != "---":
            return line_number
    return 1


def _frontmatter_health_report(root: Path, rel_path: str) -> dict[str, Any]:
    from ...frontmatter_utils import read_with_frontmatter

    abs_path = root / rel_path
    text = abs_path.read_text(encoding="utf-8")
    issues: list[dict[str, Any]] = []
    frontmatter: dict[str, Any] = {}
    body = text

    malformed_close_line = _detect_malformed_frontmatter_close(text)
    if malformed_close_line is not None:
        issues.append(
            {
                "kind": "malformed_frontmatter_close",
                "line": malformed_close_line,
                "message": "frontmatter close marker is missing or has trailing text",
            }
        )

    try:
        frontmatter, body = read_with_frontmatter(abs_path)
    except Exception as exc:
        issues.append(
            {
                "kind": "yaml_parse_error",
                "line": 1,
                "message": str(exc),
            }
        )
        return {
            "path": rel_path,
            "issue_count": len(issues),
            "issues": issues,
        }

    if malformed_close_line is not None and text.startswith("---"):
        issues.append(
            {
                "kind": "yaml_parse_error",
                "line": malformed_close_line,
                "message": "frontmatter block did not parse cleanly",
            }
        )
        return {
            "path": rel_path,
            "issue_count": len(issues),
            "issues": issues,
        }

    if rel_path.startswith("memory/knowledge/"):
        for field_name in ("source", "created", "trust"):
            if frontmatter.get(field_name) in (None, ""):
                issues.append(
                    {
                        "kind": "missing_required_field",
                        "field": field_name,
                        "message": f"missing required field: {field_name}",
                    }
                )

    for field_name in ("created", "last_verified", "expires"):
        if field_name in frontmatter and _invalid_date_string(frontmatter.get(field_name)):
            issues.append(
                {
                    "kind": "invalid_date",
                    "field": field_name,
                    "message": f"invalid date value for {field_name}",
                }
            )

    superseded_by = frontmatter.get("superseded_by")
    if superseded_by is not None:
        if not isinstance(superseded_by, str) or not superseded_by.strip():
            issues.append(
                {
                    "kind": "invalid_superseded_by",
                    "message": "superseded_by must be a non-empty repo-relative path",
                }
            )
        elif not (root / superseded_by).is_file():
            issues.append(
                {
                    "kind": "broken_superseded_by",
                    "field": "superseded_by",
                    "target": superseded_by,
                    "message": f"superseded_by target does not exist: {superseded_by}",
                }
            )

    h1_found = any(line.startswith("# ") for line in body.splitlines())
    if not h1_found:
        issues.append(
            {
                "kind": "missing_h1",
                "message": "body is missing a top-level H1 heading",
            }
        )

    related_value = frontmatter.get("related")
    if related_value is not None and not isinstance(related_value, list):
        issues.append(
            {
                "kind": "related_not_list",
                "message": "related should be a YAML list",
            }
        )

    related_entries: list[str] = []
    if isinstance(related_value, list):
        related_entries = [str(item).strip() for item in related_value]
    elif isinstance(related_value, str):
        related_entries = [item.strip() for item in related_value.split(",")]

    seen_related: set[str] = set()
    for index, item in enumerate(related_entries):
        if not item:
            issues.append(
                {
                    "kind": "related_empty_entry",
                    "index": index,
                    "message": "related contains an empty entry",
                }
            )
            continue
        if item in seen_related:
            issues.append(
                {
                    "kind": "related_duplicate_entry",
                    "index": index,
                    "value": item,
                    "message": "related contains a duplicate entry",
                }
            )
            continue
        seen_related.add(item)
        resolution = resolve_link_diagnostics(root, rel_path, item)
        if resolution["is_external"]:
            continue
        if resolution["reason"] is not None:
            issues.append(
                {
                    "kind": "unresolved_related_target",
                    "index": index,
                    "value": item,
                    "resolved_path": resolution["resolved_path"],
                    "message": str(resolution["reason"]),
                }
            )

    return {
        "path": rel_path,
        "issue_count": len(issues),
        "issues": issues,
    }


def _git_snapshot_graph(repo, scope: str, ref: str):
    from ...errors import ValidationError

    repo._run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"])
    git_scope = repo._to_git_path(scope)
    listing = repo._run(["git", "ls-tree", "-r", "--name-only", ref, "--", git_scope])

    with tempfile.TemporaryDirectory(prefix="agent-memory-graph-snapshot-") as tmpdir:
        snapshot_root = Path(tmpdir)
        for git_rel_path in listing.stdout.splitlines():
            git_rel_path = git_rel_path.strip()
            if not git_rel_path.lower().endswith(".md"):
                continue
            show_result = subprocess.run(
                ["git", "show", f"{ref}:{git_rel_path}"],
                cwd=str(repo.root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                check=False,
            )
            if show_result.returncode != 0:
                stderr = (show_result.stderr or "").strip()
                raise ValidationError(stderr or f"git show failed for {git_rel_path} at {ref}")
            content_rel = repo._from_git_path(git_rel_path)
            target = snapshot_root / content_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(show_result.stdout or "", encoding="utf-8")
        try:
            return build_connectivity_graph(snapshot_root, scope)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc


def _knowledge_domain_from_path(path: str) -> str:
    parts = PurePosixPath(path).parts
    return parts[2] if len(parts) > 2 and parts[0] == "memory" and parts[1] == "knowledge" else ""


def _filter_link_delta_payload(
    payload: dict[str, Any],
    *,
    cross_domain_only: bool,
    transition_filter: str,
) -> dict[str, Any]:
    filtered = dict(payload)

    if cross_domain_only:
        added_edges = [
            edge
            for edge in cast(list[dict[str, Any]], filtered.get("added_edges", []))
            if _knowledge_domain_from_path(str(edge.get("source", "")))
            != _knowledge_domain_from_path(str(edge.get("target", "")))
        ]
        removed_edges = [
            edge
            for edge in cast(list[dict[str, Any]], filtered.get("removed_edges", []))
            if _knowledge_domain_from_path(str(edge.get("source", "")))
            != _knowledge_domain_from_path(str(edge.get("target", "")))
        ]
        filtered["added_edges"] = added_edges
        filtered["removed_edges"] = removed_edges
        filtered["added_domain_pairs"] = [
            item
            for item in cast(list[dict[str, Any]], filtered.get("added_domain_pairs", []))
            if str(item.get("source_domain", "")) != str(item.get("target_domain", ""))
        ]
        filtered["removed_domain_pairs"] = [
            item
            for item in cast(list[dict[str, Any]], filtered.get("removed_domain_pairs", []))
            if str(item.get("source_domain", "")) != str(item.get("target_domain", ""))
        ]

        impacted_from_edges = sorted(
            {
                path
                for edge in added_edges + removed_edges
                for path in (str(edge.get("source", "")), str(edge.get("target", "")))
                if path
            }
        )
        filtered["impacted_files"] = impacted_from_edges
        filtered["impacted_files_detail"] = [
            item
            for item in cast(list[dict[str, Any]], filtered.get("impacted_files_detail", []))
            if str(item.get("path", "")) in impacted_from_edges
        ]

    if transition_filter:
        normalized = transition_filter.strip().lower()
        impacted_details = [
            item
            for item in cast(list[dict[str, Any]], filtered.get("impacted_files_detail", []))
            if f"{str(item.get('previous_category', '')).lower()}->{str(item.get('current_category', '')).lower()}"
            == normalized
        ]
        filtered["impacted_files_detail"] = impacted_details
        filtered["impacted_files"] = [str(item.get("path", "")) for item in impacted_details]
        raw_counts = cast(dict[str, Any], filtered.get("changed_category_counts", {}))
        filtered["changed_category_counts"] = {
            key: value for key, value in raw_counts.items() if str(key).lower() == normalized
        }
        impacted_paths = set(filtered["impacted_files"])
        filtered["added_edges"] = [
            edge
            for edge in cast(list[dict[str, Any]], filtered.get("added_edges", []))
            if str(edge.get("source", "")) in impacted_paths
            or str(edge.get("target", "")) in impacted_paths
        ]
        filtered["removed_edges"] = [
            edge
            for edge in cast(list[dict[str, Any]], filtered.get("removed_edges", []))
            if str(edge.get("source", "")) in impacted_paths
            or str(edge.get("target", "")) in impacted_paths
        ]

    return filtered


def _git_file_history(repo: Any, rel_path: str, limit: int = 10) -> list[dict[str, str]]:
    """Return recent commit history for a single file."""
    safe_limit = min(max(limit, 1), 20)
    git_rel_path = repo._to_git_path(rel_path) if hasattr(repo, "_to_git_path") else rel_path
    result = repo._run(
        [
            "git",
            "log",
            f"-{safe_limit}",
            "--follow",
            "--format=%H%x1f%s%x1f%aI%x1f%an%x1f%ae",
            "--",
            git_rel_path,
        ],
        check=False,
    )
    if result.returncode not in (0, 1):
        return []

    history: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) != 5:
            continue
        history.append(
            {
                "sha": parts[0].strip(),
                "message": parts[1].strip(),
                "author_date": parts[2].strip(),
                "author_name": parts[3].strip(),
                "author_email": parts[4].strip(),
            }
        )
    return history


def _commit_metadata(repo: Any, sha: str) -> dict[str, str | None]:
    """Return author/date metadata for a specific commit."""
    result = repo._run(
        ["git", "show", "--quiet", "--format=%aI%x1f%an%x1f%ae", sha],
        check=False,
    )
    if result.returncode != 0:
        return {
            "author_date": None,
            "author_name": None,
            "author_email": None,
        }

    parts = result.stdout.strip().split("\x1f")
    if len(parts) != 3:
        return {
            "author_date": None,
            "author_name": None,
            "author_email": None,
        }
    return {
        "author_date": parts[0].strip() or None,
        "author_name": parts[1].strip() or None,
        "author_email": parts[2].strip() or None,
    }


def _recognized_commit_prefix(message: str) -> str | None:
    """Return the bracketed commit prefix when it is in the allowed set."""
    match = re.match(r"^(\[[^\]]+\])", message)
    if match is None:
        return None
    prefix = match.group(1)
    if prefix not in KNOWN_COMMIT_PREFIXES:
        return None
    return prefix


def _requires_provenance_pause(path: str, frontmatter: dict[str, Any]) -> bool:
    """Apply the retrieval provenance pause rule to a file path."""
    top_level = path.split("/", 1)[0]
    if top_level in {"meta", "chats", "HUMANS"}:
        return False
    source = frontmatter.get("source")
    last_verified = frontmatter.get("last_verified")
    return not (source == "user-stated" or bool(last_verified))


def _extract_provenance_fields(frontmatter: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": frontmatter.get("source"),
        "origin_session": frontmatter.get("origin_session"),
        "origin_commit": frontmatter.get("origin_commit"),
        "produced_by": frontmatter.get("produced_by"),
        "verified_by": _coerce_path_list(frontmatter.get("verified_by")) or None,
        "inputs": _coerce_path_list(frontmatter.get("inputs")) or None,
        "related_sources": _coerce_path_list(
            frontmatter.get("related_sources") or frontmatter.get("related")
        )
        or None,
        "verified_against_commit": frontmatter.get("verified_against_commit"),
        "last_verified": frontmatter.get("last_verified"),
        "trust": frontmatter.get("trust"),
    }


def _build_lineage_summary(path: str, provenance: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if provenance.get("origin_commit"):
        notes.append(f"Origin commit recorded for {path}.")
    if provenance.get("produced_by"):
        notes.append(f"Produced by {provenance['produced_by']}.")
    if provenance.get("verified_by"):
        notes.append(
            f"Verified by {len(cast(list[str], provenance['verified_by']))} source reference(s)."
        )
    if provenance.get("inputs"):
        notes.append(f"Declares {len(cast(list[str], provenance['inputs']))} explicit input(s).")
    if provenance.get("related_sources"):
        notes.append(
            f"Carries {len(cast(list[str], provenance['related_sources']))} related source link(s)."
        )
    if provenance.get("verified_against_commit"):
        notes.append("Includes a verified-against commit marker.")
    if not notes:
        notes.append(
            "No optional lineage fields recorded; fall back to frontmatter, ACCESS history, and git history."
        )
    return notes


def _repo_relative(path: Path, root: Path) -> Path:
    """Return a path relative to the repo root."""
    return Path(_display_rel_path(path, root))


def _is_humans_path(path: Path, root: Path) -> bool:
    """Return True when a path is under HUMANS/."""
    try:
        relative = _repo_relative(path, root)
    except ValueError:
        return False
    return bool(relative.parts) and relative.parts[0] == _HUMANS_DIRNAME


def _resolve_host_repo(root: Path) -> Path | None:
    """Return the configured host repo root from agent-bootstrap.toml, if any."""
    bootstrap_path = None
    for candidate in (root / "agent-bootstrap.toml", root.parent / "agent-bootstrap.toml"):
        if candidate.exists():
            bootstrap_path = candidate
            break
    if bootstrap_path is None:
        return None

    match = re.search(
        r'^host_repo_root\s*=\s*"(?P<path>[^"]+)"',
        bootstrap_path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match is None:
        return None

    candidate = Path(match.group("path")).expanduser()
    if not candidate.is_absolute():
        candidate = (bootstrap_path.parent / candidate).resolve()
    return candidate.resolve()


def _get_git_repo_for_log(root: Path, repo, *, use_host_repo: bool):
    """Resolve the git repo to inspect for memory_git_log."""
    if not use_host_repo:
        return repo

    from ...errors import ValidationError
    from ...git_repo import GitRepo

    host_root = _resolve_host_repo(root)
    if host_root is None:
        raise ValidationError("host_repo_root is not configured in agent-bootstrap.toml")

    try:
        host_root.relative_to(root)
    except ValueError:
        pass
    else:
        raise ValidationError("host_repo_root must not point inside the memory worktree")

    try:
        return GitRepo(host_root)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


def _get_host_git_repo(root: Path, repo):
    """Return the configured host repo, if present."""
    if _resolve_host_repo(root) is None:
        return None
    return _get_git_repo_for_log(root, repo, use_host_repo=True)


def _split_csv_or_lines(raw: str) -> list[str]:
    items: list[str] = []
    for chunk in re.split(r"[,\n]", raw):
        value = chunk.strip()
        if value:
            items.append(value)
    return list(dict.fromkeys(items))


def _coerce_path_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_csv_or_lines(value)
    if isinstance(value, (list, tuple)):
        items: list[str] = []
        for entry in value:
            text = str(entry).strip()
            if text:
                items.append(text)
        return list(dict.fromkeys(items))
    text = str(value).strip()
    return [text] if text else []


def _resolve_requested_knowledge_paths(root: Path, raw_paths: str) -> list[tuple[str, Path]]:
    from ...errors import NotFoundError, ValidationError

    resolved: list[tuple[str, Path]] = []
    for requested in _split_csv_or_lines(raw_paths):
        rel_path = Path(requested)
        if rel_path.is_absolute():
            raise ValidationError(f"Knowledge path must be repo-relative: {requested}")

        abs_path = (root / rel_path).resolve()
        try:
            abs_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError(f"Knowledge path escapes repository root: {requested}") from exc

        rel = abs_path.relative_to(root).as_posix()
        if not rel.startswith("memory/knowledge/"):
            raise ValidationError(f"Knowledge path must live under memory/knowledge/: {requested}")
        if not abs_path.exists() or not abs_path.is_file():
            raise NotFoundError(f"File not found: {requested}")
        resolved.append((rel, abs_path))

    if not resolved:
        raise ValidationError("Provide at least one knowledge path")
    return list(dict.fromkeys(resolved))


def _resolve_host_source_path(host_repo, candidate: str) -> str | None:
    from ...errors import MemoryPermissionError, ValidationError

    raw_path = Path(candidate)
    if raw_path.is_absolute():
        abs_path = raw_path.resolve()
        try:
            abs_path.relative_to(host_repo.root)
        except ValueError as exc:
            raise ValidationError(f"Host source path escapes repository root: {candidate}") from exc
    else:
        try:
            abs_path = host_repo.abs_path(candidate)
        except MemoryPermissionError as exc:
            raise ValidationError(str(exc)) from exc

    if not abs_path.exists() or not abs_path.is_file():
        return None
    return abs_path.relative_to(host_repo.root).as_posix()


def _infer_host_source_files(rel_path: str, host_repo) -> list[str]:
    parts = Path(rel_path).parts
    if len(parts) < 3 or parts[0] != "knowledge" or parts[1] != "codebase":
        return []

    candidate = Path(*parts[2:])
    candidates: list[Path] = [candidate]
    if candidate.suffix == ".md":
        candidates.append(candidate.with_suffix(""))

    inferred: list[str] = []
    for item in candidates:
        if not item.parts:
            continue
        resolved = _resolve_host_source_path(host_repo, item.as_posix())
        if resolved is not None:
            inferred.append(resolved)
    return list(dict.fromkeys(inferred))


def _suggest_freshness_action(
    *,
    status: str,
    trust: str | None,
    host_changes_since: int | None,
    verified_against_commit: str | None,
    current_head: str | None,
) -> str:
    if status == "unknown":
        return "none"
    if status == "fresh":
        if trust == "low" and verified_against_commit and current_head == verified_against_commit:
            return "promote"
        return "none"
    if trust == "high" and (host_changes_since or 0) >= 20:
        return "downgrade_trust"
    return "reverify"


def _build_knowledge_freshness_report(
    root: Path, repo, rel_path: str, abs_path: Path
) -> dict[str, object]:
    from ...frontmatter_utils import read_with_frontmatter

    fm_dict, _ = read_with_frontmatter(abs_path)
    trust_value = fm_dict.get("trust")
    trust = str(trust_value) if trust_value else None
    verified_value = fm_dict.get("verified_against_commit")
    verified_against_commit = str(verified_value) if verified_value else None
    last_verified_date = _effective_date(fm_dict)
    host_repo = _get_host_git_repo(root, repo)
    source_files: list[str] = []
    current_head: str | None = None
    host_changes_since: int | None = None
    status = "unknown"

    if host_repo is not None:
        current_head = host_repo.current_head()
        explicit_sources = _coerce_path_list(fm_dict.get("related"))
        for candidate in explicit_sources:
            resolved = _resolve_host_source_path(host_repo, candidate)
            if resolved is not None:
                source_files.append(resolved)
        if not source_files:
            source_files.extend(_infer_host_source_files(rel_path, host_repo))
        source_files = list(dict.fromkeys(source_files))

        if source_files and last_verified_date is not None:
            host_changes_since = host_repo.commit_count_since(
                f"{last_verified_date} 23:59:59",
                paths=source_files,
            )
            status = "fresh" if host_changes_since == 0 else "stale"
        elif verified_against_commit and current_head:
            status = "fresh" if verified_against_commit == current_head else "stale"

    payload: dict[str, object] = {
        "path": rel_path,
        "trust": trust,
        "last_verified": str(last_verified_date) if last_verified_date is not None else None,
        "verified_against_commit": verified_against_commit,
        "current_head": current_head,
        "source_files": source_files,
        "host_changes_since": host_changes_since,
        "status": status,
    }
    payload["suggested_action"] = _suggest_freshness_action(
        status=status,
        trust=trust,
        host_changes_since=host_changes_since,
        verified_against_commit=verified_against_commit,
        current_head=current_head,
    )
    return payload
