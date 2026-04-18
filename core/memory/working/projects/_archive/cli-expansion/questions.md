---
source: agent-generated
origin_session: memory/activity/2026/04/02/chat-001
created: 2026-04-02
trust: medium
type: questions
next_question_id: 4
---

# Open Questions

_None currently._

---

# Resolved Questions

## q-001: Should the CLI framework be Click, Typer, or plain argparse?
**Asked:** 2026-04-02 | **Resolved:** 2026-04-03 | **Resolution:** Plain `argparse` shipped in the new CLI entry point.
**Why:** It matches the existing proxy/sidecar CLIs, avoids a new dependency, and was sufficient for v0 help and subcommand routing.

## q-002: Should `engram search` default to semantic or keyword search?
**Asked:** 2026-04-02 | **Resolved:** 2026-04-03 | **Resolution:** The shipped CLI auto-detects semantic search support and falls back to keyword mode when optional search dependencies are unavailable.
**Why:** This preserves zero-extra-dependency behavior while still exposing semantic retrieval when `.[search]` is installed. An explicit `--semantic` flag remains optional follow-on UX polish, not a blocker to the landed foundation.

## q-003: How should the CLI discover the repo root?
**Asked:** 2026-04-02 | **Resolved:** 2026-04-03 | **Resolution:** The CLI uses explicit `--repo-root`, then `MEMORY_REPO_ROOT` / `AGENT_MEMORY_ROOT`, then cwd-walk for `agent-bootstrap.toml`, then file-relative fallback.
**Why:** That resolution chain matches the MCP server logic while also supporting installed terminal use from arbitrary working directories.
