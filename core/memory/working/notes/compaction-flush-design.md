---
source: agent-generated
trust: medium
created: 2026-03-28
origin_session: memory/activity/2026/03/28/cowork-session
tags: [compaction-flush, session-management]
---

# Compaction Flush: 5-Point Combined Design

The context compaction flush defends against data loss when long conversations approach the LLM's context window limit and older context gets summarized or truncated. This is OpenClaw's most celebrated feature; Engram's version must work without runtime control.

## The 5 points

### 1. `memory_checkpoint` tool
- Append-only, minimal ceremony, no frontmatter, no governance gates
- Writes to `core/memory/working/CURRENT.md` or session-specific scratchpad
- Automatic-tier (no approval needed) — barrier to use must be near-zero
- Possibly extend `memory_append_scratchpad` with `checkpoint: true` mode adding timestamp + session context
- Scratchpad governance already exists (`core/governance/scratchpad-guidelines.md`)

### 2. Session skill instructions
- Update `session-start.md` and `session-sync.md`: "checkpoint working state after decisions, discoveries, and task completions"
- Frame as habit, not emergency — "persist as you go"
- Specific triggers: after completing a major task, after learning something new, after any decision with reasoning worth preserving

### 3. MCP-side session activity monitor
- Extend `memory_session_health_check` with proxy metrics: tool call count, content volume, elapsed wall time
- When heuristics suggest a long session, add `_advisory: "session_flush_recommended"` to tool responses
- Conservative trigger — false positives are cheap, false negatives lose data

### 4. `memory_session_flush` tool
- Comprehensive persist: summarize scratchpad, record reflection, update relevant SUMMARY files
- **Proposed-tier** (user awareness) — unlike checkpoint which is automatic-tier
- Respects Engram's transparency principle: checkpoint silently, flush visibly

### 5. Platform-specific hooks
- Claude Code hooks can trigger `memory_session_flush` on compaction
- `.cursorrules` can include compaction-awareness instructions
- Platform adapters (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`) are the wiring surface
- Advisory (point 3) is the platform-agnostic safety net for unsupported platforms

## Key tradeoff: silent vs. transparent

- Checkpoint writes → automatic-tier (invisible, like ACCESS logs)
- Flush/distillation → proposed-tier (user awareness, because it updates SUMMARYs and creates knowledge)

## Integration

This design is subsumed by the session-management project's three-phase roadmap. Each flush point lands across the phases as documented in [integrated-roadmap.md](integrated-roadmap.md).
