---
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - django-orm-postgres.md
  - django-production-stack.md
  - django-gunicorn-uvicorn.md
  - celery-worker-beat-ops.md
  - psycopg3-and-connection-management.md
  - django-security.md
origin_session: unknown
---

# Django Database Pooling and Postgres Production Tuning

Django's database layer is simple by design — one connection per thread, one thread per request. At production scale, that simplicity creates problems: connection exhaustion, unnecessary overhead, and queries that could perform much better with Postgres-side tuning. This file covers the full connection lifecycle and Postgres performance configuration.

---

## 1. Django's default connection behavior

By default, Django:
- Opens a new database connection at the start of each request
- Closes it at the end of the request signal (`request_finished`)
- Does this per thread (so 4-worker gunicorn with sync workers = up to 4 simultaneous connections)

This is safe and predictable, but it's expensive: TCP connect + TLS handshake + Postgres auth happens on every request, adding 1–5ms per request even on a LAN.

---

## 2. CONN_MAX_AGE — persistent connections

```python
# settings.py
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "CONN_MAX_AGE": 60,          # keep the connection alive for 60 seconds
        "CONN_HEALTH_CHECKS": True,  # test connection before reuse (Django 4.1+)
    }
}
```

**How it works**: after a request completes, Django holds the connection open instead of closing it. The next request on the same thread reuses the connection if it was opened within the last `CONN_MAX_AGE` seconds and passes the health check.

**`CONN_HEALTH_CHECKS`** (Django 4.1+): before reusing a persistent connection, Django runs a lightweight ping (`SELECT 1`) to detect dead connections. Without this, stale connections (killed by Postgres, network drops, idle timeout) cause the first query of the reuse to fail with a `OperationalError`, requiring a restart.

### Gotcha: CONN_MAX_AGE vs. pgBouncer

If you're using pgBouncer in **transaction pooling** mode (the default for high-concurrency deployments), **do not use `CONN_MAX_AGE > 0`**.

pgBouncer transaction pooling assigns a Postgres connection for the duration of a transaction, then releases it back to the pool. If Django holds a persistent connection, pgBouncer can't reclaim it between requests — defeating the purpose of pooling.

For pgBouncer + transaction pooling: set `CONN_MAX_AGE = 0` and let pgBouncer handle pooling.

---

## 3. pgBouncer

pgBouncer sits between Django and Postgres, pooling connections:

```
Django workers → pgBouncer → Postgres (limited connections)
(100 * workers)    (pool)       (max_connections=100)
```

### Pooling modes

| Mode | Django connection per | Pool connection released | Compatibility |
|---|---|---|---|
| **Session** | connection | Session end | Full — SET, prepared statements, LISTEN all work |
| **Transaction** | transaction | Transaction end | Most — breaks SET persisted across requests, SET LOCAL for session vars |
| **Statement** | statement | Statement end | Minimal Django use: breaks multi-statement transactions |

**Transaction pooling** is the right choice for Django: it allows many more Django workers than Postgres `max_connections` supports, and Django's ORM naturally uses transactions around each request.

### pgBouncer configuration

```ini
# pgbouncer.ini
[databases]
mydb = host=postgres port=5432 dbname=mydb

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
pool_mode = transaction
max_client_conn = 1000        # max connections from Django workers to pgBouncer
default_pool_size = 20        # connections from pgBouncer to Postgres per database+user pair
reserve_pool_size = 5         # extra connections for burst
server_idle_timeout = 600     # close idle Postgres connections after 10 minutes
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
logfile = /var/log/pgbouncer/pgbouncer.log
pidfile = /var/run/pgbouncer/pgbouncer.pid
```

### Django settings for pgBouncer

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "pgbouncer",             # point Django at pgBouncer, not Postgres directly
        "PORT": "6432",
        "NAME": env("DB_NAME"),
        "CONN_MAX_AGE": 0,               # must be 0 with transaction pooling
        "DISABLE_SERVER_SIDE_CURSORS": True,  # server-side cursors break transaction pooling
        "OPTIONS": {
            "options": "-c default_transaction_isolation=read committed"
        }
    }
}
```

`DISABLE_SERVER_SIDE_CURSORS`: Django uses server-side cursors for large QuerySet iterations (`.iterator()`). Server-side cursors persist across transactions, which breaks pgBouncer's transaction pooling. This setting forces Django to use client-side cursors instead. The downside: `.iterator()` loads more into memory — use in moderation on large tables.

### What breaks with transaction pooling

- `SET` statements (session-level config): use `SET LOCAL` inside a transaction block, or configure at the Postgres role level
- `LISTEN`/`NOTIFY`: requires a dedicated non-pooled connection
- Advisory locks across requests: they don't persist between pooled connections
- `PREPARE`/`EXECUTE` prepared statements: disabled by default in pgBouncer transaction mode

---

## 4. django-db-geventpool (gevent workers only)

If running Django under gunicorn with gevent workers, use a gevent-compatible connection pool:

```bash
pip install django-db-geventpool
```

```python
DATABASES = {
    "default": {
        "ENGINE": "django_db_geventpool.backends.postgresql_psycopg2",
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "MAX_CONNS": 20,      # max connections in the pool per process
            "REUSE_CONNS": 10,    # keep at least 10 connections idle
        },
    }
}
```

This uses gevent-aware locking around connection acquisition so greenlets don't block each other waiting for a connection. Do not use `django-db-geventpool` with sync or threaded workers — use pgBouncer instead.

---

## 5. Monitoring connections

### pg_stat_activity

```sql
-- Current connections and their state
SELECT pid, usename, application_name, state, wait_event_type, wait_event, query
FROM pg_stat_activity
WHERE datname = 'mydb'
ORDER BY state, query_start;

-- Count by state
SELECT state, count(*) FROM pg_stat_activity WHERE datname = 'mydb' GROUP BY state;
```

States to watch:
- `active`: running a query
- `idle`: holding a connection but not doing anything — these are persistent connections or leaked connections
- `idle in transaction`: inside a BEGIN but not running a query — dangerous if held too long (holds locks)
- `idle in transaction (aborted)`: transaction was aborted but not rolled back — Django should clean these up

### Connection limit alerts

```sql
-- Approaching max_connections
SELECT count(*) as current, max_connections, count(*) * 100 / max_connections as pct
FROM pg_stat_activity, (SELECT setting::int AS max_connections FROM pg_settings WHERE name = 'max_connections') s
GROUP BY max_connections;
```

Alert when above 80% of `max_connections`. Typical Postgres default is 100; set `max_connections = 200` or higher for production but remember each connection uses ~5-10MB of Postgres memory.

### pg_stat_statements

```sql
-- Enable (requires pg_stat_statements in postgresql.conf shared_preload_libraries)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Slowest queries by total time
SELECT query, calls, total_exec_time / 1000 AS total_seconds,
       mean_exec_time AS mean_ms, rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Reset stats (after a major code change)
SELECT pg_stat_statements_reset();
```

---

## 6. Postgres parallel query

### What it is

Postgres can split a single query across multiple CPU cores using parallel workers. Controlled by:

```sql
-- Global setting
max_parallel_workers_per_gather = 2  -- default; each query can use 2 parallel workers

-- Session override
SET max_parallel_workers_per_gather = 0;  -- disable for this session
```

### When it helps

- Large analytical queries (aggregations, sorts, full-table scans on wide tables)
- Queries without an index that must scan millions of rows

### When it hurts OLTP workloads

For typical Django OLTP workloads (many small, fast queries), parallel query is counterproductive:
- Spawning parallel workers has overhead (5–20ms) that exceeds the benefit for small result sets
- Parallel workers consume CPU that other concurrent queries could use
- Connection-heavy apps (100+ Django workers) deplete `max_parallel_workers` quickly

**Recommendation for Django production**: if your queries are well-indexed OLTP patterns, reduce `max_parallel_workers_per_gather` to 0 or 1 at the Postgres role level:

```sql
ALTER ROLE myapp_user SET max_parallel_workers_per_gather = 0;
```

Leave the global default unchanged so analytics queries (psql, reporting) still get parallelism.

---

## 7. Table partitioning

### When to use

- Tables that grow without bound (logs, events, time-series metrics, audit trails)
- Queries almost always filter by the partition key (usually a timestamp)
- You want to drop old data by dropping a partition (zero-locking, fast)
- Row counts exceed ~50–100M and query times are degrading despite good indexes

### Django support via migrations

Django doesn't generate partitioned tables via model meta — use `RunSQL`:

```python
# migrations/0001_create_events_partitioned.py
class Migration(migrations.Migration):
    operations = [
        migrations.RunSQL(
            """
            CREATE TABLE myapp_event (
                id          BIGSERIAL,
                user_id     INTEGER NOT NULL,
                event_type  VARCHAR(50) NOT NULL,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                payload     JSONB
            ) PARTITION BY RANGE (created_at);

            -- Create monthly partitions
            CREATE TABLE myapp_event_2026_01 PARTITION OF myapp_event
                FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
            CREATE TABLE myapp_event_2026_02 PARTITION OF myapp_event
                FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
            -- etc.

            CREATE INDEX ON myapp_event (user_id, created_at);  -- local index per partition
            """,
            reverse_sql="DROP TABLE myapp_event CASCADE",
        ),
        # Tell Django the model exists but don't let it manage the table
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    "Event",
                    fields=[...],
                    options={"managed": False},  # Django won't try to create/alter/drop
                ),
            ],
            database_operations=[],
        ),
    ]
```

**`managed = False`**: tells Django not to run `CREATE TABLE` for this model. It can still query, insert, update, and delete through the ORM — it just doesn't control the schema.

### pg_partman for automated partition management

```sql
CREATE EXTENSION pg_partman;

SELECT partman.create_parent(
    p_parent_table := 'public.myapp_event',
    p_control := 'created_at',
    p_type := 'range',
    p_interval := 'monthly',
    p_premake := 3              -- create 3 months of future partitions in advance
);

-- Schedule in cron or a management command
SELECT partman.run_maintenance();  -- creates new partitions, detaches old ones
```

`pg_partman` handles partition creation, retention policies (detach old partitions), and statistics maintenance. Much more robust than manually creating partitions in migrations.

---

## 8. Connection pooling decision guide

```
Single small app, low traffic
  → CONN_MAX_AGE=60, CONN_HEALTH_CHECKS=True — no additional infrastructure needed

Medium traffic, many gunicorn workers, sync
  → pgBouncer (transaction pooling), CONN_MAX_AGE=0, DISABLE_SERVER_SIDE_CURSORS=True

High traffic, gevent workers
  → django-db-geventpool, CONN_MAX_AGE=0

Very high traffic with both sync and gevent workers
  → pgBouncer for all + appropriate CONN_MAX_AGE=0

Analytical queries alongside OLTP
  → Separate read replica for analytics; pgBouncer for OLTP; parallel query enabled on replica
    (ALTER ROLE analytics_user SET max_parallel_workers_per_gather = 4)
```
