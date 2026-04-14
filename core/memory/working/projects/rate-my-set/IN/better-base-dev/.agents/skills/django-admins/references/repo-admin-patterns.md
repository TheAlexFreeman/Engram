# Repository Django Admin Patterns

This reference is derived from a full read of the admin-related files currently in this
repo.

## Inventory Read

- `backend/accounts/admin/__init__.py`
- `backend/accounts/admin/accounts.py`
- `backend/accounts/admin/forms/__init__.py`
- `backend/accounts/admin/forms/users.py`
- `backend/accounts/admin/inlines/__init__.py`
- `backend/accounts/admin/inlines/memberships.py`
- `backend/accounts/admin/invitations.py`
- `backend/accounts/admin/memberships.py`
- `backend/accounts/admin/user_app_states.py`
- `backend/accounts/admin/users.py`
- `backend/accounts/tests/admin/__init__.py`
- `backend/accounts/tests/admin/test_users.py`
- `backend/auth/admin/__init__.py`
- `backend/base/admin/__init__.py`
- `backend/base/admin/core.py`
- `backend/utils/admin/__init__.py`
- `backend/utils/admin/formsets.py`

## Core Base Classes

- `CoreModelAdmin`:
- Adds DjangoQL search mixin.
- Adds JSON editor widget override for `models.JSONField`.
- Adds `can_add/can_view/can_change/can_delete` switches used throughout the repo.
- Provides `prettify_json_as_html` helper.
- `CoreInlineModelAdmin`:
- Adds inline permission switches (`can_*_inline`).
- Used with tabular inlines where constraints/read-only UX matter.

## Common Admin Shape

- `list_display` shows IDs + key business dimensions + timestamps.
- `list_filter` includes timestamps and enum/status fields.
- `search_fields` includes user/account identifiers, textual keys, and tokens.
- `readonly_fields` is usually broad for immutable/audit-heavy data.
- Many admins are read-only (`can_change=False`) except where operational edits are
  intentional.

## Owner-Preferred Attribute Order

Keep class attributes in this order whenever possible:

1. `list_display`
2. `list_filter`
3. `list_select_related`
4. `search_fields`
5. `ordering`
6. `raw_id_fields`
7. `fieldsets`
8. `readonly_fields`
9. `inlines`
10. `actions`
11. `can_add`, `can_view`, `can_change`, `can_delete`

## Owner-Preferred Readonly Policy

- `readonly_fields` should be exhaustive.
- If a field is intentionally editable, keep it commented out in `readonly_fields` so
  that editability is explicit in review.
- The goal is explicit over implicit behavior.

## JSON + HTML Display Patterns

- JSON snapshots are rendered in read-only display methods using `prettify_json_as_html`.
- Rich text fields can be displayed with `format_html` or `mark_safe` in dedicated
  `@admin.display` methods when the source is trusted and already sanitized.

## Owner-Preferred Display Method Pattern

- Name presentational methods with `..._display`.
- Wire `..._display` methods explicitly into list/detail configurations.
- Keep the base fields present in `readonly_fields` even when display wrappers are used.

## Inline + Form Patterns

- Inlines may cap row counts with `BaseInlineFormSetWithLimit`.
- Admin forms can orchestrate multi-model creation flows (for example user/account/
  membership setup).

## Test Expectations

Admin test coverage currently exists in `backend/accounts/tests/admin/test_users.py`.
For new admins, add smoke tests for:

- changelist load
- detail page load
- basic search load
