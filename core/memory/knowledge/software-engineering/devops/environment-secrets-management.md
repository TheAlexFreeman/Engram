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
  - docker-compose-local-dev.md
  - ../django/django-security.md
  - ../django/pydantic-django-integration.md
---

# Environment Variables and Secrets Management

Secrets (passwords, API keys, signing keys) must never be baked into Docker images, committed to git, or logged. Environment variables are the correct injection mechanism, but they require discipline across three environments: local development, CI, and production.

---

## 1. The three environments and their needs

| Environment | Secret source | Committed? | Typical mechanism |
|---|---|---|---|
| Local dev | `.env` file | No (gitignored) | `env_file:` in Compose |
| CI (test) | GitHub Actions Secrets | No | `${{ secrets.* }}` in workflow |
| Staging | Same infra as prod (smaller) | No | Same as production |
| Production | Secrets manager or env injection | No | Cloud provider / deployment system |

The key invariant: **secrets never touch the filesystem on production hosts, docker images, or git history.**

---

## 2. .env file conventions

```bash
# .env — local development, gitignored
# This file is never committed
SECRET_KEY=dev-not-a-real-secret-replace-in-production
DATABASE_URL=postgres://devuser:devpass@localhost:5432/myapp_dev
REDIS_URL=redis://localhost:6379/0
DJANGO_SETTINGS_MODULE=config.settings.development
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1
EMAIL_URL=console://
```

```bash
# .env.example — committed; documents all required variables with placeholder values
# DO NOT put real secrets here
SECRET_KEY=replace-with-a-real-secret-key-in-production
DATABASE_URL=postgres://user:password@postgres:5432/myapp
REDIS_URL=redis://redis:6379/0
DJANGO_SETTINGS_MODULE=config.settings.production
DEBUG=false
ALLOWED_HOSTS=example.com,www.example.com
SENTRY_DSN=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
```

```bash
# .env.test — test-specific overrides (may be committed if no real secrets)
DATABASE_URL=postgres://testuser:testpass@localhost:5432/testdb
DJANGO_SETTINGS_MODULE=config.settings.test
CELERY_TASK_ALWAYS_EAGER=true  # run tasks synchronously in tests
```

```gitignore
# .gitignore
.env
.env.local
.env.production
*.pem
*.key
secrets/
```

### Compose env_file vs. environment precedence

```yaml
# docker-compose.yml
services:
  web:
    env_file:
      - .env          # base values
      - .env.local    # optional overrides (gitignored, personal)
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.development
      # Values here OVERRIDE env_file values (higher precedence)
```

Verify resolved values with:

```bash
docker compose config  # shows the full resolved Compose config including env vars
```

---

## 3. django-environ

`django-environ` provides a concise API for reading typed values from environment variables or from `.env` files.

```python
# config/settings/base.py
import environ

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)

# Read .env file if it exists (in development; production sets vars directly)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")  # raises ImproperlyConfigured if missing

DEBUG = env("DEBUG")

DATABASES = {
    "default": env.db(),
    # env.db() parses DATABASE_URL = postgres://user:pass@host:port/db
}

CACHES = {
    "default": env.cache(),
    # env.cache() parses CACHE_URL = redis://host:6379/0
}

# Email
EMAIL_CONFIG = env.email()
# EMAIL_URL=smtp://user:pass@smtp.example.com:587/?ssl=True
# → EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_PORT, EMAIL_USE_TLS
vars().update(EMAIL_CONFIG)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
# ALLOWED_HOSTS=example.com,www.example.com → ['example.com', 'www.example.com']

# Optional with a default
SENTRY_DSN = env("SENTRY_DSN", default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
```

### Override for tests

```python
# config/settings/test.py
from .base import *  # noqa

env.overwrite = True  # allows overwriting values in test settings

DATABASES["default"]["TEST"] = {"NAME": "testdb"}
CELERY_TASK_ALWAYS_EAGER = True
```

---

## 4. Vite environment variables in CI

Vite requires `VITE_`-prefixed variables for client-side exposure. They're embedded at **build time**, not runtime.

```bash
# GitHub Actions deploy workflow:
- name: Build React
  working-directory: frontend
  env:
    VITE_API_URL: ""        # empty = relative URL; nginx proxies /api/ to Django
    VITE_APP_NAME: "MyApp"
    VITE_SENTRY_DSN: ${{ secrets.VITE_SENTRY_DSN }}
  run: npm run build
```

```typescript
// src/env.d.ts — TypeScript types for env vars
interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_APP_NAME: string;
  readonly VITE_SENTRY_DSN: string;
}
```

**Important**: `VITE_SENTRY_DSN` is a Sentry public DSN — it identifies the project but doesn't grant access. It's safe to embed in the client bundle. Do not embed actual secrets in the React build.

### The relative URL pattern

Using an empty or relative `VITE_API_URL` (`""` or `/`) means the frontend always calls its own origin — nginx routes `/api/` to Django. This is simpler than managing the API URL as a build-time constant per environment.

---

## 5. Runtime config API pattern

When config truly needs to change at runtime (feature flags, A/B variants, non-sensitive URLs), serve a JSON config file and fetch it on app startup:

```python
# Django view (no auth required — public config only)
from django.http import JsonResponse

def frontend_config(request):
    return JsonResponse({
        "apiVersion": "v2",
        "featureFlags": {
            "newDashboard": True,
            "betaExport": False,
        },
        # Nothing sensitive here — this is public
    })
```

```typescript
// React: fetch config once on startup
const config = await fetch("/api/config/").then(r => r.json());
```

This bridges the "baked at build time" limitation of Vite without resorting to complex runtime injection. Secrets never go in this response.

---

## 6. Production secret injection patterns

### Pattern A: Environment variables from CI/CD (simplest)

```yaml
# GitHub Actions deploy job:
- uses: appleboy/ssh-action@v1
  with:
    script: |
      cd /opt/myapp

      # Write secrets to .env.production on the server
      # (server's .env.production is NOT in git; managed by ops)
      cat > .env.production << EOF
      SECRET_KEY=${{ secrets.DJANGO_SECRET_KEY }}
      DATABASE_URL=${{ secrets.DATABASE_URL }}
      REDIS_URL=${{ secrets.REDIS_URL }}
      AWS_ACCESS_KEY_ID=${{ secrets.AWS_ACCESS_KEY_ID }}
      AWS_SECRET_ACCESS_KEY=${{ secrets.AWS_SECRET_ACCESS_KEY }}
      EOF

      # Deploy with these values
      APP_VERSION=${{ github.sha }} docker compose -f docker-compose.prod.yml up -d
```

### Pattern B: AWS Secrets Manager + envconsul

For regulated environments or when secrets rotate frequently:

```bash
# entrypoint.sh (extended version)
# Fetch secrets from AWS Secrets Manager and export to environment
export AWS_REGION=us-east-1

# envconsul reads the secret and injects key=value pairs into environment
exec envconsul \
  -secret "arn:aws:secretsmanager:us-east-1:123:secret:prod/myapp" \
  gunicorn config.wsgi:application
```

`envconsul` watches for secret rotation and can restart the process when values change.

### Pattern C: Docker Secrets (Swarm mode)

```yaml
# docker-compose.prod.yml (Swarm mode)
services:
  web:
    secrets:
      - django_secret_key
      - database_password

secrets:
  django_secret_key:
    external: true  # created via: docker secret create django_secret_key <(echo "value")
```

Secrets appear as files under `/run/secrets/` — read them in settings:

```python
def read_secret(name, default=""):
    try:
        with open(f"/run/secrets/{name}") as f:
            return f.read().strip()
    except FileNotFoundError:
        return default

SECRET_KEY = read_secret("django_secret_key") or env("SECRET_KEY")
```

---

## 7. Secret rotation without downtime

Django's `SECRET_KEY_FALLBACKS` enables rolling secret rotation. The current key signs new sessions/tokens; fallback keys validate old ones during the rotation window:

```python
# settings.py
SECRET_KEY = env("SECRET_KEY")  # the new key

SECRET_KEY_FALLBACKS = [
    env("SECRET_KEY_OLD", default=""),  # the previous key (accepted for a deploy cycle)
]
```

**Rotation procedure**:
1. Generate new key: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
2. Set `SECRET_KEY_OLD = current SECRET_KEY`, `SECRET_KEY = new_key`
3. Deploy — old sessions (signed with old key) still validate via `SECRET_KEY_FALLBACKS`
4. After one deploy cycle, remove `SECRET_KEY_OLD`

---

## 8. What must never be in Docker images

```dockerfile
# ❌ Never: ARG used as ENV (visible in docker history)
ARG SECRET_KEY
ENV SECRET_KEY=$SECRET_KEY

# ❌ Never: COPY .env into image
COPY .env /app/.env

# ❌ Never: hardcoded credentials in Dockerfile
RUN psql -U admin -W "hardcoded_password" -c "CREATE DATABASE mydb;"
```

```bash
# Audit an image for leaked secrets:
docker history --no-trunc myapp:latest
docker inspect myapp:latest | python -m json.tool | grep -i "secret\|password\|key"
```

### .dockerignore

```ignore
# .dockerignore — prevents sensitive files from entering the build context
.env
.env.*
!.env.example    # allow .env.example (contains no real secrets)
*.pem
*.key
*.pfx
secrets/
.git/
.gitignore
node_modules/
*.pyc
__pycache__/
```

---

## 9. Audit and hygiene tooling

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/zricethezav/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
        # Scans staged changes for secrets before every commit
```

```bash
# One-time scan of full git history:
docker run --rm -v $(pwd):/repo zricethezav/gitleaks:latest detect \
  --source="/repo" \
  --log-opts="--all"

# TruffleHog (alternative with higher sensitivity):
trufflehog git file://. --since-commit HEAD --only-verified
```

When a secret is accidentally committed, the appropriate response is:

1. Revoke/rotate the secret immediately
2. Remove from git history with `git filter-repo`
3. Force-push to all branches
4. Verify the old commit is not accessible via reflog on any clone
