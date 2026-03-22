"""Phase 3 semantic tool package.

This package is the stable import surface for Tier 1 semantic tools.
"""

from __future__ import annotations

from . import (
    _session,
    knowledge_tools,
    plan_tools,
    session_tools,
    skill_tools,
    user_tools,
)


def register(mcp, get_repo, get_root):
    """Register semantic tools through the package surface."""

    session_state = _session.create_session_state()
    tools = {}
    tools.update(_session.register_tools(mcp, session_state))
    tools.update(plan_tools.register_tools(mcp, get_repo, get_root))
    tools.update(knowledge_tools.register_tools(mcp, get_repo, get_root))
    tools.update(user_tools.register_tools(mcp, get_repo, session_state))
    tools.update(skill_tools.register_tools(mcp, get_repo))
    tools.update(session_tools.register_tools(mcp, get_repo, get_root))
    return tools


__all__ = [
    "register",
    "_session",
    "plan_tools",
    "knowledge_tools",
    "user_tools",
    "skill_tools",
    "session_tools",
]
