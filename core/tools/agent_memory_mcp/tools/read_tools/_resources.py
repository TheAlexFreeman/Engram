"""Read tools — MCP resources and prompts submodule."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_resources(
    mcp: "FastMCP",
    get_repo,
    get_root,
    H,
    *,
    tools: dict[str, object],
) -> None:
    """Register MCP-native resources and prompts."""
    memory_prepare_unverified_review = cast(Any, tools["memory_prepare_unverified_review"])
    memory_prepare_promotion_batch = cast(Any, tools["memory_prepare_promotion_batch"])
    memory_prepare_periodic_review = cast(Any, tools["memory_prepare_periodic_review"])
    _build_session_health_payload = cast(Any, tools["_build_session_health_payload"])

    def _dump_resource_payload(payload: Any) -> str:
        return json.dumps(payload, indent=2)

    def _load_tool_payload(raw: str) -> dict[str, Any]:
        payload = cast(dict[str, Any], json.loads(raw))
        result = payload.get("result")
        if isinstance(result, dict) and "_session" in payload:
            return cast(dict[str, Any], result)
        return payload

    def _load_manifest_resource_payload() -> tuple[dict[str, Any] | None, str | None]:
        manifest, error_payload = _load_capabilities_manifest(get_root())
        if error_payload is not None:
            return None, _dump_resource_payload(error_payload)
        return cast(dict[str, Any], manifest), None

    _build_active_plan_summary_payload = H._build_active_plan_summary_payload
    _build_capabilities_summary = H._build_capabilities_summary
    _build_policy_summary_payload = H._build_policy_summary_payload
    _build_tool_profile_payload = H._build_tool_profile_payload
    _collect_plan_entries = H._collect_plan_entries
    _list_registered_tool_names = H._list_registered_tool_names
    _load_capabilities_manifest = H._load_capabilities_manifest
    _prompt_json_section = H._prompt_json_section
    _split_csv_or_lines = H._split_csv_or_lines
    _truncate_items = H._truncate_items

    # ------------------------------------------------------------------
    @mcp.resource(
        "memory://capabilities/summary",
        name="memory_capability_summary",
        title="Capability Summary Resource",
        description="Compact governed capability and profile summary.",
        mime_type="application/json",
    )
    async def memory_capability_summary_resource() -> str:
        manifest_dict, error_json = _load_manifest_resource_payload()
        if error_json is not None:
            return error_json

        runtime_tool_names = await _list_registered_tool_names(mcp)
        payload = {
            "summary": _build_capabilities_summary(
                cast(dict[str, Any], manifest_dict),
                runtime_tool_names=runtime_tool_names,
            ),
            "tool_profiles": _build_tool_profile_payload(cast(dict[str, Any], manifest_dict)),
        }
        return _dump_resource_payload(payload)

    @mcp.resource(
        "memory://policy/summary",
        name="memory_policy_summary",
        title="Policy Summary Resource",
        description="Stable change-class, fallback, and surface-boundary summary.",
        mime_type="application/json",
    )
    async def memory_policy_summary_resource() -> str:
        manifest_dict, error_json = _load_manifest_resource_payload()
        if error_json is not None:
            return error_json

        payload = _build_policy_summary_payload(cast(dict[str, Any], manifest_dict))
        return _dump_resource_payload(payload)

    @mcp.resource(
        "memory://session/health",
        name="memory_session_health_resource",
        title="Session Health Resource",
        description="Session-start maintenance and review-health snapshot.",
        mime_type="application/json",
    )
    async def memory_session_health_resource() -> str:
        return _dump_resource_payload(_build_session_health_payload())

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
        return _dump_resource_payload(payload)

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
        bundle = _load_tool_payload(
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
        bundle = _load_tool_payload(
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
        bundle = _load_tool_payload(
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
