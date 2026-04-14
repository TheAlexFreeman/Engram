---
name: update-deps
description: Run the repository dependency upgrade workflow when the user asks to update dependencies, dependency refreshes, or `/update-deps`. Handles Python, frontend, and pre-commit updates, then researches notable version jumps and fixes resulting breakages.
---

Use this skill for dependency maintenance runs in this repository.

## Invocation

Use any of these trigger forms:

- `update-deps`
- `[skill:update-deps]`
- `update deps`
- `dependency update`
- `/update-deps`

## Required Context

1. Read `AGENTS.md`.
2. Read `docs/agent-notes/2026-02-12 Python Dependency Script Hardening.md`.
3. Check `Taskfile.yml`, `pyproject.toml`, `package.json`, and `.pre-commit-config.yaml` if you need to confirm command names or touched files.

## Preflight Rules

1. Require a clean working tree before starting. If `git status --short` is not empty, stop and ask the user how to proceed.
2. Create and switch to a branch named `deps--update-YYYY-MM-DD` using the current date.
3. Activate the Python virtual environment with `source .venv/bin/activate` before Python and mixed-tooling commands.
4. Keep a running note for significant findings, breakages, and follow-up decisions. Prefer a dated file in `docs/agent-notes/` when the session produces material upgrade work.
5. If you hit a blocker you cannot resolve safely, ask the user a concise question instead of guessing.
6. Expect some upstream tools to change CLI shape across releases. When a prescribed command no longer exists, use the closest repo-local supported command, document the difference, and update this skill before finishing.

## Workflow

### 1. Runtime And Infra Version Sweep

Before or alongside the package-manager update steps, inspect the repository for
manually pinned runtime and infrastructure versions and update them where appropriate.

Specifically review and upgrade these everywhere they are pinned:

- Dockerfile syntax versions.
- Redis Docker image versions.
- PostgreSQL versions.
- Ubuntu base image versions.
- Traefik versions.
- Mailpit versions.
- AWS CLI versions.
- Node versions.
- Bun versions.
- uv versions.
- Python version in `.python-version`.
- Python version aliases and tool target versions.
- Other non-package version settings in `pyproject.toml`, `package.json`, CI, Docker, and related config files.

Rules for this sweep:

- If a PostgreSQL update would cross a major version boundary, stop and ask the user for
  confirmation before proceeding.
- If you upgrade Ubuntu anywhere, verify all affected Dockerfiles build properly across
  dev, CI, stage, and prod paths before finishing.
- If a newer Python release line is available and appropriate for the repo, update
  `.python-version` to that line as part of the dependency refresh.
- When Python changes, update all related aliases and config targets in the same pass.
  Common examples include:
  - `python3.14` -> `python3.15`
  - `py314` -> `py315`
  - `python3.14-dev` -> `python3.15-dev`
  - `python: python3.14` in pre-commit config
  - `python_version = "3.14"` and `requires-python = ">= 3.14"` in `pyproject.toml`
- When Node changes, update related engine/config references in the same pass. Common
  examples include:
  - `engines.node` in `package.json`
  - `default_language_version.node` in `.pre-commit-config.yaml`
  - CI/runtime setup references when they pin or imply a Node/Bun toolchain version
- Review Bun and uv version surfaces explicitly, including Docker base images, CI setup
  actions, copied binaries, and other tool bootstrapping paths.
- Review AWS CLI version surfaces explicitly, including production Docker images and any
  manually installed server/bootstrap paths that pin a specific release.
- Inspect `pyproject.toml` and `package.json` for non-package version settings that may
  need to move with runtime/toolchain upgrades, such as minimum supported versions,
  target versions, engine ranges, and tool config aliases.
- Keep these upgrades in the running notes, especially when they require follow-up code,
  config, or build fixes.

### 2. Python Dependencies

Run these commands in order:

```bash
python scripts/upgrade_python_reqs.py
python scripts/sync_upgraded_python_reqs.py
uv sync
```

Then:

- Inspect the resulting `pyproject.toml` and `uv.lock` changes.
- If Django changed, also sync any Django-versioned tooling config that lives outside
  `pyproject.toml`, especially `.pre-commit-config.yaml` hook args such as
  `djade --target-version` and `django-upgrade --target-version`, to the same Django
  major/minor line now pinned in `pyproject.toml`.
- Add only the Python dependency files changed by this phase.
- Commit them separately.
- Push the branch after the commit.

### 3. Frontend Dependencies

Run these commands in order:

```bash
bunx npm-check-updates -p bun -u
bun i
```

Then:

- Inspect the resulting `package.json` and `bun.lock` changes.
- Ensure repo-local tooling packages in `package.json` dev dependencies, including
  `@sentry/dotagents`, are upgraded as part of this phase when updates are available.
- If TanStack Router-related packages changed, regenerate the managed route tree through
  this repo's supported-bundler flow before moving on. This repo uses the Vite plugin
  in `vite.config.ts`, so the preferred regeneration path is:

```bash
bun run build
```

- After that build, inspect `frontend/routeTree.gen.ts` and include it if the
  generation output changed.
- Do not add or switch to `tsr generate` / `@tanstack/router-cli` for this repo unless
  the repo stops using a supported bundler. TanStack's current docs say the Router CLI
  should only be used when you are not using a supported bundler such as Vite.
- Add only the frontend dependency files changed by this phase.
- Commit them separately.
- Push the branch after the commit.

### 4. Email Template Exports

After frontend dependency updates, refresh the exported React email artifacts and copy
them into Django-managed templates:

```bash
bun run emailt
bun run emailh
python manage.py copy_react_email_templates
```

Then:

- Keep the Python virtual environment active before running
  `python manage.py copy_react_email_templates`.
- Inspect changes under exported email artifacts and copied Django email templates.
- If React email-related packages changed, treat stale exported or copied templates as a
  workflow bug and regenerate them before finishing.
- Include the resulting artifact/template changes with the relevant dependency or
  follow-up fix commit.

### 5. Dotagents Refresh

After frontend dependency updates, refresh dotagents-managed state:

```bash
bunx dotagents install
bunx dotagents sync
```

Then:

- If the repo-local dotagents version still exposes a supported `update` subcommand, you
  may run it before `install`. Do not assume that subcommand exists across dotagents
  major versions.
- Inspect changes to generated agent config files such as `.codex/config.toml`,
  `.cursor/mcp.json`, and `opencode.json`.
- Treat the repo-local `@sentry/dotagents` package version as the source of truth for
  this repository. Prefer the repo-managed `bunx dotagents ...` workflow over global
  CLI installs.
- If dotagents prints a generic suggestion to run `npm install -g @sentry/dotagents`,
  ignore it unless the user explicitly asks to maintain a separate global installation.
- Under dotagents v1, `agents.lock` is local managed state and should remain untracked
  in this repo.
- If dotagents-related files changed, include them with the appropriate dependency
  update commit or in a separate focused commit if that is clearer.
- If dotagents behavior or generated outputs changed materially, note that in the
  running upgrade notes.

### 6. Pre-Commit Hooks

Run these commands in order:

```bash
prek autoupdate
prek run --all-files
prek run django-upgrade --all-files --hook-stage manual
```

If `prek autoupdate` changes `.pre-commit-config.yaml`, commit that update in its own logical commit unless the user asks for a different commit shape.
Push that commit as well when it exists.

Notes:

- `prek run --all-files` can legitimately exit non-zero when a formatter rewrites files.
  If that happens, inspect the changes, keep them when appropriate, and rerun the
  command or the narrower formatter/lint command to confirm the tree is now clean.
- Large formatter churn after a formatter upgrade is acceptable when it is a direct
  result of the requested dependency refresh. Keep it documented in the running notes.
- When Django has been upgraded, `prek` config should already be aligned before this
  step. Treat any stale `djade` or `django-upgrade` target version in
  `.pre-commit-config.yaml` as a workflow bug to fix in the same change.

### 7. Breaking-Change Review

After the version bumps land:

1. Use `git diff` to identify backend and frontend package version changes.
2. Flag any major version bump and any unusually large skipped-version jump that looks riskier than a routine patch/minor update.
3. Research the flagged upgrades using official changelogs, release notes, migration guides, or primary documentation.
4. Make any required code or config fixes before the final verification pass.

Prefer official upstream documentation when researching upgrade fallout.

## Verification

Run these commands after addressing upgrade fallout:

```bash
task mm && task m
mypy .
pytest . --create-db
bun run tscheck
bun run lint:all
bun run circular-import-check
```

Before the migration and test steps, ensure required local services are available if the
repo depends on them. For this project, that usually means bringing up the dev
dependencies with:

```bash
docker compose -f dc.dev.yml up -d postgres redis mailpit
```

If `task` is unavailable in the current environment, fall back to the direct Django
commands:

```bash
python manage.py makemigrations
python manage.py migrate
```

If the initial `pytest . --create-db` passes and no schema/database-resetting changes occur afterward, prefer narrower reruns while fixing regressions instead of repeating the full recreate-db run.

If a major frontend or tooling upgrade proves incompatible during verification, it is
acceptable to pin that package back to the latest working release on this branch. Note
the attempted upgrade, the failure mode, and the defer rationale in the running notes.

## Docker Build Verification

After the package-manager verification steps pass, build the repo's Dockerfiles for real
before finishing whenever the update touched any of these surfaces:

- Any file under `compose/**/Dockerfile`.
- Any Docker image tag or base-image version.
- Bun, uv, Python, Ubuntu, Redis, PostgreSQL, Traefik, Mailpit, AWS CLI, or Dockerfile
  syntax versions that feed Docker builds.
- Any tooling or config copied into Docker build contexts that could break image builds.

In this repository, default to the full Dockerfile matrix instead of trying to infer a
smaller safe subset. Dependency updates routinely break images outside the Python and
frontend verification path.

Run:

```bash
docker build -f compose/dev/bun/Dockerfile .
docker build -f compose/dev/django/Dockerfile .
docker build -f compose/prod/aws/Dockerfile .
docker build -f compose/prod/django/Dockerfile .
docker build -f compose/prod/postgres/Dockerfile .
docker build -f compose/prod/traefik/Dockerfile .
docker build -f compose/stage/traefik/Dockerfile .
```

Notes:

- Treat a missing Docker build pass in an `update-deps` run as a workflow bug and fix
  the skill before finishing.
- If a build only succeeds through Compose because of repo-specific secrets or args,
  document that and use the narrowest Compose build command that actually exercises the
  Dockerfile.
- If the repo gains or removes Dockerfiles later, update this command list in the same
  change so the skill stays aligned with the real build matrix.

## Final Upgrade Audit

After the required verification steps pass, do one final self-directed upgrade audit.

Expectations:

1. Search the repository for remaining version pins, compatibility targets, setup
   actions, base images, and other upgrade surfaces that were not already handled.
2. Think through whether any related tooling, CI, deployment, or environment versions
   should move in lockstep with the updates already made.
3. If you find credible additional upgrade candidates, suggest them to the user with a
   short rationale and note whether you think they should be handled now or deferred.
4. Prefer concrete, repo-specific suggestions over generic upgrade advice.

## Commit And Push Expectations

- Keep Python dependency, frontend dependency, and pre-commit updates in separate commits when they are distinct changesets.
- Push after each meaningful commit so the branch stays recoverable.
- If upgrade fixes require extra commits, keep them scoped by concern.

## Output Expectations

Report:

- The branch name used.
- Whether the working tree was clean at start.
- Commits created and pushed.
- Major or otherwise notable version jumps researched.
- Significant breakages found and how they were handled.
- Checks run, failures encountered, and final pass/fail state.
