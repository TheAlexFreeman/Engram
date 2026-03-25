---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related:
  - django-security.md
  - django-migrations-advanced.md
---

# DRF API contracts, pytest, and django-perf-rec

For a Django team shipping APIs through DRF, the useful testing stack is layered: DRF defines the transport and schema boundary, `pytest-django` controls how Django is booted and how database access is isolated, and `django-perf-rec` can snapshot query/cache behavior for high-value endpoints. The main trap is to treat all three as doing the same job. They do not. DRF helps you test the API interface, `pytest-django` helps you test Django correctly and quickly, and `django-perf-rec` helps you freeze performance-sensitive behavior into reviewable records.

## DRF contract layer

### Built-in OpenAPI schemas are deprecated

DRF's schema docs now explicitly mark the built-in OpenAPI generation support as deprecated and recommend `drf-spectacular` as the full replacement. The built-in tools still exist, but the direction is clear: treat schema generation as a real contract layer and avoid building new long-term tooling around DRF's deprecated built-in schema stack.

Short-term built-in options still documented by DRF:

- `./manage.py generateschema --file openapi-schema.yml`
- `get_schema_view(...)` for dynamic schema serving
- `AutoSchema` / `SchemaGenerator` customization

That is still useful if a project already depends on DRF's built-ins, but it should be read as a maintenance path, not the preferred future path.

### What should stay contract-stable

For a frontend-heavy team, the API contract usually lives in:

- serializer request/response shapes
- pagination model
- filter/search parameter names
- versioning scheme
- error envelope
- OpenAPI schema output

That means contract regressions are not only "status code changed" bugs. A changed cursor format, renamed filter param, extra query explosion, or a schema drift can all be real API regressions.

## DRF testing helpers

### `APIClient`

This is the default high-leverage tool for most DRF tests.

- supports `.get()`, `.post()`, `.put()`, `.patch()`, `.delete()`, `.options()`
- supports `format="json"`
- supports `.login()` for session-authenticated tests
- supports `.credentials(...)` for header-based auth
- supports `.force_authenticate(...)` when you want to bypass auth mechanics and focus on view behavior

`force_authenticate()` is a useful shortcut, but it intentionally skips the real auth path. That makes it good for view logic tests and weaker for end-to-end auth contract tests.

### CSRF behavior in tests

DRF's testing docs note that CSRF validation is not applied by default when using `APIClient`. If you need to verify a real session-auth + CSRF flow, create the client with `enforce_csrf_checks=True`.

### `RequestsClient`

`RequestsClient` is stricter than `APIClient` because it works through the service interface instead of letting you mix direct ORM inspection into the same test body. Current DRF docs also clarify a subtle point: it still runs in-process and does not perform real network I/O. It is not a staging/prod HTTP client by itself.

That makes it useful when you want tests to feel more like consumer-level API interactions without leaving the test process.

### `APIRequestFactory`

Useful for view-level testing, but DRF warns that responses returned this way are not rendered yet. Call `response.render()` before asserting against `response.content`.

### Test-request defaults

DRF documents `TEST_REQUEST_DEFAULT_FORMAT`. Setting it to `"json"` can remove repetitive `format="json"` noise across the test suite.

## pytest-django fundamentals

### Database access is explicit by default

`pytest-django` intentionally blocks DB access unless requested. The normal path is `@pytest.mark.django_db`.

Important distinctions from the docs:

- `pytest.mark.django_db` gives transaction-wrapped DB access similar to Django `TestCase`
- `transaction=True` moves behavior closer to `TransactionTestCase`
- fixtures that need DB access themselves should explicitly request `db` or `transactional_db`
- `django_db_blocker` exists, but the docs warn that it does not manage transactions or automatic restore; it is lower-level than most tests need

This is a good match for API-heavy codebases because it makes DB use visible instead of accidental.

### Reusing the test DB

`pytest-django` explicitly documents this workflow:

- keep `--reuse-db` in default test options
- use `--create-db` when the schema changes
- optionally use `--no-migrations` for faster local setup when that tradeoff makes sense

That is usually the fastest practical baseline for a medium-to-large Django app.

### Parallel tests

When using `pytest-xdist`, `pytest-django` creates separate test databases per worker process. That matters for API suites because it keeps workers isolated without requiring the team to hand-roll DB naming rules.

### Query assertions already exist

Before reaching for `django-perf-rec`, note that `pytest-django` already provides:

- `django_assert_num_queries`
- `django_assert_max_num_queries`

These are ideal for tight, deliberately small assertions. `django-perf-rec` is better when you want a fuller snapshot of query/cache behavior rather than one numeric ceiling.

## django-perf-rec

### Current status

As of PyPI release `4.31.0` on September 18, 2025, `django-perf-rec` supports Django 4.2 through 6.0 and Python 3.9 through 3.14. The package page also notes that, as of August 1, 2025, it is in maintenance mode and that the author now recommends `inline-snapshot-django` as a faster and more convenient alternative.

That does not make `django-perf-rec` unusable. It means teams should treat it as a stable maintenance tool, not an actively evolving ecosystem bet.

### What it does well

`django-perf-rec` records performance behavior into YAML files next to tests. It fingerprints SQL and cache operations so noisy values like IDs and some changing details are normalized away.

This is stronger than `assertNumQueries` when:

- the exact query mix matters
- cache activity matters too
- you want the review diff to show what changed
- a single integer query count would be too coarse

### Important settings

The package documents:

- `HIDE_COLUMNS=True` by default, which collapses selected column lists
- `MODE="once"` by default
- `MODE="none"` as a good CI mode if you want missing perf records to fail the build
- `MODE="overwrite"` for silent regeneration

That suggests a good discipline:

- permissive mode locally when authoring
- stricter mode in CI once records are established

### Pytest usage model

The docs explicitly mention using `record()` from within a pytest fixture so that it can be applied systematically.

Minimal example pattern:

```python
import django_perf_rec
import pytest


@pytest.fixture
def perf_recorder():
    with django_perf_rec.record():
        yield


@pytest.mark.django_db
def test_order_list_endpoint(api_client, perf_recorder):
    response = api_client.get("/api/orders/")
    assert response.status_code == 200
```

The more useful real-world pattern is to apply it selectively to endpoints, serializers, or service-layer calls that are both performance-sensitive and relatively stable.

## Recommended testing split for this stack

For a DRF + pytest + `django-perf-rec` team, the clean split is:

- use `APIClient` for most API behavior tests
- use `RequestsClient` when you want stricter interface-only tests
- use `pytest.mark.django_db`, `db`, and `transactional_db` intentionally
- use `django_assert_num_queries` for tight local query budgets
- use `django-perf-rec` for high-value performance snapshots on endpoints where query shape and cache behavior matter over time

That keeps the suite readable while still protecting the parts of the API that tend to regress silently.

## Related files

- [django-react-drf.md](django-react-drf.md)
- [django-production-stack.md](django-production-stack.md)
- [django-orm-postgres.md](django-orm-postgres.md)

## Sources

- DRF testing docs: https://www.django-rest-framework.org/api-guide/testing/
- DRF schemas docs: https://www.django-rest-framework.org/api-guide/schemas/
- DRF versioning docs: https://www.django-rest-framework.org/api-guide/versioning/
- pytest-django docs index: https://pytest-django.readthedocs.io/en/latest/
- pytest-django database docs: https://pytest-django.readthedocs.io/en/latest/database.html
- pytest-django helpers docs: https://pytest-django.readthedocs.io/en/stable/helpers.html
- django-perf-rec PyPI page: https://pypi.org/project/django-perf-rec/

Last updated: 2026-03-18
