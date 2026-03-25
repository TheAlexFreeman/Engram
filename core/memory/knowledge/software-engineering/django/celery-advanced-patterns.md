---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related:
  - celery-worker-beat-ops.md
  - django-migrations-advanced.md
  - celery-canvas-in-depth.md
  - pydantic-django-integration.md
  - logfire-observability.md
  - ../devops/sentry-fullstack-observability.md
---

# Celery advanced patterns

Celery remains the operationally complete background job system in this stack. The most important production lessons are not just chains and retries; they are idempotency, acknowledgement strategy, timeouts, queue isolation, and staying honest about which tasks should store results at all.

## Django integration baseline

Celery's current Django docs still recommend the familiar integration:

```python
# myproject/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

app = Celery("myproject")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

The `CELERY_` namespace is optional but recommended.

For reusable Django apps, `@shared_task` remains the clean default:

```python
from celery import shared_task


@shared_task
def send_email_task(user_id: int) -> None:
    ...
```

## Transaction safety first

This is still the most important Django/Celery pattern:

```python
from django.db import transaction


def create_order(user_id):
    with transaction.atomic():
        order = Order.objects.create(user_id=user_id)
        transaction.on_commit(lambda: process_order.delay(order.id))
```

Never enqueue work that depends on newly committed DB state before commit.

## Idempotency is not optional

Celery's task docs explicitly recommend that tasks be idempotent. This matters because delivery and worker-failure behavior can lead to re-execution.

Strong patterns:

- pass IDs, not model instances
- make external side effects deduplicable
- store provider correlation IDs for outbound calls
- guard write-once actions with unique constraints or idempotency keys

If a task cannot be safely repeated, design work around that constraint before tuning workers.

## Acknowledgements and worker-loss behavior

Celery's task docs explain the core tradeoff:

- default behavior acknowledges a task before execution
- `acks_late=True` acknowledges after the task returns

If the task is idempotent, `acks_late=True` can be useful. If it is not, early acknowledgement may be safer than duplicate execution. Celery also documents `task_reject_on_worker_lost` for cases where you want redelivery on worker loss.

## Timeouts and hanging I/O

Celery's docs are blunt here:

- add explicit network timeouts yourself
- use time limits as a backstop, not as the primary control

```python
import requests
from celery import shared_task


@shared_task(
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def call_external_api(payload: dict):
    response = requests.post(
        "https://api.example.com/",
        json=payload,
        timeout=(5.0, 30.0),
    )
    response.raise_for_status()
    return response.json()
```

## Keep long and short tasks on different workers

Celery recommends dedicated workers for different workload shapes. This is still good advice.

- short latency-sensitive work on one queue
- long-running work on another
- CPU-heavy work separated from I/O-heavy work

That matters more than clever global concurrency numbers.

## Canvas still matters

Celery's workflow primitives remain the main reason to stay on Celery instead of assuming `django.tasks` can replace it.

- `chain` for sequential workflows
- `group` for parallel fan-out
- `chord` for fan-out/fan-in

But Celery's own docs also caution against synchronous subtasks like `.delay(...).get()` inside tasks. That pattern can deadlock exhausted worker pools.

## Results: store fewer than you think

Celery's task docs explicitly say to ignore results you don't want because result storage costs time and resources.

```python
@shared_task(ignore_result=True)
def send_webhook(event_id: int) -> None:
    ...
```

For a lot of operational tasks, "fire, log, and monitor failures" is better than storing every result forever.

## Routing and queue design

Use queue separation to reflect business boundaries, not just component boundaries.

Useful queues:

- `default`
- `emails`
- `webhooks`
- `exports`
- `reports`
- `indexing`

If one class of work can flood the broker, it deserves its own queue and likely its own worker pool.

## Observability

Flower is useful, but it is not a complete observability story.

High-value signals:

- task success/failure rate
- retry count
- queue depth
- task runtime percentiles
- worker restarts
- broker connection issues

Push real failures into Sentry/logging/metrics instead of relying only on Flower dashboards.

## Celery vs Django tasks

The clean distinction is:

- use Celery when you need operational machinery
- use `django.tasks` only when a standard Django task API brings real value and the backend story is clear

Do not treat Django 6.0's task framework as a drop-in simplification of Celery for production workloads.

## Sources

- Celery tasks guide: https://docs.celeryq.dev/en/stable/userguide/tasks.html
- Celery with Django: https://docs.celeryq.dev/en/latest/django/first-steps-with-django.html

Last updated: 2026-03-18
