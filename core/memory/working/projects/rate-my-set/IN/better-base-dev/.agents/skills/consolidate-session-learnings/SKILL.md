---
name: consolidate-session-learnings
description: End-of-session consolidation workflow. Review human feedback and update AGENTS plus engineering guidance docs so conventions stay aligned across Codex, Cursor, Claude Code, OpenCode, and Pi.
---

Use this skill near the end of a session when new standards were learned from human
feedback, review comments, implementation outcomes, or debugging discoveries.

## Purpose

Consolidate durable learnings into the right instruction documents instead of leaving
them only in chat context.

## Invocation

Use either of these trigger forms:

- `consolidate-session-learnings`
- `[skill:consolidate-session-learnings]`

Common natural-language trigger phrases:

- `consolidate session learnings`
- `consolidate learnings`
- `session closeout guidance update`

## Required Review Targets

Always review these files and update when relevant:

1. `AGENTS.md`
2. `docs/engineering/style-guide.md`
3. `docs/engineering/code-review-checklist.md`
4. `docs/engineering/agent-instruction-governance.md`
5. `frontend/AGENTS.md`
6. `backend/AGENTS.md`
7. `docs/agent-notes/` (add a concise dated note when conventions changed)

## Consolidation Rules

- Keep root `AGENTS.md` concise; move detailed policy into `docs/engineering/*`.
- Put frontend-only or backend-only guidance in path-scoped files.
- Prefer durable, actionable rules over one-off implementation details.
- Remove stale or contradictory guidance when adding new guidance.
- If there is no durable learning, explicitly state that no doc update is needed.

## Output Expectations

At completion, summarize:

- Which files were reviewed.
- Which files were updated and why.
- Which checks were run or intentionally skipped.
