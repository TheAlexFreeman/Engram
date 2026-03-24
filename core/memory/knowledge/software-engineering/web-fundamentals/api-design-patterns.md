---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-002
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [api, rest, graphql, websockets, pagination, versioning, realtime]
related:
  - http-protocol-reference.md
  - cors-in-depth.md
  - ../django/django-react-drf.md
  - ../django/drf-spectacular.md
  - ../react/tanstack-query.md
  - ../react/tanstack-router.md
---

# API Design Patterns

Protocol-level and architectural patterns for web APIs, independent of specific frameworks. Covers REST conventions, pagination strategies, versioning, real-time patterns, and error design. For DRF-specific implementation, see [django-react-drf.md](../django/django-react-drf.md); this file covers the *design-level decisions* that precede implementation.

## 1. REST Resource Design

### URL Structure Conventions

```
# Resources are nouns, not verbs
GET    /api/orders/              # list
POST   /api/orders/              # create
GET    /api/orders/42/           # retrieve
PUT    /api/orders/42/           # full update
PATCH  /api/orders/42/           # partial update
DELETE /api/orders/42/           # delete

# Nested resources — one level deep max
GET    /api/orders/42/items/     # items belonging to order 42
POST   /api/orders/42/items/     # add item to order 42

# Actions that don't map to CRUD — use verbs as sub-resources
POST   /api/orders/42/cancel/    # RPC-style action on a resource
POST   /api/orders/42/refund/
```

**Guidelines**:
- Plural nouns for collections (`/orders/`, not `/order/`)
- Trailing slashes: pick one convention and enforce (Django uses trailing slashes)
- Max 2 levels of nesting (`/orders/42/items/`). Deeper → flatten with filters (`/items/?order=42`)
- IDs in URLs, not query params, for single-resource operations

### Resource Representation

```json
// Response — include only what the client needs
{
  "id": 42,
  "status": "shipped",
  "created_at": "2026-03-24T10:30:00Z",    // ISO 8601, always UTC
  "customer": {
    "id": 7,
    "name": "Alex"                           // nested read representation
  },
  "items_url": "/api/orders/42/items/",      // link to related collection
  "total": "129.99"                          // string for decimal precision
}

// Write request — flat IDs for related objects (not nested objects)
{
  "customer_id": 7,
  "items": [{"product_id": 3, "quantity": 2}]
}
```

**Separate read and write shapes**: Read responses can include nested objects and computed fields. Write requests should accept flat IDs. DRF implements this with separate serializers (see django-react-drf.md).

## 2. Pagination Strategies

### Offset/Limit (Page Number)

```
GET /api/orders/?page=3&page_size=25

Response:
{
  "count": 234,
  "next": "/api/orders/?page=4&page_size=25",
  "previous": "/api/orders/?page=2&page_size=25",
  "results": [...]
}
```

| Pros | Cons |
|------|------|
| Simple to implement | Skips/duplicates if data changes between pages |
| Random page access | Slow on large tables (`OFFSET` scans rows) |
| Total count available | `COUNT(*)` query can be expensive |

### Cursor-Based

```
GET /api/orders/?cursor=eyJpZCI6NDJ9&page_size=25

Response:
{
  "next": "/api/orders/?cursor=eyJpZCI6Njd9&page_size=25",
  "previous": null,
  "results": [...]
}
```

| Pros | Cons |
|------|------|
| Consistent results (no skip/duplicate) | No random page access |
| Fast on any dataset size (uses `WHERE id > x`) | No total count (by design) |
| Works with real-time feeds | Client must follow links sequentially |

**When to use which**:
- Admin dashboards, tables with "go to page N" → offset/limit
- Infinite scroll, feeds, mobile apps → cursor-based
- Frequently mutating data → cursor (avoids shifting results)

TanStack Query's `useInfiniteQuery` is designed for cursor-based pagination — it manages the cursor chain and page accumulation.

### Keyset Pagination (Manual Cursor)

```sql
-- Instead of OFFSET (slow):
SELECT * FROM orders ORDER BY id LIMIT 25 OFFSET 1000;

-- Use keyset (fast — index scan):
SELECT * FROM orders WHERE id > 1000 ORDER BY id LIMIT 25;
```

The "cursor" is the last seen sort key(s), base64-encoded. DRF's `CursorPagination` implements this.

## 3. Filtering, Search, and Sorting

```
# Exact match
GET /api/orders/?status=shipped

# Multiple values (OR)
GET /api/orders/?status=shipped,delivered

# Range
GET /api/products/?price_min=10&price_max=50
GET /api/orders/?created_after=2026-01-01

# Full-text search
GET /api/products/?search=wireless+headphones

# Sorting
GET /api/orders/?ordering=-created_at,status    # descending created, ascending status

# Combining
GET /api/orders/?status=shipped&ordering=-created_at&page=1&page_size=25
```

### API Contract Stability

Expose only the filters clients need. Document which fields are filterable and sortable. Adding new filters is backward-compatible; removing or renaming them breaks clients.

**TanStack Router integration**: Search params in TanStack Router map cleanly to API query params. Define a `searchSchema` with Zod validation so type-safe search params flow from URL → Router → TanStack Query → DRF filters:

```typescript
const ordersRoute = createFileRoute('/orders')({
  validateSearch: z.object({
    status: z.enum(['pending', 'shipped', 'delivered']).optional(),
    page: z.number().default(1),
    ordering: z.string().default('-created_at'),
  }),
});
```

## 4. Error Response Design

### Consistent Error Envelope

```json
// Single error
{
  "type": "validation_error",
  "message": "Invalid input.",
  "errors": [
    { "field": "email", "message": "Enter a valid email address." },
    { "field": "quantity", "message": "Ensure this value is greater than 0." }
  ]
}

// Non-field error
{
  "type": "authentication_error",
  "message": "Authentication credentials were not provided."
}
```

**Rules**:
- Same envelope structure for all errors (4xx and 5xx)
- Machine-readable `type` for client branching (`validation_error`, `not_found`, `permission_denied`)
- Human-readable `message` for display
- Field-level `errors` array for form validation (maps to react-hook-form's `setError`)
- Never expose stack traces, SQL, or internal paths in production

### HTTP Status Code + Error Type Mapping

| Status | Error Type | Client Action |
|--------|-----------|---------------|
| 400 | `validation_error` | Show field errors in form |
| 401 | `authentication_error` | Redirect to login / refresh token |
| 403 | `permission_denied` | Show "not authorized" message |
| 404 | `not_found` | Show 404 page or remove stale item |
| 409 | `conflict` | Show conflict resolution UI |
| 422 | `validation_error` | Same as 400 (semantic variant) |
| 429 | `rate_limited` | Show retry message, respect `Retry-After` |
| 500 | `server_error` | Show generic error, report to Sentry |

## 5. API Versioning

### Strategies

| Strategy | Example | Pros | Cons |
|----------|---------|------|------|
| **URL path** | `/api/v2/orders/` | Explicit, cacheable, easy to route | URL litter, breaking change to switch |
| **Header** | `Accept: application/vnd.myapp.v2+json` | Clean URLs | Hidden, harder to test |
| **Query param** | `/api/orders/?version=2` | Easy to switch | Caching complications |

**Recommendation for Django+React**: URL path versioning (`/api/v1/`) is the most pragmatic. It's explicit, works with all HTTP caches and CDNs, and both DRF and TanStack Query handle it trivially.

### Additive Change Strategy (Avoid Versioning)

Most version bumps can be avoided by designing APIs for evolution:

| Change | Breaking? | Strategy |
|--------|-----------|----------|
| Add new field to response | No | Clients ignore unknown fields |
| Add optional query parameter | No | Existing requests still work |
| Add new endpoint | No | New capability, no impact |
| Remove field from response | **Yes** | Deprecate first, remove in v2 |
| Rename field | **Yes** | Add new name, keep old as alias, deprecate |
| Change field type | **Yes** | New field name with new type |
| Remove endpoint | **Yes** | Deprecation period, then remove |

**Document the contract**: Use [drf-spectacular](../django/drf-spectacular.md) to auto-generate OpenAPI schemas. Clients can codegen TypeScript types from the schema, making breaking changes detectable at build time.

## 6. Real-Time Patterns

### Polling (Simplest)

```javascript
// TanStack Query — automatic refetch on interval
const { data } = useQuery({
  queryKey: ['notifications'],
  queryFn: fetchNotifications,
  refetchInterval: 5000, // poll every 5 seconds
});
```

Pros: Simple, works everywhere, no infrastructure changes.
Cons: Latency (up to interval duration), unnecessary requests when nothing changes, doesn't scale for high-frequency updates.

### Server-Sent Events (SSE)

Unidirectional: server → client. Built on HTTP — works through proxies, load balancers, and CDNs.

```python
# Django view (streaming response)
from django.http import StreamingHttpResponse

def event_stream(request):
    def generate():
        while True:
            data = get_latest_notification()
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(1)
    return StreamingHttpResponse(generate(), content_type='text/event-stream')
```

```javascript
// Browser client
const source = new EventSource('/api/events/');
source.onmessage = (event) => {
  const data = JSON.parse(event.data);
  queryClient.setQueryData(['notifications'], (old) => [...old, data]);
};
source.onerror = () => source.close();  // reconnect logic
```

Pros: HTTP-native, auto-reconnection, works behind most proxies.
Cons: Unidirectional (server→client only), limited to text. No binary support.

### WebSockets

Bidirectional, full-duplex communication over a persistent TCP connection:

```javascript
const ws = new WebSocket('wss://api.example.com/ws/orders/');

ws.onopen = () => ws.send(JSON.stringify({ type: 'subscribe', channel: 'orders' }));
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  queryClient.invalidateQueries({ queryKey: ['orders'] });
};
ws.onclose = () => { /* reconnect with exponential backoff */ };
```

Django Channels provides WebSocket support with routing, groups (pub/sub), and channel layers (Redis backend).

| Feature | SSE | WebSocket |
|---------|-----|-----------|
| Direction | Server → Client | Bidirectional |
| Protocol | HTTP | ws:// / wss:// |
| Auto-reconnect | Built-in | Manual |
| Binary data | No | Yes |
| Proxy/CDN friendly | Yes | Usually (but some strip) |
| Connection overhead | Low (HTTP) | Higher (upgrade handshake) |

**Decision rule**: Use SSE for notifications, live feeds, and dashboards (server pushes updates). Use WebSockets for chat, collaborative editing, or any pattern requiring client→server messages over the same connection. Use polling if the update frequency is low and infrastructure simplicity matters.

## 7. Idempotency

An idempotent operation produces the same result whether called once or N times. Critical for retries:

```
PUT /api/orders/42/ {"status": "shipped"}
# Calling this 5 times → order is "shipped". Same result.

POST /api/orders/ {"product_id": 3}
# Calling this 5 times → 5 orders created. NOT idempotent.
```

### Idempotency Keys (for POST)

```
POST /api/payments/
Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{"amount": 100, "currency": "USD"}
```

The server stores the result keyed by the idempotency key. If the same key is sent again, the server returns the stored result without reprocessing. The client generates a UUID and retries with the same key on network failure.

This prevents double-charges, duplicate orders, and other side effects from retried POST requests.

## 8. Rate Limiting and Backoff

### Client-Side Handling

```javascript
async function fetchWithRetry(url, options, maxRetries = 3) {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const response = await fetch(url, options);
    if (response.status === 429) {
      const retryAfter = parseInt(response.headers.get('Retry-After') || '5', 10);
      await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
      continue;
    }
    return response;
  }
  throw new Error('Max retries exceeded');
}
```

**Exponential backoff**: `delay = min(baseDelay * 2^attempt + jitter, maxDelay)`. TanStack Query's built-in retry uses exponential backoff by default.

## Sources

- REST API Design Rulebook (O'Reilly)
- Microsoft REST API Guidelines: https://github.com/microsoft/api-guidelines
- Google API Design Guide: https://cloud.google.com/apis/design
- MDN Server-Sent Events: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
- MDN WebSocket API: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket
- Stripe Idempotent Requests: https://docs.stripe.com/api/idempotent_requests
