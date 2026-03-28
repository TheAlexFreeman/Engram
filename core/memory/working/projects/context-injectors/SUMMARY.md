---
type: project-summary
created: 2026-03-28
project_count: 1
---

# Context Injectors

**Status:** Draft (awaiting approval to begin)
**Plan:** [context-injectors-plan.yaml](plans/context-injectors-plan.yaml)

## Purpose

Implement single-call MCP tools that replace file-based INIT.md routing for the two most common session patterns. These are the highest-leverage adoption improvement from the strategic analysis: they reduce the barrier from "understand Engram's routing protocol" to "call one tool."

## Tools

| Tool | Pattern | Consumer |
|---|---|---|
| `memory_context_home` | General-purpose session start (user portrait, activity, working state, indexes) | Interactive chat agents (Claude Code, Cursor, chatbots) |
| `memory_context_project` | Project-focused work context (plan state, sources, IN/ staging, project summary) | Automation agents, CI/CD triggers, plan execution sessions |

## Design decisions

- **Tier 0 read-only** — no side effects, no ACCESS logging from the tool itself
- **Markdown + JSON metadata header** — content is native Markdown for token efficiency; metadata header carries provenance, budget report, and routing hints
- **Soft character budgets** — drop whole sections by priority, never truncate mid-file; budget_report shows what was included/dropped
- **Graceful degradation** — missing files and placeholder content are silently skipped

## Phases

1. **context-assembly-helpers** — Shared infrastructure (_context.py helper module + tests)
2. **context-home-tool** — `memory_context_home` implementation + tests
3. **context-project-tool** — `memory_context_project` implementation + tests
4. **registration-and-docs** — Capabilities manifest, MCP docs, README update, CHANGELOG

## Deferred

`memory_context_query` (search-dependent) and `memory_context_resume` (compaction-dependent) are documented in [notes/context-injectors-roadmap.md](../../notes/context-injectors-roadmap.md).
