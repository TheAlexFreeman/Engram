# Repository Django Model Patterns

This reference is derived from a full read of the model-related files currently in this
repo.

## Inventory Read

- `backend/accounts/models/__init__.py`
- `backend/accounts/models/accounts.py`
- `backend/accounts/models/invitations.py`
- `backend/accounts/models/memberships.py`
- `backend/accounts/models/users.py`
- `backend/accounts/models/users_app_states.py`
- `backend/accounts/tests/models/__init__.py`
- `backend/accounts/tests/models/test_accounts.py`
- `backend/auth/models/__init__.py`
- `backend/auth/models/email_changes.py`
- `backend/base/models/__init__.py`
- `backend/base/models/core.py`
- `backend/base/models/testing_models.py`

## Cross-Cutting Conventions

- Base classes:
- Most models inherit from `CoreModel`.
- Query helpers commonly live in `CoreQuerySet[...]` subclasses and are attached via
  `.as_manager()`.
- Choice fields:
- Enums are frequently `models.TextChoices` classes near the top of each file.
- Constraints:
- DB-level `CheckConstraint` and `UniqueConstraint` are heavily used for invariants.
- Constraint names are short, explicit, and prefixed by app/model abbreviations.
- Indexes:
- Indexes are explicit and named.
- BRIN/BTree and partial indexes are used where query patterns justify them.
- Relations:
- `related_name` and `related_query_name` are explicit.
- Optional relations usually use `blank=True, null=True`.
- Defaults:
- Defaults are used for intentional fallback state (for example counters or JSON
  snapshots).
- For business-significant fields, prefer explicit assignment in ops/callers.
- Validation:
- Some models include `clean()`/field clean helpers plus DB checks.
- Token-like UUID fields may enforce UUIDv7 shape both at clean-time and DB constraint
  level.

## Owner-Preferred Naming Standard

Use this naming shape for constraints and indexes:

- `{app_shorthand}_{model_shorthand}_{fields_involved}_{suffix}`
- App shorthand is usually 3 characters.
- Model shorthand is usually 2 to 4 characters (allow exceptions for clarity).

Common suffixes:

- `ix`: index
- `uix`: unique index/constraint
- `brix`: BRIN index
- `gin`: GIN index
- `gist`: GiST index
- `puix`: partial unique index/constraint
- `fuix`: functional unique index/constraint
- `fpuix`: functional partial unique index/constraint
- `cc`: check constraint

## Owner-Preferred Field Definition Order

### Non-ForeignKey fields

1. Positional label first.
2. Field-identity arguments (`max_length`, `choices`, validators, etc.).
3. Then, if present, this exact sequence:
4. `blank`, `null`, `default`, `editable`, `help_text`.
5. Remaining keyword args after those.

### ForeignKey fields

Use this argument order:

1. target model positional argument.
2. optional `to_field` (if needed).
3. `on_delete`.
4. `verbose_name`.
5. `related_name`.
6. `related_query_name`.
7. remaining args, keeping `blank`, `null`, `default`, `editable`, `help_text` in
   order when present.

## Choices + Check Constraints

- When using `TextChoices` / `IntegerChoices` style model choices, add DB-level check
  constraints to enforce valid values.

## Labels and gettext

- Use explicit labels / verbose names on all fields.
- For new model field labels, prefer plain strings rather than gettext wrappers.

## Patterns To Mirror

- Add helpful `help_text` for state snapshots and token fields.
- Keep `Meta.verbose_name` and `Meta.verbose_name_plural` set.
- Add a focused `__str__` useful in admin/logging contexts.
- Keep constraints readable and directly tied to domain invariants.
- Keep queryset methods chainable and explicit about prefetch/select behavior.

## Migration Rule

Never handwrite migrations. Always regenerate from model changes:

```bash
source .venv/bin/activate
python manage.py makemigrations <app_name>
```
