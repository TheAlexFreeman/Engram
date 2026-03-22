---
source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-16
trust: high
---

# Session Sync (Mid-Session Checkpoint)

**Load this skill on-demand only** — when a checkpoint is needed and you're uncertain about the protocol. For quick reference, `core/governance/session-checklists.md` § "Mid-session sync" has the compact version.

## When to use this skill

Activate when:
- The user says "sync", "checkpoint", "save progress", or similar.
- A long session has produced significant decisions or context that would be costly to lose.
- The agent judges that enough has happened to warrant a checkpoint (use judgment — don't checkpoint after trivial exchanges).

## Steps

### 1. Summarize progress so far

Write a brief checkpoint note capturing:
- **Decisions made** this session (with reasoning if non-obvious).
- **Open threads** — questions raised but not yet resolved.
- **Key artifacts** — files created, modified, or discussed.

### 2. Persist the checkpoint

If write access is available:
- Prefer local agent-memory MCP write tools when they can perform the checkpoint write cleanly; otherwise use direct file writes.
- Create or update the current session's chat folder (`core/memory/activity/YYYY/MM/DD/chat-NNN/`).
- Write a `checkpoint.md` file in the chat folder with the summary above. If multiple syncs happen in one session, append to the same file with timestamps.
- Stage any pending knowledge or identity updates that were discussed and approved.
- Commit with message: `[chat] Mid-session checkpoint — <brief description>`.

If read-only:
- Present the checkpoint summary to the user so they can save it.

### 3. Confirm to the user

Briefly confirm what was captured. One or two sentences — not a full recap.

## Quality criteria

- The checkpoint should be useful to a future agent (or the same agent after context loss) as a recovery point.
- Decisions are captured with enough context to understand *why*, not just *what*.
- The checkpoint is concise — aim for 10–20 lines, not a full session transcript.

## Anti-patterns

- **Don't checkpoint trivially.** A two-message exchange about a typo doesn't need a sync.
- **Don't duplicate the final session summary.** Checkpoints are mid-session snapshots, not premature wrap-ups.
- **Don't block the user.** The sync should take seconds, not interrupt the flow of work.
