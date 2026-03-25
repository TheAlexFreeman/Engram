---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
tags: [django, drf, openapi, schema, api]
related:
  - drf-testing-pytest-django-perf-rec.md
  - django-react-drf.md
  - django-storages.md
  - pydantic-django-integration.md
  - ../web-fundamentals/api-design-patterns.md
---

# drf-spectacular: OpenAPI 3 Schema Generation for DRF

## Why drf-spectacular

DRF's built-in schema generation (`rest_framework.schemas`) is limited and was officially deprecated as of DRF 3.14. `drf-spectacular` is the community standard replacement, generating OpenAPI 3.0 schemas that are compatible with Swagger UI, Redoc, and any OpenAPI toolchain. It has first-class support for DRF serializers, viewsets, generic views, authentication, pagination, and filtering.

---

## Installation and setup

```bash
pip install drf-spectacular
# For Swagger UI / Redoc served from Django:
pip install drf-spectacular[sidecar]
```

### INSTALLED_APPS

```python
INSTALLED_APPS = [
    ...
    'drf_spectacular',
]
```

### REST_FRAMEWORK setting

```python
REST_FRAMEWORK = {
    ...
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
```

### Minimal SPECTACULAR_SETTINGS

```python
SPECTACULAR_SETTINGS = {
    'TITLE': 'My API',
    'DESCRIPTION': 'API documentation.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,  # Exclude the schema endpoint itself from the schema
    # Auth / security (see JWT section below)
    'SECURITY': [{'jwtAuth': []}],
    # Enum behaviour
    'ENUM_GENERATE_CHOICE_DESCRIPTION': True,
    'ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE': True,
}
```

### URL endpoints

```python
# urls.py
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # Raw schema download
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Swagger UI
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # Redoc
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
```

`SERVE_INCLUDE_SCHEMA = False` keeps the schema endpoint out of the generated schema itself, which is almost always what you want.

---

## Schema annotation with @extend_schema

`@extend_schema` is the primary decorator for overriding or augmenting what drf-spectacular infers. Use it sparingly — the library infers correctly in most cases.

### Basic usage

```python
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

class ArticleViewSet(viewsets.ModelViewSet):
    @extend_schema(
        summary='List published articles',
        description='Returns all articles with status=published, ordered by date.',
        parameters=[
            OpenApiParameter(
                name='tag',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by tag slug',
                required=False,
            ),
        ],
        responses={200: ArticleSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        ...
```

### @extend_schema_view — annotate all actions at once

Use this on a viewset rather than repeating `@extend_schema` on each method:

```python
from drf_spectacular.utils import extend_schema_view

@extend_schema_view(
    list=extend_schema(summary='List articles', tags=['articles']),
    retrieve=extend_schema(summary='Get article', tags=['articles']),
    create=extend_schema(summary='Create article', tags=['articles']),
)
class ArticleViewSet(viewsets.ModelViewSet):
    serializer_class = ArticleSerializer
    queryset = Article.objects.all()
```

### inline_serializer — ad hoc response shapes

When an endpoint returns a shape that doesn't map to a named serializer:

```python
from drf_spectacular.utils import extend_schema, inline_serializer
import serializers as s

@extend_schema(
    responses=inline_serializer(
        name='StatusResponse',
        fields={
            'status': s.CharField(),
            'queued_at': s.DateTimeField(),
        },
    )
)
@api_view(['POST'])
def trigger_export(request):
    ...
```

### Tagging and operation IDs

```python
@extend_schema(tags=['exports'], operation_id='export_trigger')
```

Tags group endpoints in Swagger UI / Redoc. `operation_id` overrides the auto-generated one (useful when you have method collisions across routers).

---

## OpenApiTypes — type constants

`OpenApiTypes` maps to OpenAPI 3 primitive types. Useful when DRF serializer fields don't carry enough type information:

```python
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes

OpenApiParameter(name='cursor', type=OpenApiTypes.STR, location=OpenApiParameter.QUERY)
OpenApiParameter(name='limit', type=OpenApiTypes.INT32, location=OpenApiParameter.QUERY)
OpenApiParameter(name='active', type=OpenApiTypes.BOOL, location=OpenApiParameter.QUERY)
OpenApiParameter(name='from_date', type=OpenApiTypes.DATE, location=OpenApiParameter.QUERY)
```

---

## Request/response examples with OpenApiExample

```python
from drf_spectacular.utils import extend_schema, OpenApiExample

@extend_schema(
    examples=[
        OpenApiExample(
            name='Valid creation',
            summary='Minimal article payload',
            value={'title': 'My Article', 'body': 'Content here.'},
            request_only=True,   # only appear in request body
        ),
        OpenApiExample(
            name='Published response',
            value={'id': 1, 'title': 'My Article', 'status': 'published'},
            response_only=True,
            status_codes=['201'],
        ),
    ],
    responses={201: ArticleSerializer},
)
def create(self, request, *args, **kwargs):
    ...
```

---

## Polymorphic responses: PolymorphicProxySerializer

When an endpoint can return one of several serializer shapes (e.g., a union type):

```python
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema

@extend_schema(
    responses=PolymorphicProxySerializer(
        component_name='NotificationPayload',
        serializers=[EmailNotificationSerializer, SMSNotificationSerializer],
        resource_type_field_name='notification_type',
    )
)
def notification_detail(self, request, pk):
    ...
```

`resource_type_field_name` is the discriminator — the field whose value selects which sub-schema applies. It must be present in all serializer shapes.

---

## JWT authentication in the schema

Add a `SecurityScheme` to `SPECTACULAR_SETTINGS` and reference it in `SECURITY`:

```python
SPECTACULAR_SETTINGS = {
    ...
    'SECURITY': [{'jwtAuth': []}],
    'COMPONENTS': {
        'securitySchemes': {
            'jwtAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    },
}
```

If using `djangorestframework-simplejwt`, install the companion extension instead:

```bash
pip install drf-spectacular-sidecar  # already in [sidecar]
```

simplejwt registers its own `JWTAuthentication` class that drf-spectacular recognises automatically when `DEFAULT_AUTHENTICATION_CLASSES` includes it — no manual `COMPONENTS` config needed.

---

## Enum generation

drf-spectacular infers enums from `choices` on `ChoiceField` / `CharField(choices=...)`. By default it generates a named enum component and a description listing the choices.

### Key settings

```python
SPECTACULAR_SETTINGS = {
    # Include choices as inline description text (default True)
    'ENUM_GENERATE_CHOICE_DESCRIPTION': True,
    # Add explicit blank/null to nullable enums (default True)
    'ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE': True,
    # If two different enums have the same values, merge them under one name
    # Useful to avoid duplicate enum components from shared choices lists:
    'ENUM_GENERATE_CHOICE_DESCRIPTION': True,
}
```

### Suppressing enum generation per-field

If a field has choices but you don't want an enum (e.g., it's open-ended):

```python
@extend_schema_field(OpenApiTypes.STR)
def get_status(self, obj):
    ...
```

---

## Versioning

### URL-based versioning (most common)

```python
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
    'DEFAULT_VERSION': 'v1',
}
```

Generate a version-specific schema:

```bash
python manage.py spectacular --api-version v2 --file openapi-v2.yaml
```

drf-spectacular will filter endpoints to those matching the requested version. From 0.27+, if URL/namespace versioning is set on views, generation automatically scopes to the appropriate version and the schema may shrink compared to unversioned generation.

### Namespace-based versioning

Works similarly. Point the SpectacularAPIView at the right namespace:

```python
path('api/v1/schema/', SpectacularAPIView.as_view(api_version='v1'), name='schema-v1'),
path('api/v2/schema/', SpectacularAPIView.as_view(api_version='v2'), name='schema-v2'),
```

---

## CI schema validation

### Generate and validate in one step

```bash
python manage.py spectacular --validate --file /dev/null
```

`--validate` runs the generated schema through OpenAPI 3 validation. Use `--fail-on-warn` to also fail on warnings.

### CI workflow: detect schema drift

The recommended approach is to commit a generated `openapi.yaml` and fail CI if it drifts:

```bash
# In CI
python manage.py spectacular --file openapi-new.yaml
diff openapi.yaml openapi-new.yaml
```

A diff means a code change affected the API contract without a deliberate schema update. This is a useful forcing function for keeping documentation in sync.

### GitHub Actions snippet

```yaml
- name: Check schema drift
  run: |
    python manage.py spectacular --file openapi-new.yaml
    diff openapi.yaml openapi-new.yaml || (echo "Schema drift detected — regenerate openapi.yaml" && exit 1)
```

---

## Common pitfalls

**Generic views with dynamic serializers**
If `get_serializer_class()` branches at runtime, drf-spectacular can't know which branch to use. Use `@extend_schema` to pin the schema explicitly on those actions.

**SerializerMethodField loses type**
`SerializerMethodField` becomes `any` by default. Annotate it:

```python
@extend_schema_field(OpenApiTypes.STR)
def get_full_name(self, obj):
    return f"{obj.first_name} {obj.last_name}"
```

**Nested serializers in write context**
If a serializer is read-only in responses but writable in requests (a common pattern with nested writes via IDs), use separate serializers or `@extend_schema(request=WriteSerializer, responses=ReadSerializer)`.

**DjangoFilterBackend extension**
Since drf-spectacular 0.27, the built-in DjangoFilterBackend hook was removed. Install the separate extension:

```bash
pip install drf-spectacular-filter-extension
# or use django-filter's own extension support
```

Or, more practically, let `django-filter` register its own drf-spectacular hooks by ensuring `django_filters.rest_framework` is in `DEFAULT_FILTER_BACKENDS` — drf-spectacular picks these up automatically through the extension registry.

---

## Sidecar (bundled Swagger UI / Redoc assets)

If you're serving Swagger UI or Redoc from Django and don't want a CDN dependency:

```bash
pip install drf-spectacular[sidecar]
```

```python
# urls.py
from drf_spectacular.views import SpectacularSwaggerView
from drf_spectacular_sidecar import renderers

urlpatterns = [
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(
        renderer_classes=[renderers.SwaggerUIRenderer]
    ), name='swagger-ui'),
]
```

---

## Quick reference: what drf-spectacular infers automatically

| DRF construct | Inferred correctly |
|---|---|
| ModelSerializer fields | ✅ |
| ChoiceField / choices= | ✅ (enum) |
| ListSerializer / many=True | ✅ |
| CursorPagination | ✅ |
| PageNumberPagination | ✅ |
| TokenAuthentication | ✅ |
| IsAuthenticated permission | ✅ (sets security requirement) |
| `get_serializer_class()` branching | ⚠️ needs @extend_schema |
| SerializerMethodField type | ⚠️ needs @extend_schema_field |
| Non-standard response shapes | ⚠️ needs @extend_schema / inline_serializer |
