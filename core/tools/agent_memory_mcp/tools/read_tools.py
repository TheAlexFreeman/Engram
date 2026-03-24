"""
Tier 0 — Enhanced read tools.

These extend the existing read-only tool set with:
  - memory_read_file   : returns version_token + parsed frontmatter
  - memory_list_folder : unchanged from existing (re-implemented here)
    - memory_search      : unchanged from existing (re-implemented here)
        - memory_find_references: structured path/reference discovery across governed markdown
    - memory_route_intent: recommend the best governed operation for an intent
    - memory_get_policy_state: compile the live policy contract for an operation/path
    - memory_get_tool_profiles: report tool-profile metadata for host-side narrowing
    - memory_git_log     : recent commit history
    - memory_session_health_check : session-start maintenance status
    - memory_session_bootstrap : compact returning-session bundle
    - memory_prepare_unverified_review : compact unverified-review bundle
    - memory_prepare_promotion_batch : compact promotion-prep bundle
    - memory_prepare_periodic_review : compact periodic-review prep bundle
    - memory_check_knowledge_freshness : host-repo freshness for knowledge files
    - memory_diff        : working tree status
    - memory_audit_trust : trust decay audit
    - memory_check_aggregation_triggers : ACCESS.jsonl trigger status

Resources and prompts are also registered here for stable read/navigation state
and recurring workflow scaffolds.

All tools are registered onto the FastMCP instance passed in via register().
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
from importlib import import_module
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, cast

from ..path_policy import KNOWN_COMMIT_PREFIXES  # noqa: F401 — re-exported for callers
from .reference_extractor import (
    find_references,
    find_unlinked_files,
    preview_reorganization,
    suggest_structure,
    validate_links,
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
_READ_FILE_INLINE_THRESHOLD_BYTES = 20_000

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


def _build_capabilities_summary(manifest: dict[str, Any]) -> dict[str, Any]:
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

    return {
        "total_tools": len(
            {
                *[tool for tool in read_tools if isinstance(tool, str)],
                *[tool for tool in raw_tools if isinstance(tool, str)],
                *[tool for tool in semantic_tools if isinstance(tool, str)],
            }
        ),
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
    }


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
        )
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


def _route_intent_candidates(intent: str, rel_path: str | None, root: Path) -> list[dict[str, Any]]:
    intent_lower = intent.lower()
    normalized_path = _normalize_repo_relative_path(rel_path) if rel_path else None
    abs_path = (root / normalized_path) if normalized_path else None
    path_is_dir = bool(abs_path and abs_path.exists() and abs_path.is_dir())
    plural_signal = any(word in intent_lower for word in ("batch", "multiple", "many", "several"))
    nested_signal = any(word in intent_lower for word in ("subtree", "tree", "recursive", "nested"))

    candidates: list[dict[str, Any]] = []

    def add(operation: str, score: float, reason: str) -> None:
        candidates.append({"operation": operation, "score": score, "reason": reason})

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
    from ..frontmatter_utils import read_with_frontmatter

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
    from ..errors import ValidationError

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
    if normalized.startswith("memory/working/scratchpad/"):
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
    min_helpfulness: float | None = None,
    max_helpfulness: float | None = None,
) -> list[dict[str, Any]]:
    """Filter ACCESS entries by folder, file prefix, date range, and helpfulness."""
    start = _parse_iso_date(start_date) if start_date else None
    end = _parse_iso_date(end_date) if end_date else None
    folder_prefixes = _normalize_access_folder_prefixes(folder) if folder else ()

    filtered: list[dict[str, Any]] = []
    for entry in entries:
        access_file = str(entry.get("_access_file", ""))
        file_path = str(entry.get("file", ""))

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

    from ..frontmatter_utils import read_with_frontmatter

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
    from ..frontmatter_utils import read_with_frontmatter

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
    from ..plan_utils import load_plan, next_action, plan_progress, plan_title

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
        entries.append(
            {
                "plan_id": plan.id,
                "project_id": plan.project if project_id is None else project_id,
                "path": plan_file.relative_to(root).as_posix(),
                "title": plan_title(plan),
                "status": plan_status,
                "trust": "medium",
                "next_action": next_action(plan) or "",
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
    from ..frontmatter_utils import read_with_frontmatter

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
) -> dict[str, Any]:
    """Return file-level ACCESS summary for a single repo-relative path."""
    summaries = _summarize_access_by_file(
        [entry for entry in entries if str(entry.get("file", "")) == rel_path]
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

    from ..errors import ValidationError
    from ..git_repo import GitRepo

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
    from ..errors import NotFoundError, ValidationError

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
    from ..errors import MemoryPermissionError, ValidationError

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
    from ..frontmatter_utils import read_with_frontmatter

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


def register(mcp: "FastMCP", get_repo, get_root) -> dict[str, object]:
    """Register all Tier 0 read tools and return their callables."""

    # ------------------------------------------------------------------
    # memory_get_capabilities
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_get_capabilities",
        annotations=_tool_annotations(
            title="Get Capability Manifest",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_get_capabilities() -> str:
        """Return the governed capability manifest as structured JSON.

        This tool is intentionally self-referential: it is listed in the same
        `read_support` manifest entry that it reads. When the manifest cannot
        be read or parsed, it returns a structured error payload so callers can
        fall back to manual inspection.
        """
        root = get_root()
        manifest, error_payload = _load_capabilities_manifest(root)
        if error_payload is not None:
            return json.dumps(error_payload, indent=2)

        payload = dict(cast(dict[str, Any], manifest))
        payload["summary"] = _build_capabilities_summary(payload)
        return json.dumps(payload, indent=2, default=str)

    # ------------------------------------------------------------------
    # memory_get_tool_profiles
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_get_tool_profiles",
        annotations=_tool_annotations(
            title="Get Tool Profiles",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_get_tool_profiles() -> str:
        """Return advisory tool-profile metadata for host-side narrowing.

        Profiles are declarative metadata only. The current runtime exports a
        static tool surface, so hosts should treat these profiles as discovery
        hints rather than dynamic switching commands.
        """
        root = get_root()
        manifest, error_payload = _load_capabilities_manifest(root)
        if error_payload is not None:
            return json.dumps(error_payload, indent=2)

        payload = _build_tool_profile_payload(cast(dict[str, Any], manifest))
        return json.dumps(payload, indent=2, default=str)

    # ------------------------------------------------------------------
    # memory_get_policy_state
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_get_policy_state",
        annotations=_tool_annotations(
            title="Get Governed Policy State",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_get_policy_state(operation: str = "", path: str = "") -> str:
        """Compile the current governed contract for an operation and optional path.

        Use this when a caller needs the live change class, approval level,
        preview expectation, fallback behavior, and path-level governance status
        without reconstructing the rules from the capability manifest and
        governance docs manually.

        operation: Desktop operation key (for example `create_plan`) or tool
                   name (for example `memory_plan_create`).
        path:      Optional repo-relative target path whose governance surface
                   should be evaluated alongside the operation.
        """
        from ..errors import ValidationError

        root = get_root()
        manifest, error_payload = _load_capabilities_manifest(root)
        if error_payload is not None:
            return json.dumps(error_payload, indent=2)

        try:
            normalized_path = _normalize_repo_relative_path(path) if path.strip() else None
        except ValueError as exc:
            raise ValidationError(str(exc))

        payload = _build_policy_state_payload(
            root,
            cast(dict[str, Any], manifest),
            operation.strip() or None,
            normalized_path,
        )
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_route_intent
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_route_intent",
        annotations=_tool_annotations(
            title="Route Governed Intent",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_route_intent(intent: str, path: str = "") -> str:
        """Recommend the best governed operation for a natural-language intent.

        Use this when a caller knows the task goal but does not know which
        semantic tool or governed operation is the right fit. Returns the best
        match, likely alternatives, and the compiled policy state for the
        recommended path.
        """
        from ..errors import ValidationError

        if not intent.strip():
            raise ValidationError("intent must be a non-empty string")

        root = get_root()
        manifest, error_payload = _load_capabilities_manifest(root)
        if error_payload is not None:
            return json.dumps(error_payload, indent=2)

        try:
            normalized_path = _normalize_repo_relative_path(path) if path.strip() else None
        except ValueError as exc:
            raise ValidationError(str(exc))

        manifest_dict = cast(dict[str, Any], manifest)
        candidates = _route_intent_candidates(intent, normalized_path, root)
        ambiguous = False
        recommended: dict[str, Any] | None = None
        alternatives: list[dict[str, Any]] = []
        if candidates:
            recommended = candidates[0]
            alternatives = candidates[1:4]
            ambiguous = bool(
                alternatives
                and abs(cast(float, recommended["score"]) - cast(float, alternatives[0]["score"]))
                < 0.03
            )
        else:
            ambiguous = True

        policy_state = _build_policy_state_payload(
            root,
            manifest_dict,
            cast(str | None, recommended["operation"]) if recommended is not None else None,
            normalized_path,
        )
        workflow_hint = _route_workflow_hint(
            cast(str | None, recommended["operation"]) if recommended is not None else None,
            normalized_path,
            root,
        )
        if recommended is None:
            policy_state["warnings"] = list(policy_state.get("warnings", [])) + [
                "No confident governed operation match was found for this intent."
            ]

        return json.dumps(
            {
                "intent": intent,
                "path": normalized_path,
                "recommended_operation": recommended,
                "alternatives": alternatives,
                "ambiguous": ambiguous,
                "workflow_hint": workflow_hint,
                "policy_state": policy_state,
            },
            indent=2,
        )

    # ------------------------------------------------------------------
    # memory_read_file
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_read_file",
        annotations=_tool_annotations(
            title="Read Memory File",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_read_file(path: str) -> str:
        """Read a file from the memory repository.

        Returns file metadata, parsed frontmatter, and either inline content for
        files up to 20,000 bytes or a temporary file path for larger payloads.
        Always includes a version_token (git object hash) for optimistic locking.

        Args:
            path: Repo-relative content path (e.g. 'memory/users/profile.md',
                'memory/knowledge/_unverified/django/celery-canvas.md').

        Returns:
            JSON with keys:
              path         (str)       Repo-relative path requested
              size_bytes   (int)       UTF-8 byte size of the file content
              inline       (bool)      True when content is returned inline;
                                       false when content is written to temp_file
              content      (str)       Full file text when inline is true
              temp_file    (str)       Temporary file containing full text when
                                       inline is false
              version_token (str)      Git SHA-1 of the file; pass back to write
                                       tools to detect concurrent modifications
              frontmatter  (dict|null) Parsed YAML frontmatter, or null
        """
        from ..errors import NotFoundError
        from ..frontmatter_utils import read_with_frontmatter

        root = get_root()
        repo = get_repo()
        abs_path = _resolve_visible_path(root, path)
        if not abs_path.exists():
            raise NotFoundError(f"File not found: {path}")

        display_path = _display_rel_path(abs_path, root)

        fm_dict, body = read_with_frontmatter(abs_path)
        try:
            abs_path.relative_to(root)
        except ValueError:
            version_token = repo._run(["git", "hash-object", str(abs_path)]).stdout.strip()
        else:
            version_token = repo.hash_object(display_path)
        content = abs_path.read_text(encoding="utf-8")
        size_bytes = len(content.encode("utf-8"))

        result = {
            "path": display_path,
            "size_bytes": size_bytes,
            "inline": size_bytes <= _READ_FILE_INLINE_THRESHOLD_BYTES,
            "version_token": version_token,
            "frontmatter": fm_dict or None,
        }
        if result["inline"]:
            result["content"] = content
        else:
            suffix = abs_path.suffix or ".txt"
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=suffix,
                prefix="agent-memory-read-",
                delete=False,
            ) as handle:
                handle.write(content)
                temp_path = handle.name
            result["temp_file"] = temp_path
        return json.dumps(result, indent=2, default=str)

    # ------------------------------------------------------------------
    # memory_list_folder
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_list_folder",
        annotations=_tool_annotations(
            title="List Memory Folder",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_list_folder(
        path: str = ".",
        include_hidden: bool = False,
        include_humans: bool = False,
        preview_chars: int = 0,
    ) -> str:
        """List the contents of a folder in the memory repository.

        Args:
            path:           Repo-relative folder path (default: repo root '.').
            include_hidden: Include dot-files/folders (default: False).
            include_humans: Include the human-facing HUMANS/ tree when browsing
                            broad scopes like '.' (default: False).
            preview_chars:  When > 0, return structured JSON including markdown
                            frontmatter and a truncated body preview.

        Returns:
            Markdown-formatted directory listing with file sizes when
            preview_chars == 0; otherwise structured JSON entry metadata.
        """
        root = get_root()
        folder = _resolve_visible_path(root, path)
        if not folder.exists():
            return f"Error: Folder not found: {path}"
        if not folder.is_dir():
            return f"Error: Not a directory: {path}"

        explicit_humans_request = _is_humans_path(folder, root)
        lines = [f"# {path}/\n"]
        try:
            all_entries = list(folder.iterdir())
        except PermissionError:
            return f"Error: Permission denied reading {path}"

        if not explicit_humans_request and include_humans and path in {"", "."}:
            humans_root = _resolve_humans_root(root)
            if humans_root.exists() and humans_root.is_dir():
                all_entries.append(humans_root)

        def _keep(entry: Path) -> bool:
            if entry.name in _IGNORED_NAMES:
                return False
            if not include_hidden and entry.name.startswith("."):
                return False
            if not explicit_humans_request and not include_humans and _is_humans_path(entry, root):
                return False
            return True

        entries = sorted(
            [entry for entry in all_entries if _keep(entry)],
            key=lambda p: (p.is_file(), p.name),
        )

        if preview_chars > 0:
            payload_entries: list[dict[str, Any]] = []
            for entry in entries:
                rel = _display_rel_path(entry, root)
                if entry.is_dir():
                    payload_entries.append(
                        {
                            "name": entry.name,
                            "path": rel,
                            "kind": "directory",
                        }
                    )
                else:
                    payload_entries.append(_preview_file_entry(entry, root, preview_chars))

            return json.dumps(
                {
                    "path": path,
                    "preview_chars": preview_chars,
                    "entries": payload_entries,
                },
                indent=2,
                default=str,
            )

        for entry in entries:
            rel = _display_rel_path(entry, root)
            if entry.is_dir():
                lines.append(f"📁 {rel}/")
            else:
                size = entry.stat().st_size
                lines.append(f"📄 {entry.name}  ({size:,} bytes)  `{rel}`")

        if len(lines) == 1:
            lines.append("_(empty)_")
        return "\n".join(lines)

    @mcp.tool(
        name="memory_review_unverified",
        annotations=_tool_annotations(
            title="Review Unverified Knowledge",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_review_unverified(
        folder_path: str = "memory/knowledge/_unverified",
        max_extract_words: int = 150,
        include_expired: bool = True,
    ) -> str:
        """Return a grouped digest of unverified knowledge files.

        Each file entry includes provenance metadata, age, expiry status, and a
        truncated body extract to support review workflows without per-file reads.
        """
        from ..errors import ValidationError
        from ..frontmatter_utils import read_with_frontmatter

        if max_extract_words < 0:
            raise ValidationError("max_extract_words must be >= 0")

        root = get_root()
        folder = _resolve_memory_subpath(root, folder_path, "knowledge/_unverified")
        if not folder.exists():
            return json.dumps(
                {
                    "folder_path": folder_path,
                    "max_extract_words": max_extract_words,
                    "include_expired": include_expired,
                    "total_files": 0,
                    "expired_count": 0,
                    "trust_counts": {"low": 0, "medium": 0, "high": 0, "unknown": 0},
                    "groups": {},
                },
                indent=2,
                default=str,
            )
        if not folder.is_dir():
            raise ValidationError(f"Not a directory: {folder_path}")

        low_threshold, medium_threshold = _parse_trust_thresholds(root)
        today = date.today()
        grouped: dict[str, list[dict[str, Any]]] = {}
        trust_counts = {"low": 0, "medium": 0, "high": 0, "unknown": 0}
        total_files = 0
        expired_count = 0

        for md_file in sorted(folder.rglob("*.md")):
            if not md_file.is_file() or md_file.name == "SUMMARY.md":
                continue

            rel_path = md_file.relative_to(root).as_posix()
            group_key = md_file.parent.relative_to(folder).as_posix()
            if group_key == ".":
                group_key = ""

            frontmatter, body = read_with_frontmatter(md_file)
            effective_date = _effective_date(frontmatter)
            days_old = (today - effective_date).days if effective_date is not None else None
            trust_value = frontmatter.get("trust")
            trust = str(trust_value) if trust_value is not None else None
            threshold = _review_expiry_threshold_days(trust, low_threshold, medium_threshold)
            expired = days_old is not None and threshold is not None and days_old > threshold

            if not include_expired and expired:
                continue

            total_files += 1
            if trust in trust_counts:
                trust_counts[cast(str, trust)] += 1
            else:
                trust_counts["unknown"] += 1
            if expired:
                expired_count += 1

            grouped.setdefault(group_key, []).append(
                {
                    "path": rel_path,
                    "created": str(frontmatter.get("created"))
                    if frontmatter.get("created") is not None
                    else None,
                    "source": frontmatter.get("source"),
                    "trust": trust,
                    "days_old": days_old,
                    "expired": expired,
                    "extract": _extract_preview_words(body, max_extract_words),
                }
            )

        return json.dumps(
            {
                "folder_path": folder_path,
                "max_extract_words": max_extract_words,
                "include_expired": include_expired,
                "total_files": total_files,
                "expired_count": expired_count,
                "trust_counts": trust_counts,
                "groups": grouped,
            },
            indent=2,
            default=str,
        )

    # ------------------------------------------------------------------
    # memory_search
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_search",
        annotations=_tool_annotations(
            title="Search Memory Files",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_search(
        query: str,
        path: str = ".",
        glob_pattern: str = "**/*.md",
        case_sensitive: bool = False,
        max_results: int = 30,
        context_lines: int = 0,
        include_humans: bool = False,
    ) -> str:
        """Search for a pattern across files in the memory repository.

        Uses git grep for tracked files (fast — git maintains an index), then
        falls back to a Python glob walk for any untracked files. Results are
        grouped by file with line numbers. When context_lines > 0, includes up
        to that many surrounding lines before and after each match. Context
        lines do not count toward max_results.

        Args:
            query:          Search string or Python regex (POSIX ERE via git grep).
            path:           Folder to search within (default: '.').
            glob_pattern:   File glob filter (default: '**/*.md').
            case_sensitive: Case-sensitive match (default: False).
            max_results:    Max matching lines to return (default: 30, max 100).
            context_lines:  Number of surrounding lines to include before and
                            after each match (default: 0, max: 10).
            include_humans: Include the human-facing HUMANS/ tree when searching
                            broad scopes like '.' (default: False).

        Returns:
            Matching lines grouped by file with line numbers, or a not-found message.
        """
        from ..errors import StagingError, ValidationError

        root = get_root()
        search_root = _resolve_visible_path(root, path)
        if not search_root.exists():
            return f"Error: Path not found: {path}"

        if context_lines < 0:
            raise ValidationError("context_lines must be >= 0")
        if context_lines > 10:
            raise ValidationError("context_lines must be <= 10")

        # Validate regex early so we can report a helpful error before spawning git
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            python_pattern = re.compile(query, flags)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"

        max_results = min(max_results, 100)
        explicit_humans_search = _is_humans_path(search_root, root)

        # Build the git-grep path prefix (repo-relative) so git restricts the search scope
        try:
            scope_prefix = search_root.relative_to(root).as_posix()
        except ValueError:
            scope_prefix = "."

        # Derive a simple glob extension for git grep from glob_pattern
        # e.g. "**/*.md" → "*.md"; "*.txt" → "*.txt"
        simple_glob = glob_pattern.lstrip("*/")  # strip leading **/ or */
        if not simple_glob:
            simple_glob = "*"

        # Build the path spec for git grep
        if scope_prefix in (".", ""):
            git_pathspec = simple_glob
        else:
            git_pathspec = f"{scope_prefix}/{simple_glob}"

        # Try git grep first (fast path for tracked files)
        repo = get_repo()
        if explicit_humans_search:
            raw_matches = None
        else:
            try:
                raw_matches = repo.grep(
                    query,
                    glob=git_pathspec,
                    case_sensitive=case_sensitive,
                )
            except StagingError:
                # git grep unavailable or failed — fall through to Python fallback
                raw_matches = None

        # Build per-file match groups from git grep output
        results: list[str] = []
        total_matches = 0
        seen_files: set[str] = set()
        file_line_cache: dict[str, list[str]] = {}

        def _get_file_lines(file_rel: str, *, untracked_text: str | None = None) -> list[str]:
            if file_rel not in file_line_cache:
                if untracked_text is not None:
                    file_line_cache[file_rel] = untracked_text.splitlines()
                else:
                    try:
                        file_line_cache[file_rel] = (
                            (root / file_rel)
                            .read_text(encoding="utf-8", errors="replace")
                            .splitlines()
                        )
                    except OSError:
                        file_line_cache[file_rel] = []
            return file_line_cache[file_rel]

        def _append_match_lines(
            file_output: list[str],
            *,
            file_rel: str,
            line_no: int,
            line_text: str,
            untracked_text: str | None = None,
        ) -> None:
            cached_lines = _get_file_lines(file_rel, untracked_text=untracked_text)
            if not cached_lines:
                file_output.append(f"  {line_no}: {line_text.rstrip()}")
                return

            start_index = max(0, line_no - 1 - context_lines)
            end_index = min(len(cached_lines), line_no + context_lines)
            for current_index in range(start_index, end_index):
                rendered_line = cached_lines[current_index].rstrip()
                rendered_no = current_index + 1
                if rendered_no == line_no:
                    file_output.append(f"  {rendered_no}: {rendered_line}")
                else:
                    file_output.append(f"  {rendered_no}| {rendered_line}")

        if raw_matches is not None:
            # Group matches by file
            from itertools import groupby

            for file_rel, file_matches_iter in groupby(raw_matches, key=lambda t: t[0]):
                grouped_matches = list(file_matches_iter)
                file_path = root / file_rel

                # Apply HUMANS/ filter
                if (
                    not explicit_humans_search
                    and not include_humans
                    and _is_humans_path(file_path, root)
                ):
                    continue

                # Apply _IGNORED_NAMES filter
                if any(part in _IGNORED_NAMES for part in file_path.parts):
                    continue

                seen_files.add(file_rel)
                file_output: list[str] = []
                for _, line_no, line_text in grouped_matches:
                    _append_match_lines(
                        file_output,
                        file_rel=file_rel,
                        line_no=line_no,
                        line_text=line_text,
                    )
                    total_matches += 1
                    if total_matches >= max_results:
                        break

                if file_output:
                    results.append(f"\n**{file_rel}**")
                    results.extend(file_output)

                if total_matches >= max_results:
                    results.append(
                        f"\n_(truncated at {max_results} matches — use a narrower query or path)_"
                    )
                    break

        # Python fallback: search untracked files git grep wouldn't see
        if total_matches < max_results:
            for file_path in sorted(search_root.glob(glob_pattern)):
                if any(part in _IGNORED_NAMES for part in file_path.parts):
                    continue
                if not file_path.is_file():
                    continue
                try:
                    file_rel = _display_rel_path(file_path, root)
                except ValueError:
                    continue
                if file_rel in seen_files:
                    continue  # already handled by git grep
                if (
                    not explicit_humans_search
                    and not include_humans
                    and _is_humans_path(file_path, root)
                ):
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue

                cached_lines = _get_file_lines(file_rel, untracked_text=text)

                file_output = []
                for line_no, line in enumerate(cached_lines, 1):
                    if python_pattern.search(line):
                        _append_match_lines(
                            file_output,
                            file_rel=file_rel,
                            line_no=line_no,
                            line_text=line,
                            untracked_text=text,
                        )
                        total_matches += 1
                        if total_matches >= max_results:
                            break

                if file_output:
                    results.append(f"\n**{file_rel}** _(untracked)_")
                    results.extend(file_output)

                if total_matches >= max_results:
                    results.append(f"\n_(truncated at {max_results} matches)_")
                    break

        if (
            total_matches < max_results
            and not explicit_humans_search
            and include_humans
            and path in {"", "."}
        ):
            humans_root = _resolve_humans_root(root)
            if humans_root.exists() and humans_root.is_dir():
                for file_path in sorted(humans_root.glob(glob_pattern)):
                    if any(part in _IGNORED_NAMES for part in file_path.parts):
                        continue
                    if not file_path.is_file():
                        continue
                    file_rel = _display_rel_path(file_path, root)
                    if file_rel in seen_files:
                        continue
                    try:
                        text = file_path.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        continue

                    cached_lines = _get_file_lines(file_rel, untracked_text=text)

                    file_output = []
                    for line_no, line in enumerate(cached_lines, 1):
                        if python_pattern.search(line):
                            _append_match_lines(
                                file_output,
                                file_rel=file_rel,
                                line_no=line_no,
                                line_text=line,
                                untracked_text=text,
                            )
                            total_matches += 1
                            if total_matches >= max_results:
                                break

                    if file_output:
                        results.append(f"\n**{file_rel}** _(untracked)_")
                        results.extend(file_output)

                    if total_matches >= max_results:
                        results.append(f"\n_(truncated at {max_results} matches)_")
                        break

        if not results:
            return f"No matches found for {query!r} in {path!r}."

        return "\n".join(results)

    # ------------------------------------------------------------------
    # memory_find_references
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_find_references",
        annotations=_tool_annotations(
            title="Find Path References",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_find_references(path: str, include_body: bool = False) -> str:
        """Return structured references to a path or path fragment across governed markdown."""
        from ..errors import ValidationError

        if not isinstance(path, str) or not path.strip():
            raise ValidationError("path must be a non-empty string")

        root = get_root()
        matches = find_references(root, path.strip(), include_body=include_body)
        payload = {
            "query": path.strip(),
            "include_body": include_body,
            "matches": matches,
            "total": len(matches),
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_validate_links
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_validate_links",
        annotations=_tool_annotations(
            title="Validate Internal Links",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_validate_links(path: str = "") -> str:
        """Validate internal markdown and frontmatter path references within governed content."""
        from ..errors import ValidationError

        root = get_root()
        requested_path = path.strip().replace("\\", "/")
        if requested_path:
            scope_path = _resolve_visible_path(root, requested_path)
            try:
                scope_path.relative_to(root)
            except ValueError as exc:
                raise ValidationError("path must stay within the repository root") from exc
            if not scope_path.exists():
                return f"Error: Path not found: {path}"

        payload = validate_links(root, requested_path)
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_reorganize_preview
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_reorganize_preview",
        annotations=_tool_annotations(
            title="Preview Path Reorganization",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_reorganize_preview(source: str, dest: str) -> str:
        """Preview the impact of moving a file or subtree to a new repository path."""
        from ..errors import ValidationError

        if not isinstance(source, str) or not source.strip():
            raise ValidationError("source must be a non-empty string")
        if not isinstance(dest, str) or not dest.strip():
            raise ValidationError("dest must be a non-empty string")

        root = get_root()
        normalized_source = source.strip().replace("\\", "/").strip("/")
        normalized_dest = dest.strip().replace("\\", "/").strip("/")
        source_path = (root / normalized_source).resolve()
        dest_path = (root / normalized_dest).resolve()

        try:
            source_path.relative_to(root)
            dest_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("source and dest must stay within the repository root") from exc

        if not source_path.exists():
            return f"Error: Path not found: {source}"

        dest_parent = dest_path.parent
        if not dest_parent.exists():
            raise ValidationError(
                f"destination parent does not exist: {dest_parent.relative_to(root).as_posix()}"
            )

        payload = preview_reorganization(root, normalized_source, normalized_dest)
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_suggest_structure
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_suggest_structure",
        annotations=_tool_annotations(
            title="Suggest Structure Improvements",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_suggest_structure(
        folder_path: str = "",
        heuristics: list[str] | None = None,
    ) -> str:
        """Suggest advisory structure improvements for the governed markdown tree."""
        from ..errors import ValidationError

        root = get_root()
        requested_path = folder_path.strip().replace("\\", "/")
        if requested_path:
            scope_path = _resolve_visible_path(root, requested_path)
            try:
                scope_path.relative_to(root)
            except ValueError as exc:
                raise ValidationError("folder_path must stay within the repository root") from exc
            if not scope_path.exists():
                return f"Error: Path not found: {folder_path}"

        if heuristics is not None:
            if not isinstance(heuristics, list) or not all(
                isinstance(item, str) for item in heuristics
            ):
                raise ValidationError("heuristics must be a list of strings")

        try:
            payload = suggest_structure(root, requested_path, heuristics)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_check_cross_references
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_check_cross_references",
        annotations=_tool_annotations(
            title="Check Cross References",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_check_cross_references(
        path: str = ".",
        check_summaries: bool = True,
        check_links: bool = True,
    ) -> str:
        """Scan tracked Markdown files for broken links and SUMMARY drift.

        Uses git ls-files to enumerate tracked Markdown files within the
        requested scope, then checks relative Markdown links and SUMMARY.md
        coverage. External URLs and anchor-only links are ignored.

        Args:
            path: Repo-relative file or folder scope to scan (default: '.').
            check_summaries: Report SUMMARY.md orphan and stale entries.
            check_links: Report broken relative Markdown links.

        Returns:
            Structured JSON describing broken links, orphaned files, stale
            summary entries, and scan statistics.
        """
        from ..errors import ValidationError

        root = get_root()
        requested_path = path.strip() or "."
        scope_path = _resolve_visible_path(root, requested_path)
        try:
            scope_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("path must stay within the repository root") from exc

        if not scope_path.exists():
            return f"Error: Path not found: {path}"

        scope = scope_path.relative_to(root).as_posix() if scope_path != root else "."
        tracked_files = _list_tracked_markdown_files(root, scope)
        if len(tracked_files) > 500:
            raise ValidationError(
                "memory_check_cross_references scans at most 500 tracked Markdown files; narrow path"
            )

        broken_links: list[dict[str, Any]] = []
        orphaned_files: list[dict[str, Any]] = []
        stale_summary_entries: list[dict[str, Any]] = []
        links_checked = 0

        file_groups: dict[Path, list[Path]] = {}
        summary_paths: list[Path] = []

        for abs_path in tracked_files:
            file_groups.setdefault(abs_path.parent, []).append(abs_path)
            if abs_path.name == "SUMMARY.md":
                summary_paths.append(abs_path)

            text = abs_path.read_text(encoding="utf-8")
            if not check_links:
                continue

            for line_no, target in _iter_markdown_links(text):
                resolved_target, reason = _resolve_repo_relative_target(root, abs_path, target)
                links_checked += 1
                if reason is None:
                    continue
                broken_links.append(
                    {
                        "file": abs_path.relative_to(root).as_posix(),
                        "line": line_no,
                        "target": resolved_target or target,
                        "reason": reason,
                    }
                )
                if check_summaries and abs_path.name == "SUMMARY.md":
                    stale_summary_entries.append(
                        {
                            "summary": abs_path.relative_to(root).as_posix(),
                            "entry": target,
                            "reason": reason,
                        }
                    )

        if check_summaries:
            for summary_path in summary_paths:
                summary_rel = summary_path.relative_to(root).as_posix()
                summary_text = summary_path.read_text(encoding="utf-8")
                linked_targets: set[str] = set()
                for _, target in _iter_markdown_links(summary_text):
                    resolved_target, reason = _resolve_repo_relative_target(
                        root, summary_path, target
                    )
                    if resolved_target is not None:
                        linked_targets.add(resolved_target)
                    if reason is not None and not any(
                        item["summary"] == summary_rel and item["entry"] == target
                        for item in stale_summary_entries
                    ):
                        stale_summary_entries.append(
                            {
                                "summary": summary_rel,
                                "entry": target,
                                "reason": reason,
                            }
                        )

                for sibling in sorted(file_groups.get(summary_path.parent, [])):
                    if sibling.name == "SUMMARY.md":
                        continue
                    sibling_rel = sibling.relative_to(root).as_posix()
                    if sibling_rel in linked_targets or sibling.name in summary_text:
                        continue
                    orphaned_files.append(
                        {
                            "file": sibling_rel,
                            "folder_summary": summary_rel,
                            "reason": "not mentioned in SUMMARY.md",
                        }
                    )

        result = {
            "broken_links": broken_links,
            "orphaned_files": orphaned_files,
            "stale_summary_entries": stale_summary_entries,
            "stats": {
                "files_scanned": len(tracked_files),
                "links_checked": links_checked,
                "summaries_checked": len(summary_paths) if check_summaries else 0,
                "issues_found": (
                    len(broken_links) + len(orphaned_files) + len(stale_summary_entries)
                ),
            },
        }
        return json.dumps(result, indent=2)

    # ------------------------------------------------------------------
    # memory_surface_unlinked
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_surface_unlinked",
        annotations=_tool_annotations(
            title="Surface Unlinked Files",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_surface_unlinked(
        scope: str = "memory/knowledge",
        max_results: int = 25,
        include_suggestions: bool = True,
        threshold: int = 2,
        category: str = "",
    ) -> str:
        """Surface knowledge files with zero or low cross-reference connectivity.

        Builds a lightweight in-degree/out-degree connectivity graph of the
        governed Markdown files in the requested scope, identifies files that
        are isolated, sinks, sources, or have low total connectivity, and
        returns a prioritised review queue with enough context for an agent to
        decide what links to add.

        Use this tool to discover files that would benefit from additional
        cross-references. After reviewing the results, use the existing
        write tools (e.g. memory_update_frontmatter) to add ``related:``
        entries or inline Markdown links.

        Args:
            scope: Repo-relative folder to scan (default: 'memory/knowledge').
            max_results: Maximum candidates to return (default: 25, max: 100).
            include_suggestions: Include heuristic link suggestions per candidate.
            threshold: Total-degree ceiling for 'low_connectivity' bucket (default: 2).
            category: Filter to a single category: 'isolated', 'sink', 'source',
                      'low_connectivity', or '' for all.

        Returns:
            Structured JSON with graph statistics, prioritised candidate list,
            and optional link suggestions per candidate.
        """
        from ..errors import ValidationError

        root = get_root()
        requested_scope = scope.strip().replace("\\", "/")
        if not requested_scope:
            requested_scope = "memory/knowledge"

        scope_path = (root / requested_scope).resolve()
        try:
            scope_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("scope must stay within the repository root") from exc
        if not scope_path.exists():
            return f"Error: Path not found: {scope}"

        max_results = max(1, min(max_results, 100))
        if threshold < 0:
            raise ValidationError("threshold must be non-negative")

        valid_categories = {"", "isolated", "sink", "source", "low_connectivity"}
        if category not in valid_categories:
            raise ValidationError(
                f"category must be one of {sorted(valid_categories - {''})!r} or '' for all"
            )

        try:
            payload = find_unlinked_files(
                root=root,
                scope=requested_scope,
                threshold=threshold,
                category_filter=category,
                max_results=max_results,
                include_suggestions=include_suggestions,
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_generate_summary
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_generate_summary",
        annotations=_tool_annotations(
            title="Generate Summary Draft",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_generate_summary(path: str, style: str = "standard") -> str:
        """Generate a paste-ready SUMMARY.md draft for a folder.

        Reads Markdown files in a folder, extracts a title plus the first
        descriptive paragraph from each, and returns a draft SUMMARY.md string.
        The tool is read-only: it previews content but does not write it.
        """
        from ..errors import ValidationError
        from ..frontmatter_utils import read_with_frontmatter

        root = get_root()
        requested_path = path.strip()
        if not requested_path:
            raise ValidationError("path is required")

        folder_path = (root / requested_path).resolve()
        try:
            folder_path.relative_to(root)
        except ValueError as exc:
            raise ValidationError("path must stay within the repository root") from exc

        if not folder_path.exists():
            return f"Error: Path not found: {path}"
        if not folder_path.is_dir():
            return f"Error: Folder not found: {path}"
        if style not in {"standard", "detailed"}:
            raise ValidationError("style must be 'standard' or 'detailed'")

        file_entries: list[str] = []
        subfolder_entries: list[str] = []

        for entry in sorted(
            folder_path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())
        ):
            if entry.name.startswith(".") or entry.name in _IGNORED_NAMES:
                continue
            if entry.is_dir():
                summary_file = entry / "SUMMARY.md"
                if summary_file.exists():
                    subfolder_entries.append(
                        f"- **{entry.name}/** -- See [{entry.name}/SUMMARY.md]({entry.name}/SUMMARY.md)"
                    )
                continue
            if entry.suffix.lower() != ".md" or entry.name == "SUMMARY.md":
                continue

            fm_dict, body = read_with_frontmatter(entry)
            heading, description = _extract_heading_and_paragraph(
                body, entry.stem.replace("-", " ").title()
            )
            metadata = _build_summary_metadata(fm_dict)
            link_target = entry.name
            if style == "standard":
                entry_line = f"- **[{entry.name}]({link_target})** -- {description}"
                if metadata:
                    entry_line += f" ({metadata})"
            else:
                detail_parts = [description]
                if heading and heading != entry.name:
                    detail_parts.append(f"Title: {heading}.")
                if metadata:
                    detail_parts.append(f"Metadata: {metadata}.")
                entry_line = f"- **[{entry.name}]({link_target})** -- {' '.join(detail_parts)}"
            file_entries.append(entry_line)

        folder_title = _format_summary_folder_title(folder_path.name)
        generated_on = str(date.today())
        lines = [
            f"<!-- Generated by memory_generate_summary on {generated_on}. Review before committing. -->",
            f"# {folder_title} -- Summary",
            "",
            f"Source folder: `{requested_path}`. Style: `{style}`. Files: {len(file_entries)}. Subfolders: {len(subfolder_entries)}.",
            "",
        ]

        if file_entries:
            lines.append("## Files")
            lines.append("")
            lines.extend(file_entries)
            lines.append("")

        if subfolder_entries:
            lines.append("## Subfolders")
            lines.append("")
            lines.extend(subfolder_entries)
            lines.append("")

        if not file_entries and not subfolder_entries:
            lines.append("_No Markdown files or summarized subfolders found._")
            lines.append("")

        draft = "\n".join(lines).rstrip() + "\n"
        word_count = _word_count(draft)
        draft += f"\n<!-- Word count: {word_count} (target: 200-800 words) -->\n"
        return draft

    # ------------------------------------------------------------------
    # memory_access_analytics
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_access_analytics",
        annotations=_tool_annotations(
            title="Access Analytics",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_access_analytics(
        folders: str | None = None,
        window_days: int = 90,
        top_n: int = 10,
    ) -> str:
        """Classify files using curation-policy ACCESS patterns.

        Reads hot ACCESS logs and archive segments, filters entries to the
        requested window and folder prefixes, then returns policy-aligned
        categories plus suggested follow-up actions.
        """
        from ..errors import ValidationError

        if window_days <= 0:
            raise ValidationError("window_days must be >= 1")
        if top_n <= 0:
            raise ValidationError("top_n must be >= 1")

        root = get_root()
        raw_folder_filters = _split_csv_or_lines(folders) if folders else []
        folder_filters: list[str] = []
        for folder in raw_folder_filters:
            normalized = folder.replace("\\", "/").strip().rstrip("/")
            if not normalized:
                raise ValidationError("folders must contain non-empty repo-relative paths")
            if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
                raise ValidationError("folders must contain repo-relative paths")
            if re.match(r"^[A-Za-z]:[/\\]", normalized):
                raise ValidationError("folders must contain repo-relative paths")
            folder_filters.extend(_normalize_access_folder_prefixes(normalized))

        end_date = date.today()
        start_date = end_date - timedelta(days=window_days - 1)
        all_entries = _load_access_history_entries(root)
        filtered_entries: list[dict[str, Any]] = []
        for entry in all_entries:
            entry_date = _parse_iso_date(entry.get("date"))
            if entry_date is None or entry_date < start_date or entry_date > end_date:
                continue
            file_path = str(entry.get("file", ""))
            if folder_filters and not any(
                file_path == folder.rstrip("/") or file_path.startswith(f"{folder.rstrip('/')}/")
                for folder in folder_filters
            ):
                continue
            filtered_entries.append(entry)

        file_summaries = _summarize_access_by_file(filtered_entries)

        core_memory: list[dict[str, Any]] = []
        near_miss: list[dict[str, Any]] = []
        false_positive_attractor: list[dict[str, Any]] = []
        retirement_candidate: list[dict[str, Any]] = []
        hidden_gem: list[dict[str, Any]] = []
        suggested_actions: list[dict[str, Any]] = []

        for item in file_summaries:
            access_count = int(item["entry_count"])
            mean_helpfulness = item.get("mean_helpfulness")
            if mean_helpfulness is None:
                continue

            helpfulness_value = float(mean_helpfulness)
            category_payload = {
                "file": item["file"],
                "access_count": access_count,
                "mean_helpfulness": helpfulness_value,
            }

            if (
                access_count >= _CURATION_HIGH_ACCESS_THRESHOLD
                and helpfulness_value >= _CURATION_HIGH_HELPFULNESS_THRESHOLD
            ):
                core_memory.append(category_payload)
                suggested_actions.append(
                    {
                        "file": item["file"],
                        "action": "enrich_cross_refs",
                        "reason": (
                            f"Core memory: {access_count} accesses, {helpfulness_value:.3f} mean helpfulness"
                        ),
                    }
                )
                continue

            if (
                access_count >= _CURATION_HIGH_ACCESS_THRESHOLD
                and _CURATION_NEAR_MISS_MIN <= helpfulness_value <= _CURATION_NEAR_MISS_MAX
            ):
                near_miss.append(category_payload)
                suggested_actions.append(
                    {
                        "file": item["file"],
                        "action": "split_or_retitle",
                        "reason": (
                            f"Near miss: {access_count} accesses, {helpfulness_value:.3f} mean helpfulness"
                        ),
                    }
                )
                continue

            if (
                access_count >= _CURATION_HIGH_ACCESS_THRESHOLD
                and helpfulness_value <= _CURATION_FALSE_POSITIVE_MAX
            ):
                false_positive_attractor.append(category_payload)
                suggested_actions.append(
                    {
                        "file": item["file"],
                        "action": "retitle_or_retag",
                        "reason": (
                            "False-positive attractor: "
                            f"{access_count} accesses, {helpfulness_value:.3f} mean helpfulness"
                        ),
                    }
                )
                continue

            if (
                access_count < _CURATION_RETIREMENT_THRESHOLD
                and helpfulness_value >= _CURATION_HIGH_HELPFULNESS_THRESHOLD
            ):
                hidden_gem.append(category_payload)
                suggested_actions.append(
                    {
                        "file": item["file"],
                        "action": "improve_summary_placement",
                        "reason": (
                            f"Hidden gem: {access_count} accesses, {helpfulness_value:.3f} mean helpfulness"
                        ),
                    }
                )
                continue

            if (
                access_count >= _CURATION_RETIREMENT_THRESHOLD
                and helpfulness_value <= _CURATION_RETIREMENT_MAX
            ):
                retirement_candidate.append(category_payload)
                suggested_actions.append(
                    {
                        "file": item["file"],
                        "action": "flag_for_review",
                        "reason": (
                            "Retirement candidate: "
                            f"{access_count} accesses, {helpfulness_value:.3f} mean helpfulness"
                        ),
                    }
                )

        top_accessed = [
            {"file": item["file"], "count": int(item["entry_count"])}
            for item in file_summaries[:top_n]
        ]
        least_accessed_source = sorted(
            file_summaries,
            key=lambda item: (
                int(item["entry_count"]),
                str(item.get("last_access_date") or ""),
                str(item["file"]),
            ),
        )
        least_accessed = [
            {
                "file": item["file"],
                "count": int(item["entry_count"]),
                "last_access": item.get("last_access_date"),
            }
            for item in least_accessed_source[:top_n]
        ]

        payload = {
            "window": {
                "start": str(start_date),
                "end": str(end_date),
                "days": window_days,
            },
            "thresholds": {
                "high_access": _CURATION_HIGH_ACCESS_THRESHOLD,
                "retirement_access": _CURATION_RETIREMENT_THRESHOLD,
                "core_helpfulness_min": _CURATION_HIGH_HELPFULNESS_THRESHOLD,
                "near_miss_range": [_CURATION_NEAR_MISS_MIN, _CURATION_NEAR_MISS_MAX],
                "false_positive_max": _CURATION_FALSE_POSITIVE_MAX,
                "retirement_max": _CURATION_RETIREMENT_MAX,
                "policy_source": _resolve_governance_path(root, "curation-policy.md")
                .relative_to(root)
                .as_posix(),
            },
            "folders": folder_filters or None,
            "total_entries": len(filtered_entries),
            "unique_files": len(file_summaries),
            "categories": {
                "core_memory": core_memory,
                "near_miss": near_miss,
                "false_positive_attractor": false_positive_attractor,
                "retirement_candidate": retirement_candidate,
                "hidden_gem": hidden_gem,
            },
            "top_accessed": top_accessed,
            "least_accessed": least_accessed,
            "suggested_actions": suggested_actions,
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_diff_branch
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_diff_branch",
        annotations=_tool_annotations(
            title="Branch Divergence",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_diff_branch(base: str = "core") -> str:
        """Compare the current branch against a base branch.

        Returns structured divergence data for merge planning, including recent
        commits and file-change counts grouped by top-level category.
        """
        root = get_root()
        resolved_base = _resolve_default_base_branch(root, base)

        def _git(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *args],
                cwd=str(root),
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                check=check,
            )

        current_branch_result = _git(["symbolic-ref", "--quiet", "--short", "HEAD"])
        current_branch = (
            current_branch_result.stdout.strip()
            if current_branch_result.returncode == 0
            else "HEAD"
        )

        def _resolve_base_ref() -> str | None:
            local_result = _git(["rev-parse", "--verify", resolved_base])
            if local_result.returncode == 0:
                return resolved_base
            remote_result = _git(["rev-parse", "--verify", f"origin/{resolved_base}"])
            if remote_result.returncode == 0:
                return f"origin/{resolved_base}"

            fetch_result = _git(["fetch", "origin", resolved_base])
            if fetch_result.returncode != 0:
                return None

            local_retry = _git(["rev-parse", "--verify", resolved_base])
            if local_retry.returncode == 0:
                return resolved_base
            remote_retry = _git(["rev-parse", "--verify", f"origin/{resolved_base}"])
            if remote_retry.returncode == 0:
                return f"origin/{resolved_base}"
            return None

        base_ref = _resolve_base_ref()
        if base_ref is None:
            return json.dumps(
                {
                    "error": (
                        f"Base branch '{resolved_base}' is not available locally and could not be fetched from origin."
                    ),
                    "base_branch": resolved_base,
                    "current_branch": current_branch,
                },
                indent=2,
            )

        ahead_result = _git(["rev-list", "--count", f"{base_ref}..HEAD"], check=True)
        name_status_result = _git(["diff", "--name-status", f"{base_ref}...HEAD"], check=True)
        shortstat_result = _git(["diff", "--shortstat", f"{base_ref}...HEAD"], check=True)
        log_result = _git(
            [
                "log",
                f"{base_ref}..HEAD",
                "--date=short",
                "--format=%H%x09%ad%x09%s",
                "-n",
                "10",
            ],
            check=True,
        )

        category_order = [
            "knowledge",
            "plans",
            "identity",
            "meta",
            "tools",
            "skills",
            "chats",
            "scratchpad",
            "other",
        ]
        by_category = {
            category: {"added": 0, "modified": 0, "deleted": 0} for category in category_order
        }

        files_changed = 0
        for raw_line in name_status_result.stdout.splitlines():
            parts = raw_line.split("\t")
            if len(parts) < 2:
                continue
            status = parts[0]
            rel_path = parts[-1]
            visible_path = rel_path
            if root.name and rel_path.startswith(f"{root.name}/"):
                visible_path = rel_path[len(root.name) + 1 :]

            if visible_path.startswith(("memory/knowledge/", "knowledge/")):
                category = "knowledge"
            elif visible_path.startswith(("memory/working/projects/", "plans/")):
                category = "plans"
            elif visible_path.startswith(("memory/users/", "identity/")):
                category = "identity"
            elif visible_path.startswith(("memory/skills/", "skills/")):
                category = "skills"
            elif visible_path.startswith("memory/activity/"):
                category = "chats"
            elif visible_path.startswith("memory/working/scratchpad/"):
                category = "scratchpad"
            elif visible_path.startswith(("governance/", "meta/", "HUMANS/")):
                category = "meta"
            elif visible_path.startswith(("tools/", "core/tools/")):
                category = "tools"
            else:
                category = "other"
            if status.startswith("A"):
                bucket = "added"
            elif status.startswith("D"):
                bucket = "deleted"
            else:
                bucket = "modified"
            by_category[category][bucket] += 1
            files_changed += 1

        insertions = 0
        deletions = 0
        shortstat_text = shortstat_result.stdout.strip()
        files_match = re.search(r"(\d+) files? changed", shortstat_text)
        insertions_match = re.search(r"(\d+) insertions?\(\+\)", shortstat_text)
        deletions_match = re.search(r"(\d+) deletions?\(-\)", shortstat_text)
        if files_match:
            files_changed = int(files_match.group(1))
        if insertions_match:
            insertions = int(insertions_match.group(1))
        if deletions_match:
            deletions = int(deletions_match.group(1))

        recent_commits: list[dict[str, Any]] = []
        for raw_line in log_result.stdout.splitlines():
            sha, commit_date, message = (raw_line.split("\t", 2) + ["", "", ""])[:3]
            if not sha:
                continue
            recent_commits.append(
                {
                    "sha": sha[:7],
                    "message": message,
                    "date": commit_date,
                }
            )

        payload = {
            "base_branch": resolved_base,
            "resolved_base_ref": base_ref,
            "current_branch": current_branch,
            "commits_ahead": int(ahead_result.stdout.strip() or "0"),
            "files_changed": files_changed,
            "insertions": insertions,
            "deletions": deletions,
            "by_category": by_category,
            "recent_commits": recent_commits,
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_git_log
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_git_log",
        annotations=_tool_annotations(
            title="Git Log for Memory Repo",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_git_log(
        n: int = 10,
        since: str | None = None,
        path_filter: str | None = None,
        use_host_repo: bool = False,
    ) -> str:
        """Return recent commit history for the memory repository.

        Useful at session start to see what changed since the last session.

        Args:
            n: Number of commits to return (default: 10, max: 50).
            since: Optional ISO date filter (YYYY-MM-DD). Only commits after this date are returned.
            path_filter: Optional repo-relative path or git pathspec to restrict the log.
            use_host_repo: When true, read from host_repo_root in agent-bootstrap.toml.

        Returns:
            JSON list of commits, each with sha, message, date, files_changed, truncated.
        """
        from ..errors import ValidationError

        root = get_root()
        repo = _get_git_repo_for_log(root, get_repo(), use_host_repo=use_host_repo)
        n = min(n, 50)
        if since is not None and _parse_iso_date(since) is None:
            raise ValidationError("since must be a valid ISO date string (YYYY-MM-DD)")

        normalized_path_filter = None
        if path_filter is not None:
            normalized_path_filter = _normalize_git_log_path_filter(path_filter)

        commits = repo.log(n, since=since, path_filter=normalized_path_filter)
        truncated = False
        if since is not None and len(commits) == n and n > 0:
            total_commits = repo.commit_count_since(
                since,
                paths=[normalized_path_filter] if normalized_path_filter else None,
            )
            truncated = total_commits > len(commits)

        for commit in commits:
            commit["truncated"] = truncated
        return json.dumps(commits, indent=2)

    # ------------------------------------------------------------------
    # memory_check_knowledge_freshness
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_check_knowledge_freshness",
        annotations=_tool_annotations(
            title="Check Knowledge Freshness",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_check_knowledge_freshness(paths: str) -> str:
        """Check knowledge-file freshness against the configured host repository.

        Args:
            paths: Comma-separated or newline-separated knowledge file paths.

        Returns:
            JSON with one freshness report per requested knowledge file.
        """
        root = get_root()
        repo = get_repo()
        reports = [
            _build_knowledge_freshness_report(root, repo, rel_path, abs_path)
            for rel_path, abs_path in _resolve_requested_knowledge_paths(root, paths)
        ]
        payload = {
            "checked_at": str(date.today()),
            "files_checked": len(reports),
            "reports": reports,
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_session_health_check
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_session_health_check",
        annotations=_tool_annotations(
            title="Session Health Check",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_session_health_check() -> str:
        """Return session-start maintenance status for ACCESS, review queue, and review cadence.

        Reads the active aggregation trigger and last periodic review date from
        the live router file, counts hot ACCESS.jsonl entries, and summarizes
        pending review-queue items.

        Returns:
            JSON with aggregation_due, aggregation_threshold, review_queue_pending,
            periodic_review_due, days_since_review, last_periodic_review, checked_at.
        """
        root = get_root()
        trigger = _parse_aggregation_trigger(root)
        review_window_days = _parse_periodic_review_window(root)
        _, access_counts = _load_access_entries(root)
        last_review = _parse_last_periodic_review(root)
        today = date.today()
        days_since_review = (today - last_review).days if last_review is not None else None

        aggregation_due = []
        for item in access_counts:
            entry_count = int(item["entries"])
            if entry_count < trigger:
                continue
            folder = str(item["folder"]).rstrip("/")
            aggregation_due.append(
                {
                    "folder": f"{folder}/",
                    "entries": entry_count,
                    "threshold": trigger,
                    "overdue": True,
                }
            )

        aggregation_due.sort(
            key=lambda item: (-cast(int, item["entries"]), cast(str, item["folder"]))
        )

        review_queue_entries = _parse_review_queue_entries(root)
        pending_review_queue = [
            entry
            for entry in review_queue_entries
            if entry.get("status", "pending") == "pending"
            or (
                entry.get("type") == "security" and entry.get("status", "pending") == "investigated"
            )
        ]

        payload = {
            "aggregation_due": aggregation_due,
            "aggregation_threshold": trigger,
            "review_queue_pending": len(pending_review_queue),
            "periodic_review_due": last_review is None
            or (days_since_review is not None and days_since_review > review_window_days),
            "days_since_review": days_since_review,
            "last_periodic_review": str(last_review) if last_review is not None else None,
            "checked_at": str(today),
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_check_aggregation_triggers
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_check_aggregation_triggers",
        annotations=_tool_annotations(
            title="ACCESS Aggregation Trigger Status",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_check_aggregation_triggers() -> str:
        """Report which hot ACCESS logs are below, near, or above aggregation trigger.

        Uses the active aggregation threshold from the live router file and
        counts valid non-empty entries in each hot ACCESS.jsonl file.

        Returns:
            JSON with trigger metadata, per-log counts, and lists of files that
            are near or above the aggregation threshold.
        """
        root = get_root()
        trigger = _parse_aggregation_trigger(root)
        _, access_counts = _load_access_entries(root)

        report: list[dict[str, Any]] = []
        above_trigger: list[str] = []
        near_trigger: list[str] = []

        for item in access_counts:
            entry_count = int(item["entries"])
            remaining = max(trigger - entry_count, 0)
            if entry_count >= trigger:
                status = "above"
                above_trigger.append(cast(str, item["access_file"]))
            elif remaining <= _NEAR_TRIGGER_WINDOW:
                status = "near"
                near_trigger.append(cast(str, item["access_file"]))
            else:
                status = "below"

            report.append(
                {
                    **item,
                    "trigger": trigger,
                    "remaining_to_trigger": remaining,
                    "status": status,
                }
            )

        payload = {
            "aggregation_trigger": trigger,
            "near_trigger_window": _NEAR_TRIGGER_WINDOW,
            "files_checked": len(report),
            "above_trigger": above_trigger,
            "near_trigger": near_trigger,
            "reports": report,
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_aggregate_access
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_aggregate_access",
        annotations=_tool_annotations(
            title="Aggregate ACCESS Logs",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_aggregate_access(
        folder: str = "",
        file_prefix: str = "",
        start_date: str = "",
        end_date: str = "",
        min_helpfulness: float | None = None,
        max_helpfulness: float | None = None,
    ) -> str:
        """Aggregate hot ACCESS.jsonl entries into a maintenance report.

        The first cut is read-only. It computes file-level access summaries,
        high-value and low-value candidates, same-session co-retrieval clusters,
        and preview targets for follow-up curation work.

        Returns:
            JSON report with filters, file summaries, clusters, and proposed
            follow-up outputs for summary updates, review queue entries, and
            archive targets.
        """
        root = get_root()
        trigger = _parse_aggregation_trigger(root)
        all_entries, access_counts = _load_access_entries(root)
        filtered_entries = _filter_access_entries(
            all_entries,
            folder=folder,
            file_prefix=file_prefix,
            start_date=start_date,
            end_date=end_date,
            min_helpfulness=min_helpfulness,
            max_helpfulness=max_helpfulness,
        )
        file_summaries = _summarize_access_by_file(filtered_entries)
        clusters = _detect_co_retrieval_clusters(filtered_entries)

        high_value_files = [
            item
            for item in file_summaries
            if int(item["entry_count"]) >= 5
            and item["mean_helpfulness"] is not None
            and float(item["mean_helpfulness"]) >= 0.7
        ]
        low_value_files = [
            item
            for item in file_summaries
            if int(item["entry_count"]) >= 3
            and item["mean_helpfulness"] is not None
            and float(item["mean_helpfulness"]) <= 0.3
        ]

        archive_targets: list[str] = []
        if folder:
            normalized_folder = folder.rstrip("/")
            archive_targets = [
                cast(str, item["access_file"])
                for item in access_counts
                if cast(str, item["access_file"]).startswith(f"{normalized_folder}/")
                and int(item["entries"]) >= trigger
            ]
        else:
            archive_targets = [
                cast(str, item["access_file"])
                for item in access_counts
                if int(item["entries"]) >= trigger
            ]

        summary_update_targets = {
            f"{item['folder']}/SUMMARY.md"
            for item in high_value_files + low_value_files
            if isinstance(item.get("folder"), str)
        }
        for cluster in clusters:
            for folder_name in cast(list[str], cluster["folders"]):
                summary_update_targets.add(f"{folder_name}/SUMMARY.md")
        sorted_summary_update_targets = sorted(summary_update_targets)
        review_queue_candidates = [
            {
                "file": item["file"],
                "reason": "Consistently low-value ACCESS pattern",
                "entry_count": item["entry_count"],
                "mean_helpfulness": item["mean_helpfulness"],
            }
            for item in low_value_files
        ]
        task_group_candidates = [
            {
                "files": cluster["files"],
                "folders": cluster["folders"],
                "co_retrieval_count": cluster["co_retrieval_count"],
            }
            for cluster in clusters
            if len(cast(list[str], cluster["folders"])) >= 2
        ]

        payload = {
            "access_scope": "hot_only",
            "filters": {
                "folder": folder or None,
                "file_prefix": file_prefix or None,
                "start_date": start_date or None,
                "end_date": end_date or None,
                "min_helpfulness": min_helpfulness,
                "max_helpfulness": max_helpfulness,
            },
            "aggregation_trigger": trigger,
            "entries_considered": len(filtered_entries),
            "files_considered": len(file_summaries),
            "high_value_files": high_value_files,
            "low_value_files": low_value_files,
            "co_retrieval_clusters": clusters,
            "file_summaries": file_summaries,
            "proposed_outputs": {
                "summary_update_targets": sorted_summary_update_targets,
                "access_archive_targets": archive_targets,
                "review_queue_candidates": review_queue_candidates,
                "task_group_candidates": task_group_candidates,
            },
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_run_periodic_review
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_run_periodic_review",
        annotations=_tool_annotations(
            title="Periodic Review Report",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_run_periodic_review() -> str:
        """Run the ordered periodic-review checklist as a read-only report.

        The tool mirrors the checklist in governance/update-guidelines.md and returns
        structured findings plus deferred write targets rather than mutating any
        protected files directly.
        """
        root = get_root()
        repo = get_repo()
        low_threshold, _ = _parse_trust_thresholds(root)
        current_stage = _parse_current_stage(root)
        last_review = _parse_last_periodic_review(root)
        today = date.today()
        review_window_days = _parse_periodic_review_window(root)
        days_since_review = (today - last_review).days if last_review is not None else None

        all_entries, access_counts = _load_access_entries(root)
        file_summaries = _summarize_access_by_file(all_entries)
        low_value_files = [
            item
            for item in file_summaries
            if int(item["entry_count"]) >= 3
            and item["mean_helpfulness"] is not None
            and float(item["mean_helpfulness"]) <= 0.3
        ]
        clusters = _detect_co_retrieval_clusters(all_entries)
        folder_summaries = _summarize_access_by_folder(file_summaries)
        review_queue_entries = _parse_review_queue_entries(root)
        security_entries = [
            entry for entry in review_queue_entries if entry.get("type") == "security"
        ]
        pending_security_entries = [
            entry
            for entry in security_entries
            if entry.get("status", "pending") in {"pending", "investigated"}
        ]
        pending_non_security_entries = [
            entry
            for entry in review_queue_entries
            if entry.get("type") != "security" and entry.get("status", "pending") == "pending"
        ]
        false_positive_security = [
            entry for entry in security_entries if entry.get("status") == "false-positive"
        ]

        unverified = _scan_unverified_content(root, low_threshold)
        conflicts = _find_conflict_tags(root)
        signals = _compute_maturity_signals(root, repo, all_entries)
        maturity = _assess_maturity_stage(signals, current_stage)
        anomaly_candidates = _detect_access_anomalies(root, all_entries, low_threshold)
        reflections = _collect_recent_reflections(root)
        recently_touched_files = _git_changed_files_since(repo, last_review)

        if last_review is None:
            review_due_reason = "No recorded periodic review date."
        elif days_since_review is not None and days_since_review > review_window_days:
            review_due_reason = f"Last periodic review was {days_since_review} days ago, beyond the {review_window_days}-day cadence."
        else:
            review_due_reason = "Periodic review cadence not yet exceeded."

        folder_candidates = {
            "high_access": [item for item in folder_summaries if int(item["entry_count"]) >= 15],
            "low_access": [item for item in folder_summaries if int(item["entry_count"]) <= 2],
        }
        governance_review_queue_count = len(
            [entry for entry in pending_non_security_entries if entry.get("type") == "governance"]
        )
        governance_evaluation = {
            "threshold_effectiveness": {
                "overdue_low_trust_files": len(cast(list[dict[str, Any]], unverified["overdue"])),
                "low_value_files": len(low_value_files),
            },
            "signal_quality": {
                "security_entries_total": len(security_entries),
                "security_false_positive_count": len(false_positive_security),
                "security_false_positive_ratio": (
                    round(len(false_positive_security) / len(security_entries), 3)
                    if security_entries
                    else None
                ),
                "anomaly_candidates": anomaly_candidates,
            },
            "consistency_targets": [
                "README.md",
                _resolve_live_router_path(root).relative_to(root).as_posix(),
                _resolve_governance_path(root, "update-guidelines.md").relative_to(root).as_posix(),
            ],
            "user_friendliness_notes": [
                "Keep protected changes in deferred output rather than applying them silently.",
                "Preserve metadata-first checks before loading expensive governance files.",
            ],
            "context_efficiency_notes": [
                "Compact returning path remains the default routing surface.",
                "Aggregation and periodic review stay read-first until a user approves protected writes.",
            ],
            "missing_coverage_prompt": governance_review_queue_count == 0,
        }

        summary_update_targets = {
            f"{item['folder']}/SUMMARY.md"
            for item in low_value_files
            if isinstance(item.get("folder"), str)
        }
        for cluster in clusters:
            for folder_name in cast(list[str], cluster["folders"]):
                summary_update_targets.add(f"{folder_name}/SUMMARY.md")

        deferred_write_targets = [
            _resolve_governance_path(root, "belief-diff-log.md").relative_to(root).as_posix()
        ]
        if (
            pending_non_security_entries
            or pending_security_entries
            or anomaly_candidates
            or unverified["overdue"]
        ):
            deferred_write_targets.append(
                _resolve_governance_path(root, "review-queue.md").relative_to(root).as_posix()
            )
        if (
            days_since_review is None
            or (days_since_review is not None and days_since_review > review_window_days)
            or maturity["transition_recommended"]
        ):
            deferred_write_targets.append(
                _resolve_live_router_path(root).relative_to(root).as_posix()
            )
        deferred_write_targets.extend(sorted(summary_update_targets))

        new_files_since_review = []
        for rel_path in _load_content_files(root):
            try:
                text = (root / rel_path).read_text(encoding="utf-8")
            except OSError:
                continue
            created_match = re.search(r"^created:\s*(\d{4}-\d{2}-\d{2})$", text, re.MULTILINE)
            if created_match is None or last_review is None:
                continue
            created_date = _parse_iso_date(created_match.group(1))
            if created_date is not None and created_date > last_review:
                new_files_since_review.append(rel_path)

        payload = {
            "review_due": {
                "last_periodic_review": str(last_review) if last_review is not None else None,
                "days_since_review": days_since_review,
                "due": last_review is None
                or (days_since_review is not None and days_since_review > review_window_days),
                "reason": review_due_reason,
            },
            "ordered_checks": {
                "security_flags": {
                    "pending_count": len(pending_security_entries),
                    "pending_entries": pending_security_entries,
                    "generated_candidates": anomaly_candidates,
                },
                "unverified_content": {
                    "total_files": len(cast(list[dict[str, Any]], unverified["files"])),
                    "overdue_count": len(cast(list[dict[str, Any]], unverified["overdue"])),
                    "overdue_files": unverified["overdue"],
                },
                "conflict_resolution": {
                    "count": len(conflicts),
                    "files": conflicts,
                },
                "review_queue": {
                    "pending_non_security_count": len(pending_non_security_entries),
                    "pending_non_security_entries": pending_non_security_entries,
                },
                "unhelpful_memory": {
                    "count": len(low_value_files),
                    "files": low_value_files,
                },
                "maturity_assessment": {
                    **maturity,
                    "signals": signals,
                },
                "governance_evaluation": governance_evaluation,
                "folder_structure": {
                    "folder_summaries": folder_summaries,
                    "candidates": folder_candidates,
                },
                "emergent_categorization": {
                    "cluster_count": len(clusters),
                    "clusters": clusters,
                },
                "session_reflection_themes": {
                    "reflection_count": len(reflections),
                    "recent_reflections": reflections,
                },
            },
            "belief_diff_preview": {
                "new_files_since_review": sorted(new_files_since_review),
                "recently_touched_files": recently_touched_files,
            },
            "aggregation_status": {
                "trigger": _parse_aggregation_trigger(root),
                "logs": access_counts,
            },
            "proposed_outputs": {
                "deferred_write_targets": sorted(set(deferred_write_targets)),
                "summary_update_targets": sorted(summary_update_targets),
                "review_queue_candidates": [
                    {
                        "type": "security",
                        "title": candidate["type"],
                        "file": candidate["file"],
                        "recommended_action": candidate["recommended_action"],
                    }
                    for candidate in anomaly_candidates
                ],
            },
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_session_bootstrap
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_session_bootstrap",
        annotations=_tool_annotations(
            title="Session Bootstrap Bundle",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_session_bootstrap(
        max_active_plans: int = 5,
        max_review_items: int = 5,
    ) -> str:
        """Return a compact session-start bundle for the returning-agent path."""
        from ..errors import ValidationError

        if max_active_plans < 1 or max_review_items < 1:
            raise ValidationError("max_active_plans and max_review_items must be >= 1")

        root = get_root()
        manifest, manifest_error = _load_capabilities_manifest(root)
        capabilities_summary = manifest_error or {
            "summary": _build_capabilities_summary(cast(dict[str, Any], manifest))
        }
        session_health = json.loads(await memory_session_health_check())
        active_plans, active_plan_budget = _truncate_items(
            _collect_plan_entries(root, status="active"),
            max_active_plans,
        )
        review_queue_entries = _parse_review_queue_entries(root)
        pending_review_items = [
            {
                "item_id": entry.get("item_id"),
                "title": entry.get("title"),
                "type": entry.get("type", "unknown"),
                "priority": entry.get("priority", "normal"),
                "file": entry.get("file"),
                "status": entry.get("status", "pending"),
            }
            for entry in review_queue_entries
            if entry.get("status", "pending") == "pending"
        ]
        pending_review_items, review_budget = _truncate_items(
            pending_review_items,
            max_review_items,
        )

        recommended_checks: list[str] = []
        if cast(list[dict[str, Any]], session_health["aggregation_due"]):
            recommended_checks.append(
                "Inspect aggregation pressure with memory_check_aggregation_triggers."
            )
        if bool(session_health["periodic_review_due"]):
            recommended_checks.append(
                "Prepare the protected periodic review workflow with memory_prepare_periodic_review."
            )
        if pending_review_items:
            recommended_checks.append(
                "Review pending queue items before any protected cleanup writes."
            )
        if active_plans:
            recommended_checks.append(
                f"Resume the leading active plan: {active_plans[0]['plan_id']}"
            )
        if not recommended_checks:
            recommended_checks.append(
                "No urgent maintenance signals detected; continue the current plan or inspect capabilities."
            )

        payload = {
            "capabilities": capabilities_summary,
            "session_health": session_health,
            "active_plans": active_plans,
            "pending_review_items": pending_review_items,
            "recommended_checks": recommended_checks,
            "response_budget": {
                "active_plans": active_plan_budget,
                "review_items": review_budget,
            },
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_prepare_unverified_review
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_prepare_unverified_review",
        annotations=_tool_annotations(
            title="Prepare Unverified Review",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_prepare_unverified_review(
        folder_path: str = "memory/knowledge/_unverified",
        max_files: int = 12,
        max_extract_words: int = 60,
        paths_only: bool = False,
    ) -> str:
        """Return a compact unverified-review bundle with bounded file extracts."""
        from ..errors import ValidationError

        if max_files < 1 and not paths_only:
            raise ValidationError("max_files must be >= 1")

        review_payload = json.loads(
            await memory_review_unverified(
                folder_path=folder_path,
                max_extract_words=max_extract_words,
                include_expired=True,
            )
        )
        candidates: list[dict[str, Any]] = []
        for group_name, entries in cast(
            dict[str, list[dict[str, Any]]], review_payload["groups"]
        ).items():
            for entry in entries:
                candidates.append(
                    {
                        "group": group_name,
                        "path": entry.get("path"),
                        "trust": entry.get("trust"),
                        "days_old": entry.get("days_old"),
                        "expired": entry.get("expired"),
                        "source": entry.get("source"),
                        "extract": entry.get("extract"),
                    }
                )
        candidates.sort(
            key=lambda item: (
                0 if item.get("expired") else 1,
                -(cast(int | None, item.get("days_old")) or -1),
                cast(str, item.get("path") or ""),
            )
        )
        if paths_only:
            all_paths = [cast(str, item["path"]) for item in candidates if item.get("path")]
            payload = {
                "folder_path": folder_path,
                "trust_counts": review_payload["trust_counts"],
                "expired_count": review_payload["expired_count"],
                "paths_only": True,
                "all_paths": all_paths,
                "recommended_operations": {
                    "single_file": "memory_promote_knowledge",
                    "batch": "memory_promote_knowledge_batch",
                    "subtree": "memory_promote_knowledge_subtree",
                },
                "response_budget": {
                    "paths": {
                        "returned": len(all_paths),
                        "total": len(all_paths),
                        "truncated": False,
                    },
                },
            }
            return json.dumps(payload, indent=2)
        selected_files, file_budget = _truncate_items(candidates, max_files)
        payload = {
            "folder_path": folder_path,
            "trust_counts": review_payload["trust_counts"],
            "expired_count": review_payload["expired_count"],
            "paths_only": False,
            "selected_files": selected_files,
            "recommended_operations": {
                "single_file": "memory_promote_knowledge",
                "batch": "memory_promote_knowledge_batch",
                "subtree": "memory_promote_knowledge_subtree",
            },
            "response_budget": {
                "files": file_budget,
            },
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_prepare_promotion_batch
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_prepare_promotion_batch",
        annotations=_tool_annotations(
            title="Prepare Knowledge Promotion Batch",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_prepare_promotion_batch(
        folder_path: str = "memory/knowledge/_unverified",
        max_files: int = 12,
    ) -> str:
        """Return compact promotion candidates with default target paths and operation hints."""
        from ..errors import ValidationError

        if max_files < 1:
            raise ValidationError("max_files must be >= 1")

        root = get_root()
        low_threshold, _ = _parse_trust_thresholds(root)
        unverified = _scan_unverified_content(root, low_threshold)
        normalized_folder = _normalize_repo_relative_path(folder_path)
        abs_folder = root / normalized_folder
        path_is_dir = abs_folder.exists() and abs_folder.is_dir()
        has_nested_subdirectories = path_is_dir and any(
            child.is_dir() for child in abs_folder.iterdir() if child.name != "SUMMARY.md"
        )
        candidates = [
            {
                "source_path": item["path"],
                "target_path": cast(str, item["path"]).replace(
                    "memory/knowledge/_unverified/", "memory/knowledge/", 1
                ),
                "trust": item.get("trust"),
                "days_old": item.get("age_days"),
                "source": item.get("source"),
            }
            for item in cast(list[dict[str, Any]], unverified["files"])
            if cast(str, item["path"]).startswith(normalized_folder.rstrip("/") + "/")
            or cast(str, item["path"]) == normalized_folder
        ]
        candidates.sort(
            key=lambda item: (
                -(cast(int | None, item.get("days_old")) or -1),
                cast(str, item["source_path"]),
            )
        )
        selected_candidates, candidate_budget = _truncate_items(candidates, max_files)
        if path_is_dir and has_nested_subdirectories:
            suggested_operation = "memory_promote_knowledge_subtree"
        elif len(candidates) <= 1:
            suggested_operation = "memory_promote_knowledge"
        else:
            suggested_operation = "memory_promote_knowledge_batch"
        suggested_target_folder = (
            normalized_folder.replace("memory/knowledge/_unverified/", "memory/knowledge/", 1)
            if normalized_folder.startswith("memory/knowledge/_unverified/")
            else None
        )
        payload = {
            "folder_path": folder_path,
            "candidate_count": len(candidates),
            "suggested_operation": suggested_operation,
            "suggested_target_folder": suggested_target_folder,
            "folder_shape": {
                "is_directory": path_is_dir,
                "has_nested_subdirectories": has_nested_subdirectories,
            },
            "workflow_hint": _route_workflow_hint(suggested_operation, normalized_folder, root),
            "selected_candidates": selected_candidates,
            "response_budget": {
                "candidates": candidate_budget,
            },
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_prepare_periodic_review
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_prepare_periodic_review",
        annotations=_tool_annotations(
            title="Prepare Periodic Review",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_prepare_periodic_review(
        max_queue_items: int = 8,
        max_deferred_targets: int = 8,
    ) -> str:
        """Return a compact periodic-review preparation bundle with bounded high-signal outputs."""
        from ..errors import ValidationError

        if max_queue_items < 1 or max_deferred_targets < 1:
            raise ValidationError("max_queue_items and max_deferred_targets must be >= 1")

        session_health = json.loads(await memory_session_health_check())
        review_payload = json.loads(await memory_run_periodic_review())
        security_candidates, security_budget = _truncate_items(
            cast(
                list[dict[str, Any]],
                review_payload["ordered_checks"]["security_flags"]["generated_candidates"],
            ),
            max_queue_items,
        )
        deferred_targets = [
            {"path": path}
            for path in cast(
                list[str], review_payload["proposed_outputs"]["deferred_write_targets"]
            )
        ]
        deferred_targets, target_budget = _truncate_items(deferred_targets, max_deferred_targets)
        overdue_files = cast(
            list[dict[str, Any]],
            review_payload["ordered_checks"]["unverified_content"]["overdue_files"],
        )
        payload = {
            "review_due": review_payload["review_due"],
            "session_health": session_health,
            "high_signal": {
                "pending_security_count": review_payload["ordered_checks"]["security_flags"][
                    "pending_count"
                ],
                "generated_security_candidates": security_candidates,
                "overdue_unverified_count": review_payload["ordered_checks"]["unverified_content"][
                    "overdue_count"
                ],
                "overdue_unverified_files": overdue_files[:max_queue_items],
                "conflict_count": review_payload["ordered_checks"]["conflict_resolution"]["count"],
            },
            "deferred_write_targets": deferred_targets,
            "recommended_operations": {
                "write": "memory_record_periodic_review",
                "queue_resolution": "memory_resolve_review_item",
            },
            "response_budget": {
                "security_candidates": security_budget,
                "deferred_targets": target_budget,
            },
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_extract_file
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_extract_file",
        annotations=_tool_annotations(
            title="Extract Structured File Content",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_extract_file(
        path: str,
        section_headings: str = "",
        max_sections: int = 5,
        preview_chars: int = 1200,
        include_outline: bool = True,
    ) -> str:
        """Return frontmatter, outline, selected sections, and bounded previews for a file.

        This is the structured alternative to temp-file fallback when a caller
        needs targeted inspection of larger Markdown files.
        """
        from ..errors import NotFoundError, ValidationError
        from ..frontmatter_utils import read_with_frontmatter

        if max_sections < 1:
            raise ValidationError("max_sections must be >= 1")
        if preview_chars < 1:
            raise ValidationError("preview_chars must be >= 1")

        repo = get_repo()
        abs_path = repo.abs_path(path)
        if not abs_path.exists() or not abs_path.is_file():
            raise NotFoundError(f"File not found: {path}")

        requested_headings = _split_csv_or_lines(section_headings)
        frontmatter, body = read_with_frontmatter(abs_path)
        content = abs_path.read_text(encoding="utf-8")
        size_bytes = len(content.encode("utf-8"))
        markdown_sections = _build_markdown_sections(body)
        matched_sections = _match_requested_sections(markdown_sections, requested_headings)
        selected_sections = matched_sections[:max_sections]
        outline = [
            {
                "heading": section["heading"],
                "level": section["level"],
                "start_line": section["start_line"],
                "anchor": section["anchor"],
            }
            for section in markdown_sections[:50]
        ]

        payload = {
            "path": path,
            "size_bytes": size_bytes,
            "frontmatter": frontmatter or None,
            "preview": body[:preview_chars],
            "selected_headings": requested_headings or None,
            "outline": outline if include_outline else None,
            "sections": [
                {
                    "heading": section["heading"],
                    "level": section["level"],
                    "start_line": section["start_line"],
                    "end_line": section["end_line"],
                    "anchor": section["anchor"],
                    "content": cast(str, section["content"])[:preview_chars],
                    "truncated": len(cast(str, section["content"])) > preview_chars,
                }
                for section in selected_sections
            ],
            "available_section_count": len(markdown_sections),
            "delivery": {
                "uses_temp_file_fallback": False,
                "preview_chars": preview_chars,
            },
        }
        return json.dumps(payload, indent=2, default=str)

    # ------------------------------------------------------------------
    # memory_get_file_provenance
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_get_file_provenance",
        annotations=_tool_annotations(
            title="File Provenance",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_get_file_provenance(path: str, history_limit: int = 10) -> str:
        """Return provenance, ACCESS history, and git history for one file."""
        from ..errors import NotFoundError
        from ..frontmatter_utils import read_with_frontmatter

        root = get_root()
        repo = get_repo()
        abs_path = repo.abs_path(path)
        if not abs_path.exists() or not abs_path.is_file():
            raise NotFoundError(f"File not found: {path}")

        frontmatter, _ = read_with_frontmatter(abs_path)
        version_token = repo.hash_object(path)
        access_entries, _ = _load_access_entries(root)
        access_summary = _build_access_summary_for_file(access_entries, path)
        commit_history = _git_file_history(repo, path, limit=history_limit)
        latest_commit = commit_history[0] if commit_history else None
        first_tracked_date = repo.first_tracked_author_date(path)
        effective_date = _effective_date(frontmatter)
        provenance_fields = _extract_provenance_fields(frontmatter)
        lineage_summary = _build_lineage_summary(path, provenance_fields)

        payload = {
            "path": path,
            "version_token": version_token,
            "tracked": first_tracked_date is not None,
            "first_tracked_date": str(first_tracked_date)
            if first_tracked_date is not None
            else None,
            "effective_date": str(effective_date) if effective_date is not None else None,
            "frontmatter": frontmatter or None,
            "provenance_fields": provenance_fields,
            "lineage_summary": lineage_summary,
            "requires_provenance_pause": _requires_provenance_pause(path, frontmatter),
            "access_summary": access_summary,
            "latest_commit": latest_commit,
            "commit_history": commit_history,
        }
        return json.dumps(payload, indent=2, default=str)

    # ------------------------------------------------------------------
    # memory_inspect_commit
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_inspect_commit",
        annotations=_tool_annotations(
            title="Inspect Commit",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_inspect_commit(sha: str) -> str:
        """Return structured metadata for a commit plus basic scope analysis."""
        repo = get_repo()
        commit = repo.inspect_commit(sha)
        metadata = _commit_metadata(repo, str(commit["sha"]))
        files_changed = [str(path) for path in cast(list[object], commit["files_changed"])]
        top_levels = sorted({_visible_top_level_category(path) for path in files_changed if path})
        message = str(commit["message"])

        payload = {
            **commit,
            **metadata,
            "requested_sha": sha,
            "recognized_prefix": _recognized_commit_prefix(message),
            "file_count": len(files_changed),
            "top_level_paths": top_levels,
            "is_head": str(commit["sha"]) == repo.current_head(),
        }
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # memory_diff
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_diff",
        annotations=_tool_annotations(
            title="Working Tree Diff Status",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_diff() -> str:
        """Show working tree status — staged, unstaged, and untracked files.

        Call before memory_commit to verify what will be included in the commit.

        Returns:
            JSON with keys staged, unstaged, untracked (each a list of paths).
        """
        repo = get_repo()
        status = repo.diff_status()
        return json.dumps(status, indent=2)

    # ------------------------------------------------------------------
    # memory_audit_trust
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_audit_trust",
        annotations=_tool_annotations(
            title="Trust Decay Audit",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_audit_trust(
        include_categories: str = "",
        warn_pct: float = 0.75,
    ) -> str:
        """Audit trust decay across the memory repository.

                Checks all files with trust frontmatter against the decay thresholds
                from the live router file, and treats files without frontmatter as
                implicit medium-trust when a git-backed effective date is available:
          - low-trust files:    overdue at 120 days, flagged at 90 days, approaching at 75%
          - medium-trust files: overdue at 180 days, flagged at 150 days, approaching at 75%
                    - frontmatterless tracked files: audited as implicit medium-trust
                    - frontmatterless untracked files: reported as unevaluable

        Does not modify any files — pure read operation.

        Args:
            include_categories: Comma-separated list of top-level folders to scan
                                 (e.g. 'knowledge,plans'). Empty = scan all.
            warn_pct: Fraction of the threshold that should surface in the
                      approaching bucket before the 30-day upcoming window.

        Returns:
            JSON with overdue/upcoming/approaching buckets plus unevaluable files,
            checked_at, and files_checked count.
        """
        from ..errors import ValidationError
        from ..frontmatter_utils import read_with_frontmatter

        if warn_pct <= 0 or warn_pct >= 1:
            raise ValidationError("warn_pct must satisfy 0 < warn_pct < 1")

        root = get_root()
        low_threshold, medium_threshold = _parse_trust_thresholds(root)
        low_warn = low_threshold - 30
        medium_warn = medium_threshold - 30

        categories = [c.strip() for c in include_categories.split(",") if c.strip()]
        if not categories:
            categories = ["knowledge", "plans", "identity", "skills"]

        today = date.today()
        overdue_low = []
        overdue_medium = []
        approaching = []
        upcoming_low = []
        upcoming_medium = []
        unevaluable = []
        files_checked = 0
        repo = get_repo()
        host_repo = _get_host_git_repo(root, repo)
        untracked_files = set(repo.diff_status()["untracked"])

        for cat in categories:
            for category_prefix in _resolve_category_prefixes(cat):
                cat_path = root / category_prefix
                if not cat_path.is_dir():
                    continue
                for md_file in cat_path.rglob("*.md"):
                    if not md_file.is_file():
                        continue
                    try:
                        fm_dict, _ = read_with_frontmatter(md_file)
                    except Exception:
                        continue

                    rel = md_file.relative_to(root).as_posix()
                    trust = fm_dict.get("trust")
                    implicit_medium = False
                    if trust in ("low", "medium", "high"):
                        pass
                    elif fm_dict:
                        continue
                    else:
                        trust = "medium"
                        implicit_medium = True

                    files_checked += 1
                    eff_date = _effective_date(fm_dict)
                    if eff_date is None and implicit_medium:
                        if rel in untracked_files:
                            unevaluable.append(
                                {
                                    "path": rel,
                                    "trust": trust,
                                    "reason": "untracked_without_frontmatter",
                                    "implicit_trust": True,
                                }
                            )
                            continue
                        eff_date = repo.first_tracked_author_date(rel)
                    if eff_date is None:
                        if implicit_medium:
                            unevaluable.append(
                                {
                                    "path": rel,
                                    "trust": trust,
                                    "reason": "missing_effective_date",
                                    "implicit_trust": True,
                                }
                            )
                        continue

                    days = (today - eff_date).days

                    entry = {
                        "path": rel,
                        "trust": trust,
                        "effective_date": str(eff_date),
                        "days_since_verified": days,
                    }
                    if implicit_medium:
                        entry["implicit_trust"] = True

                    freshness_report = None
                    freshness_status = "unknown"
                    if host_repo is not None:
                        freshness_report = _build_knowledge_freshness_report(
                            root, repo, rel, md_file
                        )
                        freshness_status = str(freshness_report["status"])
                        for key in (
                            "current_head",
                            "verified_against_commit",
                            "host_changes_since",
                            "source_files",
                        ):
                            if freshness_report.get(key) is not None:
                                entry[key] = freshness_report[key]
                        entry["freshness_status"] = freshness_status

                    if trust == "low":
                        threshold = low_threshold
                        warn = low_warn
                        approaching_warn = threshold * warn_pct
                        entry["days_until_threshold"] = max(0, threshold - days)
                        if days >= threshold:
                            if freshness_status == "fresh":
                                entry["action_required"] = "review"
                                upcoming_low.append(entry)
                            else:
                                entry["action_required"] = "archive"
                                overdue_low.append(entry)
                        elif days >= warn or freshness_status == "stale":
                            entry["action_required"] = "review"
                            upcoming_low.append(entry)
                        elif days >= approaching_warn:
                            entry["action_required"] = "review"
                            approaching.append(entry)
                    elif trust == "medium":
                        threshold = medium_threshold
                        warn = medium_warn
                    approaching_warn = threshold * warn_pct
                    entry["days_until_threshold"] = max(0, threshold - days)
                    if days >= threshold:
                        if freshness_status == "fresh":
                            entry["action_required"] = "review"
                            upcoming_medium.append(entry)
                        else:
                            entry["action_required"] = "flag"
                            overdue_medium.append(entry)
                    elif days >= warn or freshness_status == "stale":
                        entry["action_required"] = (
                            "reverify" if freshness_status == "stale" else "review"
                        )
                        upcoming_medium.append(entry)
                    elif days >= approaching_warn:
                        entry["action_required"] = "review"
                        approaching.append(entry)

        result = {
            "overdue_low": overdue_low,
            "overdue_medium": overdue_medium,
            "approaching": approaching,
            "upcoming_low": upcoming_low,
            "upcoming_medium": upcoming_medium,
            "unevaluable": unevaluable,
            "checked_at": str(today),
            "files_checked": files_checked,
            "thresholds": {
                "low_days": low_threshold,
                "medium_days": medium_threshold,
                "warn_pct": warn_pct,
            },
        }
        return json.dumps(result, indent=2)

    # ------------------------------------------------------------------
    # memory_validate
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_validate",
        annotations=_tool_annotations(
            title="Validate Memory Repository",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_validate() -> str:
        """Run the structural validator against the memory repository.

        Checks frontmatter keys, ACCESS.jsonl structure, and governance
        consistency. Returns a validation report.

        Returns:
            Validation report with errors and warnings, or a clean-pass message.
        """
        root = get_root()
        validator_path = root / "HUMANS" / "tooling" / "scripts" / "validate_memory_repo.py"
        if not validator_path.exists():
            return "Validator not found at HUMANS/tooling/scripts/validate_memory_repo.py"
        try:
            result = subprocess.run(
                [sys.executable, str(validator_path), str(root)],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=30,
                stdin=subprocess.DEVNULL,
            )
            output = result.stdout + result.stderr
            return output.strip() or "Validation complete (no output)."
        except subprocess.TimeoutExpired:
            return "Error: Validator timed out after 30 seconds."
        except Exception as e:
            return f"Error running validator: {e}"

    # ------------------------------------------------------------------
    # memory_get_maturity_signals
    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_get_maturity_signals",
        annotations=_tool_annotations(
            title="Maturity Signals",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_get_maturity_signals() -> str:
        """Compute all six maturity signals for the periodic review.

        These signals drive the maturity stage assessment in
        governance/system-maturity.md and determine whether to retain the current
        parameter set or transition to the next stage. All values are derived
        from hot ACCESS.jsonl files and content-file frontmatter; archive
        segments and ACCESS_SCANS sidecars are excluded, and no network calls
        are made.

        Returns:
            JSON with the following keys:
              access_scope            (str)   Always "hot_only"; archive
                                              segments and ACCESS_SCANS sidecars
                                              are excluded from these metrics
              total_sessions          (int)   Distinct session_id values across
                                              hot ACCESS.jsonl files
              session_id_coverage_pct (float) % of hot ACCESS entries carrying
                                              canonical session_id values
              access_density          (int)   Total ACCESS.jsonl entries across
                                              hot logs across all folders
              file_coverage_pct       (float) % of content files accessed at
                                              least once (0–100)
              files_accessed          (int)   Count of distinct files in
                                              ACCESS.jsonl entries
              total_content_files     (int)   Total .md files in memory/knowledge,
                                              memory/working/projects,
                                              memory/users, memory/skills
              confirmation_ratio      (float) trust:high files / total content
                                              files (0.0–1.0)
              high_trust_files        (int)   Count of trust:high content files
              identity_stability      (int|null)
                                              Sessions since last change to
                                              memory/users/profile.md; null if the
                                              file has no tracked commit history
              write_sessions         (int)   Distinct session_id values with at
                                              least one non-read ACCESS entry
              access_density_by_task_id (dict) ACCESS entry counts grouped by
                                              task_id bucket; entries without
                                              task_id are grouped under
                                              "unspecified"
              proxy_sessions         (int)   Optional fallback estimate based on
                                              distinct (date, task_id or task)
                                              pairs when session_id coverage is low
              proxy_session_note     (str)   Optional warning describing when
                                              proxy_sessions was emitted
              mean_helpfulness        (float) Mean helpfulness score across all
                                              ACCESS entries that carry the field
              helpfulness_sample_size (int)   Number of entries with a
                                              helpfulness score
              computed_at             (str)   ISO date of computation
        """
        root = get_root()
        repo = get_repo()
        signals = _compute_maturity_signals(root, repo)
        return json.dumps(signals, indent=2)

    # ------------------------------------------------------------------
    # MCP-native resources
    # ------------------------------------------------------------------
    @mcp.resource(
        "memory://capabilities/summary",
        name="memory_capability_summary",
        title="Capability Summary Resource",
        description="Compact governed capability and profile summary.",
        mime_type="application/json",
    )
    async def memory_capability_summary_resource() -> str:
        root = get_root()
        manifest, error_payload = _load_capabilities_manifest(root)
        if error_payload is not None:
            return json.dumps(error_payload, indent=2)

        manifest_dict = cast(dict[str, Any], manifest)
        payload = {
            "summary": _build_capabilities_summary(manifest_dict),
            "tool_profiles": _build_tool_profile_payload(manifest_dict),
        }
        return json.dumps(payload, indent=2)

    @mcp.resource(
        "memory://policy/summary",
        name="memory_policy_summary",
        title="Policy Summary Resource",
        description="Stable change-class, fallback, and surface-boundary summary.",
        mime_type="application/json",
    )
    async def memory_policy_summary_resource() -> str:
        root = get_root()
        manifest, error_payload = _load_capabilities_manifest(root)
        if error_payload is not None:
            return json.dumps(error_payload, indent=2)

        payload = _build_policy_summary_payload(cast(dict[str, Any], manifest))
        return json.dumps(payload, indent=2)

    @mcp.resource(
        "memory://session/health",
        name="memory_session_health_resource",
        title="Session Health Resource",
        description="Session-start maintenance and review-health snapshot.",
        mime_type="application/json",
    )
    async def memory_session_health_resource() -> str:
        return await memory_session_health_check()

    @mcp.resource(
        "memory://plans/active",
        name="memory_active_plans_resource",
        title="Active Plans Resource",
        description="Compact summary of active plans and next actions.",
        mime_type="application/json",
    )
    async def memory_active_plans_resource() -> str:
        root = get_root()
        payload = _build_active_plan_summary_payload(root)
        return json.dumps(payload, indent=2)

    # ------------------------------------------------------------------
    # MCP-native prompts
    # ------------------------------------------------------------------
    @mcp.prompt(
        name="memory_prepare_unverified_review_prompt",
        title="Prepare Unverified Review Prompt",
        description="Guide a host through compact unverified-review preparation.",
    )
    async def memory_prepare_unverified_review_prompt(
        folder_path: str = "memory/knowledge/_unverified",
        max_files: int = 12,
        max_extract_words: int = 60,
    ) -> str:
        bundle = json.loads(
            await memory_prepare_unverified_review(
                folder_path=folder_path,
                max_files=max_files,
                max_extract_words=max_extract_words,
            )
        )
        sections = [
            "Guide the user through reviewing low-trust knowledge before any promotion write.",
            "Surface the highest-signal files first, call out expired items, and recommend the narrowest valid promotion operation.",
            _prompt_json_section("Review Bundle", bundle),
            "When the user is ready to act, use memory_promote_knowledge for one file, memory_promote_knowledge_batch for flat multi-file promotion, or memory_promote_knowledge_subtree when nested paths should be preserved.",
        ]
        return "\n\n".join(sections)

    @mcp.prompt(
        name="memory_governed_promotion_preview_prompt",
        title="Governed Promotion Preview Prompt",
        description="Structure a governed knowledge-promotion preview conversation.",
    )
    async def memory_governed_promotion_preview_prompt(
        folder_path: str = "memory/knowledge/_unverified",
        max_files: int = 12,
    ) -> str:
        bundle = json.loads(
            await memory_prepare_promotion_batch(
                folder_path=folder_path,
                max_files=max_files,
            )
        )
        sections = [
            "Use this prompt to prepare a governed promotion preview before any knowledge mutation.",
            "Confirm candidate paths, target paths, and whether the operation should stay single-file or batch-shaped. If the user approves, follow with the semantic write tool in preview mode first when available.",
            _prompt_json_section("Promotion Candidates", bundle),
        ]
        return "\n\n".join(sections)

    @mcp.prompt(
        name="memory_prepare_periodic_review_prompt",
        title="Prepare Periodic Review Prompt",
        description="Guide a protected periodic-review workflow using the compact preparation bundle.",
    )
    async def memory_prepare_periodic_review_prompt(
        max_queue_items: int = 8,
        max_deferred_targets: int = 8,
    ) -> str:
        bundle = json.loads(
            await memory_prepare_periodic_review(
                max_queue_items=max_queue_items,
                max_deferred_targets=max_deferred_targets,
            )
        )
        sections = [
            "Use this prompt to walk the user through the protected periodic-review workflow without applying writes prematurely.",
            "Summarize the due-state, review queue pressure, and deferred write targets. Only call memory_record_periodic_review after the user confirms the protected update.",
            _prompt_json_section("Periodic Review Bundle", bundle),
        ]
        return "\n\n".join(sections)

    @mcp.prompt(
        name="memory_session_wrap_up_prompt",
        title="Session Wrap-Up Prompt",
        description="Guide end-of-session summary, reflection, and deferred follow-up capture.",
    )
    async def memory_session_wrap_up_prompt(
        session_id: str = "",
        key_topics: str = "",
    ) -> str:
        root = get_root()
        active_plans, _ = _truncate_items(_collect_plan_entries(root, status="active"), 3)
        payload = {
            "session_id": session_id or None,
            "key_topics": _split_csv_or_lines(key_topics) if key_topics.strip() else [],
            "active_plans": active_plans,
            "target_tool": "memory_record_session",
            "recommended_fields": [
                "summary",
                "reflection",
                "key_topics",
                "access_entries",
            ],
        }
        sections = [
            "Use this prompt to prepare an end-of-session record before calling memory_record_session.",
            "Capture what changed, what was learned, which plans advanced, and any deferred actions that should persist into the next session.",
            _prompt_json_section("Session Wrap-Up Context", payload),
        ]
        return "\n\n".join(sections)

    return {
        "memory_get_capabilities": memory_get_capabilities,
        "memory_get_tool_profiles": memory_get_tool_profiles,
        "memory_get_policy_state": memory_get_policy_state,
        "memory_route_intent": memory_route_intent,
        "memory_read_file": memory_read_file,
        "memory_list_folder": memory_list_folder,
        "memory_review_unverified": memory_review_unverified,
        "memory_search": memory_search,
        "memory_find_references": memory_find_references,
        "memory_validate_links": memory_validate_links,
        "memory_reorganize_preview": memory_reorganize_preview,
        "memory_suggest_structure": memory_suggest_structure,
        "memory_check_cross_references": memory_check_cross_references,
        "memory_surface_unlinked": memory_surface_unlinked,
        "memory_generate_summary": memory_generate_summary,
        "memory_access_analytics": memory_access_analytics,
        "memory_diff_branch": memory_diff_branch,
        "memory_git_log": memory_git_log,
        "memory_session_health_check": memory_session_health_check,
        "memory_session_bootstrap": memory_session_bootstrap,
        "memory_prepare_unverified_review": memory_prepare_unverified_review,
        "memory_prepare_promotion_batch": memory_prepare_promotion_batch,
        "memory_prepare_periodic_review": memory_prepare_periodic_review,
        "memory_extract_file": memory_extract_file,
        "memory_check_knowledge_freshness": memory_check_knowledge_freshness,
        "memory_check_aggregation_triggers": memory_check_aggregation_triggers,
        "memory_aggregate_access": memory_aggregate_access,
        "memory_run_periodic_review": memory_run_periodic_review,
        "memory_get_file_provenance": memory_get_file_provenance,
        "memory_inspect_commit": memory_inspect_commit,
        "memory_diff": memory_diff,
        "memory_audit_trust": memory_audit_trust,
        "memory_validate": memory_validate,
        "memory_get_maturity_signals": memory_get_maturity_signals,
    }
