from __future__ import annotations

from factory import SubFactory

from backend.accounts.models import Membership
from backend.accounts.types.roles import Role
from backend.base.tests.factories.core import CoreFactory

from .accounts import AccountFactory


class MembershipFactory(CoreFactory[Membership]):
    account = SubFactory(AccountFactory)
    role = Role.OWNER

    class Meta:
        skip_postgeneration_save = True
