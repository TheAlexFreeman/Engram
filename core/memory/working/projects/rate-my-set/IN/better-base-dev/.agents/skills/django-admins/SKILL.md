---
name: django-admins
description: Build or update Django admin classes, forms, and inlines in this repository. Use for requests like "add admin", "improve changelist", "readonly admin view", "admin action", or "admin search/filter".
---

Use this skill when touching `backend/**/admin/**/*.py`.

## Required Context

1. Read root `AGENTS.md` and `backend/AGENTS.md`.
2. Read `references/repo-admin-patterns.md`.
3. Read `backend/base/admin/core.py` before making admin changes.

## Workflow

1. Register model admins with `@admin.register(Model)`.
2. Inherit from `CoreModelAdmin` (and `auth_admin.UserAdmin` where required).
3. Keep class attributes in a consistent order so reviews are easy and predictable.
4. Use this preferred order:
5. `list_display`, `list_filter`, `list_select_related`, `search_fields`, `ordering`, `raw_id_fields`, `fieldsets`, `readonly_fields`, `inlines`, `actions`, then `can_add/can_view/can_change/can_delete`.
6. Set `list_select_related` aggressively for FK-heavy changelists.
7. Gate permissions with `can_add`, `can_view`, `can_change`, `can_delete`.
8. Use `@admin.display` for derived columns, ordering, and labels.
9. For JSON fields, expose prettified read-only displays using `prettify_json_as_html`.
10. Use `CoreInlineModelAdmin` for inlines when permission control is needed.

## Readonly Field Policy

- `readonly_fields` should be exhaustive.
- If a field is intentionally editable, include a commented-out line for it inside
  `readonly_fields` to make the editability decision explicit.
- Favor explicit over implicit behavior in every admin class.

## Display Method Policy

- Use `..._display` naming for computed/presentational admin methods.
- Keep `@admin.display` metadata explicit (description and ordering when applicable).
- For foreign keys, prefer `..._display` methods that render hyperlinks to related
  Django admin pages instead of plain text values.
- For read-only detail pages, avoid duplicate raw+display rows:
  - If a JSON field is read-only, show only the prettified `..._display` field in
    `fieldsets`.
  - For token/identifier fields with richer rendering, show only a dedicated display
    field in `fieldsets`.
- For token displays, prefer making the rendered token clickable to the model changelist
  with `?q=<full-token>` so QA/debug can pivot from detail/list to search quickly.
- It is fine for `readonly_fields` to remain exhaustive and include base fields, but
  `fieldsets` should control what is actually rendered in detail view.

### Concise Example

```python
@admin.display(description="Email", ordering="email")
def email_display(self, obj):
    text = Truncator(obj.email).chars(63)
    return format_html(
        '<span title="{}" style="display:inline-block;max-width:63ch;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{}</span>',
        obj.email,
        text,
    )

@admin.display(description="Account", ordering="account__name")
def account_display(self, obj):
    if not obj.account_id:
        return "-"
    return format_html(
        '<a href="{}">{}</a>',
        reverse("admin:accounts_account_change", args=[obj.account_id]),
        obj.account.name,
    )

fieldsets = (
    (None, {"fields": ("email_display", "account_display", "metadata_display")}),
)
```

## Admin Checklist

- Changelist should load without N+1 issues in obvious relation fields.
- Detail page should expose critical debugging data read-only when mutable edits are
  unsafe.
- Search fields should include common identifiers (id, token, email/name, reference
  keys).
- If actions are added, enforce safe batch limits and user feedback messages.
- Ensure `readonly_fields` is exhaustive, with intentionally editable fields commented
  out in that list.
- Ensure `..._display` methods are wired consistently in `list_display`, `fieldsets`,
  and `readonly_fields`.

## Validation

```bash
source .venv/bin/activate
pytest backend/*/tests/admin -q
python manage.py check
mypy <touched-backend-paths>
```

If no admin tests exist yet for the touched model, add smoke tests:

- changelist load
- detail page load
- regular search load

## Output Expectations

Report:

- Admin files changed.
- Permission posture (`can_*`) chosen and why.
- Any JSON display helpers/actions/inlines added.
- Checks run and skipped.
