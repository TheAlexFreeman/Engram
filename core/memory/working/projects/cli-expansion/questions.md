---
source: agent-generated
origin_session: memory/activity/2026/04/02/chat-001
created: 2026-04-02
trust: medium
type: questions
next_question_id: 4
---

# Open Questions

## q-001: Should the CLI framework be Click, Typer, or plain argparse?
**Asked:** 2026-04-02 | **Last touched:** 2026-04-02 | **Context:** The existing CLIs (sidecar, proxy) use argparse. Click/Typer would give richer help text and shell completion out of the box, but add a dependency. argparse keeps deps minimal and matches existing code.

## q-002: Should `engram search` default to semantic or keyword search?
**Asked:** 2026-04-02 | **Last touched:** 2026-04-02 | **Context:** Semantic search requires `.[search]` (sentence-transformers, numpy). Keyword search (the existing `memory_search` grep-based tool) works with zero extra deps. The CLI could auto-detect and tell the user which mode it's using, or require an explicit `--semantic` flag.

## q-003: How should the CLI discover the repo root?
**Asked:** 2026-04-02 | **Last touched:** 2026-04-02 | **Context:** The MCP server already supports `MEMORY_REPO_ROOT`, `AGENT_MEMORY_ROOT`, and file-relative detection. The CLI should use the same resolution chain, plus possibly walk up from cwd looking for `agent-bootstrap.toml` (similar to how git finds `.git`).
