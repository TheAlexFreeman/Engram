---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related:
  - drf-testing-pytest-django-perf-rec.md
  - ../devops/nginx-django-react.md
  - django-security.md
  - pydantic-django-integration.md
  - ../web-fundamentals/http-protocol-reference.md
  - ../web-fundamentals/cors-in-depth.md
---

# Django + React API design via DRF

This file focuses on the Django side of a React frontend stack. The highest-leverage decisions are not serializer syntax; they are API contract design, authentication shape, pagination/filtering discipline, and keeping the browser security model straight.

## Architecture patterns

### Decoupled SPA/API

Most React setups fit here:

- Django serves JSON only
- React is deployed separately
- auth, permissions, data integrity, and file access stay on the Django side

This is the cleanest model when the frontend is a real product app.

### Same-origin React shell

React is still the frontend, but it is served from the same origin as Django. This makes session auth and CSRF easier because the browser and API share origin/session context.

### Hybrid admin / product split

Django serves admin, staff tools, or a few server-rendered pages, while React owns the customer-facing application. This is common and often more pragmatic than forcing one rendering model everywhere.

## Authentication choices

### Session auth for same-origin apps

DRF's auth docs say `SessionAuthentication` is appropriate for AJAX requests made in the same context as the rest of the site. Unsafe methods still require CSRF protection.

This is usually the cleanest choice when:

- React is same-origin with Django
- browser session login is acceptable
- you want fewer custom token flows

### Token/JWT auth for cross-origin SPAs

When the React app is on a different origin, DRF's AJAX/CSRF/CORS guidance says a non-session authentication scheme is usually needed. JWT is common, but it comes with more frontend complexity around refresh, revocation, and storage.

Practical frontend rule:

- access token in memory
- refresh token in `HttpOnly` cookie if using browser sessions across origins
- avoid `localStorage` for long-lived secrets

## CSRF and CORS: the easy place to get burned

DRF's guidance is straightforward:

- same-origin AJAX generally uses session auth
- cross-origin API clients usually need non-session auth
- if you use session auth, unsafe methods must send a valid CSRF token

Django's CSRF docs add two especially relevant implementation details:

- send the token in the `X-CSRFToken` header for AJAX
- use `ensure_csrf_cookie()` if the page doesn't render a form but still needs the CSRF cookie emitted

If `CSRF_USE_SESSIONS` or `CSRF_COOKIE_HTTPONLY` is enabled, the token can't be read from `document.cookie`; it needs to come from the DOM.

For CORS, DRF recommends handling it in middleware and points to `django-cors-headers`.

## DRF baseline settings

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 20,
}
```

If JSON should be the default response format, DRF's renderer docs recommend putting `JSONRenderer` first.

## Serializer patterns

### Separate read and write serializers

This is still one of the cleanest DRF patterns for React frontends:

- read serializers can denormalize and annotate
- write serializers can stay narrow and validation-focused

### Validate business rules close to the boundary

Serializer `validate()` and field validators should catch request-shape issues. Domain invariants that matter outside the API layer should still live deeper than the serializer.

### Prefer IDs over nested writes unless the UX truly needs nested writes

Nested writes are possible but tend to complicate validation, transactions, and frontend retry behavior. Most React apps are easier to evolve when create/update APIs use explicit IDs and dedicated nested endpoints where needed.

## Permissions and object-level enforcement

The missing trap in many DRF examples is object-level authorization. List views often filter correctly, but detail or mutation endpoints forget to enforce ownership checks.

Good pattern:

- constrain `get_queryset()` to what the user may see
- use permission classes for broad policy
- add explicit object-level checks where mutation rules differ from read rules

If the queryset is already scoped per-user, many detail endpoints become safer by default.

## Filtering, search, and ordering

DRF's filtering docs support three broad layers:

- `DjangoFilterBackend` for precise field filtering
- `SearchFilter` for simple text search
- `OrderingFilter` for client-controlled sorting

Practical rule:

- use `filterset_fields` only for simple equality filters
- move to a dedicated `FilterSet` once the contract matters
- keep `ordering_fields` explicit; do not expose every serializer field for sorting

For React frontends, the API contract should be deliberate:

- document supported filters
- keep parameter names stable
- distinguish exact filters from search
- avoid mixing search semantics into many unrelated query params

## Pagination choice matters

`PageNumberPagination` is simple, but `CursorPagination` is often better once feeds become large or frequently updated. It gives a more stable experience for infinite-scroll or activity-feed style UIs and avoids some offset-pagination consistency problems.

Use page numbers when:

- human-readable pages matter
- result sets are small or admin-like

Use cursor pagination when:

- the list is append-heavy
- stable ordering matters
- the UI is scroll/feed driven

## Throttling caveat

DRF's throttling docs explicitly say throttling is not a security boundary and that the built-in implementations use Django's cache with non-atomic operations, so high concurrency can allow some fuzziness. It is good for business-tier rate limiting and basic overuse control, not for hard anti-abuse guarantees.

Scoped throttles are still useful for expensive endpoints like uploads, exports, or report generation.

## Error-shape consistency

React apps benefit from a stable error envelope. DRF lets you override the exception handler, and that is usually worth doing once the frontend matures.

Goals for the error contract:

- top-level stable keys
- field-level validation errors preserved
- machine-readable codes where possible
- request correlation IDs if you have observability infrastructure

## File uploads

For small uploads, multipart DRF endpoints are fine. For large files, direct-to-object-storage upload is usually cleaner:

- browser uploads to S3/GCS via pre-signed URL
- Django receives metadata/key afterward
- background processing can run asynchronously

That keeps the Django app out of the hot path for large bodies.

## API design patterns that age well

- version URLs only when the contract truly changes
- prefer additive changes over mutation of existing response shapes
- annotate and prefetch for frontend-friendly read models
- standardize list envelopes and error envelopes
- make auth mode explicit per deployment model instead of mixing session/JWT casually

## Example ViewSet shape

```python
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "total"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .select_related("user")
            .prefetch_related("items__product")
        )

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return OrderWriteSerializer
        return OrderReadSerializer
```

## Sources

- DRF authentication: https://www.django-rest-framework.org/api-guide/authentication/
- DRF AJAX / CSRF / CORS: https://www.django-rest-framework.org/topics/ajax-csrf-cors/
- Django CSRF guide: https://docs.djangoproject.com/en/6.0/howto/csrf/
- DRF renderers: https://www.django-rest-framework.org/api-guide/renderers/
- DRF filtering: https://www.django-rest-framework.org/api-guide/filtering/
- DRF pagination: https://www.django-rest-framework.org/api-guide/pagination/
- DRF throttling: https://www.django-rest-framework.org/api-guide/throttling/

Last updated: 2026-03-18
