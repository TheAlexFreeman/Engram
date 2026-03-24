---
source: external-research
origin_session: core/memory/activity/2026/03/24/chat-001
created: 2026-03-24
trust: medium
type: knowledge
domain: software-engineering
tags: [pydantic, django, settings, validation, celery, drf]
related:
  - django-react-drf.md
  - drf-spectacular.md
  - celery-advanced-patterns.md
  - logfire-observability.md
  - ../devops/environment-secrets-management.md
---

# Pydantic and Django Integration

Pydantic v2 is a data validation library built on a Rust core (`pydantic-core`) that provides type-safe parsing, serialization, and settings management. In a Django stack it fills three roles: environment/settings management via `pydantic-settings`, validation of data flowing between services (Celery tasks, external APIs), and optionally as a DRF serializer alternative via `django-ninja`. It complements rather than replaces Django forms and DRF serializers.

## 1. Pydantic Settings for Django Configuration

`pydantic-settings` replaces hand-rolled `os.environ.get()` calls with typed, validated, documented configuration:

```python
# config/settings_schema.py
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
        case_sensitive=False,
    )

    debug: bool = False
    secret_key: SecretStr
    database_url: str = Field(..., description="Postgres DSN")
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    sentry_dsn: str = ""
    allowed_hosts: list[str] = ["localhost"]
    cors_origins: list[str] = ["http://localhost:5173"]

# settings.py
env = AppSettings()

DEBUG = env.debug
SECRET_KEY = env.secret_key.get_secret_value()
DATABASES = {"default": dj_database_url.parse(env.database_url)}
CACHES = {"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": env.redis_url}}
CELERY_BROKER_URL = env.celery_broker_url
```

**Key advantages over `os.environ`**:
- Type coercion (bools, lists, ints) happens at import time — errors surface on startup, not at runtime
- `SecretStr` prevents accidental logging of sensitive values
- `.env` file loading built-in (no `python-dotenv` needed)
- JSON Schema generation for documentation

See [environment-secrets-management.md](../devops/environment-secrets-management.md) for the broader secrets workflow.

## 2. Pydantic v2 Core API

The critical Pydantic v2 patterns used in Django projects:

```python
from pydantic import BaseModel, field_validator, model_validator, ConfigDict
from datetime import datetime

class OrderCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # replaces orm_mode

    product_id: int
    quantity: int
    note: str = ""

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v

    @model_validator(mode="after")
    def check_note_length(self) -> "OrderCreate":
        if self.quantity > 100 and not self.note:
            raise ValueError("bulk orders require a note")
        return self

# Ad-hoc validation without a model
from pydantic import TypeAdapter
adapter = TypeAdapter(list[int])
validated = adapter.validate_python(["1", "2", "3"])  # → [1, 2, 3]
```

`ConfigDict(from_attributes=True)` allows constructing Pydantic models directly from Django ORM instances (`OrderCreate.model_validate(order_obj)`), which is useful for serialization pipelines.

## 3. Celery Task Parameter Validation

Pydantic models as a validation gate at Celery task boundaries prevent garbage-in failures deep in worker code:

```python
from pydantic import BaseModel
from celery import shared_task

class InvoicePayload(BaseModel):
    order_id: int
    amount_cents: int
    currency: str = "USD"
    idempotency_key: str

@shared_task(bind=True, max_retries=3)
def process_invoice(self, payload_dict: dict):
    """Validate at the boundary, then work with typed data."""
    payload = InvoicePayload.model_validate(payload_dict)

    # payload.order_id, payload.amount_cents — typed and validated
    result = billing_service.charge(
        order_id=payload.order_id,
        amount=payload.amount_cents,
        currency=payload.currency,
        idempotency_key=payload.idempotency_key,
    )
    return result
```

The task signature stays JSON-serializable (Celery sends a `dict`), but validation happens immediately on the worker. Failed validation raises `ValidationError` — configure Sentry or structlog to capture these as distinct error types.

See [celery-advanced-patterns.md](celery-advanced-patterns.md) for idempotency and retry strategies.

## 4. Pydantic as DRF Serializer Alternative: django-ninja

`django-ninja` uses Pydantic models as the serialization/validation layer instead of DRF serializers, with automatic OpenAPI schema generation:

```python
from ninja import NinjaAPI, Schema

api = NinjaAPI()

class ProductOut(Schema):
    id: int
    name: str
    price: float
    in_stock: bool

class ProductIn(Schema):
    name: str
    price: float

@api.get("/products", response=list[ProductOut])
def list_products(request):
    return Product.objects.filter(active=True)

@api.post("/products", response=ProductOut)
def create_product(request, data: ProductIn):
    return Product.objects.create(**data.dict())
```

**django-ninja vs DRF**: ninja is leaner and faster (Pydantic v2 Rust core) but has a smaller ecosystem. DRF has richer browsable API, pagination, filtering, permissions, and third-party packages. For teams already invested in DRF, the better path is using `drf-spectacular` for OpenAPI (see [drf-spectacular.md](drf-spectacular.md)) and Pydantic for non-API validation.

## 5. Comparison: Pydantic vs Django Forms vs DRF Serializers

| Concern | Django Forms | DRF Serializers | Pydantic |
|---|---|---|---|
| Primary use | HTML form handling | API request/response | General-purpose validation |
| ORM integration | `ModelForm` | `ModelSerializer` | `from_attributes=True` |
| Nested validation | Limited | Nested serializers | Nested models |
| Performance | Adequate | Good | Fast (Rust core) |
| OpenAPI generation | No | Via drf-spectacular | Built-in JSON Schema |
| Async support | No | No | Yes |
| Best for | Server-rendered forms | REST APIs with DRF | Settings, Celery payloads, service boundaries |

**Practical guidance**: Use Django Forms for admin/HTML. Use DRF serializers for DRF API endpoints. Use Pydantic for settings, Celery task payloads, external service DTOs, and anywhere you need validation outside the request/response cycle.

## 6. Pydantic + Logfire Integration

Pydantic models integrate natively with Logfire for validation tracing:

```python
import logfire

logfire.instrument_pydantic()  # auto-traces all model validation

# Now every .model_validate() call emits a span with:
# - model name
# - validation success/failure
# - field-level error details on failure
```

See [logfire-observability.md](logfire-observability.md) for the full Logfire instrumentation setup.

## Sources

- Pydantic v2 docs: https://docs.pydantic.dev/latest/
- pydantic-settings docs: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- django-ninja docs: https://django-ninja.dev/
- drf-spectacular + Pydantic: https://drf-spectacular.readthedocs.io/
