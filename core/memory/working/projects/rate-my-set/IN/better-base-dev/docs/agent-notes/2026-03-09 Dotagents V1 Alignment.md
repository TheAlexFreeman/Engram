# 2026-03-09 Dotagents V1 Alignment

## Change Context

- Start time: 2026-03-09 12:07:00 PDT.
- Change time: 2026-03-09 12:07:00 PDT.
- Branch: `deps--update-2026-03-09`.
- Worktree: `/home/micah/p/et/better-base`.

## Summary

Aligned the repository's dotagents guidance and tracked files with actual dotagents
v1.0.0 behavior.

## Notes

- Removed the deprecated `gitignore = true` setting from `agents.toml`.
- Updated repo guidance to prefer repo-local `bunx dotagents install` and
  `bunx dotagents sync` for normal workflows.
- Switched the repo to the dotagents v1 expectation that `agents.lock` is local managed
  state and should not be committed.
- Updated the `dotagents` and `update-deps` skills so they no longer describe
  `agents.lock` as versioned repo state.
- Kept generated MCP config files tracked. The v1 change here is specifically about
  `agents.lock` handling and the removed `gitignore` knob.
