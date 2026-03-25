---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related:
  - django-production-stack.md
  - drf-testing-pytest-django-perf-rec.md
  - django-tasks-framework.md
  - ../devops/redis-internals-and-operations.md
  - logfire-observability.md
  - ../web-fundamentals/http-protocol-reference.md
---

# Django caching with Redis

For Alex's stack, Redis is usually playing more than one role: cache, session store, and Celery broker/result backend. The useful design question is not just "how do I connect Redis?" but "which workloads may share Redis, and which ones should be isolated?" Django's 6.0 cache docs also make the native Redis backend story clearer than older guides did.

## Native Django Redis backend

Django 6.0 documents `django.core.cache.backends.redis.RedisCache` as the built-in Redis cache backend.

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
    }
}
```

The docs recommend `redis-py` and note optional `hiredis-py` support for a compiled parser.

## Multiple Redis servers and replication

Django's cache docs support multiple Redis URLs:

```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": [
            "redis://cache-leader:6379/1",
            "redis://cache-replica-1:6379/1",
            "redis://cache-replica-2:6379/1",
        ],
    }
}
```

Writes go to the first URL; reads are distributed among the others at random.

That is useful, but it also means cache consistency is only as good as your Redis replication lag. For correctness-sensitive data, cache should remain a performance layer rather than a source of truth.

## Built-in backend vs `django-redis`

Practical split:

- use Django's native `RedisCache` when you want the simplest officially documented path
- use `django-redis` when you specifically need its extra operational features or convenience helpers

The native backend is no longer a toy option. That changes the default recommendation from older Django-era advice.

## Separation of concerns inside Redis

Avoid mixing everything into one logical Redis store.

Minimal separation:

- cache on one DB/index or instance
- sessions on another
- Celery broker on another
- Celery result backend on another, or disable result storage where possible

If the stack becomes important in production, separate instances are safer than just separate logical DBs because eviction, persistence, and traffic patterns are different.

## Core cache API details worth using

```python
from django.core.cache import cache

cache.set("user:42:profile", data, timeout=300)
value = cache.get("user:42:profile")
cache.delete("user:42:profile")
cache.touch("user:42:profile", 300)
cache.set_many({"a": 1, "b": 2}, timeout=60)
values = cache.get_many(["a", "b"])
```

Two details often missed:

- `touch()` extends an existing key's TTL
- key transformation includes prefix and version, so `KEY_PREFIX` and `VERSION` are important operational tools

## `KEY_PREFIX` and `VERSION`

Django's cache docs explicitly document `KEY_PREFIX` and `VERSION` as part of cache-key generation.

Useful patterns:

- `KEY_PREFIX` isolates environments or services
- `VERSION` helps with coarse-grained invalidation during deploys

This is safer than global flushes and makes blue/green or staged deploys less painful.

## Cache-aside remains the default pattern

```python
def get_user_stats(user_id: int) -> dict:
    cache_key = f"user:{user_id}:stats"
    data = cache.get(cache_key)
    if data is None:
        data = compute_expensive_stats(user_id)
        cache.set(cache_key, data, timeout=300)
    return data
```

Still the best default for most application caches.

## Stampede control

The naive lock pattern still works for moderate traffic:

```python
import time
from django.core.cache import cache


def get_with_lock(cache_key, compute_fn, timeout=300):
    value = cache.get(cache_key)
    if value is not None:
        return value

    lock_key = f"lock:{cache_key}"
    if cache.add(lock_key, True, timeout=30):
        try:
            value = compute_fn()
            cache.set(cache_key, value, timeout=timeout)
            return value
        finally:
            cache.delete(lock_key)

    time.sleep(0.1)
    return cache.get(cache_key)
```

But for busy systems, this should evolve into a soft-TTL or stale-while-revalidate strategy rather than a pile-up on one hot key.

## Invalidation strategy matters more than backend choice

High-value habits:

- cache stable derived data, not everything
- invalidate by explicit key where possible
- version keys when data shape changes
- accept eventual freshness for obviously read-mostly data

The deeper rule is to align cache lifetime with business tolerance for staleness.

## Avoid `KEYS` in production

Pattern deletion based on `KEYS` is an operational footgun on large keyspaces. If you truly need wildcard invalidation, prefer versioned keys, explicit indexes, or at minimum `SCAN`-based approaches through a library that handles iteration safely.

## Sessions in Redis

Redis-backed sessions are often a good fit:

```python
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "session"
```

This is fast and horizontally friendly, but it increases the importance of Redis availability. If session continuity is mission-critical, Redis becomes part of the auth path, not just a performance optimization.

## Observability and operational checks

Caching needs metrics, not just configuration.

Useful signals:

- hit rate / miss rate
- Redis memory usage
- eviction count
- connection count
- slow commands
- cache latency on the Django side

If you cannot observe those, you are often guessing about whether the cache is helping or just complicating failures.

## Recommended stance for Alex's stack

- native `RedisCache` is a credible default now
- separate cache/session/Celery workloads
- prefer explicit invalidation and versioning over wildcard deletes
- use Redis for sessions only if you are comfortable making Redis part of the auth critical path
- treat cache metrics as part of production readiness

## Sources

- Django cache framework: https://docs.djangoproject.com/en/6.0/topics/cache/

Last updated: 2026-03-18
