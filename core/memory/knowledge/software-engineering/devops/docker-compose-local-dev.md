---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
tags: [docker, docker-compose, django, celery, local-dev, postgres, redis]
version_note: Docker Compose v2 (plugin, not standalone). Uses Compose spec features (depends_on conditions, develop.watch).
related:
  - docker-production-config.md
  - celery-multi-worker-docker.md
  - dev-workflow-tooling.md
  - redis-internals-and-operations.md
---

# Docker Compose — Local Development for the Full Django + Celery + React Stack

## Overview

A production-like local environment runs all services in Docker so behaviour matches staging/production. The setup covered here:

- `web` — Django (runserver in dev, gunicorn in CI/prod)
- `celery-worker` — one or more Celery worker containers
- `celery-beat` — Celery beat scheduler (one only)
- `postgres` — Postgres database
- `redis` — broker and cache
- `flower` — optional Celery task monitor

All backend services share a single `Dockerfile`. The React dev server typically runs on the host outside Docker (see note at the end).

---

## Project layout

```
project/
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── manage.py
│   └── ...
├── frontend/
│   └── ...
├── docker-compose.yml
├── docker-compose.override.yml   # dev-only; gitignored or committed
├── .env                          # gitignored
└── .env.example                  # committed; documents all required keys
```

---

## docker-compose.yml — base file

```yaml
# docker-compose.yml
# Base configuration shared across all environments.
# Dev overrides live in docker-compose.override.yml.

x-backend-common: &backend-common
  build:
    context: ./backend
    target: development           # multi-stage: development | production
  image: myapp-backend:local
  env_file: .env
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy

services:
  web:
    <<: *backend-common
    command: python manage.py runserver 0.0.0.0:8000
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app             # bind mount for hot reload
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s

  celery-worker:
    <<: *backend-common
    command: celery -A myapp worker -Q default -l INFO --autoreload
    volumes:
      - ./backend:/app

  celery-beat:
    <<: *backend-common
    command: celery -A myapp beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
    volumes:
      - ./backend:/app

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-myapp}
      POSTGRES_USER: ${POSTGRES_USER:-myapp}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-myapp}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"               # exposed for local psql / DB tools
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-myapp} -d ${POSTGRES_DB:-myapp}"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 10s

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  flower:
    <<: *backend-common
    command: celery -A myapp flower --port=5555
    ports:
      - "5555:5555"
    depends_on:
      - redis
      - celery-worker
    profiles:
      - monitoring                 # opt-in: docker compose --profile monitoring up

volumes:
  postgres_data:
  redis_data:
```

---

## depends_on with health checks — the critical detail

`depends_on: [postgres]` alone only waits for the container to *start*, not for Postgres to be *ready to accept connections*. During the ~1–3 seconds Postgres takes to initialize, Django's startup migrations will fail.

Use `condition: service_healthy` with a proper healthcheck:

```yaml
depends_on:
  postgres:
    condition: service_healthy   # waits for healthcheck to pass
  redis:
    condition: service_healthy
```

For Postgres, `pg_isready` is the correct healthcheck — it actually tests connectivity:

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
  interval: 5s
  timeout: 3s
  retries: 5
  start_period: 10s             # grace period before first check
```

`start_period` is important: it prevents the container being marked unhealthy during normal Postgres startup time.

---

## docker-compose.override.yml — dev-specific overrides

Docker Compose automatically merges `docker-compose.override.yml` with `docker-compose.yml`. Use it for dev-only settings that should not exist in CI or production:

```yaml
# docker-compose.override.yml
# Automatically merged by `docker compose up`. Do NOT use in CI.

services:
  web:
    environment:
      DJANGO_DEBUG: "True"
      DJANGO_SETTINGS_MODULE: myapp.settings.development
    ports:
      - "5678:5678"              # debugpy remote debugging port

  celery-worker:
    environment:
      DJANGO_SETTINGS_MODULE: myapp.settings.development
```

**Patterns**:

- Keep `docker-compose.yml` environment-agnostic (reads from `.env`, no hardcoded dev values)
- Put `DEBUG=True`, dev-only ports (debugpy, metrics), and `command:` overrides in `override.yml`
- For team-specific personal overrides that shouldn't be committed, create `docker-compose.local.yml` and add it to `.gitignore`; invoke with `docker compose -f docker-compose.yml -f docker-compose.local.yml up`

---

## Environment variable management

### .env file

```bash
# .env  (gitignored)
POSTGRES_DB=myapp
POSTGRES_USER=myapp
POSTGRES_PASSWORD=dev_password_only
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
SECRET_KEY=dev-only-secret-key-not-for-production
DJANGO_SETTINGS_MODULE=myapp.settings.development
```

```bash
# .env.example  (committed — documents all required keys)
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
REDIS_URL=
CELERY_BROKER_URL=
SECRET_KEY=
DJANGO_SETTINGS_MODULE=
```

### Compose precedence (highest → lowest)

1. `environment:` key in `docker-compose.yml`
2. `environment:` key in `docker-compose.override.yml`
3. Shell environment variable on the host
4. `env_file:` file (`.env`)
5. Dockerfile `ENV` instruction

### Inspecting resolved values

```bash
docker compose config           # shows fully resolved Compose config
docker compose exec web env     # shows runtime env inside the container
```

Never commit `.env`. Always commit `.env.example` with placeholder values and a comment explaining each key.

---

## Networking

Compose creates a default bridge network named `<project>_default`. Services can reach each other by their **service name**:

```python
# settings.py — use service names, not localhost
DATABASES = {'default': env.db('DATABASE_URL')}  # DATABASE_URL=postgres://user:pass@postgres:5432/myapp
CACHES = {'default': {'BACKEND': '...', 'LOCATION': 'redis://redis:6379/1'}}
CELERY_BROKER_URL = 'redis://redis:6379/1'
```

`postgres`, `redis`, `web` etc. resolve to container IPs automatically within the Compose network.

Ports exposed with `ports:` (e.g. `5432:5432`) are accessible from the **host machine** (for psql, DB clients, browser) but are not needed for inter-service communication.

---

## Named volumes vs bind mounts

| Type | Use case | Notes |
|---|---|---|
| Named volume (`postgres_data:`) | Persistent data (Postgres, Redis) | Managed by Docker; survives `down`; destroyed by `down -v` |
| Bind mount (`./backend:/app`) | Source code hot reload | Host filesystem; cross-OS file permission caveats |
| Anonymous volume | `node_modules` exclusion pattern | Prevents host `node_modules` from shadowing container's |

### node_modules exclusion (if running React in Docker)

```yaml
frontend:
  volumes:
    - ./frontend:/app
    - /app/node_modules          # anonymous volume shadows host node_modules
```

This prevents the host's `node_modules` (which may have different platform binaries) from leaking into the container.

### Data lifecycle

```bash
docker compose down          # stops containers, keeps volumes
docker compose down -v       # stops containers AND deletes named volumes (loses DB data)
docker compose down --rmi all  # also removes built images
```

---

## Hot reload

### Django runserver

`python manage.py runserver` watches for Python file changes automatically. With a bind mount (`./backend:/app`), edits on the host trigger an immediate reload inside the container.

### Celery --autoreload

```bash
celery -A myapp worker --autoreload
```

Celery's `--autoreload` restarts workers on Python file changes. **Caveats**:

- It uses `inotify` (Linux) or polling (macOS/Windows) — can be slow on large codebases
- It doesn't work reliably with prefork workers on some systems; use `solo` or `gevent` pool in dev
- In CI and production, always restart by redeploying the container instead

### Docker Compose `develop.watch` (v2.22+)

A more reliable alternative to bind mounts + `--autoreload` in some environments:

```yaml
services:
  celery-worker:
    develop:
      watch:
        - action: sync
          path: ./backend
          target: /app
          ignore:
            - __pycache__/
            - "*.pyc"
        - action: rebuild
          path: backend/requirements.txt
```

`action: sync` copies files without a full restart. `action: rebuild` triggers a full image rebuild when dependencies change. Invoke with `docker compose watch`.

---

## Running management commands

```bash
# Run migrations
docker compose exec web python manage.py migrate

# Create superuser
docker compose exec web python manage.py createsuperuser

# Django shell with shell_plus
docker compose exec web python manage.py shell_plus

# One-off command (doesn't require web to be running)
docker compose run --rm web python manage.py collectstatic --noinput

# Run tests inside the container
docker compose run --rm web pytest
```

`exec` runs a command in a **running** container. `run --rm` starts a **new** container, runs the command, and removes it — use for one-off tasks.

### Makefile aliases

```makefile
# Makefile

.PHONY: up down logs shell migrate test lint build

up:   ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

logs: ## Tail logs for all services
	docker compose logs -f --tail=100

shell: ## Django shell_plus
	docker compose exec web python manage.py shell_plus

migrate: ## Run migrations
	docker compose exec web python manage.py migrate

test: ## Run pytest
	docker compose run --rm web pytest

lint: ## Run ruff + mypy
	docker compose run --rm web ruff check . && docker compose run --rm web mypy .

build: ## Rebuild images
	docker compose build

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
```

---

## Log handling in development

```bash
# Follow all services
docker compose logs -f

# Follow specific services with recent history
docker compose logs -f --tail=50 web celery-worker

# One-shot dump of a service's logs
docker compose logs web > web.log
```

### structlog in development

Set `DJANGO_SETTINGS_MODULE` to a dev settings file that uses `ConsoleRenderer` (human-readable, coloured output) instead of the JSON renderer used in production:

```python
# settings/development.py
import structlog

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'structlog',
        },
    },
    'formatters': {
        'structlog': {
            '()': structlog.stdlib.ProcessorFormatter,
            'processor': structlog.dev.ConsoleRenderer(colors=True),
        },
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
}
```

In production, swap `ConsoleRenderer` for `structlog.processors.JSONRenderer()` (parseable by log aggregators). Same configuration structure, different leaf processor.

---

## Frontend — running Vite outside Docker

Running the React dev server on the host (not in Docker) is the recommended development approach:

- Full HMR with no Docker bind-mount latency
- No cross-OS file watcher issues
- Node toolchain stays on the host where it's fast

Configure Vite to proxy API calls to the Dockerized Django:

```ts
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
    },
  },
})
```

Django must have `ALLOWED_HOSTS = ['localhost', '127.0.0.1']` and `CORS_ALLOWED_ORIGINS = ['http://localhost:5173']` in dev settings.

---

## Common gotchas

**"Connection refused" on startup** — `depends_on: condition: service_healthy` wasn't used; Postgres wasn't ready when Django tried to connect. Add healthchecks.

**Stale Python bytecode causing weird errors** — Add `__pycache__/` to the bind mount's `.dockerignore` (or use `PYTHONDONTWRITEBYTECODE=1` in dev env).

**Celery worker not picking up code changes** — `--autoreload` only works on file system events. If it's not triggering, fall back to `docker compose restart celery-worker`.

**Port already in use** — Another service on the host is using 8000, 5432, or 6379. Change the host-side port in `docker-compose.override.yml` (e.g. `"8001:8000"`) without touching the base file.

**Volume data out of sync after schema changes** — `docker compose down -v` to wipe the Postgres volume and start fresh with `migrate`. Never do this in staging/production.
