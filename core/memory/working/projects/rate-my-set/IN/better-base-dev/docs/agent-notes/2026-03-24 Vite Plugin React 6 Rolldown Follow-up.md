# 2026-03-24 Vite Plugin React 6 Rolldown Follow-up

## Change Context

- Start time: 2026-03-24 10:34:13 PDT.
- Change time: 2026-03-24 10:44:15 PDT.
- Branch: `deps--update-2026-03-24-plugin-react-6`.
- Commit at start: `dcff2bce143ce25eac364f95d9ba8617365c45af`.
- Worktree: `/home/micah/p/et/better-base`.

## Summary

Completed the Vite 8 / `@vitejs/plugin-react` 6 follow-up by moving the custom React
Compiler setup out of the Vite React plugin options and into
`@rolldown/plugin-babel`, then reran the generated-artifact, validation, and Docker
build workflows.

## What Changed

- Upgraded `@vitejs/plugin-react` from `5.2.0` to `6.0.1`.
- Added explicit Babel peer dependencies for the new path:
  `@rolldown/plugin-babel`, `@babel/core`, and `@types/babel__core`.
- Updated `vite.config.ts` so:
  - `react()` runs without the removed inline `babel` option.
  - React Compiler now runs through Rolldown Babel with the compiler plugin listed
    first.
  - The Babel pass is limited to `frontend/**` sources through an explicit include
    pattern.
  - The existing Jotai Babel preset remains in place on the Rolldown Babel path.

## Workflow Completed

- Refreshed exported email HTML/TXT artifacts with `bun run emailt` and
  `bun run emailh`.
- Synced Django-managed email templates with
  `python manage.py copy_react_email_templates`.
- Refreshed dotagents-managed state with `bunx dotagents install` and
  `bunx dotagents sync`.
- Ran `prek autoupdate`, `prek run --all-files`, and
  `prek run django-upgrade --all-files --hook-stage manual`.

## Validation

- `bun run build`
- `bun run tscheck`
- `bun run lint:all`
- `bun run circular-import-check`
- `source .venv/bin/activate && python manage.py check`
- `source .venv/bin/activate && mypy .`
- `source .venv/bin/activate && pytest . --create-db`
- `docker compose -f dc.dev.yml build`
- `docker compose -f dc.ci.yml build`
- `docker compose -f dc.stage.yml build`
- `docker compose -f dc.prod.yml build`

## Residual Warnings

- `jotai/babel/preset` still prints its upstream deprecation warning during the Vite
  build path. This follow-up kept the existing preset rather than widening scope to a
  Jotai Babel package migration.
- `@typescript-eslint/typescript-estree` still warns that TypeScript `6.0.2` is
  outside its officially supported range during lint-related commands.
- `drf-spectacular` still emits the existing Python `3.14` deprecation warning in the
  Swagger test.
