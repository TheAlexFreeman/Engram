---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - docker-compose-local-dev.md
  - nginx-django-react.md
  - github-actions-cicd.md
  - environment-secrets-management.md
  - ../django/django-gunicorn-uvicorn.md
---

# Docker Production Configuration

Production Docker config differs from development in specific, deliberate ways: no bind mounts, explicit image tags (not `latest`), non-root users, secrets from the environment (not files), entrypoint scripts that gate startup on dependencies, and read-only containers where feasible. This file covers the patterns for getting a production-ready Django + React stack into Docker correctly.

---

## 1. Multi-stage Dockerfile for Django

A single Dockerfile produces multiple targets: one for building Python dependencies, one for development (with extra tools), and one for production (lean, non-root).

```dockerfile
# Dockerfile

# ─── Stage 1: Python dependency builder ───────────────────────────────────────
FROM python:3.13-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install build dependencies for compiled packages (psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt


# ─── Stage 2: Development target ──────────────────────────────────────────────
FROM python:3.13-slim AS development

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=python-base /install /usr/local

COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


# ─── Stage 3: Production target ───────────────────────────────────────────────
FROM python:3.13-slim AS production

WORKDIR /app

# Runtime libs only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user before copying files
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Copy installed Python packages from builder
COPY --from=python-base /install /usr/local

# Copy application source — owned by appuser
COPY --chown=appuser:appgroup . .

# Collect static files as appuser
USER appuser
RUN python manage.py collectstatic --no-input

# Entrypoint handles startup sequencing (see section 3)
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

To build a specific stage:

```bash
docker build --target production -t myapp-django:latest .
docker build --target development -t myapp-django:dev .
```

---

## 2. Image tagging and versioning

**Tag by git SHA** — not by `latest` in production:

```bash
IMAGE="ghcr.io/org/myapp-django"
SHA=$(git rev-parse --short HEAD)

docker build --target production -t "$IMAGE:$SHA" -t "$IMAGE:latest" .
docker push "$IMAGE:$SHA"
docker push "$IMAGE:latest"
```

In `docker-compose.prod.yml`, reference the SHA explicitly:

```yaml
services:
  web:
    image: ghcr.io/org/myapp-django:${APP_VERSION}  # injected by CI
```

Why SHA tags:
- `latest` is mutable — pulling `latest` on two different days can give two different images
- SHA tags are immutable — rollback = `export APP_VERSION=<old-sha> && docker compose up -d web`
- CI sets `APP_VERSION` as an environment variable in the deploy step

---

## 3. Entrypoint script

The entrypoint runs before the `CMD` and handles: dependency checks (Postgres ready?), one-time startup tasks (migrate), then hands off to the service command.

```bash
#!/bin/sh
# entrypoint.sh

set -e

# Wait for Postgres to be ready
echo "Waiting for Postgres..."
until pg_isready -h "${POSTGRES_HOST:-postgres}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-app}" -d "${POSTGRES_DB:-app}"; do
    sleep 1
done
echo "Postgres is ready."

# Run migrations (safe to run on every startup — Django skips already-applied)
echo "Running migrations..."
python manage.py migrate --no-input

# Execute the CMD passed to the container (gunicorn, celery worker, etc.)
exec "$@"
```

```dockerfile
# In Dockerfile (production stage):
COPY --chown=appuser:appgroup entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
```

The `exec "$@"` is critical — it replaces the shell process with the CMD, so signals (SIGTERM from Docker) go directly to gunicorn or Celery, enabling graceful shutdown.

### Separate migrate-only job (alternative for CI/CD)

For zero-downtime deploys, run migrations as a separate step before updating the app container, rather than on every web process startup. In that case, entrypoint only waits for Postgres, no migration:

```bash
# CI/CD deploy script (before docker compose up):
docker compose run --rm web python manage.py migrate --no-input
```

---

## 4. docker-compose.prod.yml

Production Compose omits dev-only conveniences and adds production-grade settings:

```yaml
# docker-compose.prod.yml
version: "3.9"

services:
  web:
    image: ghcr.io/org/myapp-django:${APP_VERSION}
    restart: unless-stopped
    env_file: .env.production  # managed by deployment system; not committed
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
    expose:
      - "8000"  # not published to host; only nginx can reach it
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  celery-worker-default:
    image: ghcr.io/org/myapp-django:${APP_VERSION}
    command: celery -A config worker -Q default --pool=prefork --concurrency=4
    restart: unless-stopped
    env_file: .env.production
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  celery-beat:
    image: ghcr.io/org/myapp-django:${APP_VERSION}
    command: celery -A config beat --loglevel=info --scheduler=django_celery_beat.schedulers:DatabaseScheduler
    restart: unless-stopped
    env_file: .env.production
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  nginx:
    image: nginx:1.27-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - react_build:/usr/share/nginx/html:ro
      - ./nginx/certs:/etc/nginx/certs:ro
    depends_on:
      web:
        condition: service_healthy
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  postgres:
    image: postgres:17-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

volumes:
  postgres_data:
  react_build:
```

---

## 5. Non-root user

Running as root inside a container creates security risk — if an attacker achieves RCE, they have root inside the container, which may allow privilege escalation on the host. Non-root mitigates this:

```dockerfile
# Create system user (no login shell, no password)
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Set file ownership when copying
COPY --chown=appuser:appgroup . .

# Switch to non-root
USER appuser
```

**File permission implications**:
- `STATIC_ROOT` (where `collectstatic` writes) must be writable by `appuser`
- `MEDIA_ROOT` must be writable by `appuser` if Django handles uploads (though in production, direct-to-S3 is preferred)

---

## 6. Secrets — what must never be in images

```dockerfile
# ❌ Never: secrets as ARG or ENV in the final image
ARG SECRET_KEY
ENV SECRET_KEY=$SECRET_KEY
# These appear in `docker history --no-trunc` and are trivially extractable

# ✅ Correct: inject at runtime via environment variables
# docker compose up reads them from .env.production or the shell environment
```

```ignore
# .dockerignore — exclude sensitive files from build context
.env
.env.*
*.pem
*.key
secrets/
```

```bash
# Verify no secrets leaked into image layers:
docker history --no-trunc myapp:latest | grep -i secret
```

For managed secret injection patterns, see `environment-secrets-management.md`.

---

## 7. Read-only containers (optional hardening)

```yaml
# docker-compose.prod.yml
services:
  web:
    read_only: true  # container's root filesystem is read-only
    tmpfs:
      - /tmp         # writable temp dir
      - /app/tmp     # if Django writes to a local tmp path
```

This prevents any writes to the container filesystem — if malicious code tries to write a backdoor, it fails. The tradeoff is operational friction: you must explicitly identify all paths the app writes to and make them tmpfs.

---

## 8. Resource limits

```yaml
services:
  web:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"
        reservations:
          memory: 256M
          cpus: "0.5"

  celery-worker-default:
    deploy:
      resources:
        limits:
          memory: 1G  # prefork workers can consume significant memory
          cpus: "2.0"
```

**Celery prefork memory math**: each worker process gets a copy of the Python runtime + Django models. With `--concurrency=4` and ~100MB per process, that's ~400MB minimum — set the limit accordingly.

---

## 9. Log rotation

Without rotation, `json-file` logging fills disk unbounded on long-running containers:

```yaml
# Applied per service or globally in daemon.json
logging:
  driver: json-file
  options:
    max-size: "10m"   # rotate at 10MB
    max-file: "3"     # keep 3 rotated files (30MB max per service)
```

For centralized log aggregation, switch the driver to `loki` (with Grafana Loki) or `fluentd`. See `celery-flower-monitoring.md`.
