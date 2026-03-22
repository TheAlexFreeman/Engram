---
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - django-production-stack.md
  - django-async.md
  - django-database-pooling.md
  - django-security.md
origin_session: unknown
---

# Django — Gunicorn, Uvicorn, Static Files, and Docker Build

This file covers the production application server layer: how to run Django under gunicorn or uvicorn, when to switch to ASGI, static file serving, and the Docker multi-stage build pattern for the Django container.

---

## 1. Gunicorn sync workers

### Worker options

Gunicorn ships several worker classes. For Django, choose based on workload:

| Worker class | `--worker-class` | Best for |
|---|---|---|
| `sync` (default) | `sync` | General-purpose; simplest; handles one request at a time per worker |
| `gthread` | `gthread` | I/O-bound with blocking calls; uses threads within each worker |
| `gevent` | `gevent` | Many concurrent I/O-heavy requests; monkey-patches stdlib |
| `eventlet` | `eventlet` | Similar to gevent; less popular in Django ecosystem |

For most Django apps backed by a database and Redis: **`sync` workers with enough worker processes** is the right default. Reach for `gthread` when you have a mix of CPU and I/O. Reserve `gevent` for Celery workers doing high-concurrency HTTP calls (see `celery-worker-beat-ops.md`), not for the Django web process.

### Key gunicorn settings

```bash
gunicorn config.wsgi:application \
    --workers 5 \                   # 2*CPU_COUNT+1 is the starting formula
    --worker-class sync \
    --threads 2 \                   # gthread only; threads per worker
    --timeout 30 \                  # kill worker if no response in 30s
    --keep-alive 5 \                # HTTP keep-alive timeout (seconds)
    --max-requests 1000 \           # restart worker after N requests (memory leak mitigation)
    --max-requests-jitter 50 \      # randomize restart to avoid all workers cycling at once
    --bind 0.0.0.0:8000 \
    --access-logfile - \            # log to stdout for Docker/systemd collection
    --error-logfile - \
    --log-level info
```

**Worker count formula**: `2 * os.cpu_count() + 1` is a well-known starting point from gunicorn docs, but it's not a law:
- CPU-bound Django (heavy ORM, image processing): stay at or below `cpu_count`
- I/O-bound Django (lots of Redis/external calls): can go higher, but `gthread` with threading is better
- Always load-test your specific workload

**`max-requests`**: workers gradually increase their memory footprint due to Python's allocator and Django's request-scoped state. Restarting workers every 1000 requests (with jitter) is a lightweight mitigation.

### Graceful reload

```bash
kill -HUP $(cat gunicorn.pid)
```

Sends `SIGHUP` — gunicorn reloads its workers without downtime. Used during deploys when running directly on a host (as opposed to Docker container replacement).

In Docker, prefer the container replacement approach: deploy a new container and let the old one drain.

---

## 2. Uvicorn under gunicorn (recommended production ASGI pattern)

### Why uvicorn under gunicorn?

Running `uvicorn` standalone doesn't give you process management, worker restarts, or signal handling. The recommended production pattern is **gunicorn as the process manager** using `UvicornWorker`:

```bash
pip install uvicorn[standard] gunicorn
```

```bash
gunicorn config.asgi:application \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000
```

This gives you:
- gunicorn's battle-tested process management and signal handling
- uvicorn's async event loop for each worker
- Django async views, websockets (via Channels), streaming responses

### WSGI vs. ASGI entrypoint

```python
# config/wsgi.py — sync Django, gunicorn sync workers
import django
from django.core.wsgi import get_wsgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()

# config/asgi.py — async-capable, gunicorn + UvicornWorker
import django
from django.core.asgi import get_asgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_asgi_application()
```

### When to switch to ASGI

Switch to ASGI (gunicorn + UvicornWorker) when you need:
- Async views (see `django-async.md`)
- Django Channels / WebSockets
- HTTP/2 streaming responses
- Server-sent events (SSE) without holding a thread

Stay on WSGI if:
- Your views are all sync and you don't need WebSockets
- Your team is less familiar with async Django subtleties
- You're using gevent workers (gevent + uvicorn = conflicts)

---

## 3. Static files in production

### The static file problem

Django's development server serves static files directly. In production, Django should **not** serve static files — it adds overhead and defeats caching. The options:

| Approach | Best for |
|---|---|
| **whitenoise** | Simplest; no extra infra; HTTP/2 + compression built in |
| **nginx** | Zero Python overhead; use when nginx is already in the stack |
| **S3/CDN** | Large scale; global distribution; combine with `django-storages` |

### whitenoise

```bash
pip install whitenoise[brotli]
```

```python
# settings.py
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # immediately after SecurityMiddleware
    ...
]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
```

`CompressedManifestStaticFilesStorage`:
- Runs `collectstatic` to gather all static files into `STATIC_ROOT`
- Adds content hashes to filenames (`app.abc123.js`) for cache-busting
- Pre-generates `.gz` and `.br` compressed versions — nginx-free compression

### collectstatic in CI/CD

```dockerfile
# In Dockerfile — run collectstatic at build time
RUN python manage.py collectstatic --noinput
```

Or in the entrypoint/startup script if you need the database available (rare — usually collectstatic doesn't need the DB):

```bash
# entrypoint.sh
python manage.py collectstatic --noinput
python manage.py migrate
exec gunicorn ...
```

---

## 4. docker-environ and environment management

```bash
pip install django-environ
```

```python
# settings.py
import environ

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost"])

# Parses postgres://user:pass@host:5432/dbname into DATABASES
DATABASES = {"default": env.db("DATABASE_URL")}

# Parses redis://host:6379/1 into CACHES
CACHES = {"default": env.cache("CACHE_URL")}

# Email: smtp+tls://user:pass@smtp.mailgun.org:587
EMAIL_CONFIG = env.email("EMAIL_URL", default="consolemail://")
vars().update(EMAIL_CONFIG)
```

**Type safety**: `env()` with `(type, default)` avoids silent string-as-bool bugs:
```python
env("DEBUG")           # returns string "False" — truthy!
env.bool("DEBUG")      # returns Python False
env("DEBUG", cast=bool) # same as above
env("DEBUG", (bool, False))  # same, with default
```

---

## 5. Docker multi-stage build for Django

### The pattern

Multi-stage builds reduce the final image size by separating build tools from the runtime:

```dockerfile
# ---- Stage 1: Python dependency builder ----
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies (only needed for compiling packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies into a virtual environment in /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ---- Stage 2: Production runtime ----
FROM python:3.13-slim AS production

WORKDIR /app

# Only install runtime system libraries (not build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Non-root user for security
RUN useradd --system --create-home --shell /bin/bash appuser
USER appuser

# Copy application code
COPY --chown=appuser:appuser . .

# Collect static files at build time
RUN python manage.py collectstatic --noinput --settings=config.settings.production

# Health check: Django's admin endpoint (or a custom /health/ view)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/')"

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--timeout", "30", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "50", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
```

### Dev vs. production split

```dockerfile
# Development stage (extends builder, not production)
FROM builder AS development

RUN pip install --no-cache-dir -r requirements-dev.txt

USER appuser
COPY --chown=appuser:appuser . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

Build targets:
```bash
docker build --target production -t myapp:prod .
docker build --target development -t myapp:dev .
```

### Minimizing layer cache invalidation

```dockerfile
# Copy only requirements first — this layer is cached as long as requirements.txt is unchanged
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code last — this layer changes every deploy
COPY . .
```

Separate `requirements.txt` from source code so that a code change doesn't trigger a full pip install.

---

## 6. Production entrypoint and startup ordering

### entrypoint.sh

```bash
#!/bin/bash
set -e

echo "Waiting for database..."
until python manage.py inspectdb > /dev/null 2>&1; do
    echo "Database not ready yet, retrying..."
    sleep 2
done

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-30}" \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile -
```

**`exec`**: replaces the shell process with gunicorn so that Docker signals (SIGTERM) go directly to gunicorn, not to bash.

**Database wait**: use `depends_on: { db: { condition: service_healthy } }` in Docker Compose instead of a bash loop when possible — Compose's health check is more reliable. The bash loop is a fallback for environments without Compose health conditions.

### Whether to run migrations on startup

Pros: simple, automatic.  
Cons: multiple replicas starting simultaneously can race on migrations; migrations can fail mid-deploy leaving the system in a mixed state.

**Production recommendation**: run migrations in a dedicated pre-deploy step (a Kubernetes Job or a separate Docker Compose step), not in the app container's entrypoint. The app container should start only after migrations are confirmed complete.

---

## 7. Custom health check endpoint

Add a health check view rather than poking the admin URL:

```python
# myapp/views.py
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache

def health_check(request):
    # DB check
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False
    
    # Cache check
    try:
        cache.set("health", "ok", timeout=5)
        cache_ok = cache.get("health") == "ok"
    except Exception:
        cache_ok = False
    
    status = 200 if (db_ok and cache_ok) else 503
    return JsonResponse({"db": db_ok, "cache": cache_ok}, status=status)
```

```python
# urls.py
path("health/", health_check),  # no auth required
```

Exempt from CSRF, rate limiting, and authentication middleware:
```python
# urls.py
path("health/", csrf_exempt(health_check)),
```
