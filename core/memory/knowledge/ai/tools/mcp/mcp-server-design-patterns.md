---
source: external-research
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
origin_session: core/memory/activity/2026/03/19/chat-002
topic: mcp-protocol
related: mcp-protocol-overview.md, mcp-2026-roadmap-update.md, mcp-ecosystem-survey.md, ../../../software-engineering/ai-engineering/agent-configuration-and-tooling.md
---

# MCP Server Design Patterns — Practical Build Guide

**Source**: Synthesized from [modelcontextprotocol.io](https://modelcontextprotocol.io) docs, Python SDK docs, and operational experience building the agent_memory MCP server in this repo. Fetched 2026-03-19.

---

## FastMCP (Python) — the recommended entry point

`FastMCP` is the high-level Python framework for building MCP servers. It is part of the `mcp` package maintained by Anthropic. It handles server registration, JSON Schema generation from type hints, transport negotiation, and lifecycle management.

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-server")  # name appears in serverInfo during init

@mcp.tool()
async def search_documents(query: str, limit: int = 10) -> str:
    """Search documents matching the query. Returns JSON array of matches.

    Use this when the user asks to find or look up information in the document store.
    Prefer over read_document when you need to discover what exists.
    """
    results = await do_search(query, limit)
    return json.dumps(results)

@mcp.resource("docs://{doc_id}")
async def get_document(doc_id: str) -> str:
    """Full text of a document by ID."""
    return await fetch_document(doc_id)

if __name__ == "__main__":
    mcp.run()  # defaults to stdio transport
```

To run with HTTP transport: `mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)`

---

## Tool design

### Naming conventions

Use namespaced snake_case. The de facto convention across the ecosystem:
```
{server}_{verb}_{noun}
memory_read_file
github_create_issue
filesystem_list_directory
```

Keep names under 64 characters. Consistent prefix across all tools in a server makes the registry scannable.

### Description quality — the #1 factor in usability

The `description` field is the LLM's **only** signal for tool selection. It receives no other information about your tool unless it's in the description. A weak description causes the LLM to call the wrong tool, miss the right tool, or call it with wrong arguments.

Good description structure:
1. One-line summary (what it does)
2. When to use it (trigger conditions)
3. What it does NOT do (disambiguation from similar tools)
4. Key parameter notes (especially non-obvious ones)

```python
@mcp.tool()
async def memory_search(query: str, max_results: int = 20) -> str:
    """Full-text search across all memory files.

    Use this to find files containing a specific term, concept, or phrase when
    you don't know which file contains the information. Returns file paths and
    matching lines with line numbers.

    Do NOT use this for reading a file you already know the path to — use
    memory_read_file instead. Do NOT use for listing folder contents — use
    memory_list_folder.

    max_results: cap on returned matches (not files). Set higher for broad sweeps.
    """
```

### Input schema design

FastMCP generates JSON Schema from type hints automatically. For manual schema (TypeScript SDK):
```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "Repo-relative path to the file"
    },
    "mode": {
      "type": "string",
      "enum": ["upsert", "append", "replace"],
      "default": "upsert"
    }
  },
  "required": ["path"],
  "additionalProperties": false
}
```

Use `additionalProperties: false` to prevent injection through extra keys. Use enums for constrained choices — they appear in the schema and help the LLM pick the right value.

### Result design

Return one of:
- A **JSON string** for programmatic data (parse with `json.loads`)
- A **human-readable string** for display
- Both in a structured envelope: `json.dumps({"summary": "...", "data": [...]})`

Keep results under ~4KB. Verbose results consume context budget and can cause the model to lose track of its goal. If you have large data, return a summary + pointer, not the raw content.

For errors: prefer returning `isError: true` content over raising exceptions. Unhandled exceptions become opaque `InternalError` responses.

```python
# Tool-level error (expected failures)
return json.dumps({"error": "File not found", "path": path})
# Return this block as the tool result — most clients surface it to the model

# Protocol-level error (unexpected failures) — raise only for unrecoverable states
from mcp.types import McpError, ErrorCode
raise McpError(ErrorCode.INTERNAL_ERROR, "Database connection failed")
```

### Tool annotations

Add annotations to help clients enforce safety policies and show appropriate UIs:
```python
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool

@mcp.tool(annotations={"readOnlyHint": True})
async def read_only_tool(path: str) -> str:
    ...

@mcp.tool(annotations={"destructiveHint": True, "idempotentHint": False})
async def delete_file(path: str) -> str:
    ...
```

---

## Safety and security

### Path traversal prevention

For any tool accepting file paths, validate strictly:
```python
import pathlib

def validate_path(path: str, allowed_root: str) -> pathlib.Path:
    resolved = (pathlib.Path(allowed_root) / path).resolve()
    allowed = pathlib.Path(allowed_root).resolve()
    if not str(resolved).startswith(str(allowed)):
        raise ValueError(f"Path traversal attempt: {path}")
    return resolved
```

Never pass user-supplied `path` directly to `open()` or `subprocess.run()`.

### Subprocess stdin inheritance (stdio servers)

**Critical for stdio-mode servers**: when the MCP server is launched over stdio, its stdin IS the JSON-RPC transport pipe. Any child subprocess that inherits stdin can consume protocol bytes, causing apparent tool timeouts or silent failures.

```python
import subprocess

# WRONG — child inherits stdin from MCP server
result = subprocess.run(["git", "log"], capture_output=True)

# CORRECT — explicitly block stdin inheritance
result = subprocess.run(
    ["git", "log"],
    stdin=subprocess.DEVNULL,  # <-- required in stdio MCP servers
    capture_output=True,
    text=True,
)
```

This applies to every subprocess call inside any tool handler or any code path reachable from tool handlers.

### Input validation

Validate all tool inputs at entry before executing any logic:
- Enum parameters: check against allowed set
- Path parameters: validate against allowed roots
- Numeric parameters: check range bounds
- ISO date strings: parse before passing to git/date libraries

Raise `ValidationError` (or return error result) with a clear message. Never trust that the LLM sent valid input.

### Optimistic concurrency / version tokens

For tools that read-then-write files, use version tokens (ETags) to prevent lost updates:
```python
@mcp.tool()
async def update_file(path: str, content: str, version_token: str | None = None) -> str:
    current_hash = compute_hash(path)
    if version_token and version_token != current_hash:
        return json.dumps({"error": "Version conflict", "current_version": current_hash})
    write_file(path, content)
    return json.dumps({"version_token": compute_hash(path)})
```

The model calls `read_file` first (gets `version_token`), then calls `update_file` with that token. If another write happened in between, the update is rejected.

---

## Performance patterns

### Async everywhere

Async is required for I/O-bound operations. Never block the event loop in a tool handler:
```python
import asyncio

@mcp.tool()
async def slow_tool(path: str) -> str:
    # WRONG: blocks event loop
    result = some_blocking_operation(path)

    # CORRECT: run blocking code in thread pool
    result = await asyncio.to_thread(some_blocking_operation, path)
    return result
```

### Tool count management

The LLM receives all registered tools in every conversation turn (unless the client implements selective tool loading). More tools = more tokens consumed + higher probability of the LLM choosing the wrong tool. Community practice:

- Under 20 tools: freely usable with most models
- 20–40 tools: workable with strong models (Claude 3.7+, GPT-4o)
- Over 40 tools: consider grouping, filtering, or using Apigene-style "dynamic tool loading" (load tools only when mentioned)

Design tool sets around coherent domains. Don't expose everything you could expose — expose everything the agent actually needs for its task domain.

### Dynamic tool registration / `listChanged` notifications

If the tool set changes at runtime (e.g., based on user permissions, loaded plugins), implement `listChanged`:
```python
mcp = FastMCP("my-server", capabilities={"tools": {"listChanged": True}})

async def on_plugins_changed():
    # Re-register tools
    mcp.rebuild_tool_registry()
    # Notify all connected clients
    await mcp.send_notification("notifications/tools/list_changed")
```

---

## State management

**Prefer stateless servers** where possible. Stateless servers:
- Work correctly with Streamable HTTP (multiple concurrent clients)
- Restart-safe
- Easier to test

When state is needed:
- **Process-lifetime state** (stdio): store in module-level variables or a context object per `FastMCP` instance
- **Persistent state**: use a database, files, or git (like this repo does)
- **Cross-session state**: see `memory/` reference server — knowledge graph in sqlite with entity/relation/observation model

---

## Structuring a multi-tier server

When the tool surface grows large, organize by tier:

```
tools/
  read_tools.py     — read-only, readOnlyHint=True
  semantic_tools.py — auto-commit writes, higher-level
  write_tools.py    — staged low-level writes, caller controls commit
server.py           — assembles and registers all tiers
```

Each tier imports its tools into FastMCP in `server.py`. Path policy enforcement is centralized (one function validates that a path is writable by a given tier). This pattern is used in this agent_memory repo.

---

## Testing and debugging

### MCP Inspector

Official dev tool for interacting with and debugging MCP servers without a real AI client. Supports stdio and HTTP. Connect to a running server, list tools, call them manually, inspect JSON-RPC logs.

Usage: `npx @modelcontextprotocol/inspector`

### Writing tests

Test tool handlers directly (avoid the transport layer in unit tests):
```python
import pytest
from tools.agent_memory_mcp.read_tools import memory_read_file

@pytest.mark.asyncio
async def test_read_file_returns_content():
    result = await memory_read_file("README.md")
    assert "agent-memory" in result
```

For integration tests that go through the full transport (stdio), use `stdio_client` from the MCP SDK:
```python
from mcp.client.stdio import stdio_client
from mcp import ClientSession

async def test_via_transport():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("memory_read_file", {"path": "README.md"})
            assert result.content[0].text
```

### Postman for MCP

Postman now supports MCP server testing with full support for all major features (tools, prompts, resources, sampling, subscriptions). Useful for HTTP-transport servers and for testing against a specific tool schema without an LLM.

---

## Resources vs Tools — when to use which

| Situation | Use |
|---|---|
| Reading a file/DB record/API response to give the model context | Resource |
| Performing an action (write, delete, send, create) | Tool |
| Complex query that might trigger side effects (API call with rate limits) | Tool |
| Data that changes in real-time (subscribe to updates) | Resource + subscribe |
| User explicitly picks what data to include in context | Resource |
| Model decides whether and when to fetch | Tool |
