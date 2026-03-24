# Software Engineering — Django, React, DevOps

Promoted 2026-03-20. Stack knowledge for Alex's primary development environment: Django backends, React + Chakra frontends, Postgres, Redis, Celery, and Docker-based deployment.

## Subfolders

| Folder | Scope | Key entry points |
|--------|-------|------------------|
| [django/](django/) | Django 6.0, DRF, Celery, ORM, migrations, observability | `django-production-stack.md`, `django-6.0-whats-new.md` |
| [react/](react/) | React 19, Chakra UI 3, TanStack, testing, build tooling | `react-19-overview.md`, `chakra-ui-3-overview.md` |
| [devops/](devops/) | Docker Compose, production config, CI/CD, monitoring | `docker-production-config.md`, `celery-multi-worker-docker.md` |
| [testing/](testing/) | Unit, integration, system, performance, formal verification, ML evaluation | `testing-foundations-epistemology.md`, `unit-testing-principles.md` |
| [ai-engineering/](ai-engineering/) | AI-assisted development workflows, prompt engineering, code review, context management, agent tooling, trajectory | `ai-assisted-development-workflows.md`, `prompt-engineering-for-code.md` |
| [web-fundamentals/](web-fundamentals/) | HTTP, DNS/TLS, CORS, browser/DOM, JS core, HTML/a11y, CSS, web storage, OWASP, API design (10 files) | `http-protocol-reference.md`, `browser-dom-events.md`, `owasp-frontend-security.md` |

## Cross-stack integration

- `django/django-react-drf.md` — API design for React frontends
- `devops/docker-production-config.md` — Full-stack production Docker patterns
- `devops/nginx-django-react.md` — Reverse proxy for Django + SPA

## Observability triangle

- `django/django-observability-structlog-sentry.md` — structlog for structured event streams
- `django/logfire-observability.md` — Logfire for OpenTelemetry traces, spans, and performance profiling
- `devops/sentry-fullstack-observability.md` — Sentry for error tracking, distributed tracing, and release health
