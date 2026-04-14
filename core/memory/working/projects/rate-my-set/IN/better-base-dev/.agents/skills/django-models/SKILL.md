---
name: django-models
description: Create, update, and review Django models in this repository. Use for requests like "add a model", "update model fields", "change constraints", "queryset methods", or "Django model cleanup".
---

Use this skill when touching `backend/**/models/*.py`.

## Required Context

1. Read root `AGENTS.md` plus `backend/AGENTS.md`.
2. Read `references/repo-model-patterns.md`.
3. Read the specific model module(s) you are changing.

## Workflow

1. Define enums first when field choices are domain-significant.
2. Use a typed queryset (`CoreQuerySet[...]`) when query helpers are needed.
3. Prefer `CoreModel` for shared timestamps/behavior.
4. Add explicit DB constraints/indexes for invariants and common query paths.
5. Name constraints and indexes with this schema:
6. `{app_shorthand}_{model_shorthand}_{fields_involved}_{suffix}`.
7. Use app shorthand that is typically 3 characters.
8. Use model shorthand that is typically 2 to 4 characters (exceptions are allowed when
   clarity requires it).
9. Use suffixes consistently:
10. `ix`, `uix`, `brix`, `gin`, `gist`, `puix`, `fuix`, `fpuix`, `cc`.
11. Keep `related_name` and `related_query_name` explicit on relations.
12. Keep business-significant values explicit in ops/serializers, not implicit model
    defaults.
13. For optional relations, prefer `blank=True` + `null=True` without `default=None`
    unless intentional.
14. Add/update Django admin for the model.
15. Add/update factory for the model when relevant.
16. Generate migrations with `python manage.py makemigrations` only.

## Field Definition Ordering

Use explicit and stable keyword ordering for field declarations.

### Non-ForeignKey fields

1. Positional label first (for example `"Email"`), not gettext wrappers.
2. Field-identity arguments next (for example `max_length`, `choices`, `validators`).
3. Then, when present, keep this exact order:
4. `blank`, `null`, `default`, `editable`, `help_text`.
5. Remaining keyword arguments follow after that.

### ForeignKey fields

Use this order:

1. target model positional argument.
2. optional `to_field` positional/explicit argument (if needed).
3. `on_delete`.
4. `verbose_name`.
5. `related_name`.
6. `related_query_name`.
7. then remaining keyword arguments, with `blank`, `null`, `default`, `editable`,
   `help_text` kept in that sequence when present.

## Model Checklist

- Add or update `REPR_FIELDS`.
- Add `__str__` with useful debug text.
- Add dedicated tests for `repr(...)` behavior.
- Add dedicated tests for `str(...)` behavior.
- Add explicit labels / verbose names for all model fields.
- Prefer plain string labels instead of gettext wrappers for newly added fields.
- Add `help_text` for persisted JSON and token fields.
- Use deterministic constraint/index names with app/model prefixes.
- Add `CheckConstraint` coverage for `TextChoices` / `IntegerChoices` style fields.
- Keep imports module-scoped unless there is a concrete cycle/perf reason.

## Model Member Ordering

Keep model class members in this order.

Primary readability rule: keep all non-underscored members first, and place all
underscored private members at the bottom. Do not interleave private members between
public members.

### Class attributes and declarations

1. `REPR_FIELDS`.
2. Other upper-cased constants/finals.
3. `id` (explicit primary key field).
4. Remaining model fields.
5. `objects`.
6. Tracker attribute(s), if used.
7. `Meta`.

### Lifecycle and core hooks

1. `__str__`.
2. `clean`.
3. `save`.
4. `delete`.
5. Any additional class-level constants/finals not already placed above.

### Public computed members and helpers

1. `@cached_classproperty`.
2. `@classproperty`.
3. `@property`.
4. `@cached_property`.
5. `@staticmethod`.
6. `@classmethod`.
7. Regular methods.

### Private computed members and helpers

These always come last in the class body.

1. Underscored private `@cached_classproperty`.
2. Underscored private `@classproperty`.
3. Underscored private `@property`.
4. Underscored private `@cached_property`.
5. Underscored private static methods.
6. Underscored private class methods.
7. Underscored private regular methods.

## Validation

Run the smallest relevant set first:

```bash
source .venv/bin/activate
python manage.py makemigrations <app_name>
python manage.py check
pytest <targeted-tests>
mypy <touched-backend-paths>
```

## Output Expectations

Report:

- Model files changed.
- Migration files generated.
- Admin/factory/test updates.
- Checks run and checks skipped.
