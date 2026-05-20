---
source: agent-generated
type: knowledge
created: 2026-04-14
last_verified: 2026-04-14
trust: low
related:
  - ../../software-engineering/devops/dev-workflow-tooling.md
  - ../../software-engineering/devops/github-actions-cicd.md
  - ../../software-engineering/devops/docker-compose-local-dev.md
  - ../../software-engineering/devops/docker-production-config.md
  - ../../software-engineering/django/django-6.0-whats-new.md
  - ../../software-engineering/react/vite-react-build.md
origin_session: memory/activity/2026/04/14/chat-002
---

# Better Base Toolchain — uv, Bun, Taskfile, Jotai, Render, Ruff, Oxc, tsgo, djlint, prek

Better Base bundles a specific, opinionated set of tools that together form a fast-feedback, cross-language workflow. Most individual tools have competent replacements; the value is in how they compose. This note is a single-file reference for the full toolchain, with commands that map directly onto the project's `Taskfile.yml` and CI.

---

## 1. Stack at a glance

| Layer | Tool | Role |
|-------|------|------|
| Python package management | **uv** | Replaces pip, pip-tools, pipenv, poetry, pyenv; unified lockfile + Python version |
| Python lint/format | **ruff** | Replaces black + isort + flake8 + pyupgrade + pydocstyle |
| Python typing | **mypy** | Static type checking |
| Django template lint | **djlint** | Template-aware linter and formatter |
| JS runtime + pkg mgr | **Bun** | Replaces npm/pnpm/yarn + Node for scripts and tests |
| JS/TS lint | **oxlint** | Rust-based linter from Oxc; replaces most ESLint usage |
| JS/TS format | **oxfmt** | Rust-based formatter from Oxc; Prettier-compatible |
| TS compile / typecheck | **tsgo** | Microsoft's Go port of tsc; 10× faster typechecking |
| Frontend state | **Jotai** | Atomic client state alongside TanStack Query server state |
| Pre-commit hooks | **prek** | Rust rewrite of pre-commit; drop-in compatible |
| Task orchestration | **Taskfile** | YAML task runner replacing Make |
| Deploy | **Render** | Platform-as-a-service; `render.yaml` blueprint |

The consistent theme is "Rust or Go reimplementations of tools we already trusted." You get roughly the same semantics with 10–100× less wall-clock time and no JVM/Node overhead in CI.

---

## 2. uv — Python project and package manager

Astral's uv replaces the entire Python packaging supply chain: pip, pip-tools, pip-compile, virtualenv, pyenv, pipx, and poetry/pipenv-style project managers. Written in Rust.

### Core commands

```bash
uv init                      # scaffold a new project with pyproject.toml
uv python install 3.14       # install a Python interpreter (bypasses system Python)
uv python pin 3.14           # pin the project to a specific interpreter
uv add django celery         # add runtime deps; updates pyproject.toml + uv.lock
uv add --dev pytest ruff     # add dev-only deps
uv remove django-debug-toolbar
uv sync                      # install deps per uv.lock into .venv/
uv sync --frozen             # fail if uv.lock is out of date (CI mode)
uv lock                      # regenerate uv.lock without installing
uv run manage.py migrate     # run a command inside the project's venv
uv run python -c "import django; print(django.VERSION)"
```

`uv sync` is the workhorse. It creates `.venv/` if missing, installs exactly what `uv.lock` specifies, and prunes anything extra. A fresh clone to working venv is typically 1–3 seconds.

### pyproject.toml layout

```toml
[project]
name = "rate-my-set"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = [
  "django>=6.0,<7.0",
  "djangorestframework>=3.15",
  "drf-spectacular>=0.27",
  "celery>=5.4",
  "redis>=5.0",
  "psycopg[binary]>=3.2",
  "django-storages[s3]>=1.14",
  "orjson>=3.10",
  "argon2-cffi>=23.1",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-django>=4.9",
  "pytest-xdist>=3.6",
  "factory-boy>=3.3",
  "respx>=0.21",
  "ruff>=0.7",
  "mypy>=1.12",
  "django-stubs[compatible-mypy]>=5.1",
]

[tool.uv]
package = false               # this is an app, not a library
```

### Lockfile semantics

`uv.lock` is the source of truth. It records the exact resolved version, wheel hash, and platform markers for every dependency and transitive dependency. Like `package-lock.json` or `poetry.lock`, commit it.

The lockfile is cross-platform by default: uv resolves for Linux, macOS, and Windows simultaneously and records the union so `uv sync --frozen` works on any of those platforms from the same lockfile.

### Dependency groups

`[dependency-groups]` is the PEP-735 way to express dev-only dependencies. `uv sync --no-dev` for production installs. Better Base uses this to keep test tooling out of the production image.

### CI pattern

```yaml
- uses: astral-sh/setup-uv@v3
  with:
    enable-cache: true
- run: uv sync --frozen
- run: uv run pytest
```

`uv sync --frozen` fails fast if anyone pushed a pyproject.toml change without regenerating the lock. That's the behavior you want in CI.

### Migrating from poetry

```bash
uvx migrate-to-uv            # one-shot migration from poetry/pipenv/pip-tools
```

The migration tool is good; review the generated `pyproject.toml` for correctness.

---

## 3. ruff — Python linting and formatting

Ruff combines the functionality of black, isort, flake8, pyupgrade, pydocstyle, bandit, pylint (partial), eradicate, and ~30 other linters into a single Rust binary. Orders of magnitude faster than the tools it replaces.

### Core commands

```bash
uv run ruff check            # lint
uv run ruff check --fix      # auto-fix what's fixable
uv run ruff format           # format (black-compatible)
uv run ruff format --check   # check formatting without modifying files
```

### Config in pyproject.toml

```toml
[tool.ruff]
line-length = 100
target-version = "py314"
extend-exclude = ["migrations"]

[tool.ruff.lint]
# Start broad, then ignore what doesn't fit.
select = [
  "E", "F", "W",          # pycodestyle + pyflakes
  "I",                     # isort
  "N",                     # pep8-naming
  "UP",                    # pyupgrade
  "B",                     # flake8-bugbear
  "C4",                    # flake8-comprehensions
  "DJ",                    # flake8-django
  "DTZ",                   # flake8-datetimez (timezone-aware datetimes)
  "PIE", "PL", "PT",       # various
  "RUF",                   # ruff-specific
  "S",                     # flake8-bandit (security)
  "SIM",                   # flake8-simplify
  "T20",                   # flake8-print (no stray prints)
  "TID",                   # flake8-tidy-imports
]
ignore = [
  "E501",                  # line length handled by formatter
  "S101",                  # allow `assert` in tests
]

[tool.ruff.lint.per-file-ignores]
"**/tests/**" = ["S", "PLR2004"]   # allow magic values and assertions in tests
"**/migrations/**" = ["all"]
"**/settings/**" = ["F403", "F405"] # star imports are normal in Django settings

[tool.ruff.lint.isort]
known-first-party = ["accounts", "productions", "config"]
combine-as-imports = true
```

### Format vs. lint

Ruff's formatter is a fork of black that fixes a couple of black's rougher edges (docstring code blocks, magic trailing commas). It is black-compatible for any project that doesn't rely on black's specific edge cases. Run both `ruff format` and `ruff check --fix` on every commit; they cover different surfaces.

### Editor integration

`ruff-lsp` or the native LSP in recent ruff versions plugs into VS Code, Neovim, PyCharm. Autofix-on-save replaces ~5 separate tool invocations.

---

## 4. mypy — static type checking

Mature and well-documented; covered briefly here.

```toml
[tool.mypy]
python_version = "3.14"
strict = true
plugins = ["mypy_django_plugin.main"]

[tool.django-stubs]
django_settings_module = "config.settings.development"

[[tool.mypy.overrides]]
module = ["tests.*"]
disallow_untyped_defs = false
```

Better Base pairs mypy with `django-stubs` so Django's ORM returns concrete types instead of `Any`. Run `uv run mypy .` in CI and locally. For speed on large codebases, `dmypy` (the daemon mode) shaves seconds per run; `mypy --python-executable .venv/bin/python` avoids reinstalling stubs.

Where it fits alongside tsgo-for-Python: there isn't one yet. Static typing in Python remains CPython-runtime + mypy/pyright. pyrefly (a Rust-based type checker from Meta, preview) is worth watching but not production-grade at time of writing.

---

## 5. djlint — Django template linting

Django templates aren't Python code, so ruff doesn't touch them. djlint handles indentation, tag formatting, and common mistakes in `.html` templates.

```bash
uv run djlint templates/ --check
uv run djlint templates/ --reformat
```

```toml
[tool.djlint]
profile = "django"
indent = 2
max_line_length = 120
ignore = "H006"             # the "no alt attribute" rule is noisy on partials
```

Integrate into pre-commit so template formatting never drifts.

---

## 6. Bun — JavaScript runtime, package manager, bundler, test runner

Bun is a full Node-compatible runtime plus a package manager plus a bundler plus a test runner, all in one binary. Better Base uses it primarily as a faster replacement for `npm install` and `npm run`; the runtime side matters less when the app runs in the browser.

### Core commands

```bash
bun install                    # installs per bun.lock; 10-30x faster than npm
bun install --frozen-lockfile  # CI mode
bun add react@19               # add a dep
bun add -d vitest              # dev dep
bun remove some-pkg
bun run dev                    # runs the "dev" script from package.json
bun run lint
bun run build
bun x eslint .                 # one-shot binary, like npx
```

### package.json compatibility

Bun uses standard `package.json`. The lockfile is `bun.lock` (text, v1.1+) or `bun.lockb` (binary, older). Standard npm scripts work unchanged. Bun also honors `engines`, `workspaces`, and most of npm's config surface.

### What Bun actually speeds up

- **Install**: `bun install` is typically 10–30× faster than `npm install` on a cold cache. On a warm cache it's near-instant.
- **Script startup**: `bun run` has no Node startup penalty; useful for many short-lived scripts.
- **Binary dispatch**: `bun x` is faster than `npx` for single-shot command invocations.

### What Bun does not replace

- **Production runtime**: for Vite-built SPAs like Better Base's frontend, the production artifact is static HTML/JS/CSS. Bun as a runtime doesn't factor in.
- **Vite**: Bun has its own bundler, but Better Base uses Vite 8. Bun still runs Vite's CLI fine.
- **Node-only libraries**: most pure JS packages work; some native-binding packages lag. If a dep fails on Bun, fall back to `npm install` for that one command.

### Workspaces

Monorepo workspaces in Bun are declared in the root `package.json`:

```json
{
  "name": "better-base-monorepo",
  "workspaces": ["frontend", "shared/*"]
}
```

`bun install` hoists shared deps and sets up symlinks. `bun run --filter frontend build` runs a script in one workspace.

---

## 7. Oxc — oxlint and oxfmt

Oxc (short for "Oxidation Compiler") is a Rust-based JS/TS toolchain. The two pieces Better Base uses are **oxlint** (linter) and **oxfmt** (formatter). The goal is Prettier/ESLint semantics at ~50–100× the speed.

### oxlint

```bash
bun x oxlint                   # lint the whole project
bun x oxlint --fix             # autofix where possible
bun x oxlint src/ --deny-warnings  # CI mode
```

Config lives in `.oxlintrc.json`:

```json
{
  "categories": {
    "correctness": "error",
    "suspicious": "warn",
    "pedantic": "off"
  },
  "plugins": ["react", "typescript", "jsx-a11y", "import"],
  "rules": {
    "react/jsx-uses-react": "off",
    "react/react-in-jsx-scope": "off"
  },
  "overrides": [
    { "files": ["**/*.test.ts*"], "rules": { "no-console": "off" } }
  ]
}
```

oxlint ports a large subset of ESLint-core, typescript-eslint, react, jsx-a11y, and import rules. At time of writing it does **not** implement type-aware rules (anything that requires a TS Program). For those, keep a minimal ESLint config that only runs the type-aware subset.

### oxfmt

oxfmt is the Prettier-compatible formatter. Still labeled experimental but approaching stable for most real-world code:

```bash
bun x oxfmt --check            # verify formatting
bun x oxfmt --write             # apply formatting
```

Config in `.oxfmtrc.json` or `package.json` `"oxfmt"` field. Prettier options (`semi`, `singleQuote`, `tabWidth`, `printWidth`) are mostly honored.

### Mixing oxc with ESLint/Prettier

The pragmatic setup:

- oxfmt formats everything.
- oxlint runs all non-type-aware rules in pre-commit and CI (fast loop).
- ESLint runs only the `@typescript-eslint` type-aware subset on CI (slow loop).

This keeps the fast path fast without giving up the type-aware checks that matter.

---

## 8. tsgo — TypeScript compiler in Go

Microsoft announced a Go port of the TypeScript compiler ("Project Corsa" / `typescript-go`) targeting roughly 10× faster type checking and language service operations. As of early-to-mid 2026 it's in public preview, functional enough for real projects but still catching up on edge-case compatibility.

### What it is and isn't

- It's a line-for-line Go port of the existing TypeScript compiler's core, not a rewrite with different semantics.
- The official TypeScript team considers it the future default compiler (`tsc`) in some version of TypeScript 7.x.
- It does **not** yet cover all of `tsserver`'s language-service features (language server protocol, refactorings, code actions). For editors, stick with the classic TS language server until the port matures.

### Installation and usage

```bash
bun add -d @typescript/native-preview
# Provides the `tsgo` binary

bun x tsgo --noEmit            # typecheck the project
bun x tsgo --watch             # watch mode
bun x tsgo --build             # build composite project references
```

Config is the same `tsconfig.json`. The flags are a superset of `tsc`'s.

### CI integration

```yaml
- run: bun x tsgo --noEmit
```

Better Base's CI runs this as a separate step from `bun run build` so type errors surface with a clear status, independent of the bundler.

### Fallback posture

If tsgo produces a spurious error (still possible in preview), pin the specific files to `// @ts-nocheck` temporarily or fall back to the classic `tsc --noEmit` for that CI step. Keep the fallback one-liner ready; the preview status of tsgo makes this a realistic concern through 2026.

---

## 9. prek — pre-commit in Rust

prek is a drop-in replacement for the Python `pre-commit` framework, rewritten in Rust. Same `.pre-commit-config.yaml`, same hook definitions, significantly faster install and run.

### Install

```bash
brew install j178/tap/prek     # or from the GitHub release
prek install                    # install the git hook
prek install --hook-type pre-push  # for push-time hooks
```

### Config

Standard pre-commit config works unchanged:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.3
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/djlint/djLint
    rev: v1.35.0
    hooks:
      - id: djlint-reformat-django
      - id: djlint-django

  - repo: local
    hooks:
      - id: oxlint
        name: oxlint
        entry: bun x oxlint
        language: system
        types_or: [javascript, jsx, ts, tsx]
        pass_filenames: true
      - id: oxfmt
        name: oxfmt
        entry: bun x oxfmt --write
        language: system
        types_or: [javascript, jsx, ts, tsx]
        pass_filenames: true
```

### Running

```bash
prek run                 # run on staged files (default)
prek run --all-files     # run against everything
prek run ruff            # run one hook
prek autoupdate          # bump hook versions
```

Switching from pre-commit to prek is a matter of installing the binary and running `prek install`. No config migration.

---

## 10. Taskfile — orchestration layer

Taskfile replaces Makefiles with a modern YAML-based task runner. Better Base's `Taskfile.yml` is the canonical entry point for every developer workflow.

### Install

```bash
brew install go-task        # or download from taskfile.dev
```

### Basic syntax

```yaml
# Taskfile.yml
version: '3'

vars:
  COMPOSE_FILE: compose.dev.yml

env:
  DJANGO_SETTINGS_MODULE: config.settings.development

tasks:
  build:
    desc: Build all Docker images
    cmds:
      - docker compose -f {{.COMPOSE_FILE}} build

  back:
    desc: Start backend services (Postgres, Redis, Mailpit)
    cmds:
      - docker compose -f {{.COMPOSE_FILE}} up postgres redis mailpit

  migrate:
    desc: Apply Django migrations
    deps: [back]
    cmds:
      - uv run python manage.py migrate

  tcov:
    desc: Run backend tests with coverage (no DB)
    cmds:
      - uv run pytest --cov=. --cov-report=term-missing

  tcovdb:
    desc: Run backend tests with coverage against a real DB
    deps: [back]
    cmds:
      - uv run pytest --cov=. --create-db

  mp:
    desc: Run mypy
    cmds:
      - uv run mypy .

  lint:
    desc: All Python lint
    cmds:
      - uv run ruff check --fix
      - uv run ruff format
      - uv run djlint templates/ --reformat

  flint:
    desc: All frontend lint
    dir: frontend
    cmds:
      - bun x oxlint --fix
      - bun x oxfmt --write
      - bun x tsgo --noEmit

  openapi:
    desc: Regenerate OpenAPI schema and frontend types
    cmds:
      - uv run python manage.py spectacular --file openapi.yaml
      - cd frontend && bun x openapi-typescript ../openapi.yaml -o src/api/schema.ts

  ci:
    desc: Everything CI would run
    cmds:
      - task: lint
      - task: mp
      - task: tcov
      - task: flint
```

### Key features worth knowing

- **`deps`**: other tasks that must complete first. Runs in parallel by default.
- **`dir`**: change into a subdirectory before running the task (Better Base uses this for frontend-scoped commands).
- **`preconditions`**: fail early if, say, a file doesn't exist.
- **`sources` / `generates`**: up-to-date detection based on file mtimes, like Make.
- **`includes`**: split large Taskfiles into per-subsystem files.
- **`cmds` with `task:` refs**: one task invokes another.
- **Variable templating**: `{{.VAR}}` is Go text/template; you can branch on env.

### `task --list` and discoverability

`task --list-all` prints every defined task with its `desc`. A good Taskfile has a one-line description on every task and functions as self-documenting developer onboarding.

### vs. Make

Taskfile wins on readability (YAML beats Makefile syntax), cross-platform behavior (Windows works without tricks), and first-class parallelism via `deps`. Make wins on ubiquity. For a new project, Taskfile is the clear choice.

---

## 11. Jotai — atomic state management

Jotai sits on the client-state side of a two-store architecture:

- **TanStack Query** holds server state (cached API responses, mutations, background refresh).
- **Jotai** holds client state (UI flags, form scratch, derived computations).

Rule of thumb: if the state came from or will be sent to the server, it belongs in TanStack Query. Everything else is a candidate for Jotai.

### Core concepts

An atom is a unit of state. Components subscribe to atoms and re-render when they change. Atoms are composed of other atoms.

```typescript
import { atom, useAtom, useAtomValue, useSetAtom } from "jotai";

// Primitive atom — holds a value.
const themeAtom = atom<"light" | "dark">("light");

// Derived atom — read-only, computed from others.
const isDarkAtom = atom((get) => get(themeAtom) === "dark");

// Writable derived atom.
const toggleThemeAtom = atom(null, (get, set) => {
  set(themeAtom, get(themeAtom) === "light" ? "dark" : "light");
});

function ThemeToggle() {
  const [theme, setTheme] = useAtom(themeAtom);
  return <button onClick={() => setTheme(theme === "light" ? "dark" : "light")}>{theme}</button>;
}

function ThemeReadonly() {
  const isDark = useAtomValue(isDarkAtom);     // read only
  return <span>{isDark ? "🌙" : "☀️"}</span>;
}

function ThemeToggleButton() {
  const toggle = useSetAtom(toggleThemeAtom);  // write only, no subscription
  return <button onClick={toggle}>Toggle</button>;
}
```

### Why atomic, not monolithic

Redux and Zustand have a single store; every subscriber receives updates on every store change and opts out via selectors. Jotai inverts the model: every atom is its own micro-store, and subscription is exactly at the atom boundary. The effect in practice: fewer unnecessary re-renders, less wrapper boilerplate, and derived state "just works" via `atom((get) => ...)`.

The cost: no single place to look for "all application state." Debugging means knowing which atoms exist. Devtools (`jotai-devtools`) help.

### Async atoms

Jotai first-classes promise-returning atoms with Suspense:

```typescript
const userAtom = atom(async (get) => {
  const id = get(currentUserIdAtom);
  const res = await fetch(`/api/users/${id}/`);
  return res.json();
});

function User() {
  const user = useAtomValue(userAtom);   // suspends until resolved
  return <div>{user.name}</div>;
}
```

For network-backed state you'd almost always prefer TanStack Query; reach for async atoms for things like deriving against a promise-returning utility (e.g. loading a user's local IndexedDB state, or awaiting a Web Crypto operation).

### Persistence

```typescript
import { atomWithStorage } from "jotai/utils";

const sidebarOpenAtom = atomWithStorage("sidebarOpen", true);
// Reads from / writes to localStorage automatically.
```

Use for UI prefs and ephemeral client state. Do not use for anything sensitive — localStorage is plaintext and readable by any XSS.

### Patterns worth knowing

- **`atomFamily`**: one atom per key (e.g. `itemAtom(id)` returns a unique atom per id). Useful for per-row UI state in lists.
- **`selectAtom`**: subscribe to a slice of an atom, with custom equality.
- **`splitAtom`**: turn `atom<T[]>` into an atom of atoms; each item re-renders independently.
- **Provider-scoped atoms**: `<Provider>` boundaries give you isolated atom stores, useful for per-route scratch state that dies on navigation.

### Integration with TanStack Query

Do not store TanStack Query results in Jotai atoms. Query data should live in the query cache; atoms reference query *keys* or *parameters*:

```typescript
const selectedProductionIdAtom = atom<string | null>(null);

function ScorecardPanel() {
  const productionId = useAtomValue(selectedProductionIdAtom);
  const { data } = useQuery({
    queryKey: ["scorecard", productionId],
    queryFn: () => api.getScorecard(productionId!),
    enabled: productionId !== null,
  });
  return <div>{data?.meanOverall}</div>;
}
```

The atom controls *what* to fetch; TanStack Query caches, refreshes, and invalidates the *result*.

---

## 12. Render — deployment platform

Render is a PaaS in the Heroku / Fly / Railway space. Better Base targets Render with a `render.yaml` blueprint that defines the whole deployment declaratively.

### `render.yaml` blueprint

```yaml
# render.yaml
databases:
  - name: rate-my-set-postgres
    databaseName: rate_my_set
    plan: starter
    postgresMajorVersion: 16

services:
  - type: redis
    name: rate-my-set-redis
    plan: starter
    maxmemoryPolicy: allkeys-lru
    ipAllowList: []           # only allow from Render's private network

  - type: web
    name: rate-my-set-api
    runtime: docker
    plan: standard
    dockerfilePath: ./deploy/Dockerfile.api
    healthCheckPath: /api/health/
    autoDeploy: true
    envVars:
      - key: DJANGO_SETTINGS_MODULE
        value: config.settings.production
      - key: DATABASE_URL
        fromDatabase:
          name: rate-my-set-postgres
          property: connectionString
      - key: REDIS_URL
        fromService:
          type: redis
          name: rate-my-set-redis
          property: connectionString
      - key: DJANGO_SECRET_KEY
        generateValue: true
      - fromGroup: rate-my-set-secrets   # externally managed secret group

  - type: worker
    name: rate-my-set-celery
    runtime: docker
    plan: standard
    dockerfilePath: ./deploy/Dockerfile.worker
    envVars:
      - fromGroup: rate-my-set-secrets
      - key: DATABASE_URL
        fromDatabase:
          name: rate-my-set-postgres
          property: connectionString

  - type: worker
    name: rate-my-set-celery-beat
    runtime: docker
    plan: starter             # only one instance; small
    dockerfilePath: ./deploy/Dockerfile.beat
    envVars:
      - fromGroup: rate-my-set-secrets

  - type: cron
    name: rate-my-set-nightly-sanitize
    runtime: docker
    dockerfilePath: ./deploy/Dockerfile.api
    schedule: "0 3 * * *"
    dockerCommand: uv run python manage.py sanitize_published_reviews
    envVars:
      - fromGroup: rate-my-set-secrets

  - type: web
    name: rate-my-set-frontend
    runtime: static
    rootDir: frontend
    buildCommand: bun install --frozen-lockfile && bun run build
    staticPublishPath: ./dist
    routes:
      - type: rewrite
        source: /api/*
        destination: https://rate-my-set-api.onrender.com/api/*
      - type: rewrite
        source: /*
        destination: /index.html       # SPA fallback
    headers:
      - path: /*
        name: X-Frame-Options
        value: DENY
      - path: /assets/*
        name: Cache-Control
        value: public, max-age=31536000, immutable
```

### Service types

- **Web Service**: long-running HTTP service, autoscaling, zero-downtime deploys via health checks.
- **Worker**: no HTTP, used for Celery workers, long-running consumers.
- **Cron Job**: scheduled one-shot container.
- **Private Service**: HTTP service not exposed publicly; accessible to other services in the same Render workspace via the internal DNS name.
- **Static Site**: CDN-backed static artifact; `buildCommand` runs in CI, `staticPublishPath` is served.
- **Managed Database**: Postgres (managed). Backups, point-in-time recovery on paid plans.
- **Redis**: managed Redis with configurable eviction policy.

### Env vars and env groups

Three ways to set env vars, in increasing separation:

1. Inline in `render.yaml` (visible in repo — only for non-secret values).
2. `generateValue: true` (Render generates a random secret at first deploy; good for `SECRET_KEY`).
3. Env groups (managed in the Render dashboard, referenced by name from `render.yaml`). This is the right place for API keys, database credentials for external services, Sentry DSNs.

`fromDatabase` and `fromService` wire up internal connection strings automatically, so DB and Redis hostnames never need to be hardcoded.

### Zero-downtime deploy

Render deploys by starting new instances, waiting for the `healthCheckPath` to return 200, then draining old instances. The deploy will abort if the new container fails health checks within a window.

Two failure modes to design around:

- Migrations: run migrations before the new web instance starts accepting traffic. The common pattern is a `preDeployCommand` field at the service level, or a pre-deploy `job` that runs `manage.py migrate` once against the shared DB.
- Celery beat: only one instance should run. Set `plan: starter` and do **not** scale; if you accidentally set `numInstances: 2` on a beat worker, you'll get duplicated periodic task dispatch.

### Preview environments

```yaml
previewsEnabled: true
previewsExpireAfterDays: 7
```

Each PR gets an ephemeral Render environment with its own database snapshot (or fresh DB) and per-service URL. Tear-down is automatic on merge or expiry.

### Logs and metrics

Render streams logs per service; `render logs -s service-name --tail` via the CLI. For anything beyond recent logs, forward to an external log pipeline (Logfire, Datadog, Better Stack) — the built-in log search is adequate but not great for incidents.

### Render-specific gotchas

- **File system is ephemeral.** Every deploy gets a fresh filesystem. Store nothing locally; use S3 for uploads, managed Postgres for data.
- **`/tmp` is small and shared** across requests within the same instance. Fine for streaming temp work; not fine for accumulating state.
- **Port binding**: the service must listen on `$PORT`, which Render sets. Gunicorn/uvicorn already honor this if configured.
- **Private services** are not free — routing between services is, but private services themselves are billed. For internal-only workloads, worker-type services are often a better fit than private services.

---

## 13. Putting it together

### Local dev (zero to running)

```bash
git clone …
task build                     # docker images + base venv
task back                      # postgres, redis, mailpit in compose
task migrate                   # apply migrations
uv run python manage.py runserver 0.0.0.0:4010 &
cd frontend && bun install && bun dev   # vite on :4020
```

### Local quality gate

```bash
task lint      # ruff, djlint
task flint     # oxlint, oxfmt, tsgo
task mp        # mypy
task tcov      # pytest with coverage
cd frontend && bun test       # vitest
```

Pre-commit (via prek) runs a subset of these on staged files automatically.

### CI (GitHub Actions example)

```yaml
# .github/workflows/ci.yml
name: ci
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - run: uv sync --frozen
      - run: uv run ruff check
      - run: uv run ruff format --check
      - run: uv run djlint templates/ --check
      - run: uv run mypy .
      - run: uv run pytest --cov --cov-fail-under=85

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: bun install --frozen-lockfile
      - run: bun x oxlint
      - run: bun x oxfmt --check
      - run: bun x tsgo --noEmit
      - run: bun test
      - run: bun run build        # smoke-test the vite build

  schema:
    runs-on: ubuntu-latest
    needs: [backend]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - uses: oven-sh/setup-bun@v2
      - run: uv sync --frozen
      - run: uv run python manage.py spectacular --file openapi.yaml
      - run: cd frontend && bun x openapi-typescript ../openapi.yaml -o src/api/schema.ts
      - run: git diff --exit-code      # fail if schema drifted
```

### Deploy flow

1. Push to `main`.
2. Render detects the push (via `autoDeploy: true`), builds the Docker images per `render.yaml`.
3. Pre-deploy hook runs `manage.py migrate`.
4. New web instance spins up, passes health check, old instance drains.
5. Celery worker and beat instances deploy the same way (beat with `numInstances: 1` to preserve the single-scheduler invariant).
6. Frontend static site rebuilds and invalidates Render's CDN.

The total cycle is typically 3–6 minutes from push to live.

---

## 14. Decision summary

- **uv** for all Python dependency and interpreter management; `uv sync --frozen` in CI.
- **ruff** replaces the entire Python lint/format stack; run both `ruff check --fix` and `ruff format`.
- **mypy + django-stubs** for type checking; consider `dmypy` locally.
- **djlint** for Django templates.
- **Bun** for JS install and script execution; Vite still handles bundling.
- **oxlint + oxfmt** for most lint/format needs; minimal ESLint config for type-aware rules only.
- **tsgo** for fast typechecking with a `tsc` fallback ready while the preview matures.
- **prek** as a drop-in pre-commit replacement.
- **Taskfile** as the single entry point for every developer workflow.
- **Jotai** for client state; TanStack Query for server state; don't mix them.
- **Render** with a `render.yaml` blueprint; env groups for secrets; preview envs per PR; beat always at `numInstances: 1`.

The payoff is a feedback loop where `task ci` runs the full quality gate in seconds rather than minutes, and deploy pipelines that keep up with the feedback loop.

---

## Sources

- uv docs: https://docs.astral.sh/uv/
- ruff docs: https://docs.astral.sh/ruff/
- djlint: https://djlint.com/
- mypy: https://mypy.readthedocs.io/
- django-stubs: https://github.com/typeddjango/django-stubs
- Bun docs: https://bun.sh/docs
- Oxc (oxlint/oxfmt): https://oxc.rs/
- TypeScript Go preview (`tsgo`): https://github.com/microsoft/typescript-go
- prek: https://github.com/j178/prek
- Taskfile: https://taskfile.dev/
- Jotai: https://jotai.org/
- Render Blueprint spec: https://render.com/docs/blueprint-spec
- Render deploy model: https://render.com/docs/deploys
- PEP 735 (Dependency Groups): https://peps.python.org/pep-0735/

Last updated: 2026-04-14
