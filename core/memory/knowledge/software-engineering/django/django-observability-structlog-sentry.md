---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related:
  - logfire-observability.md
  - ../devops/sentry-fullstack-observability.md
---

# Django observability with structlog and Sentry

For this stack, structlog and Sentry solve different observability problems. structlog gives the app a disciplined stream of structured events that are good for local debugging, log pipelines, and request/task correlation. Sentry gives the team error monitoring, tracing, and targeted performance visibility. The clean design is not "pick one"; it is "use structlog for structured event context, and use Sentry for incident triage and sampled performance data."

## structlog

### What structlog is optimizing for

The current structlog docs describe it as a production-ready structured logging solution and emphasize that it can either render output itself or forward to the standard library `logging` system. The important practical consequence is that a Django team can keep Python's logging ecosystem while still getting structured events and processor pipelines.

The current stable docs are on the `25.5.0` line.

Out of the box, structlog supports:

- JSON output
- logfmt
- pretty console output
- standard-library logging integration

### Context variables are the key primitive

The `contextvars` integration is the highest-value structlog feature for web apps and workers. The docs recommend a clear flow:

1. clear context at request/task start
2. bind request/task metadata with `bind_contextvars()`
3. merge those values into all later log events via `merge_contextvars()`

This is the cleanest route to pervasive request IDs, task IDs, user IDs, and route metadata without manually passing them through every function call.

### Django-specific guidance

The structlog framework docs say `django-structlog` is a popular and well-maintained package that does the heavy lifting. That is a useful signal for teams that want the pattern but do not want to hand-roll every middleware and signal hookup.

If the team prefers a manual integration, the same underlying pattern still applies:

- clear/bind context at request start
- merge contextvars in the processor chain
- emit JSON in production and prettier output locally

### Celery-specific guidance

The structlog framework docs call out Celery explicitly:

- use Celery's `get_task_logger()` helpers to avoid interleaving problems in multiprocess workers
- wrap that logger with structlog when integrating the two
- optionally bind `task_id` and `task_name` via Celery signals such as `task_prerun`

That means the logging story for workers should not be treated as identical to web-request logging. Celery has its own process model and should be wired with that in mind.

## Sentry

### What Sentry is for in this stack

The official Sentry Python SDK is the right layer for:

- exception capture
- performance tracing
- custom span instrumentation
- cache performance visibility

The SDK should be initialized early in process startup. The official GitHub repo remains the source of truth for the Python SDK and shows the current 2.x line, with `2.55.0` marked as the latest release on March 17, 2026.

### Tracing and sampling

Sentry's current Python tracing docs recommend thinking explicitly about trace volume. The two primary knobs are:

- `traces_sample_rate`
- `traces_sampler`

The docs strongly recommend respecting `parent_sampled` when using `traces_sampler`, because that keeps distributed traces complete across services.

For a Django API, that suggests:

- low sampling for hot, low-value endpoints
- high sampling for checkout/auth/billing/admin or operationally sensitive flows
- inheritance preserved across downstream HTTP calls and workers where possible

### Custom spans

Sentry's Python tracing docs use context-manager spans as the primary custom instrumentation model. This is the cleanest way to mark expensive service-layer work, cache interactions, or third-party calls that matter to the team.

### Cache monitoring

Sentry's cache instrumentation docs say the cache dashboard can be auto-instrumented for popular Python caching setups including Django and Redis. For unsupported caching layers, the docs recommend manual spans with operations like:

- `cache.get`
- `cache.put`

That is directly relevant to this stack because Redis caching is already part of the Django deployment model.

## Structlog and Sentry together

The clean joint model is:

- structlog for dense structured event streams
- Sentry for errors, traces, and targeted health/performance monitoring

Good shared context fields:

- `request_id`
- `user_id` where appropriate
- `route`
- `method`
- `task_id`
- `task_name`
- `release`
- `environment`

The deeper point is consistency. If request IDs exist in logs but not in error context, or Celery task IDs exist in Sentry but not logs, incident debugging slows down immediately.

## Practical recommendations for this stack

- bind request/task metadata once near the boundary and let it flow through structlog contextvars
- prefer JSON logging in production
- keep web and Celery logging setup distinct even if they share one processor chain
- use Sentry tracing with explicit sampling instead of leaving high-volume APIs at full capture by default
- instrument high-value cache or service boundaries with spans when auto-instrumentation is insufficient
- treat structlog as the event stream and Sentry as the alerting/triage/performance layer, not as interchangeable products

## Related files

- [django-production-stack.md](django-production-stack.md)
- [celery-advanced-patterns.md](celery-advanced-patterns.md)
- [django-caching-redis.md](django-caching-redis.md)

## Sources

- structlog docs home: https://www.structlog.org/en/stable/
- structlog contextvars docs: https://www.structlog.org/en/25.3.0/contextvars.html
- structlog framework docs: https://www.structlog.org/en/stable/frameworks.html
- Sentry Python SDK repo: https://github.com/getsentry/sentry-python
- Sentry Python tracing sampling docs: https://docs.sentry.io/platforms/python/tracing/configure-sampling/
- Sentry Python cache instrumentation docs: https://docs.sentry.io/platforms/python/tracing/instrumentation/custom-instrumentation/caches-module/

Last updated: 2026-03-18
