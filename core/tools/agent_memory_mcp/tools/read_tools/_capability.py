"""Read tools — capability submodule."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ...errors import ValidationError
from ...response_envelope import dump_tool_result
from ...tool_schemas import get_tool_input_schema

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from ...session_state import SessionState


def register_capability(
    mcp: "FastMCP",
    get_repo,
    get_root,
    H,
    session_state: "SessionState | None" = None,
) -> dict[str, object]:
    """Register capability read tools and return their callables."""
    _build_capabilities_summary = H._build_capabilities_summary
    _build_policy_state_payload = H._build_policy_state_payload
    _build_tool_profile_payload = H._build_tool_profile_payload
    _list_registered_tool_names = H._list_registered_tool_names
    _load_capabilities_manifest = H._load_capabilities_manifest
    _normalize_repo_relative_path = H._normalize_repo_relative_path
    _route_intent_candidates = H._route_intent_candidates
    _route_workflow_hint = H._route_workflow_hint
    _tool_annotations = H._tool_annotations

    def _dump_payload(payload: Any, *, default: Any | None = str) -> str:
        if session_state is not None:
            session_state.record_tool_call()
        return dump_tool_result(payload, session_state, indent=2, default=default)

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
            return _dump_payload(error_payload)

        payload = dict(cast(dict[str, Any], manifest))
        runtime_tool_names = await _list_registered_tool_names(mcp)
        payload["summary"] = _build_capabilities_summary(
            payload,
            runtime_tool_names=runtime_tool_names,
        )
        return _dump_payload(payload)

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
            return _dump_payload(error_payload)

        payload = _build_tool_profile_payload(cast(dict[str, Any], manifest))
        return _dump_payload(payload)

    # ------------------------------------------------------------------
    # memory_tool_schema

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_tool_schema",
        annotations=_tool_annotations(
            title="Get Tool Input Schema",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_tool_schema(tool_name: str) -> str:
        """Return the structured input schema for tools in the shared registry.

        The registry in ``core/tools/agent_memory_mcp/tool_schemas.py`` covers
        Tier 1 semantic tools (nested dicts, enums, preview tokens), Tier 2 raw
        tools when enabled, and selected Tier 0 tools whose parameters benefit
        from explicit JSON Schema (for example context injectors and
        ``memory_read_file``). Remaining Tier 0 tools rely on FastMCP-generated
        schemas from their Python signatures only; calling this tool for those
        names raises ``ValidationError`` with the list of registry tool names.

        Use ``memory_plan_schema`` for the full ``memory_plan_create`` contract
        without naming the tool, or pass ``tool_name="memory_plan_create"`` here.
        """

        return _dump_payload(get_tool_input_schema(tool_name))

    # ------------------------------------------------------------------
    # memory_plan_schema

    # ------------------------------------------------------------------
    @mcp.tool(
        name="memory_plan_schema",
        annotations=_tool_annotations(
            title="Get Plan Create Schema",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_plan_schema() -> str:
        """Return the nested input schema for memory_plan_create as structured JSON.

        Use this when a caller needs the full phases/sources/postconditions/changes
        contract, including canonical enum values, conditional requirements, and
        the small alias set normalized by the plan coercion layer.
        """

        return _dump_payload(get_tool_input_schema("memory_plan_create"))

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

        root = get_root()
        manifest, error_payload = _load_capabilities_manifest(root)
        if error_payload is not None:
            return _dump_payload(error_payload)

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
        return _dump_payload(payload)

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

        if not intent.strip():
            raise ValidationError("intent must be a non-empty string")

        root = get_root()
        manifest, error_payload = _load_capabilities_manifest(root)
        if error_payload is not None:
            return _dump_payload(error_payload)

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
            recommended_item = candidates[0]
            recommended = recommended_item
            alternatives = candidates[1:4]
            primary_score = cast(float, recommended_item["score"])
            ambiguous = bool(
                alternatives and abs(primary_score - cast(float, alternatives[0]["score"])) < 0.03
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

        return _dump_payload(
            {
                "intent": intent,
                "path": normalized_path,
                "recommended_operation": recommended,
                "alternatives": alternatives,
                "ambiguous": ambiguous,
                "workflow_hint": workflow_hint,
                "policy_state": policy_state,
            },
        )

    # ------------------------------------------------------------------
    # memory_read_file

    return {
        "memory_get_capabilities": memory_get_capabilities,
        "memory_get_tool_profiles": memory_get_tool_profiles,
        "memory_tool_schema": memory_tool_schema,
        "memory_plan_schema": memory_plan_schema,
        "memory_get_policy_state": memory_get_policy_state,
        "memory_route_intent": memory_route_intent,
    }
