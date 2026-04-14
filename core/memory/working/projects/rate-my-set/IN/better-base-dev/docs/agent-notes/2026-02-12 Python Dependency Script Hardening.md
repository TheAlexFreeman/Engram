# 2026-02-12 Python Dependency Script Hardening

## Change Context

- Start time: 2026-02-12 19:49:00 PST.
- Change time: 2026-02-12 19:57:57 PST.
- Branch: `dev`.
- Commit at start: `5198ec903b2d6bfb26b18748f570a999e7b088fd`.
- Worktree: `/home/micah/p/et/better-base`.

## Summary

Hardened the Python dependency update scripts in `scripts/` to make version syncing more reliable and reproducible.

## What Changed

- Updated `scripts/upgrade_python_reqs.py` to:
  - Extract package names more robustly (including names used with extras/markers).
  - Normalize package names for deduplication (`-`, `_`, and `.` treated consistently).
  - Iterate all dependency groups dynamically instead of hardcoding only `dev` and `prod`.

- Rewrote `scripts/sync_upgraded_python_reqs.py` to:
  - Parse `uv pip freeze` output line-by-line with safer `name==version` handling.
  - Normalize package names before lookup.
  - Correctly update pinned dependencies that include extras and/or markers (for example `django-storages[s3]==...` and `psycopg[c]==...; ...`).
  - Skip wildcard pins such as `==1.*`.
  - Format TOML through the project command (`bun run fmt:toml -- pyproject.toml`) instead of `bunx @taplo/cli fmt -`.
  - Format by default, with `--no-format` available to skip formatting.

- Added regression tests in `scripts/tests/` covering:
  - Extras + marker replacement behavior.
  - Underscore/hyphen package name normalization.
  - Wildcard/non-pinned dependency behavior.
  - TOML formatter invocation path.
  - Upgrade script package extraction and deduplication.

## Validation

- `pytest -q scripts/tests` passes.
- `ruff check scripts/upgrade_python_reqs.py scripts/sync_upgraded_python_reqs.py scripts/tests` passes.
- Manual string-level repro now updates `django-storages[s3]`, `psycopg[c]` with markers, and `mypy[faster-cache]` as expected.
