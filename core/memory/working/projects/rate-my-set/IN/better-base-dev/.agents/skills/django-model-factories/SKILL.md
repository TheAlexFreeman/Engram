---
name: django-model-factories
description: Create and update Django test factories using Factory Boy and Faker in this repository. Use for requests like "add factory", "update factory traits", "faker values", "post_generation", or "factory cleanup".
---

Use this skill when touching `backend/**/tests/factories/*.py`.

## Required Context

1. Read root `AGENTS.md` and `backend/AGENTS.md`.
2. Read these references:

- `references/repo-factory-patterns.md`
- `references/factory-boy-reference.md`
- `references/faker-provider-catalog.md`

## Workflow

1. Start from `CoreFactory[...]` unless there is a strong reason not to.
2. Use `factory.Sequence` for unique fields (email, token-like values).
3. Use `factory.Faker` for human-readable/test-realistic values.
4. Use `LazyAttribute` / `LazyFunction` for dependent or probabilistic values.
5. Use `SubFactory` for required relations.
6. Use `Trait` for common state bundles.
7. Use `@post_generation` for optional relation wiring and side effects.
8. Keep `class Meta: skip_postgeneration_save = True` unless behavior requires
   otherwise.
9. Keep randomness deterministic with shared helpers from `backend/base/tests/shared.py`
   when needed.

## Factory Boy + Faker Rules

- Prefer explicit, readable trait names (`expired`, `followed`, `create_superuser`).
- Avoid hidden implicit DB writes in post-generation hooks unless clearly documented.
- If relation creation is optional, use explicit sentinels/flags (existing repo
  pattern).
- Add/update helper mapping (`get_factory`) if introducing a new factory type.

## Validation

```bash
source .venv/bin/activate
pytest backend/base/tests/factories/tests -q
pytest <touched-tests> -q
mypy <touched-backend-paths>
```

## Exhaustive Faker Method Discovery

To list all faker methods available in the installed version, run:

```bash
source .venv/bin/activate
python .agents/skills/django-model-factories/scripts/list_faker_methods.py --format markdown
```

This is version/locale-aware and should be preferred when selecting less common faker
methods.

## Output Expectations

Report:

- Factories created/updated.
- Traits/post-generation hooks added/changed.
- Faker methods selected (and why).
- Checks run and skipped.
