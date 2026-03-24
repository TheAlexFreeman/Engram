---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-001
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [sentry, error-tracking, observability, django, react, celery, tracing, source-maps]
related:
  - ../django/django-observability-structlog-sentry.md
  - ../react/react-error-boundaries-suspense.md
  - ../django/logfire-observability.md
  - ../django/celery-advanced-patterns.md
  - ../react/vite-react-build.md
  - github-actions-cicd.md
---

# Sentry Fullstack Observability: Django + React + Celery

Sentry provides error tracking, performance monitoring, and release health across the full stack. This file covers the cross-cutting Sentry configuration for a Django API + React SPA + Celery worker deployment — separate from the structlog integration covered in [django-observability-structlog-sentry.md](../django/django-observability-structlog-sentry.md), which focuses on logging patterns.

## 1. Project Architecture

Set up two Sentry Projects under one Organization:

| Project | SDK | DSN | Captures |
|---|---|---|---|
| `my-app-backend` | `sentry-sdk[django,celery]` | `SENTRY_DSN_BACKEND` | Django errors, Celery failures, API performance |
| `my-app-frontend` | `@sentry/react` | `SENTRY_DSN_FRONTEND` | JS errors, Web Vitals, user interactions |

Linking them: enable **Distributed Tracing** so spans propagate from React → Django → Celery via the `sentry-trace` and `baggage` headers. This gives end-to-end request visibility.

## 2. Django SDK Setup

```python
# settings.py
import sentry_sdk

sentry_sdk.init(
    dsn=env.sentry_dsn,  # from pydantic-settings (see pydantic-django-integration.md)
    environment=env.environment,
    release=env.sentry_release,  # e.g., "my-app@1.2.3" or git SHA

    # Tracing
    traces_sample_rate=0.1,            # 10% of transactions
    profiles_sample_rate=0.1,          # 10% of profiled transactions
    trace_propagation_targets=[        # propagate trace to these hosts
        "localhost",
        "api.myapp.com",
    ],

    # Integrations (auto-detected, but explicit for clarity)
    integrations=[
        sentry_sdk.integrations.django.DjangoIntegration(
            transaction_style="url",   # group by URL pattern, not raw path
            middleware_spans=True,
        ),
        sentry_sdk.integrations.celery.CeleryIntegration(
            monitor_beat_tasks=True,   # track beat schedule health
            propagate_traces=True,     # link task traces to parent request
        ),
        sentry_sdk.integrations.redis.RedisIntegration(),
        sentry_sdk.integrations.logging.LoggingIntegration(
            level=None,               # don't capture breadcrumbs from all logs
            event_level="ERROR",       # only create events from ERROR+ logs
        ),
    ],

    # Data scrubbing
    send_default_pii=False,
    before_send=scrub_sensitive_data,  # custom scrubber for PII
)
```

### Custom Sampling

```python
def traces_sampler(sampling_context):
    """Higher sampling for critical paths, lower for noisy endpoints."""
    name = sampling_context.get("transaction_context", {}).get("name", "")

    if "/health" in name or "/readiness" in name:
        return 0.0   # never trace health checks
    if "/admin/" in name:
        return 1.0   # always trace admin
    if "/api/checkout" in name or "/api/billing" in name:
        return 0.5   # 50% for payment flows
    if sampling_context.get("parent_sampled") is not None:
        return sampling_context["parent_sampled"]  # respect parent decision

    return 0.1  # default 10%

sentry_sdk.init(
    # ...
    traces_sampler=traces_sampler,
)
```

## 3. React SDK Setup

```typescript
// src/sentry.ts
import * as Sentry from "@sentry/react";

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  environment: import.meta.env.VITE_ENVIRONMENT,
  release: import.meta.env.VITE_SENTRY_RELEASE,

  integrations: [
    Sentry.browserTracingIntegration({
      // TanStack Router integration
      routingInstrumentation: Sentry.reactRouterV7Instrumentation,
    }),
    Sentry.replayIntegration({
      maskAllText: false,
      blockAllMedia: false,
    }),
  ],

  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0.01,  // 1% of sessions get full replay
  replaysOnErrorSampleRate: 1.0,   // 100% replay on error

  // Propagate trace headers to Django API
  tracePropagationTargets: [
    "localhost",
    /^https:\/\/api\.myapp\.com/,
  ],
});
```

### Error Boundary Integration

```tsx
// src/App.tsx — wraps with Sentry error boundary
import * as Sentry from "@sentry/react";

function FallbackComponent({ error, resetError }) {
  return (
    <Box p={8} textAlign="center">
      <Heading size="lg">Something went wrong</Heading>
      <Text>{error.message}</Text>
      <Button onClick={resetError}>Try again</Button>
    </Box>
  );
}

export function App() {
  return (
    <Sentry.ErrorBoundary fallback={FallbackComponent} showDialog>
      <RouterProvider router={router} />
    </Sentry.ErrorBoundary>
  );
}
```

See [react-error-boundaries-suspense.md](../react/react-error-boundaries-suspense.md) for the broader error boundary patterns.

### TanStack Router Integration

```typescript
import { createRouter } from "@tanstack/react-router";
import * as Sentry from "@sentry/react";

const router = createRouter({
  routeTree,
  // Wrap with Sentry instrumentation for route-level tracing
  context: { sentryTrace: true },
});

// Instrument route changes
Sentry.addIntegration(
  Sentry.tanstackRouterBrowserTracingIntegration(router),
);
```

## 4. Distributed Tracing: Django ↔ React

The trace flow:

1. React sends request to Django API with `sentry-trace` and `baggage` headers
2. Django SDK reads these headers and joins the same trace
3. If Django dispatches a Celery task, the trace propagates to the worker
4. Sentry stitches the full waterfall: React → Django → Celery

```
React (Browser)          Django (API)            Celery (Worker)
    │                        │                        │
    ├─ sentry-trace ─────────►                        │
    │                        ├─ task.apply_async() ───►
    │                        │   (trace in headers)    │
    │                        │                        ├─ process_invoice()
    │                        │                        │   spans: db, redis, http
    │◄── response ───────────┤                        │
    │                        │◄─── result ────────────┤
```

**CORS requirement**: The `sentry-trace` and `baggage` headers must be allowed in Django's CORS configuration:

```python
CORS_ALLOW_HEADERS = [
    *default_headers,
    "sentry-trace",
    "baggage",
]
```

## 5. Source Maps for React

Source maps let Sentry show original TypeScript/JSX in stack traces instead of minified production code.

### Vite Plugin

```typescript
// vite.config.ts
import { sentryVitePlugin } from "@sentry/vite-plugin";

export default defineConfig({
  build: {
    sourcemap: true,  // generate source maps
  },
  plugins: [
    react(),
    sentryVitePlugin({
      org: "my-org",
      project: "my-app-frontend",
      authToken: process.env.SENTRY_AUTH_TOKEN,
      release: {
        name: process.env.VITE_SENTRY_RELEASE,
      },
      sourcemaps: {
        filesToDeleteAfterUpload: "**/*.map",  // don't ship .map to CDN
      },
    }),
  ],
});
```

See [vite-react-build.md](../react/vite-react-build.md) for the broader Vite configuration.

### CI/CD Integration

Upload source maps in the build pipeline:

```yaml
# .github/workflows/deploy.yml
- name: Build frontend
  run: npm run build
  env:
    SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
    VITE_SENTRY_RELEASE: ${{ github.sha }}

# Alternatively, use sentry-cli directly:
- name: Upload source maps
  run: |
    sentry-cli releases new ${{ github.sha }}
    sentry-cli sourcemaps upload --release=${{ github.sha }} ./dist
    sentry-cli releases finalize ${{ github.sha }}
```

See [github-actions-cicd.md](github-actions-cicd.md) for the broader CI/CD pipeline setup.

## 6. Release Tracking

Releases connect deploys to errors:

```python
# Django — set via environment variable
# SENTRY_RELEASE=my-app@1.2.3 or git SHA
sentry_sdk.init(release=os.environ.get("SENTRY_RELEASE"))
```

```typescript
// React — set via Vite env
Sentry.init({ release: import.meta.env.VITE_SENTRY_RELEASE });
```

Both backend and frontend should use the **same release identifier** (typically the git SHA) so Sentry correlates errors across the stack. Sentry's release dashboard then shows:
- New errors introduced in this release
- Crash-free session rate
- Regression detection

## 7. Error Grouping and Fingerprinting

Sentry groups errors by stack trace by default. Custom fingerprinting helps when:

```python
# settings.py — custom grouping
def before_send(event, hint):
    exc = hint.get("exc_info")
    if exc:
        exc_type = exc[0]
        # Group all rate limit errors together regardless of endpoint
        if exc_type.__name__ == "RateLimitExceeded":
            event["fingerprint"] = ["rate-limit-exceeded"]
        # Group by Celery task name for task failures
        if "celery" in event.get("tags", {}):
            task_name = event["tags"].get("celery_task_name", "unknown")
            event["fingerprint"] = [f"celery-{task_name}", "{{ default }}"]
    return event

sentry_sdk.init(before_send=before_send)
```

## 8. Alerts and Triage Workflow

Recommended alert rules:

| Alert | Condition | Action |
|---|---|---|
| New issue | First occurrence of error | Slack notification + assign to on-call |
| Regression | Previously resolved error reappears | Slack + high priority |
| Error spike | >5× baseline error rate in 5 min | PagerDuty |
| Performance regression | p95 latency >2× baseline | Slack |
| Celery task failure rate | >10% failure in 15 min | Slack + investigate |

**Triage discipline**: Mark issues as `Resolved`, `Ignored` (with reason), or `Assigned`. Auto-resolve issues not seen for 30 days. Use Sentry's ownership rules to auto-assign based on file path patterns.

## Sources

- Sentry Python SDK docs: https://docs.sentry.io/platforms/python/
- Sentry Django integration: https://docs.sentry.io/platforms/python/integrations/django/
- Sentry Celery integration: https://docs.sentry.io/platforms/python/integrations/celery/
- Sentry React SDK: https://docs.sentry.io/platforms/javascript/guides/react/
- Sentry Vite plugin: https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite/
- Sentry distributed tracing: https://docs.sentry.io/concepts/key-terms/tracing/distributed-tracing/
- Sentry releases: https://docs.sentry.io/product/releases/
