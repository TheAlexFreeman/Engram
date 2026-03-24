---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-001
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [redis, data-structures, persistence, monitoring, caching, celery]
related:
  - ../django/django-caching-redis.md
  - ../django/celery-worker-beat-ops.md
  - docker-compose-local-dev.md
  - docker-database-ops.md
  - ../django/logfire-observability.md
---

# Redis Internals and Operations

Redis is used in this stack as both a Django cache backend and a Celery broker/result backend. This file covers Redis internals beyond the Django/Celery integration layer: data structures, persistence, memory management, high availability, monitoring, and production tuning.

## 1. Data Structures Beyond Strings

Redis supports rich data structures that are useful for patterns beyond simple key-value caching:

| Structure | Use Case | Key Commands |
|---|---|---|
| **Hash** | Object fields (user profile, session) | `HSET`, `HGET`, `HGETALL`, `HINCRBY` |
| **List** | Task queues, activity feeds | `LPUSH`, `RPOP`, `LRANGE`, `BLPOP` |
| **Set** | Tags, unique visitors, intersections | `SADD`, `SISMEMBER`, `SINTER`, `SUNION` |
| **Sorted Set** | Leaderboards, rate limiters, time-series indexes | `ZADD`, `ZRANGEBYSCORE`, `ZRANK` |
| **Stream** | Event log, message broker (Celery alternative) | `XADD`, `XREAD`, `XREADGROUP`, `XACK` |
| **HyperLogLog** | Approximate cardinality (unique counts) | `PFADD`, `PFCOUNT`, `PFMERGE` |
| **Bitmap** | Feature flags, daily active users | `SETBIT`, `GETBIT`, `BITCOUNT` |

### Streams for Event-Driven Patterns

Redis Streams provide a persistent, ordered log with consumer groups — similar to Kafka but embedded in Redis:

```bash
# Producer: append event
XADD orders:events * action created order_id 42 user_id 7

# Consumer group: read new events
XREADGROUP GROUP processors worker-1 COUNT 10 BLOCK 5000 STREAMS orders:events >

# Acknowledge processed event
XACK orders:events processors 1679234567890-0
```

Streams can serve as a lightweight event bus for patterns where Celery tasks are overkill (e.g., real-time notifications, audit trails). Consumer groups provide at-least-once delivery semantics.

## 2. Persistence Modes

| Mode | Mechanism | Durability | Performance Impact |
|---|---|---|---|
| **RDB** (snapshotting) | Point-in-time `.rdb` dump on interval | Loses data since last snapshot | Minimal (fork + background write) |
| **AOF** (append-only file) | Logs every write operation | Configurable via `appendfsync` | Higher (fsync on every write or per-second) |
| **RDB + AOF** (hybrid) | AOF with RDB preamble | Best durability | Moderate |
| **No persistence** | Pure in-memory | Complete loss on restart | Best performance |

```conf
# redis.conf — recommended production settings
appendonly yes
appendfsync everysec     # good durability/performance balance
aof-use-rdb-preamble yes # hybrid: RDB header + AOF tail for fast restarts
save 900 1               # RDB snapshot: at least 1 key changed in 900 seconds
save 300 10
save 60 10000
```

**For this stack**: Celery broker data is transient (tasks are ephemeral) — RDB snapshots are sufficient. If Redis stores session data or rate-limit counters that must survive restarts, enable AOF with `everysec`.

## 3. Memory Management and Eviction

```conf
# Memory limit and policy
maxmemory 512mb
maxmemory-policy allkeys-lru    # evict least-recently-used keys when full

# Key expiration
# SET cache:user:42 "{...}" EX 3600    # 1 hour TTL
```

| Eviction Policy | Behavior | Best For |
|---|---|---|
| `noeviction` | Return errors on write when full | Persistent data (queues, counters) |
| `allkeys-lru` | Evict least-recently-used across all keys | General cache |
| `volatile-lru` | Evict LRU only among keys with TTL | Mixed cache + persistent keys |
| `allkeys-lfu` | Evict least-frequently-used | Hot-spot workloads |
| `volatile-ttl` | Evict keys closest to expiration | TTL-heavy caching |

**Practical rule**: If Redis serves both as Celery broker and Django cache, use separate Redis databases (or separate instances) so eviction in the cache db doesn't destroy broker messages.

## 4. High Availability

### Redis Sentinel

Sentinel monitors Redis primaries and promotes replicas on failure:

```conf
# sentinel.conf
sentinel monitor myredis 10.0.0.1 6379 2  # quorum of 2
sentinel down-after-milliseconds myredis 5000
sentinel failover-timeout myredis 60000
```

Django connects via Sentinel-aware client:
```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://myredis/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.SentinelClient",
            "SENTINELS": [("sentinel-1", 26379), ("sentinel-2", 26379)],
        },
    }
}
```

### Redis Cluster

Cluster shards data across multiple nodes. Use when dataset exceeds single-node memory. Limitations: multi-key commands (`MGET`, `SUNION`) only work within the same hash slot. Celery has limited Cluster support — test thoroughly.

## 5. Monitoring and Diagnostics

```bash
# Real-time stats
redis-cli INFO server          # version, uptime, config
redis-cli INFO memory          # used_memory, fragmentation_ratio, evicted_keys
redis-cli INFO clients         # connected_clients, blocked_clients
redis-cli INFO stats           # total_commands_processed, keyspace_hits/misses
redis-cli INFO keyspace        # per-db key counts

# Slow query log
redis-cli SLOWLOG GET 10       # last 10 slow commands
redis-cli CONFIG SET slowlog-log-slower-than 10000   # log queries > 10ms

# Memory analysis
redis-cli MEMORY DOCTOR        # automated memory health check
redis-cli MEMORY USAGE mykey   # bytes used by specific key
redis-cli --bigkeys             # scan for largest keys (safe in production)

# Live command stream (⚠ high overhead — use briefly)
redis-cli MONITOR
```

**Key metrics to watch**:
- `used_memory` vs `maxmemory` — approaching limit means eviction or OOM
- `keyspace_hits / (keyspace_hits + keyspace_misses)` — cache hit ratio (target >95%)
- `connected_clients` — spike indicates connection leak
- `evicted_keys` — nonzero means capacity pressure

## 6. Lua Scripting for Atomic Operations

Lua scripts execute atomically on the Redis server — no other command runs between script steps:

```python
import redis

r = redis.Redis()

# Atomic rate limiter: increment and check in one round-trip
rate_limit_script = r.register_script("""
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
""")

count = rate_limit_script(keys=["ratelimit:user:42"], args=[60])
if count > 100:
    raise RateLimitExceeded()
```

Common patterns: rate limiting, distributed locks, conditional updates, compare-and-swap. Lua scripts avoid race conditions that would require `WATCH`/`MULTI`/`EXEC` pipelines.

## 7. Production Tuning

```conf
# Network
tcp-backlog 511              # match OS somaxconn
tcp-keepalive 300            # detect dead connections
timeout 0                    # disable idle timeout (let app manage)

# Performance
hz 10                        # event loop frequency (default 10, raise to 100 for latency-sensitive)
lazyfree-lazy-eviction yes   # async memory reclaim on eviction
lazyfree-lazy-expire yes     # async memory reclaim on TTL expiry

# Durability
no-appendfsync-on-rewrite yes  # don't block AOF during RDB save
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

**Docker-specific**: Redis in Docker should set `--stop-timeout` high enough for RDB/AOF flush on shutdown. Mount data directory as a volume (`/data`). Avoid `--memory` cgroup limits below Redis `maxmemory` — let Redis manage its own eviction.

## Sources

- Redis docs: https://redis.io/docs/
- Redis data types: https://redis.io/docs/data-types/
- Redis Streams: https://redis.io/docs/data-types/streams/
- Redis persistence: https://redis.io/docs/management/persistence/
- Redis Sentinel: https://redis.io/docs/management/sentinel/
- Redis memory optimization: https://redis.io/docs/management/optimization/memory-optimization/
