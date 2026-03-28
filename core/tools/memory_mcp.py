#!/usr/bin/env python3
"""Compatibility entrypoint for the repo-local Engram MCP server.

Prefer the installed ``engram-mcp`` CLI or
``python -m engram_mcp.agent_memory_mcp.server_main`` when available. This
wrapper remains for path-based client configs that launch the server directly
from a repository checkout.
"""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent  # core/tools/

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# When the package is pip-installed, the setuptools package-dir mapping makes
# ``import engram_mcp`` resolve to core/tools/.  When running as a standalone
# script in a Python that lacks the install, we replicate that mapping manually
# so sub-imports (engram_mcp.agent_memory_mcp.*) still work.
try:
    import_module("engram_mcp")
except ImportError:
    import types

    _pkg = types.ModuleType("engram_mcp")
    _pkg.__path__ = [str(SCRIPT_DIR)]
    _pkg.__file__ = str(SCRIPT_DIR / "__init__.py")
    sys.modules["engram_mcp"] = _pkg

_server = import_module("engram_mcp.agent_memory_mcp.server")

mcp = _server.mcp  # triggers lazy initialization
TOOLS = _server.TOOLS
__all__ = ["mcp", "TOOLS", *sorted(TOOLS)]
globals().update(TOOLS)


if __name__ == "__main__":
    mcp.run()
