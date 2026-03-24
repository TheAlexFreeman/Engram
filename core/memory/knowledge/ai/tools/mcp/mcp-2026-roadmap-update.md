---
source: external-research
created: 2026-03-20
last_verified: 2026-03-20
trust: medium
origin_session: core/memory/activity/2026/03/20/chat-001
topic: mcp-protocol
type: knowledge
domain: mcp
tags: [mcp, roadmap, 2026, transport, enterprise, tasks, governance]
related: mcp-ecosystem-survey.md, mcp-protocol-overview.md, mcp-server-design-patterns.md
---

# MCP 2026 Roadmap Update

**Sources**: modelcontextprotocol.io blog, The New Stack, March 2026.

## Context

MCP has matured from a local tool-wiring mechanism into a production system powering enterprise deployments. The 2026 roadmap shifts from release-based planning to **Working Group-driven priorities**, with four areas receiving expedited SEP (Spec Enhancement Proposal) review.

## Four Priority Areas

### 1. Transport Scalability
Streamable HTTP enables remote MCP servers but doesn't yet scale cleanly. Stateful sessions fight load balancers; horizontal scaling requires workarounds. Fixes target stateless session models and `.well-known` metadata endpoints for server discovery without connecting first.

### 2. Tasks Primitive
The Tasks feature (async agent work, SEP-1686) shipped experimentally. Production gaps: retry semantics for transient failures, expiry policies for retained results. Refinement in progress.

### 3. Enterprise Readiness
Audit trails, SSO-integrated auth, gateway behavior, config portability. Landing as extensions rather than core spec changes to keep the spec lean.

### 4. Governance Maturation
Every proposal currently requires full core maintainer review — a bottleneck at scale. New contributor ladder and delegation model will let Working Groups accept domain-specific proposals independently.

## Infrastructure Announcements (March 2026)

- **AWS**: Stateful MCP server support across 14 regions (March 10).
- **Cloudflare**: Official guides for deploying remote MCP servers with and without auth.

## MCP Apps (January 2026)

First official MCP extension: tools can return interactive UI components (dashboards, forms, visualizations) rendered in conversation rather than plain text. Sandboxed iframes, bidirectional JSON-RPC, cross-platform (Claude, ChatGPT, VS Code, Goose).

## Relevance to Engram

- **Tasks** improvements are directly relevant to any future async PWR logging or goal evaluation triggered via MCP.
- **Transport scalability** matters if Engram ever exposes memory read/write as a remote MCP server.
- **Enterprise audit trail** work overlaps with Engram's own git-based auditability goals.
