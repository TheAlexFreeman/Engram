---
source: external-research
origin_session: core/memory/activity/2026/03/18/chat-001
created: 2026-03-18
last_verified: 2026-03-20
trust: medium
related:
  - memory/knowledge/software-engineering/django/django-async.md
  - memory/knowledge/software-engineering/django/django-database-pooling.md
  - memory/knowledge/software-engineering/django/django-orm-postgres.md
  - memory/knowledge/software-engineering/django/django-production-stack.md
  - memory/knowledge/software-engineering/django/django-security.md
---

# Django 6.0 — What's New

Base Django 6.0 released on December 3, 2025. As of 2026-03-18, the 6.0 patch line has reached 6.0.3 (released March 3, 2026). Django 6.0 supports Python 3.12, 3.13, and 3.14.

This file focuses on what changed in the 6.0 line and what matters most for Alex's stack, rather than treating every long-running migration concern as if it were a brand-new 6.0 feature.

## Four headline features

### 1. Template Partials
Named, reusable template fragments within a single template file. Eliminates the need to split small components into separate files.

```django
{% partialdef user-card %}
  <div class="card">{{ user.name }}</div>
{% endpartialdef user-card %}

{# render it: #}
{% partial user-card %}

{# inline option: define and render in place #}
{% partialdef hero inline %}
  <h1>{{ title }}</h1>
{% endpartialdef %}
```

Cross-file reference via `template_name#partial_name` syntax works with `get_template()`, `render()`, `{% include %}`, and other template-loading tools.

Partials receive the current context, so they work naturally inside loops. Use the `with` tag to adjust context as needed.

**Relevance for React stack:** Mostly relevant for server-rendered pages or HTMX workflows. Less directly relevant for SPA setups, but useful for admin UIs or hybrid pages.

### 2. Background Tasks (`django.tasks`)
A standardized API for defining and enqueueing background work. See `django-tasks-framework.md` for full detail — this is the most architecturally significant feature for teams using Celery.

### 3. Content Security Policy (CSP)
Built-in CSP support via `django.middleware.csp.ContentSecurityPolicyMiddleware`. Previously required the third-party `django-csp` (Mozilla) package.

```python
MIDDLEWARE = [
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    ...
]

from django.utils.csp import CSP

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],  # enables per-request nonces
    "style-src": [CSP.SELF],
}

# Report-only mode for testing without enforcement:
SECURE_CSP_REPORT_ONLY = {
    "default-src": [CSP.SELF],
}
```

Add the `csp()` context processor to TEMPLATES to make `csp_nonce` available in templates. The middleware generates a unique nonce per request automatically.

Existing `django-csp` users will need to migrate; the APIs are similar but not identical.

### 4. Modernized Email API
Django now uses Python's modern `email.message.EmailMessage` (not the legacy Compat32 MIME classes). Cleaner, Unicode-friendly, and consistent with Python 3.6+ email API.

```python
# Before (still works in 6.0, but deprecated):
from email.mime.text import MIMEText
msg.attach(MIMEText("body"))

# After (modern API):
from email.message import MIMEPart
part = MIMEPart()
part.set_content("body")
msg.attach(part)
```

`EmailMessage.message()` now returns `email.message.EmailMessage` (not `SafeMIMEText`/`SafeMIMEMultipart`, which are deprecated). The `BadHeaderError` exception is also deprecated (Python's modern email raises `ValueError` for bad headers).

---

## ORM and database changes

- **`DEFAULT_AUTO_FIELD` default is `BigAutoField`** in the 6.0 line. This is most important when auditing older projects that still depend on implicit defaults.
  - **Watch out:** changing PK defaults in an existing project is a migration concern, not a casual settings cleanup.
- **`RETURNING` clause optimization** — `GeneratedField` and expression-assigned fields are now refreshed via a single `RETURNING` query after `save()` on SQLite, PostgreSQL, and Oracle. Eliminates a separate `SELECT` after insert/update.
- **`StringAgg` aggregate** now available on all backends (previously PostgreSQL-only).
- **`AnyValue` aggregate** — returns an arbitrary non-null value from a group. Supported on SQLite, MySQL, Oracle, PostgreSQL 16+.
- **`QuerySet.raw()` supports `CompositePrimaryKey` models.**
- **Subqueries with `CompositePrimaryKey`** can now be the target of lookups beyond `__in` (e.g., `__exact`).
- **JSON field** now supports negative array indexing on SQLite.
- **ORM expression `params`** must now be tuples, not lists. Breaking for custom expressions.
- **`return_insert_columns` renamed to `returning_columns`** in the Database API.
- **PostgreSQL `CreateExtension` and related operations** now support an optional `hints` parameter for database-router hints.
- **`Lexeme`** for PostgreSQL full-text search gives safer composition of search terms, including prefix matching and weighting.
- **`django.contrib.postgres` fields, indexes, and constraints** now include system checks to ensure the app is installed correctly.
- **`BaseDatabaseSchemaEditor`** no longer uses `CASCADE` when dropping a column (more conservative and correct behavior).

---

## Async improvements

- `AsyncPaginator` and `AsyncPage` are new in 6.0.
- Async support continues to get broader, but 6.0 should still be read as "more capable async Django," not "everything is transparently async now."
- For mixed sync/async stacks, the operational question remains where async actually improves throughput versus where the ORM, cache, or task boundary is still doing the real work.

---

## Deprecations introduced in 6.0

- `ADMINS` / `MANAGERS` as list of `(name, address)` tuples → change to list of email address strings.
- `OrderableAggMixin` (PostgreSQL) → use the `order_by` attribute on `Aggregate` class.
- `orphans` argument ≥ `per_page` in `Paginator` / `AsyncPaginator` is deprecated.
- Percent sign in column alias or annotation name is deprecated.
- `EmailMessage.attach()` with legacy `MIMEBase` objects → use `MIMEPart`.
- `SafeMIMEText`, `SafeMIMEMultipart`, `BadHeaderError` → deprecated.
- Default protocol in `urlize` / `urlizetrunc` will change from HTTP to HTTPS in Django 7.0; opt in now via `URLIZE_ASSUME_HTTPS = True`.

---

## Features removed in 6.0 (end of deprecation cycle from 5.x)

- Positional arguments to `BaseConstraint` removed.
- See Django 5.0/5.1/5.2 deprecation notes for the complete list.

---

## Patch-line notes

- Django 6.0.1 shipped on January 6, 2026 and fixed several regressions plus a PostgreSQL `bulk_create()` data-loss bug first introduced in Django 5.2.
- Django 6.0.3 shipped on March 3, 2026 and included security fixes, including a moderate-severity `URLField` denial-of-service issue on Windows and a low-severity file-permission issue affecting file-based storage/cache creation.

## Upgrade notes

- Run with `-Wall` on Django 5.2 first to surface deprecations before upgrading.
- Audit any custom ORM expressions that return `params` as lists.
- If using `django-csp`, plan migration to built-in CSP.
- If using `SafeMIMEText`/`SafeMIMEMultipart` directly, switch to Python's `email.message` API.
- Treat PK default changes and large-schema migrations as rollout work, not just version-bump work.

## Sources

- Django 6.0 release notes: https://docs.djangoproject.com/en/6.0/releases/6.0/
- Django 6.0.1 release notes: https://docs.djangoproject.com/en/6.0/releases/6.0.1/
- Django 6.0.3 release notes: https://docs.djangoproject.com/en/6.0/releases/6.0.3/

Last updated: 2026-03-18
