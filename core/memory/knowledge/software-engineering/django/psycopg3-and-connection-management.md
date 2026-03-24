---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-001
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [psycopg3, postgres, django, async, connection-pooling, database]
related:
  - django-orm-postgres.md
  - django-database-pooling.md
  - django-async.md
  - ../devops/docker-database-ops.md
  - logfire-observability.md
---

# Psycopg 3 and Connection Management

Psycopg 3 is the modern PostgreSQL adapter for Python, rewritten from the ground up as a successor to psycopg2. Django 5.x+ ships `django.db.backends.postgresql` backed by psycopg (the psycopg3 package) as the recommended default. Psycopg 3 brings native async support, pipeline mode, strongly typed parameters, and a redesigned connection pool — all directly relevant to Django + Postgres production stacks.

## 1. Installation and Django Backend Configuration

```python
# Install psycopg 3 (binary wheels for fast install, or source for custom builds)
# pip install "psycopg[binary]"    # binary — recommended for dev
# pip install "psycopg[c]"         # C extension — recommended for production

# settings.py — Django 5.x+ default backend uses psycopg 3
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "mydb",
        "HOST": "db",
        "PORT": "5432",
        "USER": "app",
        "PASSWORD": "secret",
        # psycopg 3 connection options via OPTIONS
        "OPTIONS": {
            "pool": True,                  # enable built-in connection pool (Django 5.1+)
            "pool_options": {
                "min_size": 2,
                "max_size": 10,
                "max_idle": 300,
            },
        },
    }
}
```

Django's `django.db.backends.postgresql` auto-detects whether psycopg 2 or 3 is installed. When both are present, psycopg 3 takes priority. The `"pool": True` option enables psycopg 3's built-in `ConnectionPool`, eliminating the need for pgBouncer in many deployment models (see [django-database-pooling.md](django-database-pooling.md) for the pgBouncer comparison).

## 2. Async Connections

Psycopg 3's `AsyncConnection` makes native async database access possible — a prerequisite for Django's async ORM queries:

```python
import psycopg

# Async context manager — connection is returned to pool on exit
async with await psycopg.AsyncConnection.connect(conninfo) as conn:
    async with conn.cursor() as cur:
        await cur.execute("SELECT id, name FROM products WHERE active = %s", [True])
        rows = await cur.fetchall()
```

In Django async views, the ORM handles this internally when using `await` with querysets. The async adapter is the same psycopg 3 driver, not a separate package. This aligns with Django's async story (see [django-async.md](django-async.md)).

## 3. Connection Pooling: psycopg 3 Pool vs pgBouncer

| Feature | psycopg 3 `ConnectionPool` | pgBouncer |
|---|---|---|
| Deployment | In-process (per-worker) | External proxy |
| Protocol overhead | None (direct) | Extra TCP hop |
| Prepared statements | Full support | Transaction-mode breaks them |
| `LISTEN/NOTIFY` | Works | Requires session mode |
| Pool sizing | Per Django worker | Global across all workers |
| Monitoring | Python metrics/callbacks | `SHOW STATS` console |

**When to use pgBouncer**: large Gunicorn/Uvicorn deployments where per-worker pools exceed Postgres `max_connections`. pgBouncer gives global connection control.

**When to use psycopg 3 pool**: simpler deployments, async Django, or when prepared statements and `LISTEN/NOTIFY` are needed.

## 4. Pipeline Mode (Batch Operations)

Pipeline mode sends multiple queries over a single connection without waiting for individual results, reducing round-trip latency:

```python
async with await psycopg.AsyncConnection.connect(conninfo) as conn:
    async with conn.pipeline():
        results = []
        for user_id in user_ids:
            cur = await conn.execute(
                "UPDATE users SET last_seen = now() WHERE id = %s RETURNING id",
                [user_id],
            )
            results.append(cur)
        # All queries sent in one batch; results arrive together
```

Pipeline mode is particularly effective for batch updates, cache warming, or any pattern that would otherwise issue sequential round-trips to Postgres.

## 5. COPY Protocol for Bulk Data

The `COPY` protocol is the fastest way to load large datasets into Postgres. Psycopg 3 exposes a clean Python interface:

```python
import psycopg
from psycopg import sql

async with await psycopg.AsyncConnection.connect(conninfo) as conn:
    async with conn.cursor() as cur:
        # COPY FROM: bulk insert rows
        async with cur.copy(
            "COPY products (name, price, category) FROM STDIN"
        ) as copy:
            for name, price, category in product_data:
                await copy.write_row((name, price, category))

        # COPY TO: bulk export
        async with cur.copy("COPY products TO STDOUT") as copy:
            async for row in copy.rows():
                process(row)
```

For Django management commands that seed data or ETL pipelines, COPY is 10–50× faster than row-by-row `INSERT` or `bulk_create()` with large datasets.

## 6. Server-Side Cursors

For processing millions of rows without loading them all into memory:

```python
async with await psycopg.AsyncConnection.connect(conninfo) as conn:
    async with conn.cursor(name="large_export") as cur:
        await cur.execute("SELECT * FROM audit_log WHERE created > %s", [cutoff])
        async for row in cur:  # fetches in chunks from the server
            process_row(row)
```

Django's ORM exposes this via `QuerySet.iterator(chunk_size=2000)`. Under psycopg 3, `iterator()` uses server-side cursors automatically.

## 7. Type Adaptation System

Psycopg 3 replaces psycopg2's global `register_adapter`/`register_type` with a scoped, composable system:

```python
from psycopg.adapt import Dumper, Loader

class PointDumper(Dumper):
    oid = psycopg.postgres.types["point"].oid

    def dump(self, obj):
        return f"({obj.x},{obj.y})".encode()

# Register per-connection (not global — avoids cross-contamination)
conn.adapters.register_dumper(Point, PointDumper)
```

Key difference from psycopg2: adapters are scoped to connection or cursor, not registered globally. This is safer in multi-tenant or testing scenarios.

## 8. Migration from psycopg2 to psycopg 3

| psycopg2 | psycopg 3 | Notes |
|---|---|---|
| `import psycopg2` | `import psycopg` | Package renamed |
| `psycopg2.extras.RealDictCursor` | `psycopg.rows.dict_row` | Row factories replace cursor subclasses |
| `register_adapter(MyType, adapt_fn)` | `conn.adapters.register_dumper(MyType, Dumper)` | Scoped, not global |
| `cursor.execute(sql, {named})` | `cursor.execute(sql, {named})` | Named params still supported |
| `psycopg2.extensions.ISOLATION_*` | `psycopg.IsolationLevel.*` | Enum instead of constant |
| Server-side cursor via name kwarg | Same: `cursor(name="xxx")` | Identical API |

**Django migration path**: Change `psycopg2-binary` → `psycopg[binary]` in requirements. If no raw SQL uses psycopg2-specific APIs (extras, extensions), the switch is transparent — Django's backend handles the rest.

## Sources

- psycopg 3 docs: https://www.psycopg.org/psycopg3/docs/
- psycopg 3 async: https://www.psycopg.org/psycopg3/docs/advanced/async.html
- psycopg 3 connection pool: https://www.psycopg.org/psycopg3/docs/api/pool.html
- psycopg 3 COPY: https://www.psycopg.org/psycopg3/docs/basic/copy.html
- Django PostgreSQL backend notes: https://docs.djangoproject.com/en/5.2/ref/databases/#postgresql-notes
