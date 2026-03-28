"""
Tier 0 — Enhanced read tools.

Split into submodules for maintainability; this package re-exports the
same ``register()`` entry point consumed by the MCP server.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

# Re-export for callers that import KNOWN_COMMIT_PREFIXES from read_tools
from ._helpers import KNOWN_COMMIT_PREFIXES  # noqa: F401


def register(mcp: "FastMCP", get_repo, get_root) -> dict[str, object]:
    """Register all Tier 0 read tools and return their callables."""
    from . import _helpers as H
    from ._capability import register_capability
    from ._generation import register_generation
    from ._git import register_git
    from ._health import register_health
    from ._inspection import register_inspection
    from ._links import register_links
    from ._resources import register_resources
    from ._search import register_search

    result: dict[str, object] = {}
    result.update(register_capability(mcp, get_repo, get_root, H))
    result.update(register_inspection(mcp, get_repo, get_root, H))
    result.update(register_search(mcp, get_repo, get_root, H))
    result.update(register_links(mcp, get_repo, get_root, H))
    result.update(register_generation(mcp, get_repo, get_root, H))
    result.update(register_git(mcp, get_repo, get_root, H))
    result.update(register_health(mcp, get_repo, get_root, H, tools=result))
    register_resources(mcp, get_repo, get_root, H, tools=result)
    return result
