---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-002
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [http, protocol, status-codes, headers, caching, rest, http2]
related:
  - ../django/django-react-drf.md
  - ../devops/nginx-django-react.md
  - ../django/django-caching-redis.md
  - dns-tls-and-networking.md
  - cors-in-depth.md
  - ../django/django-security.md
---

# HTTP Protocol Reference

Practical reference for HTTP as it affects a Django API + React SPA stack. Covers the request/response model, methods, status codes, headers, caching, and protocol versions.

## 1. Request/Response Anatomy

```
REQUEST                              RESPONSE
POST /api/orders/ HTTP/1.1           HTTP/1.1 201 Created
Host: api.example.com                Content-Type: application/json
Content-Type: application/json       Cache-Control: no-store
Authorization: Bearer eyJ...         X-Request-ID: abc-123
Accept: application/json             Location: /api/orders/42/
X-Request-ID: abc-123
                                     {"id": 42, "status": "created"}
{"product_id": 7, "quantity": 2}
```

**Request**: method + path + HTTP version, then headers, then optional body.
**Response**: HTTP version + status code + reason phrase, then headers, then optional body.

Headers are case-insensitive. Body encoding is declared by `Content-Type`.

## 2. HTTP Methods

| Method | Safe | Idempotent | Body | Typical Use |
|--------|------|------------|------|-------------|
| `GET` | Yes | Yes | No | Retrieve resource(s) |
| `HEAD` | Yes | Yes | No | Like GET but response-body-free (health checks) |
| `POST` | No | No | Yes | Create resource, trigger action |
| `PUT` | No | Yes | Yes | Full replace of a resource |
| `PATCH` | No | No* | Yes | Partial update |
| `DELETE` | No | Yes | Rarely | Remove resource |
| `OPTIONS` | Yes | Yes | No | CORS preflight, capability discovery |

**Safe** = no server-side effect. **Idempotent** = calling N times produces the same result as calling once.

*`PATCH` can be made idempotent with conditional headers (`If-Match` + ETag), but the spec does not require it.

DRF maps these methods to viewset actions: `list` (GET collection), `retrieve` (GET detail), `create` (POST), `update` (PUT), `partial_update` (PATCH), `destroy` (DELETE).

## 3. Status Codes — Practical Reference

### 2xx Success

| Code | Name | When to Use |
|------|------|-------------|
| **200** | OK | Successful GET, PUT, PATCH |
| **201** | Created | Successful POST that creates a resource. Include `Location` header |
| **204** | No Content | Successful DELETE, or PUT/PATCH when there's nothing to return |

### 3xx Redirection

| Code | Name | Key Behavior |
|------|------|--------------|
| **301** | Moved Permanently | Browser caches. Method may change to GET (historical) |
| **302** | Found | Temporary. Method may change to GET |
| **307** | Temporary Redirect | Like 302 but **preserves method** (POST stays POST) |
| **308** | Permanent Redirect | Like 301 but **preserves method** |
| **304** | Not Modified | Conditional GET: resource unchanged, use cached version |

**Rule of thumb**: Use 307/308 when method preservation matters (API redirects). 301/302 are fine for browser navigation.

### 4xx Client Errors

| Code | Name | When to Use |
|------|------|-------------|
| **400** | Bad Request | Malformed request syntax, invalid JSON |
| **401** | Unauthorized | Missing or invalid authentication credentials |
| **403** | Forbidden | Authenticated but not authorized for this resource |
| **404** | Not Found | Resource doesn't exist (or intentionally hiding from unauthorized users) |
| **405** | Method Not Allowed | HTTP method not supported on this endpoint |
| **409** | Conflict | State conflict (optimistic concurrency, duplicate creation) |
| **422** | Unprocessable Entity | Valid syntax but semantic errors (DRF validation failures) |
| **429** | Too Many Requests | Rate limited. Include `Retry-After` header |

**401 vs 403**: 401 means "who are you?" (re-authenticate). 403 means "I know who you are, but no" (re-authorization won't help).

**400 vs 422**: DRF uses 400 for validation errors by default. 422 is more semantically precise for "valid JSON, invalid field values." Either is acceptable if consistent.

### 5xx Server Errors

| Code | Name | Meaning |
|------|------|---------|
| **500** | Internal Server Error | Unhandled exception on the server |
| **502** | Bad Gateway | Upstream server (Gunicorn/Uvicorn) returned invalid response to proxy (Nginx) |
| **503** | Service Unavailable | Server overloaded or in maintenance. Include `Retry-After` |
| **504** | Gateway Timeout | Proxy (Nginx) timed out waiting for upstream |

**502 vs 504**: 502 = upstream responded but response was bad. 504 = upstream didn't respond at all within the timeout. Both indicate unhealthy app servers.

## 4. Key Headers Reference

### Request Headers

| Header | Purpose | Example |
|--------|---------|---------|
| `Content-Type` | Body encoding | `application/json` |
| `Accept` | Desired response format | `application/json, text/html;q=0.9` |
| `Authorization` | Auth credentials | `Bearer eyJ...` or `Token abc123` |
| `Cookie` | Session/auth cookies | `sessionid=abc; csrftoken=xyz` |
| `If-None-Match` | Conditional GET (ETag) | `"v1-abc123"` |
| `If-Modified-Since` | Conditional GET (date) | `Mon, 24 Mar 2026 12:00:00 GMT` |
| `X-Request-ID` | Request correlation | `uuid-for-tracing` |
| `Origin` | CORS: requesting origin | `https://app.example.com` |

### Response Headers

| Header | Purpose | Example |
|--------|---------|---------|
| `Content-Type` | Body encoding | `application/json; charset=utf-8` |
| `Cache-Control` | Caching directives | `public, max-age=3600, immutable` |
| `ETag` | Resource version tag | `"v1-abc123"` |
| `Vary` | Cache key dimensions | `Accept, Authorization` |
| `Location` | Redirect or created resource URL | `/api/orders/42/` |
| `Retry-After` | When to retry (429/503) | `60` (seconds) or date |
| `X-Request-ID` | Request correlation (echo back) | `uuid-for-tracing` |
| `Access-Control-*` | CORS headers | See [cors-in-depth.md](cors-in-depth.md) |

### Content Negotiation

The `Accept` header tells the server which response formats the client prefers:

```
Accept: application/json                     # JSON only
Accept: application/json, text/html;q=0.9   # prefer JSON, accept HTML
Accept: */*                                  # anything
```

DRF uses `DEFAULT_RENDERER_CLASSES` to respond with the best match. The `Content-Type` request header declares what the client is *sending* — distinct from `Accept`, which declares what it wants *back*.

The `Vary` response header tells caches which request headers affect the response. `Vary: Accept` means "the response depends on the `Accept` header — cache separate versions." Always set `Vary` for content-negotiated endpoints.

## 5. HTTP Caching Model

### Cache-Control Directives

```
Cache-Control: public, max-age=31536000, immutable   # static assets (JS/CSS bundles)
Cache-Control: private, no-cache                      # user-specific API responses
Cache-Control: no-store                               # sensitive data, never cache
```

| Directive | Meaning |
|-----------|---------|
| `public` | Any cache (CDN, proxy, browser) may store |
| `private` | Only the browser may store (not shared caches) |
| `no-cache` | Cache may store, but **must revalidate** before each use |
| `no-store` | **Do not store** anywhere — for sensitive responses |
| `max-age=N` | Fresh for N seconds from response time |
| `s-maxage=N` | Like `max-age` but only for shared caches (CDN/proxy) |
| `immutable` | Content will never change at this URL (fingerprinted assets) |
| `stale-while-revalidate=N` | Serve stale for N seconds while revalidating in background |
| `must-revalidate` | Once stale, must revalidate — no grace period |

**`no-cache` vs `no-store`**: `no-cache` permits caching but requires the cache to check the server on every request (via ETag or `If-Modified-Since`). `no-store` forbids caching entirely. For API responses with user data, `no-store` is safest.

### Conditional Requests (ETags)

```
# First request
→ GET /api/products/42/
← 200 OK
← ETag: "v3-f4b2"

# Later request — browser includes the ETag
→ GET /api/products/42/
→ If-None-Match: "v3-f4b2"
← 304 Not Modified          # body not sent, use cached version
```

Conditional requests save bandwidth and server processing. Django's `ConditionalGetMiddleware` adds `ETag` and handles `If-None-Match` automatically for GET responses.

### Caching Strategy by Resource Type

| Resource | `Cache-Control` | Why |
|----------|-----------------|-----|
| Vite bundles (`app.abc123.js`) | `public, max-age=31536000, immutable` | Hash in filename = unique URL per build |
| `index.html` (SPA entry) | `no-cache` | Must check for new deployments |
| API list endpoints | `private, no-cache` + ETag | User-specific, may change |
| API detail with slow mutation | `private, max-age=60` | Short freshness window |
| Sensitive API (billing, PII) | `no-store` | Never cache |
| Static media (images) | `public, max-age=86400` | Moderate freshness |

See [nginx-django-react.md](../devops/nginx-django-react.md) for how Nginx applies these headers in the reverse-proxy layer.

## 6. HTTP/2 and HTTP/3

### HTTP/2

| Feature | Benefit |
|---------|---------|
| **Multiplexing** | Multiple requests/responses over one TCP connection — eliminates head-of-line blocking at HTTP layer |
| **Header compression (HPACK)** | Reduces overhead on repeated headers (cookies, auth tokens) |
| **Stream prioritization** | Client hints which resources to send first |
| **Server Push** | Server proactively sends resources (largely deprecated — better alternatives exist) |
| **Binary framing** | More efficient parsing vs HTTP/1.1 text format |

**Practical impact**: With h2, bundling strategies change. Concatenating many small files into one large bundle is less important because multiplexing handles parallel delivery efficiently. However, code splitting is still valuable for cache granularity.

Nginx enables HTTP/2 with `listen 443 ssl http2;`. All modern browsers require TLS for h2.

### HTTP/3 (QUIC)

HTTP/3 replaces TCP with QUIC (UDP-based). Key benefit: eliminates TCP head-of-line blocking at the transport layer. Streams are independent — a lost packet only stalls one stream, not all multiplexed streams.

Adoption: supported by major CDNs (Cloudflare, AWS CloudFront) and browsers. Nginx experimental support. Not yet critical for most deployments but worth awareness for latency-sensitive applications.

## Sources

- MDN HTTP reference: https://developer.mozilla.org/en-US/docs/Web/HTTP
- RFC 9110 (HTTP Semantics): https://httpwg.org/specs/rfc9110.html
- RFC 9111 (HTTP Caching): https://httpwg.org/specs/rfc9111.html
- RFC 9113 (HTTP/2): https://httpwg.org/specs/rfc9113.html
- MDN Cache-Control: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
