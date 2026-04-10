---
name: session-start
description: >-
  Session opener for returning users. Loads recent context, checks pending
  review items and maintenance triggers, greets the user with continuity.
  Use at the beginning of any returning session after initial routing.
compatibility: Requires agent-memory MCP server with memory_context_home and memory_session_health_check
trigger:
  event: session-start
  matcher:
    condition: returning_session
  priority: 50

source: user-stated
origin_session: manual
created: 2026-03-16
last_verified: 2026-03-20
trust: high
---

# Session Start

**Load this skill on your first bootstrap or when uncertain about the session-start protocol.** For normal returning sessions, follow the compact returning manifest in `core/INIT.md`, then use `core/memory/HOME.md` as the session entry point for the actual load order. Load `core/governance/session-checklists.md` only when you want more detail than that compact path.

## When to use this skill

Run at the beginning of returning sessions after the compact returning manifest in `core/INIT.md` has oriented the agent. This skill expands that compact path into a detailed workflow.

Skip this skill on the very first session — use `core/governance/first-run.md` and the onboarding skill instead.

## Steps

### 1. Load recent context (silent)

- When available, call `memory_context_home` — it replaces the entire HOME.md load sequence in a single call and returns a budget report. Only fall back to the manual steps below if the MCP surface is unavailable.
- Manual fallback: Read `core/memory/HOME.md` first if the compact manifest routed you there, then follow its ordered summary loads.
- Use `core/memory/working/projects/SUMMARY.md` as task-driven drill-down context to identify the active project, current focus, and the most relevant next reads for this session.
- Read the most recent chat summary (`core/memory/activity/SUMMARY.md` → latest date folder → latest chat `SUMMARY.md`).
- Note what the user was working on, any open threads, and any action items from the previous session.

### 2. Check pending items (silent)

- When available, call `memory_session_health_check()` first and treat its output as the authoritative compact maintenance probe.
- If `memory_session_health_check()` reports pending review-queue items, load `core/governance/review-queue.md` only when you need the actual entries or the user asks about them.
- If `memory_session_health_check()` reports one or more folders in `aggregation_due`, flag them for session-end handling. At wrap-up, preview the compaction with `memory_run_aggregation(dry_run=True)` before deciding whether to apply summary/archive updates.
- If `memory_session_health_check()` reports `periodic_review_due: true`, note that during the greeting.
- Manual fallback when the MCP tool is unavailable: use metadata-first maintenance checks. If `core/governance/review-queue.md` still contains only its placeholder, skip it. Load it only when there are real pending items or the user asks about them. Check whether any ACCESS.jsonl file has reached the aggregation trigger (see `core/INIT.md`). If so, flag it for session-end handling. Check `core/INIT.md` for the last periodic review date. If overdue, note it.

### 3. Check write access (silent)

- If running on a read-only platform, note this and prepare to produce deferred actions at session end per `core/governance/update-guidelines.md` § "Read-only operation". If this is your first read-only session, also review the worked example in `core/governance/update-guidelines.md` § "Worked example" for the output format.

### 4. Build checkpoint habit (silent)

- Use `memory_checkpoint` as the default low-ceremony persistence tool during active work when write access is available.
- Call it after completing a major task, learning something new about the user or repo that should survive compaction, making a non-obvious decision, or spotting a pattern worth preserving.
- Treat checkpointing as a habit, not an emergency procedure. Save small but valuable state before context pressure forces a heavier sync.

### 5. Greet with continuity (interactive)

Greet the user in a way that reflects:

- What they were working on last time (from the recent chat summary).
- Any pending items that need attention (from the review queue).
- Any system maintenance due (aggregation, periodic review).

Keep the greeting concise — 2–3 sentences. Then ask: "Has anything important changed since last time?"

### Greeting examples

**Good:** "Last time we were debugging that WebSocket connection issue in your dashboard — did you find the root cause? I also have a couple of review items queued up whenever you want to look at them."

**Bad:** "Welcome back. Your profile indicates you are a software developer who prefers TypeScript. I have loaded your identity, knowledge, and skills summaries."

The first demonstrates memory and invites continuation. The second recites data and narrates the bootstrap.

## Quality criteria

- The user should feel recognized — the greeting demonstrates that memory is working.
- Pending items are mentioned naturally, not as a status dump.
- The greeting takes no more than one short paragraph before the user can speak.

## Anti-patterns

- **Don't recite the bootstrap.** Never say "I read README.md, then CHANGELOG.md, then..."
- **Don't overwhelm.** If there are 5 pending review items, summarize as "a few pending review items" and offer to go through them, rather than listing all 5 up front.
- **Don't fabricate continuity.** If there's no prior chat history, say so honestly rather than pretending to remember.
