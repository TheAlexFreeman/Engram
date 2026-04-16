# rate-my-set — Render Deploy Review

_Based on the Better Base starter snapshot in Engram memory at `memory/working/projects/rate-my-set/IN/better-base-dev/` (as of 2026-04-16). Paths in this doc are repo-relative — cross-reference against your live working copy before acting._

## TL;DR

The Better Base scaffold is a well-organized Django 6 + TanStack/React SPA baked into a single Docker image, intended to deploy to Render via the existing `render.yaml` blueprint. The blueprint is mostly production-grade but has **three hard blockers** that will prevent a fresh deploy from reaching a running state:

1. **Celery worker command mismatch** — blueprint calls `/app/start-celeryworker-regular`, image ships `/app/start-celeryworker`.
2. **Entrypoint overwrites the injected `DATABASE_URL`** — Render's correct connection string gets clobbered by a broken one reconstructed from unset `POSTGRES_*` vars.
3. **`prod.py` hard-asserts Cloudflare R2 + Mailgun + Sentry + admin URL are configured** — no sensible defaults, so missing secrets fail at settings-import time rather than at runtime.

Everything else is mostly environment variable plumbing and brand/domain renaming for rate-my-set. A realistic path to "live" is: fix the three blockers in your repo, stand up R2 + Mailgun + Sentry externally, populate the Render env groups, `render blueprint apply` against your fork, watch the logs. Details below.

---

## Stack recap

What Render will actually run, reconstructed from `compose/prod/django/Dockerfile`, `compose/prod/django/start`, and `config/settings/prod.py`:

- **Backend**: Django 6.0 + DRF on Python 3.14, served by Gunicorn sync workers (`--max-requests 3000 --max-requests-jitter 100`), bound to `0.0.0.0:${PORT:-5000}`.
- **Frontend**: React 19 + Chakra UI v3 + TanStack Router/Query, built with Vite 8 via Bun 1.3 inside the Dockerfile, emitted to `/app/dist`. Served by Django through `ViteManifestStaticFilesStorage` + WhiteNoise — **there is no separate frontend static site service; the SPA and API share one domain**. This is deliberate and fine.
- **Workers**: Celery 5.6 — one beat scheduler + one worker pool (`-c 2`, so 2 concurrent child processes per worker dyno). Broker is Redis with `noeviction`; result backend is `django-db`.
- **Cache**: Second Redis with `allkeys-lru`, used as Django's cache backend (`django-redis`) and by `django-cachalot`.
- **DB**: Postgres 18 managed by Render (`basic-256mb`, 5 GB disk), reached via `DATABASE_URL`.
- **Media storage**: Cloudflare R2 via `django-storages[s3]`. Two buckets: `*-public` (public-read, served via custom domain) and `*-private` (authenticated URLs).
- **Email**: Mailgun via `django-anymail`.
- **Observability**: Sentry (Python SDK + `@sentry/react`) wired through `structlog-sentry`. Release is pinned to the git SHA via `RENDER_GIT_COMMIT` in the Docker build and `.sentry-release` baked into the image.
- **Init/signals**: `tini` as PID 1 wrapping `entrypoint`, with `STOPSIGNAL SIGTERM` — correct for Render's shutdown lifecycle.

Non-secret notes worth internalizing:

- `config/settings/prod.py` inherits from `base.py`, so a lot of behavior (URLs, middleware, installed apps, DATABASES dict) comes from there — don't tune prod settings without reading base.
- `whitenoise==6.12.0` is a top-level dep, and `django-vite==3.1.0` handles template-time manifest lookup. When adding new static assets to the SPA, confirm they end up in `dist/` and show up in the Vite manifest; otherwise WhiteNoise will 404 them.
- `collectstatic --noinput` runs **on every web-service start** (inside `compose/prod/django/start`). Fine for correctness, but if you ever see slow cold boots that's where to look.

---

## How Render runs this — blueprint walk-through

The declarative contract lives in `render.yaml`. Here's what each piece does, with the gotchas inline.

### Databases

```yaml
databases:
  - name: better-base-prod-db-postgresql
    region: oregon
    databaseName: better_base_prod
    diskSizeGB: 5
    plan: basic-256mb
    postgresMajorVersion: "18"
```

One managed Postgres, `basic-256mb` plan ($6/mo at current list), 5 GB disk, Oregon. Render exposes this as `connectionString` which the services consume.

**Watch items:**

- `postgresMajorVersion: "18"` — verify Postgres 18 is actually supported on Render at deploy time. If not, drop to `"17"`. Changing major version post-create requires a migration.
- `plan: basic-256mb` — fine for a starter/forum workload. You can bump without rewriting blueprint.

### Env var groups

Three logical bundles, injected into every service that needs them:

1. `better-base-prod-shared` — environment markers (`ENVIRONMENT=prod`, `VITE_ENVIRONMENT=prod`) and Vite Sentry wiring. `VITE_SENTRY_RELEASE` is deliberately **not** set here — it's injected during the Docker build from `RENDER_GIT_COMMIT`. Don't set it in the dashboard; doing so will be overwritten by the build pipeline.
2. `better-base-prod-backend` — ~40 keys covering Django security, email, storage, Celery Flower creds, feature flags, Sentry. This is the big one.
3. `better-base-prod-frontend` — Hotjar config. Small.

`sync: false` means "don't sync a literal value from the blueprint; I'll set it in the Render dashboard." Every `sync: false` key is a secret-ish value you'll fill in manually after the blueprint applies. Count them carefully (see the env-var checklist below).

### Redis (two instances)

- `better-base-prod-redis-cache` — `plan: free`, `allkeys-lru`. Used for Django cache.
- `better-base-prod-redis-celery-broker` — `plan: starter`, `noeviction`. Used for Celery broker.

**Important:** Render deprecated the `free` Redis plan; current naming is "Key Value" service with "free" tier. Verify `plan: free` still applies at your apply time — if not, switch to `starter` or `free` under the Key Value service type. `noeviction` on the broker is correct (you never want Celery to silently drop tasks).

### Services

All three services share a single Docker image built from `compose/prod/django/Dockerfile`. They differ only in `dockerCommand`:

| Service name (blueprint)                                | Type   | Docker command                    | Plan     | Purpose                                             |
| ------------------------------------------------------- | ------ | --------------------------------- | -------- | --------------------------------------------------- |
| `better-base-prod-webserver-django`                     | web    | `/app/start`                      | standard | Gunicorn for Django + SPA on `app.betterbase.com`   |
| `better-base-prod-celery-beat`                          | worker | `/app/start-celerybeat`           | starter  | Celery beat scheduler                               |
| `better-base-prod-background-celery-worker-regular`     | worker | `/app/start-celeryworker-regular` | standard | Celery worker pool (2 concurrency) — **BROKEN, see blockers** |

Service-level env additions, beyond the groups:

- `DATABASE_URL` ← `fromDatabase(connectionString)`
- `CELERY_BROKER_URL` + `REDIS_CELERY_BROKER_URL` ← `fromService(better-base-prod-redis-celery-broker, connectionString)`
- `REDIS_CACHE_URL` ← `fromService(better-base-prod-redis-cache, connectionString)`
- `PORT=5000` (web only), `WEB_CONCURRENCY` (sync:false), `JUDOSCALE_*` (sync:false)

`preDeployCommand: "python manage.py migrate"` runs before each web deploy swap — Render enforces this serially, so migrations can't race the new workers.

`autoDeploy: true` + `branch: main` means every push to `main` triggers a deploy. Fine for a starter, but you may want to point at a `prod` branch once the product has real users.

---

## Deploy blockers — fix these in your repo before `blueprint apply`

### 1. Celery worker command mismatch (CRITICAL, crash-loop on boot)

**What's wrong:** `render.yaml` invokes `/app/start-celeryworker-regular`, but `compose/prod/django/Dockerfile` only copies one worker start script, named `/app/start-celeryworker` (no `-regular` suffix):

```dockerfile
COPY --chown=app:app ./compose/prod/django/celery/worker/start /app/start-celeryworker
```

The filesystem path `/app/start-celeryworker-regular` does not exist in the image. The worker service will fail its command exec and crash-loop indefinitely.

**Fix options (pick one):**

- **(a) Align the blueprint to the image (simplest):** change the worker `dockerCommand` in `render.yaml` to `/app/start-celeryworker`, and consider renaming the service from `...worker-regular` to `...worker` since there's only one tier.
- **(b) Align the image to the blueprint:** add a second copy line in the Dockerfile — e.g. `COPY --chown=app:app ./compose/prod/django/celery/worker/start /app/start-celeryworker-regular`. Keeps the name "regular" open for future addition of `start-celeryworker-priority` etc.

Given the roadmap probably intends multiple priority tiers eventually (the `-regular` naming strongly implies this), option (b) is a cleaner placeholder. But it's also fine to ship with (a) and revisit when a second worker is actually needed.

### 2. Entrypoint clobbers Render's `DATABASE_URL` (CRITICAL, all services fail DB connect)

**What's wrong:** `compose/prod/django/entrypoint` assumes the VPS/Docker-Compose environment where `POSTGRES_USER/PASSWORD/HOST/PORT/DB` are set individually and `DATABASE_URL` needs to be synthesized. It unconditionally runs:

```bash
if [ -z "${POSTGRES_USER:-}" ]; then
    export POSTGRES_USER="postgres"
fi
export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
```

On Render, none of the `POSTGRES_*` vars are set (the blueprint only injects `DATABASE_URL` from `fromDatabase.connectionString`). The entrypoint will **overwrite the correct connection string with `postgres://postgres:@:/`** and then try to wait on `psycopg.connect(host="", port="", ...)`. This blocks until timeout on every service startup.

**Fix:** guard the rewrite. Only synthesize `DATABASE_URL` when it isn't already provided. Something like:

```bash
if [ -z "${DATABASE_URL:-}" ]; then
    if [ -z "${POSTGRES_USER:-}" ]; then
        export POSTGRES_USER="postgres"
    fi
    export DATABASE_URL="postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
fi

# And swap the psycopg wait to use DATABASE_URL directly so it works in both modes:
python - <<'END'
import os, sys, time, psycopg
start = time.time()
while True:
    try:
        psycopg.connect(os.environ["DATABASE_URL"]).close()
        break
    except psycopg.OperationalError as e:
        if time.time() - start > 30:
            sys.stderr.write(f"Postgres slow to come up: {e}\n")
        time.sleep(0.5)
END
```

This keeps the VPS/Compose path working while letting Render drive through `DATABASE_URL`.

### 3. `prod.py` hard-asserts external services (BLOCKING, import-time failure)

**What's wrong:** `config/settings/prod.py` uses `env("KEY")` (no default) and `assert` statements for several external integrations. If any of these are missing or malformed, Django raises at **settings import**, before the app boots — including before `preDeployCommand`'s `migrate` step:

| Env var                                | Behavior if missing                       |
| -------------------------------------- | ----------------------------------------- |
| `DJANGO_SECRET_KEY`                    | `ImproperlyConfigured`                    |
| `DJANGO_ADMIN_URL`                     | `ImproperlyConfigured`                    |
| `DJANGO_AWS_ACCESS_KEY_ID`             | `ImproperlyConfigured`                    |
| `DJANGO_AWS_SECRET_ACCESS_KEY`         | `ImproperlyConfigured`                    |
| `DJANGO_AWS_STORAGE_BUCKET_NAME`       | `ImproperlyConfigured`                    |
| `DJANGO_AWS_PUBLIC_STORAGE_BUCKET_NAME` | `ImproperlyConfigured`                    |
| `DJANGO_AWS_PRIVATE_STORAGE_BUCKET_NAME` | `ImproperlyConfigured`                    |
| `DJANGO_AWS_S3_CUSTOM_DOMAIN`          | `AssertionError: "Current pre-condition"` |
| `DJANGO_AWS_S3_PUBLIC_CUSTOM_DOMAIN`   | `AssertionError`                          |
| `DJANGO_AWS_S3_PRIVATE_CUSTOM_DOMAIN`  | `AssertionError`                          |
| `DJANGO_AWS_S3_ENDPOINT_URL`           | `AssertionError` + must start with `https://` |
| `DJANGO_AWS_S3_PRIVATE_ENDPOINT_URL`   | `AssertionError`                          |
| `DJANGO_AWS_S3_PUBLIC_ENDPOINT_URL`    | `AssertionError`                          |
| `MAILGUN_API_KEY`                      | `ImproperlyConfigured`                    |
| `MAILGUN_WEBHOOK_SIGNING_KEY`          | `ImproperlyConfigured`                    |
| `MAILGUN_DOMAIN`                       | `ImproperlyConfigured`                    |
| `SENTRY_DSN`                           | `ImproperlyConfigured` (unless `DJANGO_IS_SENTRY_ENABLED=False`) |
| `DJANGO_CORS_ALLOWED_ORIGINS`          | `ImproperlyConfigured`                    |
| `DJANGO_CSRF_TRUSTED_ORIGINS`          | `ImproperlyConfigured`                    |
| `REDIS_CACHE_URL`                      | `ImproperlyConfigured`                    |

Also, there's a stern cross-check in `prod.py`:

```python
assert AWS_S3_ENDPOINT_URL == f"https://{aws_s3_domain}"
assert AWS_S3_PRIVATE_ENDPOINT_URL == f"https://{aws_s3_private_domain}"
assert AWS_S3_PUBLIC_ENDPOINT_URL == f"https://{aws_s3_private_domain}"  # intentional, not a typo
```

Note the last line — `AWS_S3_PUBLIC_ENDPOINT_URL` is asserted to equal the **private** domain expression. This is intentional (there's a comment saying so) but it's a surprising coupling. When you set these in the Render env group, make sure `DJANGO_AWS_S3_PUBLIC_ENDPOINT_URL` and `DJANGO_AWS_S3_PRIVATE_ENDPOINT_URL` both point to the same R2 hostname, while `DJANGO_AWS_S3_PUBLIC_CUSTOM_DOMAIN` is your public-facing CDN hostname (e.g. `public-files.ratemyset.com`).

**What this means practically:** Cloudflare R2 buckets + custom domains + Mailgun account + Sentry project must be **set up before the first Render deploy attempt**. You cannot deploy a stub and fill in integrations later. Either finish external setup first, or temporarily disable the prod integrations with env flags (see "Minimal deploy path" below).

---

## Pre-deploy setup (do these before touching Render)

### A. Rebranding pass

The scaffold's `docs/deployment_checklist.md` references a `bb_eject.py` script that renames "Better Base" / `better_base` / `betterbase.com` / "Elyon Tech" throughout the tree. Before deploying rate-my-set, run that script (or its current-named equivalent) end-to-end and:

- Replace all `betterbase.com` domains in `render.yaml` — `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DEFAULT_SITE_DOMAIN`, `DJANGO_SESSION_COOKIE_DOMAIN`, `DJANGO_DEFAULT_FROM_EMAIL`, `SERVER_EMAIL`, `MAILGUN_DOMAIN`, `BASE_BACKEND_URL`, `BASE_LANDING_SITE_URL`, `BASE_WEB_APP_URL`, etc.
- Decide whether to rename Render service names from `better-base-prod-*` to `rate-my-set-prod-*` (earlier memory references suggest you already intended to; the service names are user-visible in the Render dashboard and in `connectionString` references).
- Replace bucket name literals: `better-base-prod-public` → `rate-my-set-prod-public`, same for `-private`.
- Replace Sentry org/project literals: `VITE_SENTRY_ORG: "better-base"` → `"rate-my-set"` (or whatever your Sentry org slug is), `VITE_SENTRY_PROJECT: "better-base-prod"` → `"rate-my-set-prod"`.
- Update `SIGNUP_ONLY_ALLOW_SPECIFIC_EMAIL_DOMAINS: "betterbase.com"` — if you plan to open signup broadly, leave `SIGNUP_ENABLE_ONLY_ALLOWING_SPECIFIC_EMAIL_DOMAINS: "False"` which disables the check entirely, but still clean up the stale value.

### B. Cloudflare R2

- Create two R2 buckets: `rate-my-set-prod-public` and `rate-my-set-prod-private`.
- Provision an R2 access key pair scoped to those buckets.
- Note the R2 S3 API endpoint (looks like `https://<account-id>.r2.cloudflarestorage.com`).
- Set up a custom domain on the public bucket (e.g. `public-files.ratemyset.com`) via Cloudflare.
- CORS config: the `scripts/prod/setup_cloudflare_buckets.sh` script the checklist mentions should handle this; run it.
- Remember the `AWS_S3_PUBLIC_ENDPOINT_URL == f"https://{aws_s3_private_domain}"` quirk — `DJANGO_AWS_S3_PUBLIC_ENDPOINT_URL` should be the same R2 hostname as `DJANGO_AWS_S3_PRIVATE_ENDPOINT_URL`; only `DJANGO_AWS_S3_PUBLIC_CUSTOM_DOMAIN` differs.

### C. Mailgun (or Resend, per checklist option)

- Create a Mailgun account, add `mail.ratemyset.com` (or equivalent) as the sending domain, verify the DNS records (SPF, DKIM, MX, tracking).
- Set up a DMARC record — `p=quarantine` minimum once DKIM is stable.
- Generate an API key and a webhook signing key.
- Aim for 10/10 on https://www.mail-tester.com/ before you ship invites — this is called out in the checklist and matters for forum signups landing in inboxes.

### D. Sentry

- Create a Sentry project for `rate-my-set-prod` (or single project with environment tagging; the codebase already tags with `ENVIRONMENT`).
- Grab the DSN and an auth token (you'll need `sentry-cli` permissions for release uploading during Docker build).
- If you want to skip Sentry for the first boot, set `DJANGO_IS_SENTRY_ENABLED=False` in the env group — this short-circuits the `SENTRY_DSN = env("SENTRY_DSN")` line in `prod.py`.

### E. DNS / domains

- Register or confirm `ratemyset.com` (and decide on `app.ratemyset.com` vs bare apex — the blueprint points Render at `app.betterbase.com`, so `app.ratemyset.com` is the most direct substitution).
- Set Cloudflare as DNS (per checklist).
- Set up forwarding for `support@`, `help@`, personal aliases.
- Don't point the A/CNAME records at Render yet — you'll add those after the web service is live and validated.

### F. Generate secrets you'll paste into Render

Run on your laptop, store in Dashlane/1Password:

- `DJANGO_SECRET_KEY` — e.g. `python -c "import secrets; print(secrets.token_urlsafe(100)[:50])"`
- `DJANGO_ADMIN_URL` — a hard-to-guess URL suffix, e.g. `admin-8x2q7m/`. Non-obvious means less admin probing.
- `CELERY_FLOWER_PASSWORD` — only relevant if you add a Flower service later (current blueprint has creds env vars but no Flower service — see "Gaps" below).

---

## Environment variable checklist — what to paste where

Grouped by the env group or per-service. All `sync: false` values require a paste. Everything with a `value:` is already hardcoded in the blueprint — rename/update but don't paste.

**`better-base-prod-shared` — three secret pastes:**

- `VITE_SENTRY_AUTH_TOKEN` — Sentry auth token with release upload scope.
- `VITE_SENTRY_DSN` — frontend Sentry project DSN.
- `VITE_SENTRY_ORG` / `VITE_SENTRY_PROJECT` — hardcoded in blueprint but likely need renaming from `better-base` / `better-base-prod`.

**`better-base-prod-backend` — secret pastes (~15):**

- `ARE_ROOT_DOMAIN_COOKIES_ENABLED` — probably `"True"` if you want shared-cookie subdomains; `"False"` to scope cookies per-subdomain.
- `CELERY_FLOWER_PASSWORD` — unused if no Flower service, but don't leave blank; pick a random value.
- `DJANGO_ADMIN_URL` — the admin URL suffix you generated.
- `DJANGO_AWS_ACCESS_KEY_ID`, `DJANGO_AWS_SECRET_ACCESS_KEY` — R2 creds.
- `DJANGO_AWS_S3_CUSTOM_DOMAIN`, `DJANGO_AWS_S3_ENDPOINT_URL`, `DJANGO_AWS_S3_PRIVATE_ENDPOINT_URL`, `DJANGO_AWS_S3_PUBLIC_ENDPOINT_URL`, `DJANGO_AWS_S3_PRIVATE_CUSTOM_DOMAIN` — R2 hostnames (with and without `https://` as appropriate). Respect the asserted equalities.
- `DJANGO_SECRET_KEY` — the 50-char token you generated.
- `DJANGO_SENTRY_EVENT_LEVEL`, `DJANGO_SENTRY_LOG_LEVEL` — integer log levels, `30` (WARNING) and `20` (INFO) are sane defaults.
- `MAILGUN_API_KEY`, `MAILGUN_WEBHOOK_SIGNING_KEY` — Mailgun creds.
- `SENTRY_DSN` — backend Sentry DSN.
- `SENTRY_PROFILES_SAMPLE_RATE`, `SENTRY_SEND_DEFAULT_PII`, `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_RELEASE` — sampling + PII + release. Leave `SENTRY_RELEASE` unset; it's supplied by the Docker build through `.sentry-release`.
- `WEB_CONCURRENCY` — gunicorn worker count. For the `standard` plan (2 GB RAM / 1 CPU), set to `3` to start. Don't leave unset or you'll run with the gunicorn default of 1 worker.

**`better-base-prod-backend` — hardcoded values to rename, not paste:**

- `BASE_BACKEND_URL`, `BASE_WEB_APP_URL`, `BASE_DOMAIN_FOR_SUBDOMAINS`, `BASE_LANDING_SITE_URL` — all `betterbase.com` flavors.
- `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`, `DJANGO_CSRF_TRUSTED_ORIGINS` — all need rate-my-set domains plus the `.onrender.com` fallback.
- `DJANGO_SESSION_COOKIE_DOMAIN` — `.ratemyset.com` if sharing cookies across subdomains, empty or specific subdomain otherwise.
- `DEFAULT_SITE_DOMAIN`, `DEFAULT_SITE_NAME`, `DEFAULT_SUPPORT_EMAIL`, `DJANGO_DEFAULT_FROM_EMAIL`, `SERVER_EMAIL`, `MAILGUN_DOMAIN` — obvious renames.
- `DJANGO_AWS_STORAGE_BUCKET_NAME`, `DJANGO_AWS_PUBLIC_STORAGE_BUCKET_NAME`, `DJANGO_AWS_PRIVATE_STORAGE_BUCKET_NAME` — bucket name renames.
- `DJANGO_AWS_S3_PUBLIC_CUSTOM_DOMAIN` — currently literal `"TODO-FILL-IN.betterbase.com"`. Replace with your public CDN hostname.

**`better-base-prod-frontend` — two secret pastes:**

- `VITE_HOTJAR_IS_ENABLED` — `"true"` or `"false"`.
- `VITE_HOTJAR_SITE_ID` — Hotjar site ID if enabled.

**Per-service extras (already wired):**

- `DATABASE_URL`, `CELERY_BROKER_URL`, `REDIS_CACHE_URL`, `REDIS_CELERY_BROKER_URL` — all injected via `fromDatabase`/`fromService`. Don't paste these; Render handles them.
- `JUDOSCALE_IS_ENABLED`, `JUDOSCALE_URL` — only set these if you're signing up for Judoscale autoscaling. Otherwise leave unset (the app handles the absence).

---

## Minimal deploy path (the one-shot happy path)

Assuming blockers are fixed and external integrations are stood up. Numbered, so you can treat as a checklist:

1. **Fork / clone** the better-base-dev repo into `rate-my-set`. Run the eject/rename script to produce a rate-my-set-branded working tree on `main`.
2. **Fix the three blockers** in the repo (see sections above), commit, push `main`.
3. **Create Render services** — log into Render, select "New → Blueprint", point at your fork's `main` branch. Render parses `render.yaml` and shows you the full service list + env groups.
4. **Hit Apply.** Render provisions:
   - Postgres (takes ~2 min),
   - Redis cache + Redis broker,
   - Both env groups (blank secret slots + hardcoded values),
   - Web + beat + worker services (will start building Docker images immediately).
5. **Build will succeed; first deploy will fail.** That's fine — the env groups are still empty on their `sync: false` rows, so Django settings import crashes at startup. The failure is expected and tells you you're at step 6.
6. **Fill in every `sync: false` env var** — paste the R2/Mailgun/Sentry/admin/secret values. Use the list above. Trigger a manual redeploy on the web service.
7. **Migrations run** via `preDeployCommand: "python manage.py migrate"`. You should see green log lines. If this hangs > 1 min, your `DATABASE_URL` is probably still being clobbered — revisit blocker #2.
8. **Web service boots.** Hit `https://better-base-prod-webserver-django.onrender.com/` (or the rate-my-set-renamed equivalent) — you should see the SPA loading. If you see a Django 500/400 "DisallowedHost", `DJANGO_ALLOWED_HOSTS` is wrong.
9. **Worker boots.** Check the worker logs — you should see `celery@... ready.` If it crash-loops, revisit blocker #1.
10. **Create superuser** — open the web service's shell tab in the Render dashboard, run `python manage.py createsuperuser`. Use a throwaway admin email; you'll need email delivery working to verify non-admin signups.
11. **DNS cutover.** Add a CNAME for `app.ratemyset.com` → the Render-provided hostname; verify SSL.
12. **Run the signup/email sanity checks** from `docs/deployment_checklist.md` — signup, email verify, mail-tester 10/10, celery task processing. The checklist is VPS-heavy but the "Sanity Checks" section applies cleanly to Render.

---

## First-boot debugging — common failure modes

| Symptom                                                           | Root cause                                                       | Fix                                                                                 |
| ----------------------------------------------------------------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Service hangs on "Waiting for PostgreSQL..."                      | Entrypoint rewrote `DATABASE_URL` to garbage                     | Apply blocker #2 fix                                                                |
| `FileNotFoundError: '/app/start-celeryworker-regular'`            | Missing start script                                             | Apply blocker #1 fix                                                                |
| `AssertionError: Current pre-condition` in gunicorn startup logs  | R2 endpoint/domain env var missing or mismatched                 | Fill in all `DJANGO_AWS_S3_*` vars per the equality assertions                      |
| `ImproperlyConfigured: Set the SENTRY_DSN environment variable`   | Sentry enabled but DSN unset                                     | Set `SENTRY_DSN` or `DJANGO_IS_SENTRY_ENABLED=False`                                |
| HTTP 400 "DisallowedHost" on first page load                      | `DJANGO_ALLOWED_HOSTS` doesn't include the `*.onrender.com` host | Add the Render-assigned hostname to the list                                        |
| CSRF 403 on login/signup                                          | `DJANGO_CSRF_TRUSTED_ORIGINS` missing the frontend origin        | Add `https://<your-domain>` to the CSV                                              |
| SPA loads but API calls 404                                       | Django routing mismatch, or WhiteNoise serving `index.html` for API paths | Check `config/urls.py` — API prefix must be before the SPA catch-all       |
| Celery worker logs `kombu.exceptions.OperationalError: Error 111 connecting to localhost:6379` | `CELERY_BROKER_URL` unset on that service                        | Verify blueprint has `fromService` block for the worker (it does — if still failing, env group conflict) |
| 502 on first deploy despite build succeeding                      | Gunicorn `WEB_CONCURRENCY` unset, single worker OOM during collectstatic or slow startup | Set `WEB_CONCURRENCY=3`, consider moving `collectstatic` to build time |

---

## Post-deploy sanity checks

Mirror the `docs/deployment_checklist.md` "Sanity Checks" subsection — applies cleanly to Render:

- Does Sign Up work end-to-end? (form → verification email → confirm → login)
- Does the verify email actually arrive? (check Mailgun dashboard for delivery)
- Does `/sentry-test` on the frontend trigger a Sentry event? (validates both backend and frontend Sentry wiring)
- Is the Celery worker processing tasks? (check worker logs for "Task ... succeeded")
- Scored 10/10 on mail-tester.com? (SPF/DKIM/DMARC/reverse DNS all lining up)
- Delete the test user(s) you created during sanity checks.

Then set up Render's uptime pings + Sentry uptime alerts, and bookmark the operational dashboards.

---

## Gaps & future work (not blockers)

- **No Flower service.** `render.yaml` sets `CELERY_FLOWER_USER` / `CELERY_FLOWER_PASSWORD` but doesn't run a Flower service. If you want Celery task introspection, add a fourth worker entry with `dockerCommand: /app/start-flower` and a small plan. The Dockerfile already copies `start-flower`.
- **No scheduled / cron job.** The Engram memory previously referenced a `rate-my-set-nightly-sanitize` job — not in the current blueprint. If you want periodic cleanup (purging stale sessions, sanitizing user-submitted content, rolling DB backups), add a Render cron job or use `django-celery-beat` with a scheduled task (beat is already running).
- **No DB backup story.** The VPS checklist mentions `backup_db_and_fixtures.py` + R2 backup buckets. On Render, managed Postgres has point-in-time recovery on paid plans, but custom off-site backups are still wise. Either adapt the existing backup script to run as a Celery periodic task, or add a Render cron job.
- **Postgres 18 support verification.** `postgresMajorVersion: "18"` may not yet be GA on Render. Verify at apply time; fall back to `"17"` if needed. Major-version downgrades post-create require a migration, so get this right on the first apply.
- **Free Redis plan deprecation.** `plan: free` on the cache Redis may have been renamed or removed. Verify on Render's Key Value plan matrix.
- **`RENDER_GIT_COMMIT` during Docker build.** The Dockerfile reads this as a build-arg and writes `.sentry-release`. Render does expose this during builds (per Render docs) — verify by checking that `.sentry-release` is non-empty in a built image. If blank, Sentry release tagging won't work correctly.
- **Cost.** Rough monthly: web (standard ~$25) + worker (standard ~$25) + beat (starter ~$7) + Postgres basic-256mb ($6) + Redis broker starter ($7) + Redis cache free ($0 if the tier still exists). Call it ~$70/mo for a forum that hasn't shipped yet — consider dropping web and worker to `starter` until you have real traffic, and bump later.

---

## References

All paths are repo-relative within the `better-base-dev` working copy.

- Blueprint: `render.yaml`
- Project deploy checklist: `docs/deployment_checklist.md`
- Agent/repo conventions: `AGENTS.md`, `backend/AGENTS.md`
- Prod Dockerfile: `compose/prod/django/Dockerfile`
- Prod entrypoint: `compose/prod/django/entrypoint` ← blocker #2
- Prod start scripts: `compose/prod/django/start`, `compose/prod/django/celery/{worker,beat,flower}/start` ← blocker #1 lives in the worker path naming
- Prod Django settings: `config/settings/prod.py` ← blocker #3 lives here
- WSGI entry: `config/wsgi.py`
- Python deps + groups: `pyproject.toml` (`[dependency-groups].prod` is what the Dockerfile installs)
- Frontend deps + build scripts: `package.json`
- Taskfile (local/VPS workflows): `Taskfile.yml`
- VPS prod compose reference (not used by Render but good for comparison): `dc.prod.yml`
- Engram-side knowledge synthesis: `memory/knowledge/software-engineering/devops/better-base-toolchain.md`
