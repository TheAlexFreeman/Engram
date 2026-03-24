---
source: external-research
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
origin_session: core/memory/activity/2026/03/19/chat-002
topic: mcp-protocol
related: mcp-2026-roadmap-update.md, mcp-protocol-overview.md, mcp-server-design-patterns.md
---

# MCP Ecosystem Survey — Clients, Servers, and Discovery (2026)

**Source**: [modelcontextprotocol.io/clients](https://modelcontextprotocol.io/clients) and [modelcontextprotocol.io/examples](https://modelcontextprotocol.io/examples), fetched 2026-03-19.
**Scale**: 108 clients listed as of March 2026. The ecosystem has grown dramatically since the November 2024 launch.

---

## Client landscape

### Tier 1: Primary AI coding environments

These are the clients most developers encounter in daily use:

| Client | Primitives | Notes |
|---|---|---|
| **VS Code GitHub Copilot** | Resources, Prompts, Tools, Discovery, Instructions, Sampling, Roots, Elicitation, DCR, Apps | Full-feature. Config via `mcp.json` or Claude Desktop format. Per-session tool selection. |
| **Claude Desktop** | Resources, Prompts, Tools, Roots, DCR, Apps | Original MCP client. Supports local (stdio) and remote servers. File attachment via Resources. |
| **Claude.ai** | Resources, Prompts, Tools, CIMD, DCR, Apps | Remote MCP servers via integrations UI. |
| **Claude Code** | Resources, Prompts, Tools, Discovery, Instructions, Roots, Elicitation, DCR | Anthropic's agentic coding CLI. Also functions as an MCP server (can be connected to by other clients). |
| **Cursor** | Prompts, Tools, Roots, Elicitation, DCR | Support for stdio and SSE. MCP in Composer (agent mode). |
| **Windsurf Editor** | Tools, Discovery | Codeium's agentic IDE. AI Flow paradigm. |
| **Cline** | Resources, Tools, Discovery | VS Code extension. Autonomous agent: files, commands, browser. Can scaffold new MCP servers via natural language. |
| **Roo Code** | Resources, Tools | VS Code. Forked from Cline lineage. |

### Tier 2: Other major AI platforms

| Client | Notes |
|---|---|
| **ChatGPT** | Remote MCP servers only. MCP Apps support. Enterprise security. |
| **Mistral AI (Le Chat)** | Remote servers, enterprise features. |
| **Gemini CLI** | Google's open-source terminal agent. Prompts, Tools, Instructions, DCR. |
| **Amazon Q CLI** | AWS's open-source terminal agent. Prompts, Tools. |
| **Amazon Q IDE** | VS Code, JetBrains, Visual Studio, Eclipse. |
| **JetBrains AI Assistant** | All JetBrains IDEs. Tools support. |
| **JetBrains Junie** | JetBrains' dedicated coding agent. stdio, config via mcp.json. |
| **Zed** | High-performance editor. Prompts (as slash commands), Tools. No Resources. |
| **Replit Agent** | Build-and-deploy agent. Tools + DCR. |
| **v0 (Vercel)** | Full-stack app builder. Vercel Marketplace MCP servers. |
| **Microsoft Copilot Studio** | Enterprise SaaS. Resources, Tools, Discovery. |
| **LM Studio** | Local model runner. Tools, confirmation UI. `mcp.json` config. |
| **Continue** | VS Code/JetBrains. Resources (@ mentions), Prompts (slash commands), Tools, Apps. |
| **Augment Code** | VS Code/JetBrains. Local and remote agents. Full MCP support. |
| **Warp** | Intelligent terminal. Resources, Tools, Discovery. Natural language + MCP. |

### Tier 3: Notable specialized clients

- **Postman**: Full MCP testing/debugging client (all primitives + sampling + subscriptions). Now the de facto tool for testing MCP servers without an LLM.
- **Goose (Block)**: Open-source agent. Resources, Prompts, Tools, Instructions, Sampling, Elicitation, Apps. Extensions directory for server discovery.
- **fast-agent**: Python agent framework. Full-feature MCP support including sampling. Deploy agents as MCP servers.
- **mcp-agent (LastMile AI)**: Composable framework implementing every pattern from Anthropic's "Building Effective Agents" paper. Supports workflow pause/resume.
- **MCPJam Inspector**: Local dev client and ChatGPT Apps emulator. OAuth debugger. Supports all transports. Free API tokens for playground testing.
- **Smithery Playground**: Testing client for MCP servers with full OAuth support. Detailed RPC traces.
- **Amp (Sourcegraph)**: Agentic coding tool. VS Code, JetBrains, Neovim, CLI. Multiplayer/shared threads. Resources, Prompts, Tools, Sampling.
- **Codeium/Windsurf**: AI Flow paradigm IDE.
- **Glama**: AI workspace with integrated MCP Server Directory, Tool Directory, and hosted MCP servers.

### Mobile and messaging clients

- **Joey**: iOS/Android + desktop MCP client. Streamable HTTP, OAuth, sampling, elicitation.
- **systemprompt**: Voice-controlled iOS/Android MCP client.
- **WhatsMCP**: MCP via WhatsApp interface.
- **Shortwave**: AI email client with stdio and HTTP MCP server support.

---

## MCP capability feature matrix

Clients declare capability support (the following features go beyond basic Tools):

| Feature | Description | Who supports it |
|---|---|---|
| **Resources** | Read data from servers | ~50% of listed clients |
| **Prompts** | Use server prompt templates | ~40% of listed clients |
| **Sampling** | Server requests LLM completions from host | ~15% of listed clients |
| **Elicitation** | Server requests user input | ~20% of listed clients |
| **Roots** | Client exposes filesystem boundaries | Cursor, Claude Code, VS Code Copilot, fast-agent |
| **Discovery** | `listChanged` notification support | Cline, Glama, fast-agent, Warp, Kilo Code |
| **Tasks** | Long-running operation tracking (experimental) | Glama, MCPJam, Postman |
| **Apps** | Interactive HTML interfaces | VS Code Copilot, Claude.ai, Claude Desktop, ChatGPT, Goose, Postman, MCPJam |
| **DCR** | Dynamic Client Registration (OAuth) | Claude Code, Cursor, VS Code, Gemini CLI, Replit, v0 |

Most clients support **Tools only** as a baseline. Sampling remains rare and is a differentiating feature.

---

## Official MCP reference servers (active)

As at March 2026, the reference servers repository has been trimmed down. Active servers:

| Server | What it provides |
|---|---|
| **Everything** | Full-featured reference/test server: tools, resources, prompts. Use for SDK testing. |
| **Fetch** | HTTP fetching with clean LLM-optimized output. |
| **Filesystem** | Secure file read/write with configurable path restrictions. |
| **Git** | Read, search, and manipulate Git repos. |
| **Memory** | Knowledge graph-based persistent memory (SQLite + entity/relation model). |
| **Sequential Thinking** | Dynamic reflective problem-solving through thought sequences. |
| **Time** | Time and timezone conversion. |

Previously active servers (GitHub, PostgreSQL, Slack, Google Drive, Brave Search, etc.) have been **archived** to `github.com/modelcontextprotocol/servers-archived`. They are provided for historical reference. For production use of these integrations, prefer official company-maintained servers.

### Using reference servers

```bash
# TypeScript servers via npx
npx -y @modelcontextprotocol/server-memory
npx -y @modelcontextprotocol/server-filesystem /allowed/path

# Python servers via uvx (recommended)
uvx mcp-server-git
uvx mcp-server-fetch
```

Claude Desktop config:
```json
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "git": {
      "command": "uvx",
      "args": ["mcp-server-git", "--repository", "/path/to/repo"]
    }
  }
}
```

---

## Official company-maintained integrations

The MCP servers repository (`github.com/modelcontextprotocol/servers`) lists integrations maintained by companies. Notable ones:

- **Sentry MCP Server**: Error and issue tracking. Remote (Streamable HTTP), OAuth.
- **Linear MCP Server**: Issue and project tracking via Linear API.
- **Notion MCP Server**: Notion workspace access.
- **Supabase MCP Server**: Supabase/PostgreSQL database operations.
- **Cloudflare MCP Series**: Workers, KV Store, R2, and other Cloudflare services.
- **GitHub MCP Server**: Issues, PRs, repos, search. Maintained by GitHub.
- **Atlassian MCP**: Jira, Confluence.
- **Stripe MCP Server**: Payment workflows.
- **Neon MCP Server**: Serverless Postgres.
- **Grafana MCP Server**: Observability queries.
- **Proxyman**: HTTP debugging and interception (also acts as an MCP server for AI traffic analysis).

---

## Discovery and registries

| Resource | URL | Purpose |
|---|---|---|
| **Official servers repo** | github.com/modelcontextprotocol/servers | Canonical list of reference + company-maintained servers |
| **Smithery.ai** | smithery.ai | Hosted marketplace. One-click install links for Claude Desktop, Cursor, etc. |
| **Glama MCP Directory** | glama.ai/mcp/servers | Discovery + hosted execution |
| **mcp.so** | mcp.so | Community-run directory |
| **mcp-get** | npm: `npx mcp-get` | CLI tool for searching and installing MCP servers |
| **MCPJam** | mcpjam.com | Dev playground + server registry |

---

## SDK availability

| Language | Package | Maintainer |
|---|---|---|
| **Python** | `mcp` (includes FastMCP) | Anthropic |
| **TypeScript/Node** | `@modelcontextprotocol/sdk` | Anthropic (reference impl) |
| **Go** | `github.com/mark3labs/mcp-go` | Community |
| **Rust** | `rmcp` crate | Community |
| **C# / .NET** | via LM-Kit.NET MCP client | Third-party |
| **Ruby** | `mcp-rb` gem | Community |
| **Java/Kotlin** | `kotlin-mcp-sdk` (JetBrains) | JetBrains |

---

## Community frameworks for building agents with MCP

Libraries that abstract agent loop + MCP client management:

| Framework | Language | Notes |
|---|---|---|
| **mcp-agent** | Python | Simple composable agents. All "Building Effective Agents" patterns. |
| **fast-agent** | Python | Full multimodal, can deploy agents as MCP servers. |
| **mcp-use** | Python | Connect any LangChain-supported LLM to any MCP server. |
| **BeeAI Framework** | TypeScript | IBM/bee-ai. Production-grade multi-agent. |
| **Swarms** | Python | Enterprise multi-agent orchestration. SSE MCP. |
| **GenAIScript** | JavaScript | Microsoft. Programmatic prompt assembly + MCP. |
| **Genkit** | TypeScript | Google Firebase. MCP plugin. |
| **SpinAI** | TypeScript | Observable agents. Native MCP compatibility. |
| **LangChain / LangGraph** | Python/TS | MCP integration via `mcp-use` or native adapters. |
| **CrewAI** | Python | Role-based multi-agent. MCP tool support via adapter. |

---

## Protocol governance

MCP is governed by **LF Projects, LLC** (a Linux Foundation entity), not by Anthropic alone. This prevents single-vendor lock-in and enables industry-wide participation in spec development. The GitHub org is `github.com/modelcontextprotocol` and contributions happen via pull requests and discussions at `github.com/orgs/modelcontextprotocol/discussions`.

This governance structure explains why ChatGPT, Gemini CLI, JetBrains, GitHub, Amazon, Microsoft, and many others have adopted MCP — it's a true open standard.
