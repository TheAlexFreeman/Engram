---
name: session-sync
description: >-
  Mid-session checkpoint. Captures decisions, open threads, and key artifacts
  without ending the session. Activate when the user says "sync" or "checkpoint",
  or when context pressure makes a save worthwhile.
compatibility: Requires agent-memory MCP server with memory_checkpoint
trigger:
  event: session-checkpoint
  priority: 50

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

For lightweight in-progress saves, use `memory_checkpoint` instead. This skill is the heavier checkpoint path: it writes `checkpoint.md`, stages broader session state, and ends with a commit.

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
- Decisions are captured with enough context to understand _why_, not just _what_.
- The checkpoint is concise — aim for 10–20 lines, not a full session transcript.

## Anti-patterns

- **Don't checkpoint trivially.** A two-message exchange about a typo doesn't need a sync.
- **Don't duplicate the final session summary.** Checkpoints are mid-session snapshots, not premature wrap-ups.
- **Don't block the user.** The sync should take seconds, not interrupt the flow of work.

---

## Context-pressure flush

This is an automatic variant of the checkpoint protocol above. It triggers without a user request when context loss is imminent.

### When to trigger

- The agent estimates it has consumed **>75%** of its effective context window.
- The platform signals that compaction, summarization, or context truncation is imminent.
- The agent detects that it can no longer recall details from earlier in the session that it previously had access to.

### What to do

1. Execute Steps 1–2 of the manual checkpoint protocol above (summarize progress, persist `checkpoint.md`).
2. If the chat folder does not yet exist, create it before writing.
3. If a `checkpoint.md` already exists from an earlier sync, append a new timestamped section rather than overwriting.
4. Commit with message: `[chat] Context-pressure flush — <brief description>`.
5. If read-only, present the checkpoint summary to the user immediately.

### What not to do

- Do not attempt a full session wrap-up — this is a checkpoint, not an ending.
- Do not interrupt the user's active request to announce the flush. Complete the current response first, then flush.
- Do not flush if the session has produced no decisions, artifacts, or meaningful context since the last checkpoint.

### Advisory note

Most current platforms do not expose context-usage metrics to agents. This protocol documents the intended behavior so that agents which can detect context pressure know what to do, and platforms that add this capability have a target protocol to trigger. See `agent-bootstrap.toml` § `[compaction_flush]` for the machine-readable configuration.
