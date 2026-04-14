# Factory Boy Reference (Practical)

Primary docs:

- https://factoryboy.readthedocs.io/
- https://factoryboy.readthedocs.io/en/stable/reference.html
- https://factoryboy.readthedocs.io/en/stable/orms.html
- https://factoryboy.readthedocs.io/en/stable/recipes.html

## Key Declarations

- `factory.Sequence(...)`
- Use for deterministic uniqueness.
- Example: `email = factory.Sequence(lambda n: f"user{n}@tests.better-base.local")`

- `factory.LazyFunction(...)`
- Use when value is computed without object context.
- Example: `expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=3))`

- `factory.LazyAttribute(...)`
- Use when value depends on previously-built attributes.
- Example: `modified = factory.LazyAttribute(lambda o: fake.date_time_between(start_date=o.created, end_date="now"))`

- `factory.SubFactory(...)`
- Use for related model construction.
- Example: `account = factory.SubFactory(AccountFactory)`

- `factory.SelfAttribute(...)`
- Copy or derive from another attribute path.
- Example: `shipped_to = factory.SelfAttribute("..billing_address")`

- `factory.Trait(...)`
- Named toggle-able state bundles.
- Example:
  `class Params: expired = factory.Trait(expires_at=factory.Faker("date_time_between", start_date="-90d", end_date="-30d"))`

- `@factory.post_generation`
- Hook for M2M or optional relation wiring after base build/create.
- Example: attach or create `invited_by`/`user` depending on extracted args.

## Django ORM Notes

- `DjangoModelFactory` creates persistent objects with `.create()` and non-persistent
  objects with `.build()`.
- Use explicit post-generation save behavior (`skip_postgeneration_save`) to avoid
  accidental extra writes.
- Keep factory side effects obvious and limited.

## Recommended Pattern In This Repo

- Extend `CoreFactory[T]`.
- Prefer readable traits over deep conditional logic in one hook.
- Keep relation creation options explicit (flags, sentinels, extracted args).
