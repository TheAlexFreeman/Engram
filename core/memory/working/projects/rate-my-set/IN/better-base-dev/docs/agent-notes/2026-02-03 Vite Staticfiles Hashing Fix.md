# 2026-02-03 Vite Staticfiles Hashing Fix

- Start time: 2026-02-03 07:13:21 PST.
- Change time: 2026-02-03 07:13:50 PST.
- Branch: `main`.
- Commit at start: `426f416f617bb8748f9265ce23353f0e51384f41`.
- Worktree: `/home/micah/p/et/better-base`.

## Root Cause

Django's `CompressedManifestStaticFilesStorage` (from WhiteNoise) runs `hashed_name()` on
all collected static files during `collectstatic`. Vite already hashes its output
filenames (e.g. `main-PLbNeZfF.js`), but Django's manifest storage appended a *second*
hash (e.g. `main-PLbNeZfF.a4ef2389.js`). Code-split chunks emitted by Vite still
referenced the original single-hash filenames, so they loaded a different copy of shared
modules like React — resulting in duplicate React instances at runtime.

The symptom was `TypeError: Cannot read properties of null (reading 'useMemoCache')` (or
`useRef` when React Compiler was disabled via `'use no memo'`). The null value was
`ReactSharedInternals.H`, which is set by the React reconciler during rendering. When a
code-split chunk loaded its own React instance (from the non-double-hashed URL), that
instance's `ReactSharedInternals.H` was never initialized by the reconciler, causing the
null dereference.

## What Was Tried (and Didn't Work)

1. **Breaking circular dependencies** (`initialData → memberships → request → csrf →
   initialData`) via dynamic import — did not fix the issue because the circular
   dependency wasn't the root cause.
2. **`'use no memo'` on the login component** — changed the error from `useMemoCache` to
   `useRef`, confirming the issue was a null React dispatcher, not React Compiler
   specifically.
3. **`resolve.dedupe: ['react', 'react-dom']`** in `vite.config.ts` — had no effect
   because Vite was already bundling a single copy of React; the duplication happened at
   the Django/WhiteNoise layer.

## Fix

Created `backend/base/staticfiles.py` with `ViteManifestStaticFilesStorage`, a subclass
of `CompressedManifestStaticFilesStorage` that overrides `hashed_name()` to skip
re-hashing any file under the `bundler/` prefix (where Vite outputs go). Changed
`config/settings/prod.py` to use this storage backend.

The existing `WHITENOISE_IMMUTABLE_FILE_TEST` regex in `base.py` controls Cache-Control
headers (immutable caching), not the hashing/renaming behavior. Those are two separate
concerns.

## Validation

A script at `scripts/check_vite_staticfiles_hashing.py` can verify the staticfiles
manifest doesn't contain double-hashed or rehashed `bundler/` entries after
`collectstatic` runs.

## Related Changes

- Improved Docker layer caching in `compose/prod/django/Dockerfile` — `bun install` no
  longer invalidated by frontend source file changes (only `package.json`, `bun.lock`,
  config files, and `frontend/theme/` are copied before install).
- Added `madge` to devDependencies with `skipTypeImports: true` for ongoing circular
  dependency detection.
- Fixed `dev_server_port` default in `config/settings/base.py` from `3000` to `4020` to
  match `vite.config.ts`.
