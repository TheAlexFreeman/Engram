"""Session-state helpers and tool registration for semantic tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ...response_envelope import dump_tool_result
from ...session_state import SessionState, create_session_state

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


_IDENTITY_CHURN_LIMIT = 5


def get_identity_churn_limit() -> int:
    return _IDENTITY_CHURN_LIMIT


def get_identity_updates(session_state: SessionState) -> int:
    return session_state.identity_updates


def increment_identity_updates(session_state: SessionState) -> int:
    session_state.identity_updates += 1
    return session_state.identity_updates


def reset_session_state(session_state: SessionState) -> dict[str, object]:
    return session_state.reset()


def _tool_annotations(**kwargs: object) -> Any:
    return cast(Any, kwargs)


def register_tools(mcp: "FastMCP", session_state: SessionState) -> dict[str, object]:
    """Register session-scoped semantic tools backed by a shared state object."""

    @mcp.tool(
        name="memory_reset_session_state",
        annotations=_tool_annotations(
            title="Reset Per-Session State",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def memory_reset_session_state() -> str:
        """Reset per-session counters and advisory state to their initial values.

        Call this at the start of each new session to ensure a clean slate,
        particularly in long-running MCP server processes where the server is
        not restarted between sessions.

        Use memory_tool_schema with tool_name="memory_reset_session_state" for
        the explicit no-argument contract.

        Returns:
            JSON envelope with the reset state in result and compact
            session metadata in _session.
        """
        return dump_tool_result(reset_session_state(session_state), session_state)

    return {"memory_reset_session_state": memory_reset_session_state}


__all__ = [
    "SessionState",
    "create_session_state",
    "get_identity_churn_limit",
    "get_identity_updates",
    "increment_identity_updates",
    "register_tools",
    "reset_session_state",
]
