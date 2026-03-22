"""Enhanced agent-memory MCP package.

The package root stays importable without `mcp` installed. Runtime exports are
resolved lazily so callers that only need the format-layer helpers can import
`engram_mcp.agent_memory_mcp.core` without pulling in the MCP server.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["GIT_REPO", "REPO_ROOT", "TOOLS", "core", "create_mcp", "mcp"]


def __getattr__(name: str) -> Any:
    if name == "core":
        return import_module(".core", __name__)
    if name in {"GIT_REPO", "REPO_ROOT", "TOOLS", "create_mcp", "mcp"}:
        server = import_module(".server", __name__)
        return getattr(server, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
