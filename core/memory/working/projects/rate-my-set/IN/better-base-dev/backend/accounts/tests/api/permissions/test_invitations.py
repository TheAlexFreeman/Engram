from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.accounts.api.permissions.invitations import (
    InvitationAccountHasRequestingUserAsOwner,
)
from backend.accounts.tests.factories.accounts import AccountFactory
from backend.accounts.tests.factories.invitations import InvitationFactory
from backend.accounts.tests.factories.memberships import MembershipFactory
from backend.accounts.tests.factories.users import UserFactory
from backend.accounts.types.roles import Role

# mypy: disable-error-code="arg-type"


class TestInvitationAccountHasRequestingUserAsOwner:
    @pytest.mark.django_db
    def test_all_branches(self):
        # NOTE: Usually `InvitationAccountHasRequestingUserAsOwner` is used alongside
        # `InvitationSharesAccountWithRequestingUser`, so it's hard to test all of the
        # branches in view/integration tests because
        # `InvitationAccountHasRequestingUserAsOwner` will shield certain branches from
        # occurring, etc. Hence, we write a test here.
        a1 = AccountFactory.create()
        u1 = UserFactory.create()
        MembershipFactory.create(account=a1, user=u1, role=Role.OWNER)
        i1 = InvitationFactory.create(account=a1, invited_by=u1)

        u2 = UserFactory.create()

        P = InvitationAccountHasRequestingUserAsOwner
        p = P()

        fake_request = SimpleNamespace(user=u2)

        assert p.has_object_permission(fake_request, None, i1) is False

        m2 = MembershipFactory.create(account=a1, user=u2, role=Role.MEMBER)
        u2 = u2.__class__.objects.get(pk=u2.pk)
        fake_request.user = u2
        assert p.has_object_permission(fake_request, None, i1) is False

        m2.role = Role.OWNER
        m2.save()
        u2 = u2.__class__.objects.get(pk=u2.pk)
        fake_request.user = u2
        assert p.has_object_permission(fake_request, None, i1) is True
