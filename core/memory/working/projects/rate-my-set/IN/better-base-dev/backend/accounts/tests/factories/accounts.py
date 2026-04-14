from __future__ import annotations

from functools import partial

import factory

from backend.accounts.models import Account
from backend.accounts.models.accounts import AccountType
from backend.base.tests.factories.core import CoreFactory
from backend.base.tests.shared import fake, random


class AccountFactory(CoreFactory[Account]):
    account_type = factory.LazyFunction(partial(random.choice, [*AccountType]))

    # ~75% of the time: Use a `company` from Faker.
    # ~25% of the time: Don't populate the `name` field.
    name = factory.LazyFunction(
        lambda: fake.company() if random.choice(range(4)) else ""
    )

    class Meta:
        skip_postgeneration_save = True
