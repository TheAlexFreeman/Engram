# 2026-03-24 Dependency Update Run

## Change Context

- Start time: 2026-03-24 09:29:01 PDT.
- Change time: 2026-03-24 09:42:10 PDT.
- Branch: `deps--update-2026-03-24`.
- Commit at start: `9bd6389ec51a0fcb9d779cf5928a1f7e60ecbc18`.
- Worktree: `/home/micah/p/et/better-base`.

## Summary

Ran the full `update-deps` workflow, including Python, frontend, pre-commit, runtime,
and dotagents refresh steps, with explicit release-history review for dotagents before
finalizing the repo updates.

## Notes

- Python dependency upgrades pulled in newer `attrs`, Django REST framework, Redis
  client, `django-stubs`, `faker`, Sentry SDK, `ruff`, `pytest-cov`, `prek`, and
  related lockfile updates without requiring a Django target-version change.
- Frontend dependency upgrades pulled in `@sentry/dotagents 1.5.0`, newer TanStack
  packages, Storybook-adjacent tooling, `eslint 10.1.0`, `typescript 6.0.2`,
  `oxlint 1.57.0`, `oxfmt 0.42.0`, `vite 8.0.2`, and related runtime libraries.
- `@vitejs/plugin-react 6.x` was not compatible with the repo's current Vite config
  because the plugin no longer accepts the existing `babel` option. The repo stayed on
  the Vite 8-compatible `@vitejs/plugin-react 5.2.0` line instead of rewriting the
  config during the dependency sweep.
- Runtime and infra pins were refreshed for Bun `1.3.11`, uv `0.11.0`, Traefik
  `3.6.11`, Mailpit `v1.29.4`, and AWS CLI `2.34.15`.
- `bunx dotagents install` and `bunx dotagents sync` both succeeded cleanly after the
  update, and the repo remained aligned with dotagents v1 expectations.
- Dotagents release history between `1.0.0` and `1.5.0` was reviewed directly from the
  upstream package and GitHub compare views. The most notable changes for repo
  maintenance were the optional post-merge auto-install hook, the trust-command
  refinements, path-aware trust matching, and skill copy behavior that excludes `.git`
  content.
- `eslint 10.1.0` now works with the current repo configuration. This supersedes the
  earlier 2026-03-09 note that required pinning back to ESLint 9.
- TypeScript `6.0.2` works with the current toolchain, but `typescript-estree` still
  emits an unsupported-version warning during lint-related commands. The warning did not
  block validation in this run.
- Newer `django-stubs` surfaced a few stricter nullability and stale-ignore issues in
  backend account code and tests. Those were fixed directly so `mypy` stays clean on
  the upgraded type stack.
- Validation passed after the follow-up fixes: `bun run build`, `bun run tscheck`,
  `bun run lint:all`, `bun run circular-import-check`, `mypy .`, `pytest . --create-db`,
  and `prek run --all-files`.
