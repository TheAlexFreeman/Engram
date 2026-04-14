# Agent Instruction Governance

## Scope

This document defines how instruction files are organized and maintained for the primary
coding agents used in this repository:

1. Codex
2. Cursor
3. Claude Code
4. OpenCode
5. Pi

## Structural Standard

Use a layered model:

1. Root `AGENTS.md` as concise index + non-negotiable operational rules.
2. Detailed, durable policy in `docs/engineering/*`.
3. Path-scoped guidance in `frontend/AGENTS.md` and `backend/AGENTS.md`.
4. Tool-native files only where required by a tool feature.

## Why This Structure

- It keeps top-level instructions readable and avoids context bloat.
- It supports precedence behavior across tools that resolve instructions by scope.
- It keeps one shared policy set for multi-agent consistency.

## Tool Notes

### Codex

- Reads `AGENTS.md` in the working tree hierarchy.
- Prefer repository-local instructions over relying on global-only policies.

### Cursor

- Supports `.cursor/rules/*` and `AGENTS.md`.
- Prefer `AGENTS.md` + scoped files for shared policy; use `.cursor/rules/*` for
  Cursor-specific workflows and metadata-driven rule attachment.

### Claude Code

- Uses repository instructions and supports modular memory/rules.
- Keep root guidance concise and reference deeper files for detail.

### OpenCode

- Supports project config and instruction paths/globs through config.
- Keep reusable guidance in repository files so OpenCode can ingest the same instruction
  corpus as other agents.

### Pi

- Pi consumes skill content from `.agents/skills/`.
- Dotagents-managed skills should remain in `.agents/skills/` so Pi and other agents can
  share the same skill inventory.

## Proactive Maintenance Rule

When users provide broad feedback about style, review standards, architecture decisions,
or agent workflow, agents should:

1. Apply the requested code/task change.
2. Update instruction docs in the same change unless the user declines.
3. Log the update in `docs/agent-notes/` with concise context and rationale.

## Maintenance Cadence

- Keep root `AGENTS.md` concise; move expanding details into `docs/engineering/*`.
- Update path-scoped files when feedback applies only to a subtree.
- Remove stale guidance when implementation conventions or tooling change.

## Path-Based Skill Defaults

Use path-sensitive defaults for recurring workflows when they improve consistency.

- If touched files include `backend/**/ops.py` or `backend/**/ops/**/*.py`, agents
  should load the `operations` skill by default.
- Keep these path-to-skill mappings documented in both `AGENTS.md` and the relevant
  skill file so local sessions and PR review flows remain aligned.
