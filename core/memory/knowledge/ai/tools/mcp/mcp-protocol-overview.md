---
source: external-research
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
origin_session: core/memory/activity/2026/03/19/chat-002
topic: mcp-protocol
related: mcp-ecosystem-survey.md, mcp-server-design-patterns.md, mcp-2026-roadmap-update.md
---

# Model Context Protocol — Architecture and Specification Overview

**Source**: [modelcontextprotocol.io](https://modelcontextprotocol.io) docs fetched 2026-03-19. Reflects spec version `2025-06-18`, the current production version.
**Governance**: MCP is an open-source standard now under **LF Projects (Linux Foundation)**. Not Anthropic-exclusive.

---

## What MCP is

MCP (Model Context Protocol) is an open protocol that standardizes how AI applications connect to external data sources, tools, and workflows. Analogous to "USB-C for AI": once you build an MCP server or client, it interoperates with the full ecosystem without bespoke integrations.

The protocol specifies **only the connection** — it does not dictate how AI applications use LLMs or how they manage the context they receive.

---

## Participants (Host / Client / Server)

```
MCP Host (AI application: Claude Desktop, VS Code, Cursor…)
 ├── MCP Client 1  ──── MCP Server A (local: filesystem, git)
 ├── MCP Client 2  ──── MCP Server B (local: database)
 └── MCP Client 3  ──── MCP Server C (remote: Sentry, GitHub…)
```

- **MCP Host**: The AI application that manages one or more MCP clients (e.g., VS Code, Claude Desktop, Cursor).
- **MCP Client**: A component inside the host that maintains a dedicated connection to one MCP server.
- **MCP Server**: A program that provides context (tools, resources, prompts) to MCP clients. Can run locally or remotely.

One host → many clients (one per server). One local server (stdio) typically serves a single client; remote servers (Streamable HTTP) typically serve many.

---

## Protocol layers

### Data layer (JSON-RPC 2.0)

Defines message schema and semantics:
- **Lifecycle management**: Initialize → capability negotiation → ready → terminate
- **Server features**: tools, resources, prompts
- **Client features**: sampling (request LLM completions from host), elicitation (request user input), logging
- **Utility features**: notifications (real-time updates), progress tracking

### Transport layer

Abstracts communication from the data layer. Two supported transports:

| Transport | Use case | Notes |
|---|---|---|
| **stdio** | Local process ↔ subprocess | Best for local tools. No network, no auth needed. Child processes inside the server MUST use `stdin=subprocess.DEVNULL` to prevent transport pipe inheritance. |
| **Streamable HTTP** | Remote / multi-client | HTTP POST to single `/mcp` endpoint, with optional SSE for streaming. Supports OAuth. The current HTTP standard. |

The old dual-endpoint SSE transport (GET `/sse` + POST `/messages`) is deprecated as of `2025-03-26` spec revision, though many clients still support it for backward compat.

---

## Protocol lifecycle

1. **Initialize**: Client sends `initialize` with `protocolVersion` and `capabilities`. Server responds with its own `serverInfo` and `capabilities`.
2. **Ready**: Client sends `notifications/initialized`.
3. **Operation**: Client discovers and calls tools/resources/prompts.
4. **Notifications**: Either side sends async notifications (no response expected).
5. **Termination**: Connection closed or subprocess exits.

Current production protocol version: **`2025-06-18`**

Initialization example (client → server):
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-06-18",
    "capabilities": { "elicitation": {} },
    "clientInfo": { "name": "my-client", "version": "1.0.0" }
  }
}
```

Server declares `"tools": {"listChanged": true}` to indicate it can send `notifications/tools/list_changed`.

---

## Server primitives

### Tools (model-controlled)

Executable functions the LLM invokes based on context. The AI decides autonomously which tool to call. Each tool has:
- `name`: unique identifier (follows `server_verb_noun` pattern in practice)
- `title`: human-readable display name (new in 2025 spec)
- `description`: LLM-readable explanation (most critical field for tool selection quality)
- `inputSchema`: JSON Schema defining expected parameters

Protocol operations: `tools/list`, `tools/call`

Tool result content types: `TextContent`, `ImageContent`, `EmbeddedResource`

Tool annotations (added in 2025 spec, informational only — not enforced):
- `readOnlyHint`: no side effects
- `destructiveHint`: may cause data loss
- `idempotentHint`: safe to retry
- `openWorldHint`: interacts with external systems

User consent mechanisms: approval dialogs, pre-approved allowlists, activity logs.

### Resources (application-controlled)

Read-only data sources the AI application retrieves and passes as context. Applications decide what to select and how (subset, embeddings, full content). Resources have URIs and declare MIME types.

Discovery patterns:
- **Direct resources**: fixed URIs (`calendar://events/2024`)
- **Resource templates**: parameterized URI patterns with `{variables}` (`weather://forecast/{city}/{date}`)

Protocol operations: `resources/list`, `resources/templates/list`, `resources/read`, `resources/subscribe`

Resources support parameter completion for UI affordances (type "Par" → suggest "Paris").

### Prompts (user-controlled)

Reusable parameterized templates that **users explicitly invoke**. Not auto-triggered by the LLM. Useful for structured workflows, domain-specific system prompts, few-shot examples.

Protocol operations: `prompts/list`, `prompts/get`

Common UI patterns: slash commands `/`, command palettes, keyboard shortcuts.

---

## Client primitives (server → client requests)

- **Sampling** (`sampling/complete`): Server requests an LLM completion from the host. Useful for model-independent servers that need AI reasoning. NOT all clients support this.
- **Elicitation** (`elicitation/request`): Server asks the user for input or confirmation mid-operation. New in recent spec; enables interactive server workflows.
- **Logging**: Servers send debug/info/warning messages to the client for display.

---

## Experimental / emerging primitives

- **Tasks**: Durable execution wrappers for deferred result retrieval and status tracking. Relevant for expensive computations, batch processing, multi-step workflows. Experimental as of 2025 spec; not widely supported yet.
- **Apps**: Interactive HTML interfaces that MCP servers can render in supporting clients. Some clients (VS Code Copilot, Claude.ai, MCPJam) now support this.

---

## Notifications

Async JSON-RPC 2.0 messages with no `id` field (no response expected):
- `notifications/initialized` (client → server after init)
- `notifications/tools/list_changed` (server → clients when tool list changes, only if `listChanged: true` declared)
- `notifications/resources/list_changed` (similarly)
- `notifications/progress` (long-running operation updates)

---

## Capability negotiation summary

Clients declare what they support (e.g., `elicitation: {}`, `sampling: {}`). Servers declare what they expose (e.g., `tools: {listChanged: true}`, `resources: {}`, `prompts: {}`). Both sides only send messages for capabilities the other side declared support for.

---

## Where to go deeper

- Specification: `https://modelcontextprotocol.io/specification/latest`
- Python SDK: `https://github.com/modelcontextprotocol/python-sdk`
- TypeScript SDK: `https://github.com/modelcontextprotocol/typescript-sdk`
- MCP Inspector (dev tool): `https://github.com/modelcontextprotocol/inspector`
