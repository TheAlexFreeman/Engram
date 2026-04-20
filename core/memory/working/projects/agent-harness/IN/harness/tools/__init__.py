from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    id: str | None = None  # native mode sets this; text mode leaves it None


@dataclass
class ToolResult:
    call: ToolCall
    content: str
    is_error: bool = False


class Tool(Protocol):
    name: str
    description: str
    input_schema: dict

    def run(self, args: dict) -> str: ...


def execute(call: ToolCall, registry: dict[str, Tool]) -> ToolResult:
    """Single point of execution. Errors become results, never exceptions."""
    tool = registry.get(call.name)
    if tool is None:
        return ToolResult(
            call=call,
            content=f"Unknown tool: {call.name}. Available: {sorted(registry)}",
            is_error=True,
        )
    try:
        content = tool.run(call.args)
        return ToolResult(call=call, content=content, is_error=False)
    except Exception as e:
        import traceback

        return ToolResult(
            call=call,
            content=f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}",
            is_error=True,
        )
