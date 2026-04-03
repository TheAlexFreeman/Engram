"""Phase 3 semantic tool package.

This package is the stable import surface for Tier 1 semantic tools.
"""

from __future__ import annotations

from ...session_state import SessionState, create_session_state
from . import (
    _session,
    graph_tools,
    knowledge_tools,
    plan_tools,
    search_tools,
    session_tools,
    skill_tools,
    user_tools,
)


def register(mcp, get_repo, get_root, session_state: SessionState | None = None):
    """Register semantic tools through the package surface."""

    if session_state is None:
        session_state = create_session_state()
    tools = {}
    tools.update(_session.register_tools(mcp, session_state))
    tools.update(plan_tools.register_tools(mcp, get_repo, get_root))
    tools.update(knowledge_tools.register_tools(mcp, get_repo, get_root))
    tools.update(user_tools.register_tools(mcp, get_repo, session_state))
    tools.update(skill_tools.register_tools(mcp, get_repo))
    tools.update(session_tools.register_tools(mcp, get_repo, get_root, session_state=session_state))
    tools.update(graph_tools.register_tools(mcp, get_repo, get_root))
    tools.update(search_tools.register_tools(mcp, get_repo, get_root))
    return tools


__all__ = [
    "register",
    "_session",
    "graph_tools",
    "plan_tools",
    "knowledge_tools",
    "search_tools",
    "user_tools",
    "skill_tools",
    "session_tools",
]
