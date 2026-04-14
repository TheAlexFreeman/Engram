# Repository Factory Patterns

This reference is derived from a full read of factory-related files currently in this
repo.

## Inventory Read

- `backend/accounts/tests/factories/__init__.py`
- `backend/accounts/tests/factories/accounts.py`
- `backend/accounts/tests/factories/invitations.py`
- `backend/accounts/tests/factories/memberships.py`
- `backend/accounts/tests/factories/users.py`
- `backend/base/tests/factories/__init__.py`
- `backend/base/tests/factories/core.py`
- `backend/base/tests/factories/helpers.py`
- `backend/base/tests/factories/testing_models.py`
- `backend/base/tests/factories/tests/__init__.py`
- `backend/base/tests/factories/tests/test_core_factories.py`
- `backend/base/tests/factories/typed_base.py`

## Core Patterns To Reuse

- Base classes:
- `BaseDjangoModelFactory[T]` provides typed return methods.
- `CoreFactory[T]` sets common `created`/`modified` faker behavior.
- Deterministic randomness:
- Shared `fake` and `random` come from `backend/base/tests/shared.py`.
- Seeding is coordinated through factory_boy random machinery.
- Factory defaults:
- Many factories use `class Meta: skip_postgeneration_save = True`.
- Relationship composition:
- `SubFactory` for direct relations.
- `@post_generation` for conditional relation creation and optional overrides.
- State bundles:
- Traits are used for lifecycle states (`sent`, `followed`, `expired`,
  `create_superuser`).
- Sentinel pattern:
- `UserFactory` uses sentinels to explicitly skip account/membership creation.

## Existing Faker Usage Patterns

- Frequent:
- `Faker("name")`
- `Faker("date_time_between", ...)`
- Password generation via `Faker("password", ...)`
- Combined patterns:
- `factory.Sequence` for uniqueness + `Faker` for realism.
- `LazyAttribute` for values derived from previously generated fields.

## Factory Helper Mapping

`backend/base/tests/factories/helpers.py` maps model classes to factory classes via
`get_factory(...)`. When adding a new commonly-used factory, update that mapping if
appropriate.
