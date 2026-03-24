---
type: summary
domain: software-engineering
scope: web-fundamentals
---

# Web Fundamentals

Foundational web-platform knowledge underlying the Django + React stack. Protocol-level reference material that other knowledge areas (django, react, devops) build on.

## Files

### Protocol & Networking

| File | Coverage |
|------|----------|
| [http-protocol-reference.md](http-protocol-reference.md) | HTTP methods, status codes, headers, caching model, content negotiation, HTTP/2 and HTTP/3 |
| [dns-tls-and-networking.md](dns-tls-and-networking.md) | DNS resolution, record types, TCP lifecycle, TLS 1.3, HTTPS/Let's Encrypt, CDNs, debugging tools |
| [cors-in-depth.md](cors-in-depth.md) | Same-origin policy, CORS mechanism, preflight, credentialed requests, django-cors-headers config, debugging |
| [api-design-patterns.md](api-design-patterns.md) | REST conventions, pagination strategies, versioning, error design, real-time patterns (SSE, WebSockets), idempotency |

### Browser Platform

| File | Coverage |
|------|----------|
| [browser-dom-events.md](browser-dom-events.md) | Rendering pipeline, DOM tree, event model (capture/bubble/delegation), browser APIs (IntersectionObserver, rAF), script loading |
| [javascript-core-patterns.md](javascript-core-patterns.md) | Event loop, closures, `this` binding, async/await, destructuring, modules, generators |
| [html-semantics-accessibility.md](html-semantics-accessibility.md) | Semantic HTML, landmarks, headings, ARIA, focus management, form accessibility, a11y testing |
| [css-layout-and-selectors.md](css-layout-and-selectors.md) | Box model, Flexbox, Grid, specificity, cascade layers, positioning, container queries, modern CSS |

### Storage & Security

| File | Coverage |
|------|----------|
| [web-storage-and-state.md](web-storage-and-state.md) | Cookies, localStorage, sessionStorage, IndexedDB, Cache API, storage eviction, security guidance |
| [owasp-frontend-security.md](owasp-frontend-security.md) | XSS, CSP, CSRF, clickjacking, open redirect, third-party script risks, security headers |

## Cross-References

These files are referenced by and link to:
- `django/django-react-drf.md` — API design patterns, HTTP semantics, CORS
- `django/django-security.md` — CSRF/CORS interaction, HSTS, CSP
- `django/django-caching-redis.md` — HTTP caching layer in front of application caching
- `django/drf-spectacular.md` — OpenAPI schema generation, API contract documentation
- `devops/nginx-django-react.md` — Reverse proxy: HTTP/2, TLS, caching headers
- `devops/docker-production-config.md` — TLS certificate management in containers
- `devops/zero-downtime-deploys.md` — DNS TTL management during migrations
- `react/react-auth-patterns.md` — Token storage, CORS implications
- `react/react-performance.md` — Browser rendering pipeline foundation
- `react/react-error-boundaries-suspense.md` — Error handling, Sentry reporting
- `react/typescript-react-patterns.md` — JS core patterns foundation
- `react/tanstack-query.md` — Pagination, caching, real-time patterns
- `react/chakra-ui-3-styling-system.md` — CSS cascade, specificity, custom properties
- `react/chakra-ui-3-overview.md` — ARIA patterns in component primitives
