---
source: external-research
origin_session: manual
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related:
  - ../devops/redis-internals-and-operations.md
---

# Celery worker and beat operations

Celery gets operationally sharp once you stop treating "a worker" as one thing. The real decisions are pool type, queue isolation, periodic scheduling strategy, and shutdown behavior during deploys. For Alex's Django stack, the safest default is still prefork workers for most queues, one dedicated beat instance, and explicit routing between short I/O tasks, long-running tasks, and CPU-heavy jobs.

## Worker pool types: choose for workload shape, not fashion

Celery's default pool is `prefork`, and that remains the safest production choice for most Django workloads. It gives process isolation, supports features like soft time limits and child recycling, and avoids many monkey-patching surprises.

```bash
celery -A myproject worker --loglevel=INFO --pool=prefork --concurrency=4
```

How the main pools differ:

- **prefork**: best general-purpose pool, especially when tasks touch Django ORM, CPU-heavy Python, or libraries that are not greenlet-safe
- **gevent / eventlet**: for high-concurrency I/O workloads, but only when the whole dependency stack cooperates with monkey patching; Celery's docs warn that alternative pools can disable features available in prefork
- **threads**: lighter than prefork, but still constrained by the GIL for CPU-bound Python work; useful only for specific I/O-heavy cases where thread safety is understood
- **solo**: one task at a time in-process; great for debugging and low-volume admin jobs, bad for throughput

The practical Django rule is simple:

- ORM-heavy tasks: prefer `prefork`
- CPU-heavy transforms: `prefork` on a dedicated queue
- high-volume HTTP calls: consider a separate gevent/eventlet worker only if you have verified every dependency path

If you do not have a strong reason otherwise, stick to prefork and solve scale with more worker processes and better queue separation.

## Concurrency tuning: separate mixed workloads

One global concurrency number is rarely the right answer for a mixed Django/Celery deployment.

Good defaults:

- one worker deployment for short latency-sensitive jobs
- one worker deployment for long-running or retry-heavy jobs
- one worker deployment for CPU-heavy jobs if they exist

Example:

```python
CELERY_TASK_ROUTES = {
    "billing.tasks.*": {"queue": "billing"},
    "integrations.tasks.*": {"queue": "io"},
    "reports.tasks.*": {"queue": "reports"},
}
```

```bash
celery -A myproject worker -Q billing --pool=prefork --concurrency=4
celery -A myproject worker -Q io --pool=prefork --concurrency=8
celery -A myproject worker -Q reports --pool=prefork --concurrency=2
```

That is usually better than one giant worker trying to do everything.

Useful process-level safety valves:

- `worker_max_tasks_per_child` / `--max-tasks-per-child`: recycle child processes to contain leaks or fragmentation
- `worker_max_memory_per_child` / `--max-memory-per-child`: kill and replace children that cross a memory ceiling

For Django apps with occasional leaks from image processing, PDF work, or large queryset materialization, child recycling is often more effective than trying to tune the leak away immediately.

## Autoscaling: useful, but not magic

Celery's prefork pool supports autoscaling:

```bash
celery -A myproject worker --autoscale=12,3 -Q io
```

This means "grow to 12 child processes, shrink to 3 when idle."

Autoscale helps when workload is bursty and tasks are short enough that extra processes clear the queue quickly. It helps less when:

- tasks are long-running
- tasks are CPU-bound and already saturate the host
- the real bottleneck is Postgres, Redis, or an upstream API rate limit

Treat autoscale as a capacity smoother, not as a fix for bad queue design.

## Beat scheduling: one scheduler instance only

Celery's periodic task docs are explicit about the core invariant: only one scheduler should own a given schedule at a time, or duplicate tasks will be sent.

That matters in Docker or Kubernetes deployments. If you run three replicas of beat with the same schedule database, you do not get high availability, you get duplicate dispatch.

Safe patterns:

- one dedicated beat container or process
- if you need failover, use leader election or an external process supervisor so only one instance is active

## `django-celery-beat`: dynamic schedules from the database

`django-celery-beat` is the standard way to manage periodic tasks through Django models rather than hard-coded settings.

Core pieces:

- `PeriodicTask`
- `IntervalSchedule`
- `CrontabSchedule`
- `ClockedSchedule`
- `SolarSchedule`

Typical setup:

```python
INSTALLED_APPS = [
    ...,
    "django_celery_beat",
]
```

```bash
celery -A myproject beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Operational details that matter:

- after changing periodic tasks in bulk, call `PeriodicTasks.changed()` so the scheduler notices
- if Django `TIME_ZONE` changes, `django-celery-beat` warns that existing schedule state is not reset automatically; you may need to clear `last_run_at`
- database-backed schedules are excellent for admin-managed jobs, but they also make beat dependent on DB availability and correctness

For Alex's stack, `django-celery-beat` is the right choice when schedules need to be changed without deploys or exposed in admin. For fixed infrastructure jobs, `beat_schedule` in settings is simpler.

## Beat without `django-celery-beat`

Celery also supports static schedules in settings:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "cleanup-expired-sessions": {
        "task": "core.tasks.cleanup_expired_sessions",
        "schedule": crontab(minute="0", hour="3"),
    },
}
```

This is a good fit when:

- the schedule changes rarely
- you want the schedule versioned with the code
- you do not need runtime admin editing

Use static schedules for stable infra jobs; use `django-celery-beat` for user- or operator-managed schedules.

## Graceful shutdown and deploy behavior

Celery workers distinguish between warm and cold shutdown behavior.

- `TERM` triggers warm shutdown: stop accepting new work and finish in-flight tasks
- `QUIT` triggers cold shutdown: terminate quickly

For normal deploys, prefer warm shutdown. In practice that means:

- send `SIGTERM`
- wait long enough for in-flight work to finish
- only fall back to hard termination if the process refuses to drain

This matters even more when `acks_late=True`, because abrupt worker death can create redelivery and duplicate execution risk.

The newer `worker_cancel_long_running_tasks_on_connection_loss` setting is worth knowing for workers that lose broker connection while running long `acks_late` tasks. It cancels those tasks instead of letting them continue detached from broker state. That can be safer than silent split-brain execution, but it only helps if the task is retryable and idempotent.

## Routing, queues, and priority

Celery routing is where "operations" becomes architecture.

Core knobs:

- `task_routes`
- `task_queues`
- per-task `queue=` and routing key options

Example:

```python
from kombu import Exchange, Queue

CELERY_TASK_QUEUES = (
    Queue("default", Exchange("default"), routing_key="default"),
    Queue("priority", Exchange("priority"), routing_key="priority"),
    Queue("reports", Exchange("reports"), routing_key="reports"),
)

CELERY_TASK_ROUTES = {
    "reports.tasks.*": {"queue": "reports", "routing_key": "reports"},
    "billing.tasks.charge_card": {"queue": "priority", "routing_key": "priority"},
}
```

Priority support is broker-dependent:

- RabbitMQ has native priority queues when configured with `x-max-priority`
- Redis priority is approximate; Celery emulates it by splitting work across multiple lists

That means "priority" on Redis is useful, but not as strong or predictable as on RabbitMQ.

## Dead-letter and retry-exhaustion patterns

Celery retries are task-level, not queue-lifecycle management. Once `max_retries` is exhausted, the task ends in failure; Celery does not create a dead-letter queue for you.

Operationally, that means:

- treat retry exhaustion as an explicit failure state
- capture it in Sentry/logging/metrics
- if you want a true dead-letter queue, use broker-native features and route failures deliberately

In RabbitMQ, that usually means a dead-letter exchange/queue policy. In Redis, the pattern is more often "record failure details and requeue intentionally" than a true DLQ primitive.

## Practical decision guide

- use **prefork** unless you have proven that an alternative pool is safe and useful
- split workers by workload type before tuning exotic concurrency settings
- run exactly **one active beat**
- use `django-celery-beat` when operators need runtime schedule control
- use static `CELERY_BEAT_SCHEDULE` when schedules are code-owned and stable
- treat autoscale as optional optimization, not core design
- make shutdown warm-by-default and tasks idempotent enough to survive redelivery

## Related files

- [celery-advanced-patterns.md](celery-advanced-patterns.md)
- [celery-canvas-in-depth.md](celery-canvas-in-depth.md)
- [django-production-stack.md](django-production-stack.md)

## Sources

- Celery workers guide: https://docs.celeryq.dev/en/stable/userguide/workers.html
- Celery concurrency guide: https://docs.celeryq.dev/en/stable/userguide/concurrency/
- Celery gevent pool: https://docs.celeryq.dev/en/stable/userguide/concurrency/gevent.html
- Celery eventlet pool: https://docs.celeryq.dev/en/stable/userguide/concurrency/eventlet.html
- Celery routing guide: https://docs.celeryq.dev/en/stable/userguide/routing.html
- Celery periodic tasks guide: https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html
- Celery configuration guide: https://docs.celeryq.dev/en/stable/userguide/configuration.html
- django-celery-beat docs: https://django-celery-beat.readthedocs.io/en/latest/

Last updated: 2026-03-18
