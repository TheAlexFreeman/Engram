# 2026-03-10 Dockerfile Optimization Port From Ren Magic

## Change Context

- Start time: 2026-03-10 11:20:55 PDT.
- Change time: 2026-03-10 11:20:55 PDT.
- Branch: `feature--2026-03-10-dockerfile-optimizations`.
- Commit at start: `a4d3ab4ecde6df9d392f989746123b0b746e50a8`.
- Worktree: `/home/micah/p/et/better-base`.

## Summary

Ported the recent `ren-magic` Docker optimization pattern into Better Base, then adapted
it to Better Base's root-context Docker builds and current runtime expectations.

## Source Context

- In `ren-magic`, the latest merged PR that included Dockerfile changes was the squash
  merge `ce5c81f8` (`Apply Better Base upgrade package in REN (#279)`).
- The newer Docker-specific improvements that mattered for this port were follow-up
  direct commits:
  - `80f597cb` (`Optimize Docker build contexts and caching`)
  - `802d68ff` (`Fix dockerfile permissions issue`)

Future agents should prefer the follow-up commit content over stopping at `#279`,
because that is where the narrowed build contexts, explicit frontend copy graph, and
runtime permission fix actually landed.

## Better Base Adaptation

- Added Dockerfile-specific `.dockerignore` files for the app and infra images so each
  build stops sending the whole repository as context.
- Reworked the production Django Dockerfile to copy only the frontend build inputs into
  the Bun stage and only the runtime-required paths into the final Python image.
- Kept Better Base's production source-map stripping step after the frontend build,
  because this repo already relied on it and `ren-magic` had dropped it for repo-local
  reasons.
- Adapted the `802d68ff` permission fix to Better Base's actual writable runtime paths:
  `/app/staticfiles`, `/app/backend/media/public`, and `/app/backend/media/private`.
- Applied the same context-tightening spirit to Better Base-only Dockerfiles that do not
  exist in `ren-magic`, including the stage Traefik image.

## Validation

- Built all touched images successfully:
  - `compose/dev/bun/Dockerfile`
  - `compose/dev/django/Dockerfile`
  - `compose/prod/django/Dockerfile`
  - `compose/prod/postgres/Dockerfile`
  - `compose/prod/aws/Dockerfile`
  - `compose/prod/traefik/Dockerfile`
  - `compose/stage/traefik/Dockerfile`
- Ran runtime smoke checks against the built images to verify:
  - the production Django image runs as the non-root `app` user and can write to the
    startup-created `staticfiles` and media directories,
  - the production Django image contains the copied `jsoneditor` static assets and
    `.sentry-release`,
  - the Bun, AWS, Postgres, and Traefik images contain the expected copied files.
