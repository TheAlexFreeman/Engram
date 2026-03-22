---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - docker-compose-local-dev.md
  - docker-production-config.md
  - github-actions-cicd.md
---

# Dev Workflow Tooling

Tooling that makes the development loop faster and consistent across contributors: Makefile tasks, pre-commit hooks, ruff, mypy, remote debugging in Docker, and frontend dev server patterns.

---

## 1. Makefile as dev interface

A project Makefile provides consistent, discoverable commands that work the same for every contributor regardless of their shell setup.

```makefile
# Makefile
.PHONY: help up down logs shell migrate test lint build clean seed

## help: Print this message
help:
	@grep -h '##' $(MAKEFILE_LIST) | grep -v grep | sed 's/## //' | column -t -s ':'

## up: Start all services in the background
up:
	docker compose up -d

## down: Stop all services
down:
	docker compose down

## logs: Follow logs for all services (Ctrl+C to stop)
logs:
	docker compose logs -f

## shell: Open a Django shell_plus in the web container
shell:
	docker compose run --rm web python manage.py shell_plus

## migrate: Run Django migrations
migrate:
	docker compose run --rm web python manage.py migrate

## makemigrations: Create new migrations
makemigrations:
	docker compose run --rm web python manage.py makemigrations

## test: Run Django tests with coverage
test:
	docker compose run --rm web pytest --tb=short --reuse-db

## lint: Run all linters (ruff, mypy)
lint:
	docker compose run --rm web ruff check .
	docker compose run --rm web ruff format --check .
	docker compose run --rm web mypy .

## build: Build production Docker image
build:
	docker build --target production -t myapp:latest .

## clean: Remove stopped containers, volumes, and build cache
clean:
	docker compose down -v --remove-orphans
	docker builder prune -f

## seed: Seed the database with development data
seed:
	docker compose run --rm web python manage.py seed --flush

## frontend: Start Vite dev server on host (requires Node.js)
frontend:
	cd frontend && npm run dev

DJANGO_MANAGE := docker compose run --rm web python manage.py

## superuser: Create a Django superuser
superuser:
	$(DJANGO_MANAGE) createsuperuser
```

Self-documenting help via `##` comment convention:

```
$ make help
up         Start all services in the background
down       Stop all services
logs       Follow logs for all services (Ctrl+C to stop)
shell      Open a Django shell_plus in the web container
migrate    Run Django migrations
...
```

---

## 2. pre-commit

`pre-commit` runs hooks before each commit, catching errors before CI catches them.

```bash
pip install pre-commit
pre-commit install   # installs the git hook
```

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.9.0
    hooks:
      - id: mypy
        additional_dependencies:
          - django-stubs[compatible-mypy]
          - djangorestframework-stubs

  - repo: https://github.com/Riverside-Healthcare/djLint
    rev: v1.34.1
    hooks:
      - id: djlint-django  # HTML template formatter/linter

  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v8.57.0
    hooks:
      - id: eslint
        files: \.tsx?$
        additional_dependencies:
          - eslint
          - "@typescript-eslint/parser"
          - "@typescript-eslint/eslint-plugin"

  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: v3.2.5
    hooks:
      - id: prettier
        types_or: [typescript, tsx, json, css, markdown]

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ["--baseline", ".secrets.baseline"]
```

```bash
# Run against all files (not just staged):
pre-commit run --all-files

# Update hook versions:
pre-commit autoupdate

# Skip a hook temporarily:
SKIP=mypy git commit -m "wip"

# In CI (GitHub Actions):
- uses: pre-commit/action@v3.0.0
```

---

## 3. ruff

`ruff` replaces black, isort, flake8, pyupgrade, and more in a single fast tool.

```toml
# pyproject.toml
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["config", "apps", "tests"]

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear (common bugs)
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade (modernize syntax)
    "DJ",  # flake8-django (Django-specific rules)
    "S",   # flake8-bandit (security)
    "RUF", # ruff-specific rules
]
ignore = [
    "E501",   # line too long (ruff format handles this)
    "S101",   # use of `assert` (fine in tests)
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S106"]   # assert and hardcoded passwords ok in tests
"**/migrations/**" = ["E501"]   # long lines in migrations are acceptable

[tool.ruff.lint.isort]
known-django = ["django"]
known-first-party = ["config", "apps"]
section-order = ["future", "standard-library", "django", "third-party", "first-party", "local-folder"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

```bash
# Auto-fix most issues:
ruff check --fix .

# Check and format:
ruff format .

# Check if formatting is needed (CI):
ruff format --check .
```

---

## 4. mypy with Django

```bash
pip install mypy django-stubs djangorestframework-stubs
```

```ini
# mypy.ini (or [tool.mypy] in pyproject.toml)
[mypy]
python_version = 3.12
django_settings_module = config.settings.test
plugins = mypy_django_plugin.main, mypy_drf_plugin.main

# Start with these flags; enable strict incrementally
strict = false
disallow_untyped_defs = true
warn_return_any = true
warn_unused_ignores = true
ignore_missing_imports = false

# Exclude generated code
exclude = ['migrations/', 'venv/', '.venv/']

[mypy.plugins.django-stubs]
django_settings_module = "config.settings.test"

# Third-party packages without stubs
[mypy-factory_boy.*]
ignore_missing_imports = true
[mypy-celery.*]
ignore_missing_imports = true
```

```python
# reveal_type for debugging during development:
x = SomeModel.objects.get(pk=1)
reveal_type(x)  # mypy outputs the inferred type; remove before committing
```

### Incremental adoption strategy

1. Add `ignore_missing_imports = true` initially to suppress noise from third-party packages
2. Fix all `disallow_untyped_defs` errors in new code
3. Enable `warn_return_any = true` for return type safety
4. Gradually add `strict = true` per module via per-module overrides

---

## 5. Remote debugging Django in Docker

Standard Django dev server (`runserver`) doesn't work with external debuggers because it restarts processes. Use `debugpy` instead.

### Setup

```bash
pip install debugpy
```

```python
# config/settings/development.py
import debugpy

# Only start debugpy if the listener isn't already running
if not debugpy.is_client_connected():
    debugpy.listen(("0.0.0.0", 5678))
    # Optionally wait for debugger before proceeding:
    # debugpy.wait_for_client()
```

Alternative: launch via command line (more explicit):

```dockerfile
# docker-compose.override.yml (gitignored or committed for shared use)
services:
  web:
    command: python -m debugpy --listen 0.0.0.0:5678 manage.py runserver 0.0.0.0:8000
    ports:
      - "5678:5678"   # debugpy
    stdin_open: true
    tty: true
```

### VS Code launch.json

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Django (Docker)",
      "type": "debugpy",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      },
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}",
          "remoteRoot": "/app"
        }
      ],
      "django": true
    }
  ]
}
```

`pathMappings` maps local source files to their paths inside the container, enabling breakpoints to work correctly.

---

## 6. Frontend Vite dev server outside Docker

Running Vite on the host (not in Docker) provides fast HMR without file-watching latency through Docker bind mounts.

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",  // Django in Docker (exposed port)
        changeOrigin: true,
      },
      "/admin": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/static": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

```yaml
# docker-compose.override.yml — expose Django's port to host
services:
  web:
    ports:
      - "8000:8000"
```

Development workflow:
1. `make up` — start Postgres, Redis, Django (with port 8000 exposed)
2. `cd frontend && npm run dev` — Vite on localhost:5173
3. Browser hits `localhost:5173` — Vite serves React, proxies `/api/` to Django

No Docker involvement in the hot-reload loop.

---

## 7. Docker Compose watch mode

Docker Compose v2.22+ supports `develop.watch` as an alternative to bind mounts. It syncs files from host to container without full bind mount overhead, avoiding Windows/Mac filesystem performance issues.

```yaml
# docker-compose.yml
services:
  web:
    develop:
      watch:
        - action: sync
          path: ./apps
          target: /app/apps
          ignore:
            - "**/__pycache__"
            - "**/*.pyc"

        - action: sync+restart
          path: ./config
          target: /app/config

        - action: rebuild
          path: ./requirements.txt
```

Actions:
- `sync` — copy changed files into the container (Django autoreload picks them up)
- `sync+restart` — sync then restart the container service
- `rebuild` — rebuild the Docker image (needed when dependencies change)

```bash
docker compose watch   # runs compose up + watch in one command
```

---

## 8. Environment parity checklist

Differences between local dev, CI, and production are a primary source of "works on my machine" bugs.

```bash
# Inspect the fully-resolved Compose config (variable substitution applied):
docker compose config

# Compare service definitions across files:
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```

Key parity points to document and check:

| Setting | Dev | CI | Production |
|---|---|---|---|
| `DEBUG` | true | false | false |
| `DATABASES` host | postgres (container) | localhost (service) | RDS/external |
| Static files | Whitenoise or volume | Built in CI | nginx or S3 |
| Celery | eager (sync) or separate | eager | separate workers |
| Email | console backend | dummy | SMTP/SES |
| Volumes | bind mount | none | named volumes |

Document any intentional divergences in `docker-compose.override.yml` comments and the project README so contributors understand differences explicitly rather than discovering them through failures.
