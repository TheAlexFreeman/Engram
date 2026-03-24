---
type: summary
related:
  - mcp-ecosystem-survey.md
  - mcp-2026-roadmap-update.md
---

# MCP Knowledge — Summary

Four files covering the Model Context Protocol specification, server design patterns, ecosystem landscape, and 2026 roadmap. Synthesized from `modelcontextprotocol.io` docs (spec version `2025-06-18`) and operational experience building the `agent_memory` MCP server in this repo. Promoted from `_unverified/` on 2026-03-20 after review.

## Files

- **`mcp-protocol-overview.md`** — Architecture and spec overview: Host/Client/Server model, JSON-RPC 2.0 data layer, stdio vs. Streamable HTTP transports, server primitives (Tools, Resources, Prompts), client primitives (Sampling, Elicitation), capability negotiation, protocol lifecycle, and spec version timeline.
- **`mcp-server-design-patterns.md`** — Practical server-building guide: FastMCP patterns, tool naming and description quality, input schema design, result design, tool annotations, security (path traversal prevention, stdio stdin inheritance fix, optimistic concurrency), async performance, tool count management, dynamic registration, state management, multi-tier organization, testing with MCP Inspector and Postman.
- **`mcp-ecosystem-survey.md`** — Ecosystem survey (March 2026): 108 clients categorized by tier, capability feature matrix, 7 active reference servers, official company integrations, discovery registries (Smithery, Glama, mcp.so), SDK availability (Python, TypeScript, Go, Rust, Kotlin, Java), and community agent frameworks.
- **`mcp-2026-roadmap-update.md`** — 2026 roadmap: transport scalability, Tasks primitive refinement, enterprise readiness, governance maturation, AWS/Cloudflare infrastructure announcements, MCP Apps extension.

## Related

- [../codex-mcp-timeouts-git-stdin.md](../codex-mcp-timeouts-git-stdin.md) — Debugging stdio transport stdin inheritance issue in this repo's MCP server
- [../../../plans/mcp-reorganization.md](../../../plans/mcp-reorganization.md) — MCP server reorganization plan
