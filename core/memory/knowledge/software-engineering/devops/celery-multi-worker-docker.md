---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
tags: [docker, docker-compose, celery, workers, queues, redis]
cross_references: ../django/celery-worker-beat-ops.md
related:
  - ../django/celery-worker-beat-ops.md
  - celery-flower-monitoring.md
  - docker-compose-local-dev.md
---

# Celery Multi-Worker Setup in Docker Compose

## Why multiple worker containers

A single `celery worker -Q default` container running all task types creates resource contention and makes tuning impossible:

- **I/O-bound tasks** (outbound HTTP, email, Slack notifications) need high concurrency with gevent/eventlet — they spend most of their time waiting on network
- **CPU-bound tasks** (PDF generation, image processing, data exports) need prefork workers with concurrency matching CPU count — they block the GIL
- **Quick transactional tasks** (send welcome email, invalidate cache after model save) should stay on a fast, low-latency queue and not get stuck behind a slow export job

Separating workers by queue and pool type gives you independent scaling, independent failure domains, and correct resource sizing for each task class.

---

## The three-worker pattern

```yaml
# docker-compose.yml (worker section)

  # Default: fast transactional tasks (DB writes, cache invalidation, notifications)
  celery-worker-default:
    <<: *backend-common
    command: >
      celery -A myapp worker
        --queues=default
        --pool=prefork
        --concurrency=4
        --hostname=worker-default@%h
        --loglevel=INFO
        --max-tasks-per-child=500

  # IO: outbound HTTP, emails, third-party API calls
  celery-worker-io:
    <<: *backend-common
    command: >
      celery -A myapp worker
        --queues=io
        --pool=gevent
        --concurrency=100
        --hostname=worker-io@%h
        --loglevel=INFO

  # Heavy: CPU-bound work (PDF, image processing, large exports)
  celery-worker-heavy:
    <<: *backend-common
    command: >
      celery -A myapp worker
        --queues=heavy
        --pool=prefork
        --concurrency=2
        --hostname=worker-heavy@%h
        --loglevel=INFO
        --max-tasks-per-child=50
    deploy:
      resources:
        limits:
          memory: 1g
          cpus: "2"
```

**Hostname matters**: `--hostname=worker-default@%h` (where `%h` is the container hostname) gives each worker a unique identity in Flower and Celery's monitoring tools. Without unique hostnames, workers shadow each other in the monitoring UI.

---

## Queue routing in Django settings

```python
# settings.py
from kombu import Queue, Exchange

CELERY_TASK_QUEUES = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('io',      Exchange('io'),      routing_key='io'),
    Queue('heavy',   Exchange('heavy'),   routing_key='heavy'),
)
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_DEFAULT_EXCHANGE = 'default'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'default'

CELERY_TASK_ROUTES = {
    # Route by task name
    'myapp.tasks.send_notification':  {'queue': 'io'},
    'myapp.tasks.call_external_api':  {'queue': 'io'},
    'myapp.tasks.generate_pdf':       {'queue': 'heavy'},
    'myapp.tasks.export_report':      {'queue': 'heavy'},
    # Anything not listed goes to CELERY_TASK_DEFAULT_QUEUE
}
```

Or route with the decorator directly:

```python
@shared_task(queue='io')
def send_notification(user_id: int) -> None:
    ...

@shared_task(queue='heavy')
def generate_pdf(document_id: int) -> None:
    ...
```

The `CELERY_TASK_ROUTES` setting takes precedence over the decorator `queue` argument. Use one approach consistently per project.

---

## Pool type selection guide

| Pool | Best for | Concurrency | Caveats |
|---|---|---|---|
| `prefork` (default) | CPU-bound, DB-heavy, general | `2 * CPU + 1` starting point | Each worker is a subprocess; fork safety matters |
| `gevent` | Outbound HTTP, email, high-wait I/O | 50–500 | Must `from gevent import monkey; monkey.patch_all()` before Django imports |
| `eventlet` | Same as gevent | 50–500 | Similar caveats; gevent generally preferred |
| `solo` | Local dev, debugging | 1 | Single-threaded; tasks block each other; safe for development |
| `threads` | Moderate I/O with thread-safe code | 4–20 | Django ORM is thread-safe since Django 3.1; generally safe |

### gevent patching in Docker

Gevent monkey-patching must happen before any other imports. The cleanest way is a custom `celery.py` entrypoint:

```python
# myapp/celery.py
from __future__ import absolute_import
import os

# Patch before anything else when gevent pool is active
if os.environ.get('CELERY_POOL') == 'gevent':
    from gevent import monkey
    monkey.patch_all()

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')
app = Celery('myapp')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

Set `CELERY_POOL=gevent` in the environment for the `celery-worker-io` service only. The default and heavy workers don't set this variable.

---

## Concurrency tuning

### Prefork workers

```
Starting point: --concurrency = 2 * (number of CPU cores) + 1
```

On a 2-core container: `--concurrency=5`. Watch memory — each prefork worker child is a full Django process. A 200MB Django process × 5 workers = 1GB for that container.

`--max-tasks-per-child` recycles prefork children after N tasks, preventing memory leaks from accumulating across long-running workers:

```bash
# Recycle after 500 tasks (good default for most workloads)
--max-tasks-per-child=500

# More aggressive recycling for memory-intensive tasks
--max-tasks-per-child=50
```

### Gevent workers

Start with `--concurrency=100` and tune up. The practical limit is determined by how many simultaneous open sockets/connections the OS and broker allow. 500 is a reasonable ceiling for most workloads.

Verify gevent is actually installed:

```bash
docker compose exec celery-worker-io pip show gevent
```

If gevent isn't installed, Celery silently falls back to prefork — the warning is easy to miss.

---

## Resource limits in Compose

```yaml
celery-worker-heavy:
  <<: *backend-common
  command: celery -A myapp worker --queues=heavy --pool=prefork --concurrency=2
  deploy:
    resources:
      limits:
        memory: 1g      # Hard limit — container is OOM-killed if exceeded
        cpus: "2"       # CPU throttle (not a reservation)
      reservations:
        memory: 512m    # Soft reservation for scheduling
```

**OOM kill implications**: If a prefork worker child is OOM-killed mid-task, Celery receives a `WorkerLostError`. With `acks_late=True`, the task is requeued (safe if idempotent). Without it, the task is lost. Always use `acks_late=True` on tasks that run in memory-constrained workers.

**Note**: `deploy.resources` is honoured by Docker Compose v2. In Docker Desktop, you may need to increase the VM memory allocation to see limits take effect.

---

## Shared image, different entrypoints

All backend services (web, workers, beat) should share one image to ensure code consistency:

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

FROM base AS development
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS production
RUN python manage.py collectstatic --noinput
CMD ["gunicorn", "myapp.wsgi:application", "--bind", "0.0.0.0:8000"]
```

In Compose, override `command:` per service — the image stays the same:

```yaml
x-backend-common: &backend-common
  build:
    context: ./backend
    target: development
  image: myapp-backend:local

services:
  web:
    <<: *backend-common
    command: python manage.py runserver 0.0.0.0:8000

  celery-worker-default:
    <<: *backend-common
    command: celery -A myapp worker --queues=default --pool=prefork --concurrency=4

  celery-beat:
    <<: *backend-common
    command: celery -A myapp beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

If you need a finer-grained entrypoint (e.g., to wait for Postgres before starting), use an entrypoint script:

```bash
#!/bin/bash
# backend/entrypoint.sh
set -e

echo "Waiting for postgres..."
until pg_isready -h "${POSTGRES_HOST:-postgres}" -U "${POSTGRES_USER:-myapp}"; do
  sleep 1
done

echo "Running migrations..."
python manage.py migrate --noinput

exec "$@"   # hand off to CMD
```

```dockerfile
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

The `exec "$@"` ensures the CMD (`runserver`, `celery worker`, etc.) receives Unix signals directly (PID 1 behaviour), which matters for graceful shutdown.

---

## Beat — one and only one

Beat must run as a **single instance**. Running two beat containers fires every scheduled task twice (or more). This is a real production footgun.

```yaml
celery-beat:
  <<: *backend-common
  command: celery -A myapp beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler
  restart: unless-stopped
  # No scaling: `docker compose up --scale celery-beat=2` would be dangerous
  deploy:
    replicas: 1          # explicit in Swarm; Compose ignores but documents intent
```

In multi-host production (Swarm, Kubernetes), use a DB-backed scheduler (`django-celery-beat`) with a distributed lock, or run beat as a sidecar of one designated web instance. Never rely on process-level beat in multi-host setups without locking.

`--scheduler django_celery_beat.schedulers:DatabaseScheduler` reads `PeriodicTask` records from Postgres, allowing dynamic schedule changes from the Django admin without a container restart.

---

## Worker health checks in Compose

Celery workers don't expose an HTTP endpoint, so standard curl-based healthchecks don't work. Use `celery inspect ping`:

```yaml
celery-worker-default:
  <<: *backend-common
  command: celery -A myapp worker --queues=default --hostname=worker-default@%h
  healthcheck:
    test: ["CMD-SHELL", "celery -A myapp inspect ping -d worker-default@$$HOSTNAME | grep -q pong"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 20s
```

`$$HOSTNAME` (double-dollar) is Compose's escape for a literal `$` in `test` commands (so the shell sees `$HOSTNAME`).

`celery inspect ping` requires the broker to be reachable, so it tests both worker liveness and broker connectivity simultaneously.

---

## Graceful shutdown

### Signal handling

| Signal | Celery behaviour |
|---|---|
| `SIGTERM` | Warm shutdown — finish current task, then exit |
| `SIGQUIT` | Cold shutdown — abandon current task immediately, exit |
| `SIGUSR1` | Dump traceback of all active tasks to log |
| `SIGUSR2` | Toggle verbose logging |

Docker sends `SIGTERM` first, waits `stop_grace_period`, then sends `SIGKILL`.

```yaml
celery-worker-default:
  <<: *backend-common
  stop_signal: SIGTERM           # default; explicit for clarity
  stop_grace_period: 60s         # 60s for current tasks to finish before SIGKILL
```

`stop_grace_period` should be set to a value longer than your longest expected task runtime on that queue. For the heavy queue, you may need 5–10 minutes.

### Pre-deploy drain (optional)

Before rolling a new deployment, send workers a warm shutdown signal to drain in-flight tasks:

```bash
# Drain workers gracefully before deploying new version
docker compose exec celery-worker-default celery -A myapp control shutdown
# Wait, then start new containers
docker compose up -d celery-worker-default
```

For tasks with `acks_late=True`, unfinished tasks are requeued automatically on SIGKILL — so even an imperfect shutdown is recoverable.

---

## Scaling a worker service

### Scale in Compose (local/staging)

```bash
# Run 3 IO worker containers
docker compose up --scale celery-worker-io=3
```

Each scaled instance gets a unique container name (`celery-worker-io-1`, `-2`, `-3`) and connects to the same `io` queue. Load is distributed automatically by the broker.

**`--hostname` with scaling**: `--hostname=worker-io@%h` uses the container hostname (`%h`), which is unique per container — so Flower and `celery inspect` can address each worker individually.

### Named services vs. scaled service (tradeoffs)

| Approach | Best for | Tradeoff |
|---|---|---|
| `--scale celery-worker-io=3` | Identical worker replicas | Harder to configure each instance differently |
| Separate named services (`celery-worker-io-1`, `-2`) | Different configs per worker | More Compose YAML; easier per-instance override |

For local dev, `--scale` is simpler. For production with distinct configs (different memory limits per instance), named services are clearer.

---

## Complete Compose worker section (reference)

```yaml
  celery-worker-default:
    <<: *backend-common
    command: >
      celery -A myapp worker
        --queues=default
        --pool=prefork
        --concurrency=4
        --hostname=worker-default@%h
        --loglevel=INFO
        --max-tasks-per-child=500
    stop_signal: SIGTERM
    stop_grace_period: 30s
    healthcheck:
      test: ["CMD-SHELL", "celery -A myapp inspect ping -d worker-default@$$HOSTNAME | grep -q pong"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  celery-worker-io:
    <<: *backend-common
    command: >
      celery -A myapp worker
        --queues=io
        --pool=gevent
        --concurrency=100
        --hostname=worker-io@%h
        --loglevel=INFO
    environment:
      CELERY_POOL: gevent          # triggers monkey-patching in celery.py
    stop_grace_period: 15s

  celery-worker-heavy:
    <<: *backend-common
    command: >
      celery -A myapp worker
        --queues=heavy
        --pool=prefork
        --concurrency=2
        --hostname=worker-heavy@%h
        --loglevel=INFO
        --max-tasks-per-child=50
    stop_grace_period: 300s        # long-running tasks need time to finish
    deploy:
      resources:
        limits:
          memory: 1g
          cpus: "2"

  celery-beat:
    <<: *backend-common
    command: >
      celery -A myapp beat
        --loglevel=INFO
        --scheduler django_celery_beat.schedulers:DatabaseScheduler
    restart: unless-stopped
    stop_grace_period: 10s
```
