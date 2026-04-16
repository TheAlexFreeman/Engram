---
name: update-eng-style-guide
description: Update and normalize engineering guidance docs when the user asks to "update style guide", "update eng style guide", or "update engineering style guide". Keeps AGENTS and docs/engineering aligned across Codex, Cursor, Claude Code, OpenCode, and Pi.
source: external-research
origin_session: unknown
created: 2026-04-14
trust: low
---

Use this skill when the user gives broad feedback about coding style, review process,
architecture conventions, or agent workflow and wants the repository guidance updated.

## Goals

1. Keep `AGENTS.md` concise and index-like.
2. Keep durable policy in `docs/engineering/*`.
3. Keep path-specific guidance in `frontend/AGENTS.md` and `backend/AGENTS.md`.
4. Keep guidance portable across Codex, Cursor, Claude Code, OpenCode, and Pi.

## Invocation

Use either of these trigger forms:

- `update-eng-style-guide`
- `[skill:update-eng-style-guide]`
- `update style guide`
- `update eng style guide`
- `update engineering style guide`

These triggers are intended to work in local prompts and in PR review comments where an
agent is reading the comment text.

## Required Update Targets

Always consider whether these files need updates in the same change:

- `AGENTS.md`
- `docs/engineering/style-guide.md`
- `docs/engineering/code-review-checklist.md`
- `docs/engineering/agent-instruction-governance.md`
- `frontend/AGENTS.md`
- `backend/AGENTS.md`

If conventions materially changed, add a concise note in `docs/agent-notes/`.

## Style Guide Shape

Maintain four top-level sections in `docs/engineering/style-guide.md`:

1. `General / Overall`
2. `Backend`
3. `Frontend`
4. `DevOps / Infra`

Keep bullets actionable and repository-specific.

## Output Expectations

- Explain what changed and why.
- List file paths updated.
- Mention any checks run and any checks skipped.
