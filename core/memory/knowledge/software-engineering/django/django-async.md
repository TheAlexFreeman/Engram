---
created: '2026-03-19'
last_verified: 2026-03-20
origin_session: manual
source: external-research
trust: medium
related:
  - psycopg3-and-connection-management.md
---

# Django async

Django async is real, but it is not "the whole framework is magically non-blocking now." As of Django 6.0, the practical picture is: async views and an async request stack work well under ASGI, parts of the ORM have async entrypoints, and some core surfaces are still sync-only enough that you need explicit boundaries. The safe mental model for Alex's stack is to treat async as a way to improve high-concurrency request handling and realtime I/O, not as a replacement for Celery.

## The deployment boundary matters more than `async def`

An `async def` view is only the start. Django's docs are explicit that the full async request stack is available when you run under ASGI. Under WSGI, async views still run, but Django has to create a one-off event loop for the request, which means you can use async APIs but you do not get the scaling advantages of an async stack.

Practical implication:

- ASGI deployment is the path for long-polling, streaming responses, SSE-style endpoints, or high-concurrency outbound I/O.
- WSGI + `async def` is usually a compatibility bridge, not the final architecture.
- If even one synchronous middleware sits in the request path, Django may need to keep a thread per request to emulate the synchronous environment, which can erase much of the async win.

That is why "async Django" is really a stack question, not just a view-signature question.

## Async views: good for concurrent I/O, not for background work

Django supports async function-based views and async HTTP-method handlers on class-based views:

```python
from django.http import JsonResponse

async def healthcheck(request):
    return JsonResponse({"ok": True})
```

```python
from django.views import View
from django.http import JsonResponse

class StatusView(View):
    async def get(self, request):
        return JsonResponse({"status": "ready"})
```

The sweet spot is request-scoped concurrency:

- making several outbound HTTP calls in parallel
- talking to async-native clients
- serving long-lived streaming or push-style HTTP responses
- handling large numbers of mostly-waiting connections under ASGI

Django also notes that client disconnects matter in long-lived async views: a disconnect can raise `asyncio.CancelledError`, so cleanup-sensitive code should handle that explicitly.

## `sync_to_async()` and `async_to_sync()`: the boundary adapters

The two key adapter functions come from `asgiref.sync`:

- `sync_to_async()` lets async code call synchronous code safely
- `async_to_sync()` lets synchronous code call async code safely

In Django work, `sync_to_async()` is the one you reach for most often. Its default mode is `thread_sensitive=True`, which is important rather than incidental. Django's docs explain that many libraries, especially database adapters, require same-thread access, and a lot of existing Django code assumes a single-threaded sync context. That is why the default is conservative.

```python
from asgiref.sync import sync_to_async


def fetch_order(order_id: int):
    return Order.objects.select_related("customer").get(pk=order_id)


async def order_detail(request, order_id: int):
    order = await sync_to_async(fetch_order)(order_id)
    return JsonResponse({"id": order.id, "customer": order.customer_id})
```

Rules that matter in practice:

- Put the whole sync operation inside a helper function and cross the boundary once.
- Do not pass database connections, cursors, or other thread-bound objects across the boundary.
- Prefer `thread_sensitive=True` for Django/ORM code; use `thread_sensitive=False` only for code you know is safely independent.
- `async_to_sync()` is commonly needed when sync code must talk to async-only APIs, such as Channel Layer operations.

## ORM in async code: partially async, not fully async

Django 6.0 is no longer in the "ORM is totally sync-only" phase, but it is also not at "fully native async ORM" yet.

The current state from the official docs:

- query-triggering `QuerySet` methods have `a`-prefixed async variants
- `async for` works over QuerySets
- model/database operations such as `acreate()`, `asave()`, and relation methods like `aset()` are available
- transactions still do not work in async mode
- `CONN_MAX_AGE` persistent connections should be disabled in async mode

Examples:

```python
book = await Book.objects.aget(pk=book_id)
first_tag = await book.tags.afirst()
```

```python
async for author in Author.objects.filter(active=True):
    ...
```

This leads to an important architectural rule: async ORM support is good enough for straightforward query paths, but transaction-heavy or connection-sensitive units of work still belong inside a synchronous helper function called through `sync_to_async()`.

If you violate Django's async-safety rules, you will typically see `SynchronousOnlyOperation`.

Another practical caution: do not build part of a database interaction in async code and then pass a connection-bound object into `sync_to_async()`. Django explicitly warns against passing database connection features across the thread boundary. Encapsulate the full DB operation inside the helper.

Inference from Django's manager model: if a project replaces `.objects` with a custom default manager, use the model's actual default manager methods rather than assuming `.objects` exists. In async code that usually means either `MyModel._default_manager.aget(...)` or a small sync helper that hides the manager choice.

## Async middleware: one sync component can collapse the benefit

Middleware is one of the easiest places to lose the async advantage accidentally.

Django middleware can declare:

- `sync_capable = True`
- `async_capable = True`

If middleware supports both modes, Django can avoid adaptation and pass requests through directly. The `sync_and_async_middleware` decorator exists for this dual-mode pattern.

```python
from asgiref.sync import iscoroutinefunction
from django.utils.decorators import sync_and_async_middleware


@sync_and_async_middleware
def timing_middleware(get_response):
    if iscoroutinefunction(get_response):
        async def middleware(request):
            return await get_response(request)
    else:
        def middleware(request):
            return get_response(request)
    return middleware
```

Operationally:

- sync middleware inside an ASGI stack forces adaptation and can keep a thread per request alive
- `process_view`, `process_exception`, and related hooks should match the actual mode when possible
- Django can adapt mismatched middleware methods, but that adds overhead
- the `django.request` logger can show when Django is adapting middleware for the async handler

For an async-heavy deployment, middleware auditing matters almost as much as view auditing.

## Channels: websockets and realtime, with explicit tradeoffs

Django Channels is the main path when the app needs WebSockets or broader ASGI-style realtime features.

Channels offers both sync and async consumer styles:

- `SyncConsumer` / `WebsocketConsumer`
- `AsyncConsumer` / `AsyncWebsocketConsumer`

The Channels docs recommend a conservative default that mirrors Django's own async story:

- use sync consumers by default
- use async consumers when you are actually working with async-native libraries or parallel I/O
- if async consumers touch the ORM, use `database_sync_to_async` or the ORM's async methods

That recommendation is important because an `AsyncConsumer` that calls blocking sync code will stall the whole event loop.

For channel layers, the production answer is also explicit in the official docs:

- `channels_redis.core.RedisChannelLayer` is the official production backend
- `InMemoryChannelLayer` is for testing or local development only and should not be used in production because it does not support real cross-process messaging

A practical selection rule:

- use Channels when you need bidirectional WebSockets, fan-out groups, or long-lived connection state
- use SSE when communication is one-way server-to-client and the browser/client simplicity matters more than duplex interaction
- use polling when update frequency is low and operational simplicity beats realtime fidelity

That SSE vs. polling guideline is an engineering inference, not a Django rule, but it matches the cost profile of the available tools.

## Async views vs. Celery: do not confuse concurrency with background execution

This is the most important architectural boundary for Alex's stack.

Use async Django when:

- the user is still waiting on the response
- the work is mostly I/O-bound
- concurrency inside the request materially helps latency or connection scaling
- cancellation should be tied to the client connection

Use Celery when:

- the work should survive beyond the request lifecycle
- retries, backoff, or scheduling matter
- queue isolation matters
- the task is CPU-heavy, long-running, or operationally important

Bad pattern:

- turning a 30-second report-generation endpoint into an async view and calling it "background work"

That request is still owned by the web tier, still competes for app capacity, and still lacks Celery's retry, routing, and operational controls. Async Django is not a substitute for the queueing model described in `celery-worker-beat-ops.md` and `celery-canvas-in-depth.md`.

## Testing async views

Django's own testing tools support async tests directly:

- `async def` test methods are detected and run in their own event loop
- when testing from async code, use `django.test.AsyncClient` or `self.async_client`
- requests through `AsyncClient` must be awaited
- `AsyncClient` runs through Django's async request path and hands views an `ASGIRequest`
- headers passed via `extra` do not use the `HTTP_` prefix expected by the sync client

```python
from django.test import AsyncClient, TestCase


class OrdersTests(TestCase):
    async def test_order_detail(self):
        client = AsyncClient()
        response = await client.get("/orders/1/", ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
```

Django also warns that third-party test decorators must be async-compatible. Django's built-in decorators are fine; third-party ones may wrap the wrong layer of execution.

If the project uses pytest, `pytest-asyncio` is the standard event-loop plugin:

- `@pytest.mark.asyncio` makes a coroutine test run as an asyncio task
- in auto mode, the marker can be omitted
- each test gets its own event loop by default, with wider loop scopes available when explicitly requested

That makes the usual Django + pytest pattern straightforward: async tests can use `AsyncClient`, while sync database-heavy setup can remain in ordinary Django/pytest fixtures as needed.

## Practical decision guide for this stack

- Default to sync Django views when the code is mostly ORM and template/serialization work.
- Use async views when the request fan-outs to async HTTP calls or needs long-lived connection handling under ASGI.
- Keep transaction-heavy DB units in sync helpers behind `sync_to_async()`.
- Reach for Channels only when the product actually needs WebSockets or broadcast-style realtime behavior.
- Keep Celery as the boundary for slow, retryable, scheduled, or CPU-heavy work.

That is the cleanest split for a Django + DRF + Celery + Redis deployment: async improves request-path concurrency; Celery owns durable background execution.

## Related files

- `celery-worker-beat-ops.md`
- `celery-canvas-in-depth.md`
- `django-production-stack.md`
- `django-react-drf.md`
- `django-test-data-factories.md`

## Sources

- Django 6.0 async support: https://docs.djangoproject.com/en/6.0/topics/async/
- Django 6.0 middleware docs: https://docs.djangoproject.com/en/6.0/topics/http/middleware/
- Django 6.0 testing tools: https://docs.djangoproject.com/en/6.0/topics/testing/tools/
- Channels 4 consumers: https://channels.readthedocs.io/en/stable/topics/consumers.html
- Channels 4 database access: https://channels.readthedocs.io/en/stable/topics/databases.html
- Channels 4 channel layers: https://channels.readthedocs.io/en/stable/topics/channel_layers.html
- pytest-asyncio docs: https://pytest-asyncio.readthedocs.io/en/stable/
- pytest-asyncio markers: https://pytest-asyncio.readthedocs.io/en/stable/reference/markers/index.html

Last updated: 2026-03-19
