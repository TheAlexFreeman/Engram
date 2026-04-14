# 2026-03-09 Django Target Version Sync In Dependency Updates

## Change Context

- Start time: 2026-03-09 15:05:00 PDT.
- Change time: 2026-03-09 15:05:00 PDT.
- Branch: `dev`.
- Commit at start: `51b27aa`.
- Worktree: `/home/micah/p/et/better-base`.

## Summary

Aligned Django-versioned pre-commit hooks with the repo's Django dependency and taught
the Python dependency sync workflow to keep them aligned automatically.

## Notes

- `.pre-commit-config.yaml` had `djade` and `django-upgrade` still targeting Django
  `5.2` after the repo moved to `django==6.0.3`.
- `scripts/sync_upgraded_python_reqs.py` now derives the Django major/minor target from
  `pyproject.toml` and updates those hook args when needed.
- The `update-deps` skill now explicitly treats stale Django target versions in
  `.pre-commit-config.yaml` as a workflow bug that should be fixed in the same change.
