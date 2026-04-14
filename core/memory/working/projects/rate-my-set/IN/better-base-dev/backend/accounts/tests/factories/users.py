from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING, Any, Final

import factory
from factory import Faker, LazyAttribute, Trait, post_generation
from typing_extensions import Sentinel

from backend.accounts.models import User
from backend.accounts.types.roles import Role
from backend.base.tests.factories.core import CoreFactory
from backend.base.tests.shared import fake, random

from .accounts import AccountFactory
from .memberships import MembershipFactory

if TYPE_CHECKING:
    from backend.accounts.models import Account, Membership

SKIP_ACCOUNT_CREATION: Final[Sentinel] = Sentinel("SKIP_ACCOUNT_CREATION")
SKIP_MEMBERSHIP_CREATION: Final[Sentinel] = Sentinel("SKIP_MEMBERSHIP_CREATION")


class _FactoryUserType(User):
    _FACTORY_IS_TYPE_SUBCLASS_HELPER_FOR_ = User

    # Indicate that these types are present, and assume they're there. If they're not,
    # tests will fail anyway, and it makes working with the type checker(s) a lot
    # easier.
    _account_: Account
    _account_factory_built_: Account
    _account_factory_created_: Account
    _membership_factory_built_: Membership
    _membership_factory_created_: Membership

    class Meta:
        abstract = True


class UserFactory(CoreFactory[_FactoryUserType]):
    email = factory.Sequence(lambda n: f"email{n + 1}@tests.betterbase.com")
    email_is_verified = True
    # Pick a `datetime` between two years ago and the current datetime.
    email_verified_as_of = Faker(
        "date_time_between", start_date="-2y", end_date="now", tzinfo=UTC
    )

    name = Faker("name")

    is_active = True

    is_staff = False
    is_superuser = False

    # Pick a `datetime` between two years ago and the current datetime.
    date_joined = Faker(
        "date_time_between", start_date="-2y", end_date="now", tzinfo=UTC
    )
    # ~50% of the time: Pick a `datetime` between `date_joined` and the current datetime.
    # ~25% of the time: Use the exact same value as `date_joined`.
    # ~25% of the time: Use `None` as the value.
    last_login = LazyAttribute(
        lambda o: (
            fake.date_time_between(start_date=o.date_joined, end_date="now", tzinfo=UTC)
            if random.choice(range(2))
            else (o.date_joined if random.choice(range(2)) else None)
        )
    )

    # Use the exact same value as `date_joined` in the `User` case.
    created = LazyAttribute(lambda o: o.date_joined)  # type: ignore[assignment]
    # ~75% of the time: Pick a `datetime` between `date_joined` and the current
    # datetime.
    # ~25% of the time: Use the exact same value as `date_joined`.
    modified = LazyAttribute(
        lambda o: (
            fake.date_time_between(start_date=o.date_joined, end_date="now", tzinfo=UTC)
            if random.choice(range(4))
            else o.date_joined
        )
    )

    @post_generation
    def password(self: _FactoryUserType, create: bool, extracted: Any, **kwargs: Any):
        password = (
            extracted
            if extracted
            else Faker(
                "password",
                length=42,
                special_chars=True,
                digits=True,
                upper_case=True,
                lower_case=True,
            ).evaluate(None, None, extra={"locale": None})
        )
        self.set_password(password)
        if create:
            self.save()

    @post_generation
    def account(self: _FactoryUserType, create: bool, extracted: Any, **kwargs: Any):
        if extracted is None and extracted != SKIP_ACCOUNT_CREATION:
            if create:
                self._account_factory_created_ = AccountFactory.create(**kwargs)
                self._account_ = self._account_factory_created_
            else:
                self._account_factory_built_ = AccountFactory.build(**kwargs)
                self._account_ = self._account_factory_built_
        else:
            self._account_ = extracted

    @post_generation
    def membership(self: _FactoryUserType, create: bool, extracted: Any, **kwargs: Any):
        if extracted is None and extracted != SKIP_MEMBERSHIP_CREATION:
            kwargs.setdefault("role", Role.OWNER)
            kwargs.setdefault("created", self.created)

            account_from_here = self._account_
            if (
                account_from_here is not None
                and account_from_here != SKIP_ACCOUNT_CREATION
            ):
                kwargs.setdefault("account", account_from_here)

            if create:
                self._membership_factory_created_ = MembershipFactory.create(
                    user=self, **kwargs
                )
            else:
                self._membership_factory_built_ = MembershipFactory.build(
                    user=self, **kwargs
                )

    class Meta:
        skip_postgeneration_save = True

    class Params:
        create_superuser = Trait(
            is_staff=True,
            is_superuser=True,
        )
        email_is_not_verified = Trait(
            email_is_verified=False,
            email_verified_as_of=None,
        )
