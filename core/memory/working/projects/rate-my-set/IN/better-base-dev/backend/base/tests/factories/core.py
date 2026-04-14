from __future__ import annotations

from datetime import UTC

from factory import Faker, LazyAttribute

from backend.base.tests.shared import fake, random

from .typed_base import BaseDjangoModelFactory, T


class CoreFactory(BaseDjangoModelFactory[T]):
    # Pick a `datetime` between two years ago and the current datetime.
    created = Faker("date_time_between", start_date="-2y", end_date="now", tzinfo=UTC)

    # ~75% of the time: Pick a `datetime` between `created` and the current datetime.
    # ~25% of the time: Use the exact same value as `created`.
    modified = LazyAttribute(
        lambda o: (
            fake.date_time_between(start_date=o.created, end_date="now", tzinfo=UTC)
            if random.choice(range(4))
            else o.created
        )
    )

    class Meta:
        abstract = True
