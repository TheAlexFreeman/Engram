---
type: summary
related:
  - docker-compose-local-dev.md
  - docker-production-config.md
  - zero-downtime-deploys.md
---

# DevOps — Docker, CI/CD, Monitoring

Infrastructure for Django + React + Celery + Redis + Postgres. Promoted 2026-03-20.

## Docker

- `docker-compose-local-dev.md` — Local dev Compose, depends_on, volumes, management commands
- `docker-production-config.md` — **Start here.** Multi-stage Dockerfile, non-root user, secrets, entrypoint
- `docker-database-ops.md` — Postgres/Redis in containers, backups, migrations

## Celery in containers

- `celery-multi-worker-docker.md` — Queue separation, pool types (prefork/gevent), scaling, beat singleton
- `celery-flower-monitoring.md` — Flower setup, metrics, Celery visibility

## Deployment

- `nginx-django-react.md` — Reverse proxy for Django API + React SPA
- `zero-downtime-deploys.md` — Rolling deploys, migration strategy
- `github-actions-cicd.md` — CI/CD pipelines
- `environment-secrets-management.md` — Secrets injection, env handling
- `dev-workflow-tooling.md` — Dev tooling, scripts, workflows

## Data stores and observability

- `redis-internals-and-operations.md` — Redis data structures, persistence, HA, monitoring, production tuning
- `sentry-fullstack-observability.md` — Sentry across Django + React + Celery: distributed tracing, source maps, releases, alerts
