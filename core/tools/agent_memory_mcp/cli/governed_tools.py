"""Helpers for CLI commands that proxy governed semantic tools."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, cast

ToolCallable = Callable[..., Coroutine[Any, Any, str]]


def invoke_semantic_tool(repo_root: Path, tool_name: str, **kwargs: Any) -> dict[str, Any]:
    from ..server import create_mcp

    _mcp, tools, _root, _repo = create_mcp(repo_root=repo_root)
    tool = tools.get(tool_name)
    if not callable(tool):
        raise ValueError(f"Semantic tool unavailable: {tool_name}")

    raw_result = asyncio.run(cast(ToolCallable, tool)(**kwargs))
    payload = json.loads(raw_result)
    if not isinstance(payload, dict):
        raise ValueError(f"Semantic tool returned a non-object payload: {tool_name}")
    return payload
