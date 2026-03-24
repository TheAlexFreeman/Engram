---
source: agent-generated
origin_session: manual
created: 2026-03-18
trust: medium
related: 2026-03-20-git-session-followup.md, ../../ai/tools/mcp/mcp-2026-roadmap-update.md, ../../ai/tools/mcp/mcp-ecosystem-survey.md
---

# Codex Desktop MCP Timeouts Caused by Git Subprocess stdin Inheritance

On 2026-03-18, Codex Desktop appeared to have a bad `~/.codex/config.toml`, but investigation showed that the config loaded correctly and the timeout came from the local `agent_memory` MCP server. The server started normally, `initialize` and `list_tools` succeeded, and non-git subprocesses worked. The hang appeared when tool handlers spawned `git` with `subprocess.run()` while the server itself was running over stdio MCP.

## Symptoms

- A fresh desktop session after reboot still showed `agent_memory` MCP tool calls timing out.
- `~/.codex/config.toml` resolved the expected repo venv interpreter and `engram_mcp/memory_mcp.py`.
- Desktop logs showed the server starting and handling requests such as `ListToolsRequest`, `ListResourcesRequest`, and `CallToolRequest`.
- A standalone Python MCP client reproduced the hang outside the desktop app, which ruled out Codex-specific configuration as the primary problem.
- `memory_list_folder` succeeded over stdio MCP, while `memory_read_file` hung because it reaches git-backed code to compute the file `version_token`.

## Root Cause

When the stdio MCP server spawned `git`, the child process inherited stdin from the server process. In stdio mode, that stdin is the JSON-RPC transport pipe. Git subprocesses with inherited stdin could block or interfere with the transport, producing apparent tool timeouts even though the MCP server was configured correctly.

## Fix Implemented

The fix was to set `stdin=subprocess.DEVNULL` for subprocesses that run inside the MCP server:

- `engram_mcp/agent_memory_mcp/git_repo.py`
- `engram_mcp/agent_memory_mcp/server.py`
- `engram_mcp/agent_memory_mcp/tools/read_tools.py`

A regression test was added in `engram_mcp/tests/test_memory_mcp.py` that launches the server over real stdio transport with the repo venv interpreter and calls `memory_read_file`.

## Verification

- `.venv\Scripts\python.exe -m unittest engram_mcp.tests.test_memory_mcp` passed after the fix.
- A direct stdio MCP client call successfully returned both `memory_list_folder` and `memory_read_file`.
- Empty `list_resources` and `list_resource_templates` responses were not the issue; this server is primarily tool-oriented.

## Follow-up Note

If MCP calls still time out immediately after the fix is present on disk, a likely explanation is that the current desktop session is still attached to a server process that started before the patch. Restarting the Codex app or forcing the MCP server to reconnect should load the updated code.
