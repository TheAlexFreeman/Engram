# 2026-03-24 TanStack Intent Review Hold

## Change Context

- Start time: 2026-03-24 09:44:14 PDT.
- Change time: 2026-03-24 09:44:14 PDT.
- Branch: `deps--update-2026-03-24`.
- Commit at start: `4a540cef66e82f8c9d5bec0720878d09c0d83c3c`.
- Worktree: `/home/micah/p/et/better-base`.

## Summary

Reviewed TanStack Intent as a possible complement to the repo's existing
dotagents-based agent workflow. The current decision is to wait before adopting it in
this repo so the tool and surrounding conventions have more time to stabilize.

## Review Scope

- Reviewed the TanStack Intent docs overview.
- Reviewed the TanStack Intent repository.
- Reviewed the consumer and maintainer quick-start guidance.
- Reviewed the TanStack blog post on shipping docs and skills to agents.
- Compared that model with Better Base's current dotagents setup and local skills.

## Links Reviewed

- dotagents docs: <https://docs.sentry.io/ai/dotagents/>
- TanStack Intent landing page: <https://tanstack.com/intent/latest>
- TanStack Intent overview docs: <https://tanstack.com/intent/latest/docs/overview>
- TanStack Intent consumer quick start: <https://tanstack.com/intent/latest/docs/getting-started/quick-start-consumers>
- TanStack Intent maintainer quick start: <https://tanstack.com/intent/latest/docs/getting-started/quick-start-maintainers>
- TanStack Intent GitHub repo: <https://github.com/tanstack/intent>
- TanStack blog post, "From Docs to Agents": <https://tanstack.com/blog/from-docs-to-agents>

## Local Checks Used

- Reviewed repo agent config and skill definitions in `agents.toml`,
  `.agents/skills/dotagents/SKILL.md`, and `.agents/skills/update-deps/SKILL.md`.
- Reviewed related repo notes under `docs/agent-notes/`, especially the dotagents and
  dependency-update notes from 2026-03-09.
- Reviewed frontend instruction context in `frontend/AGENTS.md`.
- Ran `bunx @tanstack/intent@latest list --json` to see which installed packages in
  this repo currently expose Intent skills.
- Ran `bunx @tanstack/intent@latest install` to inspect the current consumer setup
  prompt behavior.
- Ran `bunx @tanstack/intent@latest --help` and related command help checks to inspect
  the current CLI surface.
- Ran `bunx dotagents --help` and `bunx dotagents --version` to verify the repo-local
  dotagents workflow and confirm the installed version during this review.

## Current Decision

- Do not integrate TanStack Intent into repo instructions or skills yet.
- Do not add npm-sourced skill extraction or mirroring into dotagents workflows yet.
- Keep dotagents as the repo's current source of truth for shared repo-owned skills,
  MCP declarations, and related agent config.
- Revisit TanStack Intent after at least a few weeks or a few months, once the project
  and its conventions feel more mature and stable.

## Why We Are Waiting

- TanStack Intent is still early, so CLI shape and recommended integration patterns may
  continue to move.
- The repo already has a working multi-agent setup centered on `agents.toml`,
  `.agents/skills/`, and repo instruction files.
- Prematurely coupling dotagents workflows to npm-discovered skills would add
  maintenance surface before the benefits are clearly worth it here.

## Likely Revisit Path

If TanStack Intent matures and continues to look useful later, the first integration
pass should likely be small:

- Add a curated `intent-skills` mapping block in `AGENTS.md` for the TanStack Router /
  CLI areas this repo actually uses.
- Keep dotagents responsible for repo-owned skills and config generation rather than
  trying to turn it into an npm skill extractor.
- If needed, update the dependency-refresh workflow to verify or refresh those mappings
  after frontend dependency upgrades.
