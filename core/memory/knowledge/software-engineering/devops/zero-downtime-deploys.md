---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - docker-production-config.md
  - github-actions-cicd.md
  - celery-multi-worker-docker.md
  - ../django/django-migrations-advanced.md
---

# Zero-Downtime Deploys with Docker Compose

Zero-downtime deployment means users don't see errors or outages during a rolling update. For a Django + Celery stack, this requires careful coordination across three dimensions: database migrations, Celery task signatures, and the container update sequence.

---

## 1. The core problem

When you deploy new code, there is a window — however brief — where the old version and the new version exist simultaneously:

- The web container may restart while active requests are in flight
- Celery workers completing tasks may be running old code while new workers start up on new code
- A migration applied before the app update means **new DB schema, old code** for a moment
- A migration after the app update means **new code, old schema** for a moment

Zero-downtime requires that every combination of (old code ↔ new DB schema) and (new code ↔ old DB schema) works correctly.

---

## 2. Migration strategy: additive-first

### The three-phase migration pattern

Never make breaking schema changes in a single deploy. Instead, split across two or three deploys:

**Phase 1 (Deploy 1): Add the new state**
```python
# Add a nullable column — safe for old code (ignores it) and new code (uses it)
class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name="order",
            field=models.CharField(max_length=50, null=True, blank=True, name="status_v2"),
        ),
    ]
```

**Phase 2 (Deploy 2, or during deploy 1): Backfill data**
```python
# Data migration to populate the new column
operations = [
    migrations.RunPython(
        code=lambda apps, schema_editor: apps.get_model("orders", "Order")
            .objects.filter(status_v2__isnull=True)
            .update(status_v2=F("status")),
        reverse_code=migrations.RunPython.noop,
    ),
]
```

**Phase 3 (Deploy 3): Make it non-nullable, drop old column**
```python
operations = [
    migrations.AlterField(
        model_name="order",
        field=models.CharField(max_length=50, name="status_v2"),  # remove null=True
    ),
    migrations.RemoveField(model_name="order", field_name="status"),
    migrations.RenameField(model_name="order", old_name="status_v2", new_name="status"),
]
```

This approach guarantees that at no point does old code break against new schema or vice versa. See `django-migrations-advanced.md` for `SeparateDatabaseAndState`, `AddIndexConcurrently`, and other zero-downtime patterns.

### Run migrations before app update

```bash
# In the CI/CD deploy step:
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate --no-input
# THEN update the web container:
docker compose -f docker-compose.prod.yml up -d --no-build web
```

The brief window (migration applied, new image pulling) has: new schema, old code. The old code must work on the new schema — this is why additive-first matters.

---

## 3. Celery task versioning

Tasks queued by old code may be processed by new workers, and tasks queued by new code may be processed by old workers. Task signatures must be forward and backward compatible during deploys.

### Use keyword arguments (not positional)

```python
# ❌ Positional args break when you add a new argument
@app.task
def send_email(user_id, template, subject):
    ...

# Old call: send_email.delay(123, "welcome", "Hello")
# New signature: send_email.delay(123, "welcome", "Hello", cc_list=[])
# Problem: old workers receive new task with unexpected arg

# ✅ Keyword args + defaults — safe to add new kwargs without breaking old workers
@app.task(bind=True)
def send_email(self, user_id, template, subject, cc_list=None, priority="normal"):
    ...
```

### Versioned task names

For truly incompatible signature changes, use a new task name:

```python
@app.task(name="myapp.send_email_v2")
def send_email_v2(...):
    ...
```

Deploy new workers that handle `send_email_v2`, queue new tasks to the v2 name, let old workers drain the v1 queue, then remove v1 after confirming drain.

---

## 4. Graceful worker shutdown during deploys

### Warm shutdown (SIGTERM)

Celery workers respond to SIGTERM with a warm shutdown: finish the currently executing task, then exit. New tasks from the queue are not accepted after SIGTERM.

```yaml
# docker-compose.prod.yml
services:
  celery-worker-default:
    stop_signal: SIGTERM
    stop_grace_period: 120s  # wait up to 2 min for current task to finish
```

If a task is lost mid-execution because stop_grace_period expires before it finishes, Celery will report it as failed (for `acks_late=True` tasks, it will be re-queued). See `celery-multi-worker-docker.md` for acks_late and warm shutdown details.

### Deploy strategy: update workers last

```bash
# 1. Apply migrations (schema change; both old and new code compatible)
docker compose run --rm web python manage.py migrate --no-input

# 2. Update web (nginx + gunicorn — fast startup, handles new requests)
docker compose up -d --no-deps web

# 3. Let current worker tasks complete (brief pause — or check worker task count)
sleep 30

# 4. Update workers (they'll warm-shutdown and restart with new code)
docker compose up -d --no-deps celery-worker-default celery-worker-io

# 5. Update beat (safe — one container)
docker compose up -d --no-deps celery-beat
```

---

## 5. Blue-green deployment with Docker Compose

Blue-green runs two full stacks simultaneously, then switches traffic:

```bash
# Stack "blue" is current production
# "Green" is the new version

# 1. Bring up the green stack on the same host (or a different host)
export COMPOSE_PROJECT_NAME=green
docker compose -f docker-compose.prod.yml up -d
# Green stack runs on different published ports (e.g., 8001 instead of 8000)

# 2. Verify green is healthy
curl http://localhost:8001/health/
curl http://localhost:8001/api/health/

# 3. Switch nginx upstream from blue to green
# (nginx upstream config references blue host:port; update to green)
docker exec nginx nginx -s reload

# 4. Allow blue to drain (stop accepting new tasks, finish in-flight)
export COMPOSE_PROJECT_NAME=blue
docker compose stop web
sleep 60  # wait for in-flight tasks to finish
docker compose down

# 5. Tag green as the new blue
export COMPOSE_PROJECT_NAME=green
docker compose rename-to blue  # non-standard; usually just rename with docker-compose
```

Blue-green is most practical with a load balancer or a second server. On a single host with Docker Compose, the version-by-version service update (section 4) is simpler.

---

## 6. Rolling update: single host, single service

Docker Compose v2 supports rolling updates natively via `--wait`:

```bash
# Update web service only, wait for healthchecks before proceeding
docker compose -f docker-compose.prod.yml up -d --no-deps --wait web
# --wait: blocks until the service is healthy (or times out)
```

The `--wait` flag reads healthcheck intervals and retries from the Compose file. It fails the deploy if the new container doesn't become healthy, preventing silent rollouts of broken code.

---

## 7. Health checks as traffic gates

```yaml
# docker-compose.prod.yml
services:
  web:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s  # grace period before healthchecks start (app startup time)
```

```python
# Django: simple health check view
from django.http import JsonResponse
from django.db import connection

def health(request):
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    status = 200 if db_ok else 503
    return JsonResponse({"db": db_ok}, status=status)
```

nginx won't start routing to a new web container until the healthcheck passes (when using `service_healthy` in `depends_on`).

---

## 8. Rollback procedure

Since containers are tagged by git SHA:

```bash
# 1. Set the version to roll back to
export APP_VERSION=abc1234  # previous working SHA

# 2. Pull that image (should be in registry or local cache)
docker compose -f docker-compose.prod.yml pull web

# 3. Update the web service only
docker compose -f docker-compose.prod.yml up -d --no-deps web

# 4. Verify
curl https://example.com/health/
```

**Database rollback limitations**: Django migrations are forward-only (reversing them can lose data). For rollback, you generally revert to a pre-migration DB backup rather than running `python manage.py migrate <app> <prev_migration>`. This is why migrations must be backward-compatible with the previous code version.

---

## 9. Smoke tests post-deploy

Add smoke tests to the CI/CD deploy job:

```yaml
- name: Smoke test
  run: |
    # Wait for services to be ready
    sleep 15

    # Test main app response
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://example.com/)
    if [ "$STATUS" != "200" ]; then echo "Frontend unhealthy: $STATUS"; exit 1; fi

    # Test API health endpoint
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://example.com/api/health/)
    if [ "$STATUS" != "200" ]; then echo "API unhealthy: $STATUS"; exit 1; fi

    # Test that admin doesn't error (302 is expected redirect to login)
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://example.com/admin/)
    if [ "$STATUS" != "302" ]; then echo "Admin unhealthy: $STATUS"; exit 1; fi

    echo "All smoke tests passed."
```

A more thorough smoke test dispatches a Celery task and polls for its result:

```python
# management/commands/smoke_test.py
from django.core.management.base import BaseCommand
from myapp.tasks import health_check_task

class Command(BaseCommand):
    def handle(self, *args, **options):
        result = health_check_task.apply_async()
        try:
            result.get(timeout=30)
            self.stdout.write("Celery: OK")
        except Exception as e:
            self.stderr.write(f"Celery: FAIL — {e}")
            raise SystemExit(1)
```

```bash
# In deploy job:
docker compose run --rm web python manage.py smoke_test
```
