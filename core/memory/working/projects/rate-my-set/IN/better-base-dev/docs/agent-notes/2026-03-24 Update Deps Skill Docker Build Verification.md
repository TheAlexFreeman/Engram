# 2026-03-24 Update Deps Skill Docker Build Verification

## Change Context

- Start time: 2026-03-24 10:01:42 PDT.
- Change time: 2026-03-24 10:01:42 PDT.
- Branch: `dev`.
- Commit at start: `081b65d5554dcb6be40d23674a6debf9d7cebabb`.
- Worktree: `/home/micah/p/et/better-base`.

## Summary

Updated the `update-deps` skill so dependency-refresh runs must finish with real Docker
build verification, not just Python and frontend checks.

## Notes

- A 2026-03-24 follow-up build exposed that the dependency-update workflow had left
  `oven/bun:1.3.11-debian` pinned in Dockerfiles even though that tag does not exist on
  Docker Hub.
- The gap was procedural: the skill validated application-level commands but did not
  require post-update Docker builds, so the broken image reference escaped the original
  run.
- The skill now defaults to building the full repo Dockerfile matrix whenever
  dependency updates touch Docker-relevant version surfaces or copied build-context
  inputs.
- Future dependency-update changes should treat missing Docker build coverage as a
  workflow bug and update the skill in the same change.
