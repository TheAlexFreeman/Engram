---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-002
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [cors, same-origin-policy, security, http, django, react]
related:
  - http-protocol-reference.md
  - ../django/django-react-drf.md
  - ../django/django-security.md
  - ../react/react-auth-patterns.md
---

# CORS In Depth

CORS (Cross-Origin Resource Sharing) is the mechanism browsers use to safely allow web pages to make HTTP requests to a different origin than the one that served the page. This is the most common source of "why doesn't my React app talk to my Django API?" errors. This file explains the underlying model, not just the config snippets.

## 1. Same-Origin Policy

The same-origin policy is the browser's default security model. Two URLs have the **same origin** if and only if they share all three: **scheme**, **host**, and **port**.

```
https://app.example.com:443/page     ← origin
https://app.example.com:443/other    ← same origin (different path is fine)
https://api.example.com:443/data     ← different origin (different host)
http://app.example.com:443/page      ← different origin (different scheme)
https://app.example.com:8080/page    ← different origin (different port)
```

**What same-origin policy restricts** (without CORS headers):
- `fetch()` / `XMLHttpRequest` — blocked
- Canvas reading cross-origin images — tainted
- `postMessage` — allowed (origin check is manual)
- Web fonts loaded via `@font-face` — blocked

**What it does NOT restrict**:
- `<img src="...">` — images load (but canvas can't read pixels)
- `<script src="...">` — scripts execute (this is how CDN-hosted libraries work)
- `<link rel="stylesheet" href="...">` — stylesheets apply
- `<form action="...">` — form submissions (this is why CSRF exists)
- `<iframe src="...">` — loads (but cross-origin iframe content is inaccessible to parent JS)

The key distinction: the browser **sends** the cross-origin request. It just **blocks the response** from being read by JavaScript unless CORS headers authorize it.

## 2. CORS Mechanism

### Simple Requests (No Preflight)

A request is "simple" if it meets ALL of:
1. Method is `GET`, `HEAD`, or `POST`
2. Only "safe" headers: `Accept`, `Accept-Language`, `Content-Language`, `Content-Type` (limited to `application/x-www-form-urlencoded`, `multipart/form-data`, `text/plain`)
3. No `ReadableStream` body

```
Browser                                 Server
  │── GET /api/public/ ─────────────────→│
  │   Origin: https://app.example.com    │
  │                                      │
  │←── 200 OK ──────────────────────────│
  │   Access-Control-Allow-Origin: *     │
  │   (browser allows JS to read body)  │
```

Simple requests skip the preflight — the browser sends the real request directly and checks the response headers.

### Preflighted Requests

Any request that isn't "simple" triggers a preflight `OPTIONS` request first:
- Custom headers (`Authorization`, `Content-Type: application/json`, `X-Request-ID`)
- Methods other than GET/HEAD/POST
- Non-simple `Content-Type`

```
Browser                                      Server
  │── OPTIONS /api/orders/ ──────────────────→│   ← preflight
  │   Origin: https://app.example.com         │
  │   Access-Control-Request-Method: POST     │
  │   Access-Control-Request-Headers:         │
  │     Authorization, Content-Type           │
  │                                           │
  │←── 204 No Content ──────────────────────│
  │   Access-Control-Allow-Origin:            │
  │     https://app.example.com               │
  │   Access-Control-Allow-Methods:           │
  │     GET, POST, PUT, PATCH, DELETE         │
  │   Access-Control-Allow-Headers:           │
  │     Authorization, Content-Type           │
  │   Access-Control-Max-Age: 86400           │
  │                                           │
  │── POST /api/orders/ ────────────────────→│   ← actual request
  │   Origin: https://app.example.com         │
  │   Authorization: Bearer eyJ...            │
  │   Content-Type: application/json          │
  │                                           │
  │←── 201 Created ─────────────────────────│
  │   Access-Control-Allow-Origin:            │
  │     https://app.example.com               │
```

**Why `Content-Type: application/json` triggers preflight**: JSON bodies were not possible with HTML forms (which existed before CORS), so the spec treats them as "not simple" to prevent unexpected cross-origin requests to servers that predate CORS.

## 3. CORS Response Headers

| Header | Purpose | Example |
|--------|---------|---------|
| `Access-Control-Allow-Origin` | Which origin(s) may read the response | `https://app.example.com` or `*` |
| `Access-Control-Allow-Methods` | Allowed methods (preflight only) | `GET, POST, PUT, PATCH, DELETE` |
| `Access-Control-Allow-Headers` | Allowed request headers (preflight only) | `Authorization, Content-Type, X-Request-ID` |
| `Access-Control-Allow-Credentials` | Allow cookies/auth headers | `true` |
| `Access-Control-Max-Age` | Preflight cache duration (seconds) | `86400` (1 day) |
| `Access-Control-Expose-Headers` | Response headers JS can read | `X-Request-ID, X-Total-Count` |

### `Access-Control-Allow-Origin`

Three possible values:
- **`*`** — any origin (public APIs, CDN assets). Cannot be used with `credentials: true`.
- **Specific origin** — `https://app.example.com`. Must match the request `Origin` exactly.
- **Absent** — CORS blocked.

There is no multi-origin syntax. If you need to allow 2+ specific origins, the server must read the `Origin` request header, check it against a whitelist, and echo it back dynamically:

```python
# Pseudocode — this is what django-cors-headers does internally
if request.headers["Origin"] in ALLOWED_ORIGINS:
    response["Access-Control-Allow-Origin"] = request.headers["Origin"]
    response["Vary"] = "Origin"  # CRITICAL: tells caches this varies by origin
```

Without `Vary: Origin`, a CDN might cache the response with one origin and serve it to a different origin, breaking CORS.

### `Access-Control-Expose-Headers`

By default, JavaScript can only read these response headers: `Cache-Control`, `Content-Language`, `Content-Length`, `Content-Type`, `Expires`, `Pragma`. Custom headers like `X-Request-ID` or pagination headers must be explicitly exposed.

## 4. Credentialed Requests

When the browser sends cookies or `Authorization` headers cross-origin, it's a **credentialed request**:

```javascript
// React — fetch with credentials
fetch("https://api.example.com/api/orders/", {
  credentials: "include",   // sends cookies
  headers: { "Content-Type": "application/json" },
});

// Or with axios
axios.defaults.withCredentials = true;
```

**Credentialed CORS rules** (stricter):
1. `Access-Control-Allow-Origin` **cannot be `*`** — must be the exact origin
2. `Access-Control-Allow-Credentials: true` must be present
3. `Access-Control-Allow-Headers` and `Access-Control-Allow-Methods` **cannot be `*`** — must list explicitly

Violating any of these = browser blocks the response silently. The most common error is `*` + credentials.

## 5. Django + React CORS Configuration

### `django-cors-headers` Setup

```python
# settings.py
INSTALLED_APPS = [
    "corsheaders",
    # ... other apps
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",   # MUST be before CommonMiddleware
    "django.middleware.common.CommonMiddleware",
    # ...
]

# Option A: explicit origins (recommended for production)
CORS_ALLOWED_ORIGINS = [
    "https://app.example.com",
    "https://staging.example.com",
]

# Option B: regex pattern
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.example\.com$",
]

# Option C: allow all (dev only — never in production with credentials)
CORS_ALLOW_ALL_ORIGINS = True

# Credentials (needed for session/cookie auth)
CORS_ALLOW_CREDENTIALS = True

# Custom headers your React app sends
CORS_ALLOW_HEADERS = [
    *default_headers,
    "x-request-id",
    "sentry-trace",
    "baggage",
]

# Headers your React app needs to read
CORS_EXPOSE_HEADERS = [
    "x-request-id",
    "x-total-count",
]

# Preflight cache — reduce OPTIONS overhead
CORS_PREFLIGHT_MAX_AGE = 86400  # 1 day
```

**Middleware ordering**: `CorsMiddleware` must run before any middleware that might generate a response (like `CommonMiddleware`), otherwise the CORS headers won't be added to error responses.

### Vite Dev Proxy (CORS Bypass)

During development, the Vite dev server can proxy API requests to Django, avoiding CORS entirely:

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

With this config, React sends requests to `http://localhost:5173/api/...` (same origin), and Vite forwards them to Django. No CORS involved. This is a development convenience — production uses proper CORS headers.

See [django-react-drf.md](../django/django-react-drf.md) for auth-mode-specific CORS patterns and [react-auth-patterns.md](../react/react-auth-patterns.md) for the token vs session auth CORS implications.

## 6. Debugging CORS Errors

### What the Browser Console Shows

```
Access to fetch at 'https://api.example.com/api/orders/'
from origin 'https://app.example.com' has been blocked by CORS policy:
No 'Access-Control-Allow-Origin' header is present on the requested resource.
```

### Systematic Debugging

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "No `Access-Control-Allow-Origin` header" | Server isn't sending CORS headers | Check middleware order, verify `corsheaders` is installed |
| Preflight fails (OPTIONS returns 405) | Server doesn't handle OPTIONS | `CorsMiddleware` handles this — check middleware order |
| "Origin not allowed" | Origin not in `CORS_ALLOWED_ORIGINS` | Add the exact origin (scheme + host + port) |
| Credentialed request blocked | Using `*` with `credentials: include` | Set explicit origin in `CORS_ALLOWED_ORIGINS` + `CORS_ALLOW_CREDENTIALS = True` |
| Custom header blocked | Header not in allowed list | Add to `CORS_ALLOW_HEADERS` |
| Response header unreadable in JS | Header not exposed | Add to `CORS_EXPOSE_HEADERS` |
| Works in Postman, fails in browser | CORS is browser-only | Confirms CORS is the issue (server works fine) |
| Works for GET, fails for POST | Preflight failing | Check if `Access-Control-Allow-Methods` includes POST |

**Key insight**: The server receives and processes the request — CORS doesn't block requests, it blocks response reading. If your Django logs show a 200 but the browser shows a CORS error, the server is fine; the response headers are the problem.

### Inspecting with Browser DevTools

1. Open Network tab → find the failed request
2. Look for a preceding `OPTIONS` request → check its response headers
3. Verify `Access-Control-Allow-Origin` matches the requesting origin exactly
4. For credentialed requests, verify `Access-Control-Allow-Credentials: true`
5. Check the request's `Origin` header to confirm what origin the browser is sending

## 7. Security Considerations

**Why `*` is dangerous with credentials**: If `Access-Control-Allow-Origin: *` could work with credentials, any website could make authenticated requests to your API and read the responses. This would make session cookies meaningless as a security boundary.

**CORS is not a server-side security mechanism**: CORS headers tell the *browser* what to allow. Non-browser clients (curl, Postman, mobile apps, server-to-server) ignore CORS entirely. Never rely on CORS as your only access control — always authenticate and authorize on the server.

**CSRF interaction**: CORS and CSRF are related but distinct. CORS prevents reading cross-origin responses. CSRF prevents forging cross-origin state-changing requests. A form submission (`<form action="https://api/transfer" method="POST">`) bypasses CORS (no JavaScript reads the response) but is caught by CSRF tokens. Both protections are needed.

See [django-security.md](../django/django-security.md) for the CSRF token setup and defense-in-depth patterns.

## Sources

- MDN CORS: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
- MDN Same-Origin Policy: https://developer.mozilla.org/en-US/docs/Web/Security/Same-origin_policy
- Fetch Standard (CORS section): https://fetch.spec.whatwg.org/#http-cors-protocol
- django-cors-headers docs: https://github.com/adamchainz/django-cors-headers
