# 2026-03-09 Dependency Update Skill

## Change Context

- Start time: 2026-03-09 11:22:16 PDT.
- Change time: 2026-03-09 15:19:27 PDT.
- Branch: `dev`.
- Commit at start: `8818698040d48162178bc7ae4705b4cd108190d9`.
- Worktree: `/home/micah/p/et/better-base`.

## Summary

Added a repository-local `update-deps` skill to standardize recurring dependency
maintenance across Codex, Cursor, Claude Code, OpenCode, and Pi.

## Notes

- Chose a skill over a native slash command because the repo's instruction system is
  built around cross-agent skills and `AGENTS.md` trigger phrases.
- Documented `/update-deps` as a text trigger so prompts and PR comments can still use
  the slash-style phrasing without depending on tool-specific slash-command support.
- The skill codifies the staged workflow for Python, frontend, and pre-commit updates,
  plus required breaking-change research and verification.
- Expanded the workflow to include a broader runtime and infrastructure version sweep
  for Dockerfile syntax, Redis, PostgreSQL, Ubuntu, Traefik, Mailpit, and
  `.python-version`.
- Added an explicit human-confirmation gate for major PostgreSQL upgrades.
- Made `bun run tscheck` and `bun run lint:all` required verification steps after the
  Python test pass.
- Added an explicit dotagents refresh step after frontend dependency updates so
  generated agent config files stay in sync when `@sentry/dotagents` changes.
- Added `bun run circular-import-check` after `bun run lint:all` in the required
  verification sequence.
- Expanded the runtime/toolchain sweep to explicitly include Node, Bun, and uv, plus
  non-package version settings and alias updates in files like `pyproject.toml`,
  `package.json`, pre-commit config, CI config, and Dockerfiles.
- Follow-up: the runtime/infra sweep also now explicitly includes AWS CLI version
  surfaces, including the production AWS CLI Docker image.
- Follow-up: TanStack Router upgrades now explicitly require route tree regeneration via
  this repo's Vite-plugin flow (`bun run build`) and a check for changes to
  `frontend/routeTree.gen.ts`, rather than switching this repo to `tsr generate`.
- Added `bunx dotagents update` before `bunx dotagents install` in the dotagents phase.
- Added a final self-directed upgrade audit step so the agent does one more pass for
  missed version pins or related tooling upgrades and reports credible suggestions to
  the user.
- Clarified that repo-local `@sentry/dotagents` in `package.json` is the version that
  should be upgraded and used during the workflow, rather than following the generic
  global `npm install -g @sentry/dotagents` suggestion.
- Real-run follow-up: the initial skill overstated the dotagents workflow by requiring
  `bunx dotagents update`, which is not present in `dotagents 1.0.0`. The skill now
  treats that command as optional and version-dependent.
- Real-run follow-up: the verification block now documents the need to start local dev
  services when required and to fall back to direct Django commands if `task` is not
  installed.
- Real-run follow-up: the pre-commit section now explicitly handles formatter-driven
  file rewrites as an expected part of dependency refreshes instead of treating them as
  a terminal failure.
- Dotagents v1 alignment follow-up: the repo no longer treats `agents.lock` as tracked
  state, removes the deprecated `gitignore = true` setting from `agents.toml`, and
  prefers `install` plus `sync` as the stable repo workflow.
- Workflow follow-up: the dependency refresh skill now explicitly regenerates React
  email artifacts with `bun run emailt`, `bun run emailh`, and
  `python manage.py copy_react_email_templates` after frontend upgrades so copied Django
  email templates do not drift from the upgraded frontend email toolchain.
