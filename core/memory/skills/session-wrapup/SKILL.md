---
name: session-wrapup
description: >-
  Session closer. Writes chat summary, reflection note, ACCESS entries, and
  flags pending system maintenance. Produces deferred actions on read-only
  platforms. Activate when the user ends the session or context is running low.
compatibility: Requires agent-memory MCP server with memory_record_session
trigger:
  event: session-end
  priority: 50

source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-20
trust: high
---

# Session Wrap-Up

**Load this skill on your first bootstrap or when uncertain about the wrap-up protocol.** Load `core/governance/session-checklists.md` only when you want the shorter session-end runbook there during normal sessions; it is an on-demand reference, not the live router.

## When to use this skill

Activate when:

- The user says "wrap up", "end session", "that's all", or similar.
- The session is clearly concluding (final thanks, sign-off language).
- Context window is running low and the session should be archived before context is lost.

## Steps

### 1. Record the session atomically

- Prefer `memory_record_session` when the local agent-memory MCP surface is available. It should write the session `SUMMARY.md`, optional `reflection.md`, update `core/memory/activity/SUMMARY.md`, and append ACCESS entries in one commit.
- If the composite tool is unavailable, fall back to the individual governed writes or direct file writes as needed.

Create the session's chat folder if it doesn't exist: `core/memory/activity/YYYY/MM/DD/chat-NNN/`.

Write `SUMMARY.md` following the compression hierarchy in README.md § "Summaries":

- Key topics discussed.
- Decisions made and their reasoning.
- Action items (for the user or for future sessions).
- Notable context that a future agent should know.

If writing a reflection, follow the canonical format in README.md § "Session reflection".

When ACCESS entries are available, include them in the same composite call so `session_id` is injected automatically.

### 2. Update summaries if warranted

If this session produced significant new knowledge, identity changes, or skill refinements:

- Update the relevant folder's `SUMMARY.md` to reflect the new content.
- For identity or governance changes, ensure they were proposed and approved per `core/governance/update-guidelines.md`.

### 3. Check for system maintenance

- If any ACCESS.jsonl has hit the aggregation trigger (see `core/INIT.md`), load `core/governance/curation-algorithms.md` and run aggregation now, or flag it for the next session start.
- If periodic review is overdue, add a reminder to `core/governance/review-queue.md`.

### 4. Produce deferred actions (if read-only)

If write access is unavailable, produce a deferred-action summary listing:

- All ACCESS entries that should be appended.
- All file writes (summaries, reflections, knowledge updates) that should be applied.
- All review-queue items.

Present this using the format in `core/governance/update-guidelines.md` § "How to communicate deferred actions". If this is your first read-only session, also review the worked example in `core/governance/update-guidelines.md` § "Worked example" for the output format. (`HUMANS/tooling/scripts/onboard-export.sh` is for first-session onboarding only; it does not apply here.)

### 5. Sign off

Brief, warm sign-off. Reference something specific from the session to demonstrate continuity — not a generic "have a great day."

## Quality criteria

- The chat summary should be useful to a future agent reading only SUMMARY.md files (no transcript access needed for basic context).
- The reflection note should be honest — low helpfulness scores and gap observations are more valuable than optimistic self-assessment.
- ACCESS entries are complete — every content file read is logged, including misses.
- If read-only, the deferred-action summary is comprehensive enough that a user can apply all changes without needing to re-read the session.

## Anti-patterns

- **Don't skip the reflection.** It's tempting to write only the summary. The reflection is what makes the system self-improving.
- **Don't inflate helpfulness scores.** A file that was opened but didn't influence the response is a 0.2–0.4, not a 0.7.
- **Don't write a novel.** The summary should be 10–30 lines, not a transcript rehash.
- **Don't forget deferred actions on read-only platforms.** This is the user's only way to persist the session's value.
