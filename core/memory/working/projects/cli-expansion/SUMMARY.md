---
active_plans: 1
cognitive_mode: design
created: 2026-04-02
current_focus: Design and implement a human- and agent-facing CLI for the Engram memory
  system.
last_activity: '2026-04-02'
open_questions: 3
origin_session: memory/activity/2026/04/02/chat-001
plans: 1
source: agent-generated
status: active
trust: medium
type: project
---

# Project: CLI Expansion

## Description
Add an `engram` CLI that exposes the memory system's core operations to humans, shell-based agents, and automation scripts. The MCP server is the right interface for agents inside a chat session, but there is no way to query, inspect, or maintain memory from a terminal today. The CLI closes that gap.

## Motivation
Engram currently has three CLI entry points (`engram-mcp`, `engram-proxy`, `engram-sidecar`), but all are infrastructure — they run servers and watchers. As more users adopt Engram, they need a way to:
- Quickly check what the system knows (`search`)
- Assess memory health without reading multiple files (`status`)
- Validate repo integrity in CI and local workflows (`validate`)
- Interact with memory from shell-based agents that don't have MCP wired up

## Cognitive mode
Design mode: the v0 scope (search, status, validate) is defined and ready for implementation planning. The broader roadmap (recall, add, review, plan, export) is captured in notes/ for future phases.

## Artifact flow
- IN/: design references, prior art research, user feedback on CLI ergonomics
- notes/: roadmap, design decisions, architecture notes
- plans/: phased implementation plans
- OUT contributions: `engram` entry point in pyproject.toml, `core/tools/agent_memory_mcp/cli/` module tree

## Key design decisions
1. **Thin presentation layer** — the CLI reuses existing business logic from `engram_mcp` (frontmatter parsing, path policy, search, validation). No parallel implementation.
2. **`--json` everywhere** — every command supports structured output for agent/script consumption.
3. **Graceful degradation** — `engram search` falls back to keyword/frontmatter search when the embedding model (`.[search]` extra) isn't installed.
4. **Single entry point** — `engram` with subcommands, registered in pyproject.toml alongside the existing entry points.