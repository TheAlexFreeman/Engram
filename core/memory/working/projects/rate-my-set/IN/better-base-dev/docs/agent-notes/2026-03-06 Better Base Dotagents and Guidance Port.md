# 2026-03-06 Better Base Dotagents and Guidance Port

## Change Context

- Start time: 2026-03-06 16:25:11 PST.
- Change time: 2026-03-06 16:25:11 PST.
- Branch: `dev`.
- Commit at start: `44172bbf93f91a96d497522b81449991895a5d39`.
- Worktree: `<current-worktree>`.

## Summary

Ported a derived project's multi-agent instruction stack and related tooling changes
back into Better Base, while adapting the guidance to Better Base's role as a reusable
scaffold.

## Source Details

- Source repo names and commit lists are intentionally omitted in this note.

## Changes Brought In

- Added `django.contrib.postgres` to `config/settings/base.py`.
- Added dotagents-managed agent scaffolding:
  - `.agents/skills/**`
  - `agents.toml`
  - generated agent config targets such as `.codex/config.toml`,
    `.cursor/mcp.json`, and `opencode.json`
- Added shared/path-scoped instruction docs:
  - `docs/engineering/style-guide.md`
  - `docs/engineering/code-review-checklist.md`
  - `docs/engineering/agent-instruction-governance.md`
  - `docs/engineering/operations-pattern.md`
  - `frontend/AGENTS.md`
  - `backend/AGENTS.md`
  - `.github/pull_request_template.md`
- Updated linting and docs/tooling:
  - `.agents/**` excluded from ESLint scope
  - TanStack guidance changed from MCP-first to CLI-first
  - TanStack Cursor rule snippets updated from `npx` to `bunx`
  - removed the legacy tracked `.mcp.example.json` path in favor of generated MCP
    outputs from `agents.toml`

## Better Base Adaptation

- Rewrote project context sections so they describe Better Base as a reusable base
  project instead of copying child-project-specific product framing.
- Kept shared skills and engineering guidance that are broadly useful across derived
  projects.
- Updated the factory reference example domain to `tests.better-base.local`.
- Kept MCP setup centered on generated outputs from `agents.toml` instead of maintaining
  a separate tracked example file.

## Validation Intent

- Install dotagents-related dependencies.
- Run `bunx dotagents install` to generate the managed files from `agents.toml`.
- Run targeted lint/tooling checks to confirm the new config is coherent.
- Follow-up: dotagents v1 later removed the `gitignore` setting from `agents.toml` and
  moved `agents.lock` to local managed state rather than tracked repo state.
