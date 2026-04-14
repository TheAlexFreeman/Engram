from __future__ import annotations

from datetime import UTC, timedelta
from secrets import token_urlsafe
from typing import Any

import factory
from django.utils import timezone
from factory import Faker, Trait, post_generation

from backend.accounts.models import Invitation, User
from backend.accounts.types.invitations import DeliveryMethod
from backend.accounts.types.roles import Role
from backend.base.tests.factories.core import CoreFactory

from .users import UserFactory


class InvitationFactory(CoreFactory[Invitation]):
    # The account should be provided by the caller.
    account = None  # type: ignore[var-annotated]

    email = factory.Sequence(lambda n: f"invited-email{n + 1}@tests.betterbase.com")
    name = Faker("name")

    role = Role.MEMBER

    user = None  # type: ignore[var-annotated]
    accepted_at = None  # type: ignore[var-annotated]

    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=3))

    # This `secret_token` is for factory instances for the tests and guarantees
    # uniqueness by using a sequence. The `secret_token` on Non-test `Invitation`s won't
    # use the same logic and may look different and/or have a lot more characters, etc.
    secret_token = factory.Sequence(lambda n: f"{n}-{token_urlsafe(16)[:16]}")

    delivery_method = DeliveryMethod.EMAIL
    last_sent_at = None  # type: ignore[var-annotated]
    num_times_sent = 0
    delivery_data = None  # type: ignore[var-annotated]

    first_followed_at = None  # type: ignore[var-annotated]
    last_followed_at = None  # type: ignore[var-annotated]
    num_times_followed = 0

    @post_generation
    def set_invited_by(self, create: bool, extracted: Any, **kwargs: Any):
        if extracted is False:
            self.invited_by = None
        elif extracted is not None and isinstance(extracted, User):
            self.invited_by = extracted
        else:
            user_factory_kwargs: dict[str, Any] = {
                **kwargs,
                **{
                    "membership__role": Role.OWNER,
                },
            }
            if self.account is not None:
                user_factory_kwargs["account"] = self.account
            elif self.user is not None:
                user_factory_kwargs["account"] = list(self.user.active_memberships)[
                    0
                ].account

            invited_by: User
            if create:
                invited_by = UserFactory.create(**user_factory_kwargs)
            else:
                invited_by = UserFactory.build(**user_factory_kwargs)

            self.invited_by = invited_by

        if create and extracted is not False:
            self.save()  # type: ignore[attr-defined]

    @post_generation
    def accepted(self, create: bool, extracted: Any, **kwargs: Any):
        # Option 1: Just pass `accepted=True` to the factory.
        if extracted is True:
            user_factory_kwargs: dict[str, Any] = {
                "email": self.email,
                "name": (self.name or ""),
                "membership__role": self.role,
            }
            if self.account is not None:
                user_factory_kwargs["account"] = self.account
            elif self.invited_by is not None:
                user_factory_kwargs["account"] = self.invited_by.account

            user: User
            if create:
                user = UserFactory.create(**user_factory_kwargs)
            else:
                user = UserFactory.build(**user_factory_kwargs)

            self.user = user
            self.accepted_at = timezone.now()
        # Option 2: Explicitly pass a `User` instance to the factory. That user instance
        # will be used as the accepted user and the invitation's `email` and `name` (for
        # the `User`) and `role` (for the `Membership`), etc. will be ignored.
        elif extracted is not None and isinstance(extracted, User):
            self.user = extracted
            self.accepted_at = timezone.now()

        if create and (
            extracted is not None and (extracted is True or isinstance(extracted, User))
        ):
            self.save()  # type: ignore[attr-defined]

    class Meta:
        skip_postgeneration_save = True

    class Params:
        # The `Invitation` has been sent (at least once).
        sent = Trait(
            first_sent_at=factory.LazyFunction(
                lambda: timezone.now() - timedelta(days=2, hours=10)
            ),
            last_sent_at=factory.LazyFunction(
                lambda: timezone.now() - timedelta(days=1, minutes=1)
            ),
            num_times_sent=3,
            delivery_data=factory.LazyFunction(lambda: {"some": "delivery data"}),
        )

        # The `Invitation` has been followed (at least once).
        followed = Trait(
            first_followed_at=factory.LazyFunction(
                lambda: timezone.now() - timedelta(minutes=45)
            ),
            last_followed_at=factory.LazyFunction(
                lambda: timezone.now() - timedelta(minutes=1)
            ),
            num_times_followed=2,
        )

        # The `Invitation` is expired with `expires_at` in the past.
        expired = Trait(
            expires_at=Faker(
                "date_time_between",
                start_date="-89d",
                end_date="-32d",
                tzinfo=UTC,
            )
        )

        # The `Invitation` hasn't expired yet, but it's within the
        # `Invitation.cannot_follow_within` window of expiring.
        expiring_soon_and_cannot_follow = Trait(
            expires_at=factory.LazyFunction(
                lambda: (
                    timezone.now()
                    + Invitation.cannot_follow_within
                    - timedelta(seconds=1)
                )
            ),
        )

        # The `Invitation` is expiring soon, but it's not within the
        # `Invitation.cannot_follow_within` window of expiring.
        expiring_soon_and_can_follow = Trait(
            expires_at=factory.LazyFunction(
                lambda: (
                    timezone.now()
                    + Invitation.cannot_follow_within
                    + timedelta(minutes=3)
                )
            ),
        )
