---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - docker-production-config.md
  - docker-compose-local-dev.md
  - zero-downtime-deploys.md
  - ../django/psycopg3-and-connection-management.md
  - redis-internals-and-operations.md
---

# Docker Database Operations

Operational tasks: backups, restores, seeding dev data, running management commands, and database initialization.

---

## 1. Running management commands via Compose

```bash
# Standard pattern: run → rm (ephemeral container, not left behind)
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose run --rm web python manage.py shell
docker compose run --rm web python manage.py collectstatic --noinput
docker compose run --rm web python manage.py check --deploy

# With environment override:
docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.production web \
  python manage.py dbshell
```

Always use `--rm` to prevent dead stopped containers accumulating. Without it, each `docker compose run` creates a new named container that persists after exit.

```bash
# Clear accumulated stopped containers if --rm wasn't used:
docker compose rm -f
```

---

## 2. pg_dump and pg_restore

```bash
# Dump from running Postgres container to local file:
docker compose exec -T postgres pg_dump \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  -F c \                    # custom format (compressed, supports parallel restore)
  -f /tmp/backup.dump

# Copy out of container:
docker compose cp postgres:/tmp/backup.dump ./backups/$(date +%Y%m%d_%H%M%S).dump
```

```bash
# Alternative: pipe directly to host (no file in container):
docker compose exec -T postgres pg_dump \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  -F c \
  > ./backups/$(date +%Y%m%d_%H%M%S).dump
```

```bash
# Plain SQL format (readable, no parallel restore, large files):
docker compose exec -T postgres pg_dump \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  > ./backups/$(date +%Y%m%d_%H%M%S).sql
```

### Restore

```bash
# Restore custom format:
docker compose exec -T postgres pg_restore \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  --clean \               # drop objects before recreating
  --no-acl \
  --no-owner \
  -F c \
  < ./backups/20240319_120000.dump

# Restore plain SQL:
docker compose exec -T postgres psql \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  < ./backups/20240319_120000.sql
```

**For production restore**: stop the app first, restore, run migrations if needed, restart.

---

## 3. S3 upload for off-site backup

```bash
# Upload to S3 immediately after dump:
docker compose exec -T postgres pg_dump \
  -U $POSTGRES_USER \
  -d $POSTGRES_DB \
  -F c \
  | aws s3 cp - s3://myapp-backups/postgres/$(date +%Y/%m/%d/backup_%H%M%S.dump) \
    --storage-class STANDARD_IA

# Verify the upload:
aws s3 ls s3://myapp-backups/postgres/ --recursive | tail -5
```

---

## 4. Backup automation

### Option A: prodrigestivill/postgres-backup-local

```yaml
services:
  postgres-backup:
    image: prodrigestivill/postgres-backup-local:16
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_DB: myapp
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      SCHEDULE: "@daily"
      BACKUP_KEEP_DAYS: 7
      BACKUP_KEEP_WEEKS: 4
      BACKUP_KEEP_MONTHS: 6
      HEALTHCHECK_PORT: 8080
    volumes:
      - ./backups:/backups
    depends_on:
      - postgres
```

Backups stored at `./backups/daily/`, `./backups/weekly/`, `./backups/monthly/` with automatic retention.

### Option B: offen/docker-volume-backup (volume-level)

For backing up named Docker volumes (includes Postgres data directory):

```yaml
services:
  backup:
    image: offen/docker-volume-backup:v2
    environment:
      BACKUP_CRON_EXPRESSION: "0 2 * * *"
      AWS_S3_BUCKET_NAME: myapp-volume-backups
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      BACKUP_RETENTION_DAYS: "14"
    volumes:
      - postgres_data:/backup/postgres-data:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
```

---

## 5. Seeding development data

### Option A: Django fixtures with loaddata

```bash
# Create fixture from current state:
docker compose run --rm web python manage.py dumpdata \
  --indent 2 \
  --natural-foreign \
  --natural-primary \
  -o fixtures/initial_data.json

# Load fixture:
docker compose run --rm web python manage.py loaddata fixtures/initial_data.json
```

Fixtures are brittle with model changes. Prefer factory_boy for dev seeds.

### Option B: Custom seed management command with factory_boy

```python
# management/commands/seed.py
from django.core.management.base import BaseCommand
from django.db import transaction

class Command(BaseCommand):
    help = "Seed database with development data"

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true",
                            help="Flush DB before seeding")

    def handle(self, *args, **options):
        if options["flush"]:
            self.stdout.write("Flushing database...")
            from django.core.management import call_command
            call_command("flush", "--noinput")

        from myapp.factories import UserFactory, PostFactory, CommentFactory

        with transaction.atomic():
            admin = UserFactory(
                username="admin",
                email="admin@example.com",
                is_staff=True,
                is_superuser=True,
            )
            admin.set_password("admin")
            admin.save()

            users = UserFactory.create_batch(20)

            for user in users[:5]:
                posts = PostFactory.create_batch(3, author=user, published=True)
                for post in posts:
                    CommentFactory.create_batch(5, post=post)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded: 1 admin, {len(users)} users, posts, comments"
        ))
```

```bash
docker compose run --rm web python manage.py seed --flush
```

### Option C: Sanitized production dump

```bash
# On production: anonymize, strip PII, then dump
docker compose run --rm web python manage.py anonymize_data
docker compose exec -T postgres pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -F c \
  > /tmp/sanitized.dump

# On dev: restore sanitized dump
docker compose exec -T postgres pg_restore \
  -U $POSTGRES_USER -d $POSTGRES_DB --clean -F c < /tmp/sanitized.dump
```

---

## 6. Migration execution in CD

```bash
# 1. Check if any migrations are pending (fails CI if unapplied):
docker compose run --rm web python manage.py migrate --check

# 2. Show current migration state for debugging:
docker compose run --rm web python manage.py showmigrations

# 3. Create new migrations (dev only):
docker compose run --rm web python manage.py makemigrations
docker compose run --rm web python manage.py makemigrations --check  # fails if missing

# 4. Detect conflicts (two branches made migrations to same app):
docker compose run --rm web python manage.py migrate --check
```

In the GitHub Actions deploy sequence:

```yaml
- name: Run migrations
  uses: appleboy/ssh-action@v1
  with:
    script: |
      cd /opt/myapp
      docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate --noinput
      docker compose -f docker-compose.prod.yml up -d --no-build
```

Migrations run before the new app containers start. See `zero-downtime-deploys.md` for the additive-first migration pattern.

---

## 7. Database initialization on first start

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: myapp          # created automatically on first start
      POSTGRES_USER: myappuser
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init:/docker-entrypoint-initdb.d
```

```bash
# docker/postgres/init/01-extensions.sql (runs once on first start only)
CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- trigram indexes for search
CREATE EXTENSION IF NOT EXISTS unaccent;       -- accent-insensitive search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- uuid_generate_v4()
```

Scripts in `/docker-entrypoint-initdb.d/` run **once, alphabetically, only if the data directory is empty** (i.e., first initialization). They do not run on subsequent container starts.

---

## 8. Volume inspection and recovery

```bash
# List volumes:
docker volume ls
# DRIVER    VOLUME NAME
# local     myapp_postgres_data
# local     myapp_redis_data

# Inspect volume details (mountpoint on host):
docker volume inspect myapp_postgres_data

# Access volume data via temp container (e.g., inspect or copy files):
docker run --rm \
  -v myapp_postgres_data:/data:ro \
  alpine \
  ls -la /data/

# Copy a file out of a volume:
docker run --rm \
  -v myapp_postgres_data:/data:ro \
  -v $(pwd)/recovery:/out \
  alpine \
  cp /data/pg_hba.conf /out/

# Delete a volume (DESTRUCTIVE — all data lost):
docker compose down -v          # removes named volumes defined in compose
docker volume rm myapp_postgres_data   # remove specific volume
```

---

## 9. Backup verification in staging

A backup that is never tested is not a backup.

```bash
# Weekly smoke test: restore production backup to staging DB
docker compose -f docker-compose.staging.yml exec -T postgres pg_restore \
  -U $POSTGRES_USER \
  -d staging_verify \
  --clean \
  -F c \
  < latest_production.dump

# Then run a quick integrity check:
docker compose -f docker-compose.staging.yml run --rm web \
  python manage.py check --database default
```

```yaml
# GitHub Actions scheduled job:
on:
  schedule:
    - cron: "0 4 * * 0"  # Weekly on Sunday at 4 AM UTC

jobs:
  backup-verify:
    runs-on: ubuntu-latest
    steps:
      - name: Download latest backup from S3
        run: aws s3 cp s3://myapp-backups/postgres/latest.dump ./latest.dump

      - name: Restore into test Postgres
        run: |
          docker run -d --name pg-verify -e POSTGRES_PASSWORD=test postgres:16
          docker exec pg-verify pg_restore -U postgres -d postgres -F c < latest.dump

      - name: Verify row counts
        run: |
          docker exec pg-verify psql -U postgres -c "SELECT count(*) FROM auth_user;"
```
