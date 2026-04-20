from __future__ import annotations
from harness.tools import Tool


_IDENTITY = """You are a coding assistant operating on a local workspace via tools. \
You work one step at a time, verify your changes, and prefer small precise edits over large rewrites."""

_RULES = """Rules:
- Read before you edit. Always inspect a file's current contents before editing it.
- Use exact strings in edit_file.old_str. If it fails, re-read the file and try again.
- Prefer path_stat or glob_files before reading huge directories or unknown file sizes; use read_file offset/limit or line_start/line_end for large files.
- Use write_file only for intentional full-file writes or creates; prefer edit_file for small surgical edits.
- delete_path and move_path require confirm: true; never assume destructive calls succeeded without checking tool results.
- If you don't know, say so. Do not invent file contents.
- Use web_search for external docs or facts not in the workspace; prefer local file tools for repository code.
- When multiple independent tool calls are needed, emit them together in a single response; the harness executes them concurrently."""

_OUTPUT_NATIVE = (
    """When you are done, respond with a plain-text summary of what you did."""
)

_OUTPUT_TEXT = """To call a tool, emit EXACTLY one line:
    tool: TOOL_NAME({"arg": "value"})
Use compact JSON with double quotes. No prose on tool-call lines.
When you are done, respond with a plain-text summary and no tool lines."""


def _render_tool(tool: Tool) -> str:
    import json

    schema = json.dumps(tool.input_schema, indent=2)
    return (
        f"### {tool.name}\n{tool.description}\n\nInput schema:\n```json\n{schema}\n```"
    )


def system_prompt_native() -> str:
    return f"{_IDENTITY}\n\n{_RULES}\n\n{_OUTPUT_NATIVE}"


def system_prompt_text(tools: dict[str, Tool]) -> str:
    tool_docs = "\n\n".join(_render_tool(t) for t in tools.values())
    return f"{_IDENTITY}\n\n## Tools\n\n{tool_docs}\n\n{_RULES}\n\n{_OUTPUT_TEXT}"
