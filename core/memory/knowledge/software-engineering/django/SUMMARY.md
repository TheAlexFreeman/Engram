---
type: summary
related:
  - django-react-drf.md
  - drf-spectacular.md
  - django-storages.md
---

# Django Stack

Django 6.0, DRF, Celery, Postgres, Redis. Promoted 2026-03-20.

## Core framework

- `django-6.0-whats-new.md` — Template partials, `django.tasks`, CSP, email API, ORM changes, deprecations
- `django-tasks-framework.md` — Built-in vs Celery decision boundary, transaction caveats
- `django-async.md` — Async support, ORM and view patterns

## ORM and database

- `django-orm-postgres.md` — Advanced ORM, Postgres features, `Lexeme`, indexing
- `django-database-pooling.md` — pgBouncer, transaction pooling, `DISABLE_SERVER_SIDE_CURSORS`
- `django-migrations-advanced.md` — Zero-downtime patterns, large migrations
- `psycopg3-and-connection-management.md` — Psycopg 3 async, pooling, pipeline mode, COPY, migration from psycopg2

## API and React integration

- `django-react-drf.md` — Auth modes, CSRF/CORS, pagination, filtering, error contracts
- `drf-spectacular.md` — OpenAPI generation
- `drf-testing-pytest-django-perf-rec.md` — DRF testing, pytest-django, django-perf-rec

## Celery

- `celery-advanced-patterns.md` — Idempotency, acks_late, retries, queue isolation
- `celery-canvas-in-depth.md` — Chain, group, chord, workflow composition
- `celery-worker-beat-ops.md` — Pool types, beat singleton, graceful shutdown
- `django-test-data-factories.md` — Factory Boy, test data patterns

## Production and observability

- `django-production-stack.md` — **Start here.** Service boundaries, startup order, migrations, Redis topology
- `django-caching-redis.md` — Cache backend, invalidation, Celery separation
- `django-observability-structlog-sentry.md` — Structured logging, Sentry integration
- `logfire-observability.md` — Pydantic Logfire: OpenTelemetry-native tracing for Django, Celery, psycopg, Redis
- `django-gunicorn-uvicorn.md` — ASGI/WSGI servers
- `django-security.md` — Security checklist
- `django-storages.md` — S3, media handling

## Validation and settings

- `pydantic-django-integration.md` — Pydantic settings, Celery payload validation, django-ninja, comparison with DRF serializers
