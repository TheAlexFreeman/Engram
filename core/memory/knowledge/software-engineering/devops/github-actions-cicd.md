---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - docker-production-config.md
  - zero-downtime-deploys.md
  - environment-secrets-management.md
  - dev-workflow-tooling.md
  - sentry-fullstack-observability.md
  - ../react/vite-react-build.md
---

# GitHub Actions CI/CD for Django + React

A two-stage pipeline: the test+lint stage runs fast checks on every push; the build+deploy stage runs only on merge to `main` (or on a tag). Tests must pass before deployable artifacts are produced.

---

## 1. Pipeline overview

```
Push to any branch:
  ┌─────────────────────────────┐
  │ Job: django-test            │
  │  postgres + redis services  │
  │  pytest, ruff, mypy         │
  └─────────────┬───────────────┘
                │
  ┌─────────────▼───────────────┐
  │ Job: react-test-build       │
  │  npm ci, vitest, vite build │
  │  Upload dist/ artifact      │
  └─────────────────────────────┘

On merge to main (or tag push):
  ┌─────────────────────────────┐
  │ Job: docker-build-push      │
  │  Build Django image         │
  │  Build/push to GHCR         │
  └─────────────┬───────────────┘
                │
  ┌─────────────▼───────────────┐
  │ Job: deploy                 │
  │  SSH to server              │
  │  docker compose pull + up   │
  │  Smoke test                 │
  └─────────────────────────────┘
```

---

## 2. Django test job

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches: ["**"]
  pull_request:
    branches: [main]

jobs:
  django-test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:17-alpine
        env:
          POSTGRES_DB: testdb
          POSTGRES_USER: testuser
          POSTGRES_PASSWORD: testpass
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    env:
      DATABASE_URL: postgres://testuser:testpass@localhost:5432/testdb
      REDIS_URL: redis://localhost:6379/0
      DJANGO_SETTINGS_MODULE: config.settings.test
      SECRET_KEY: ci-not-a-real-secret-key

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Cache pip dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements*.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Run ruff (lint + format check)
        run: |
          ruff check .
          ruff format --check .

      - name: Run mypy
        run: mypy .
        continue-on-error: true  # remove once fully typed

      - name: Run pytest
        run: pytest --reuse-db --cov=. --cov-report=xml -q

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
        if: success()
```

### Key patterns

- **`services:`** — GitHub Actions spins up Postgres and Redis as Docker containers; the Django job connects to them via `localhost`
- **`--reuse-db`** — `pytest-django` flag that reuses the test database between runs when schema hasn't changed; dramatically faster on iterative CI
- **Cache key on `requirements*.txt`** — invalidates the pip cache only when dependencies change, not on every commit

---

## 3. React test + build job

```yaml
  react-test-build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci

      - name: Run ESLint
        working-directory: frontend
        run: npx eslint src/

      - name: Run Vitest
        working-directory: frontend
        run: npx vitest run --coverage

      - name: Build for production
        working-directory: frontend
        env:
          VITE_API_URL: ""  # relative URL — nginx handles routing
        run: npx vite build

      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: react-dist
          path: frontend/dist/
          retention-days: 1
```

---

## 4. Docker build and push job

```yaml
  docker-build-push:
    runs-on: ubuntu-latest
    needs: [django-test, react-test-build]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

    permissions:
      contents: read
      packages: write  # required for GHCR push

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push Django image
        uses: docker/build-push-action@v6
        with:
          context: .
          target: production
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:${{ github.sha }}
            ghcr.io/${{ github.repository }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Download React build artifact
        uses: actions/download-artifact@v4
        with:
          name: react-dist
          path: ./react-dist

      - name: Build and push React/nginx image
        uses: docker/build-push-action@v6
        with:
          context: ./frontend
          # The React Dockerfile copies pre-built dist/ into nginx
          # (dist/ already built by react-test-build job)
          build-contexts:
            dist=./react-dist
          push: true
          tags: |
            ghcr.io/${{ github.repository }}-frontend:${{ github.sha }}
            ghcr.io/${{ github.repository }}-frontend:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### GitHub Actions cache for Docker layers

`cache-from: type=gha` and `cache-to: type=gha,mode=max` store Docker layer cache in GitHub's Actions cache service. This dramatically reduces build times — only changed layers are rebuilt. `mode=max` exports all layers (including intermediate stages), giving the best cache hit rate.

---

## 5. Deploy job

```yaml
  deploy:
    runs-on: ubuntu-latest
    needs: [docker-build-push]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'

    environment:
      name: production
      url: https://example.com

    steps:
      - name: Deploy to production
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.PRODUCTION_HOST }}
          username: ${{ secrets.PRODUCTION_USER }}
          key: ${{ secrets.PRODUCTION_SSH_KEY }}
          script: |
            export APP_VERSION=${{ github.sha }}

            cd /opt/myapp

            # Pull new images
            docker compose -f docker-compose.prod.yml pull

            # Run migrations before updating app
            docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate --no-input

            # Update services (zero-downtime pattern: web first, then workers)
            docker compose -f docker-compose.prod.yml up -d --no-build nginx web
            docker compose -f docker-compose.prod.yml up -d --no-build celery-worker-default celery-beat

            # Remove old images
            docker image prune -f

      - name: Smoke test
        run: |
          sleep 10  # wait for containers to start
          curl -f https://example.com/health/ || exit 1
          curl -f https://example.com/api/health/ || exit 1
```

---

## 6. Pipeline sequencing with `needs`

```yaml
jobs:
  lint-test-django:   # runs first (no needs)
    ...
  lint-test-react:    # runs first (no needs, parallel with Django)
    ...
  docker-build:
    needs: [lint-test-django, lint-test-react]  # waits for both
    ...
  deploy:
    needs: [docker-build]  # waits for build
    ...
```

Running Django and React tests in parallel cuts total CI time roughly in half.

---

## 7. Secrets management in GH Actions

```yaml
# Access secrets via ${{ secrets.VARIABLE_NAME }}
# Set in: GitHub repository → Settings → Secrets and variables → Actions

# Common secrets needed:
# PRODUCTION_HOST      — server IP/hostname for SSH deploy
# PRODUCTION_USER      — SSH username (e.g., "deploy")
# PRODUCTION_SSH_KEY   — private SSH key (the server has the matching public key)
# DATABASE_URL         — for test job if not using services (optional)
```

```bash
# Set secrets from CLI (gh CLI):
gh secret set PRODUCTION_SSH_KEY < ~/.ssh/deploy_key
gh secret set PRODUCTION_HOST --body "203.0.113.10"
```

**Never log secrets**:

```yaml
# ❌ Bad: secret appears in logs
- run: echo "Key is ${{ secrets.SECRET_KEY }}"

# ✅ Safe: GH Actions masks secrets in step logs automatically
# (but only when accessed via ${{ secrets.* }} syntax)
```

---

## 8. Branch protection and required checks

In GitHub repository Settings → Branches → Branch protection rules for `main`:

- **Require status checks to pass**: add `django-test` and `react-test-build`
- **Require branches to be up to date**: ensures tests run against the current `main`
- **Require linear history**: enforces rebase merges (cleaner git history)
- **Restrict pushes**: only allow merges via PRs (no direct push to main)

---

## 9. Caching deep dive

| Cache | Key strategy | Invalidation trigger |
|---|---|---|
| pip | `runner.os + hashFiles('requirements*.txt')` | `requirements.txt` change |
| npm | Built into `setup-node` with `cache: npm` + `cache-dependency-path` | `package-lock.json` change |
| Docker layers (GHA) | `type=gha,mode=max` — managed by buildx | Layer content change |

**Restore keys**: when the exact key misses, Action tries progressively less specific restore keys:

```yaml
restore-keys: |
  ${{ runner.os }}-pip-
```

This restores the most recent pip cache for this OS even if `requirements.txt` changed, then only the new packages are installed on top.

---

## 10. Linting as a pre-test gate

Running linters before tests fails fast on formatting/typing issues without wasting time on test setup:

```yaml
steps:
  - name: Ruff (fast — runs first)
    run: ruff check . && ruff format --check .

  - name: Mypy (slower — after ruff)
    run: mypy .

  - name: Pytest (slowest — last)
    run: pytest
```

For the React job:

```yaml
  - name: ESLint + Prettier check
    run: |
      npx eslint src/
      npx prettier --check "src/**/*.{ts,tsx}"

  - name: Vitest
    run: npx vitest run
```

Alternatively, run `pre-commit run --all-files` in CI as a single gate for all linters at once. See `dev-workflow-tooling.md`.
