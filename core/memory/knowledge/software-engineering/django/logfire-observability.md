---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-001
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [logfire, observability, opentelemetry, django, celery, psycopg, tracing]
related:
  - django-observability-structlog-sentry.md
  - pydantic-django-integration.md
  - psycopg3-and-connection-management.md
  - celery-advanced-patterns.md
  - django-caching-redis.md
  - ../devops/sentry-fullstack-observability.md
---

# Logfire Observability for Django

Pydantic Logfire is an OpenTelemetry-native observability platform built by the Pydantic team. It provides auto-instrumentation for Django, Celery, psycopg, Redis, and HTTPX with minimal configuration. Logfire's role in this stack is complementary to Sentry: Logfire focuses on traces, spans, and structured telemetry data for understanding system behavior, while Sentry focuses on error capture, crash reporting, and release health.

## 1. Installation and Basic Setup

```bash
pip install "logfire[django,celery,psycopg,redis,httpx]"
logfire auth   # authenticate with Logfire cloud (one-time)
```

```python
# settings.py or early startup
import logfire

logfire.configure(
    service_name="my-django-app",
    environment="production",       # or from env var
    send_to_logfire=True,           # True for cloud, False for local OTEL collector
)
```

Logfire uses OpenTelemetry under the hood — all instrumentation produces standard OTEL spans that can also be exported to Jaeger, Grafana Tempo, or any OTEL-compatible backend.

## 2. Django Auto-Instrumentation

```python
# settings.py — after logfire.configure()
logfire.instrument_django()
```

This automatically traces:
- Every HTTP request (method, path, status code, duration)
- Template rendering time
- Middleware execution
- Database query time (when combined with psycopg instrumentation)

Spans appear in the Logfire dashboard with full request metadata. No middleware or decorator changes needed.

## 3. Celery Task Tracing

```python
# celery.py — after app = Celery(...)
import logfire
logfire.instrument_celery()
```

Traces include:
- Task name, args, kwargs
- Queue name and worker identity
- Execution duration and result status
- Retry attempts and failure chains
- Parent trace propagation (if the task was triggered from a Django request, the trace links them)

This is particularly valuable for debugging slow task chains (see [celery-advanced-patterns.md](celery-advanced-patterns.md) for canvas workflows) — Logfire shows the full execution waterfall across chords and groups.

## 4. Psycopg Query Tracing

```python
logfire.instrument_psycopg()
```

Traces every database query with:
- SQL text (parameterized — no sensitive data in spans)
- Execution time
- Connection pool utilization
- Row count

Combined with `instrument_django()`, you get full request → query waterfalls: how many queries a view issues, which are slow, and where N+1 patterns hide. This is the observability complement to [psycopg3-and-connection-management.md](psycopg3-and-connection-management.md).

## 5. Redis and HTTPX Tracing

```python
logfire.instrument_redis()   # traces cache.get/set, Celery broker ops
logfire.instrument_httpx()   # traces outbound HTTP calls
```

Redis instrumentation captures:
- Command type (`GET`, `SET`, `HGETALL`, `LPUSH`, etc.)
- Key patterns (configurable redaction for sensitive keys)
- Latency per operation

HTTPX instrumentation captures outbound API calls with method, URL, status, and latency. Useful for tracking third-party service dependencies.

## 6. Pydantic Model Validation Tracing

```python
logfire.instrument_pydantic()
```

Traces every `BaseModel.model_validate()` call with:
- Model class name
- Validation success/failure
- Field-level error details on failure
- Serialization time

This connects the Pydantic integration (see [pydantic-django-integration.md](pydantic-django-integration.md)) to the observability layer — validation failures in Celery task payloads or API inputs become visible in traces.

## 7. Structured Logging Integration: Logfire + structlog

Logfire and structlog serve different purposes and can coexist:

| Layer | structlog | Logfire |
|---|---|---|
| **What it captures** | Application events (log lines) | Distributed traces and spans |
| **Output format** | JSON log lines to stdout/files | OTEL spans to Logfire cloud |
| **Correlation** | `request_id`, `task_id` via contextvars | Trace ID, span ID (OTEL standard) |
| **Best for** | Grep-able event streams, log aggregation | Request waterfalls, performance profiling |

To use both:

```python
import logfire
import structlog

# Logfire handles tracing
logfire.configure(service_name="my-app")
logfire.instrument_django()

# structlog handles logging — configure as normal
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        # Inject trace context into log lines for correlation
        logfire.StructlogProcessor(),   # adds trace_id, span_id to log events
        structlog.dev.ConsoleRenderer(),  # or JSONRenderer for production
    ],
)
```

`logfire.StructlogProcessor()` injects the current OTEL trace/span ID into every structlog event, enabling log↔trace correlation. When investigating a slow request in Logfire, you can find the corresponding log lines; when reading logs, you can jump to the full trace.

See [django-observability-structlog-sentry.md](django-observability-structlog-sentry.md) for the structlog setup details.

## 8. Logfire vs Sentry: Complementary Roles

| Dimension | Logfire | Sentry |
|---|---|---|
| **Primary focus** | Traces, spans, metrics | Errors, crashes, release health |
| **Query model** | SQL-like queries over spans | Issue grouping + triage |
| **Performance data** | Full trace waterfalls, custom spans | Sampled transactions, Web Vitals |
| **Alerting** | Metric-based (latency, error rate) | Error-based (new issues, regressions) |
| **Cost model** | Per-span ingestion | Per-event + per-transaction |
| **Best for** | "Why is this request slow?" | "What broke and who's affected?" |

**Recommended setup**: Use both. Sentry for error alerting and crash triage (see [sentry-fullstack-observability.md](../devops/sentry-fullstack-observability.md)). Logfire for performance profiling, query analysis, and understanding request flow. Share trace IDs between them for full correlation.

## 9. Dashboard and Query Patterns

Logfire provides a SQL query interface over collected spans:

```sql
-- Slowest Django endpoints (p95 latency)
SELECT
    attributes->>'http.route' AS route,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms,
    count(*) AS request_count
FROM spans
WHERE span_name LIKE 'GET %' OR span_name LIKE 'POST %'
GROUP BY route
ORDER BY p95_ms DESC
LIMIT 20;

-- Database queries per request (N+1 detection)
SELECT
    parent_span->>'http.route' AS route,
    count(*) AS query_count,
    sum(duration_ms) AS total_db_ms
FROM spans
WHERE span_name LIKE 'SELECT%' OR span_name LIKE 'INSERT%'
GROUP BY route
ORDER BY query_count DESC;
```

These queries run directly in the Logfire web UI. Custom dashboards can combine endpoint latency, database query counts, cache hit rates, and Celery task durations.

## Sources

- Logfire docs: https://logfire.pydantic.dev/docs/
- Logfire Django integration: https://logfire.pydantic.dev/docs/integrations/django/
- Logfire Celery integration: https://logfire.pydantic.dev/docs/integrations/celery/
- Logfire psycopg integration: https://logfire.pydantic.dev/docs/integrations/psycopg/
- Logfire structlog integration: https://logfire.pydantic.dev/docs/integrations/structlog/
- OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/
