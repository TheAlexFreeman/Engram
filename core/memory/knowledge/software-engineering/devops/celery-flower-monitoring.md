---
origin_session: unknown
source: agent-generated
type: knowledge
created: 2026-03-19
last_verified: 2026-03-20
trust: medium
related:
  - celery-multi-worker-docker.md
  - docker-production-config.md
  - github-actions-cicd.md
---

# Celery Monitoring with Flower and Prometheus

Visibility into Celery worker state and task throughput is critical in production. Two complementary layers: **Flower** (real-time task browser) and **Prometheus + Grafana** (time-series metrics, alerting).

---

## 1. Flower — real-time Celery task browser

Flower provides a web UI showing active workers, running/queued/failed tasks, task arguments, durations, and worker resource usage.

### Compose service

```yaml
# docker-compose.yml
services:
  flower:
    image: mher/flower:2.0
    command:
      - celery
      - --broker=redis://redis:6379/0
      - flower
      - --url_prefix=flower
      - --basic_auth=admin:${FLOWER_PASSWORD}
      - --address=0.0.0.0
      - --port=5555
    environment:
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/1
    ports: []  # not directly exposed; reverse-proxied through nginx
    depends_on:
      - redis
```

```nginx
# nginx: proxy /flower/ to Flower
location /flower/ {
    proxy_pass         http://flower:5555/flower/;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
    # WebSocket support (Flower uses WebSocket for live updates)
    proxy_http_version 1.1;
    proxy_set_header   Upgrade $http_upgrade;
    proxy_set_header   Connection "upgrade";
}
```

`--url_prefix=flower` ensures Flower generates correct relative URLs when behind a prefix.

### Flower limitations

- **State is in-memory**: If the Flower container restarts, all task history is lost. Flower shows "live" state from the broker, not persisted history.
- **Not a metrics system**: Use Prometheus for alerting and historical trends.
- **Auth**: `basic_auth` is adequate behind TLS; add IP allowlisting for extra security.
- **Celery 5 and the `celery events` stream**: Flower connects to the Celery events stream (UDP/TCP depending on broker). Redis broker uses regular pubsub — no extra config needed.

---

## 2. django-prometheus

```bash
pip install django-prometheus
```

```python
# settings.py
INSTALLED_APPS = [
    ...
    "django_prometheus",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    # ... other middleware ...
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]
```

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    ...
    path("", include("django_prometheus.urls")),  # exposes /metrics
]
```

`/metrics` endpoint exposes:
- `django_http_requests_total_by_method_total` — request counts by method/view/status
- `django_http_request_duration_seconds` — response time histogram
- `django_http_requests_body_total_bytes` — request payload sizes
- `django_db_execute_total` — SQL query counts
- Python process metrics (memory, GC, open FDs)

### Protecting /metrics in production

```python
# Restrict to internal Prometheus scraper only (nginx allowlist)
location /metrics {
    allow 10.0.0.0/8;   # internal network
    allow 172.16.0.0/12;
    deny all;
    proxy_pass http://web:8000;
}
```

---

## 3. Celery metrics

### Option A: celery-prometheus-exporter (sidecar)

```yaml
services:
  celery-exporter:
    image: danihodovic/celery-exporter:0.10
    command:
      - --broker-url=redis://redis:6379/0
      - --listen-address=0.0.0.0:9808
    depends_on:
      - redis
```

Exposes on `:9808/metrics`:
- `celery_task_received_total` — tasks received (by name)
- `celery_task_started_total` — tasks started
- `celery_task_succeeded_total` — tasks successful
- `celery_task_failed_total` — tasks failed
- `celery_task_retried_total` — tasks retried
- `celery_task_runtime_seconds` — execution duration histogram (percentiles)
- `celery_worker_tasks_active` — currently executing per worker
- `celery_workers_online` — worker count gauge

### Option B: Custom signals (no sidecar)

```python
# tasks/metrics.py
from celery.signals import task_prerun, task_postrun, task_failure
from prometheus_client import Counter, Histogram
import time

TASK_SUCCEEDED = Counter("celery_task_succeeded_total", "Tasks succeeded", ["task_name"])
TASK_FAILED = Counter("celery_task_failed_total", "Tasks failed", ["task_name"])
TASK_RUNTIME = Histogram("celery_task_runtime_seconds", "Task runtime", ["task_name"],
                          buckets=[0.1, 0.5, 1, 5, 10, 30, 60, 120])

_task_start_times = {}

@task_prerun.connect
def task_prerun_handler(task_id, task, **kwargs):
    _task_start_times[task_id] = time.monotonic()

@task_postrun.connect
def task_postrun_handler(task_id, task, retval, state, **kwargs):
    start = _task_start_times.pop(task_id, None)
    if start is not None:
        TASK_RUNTIME.labels(task_name=task.name).observe(time.monotonic() - start)
    if state == "SUCCESS":
        TASK_SUCCEEDED.labels(task_name=task.name).inc()

@task_failure.connect
def task_failure_handler(task_id, exception, sender, **kwargs):
    TASK_FAILED.labels(task_name=sender.name).inc()
```

---

## 4. Queue depth via Redis LLEN

Queue depth is the most actionable metric for scaling decisions. Celery uses Redis lists; check depth with:

```bash
# Manual check:
docker compose exec redis redis-cli LLEN celery          # default queue
docker compose exec redis redis-cli LLEN priority        # priority queue
docker compose exec redis redis-cli LLEN emails
```

For Prometheus:

```yaml
# redis_exporter: expose redis metrics including list lengths
services:
  redis-exporter:
    image: oliver006/redis_exporter:v1.58.0
    environment:
      REDIS_ADDR: redis:6379
    command:
      - --include-system-metrics
      - --check-streams
      # Expose LLEN for Celery queues as a custom metric:
      - --check-keys=celery,priority,emails
```

This exposes `redis_list_length{key="celery"}` which can be alerted on.

---

## 5. Prometheus scrape configuration

```yaml
# prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: django
    static_configs:
      - targets: ["web:8000"]
    metrics_path: /metrics

  - job_name: celery
    static_configs:
      - targets: ["celery-exporter:9808"]

  - job_name: redis
    static_configs:
      - targets: ["redis-exporter:9121"]

  - job_name: postgres
    static_configs:
      - targets: ["postgres-exporter:9187"]
```

### Postgres exporter

```yaml
services:
  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:v0.15.0
    environment:
      DATA_SOURCE_NAME: "postgresql://monitor:monitorpass@postgres:5432/myapp?sslmode=disable"
```

Key metrics: `pg_up`, `pg_stat_database_blks_hit/read` (cache hit ratio), `pg_stat_activity_count`, `pg_database_size_bytes`, `pg_stat_user_tables_seq_scan` (full table scans = missing index).

---

## 6. Grafana

```yaml
services:
  grafana:
    image: grafana/grafana:10.3.1
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
      GF_SERVER_ROOT_URL: "%(protocol)s://%(domain)s/grafana/"
      GF_SERVER_SERVE_FROM_SUB_PATH: "true"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
```

```yaml
# grafana/provisioning/datasources/prometheus.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
```

```yaml
# grafana/provisioning/dashboards/provider.yml
apiVersion: 1
providers:
  - name: default
    folder: ""
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards/json
```

Provisioned dashboards (JSON files in `grafana/provisioning/dashboards/json/`) are loaded on startup. Use [grafana.com/grafana/dashboards](https://grafana.com/grafana/dashboards) IDs for community dashboards.

---

## 7. Alerting rules

```yaml
# prometheus/alerts.yml
groups:
  - name: celery
    rules:
      - alert: CeleryQueueDepthHigh
        expr: redis_list_length{key="celery"} > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Celery queue backlog: {{ $value }} tasks"

      - alert: CeleryWorkerDown
        expr: celery_workers_online < 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "No Celery workers online"

      - alert: CeleryTaskFailureRateHigh
        expr: |
          rate(celery_task_failed_total[5m]) /
          (rate(celery_task_succeeded_total[5m]) + rate(celery_task_failed_total[5m])) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Task failure rate above 5%: {{ $value | humanizePercentage }}"

      - alert: CeleryTaskRuntimeP95High
        expr: histogram_quantile(0.95, rate(celery_task_runtime_seconds_bucket[10m])) > 60
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "95th pct task runtime > 60s"
```

---

## 8. Promtail + Loki (log aggregation)

For lightweight log aggregation without ELK complexity:

```yaml
services:
  loki:
    image: grafana/loki:2.9.4
    command: -config.file=/etc/loki/local-config.yaml
    volumes:
      - loki_data:/loki

  promtail:
    image: grafana/promtail:2.9.4
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock
      - ./promtail/config.yml:/etc/promtail/config.yml
    command: -config.file=/etc/promtail/config.yml
```

```yaml
# promtail/config.yml
server:
  http_listen_port: 9080

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
    relabel_configs:
      - source_labels: ["__meta_docker_container_name"]
        target_label: container
```

Add Loki as a Grafana datasource (`http://loki:3100`), then use LogQL to query logs alongside metrics in the same dashboard.
