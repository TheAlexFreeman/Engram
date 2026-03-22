---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
---

# Django production stack: Postgres + Redis + Celery + Docker

This is a practical synthesis for Alex's actual backend stack. The main architectural move is to separate responsibilities clearly: Django handles request/response and domain logic, Postgres is the source of truth, Redis is infrastructure for ephemeral coordination, and Celery handles background execution. Docker gives reproducible packaging, but it does not remove the need to think about startup order, migrations, storage, and observability.

## Service boundaries

Typical service split:

- `web`: Django app process
- `worker`: Celery worker
- `beat`: Celery beat if periodic jobs are needed
- `postgres`: primary database
- `redis`: cache and/or broker infrastructure
- optional reverse proxy, object storage, and monitoring services

The important point is that `web`, `worker`, and `beat` are different runtime roles even if they share one image.

## Startup ordering

The safe order is not just "containers started"; it is "dependencies ready enough for use."

Operational sequence:

1. Postgres reachable
2. Redis reachable
3. Run migrations
4. Start Django web
5. Start Celery workers
6. Start Celery beat

Workers should not come up against an unmigrated database if tasks depend on new schema.

## Migrations and deploy discipline

For this stack, migrations are part of deploy, not an afterthought.

High-value rules:

- run migrations before workers consume schema-dependent tasks
- use additive migrations first for large changes
- avoid deploys where old workers and new schema assumptions are wildly incompatible

If a migration is long-running or disruptive, queue behavior becomes part of rollout planning.

## Redis topology

Redis is usually the easiest service to overload by accident because teams pile too many roles onto it.

Safer split:

- cache on one logical DB or instance
- sessions on another
- Celery broker on another
- result backend on another, or disable result storage where unnecessary

Once throughput matters, separate instances are often cleaner than separate DB numbers because eviction and persistence expectations differ.

## Postgres role

Postgres is the durable system of record. Background jobs should treat it that way:

- pass primary keys into tasks
- re-read current state in the task
- avoid assuming request-time in-memory objects are still authoritative

That aligns naturally with Django ORM patterns and reduces serialization mistakes.

## Static and media handling

Do not treat Docker containers as durable asset stores.

Normal pattern:

- static files built and collected during build/release
- user-uploaded media stored outside the app container, usually object storage or mounted durable storage

This matters because web and worker containers should be replaceable at any time.

## Health and readiness

Health checks should reflect dependency truth, not just process existence.

Useful checks:

- web process can import settings and open DB connection
- Postgres reachable
- Redis reachable
- worker heartbeat or queue responsiveness
- migrations up to date, if your platform supports a readiness distinction

## Observability

Minimum useful observability for this stack:

- Django error reporting and structured logs
- Celery task failures and retry visibility
- queue depth and worker runtime metrics
- Postgres slow queries / query plans
- Redis memory and eviction metrics

Flower helps for Celery visibility, but it is not a substitute for logs, metrics, and alerts.

## Security and secrets

Keep these explicit:

- Django secret key
- database credentials
- Redis credentials if exposed beyond trusted network
- allowed hosts / CORS / CSRF trusted origins
- object-storage credentials

Do not bake production secrets into images. Docker makes that mistake easy to operationalize at scale.

## Good fit for this stack

This stack is strongest when:

- Django remains the source of truth for business logic
- Postgres holds durable truth
- Redis is used for ephemeral coordination and caching
- Celery handles asynchronous execution with clear queue boundaries
- Docker standardizes packaging without becoming the architecture itself

## Related files

- [django-react-drf.md](django-react-drf.md)
- [django-caching-redis.md](django-caching-redis.md)
- [celery-advanced-patterns.md](celery-advanced-patterns.md)
- [django-orm-postgres.md](django-orm-postgres.md)

## Sources

- Django cache framework: https://docs.djangoproject.com/en/6.0/topics/cache/
- Celery with Django: https://docs.celeryq.dev/en/latest/django/first-steps-with-django.html
- Celery tasks guide: https://docs.celeryq.dev/en/stable/userguide/tasks.html

Last updated: 2026-03-18
