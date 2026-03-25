---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related:
  - django-production-stack.md
  - django-async.md
  - django-caching-redis.md
---

# Django 6.0 Tasks Framework (`django.tasks`)

Django 6.0 introduces a standardized background task API, but the official docs are careful about the boundary: Django handles task definition, validation, queuing, and result handling, not execution. The built-in backends are for development/testing only. For Alex's stack, that makes `django.tasks` an architectural standardization tool, not a Celery replacement.

## What Django actually ships

### Built-in backends

Django 6.0 ships two built-in backends:

- `ImmediateBackend` for local synchronous execution
- `DummyBackend` for development/testing, storing results without executing work

The official docs explicitly say the built-in backends are suitable for development and testing only. Production systems need a third-party backend that supplies both a worker process and a durable queue.

## Core API

```python
from django.tasks import task


@task
def send_welcome_email(user_id: int) -> None:
    user = User.objects.get(pk=user_id)
    send_email(user.email)


result = send_welcome_email.enqueue(user_id=42)
retrieved = send_welcome_email.get_result(result.id)
print(retrieved.status)
```

Important details from the docs:

- tasks are defined on module-level functions
- task arguments and return values must be JSON-serializable
- arguments must survive a JSON round-trip without changing meaning

That means model instances, `datetime`, `tuple`, and other richer objects should generally be converted to primitive IDs/strings before enqueueing.

## Task features worth knowing

### Task options

```python
from django.tasks import task


@task(priority=2, queue_name="emails")
def email_users(emails, subject, message):
    return send_mail(subject=subject, message=message, from_email=None, recipient_list=emails)
```

### Task context

```python
import logging
from django.tasks import task

logger = logging.getLogger(__name__)


@task(takes_context=True)
def email_users(context, emails, subject, message):
    logger.debug(
        "Attempt %s for result %s",
        context.attempt,
        context.task_result.id,
    )
    return send_mail(subject=subject, message=message, from_email=None, recipient_list=emails)
```

### Per-call overrides with `using()`

```python
high_priority = email_users.using(priority=10, queue_name="vip-emails")
high_priority.enqueue(emails=["user@example.com"], subject="Hello", message="Hi")
```

This is one of the cleaner design choices in `django.tasks`: the base task definition stays stable, and enqueue-time overrides produce a modified task instance instead of mutating the original.

## Transactions: the most important caveat

The task docs explicitly warn that most backends run tasks in another process on another database connection. If you enqueue inside a transaction, the worker may start before the transaction commits.

```python
from functools import partial
from django.db import transaction


@task
def process_order(order_id):
    Order.objects.get(pk=order_id)


with transaction.atomic():
    order = Order.objects.create(...)
    transaction.on_commit(partial(process_order.enqueue, order_id=order.id))
```

This is the same race that Celery users solve with `transaction.on_commit(...)`. `django.tasks` does not remove that requirement in the general case.

## What `django.tasks` does not include

The official framework is intentionally smaller than Celery. Out of the box it does not provide:

- a production worker implementation
- scheduling / periodic jobs
- workflow composition like chains, groups, or chords
- retry/backoff orchestration comparable to Celery
- mature monitoring comparable to Flower

That keeps the API small, but it also means teams should resist reading more capability into it than the docs claim.

## Decision boundary for Alex's stack

### Strong fits for `django.tasks`

- simple fire-and-forget jobs
- apps that want a Django-native task API first and can choose a backend later
- projects that want to standardize task definitions across teams or apps
- test/dev workflows where `ImmediateBackend` is convenient

### Strong fits for Celery

- periodic work
- retries with backoff/jitter
- queue routing at scale
- chains, groups, chords, fan-out/fan-in workflows
- observability, worker tuning, and mature ecosystem tooling

### Coexistence model

The cleanest coexistence model is:

- use `django.tasks` only if a backend in your stack actually benefits from the API standardization
- keep Celery for operationally important background work
- do not assume Django's built-in Tasks framework removes the need for worker design, idempotency, or transaction safety

## Practical comparison with Celery

| Capability | `django.tasks` | Celery |
|---|---|---|
| Standard Django API | Yes | No |
| Built-in production worker | No | Yes |
| Built-in scheduling | No | Yes |
| Built-in workflow composition | No | Yes |
| Built-in retry/backoff model | No | Yes |
| Built-in monitoring ecosystem | No | Yes |
| Dev/test synchronous backend | Yes | Yes (`task_always_eager`) |

## Bottom line

`django.tasks` is best understood as a standard interface, not a complete job system. In Django 6.0, it is most valuable as a clean abstraction layer and a future integration point for third-party backends. For Alex's Django/Postgres/Redis/Celery stack, Celery remains the operationally complete choice for serious background processing.

## Sources

- Django tasks topic guide: https://docs.djangoproject.com/en/6.0/topics/tasks/
- Django tasks reference: https://docs.djangoproject.com/en/6.0/ref/tasks/
- Django 6.0 release notes: https://docs.djangoproject.com/en/6.0/releases/6.0/

Last updated: 2026-03-18
