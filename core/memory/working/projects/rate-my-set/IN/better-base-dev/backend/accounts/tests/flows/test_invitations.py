"""
Some Security Notes
-------------------

2024-11-19
==========
* At the time of writing, we require email verification before accepting an invitation
  through the accept endpoint (that is, we require your email to be verified).
* We're also playing it on the "safe side" with case-insensitive emails, meaning, we
  will require you to follow certain invitation links instead of being able to just
  click "accept", etc. if there's not an exact match (and you haven't already followed
  the invitation email).
* All of this is explicitly or implicitly tested here, but it's worth at least
  mentioning up here and/or keeping in mind when reviewing this code.
"""

from __future__ import annotations

from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

import pytest
from dirty_equals import IsStr
from django.contrib.sessions.models import Session
from django.http.response import HttpResponse
from django.template import RequestContext
from django.test.client import Client
from django.utils import timezone
from djangorestframework_camel_case.util import camelize
from pytest_django import DjangoCaptureOnCommitCallbacks
from rest_framework.exceptions import ErrorDetail
from rest_framework.response import Response
from rest_framework.reverse import reverse as drf_reverse
from rest_framework.test import APIClient
from time_machine import TimeMachineFixture

from backend.accounts.api.serializers.invitations import (
    InvitationListAccountExcludedReadOnlySerializer,
    InvitationListReadOnlySerializer,
    InvitationListUserExcludedReadOnlySerializer,
    InvitationReadOnlySerializer,
)
from backend.accounts.api.serializers.memberships import (
    MembershipReadOnlySerializer,
)
from backend.accounts.api.serializers.users import UserReadOnlySerializer
from backend.accounts.models import User
from backend.accounts.models.accounts import Account, AccountType
from backend.accounts.models.invitations import Invitation
from backend.accounts.models.memberships import Membership
from backend.accounts.ops.invitations import (
    check_invitation_email_delivery_signature,
    get_invitation_email_delivery_signature,
    mark_invitation_as_followed_in_session,
)
from backend.accounts.types.invitations import DeliveryMethod, InvitationStatus
from backend.accounts.types.roles import Role
from backend.accounts.types.users import UserCreatedFrom
from backend.base.templatetags.initial_server_data_provided_for_web import (
    get_all_data,
)
from backend.base.tests import gf
from backend.base.tests.helpers.datetimes import Times
from backend.base.tests.helpers.emails import EmailAssertions
from backend.base.tests.helpers.initial_server_data_provided_for_web import (
    extract_initial_data,
)
from backend.base.tests.helpers.transactions import auto_rolling_back_transaction


@pytest.mark.django_db
class TestInviterInvitationsFlows:
    account_maker = staticmethod(gf(Account))
    invitation_maker = staticmethod(gf(Invitation))
    membership_maker = staticmethod(gf(Membership))
    user_maker = staticmethod(gf(User))

    endpoint_create = "/api/invitations"
    endpoint_list = "/api/invitations"
    endpoint_retrieve = "/api/invitations/{pk}"
    endpoint_update = "/api/invitations/{pk}"
    endpoint_resend = "/api/invitations/{pk}/resend"
    endpoint_destroy = "/api/invitations/{pk}"

    @pytest.fixture(autouse=True)
    def setup(self, settings, times: Times, api_client: APIClient, mailoutbox) -> None:
        self.settings = settings
        self.times = times
        self.api_client = api_client
        self.mailoutbox = mailoutbox

    @pytest.fixture
    def setup_default_inviter(self) -> None:
        self.account = self.account_maker(account_type=AccountType.TEAM)
        self.inviter = self.user_maker(account=self.account, email="email0@example.com")
        self.api_client.force_authenticate(self.inviter)

    def create(self, **kwargs: Any):
        kwargs.setdefault("email", "email2@example.com")
        kwargs.setdefault("name", "John Doe")
        kwargs.setdefault("role", Role.MEMBER.value)

        return self.api_client.post(self.endpoint_create, data=kwargs)

    def list(self, **kwargs: Any):
        return self.api_client.get(self.endpoint_list, data=kwargs)

    def retrieve(self, pk: int, **kwargs: Any):
        return self.api_client.get(self.endpoint_retrieve.format(pk=pk))

    def partial_update(self, pk: int, **kwargs: Any):
        return self.api_client.patch(self.endpoint_update.format(pk=pk), data=kwargs)

    def resend(self, pk: int, **kwargs: Any):
        return self.api_client.post(self.endpoint_resend.format(pk=pk), data=kwargs)

    def destroy(self, pk: int):
        return self.api_client.delete(self.endpoint_destroy.format(pk=pk))

    def test_create_403_not_member_of_account(self):
        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        inviter = self.user_maker(account=a1)

        self.api_client.force_authenticate(inviter)
        r = self.create(account=a2.pk, invited_by=inviter.pk)

        assert r.status_code == 403
        assert r.data == {
            "detail": (
                ErrorDetail(
                    "You are not a member of this account.", code="missing_membership"
                )
            )
        }

    def test_create_403_not_owner_in_account(self):
        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        inviter = self.user_maker(account=a1)
        self.membership_maker(account=a2, user=inviter, role=Role.MEMBER)

        self.api_client.force_authenticate(inviter)
        r = self.create(account=a2.pk, invited_by=inviter.pk)

        assert r.status_code == 403
        assert r.data == {
            "detail": (
                ErrorDetail(
                    "You must be an account owner to invite new users.",
                    code="owner_required",
                )
            )
        }

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_create_400_invalid_data(self):
        r1 = self.create(
            account=self.account.pk, invited_by=self.inviter.pk, email="duck"
        )
        r2 = self.create(
            account=self.account.pk, invited_by=self.inviter.pk, name="A" * 256
        )
        r3 = self.create(account="abc", invited_by=self.inviter.pk)
        r4 = self.create(account=self.account.pk + 10_000, invited_by=self.inviter.pk)

        for r in [r1, r2, r3, r4]:
            assert r.status_code == 400

        assert r1.data == {
            "email": [ErrorDetail("Enter a valid email address.", code="invalid")]
        }
        assert r2.data == {
            "name": ["Ensure this field has no more than 255 characters."]
        }
        assert r3.data == {
            "account": [
                ErrorDetail(
                    string="Incorrect type. Expected pk value, received str.",
                    code="incorrect_type",
                )
            ],
        }
        assert r4.data == {
            "account": [
                ErrorDetail(
                    string=f'Invalid pk "{self.account.pk + 10_000}" - object does not exist.',
                    code="does_not_exist",
                )
            ],
        }

        a2 = self.account_maker(account_type=AccountType.PERSONAL)
        u2 = self.user_maker(account=a2)
        r5 = self.create(account=a2.pk, invited_by=u2.pk)
        assert r5.status_code == 400
        assert r5.data == {
            "non_field_errors": [
                ErrorDetail(
                    (
                        "The account you're attempting to invite to is not a team account. "
                        "Please create a team account first and then invite members to that account."
                    ),
                    code="not_team_account",
                )
            ]
        }

    @pytest.mark.usefixtures("setup_default_inviter")
    @pytest.mark.parametrize(
        "existing_email", ["email2@example.com", "eMail2@example.com"]
    )
    @pytest.mark.parametrize("existing_role", [Role.OWNER, Role.MEMBER])
    def test_create_400_already_member_of_team(
        self, existing_email: str, existing_role: Role
    ):
        self.user_maker(
            account=self.account, email=existing_email, membership__role=existing_role
        )

        r = self.create(
            account=self.account.pk,
            invited_by=self.inviter.pk,
            email="email2@example.com",
        )

        assert r.status_code == 400
        assert r.data == {
            "non_field_errors": [
                ErrorDetail(
                    "A user with that email address is already a part of your team.",
                    code="membership_already_exists",
                )
            ]
        }

    def test_create_201_succeeds_for_user_needing_creation(self):
        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        inviter = self.user_maker(account=a1)
        self.membership_maker(account=a2, user=inviter, role=Role.OWNER)

        self.api_client.force_authenticate(inviter)
        r = self.create(account=a1.pk, invited_by=inviter.pk)

        i = Invitation.objects.get()

        assert r.status_code == 201
        assert r.data == InvitationReadOnlySerializer(i).data
        self._assert_invitation_properly_created(
            i, account=a1, inviter=inviter, user=None
        )
        self._assert_invitation_email_properly_sent(
            i, account=a1, inviter=inviter, user=None
        )

    @pytest.mark.parametrize(
        "existing_email", ["email2@example.com", "eMail2@example.com"]
    )
    @pytest.mark.parametrize(
        "existing_role_in_other_account", [Role.OWNER, Role.MEMBER]
    )
    def test_create_201_succeeds_for_user_already_present(
        self, existing_email: str, existing_role_in_other_account: Role
    ):
        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        inviter = self.user_maker(account=a1)

        u2 = self.user_maker(
            account=a2,
            email=existing_email,
            membership__role=existing_role_in_other_account,
        )

        self.api_client.force_authenticate(inviter)
        r = self.create(account=a1.pk, invited_by=inviter.pk)

        i = Invitation.objects.get()

        assert r.status_code == 201
        assert r.data == InvitationReadOnlySerializer(i).data
        self._assert_invitation_properly_created(
            i,
            account=a1,
            inviter=inviter,
            user=(u2 if existing_email == "email2@example.com" else None),
        )
        self._assert_invitation_email_properly_sent(
            i, account=a1, inviter=inviter, user=u2
        )

    def test_list_200_from_inviter_perspective(self):
        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        a3 = self.account_maker(account_type=AccountType.TEAM)
        a4 = self.account_maker(account_type=AccountType.TEAM)
        a5 = self.account_maker(account_type=AccountType.TEAM)
        u1 = self.user_maker(account=a1, email="email1@example.com")
        self.membership_maker(account=a3, user=u1, role=Role.OWNER)
        self.membership_maker(account=a5, user=u1, role=Role.MEMBER)

        other_user1 = self.user_maker(account=a2, email="email70@example.com")
        self.membership_maker(account=a1, user=other_user1, role=Role.OWNER)
        invited_user1 = self.user_maker(account=a2, email="email100@example.com")
        invited_user2 = self.user_maker(
            account=a4, email="email101@example.com", membership__role=Role.MEMBER
        )

        def im(**kwargs: Any) -> Invitation:
            kwargs.setdefault("account", a1)
            kwargs.setdefault("invited_by", u1)
            kwargs.setdefault("user", None)
            kwargs.setdefault("role", Role.MEMBER)

            return self.invitation_maker(**kwargs)

        # fmt: off
        i11 = im(email="email11@example.com")
        i12 = im(email=invited_user1.email, user=invited_user1)
        i13 = im(invited_by=other_user1, email="emaiL101@example.com")
        i14 = im(email="email14@example.com", role=Role.OWNER)
        i15 = im(invited_by=other_user1, email="email15@example.com", declined_at=self.times.now)
        i16 = im(email="email16@example.com", accepted_at=self.times.now - timedelta(seconds=1))
        i17 = im(email="email17@example.com", accepted_at=self.times.now + timedelta(minutes=3))
        i18 = im(email="email18@example.com", expires_at=self.times.now - timedelta(seconds=1))
        i19 = im(email="email19@example.com", expires_at=self.times.now - timedelta(days=50))

        i21 = im(account=a2, invited_by=other_user1, email="email21@example.com")  # noqa: F841
        i22 = im(account=a2, email=invited_user2.email, user=invited_user2, accepted_at=self.times.now)  # noqa: F841
        i23 = im(account=a2, invited_by=other_user1, email="email23@example.com")  # noqa: F841

        i31 = im(account=a3, invited_by=other_user1, email="email31@example.com")
        i32 = im(account=a3, email=invited_user1.email, user=invited_user1, accepted_at=self.times.now)
        i33 = im(account=a3, email=invited_user2.email, user=invited_user2, accepted_at=self.times.now)
        i34 = im(account=a3, invited_by=other_user1, email="email34@example.com")

        i41 = im(account=a4, invited_by=invited_user2, email="email41@example.com")  # noqa: F841
        i42 = im(account=a4, invited_by=invited_user2, email=invited_user1.email, user=invited_user1, accepted_at=self.times.now)  # noqa: F841
        # fmt: on

        self.api_client.force_authenticate(u1)
        r_no_account_specified = self.list()
        r1_default = self.list(account_id=a1.pk)
        r1_only_accepted = self.list(account_id=a1.pk, is_accepted=True)
        r1_only_not_accepted = self.list(account_id=a1.pk, is_accepted=False)
        r1_only_declined = self.list(account_id=a1.pk, is_declined=True)
        r1_only_not_declined = self.list(account_id=a1.pk, is_declined=False)
        r1_only_expired = self.list(account_id=a1.pk, is_expired=True)
        r1_only_not_expired = self.list(account_id=a1.pk, is_expired=False)
        r2_default = self.list(account_id=a2.pk)
        r2_only_not_accepted = self.list(account_id=a2.pk, is_accepted=False)
        r3_default = self.list(account_id=a3.pk)
        r3_only_not_accepted = self.list(account_id=a3.pk, is_accepted=False)
        r4_default = self.list(account_id=a4.pk)
        r4_only_not_accepted = self.list(account_id=a4.pk, is_accepted=False)
        r5_default = self.list(account_id=a5.pk)
        r5_only_not_accepted = self.list(account_id=a5.pk, is_accepted=False)

        assert r_no_account_specified.status_code == 400
        assert r_no_account_specified.data == {
            "non_field_errors": [
                ErrorDetail(
                    string="You must provide at least one of `user_id` or `account_id` as a query parameter.",
                    code="missing_query_param",
                ),
            ]
        }

        S = InvitationListAccountExcludedReadOnlySerializer

        def assert_response_correct(r, *invitations):
            assert r.status_code == 200
            serializer_data = S(invitations, many=True).data
            # Start with the easier assertions to see pytest error output for and then
            # progress to the ones that would have the most red/green output, etc.
            assert len(r.data) == len(invitations)
            assert len(serializer_data) == len(invitations)
            if invitations:
                assert r.data[0] == serializer_data[0]
                assert r.data[-1] == serializer_data[-1]
            assert r.data == serializer_data

        # fmt: off
        assert_response_correct(r1_default, i19, i18, i17, i16, i15, i14, i13, i12, i11)
        assert_response_correct(r1_only_accepted, i17, i16)
        assert_response_correct(r1_only_not_accepted, i19, i18, i15, i14, i13, i12, i11)
        assert_response_correct(r1_only_declined, i15)
        assert_response_correct(r1_only_not_declined, i19, i18, i17, i16, i14, i13, i12, i11)
        assert_response_correct(r1_only_expired, i19, i18)
        assert_response_correct(r1_only_not_expired, i17, i16, i15, i14, i13, i12, i11)

        assert r2_default.status_code == 403
        assert r2_only_not_accepted.status_code == 403
        assert r2_default.data == {
            "detail": (
                ErrorDetail(
                    "You do not have a membership in the account you are attempting to view or act on.",
                    code="missing_membership",
                )
            )
        }
        assert r2_only_not_accepted.data == {
            "detail": (
                ErrorDetail(
                    "You do not have a membership in the account you are attempting to view or act on.",
                    code="missing_membership",
                )
            )
        }

        assert_response_correct(r3_default, i34, i33, i32, i31)
        assert_response_correct(r3_only_not_accepted, i34, i31)

        assert r4_default.status_code == 403
        assert r4_only_not_accepted.status_code == 403
        assert r4_default.data == {
            "detail": (
                ErrorDetail(
                    "You do not have a membership in the account you are attempting to view or act on.",
                    code="missing_membership",
                )
            )
        }
        assert r4_only_not_accepted.data == {
            "detail": (
                ErrorDetail(
                    "You do not have a membership in the account you are attempting to view or act on.",
                    code="missing_membership",
                )
            )
        }

        assert_response_correct(r5_default)
        assert_response_correct(r5_only_not_accepted)
        # fmt: on

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_retrieve_404(self):
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u2 = self.user_maker(account=a2)
        i2 = self.invitation_maker(
            account=a2, invited_by=u2, email="email2@example.com"
        )

        r = self.retrieve(i2.pk + 10_000)

        assert r.status_code == 404

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_retrieve_403(self):
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u2 = self.user_maker(account=a2)
        i2 = self.invitation_maker(
            account=a2, invited_by=u2, email="email2@example.com"
        )

        r = self.retrieve(i2.pk)

        assert r.status_code == 403
        assert r.data == {
            "detail": ErrorDetail(
                "You must have a membership in the account you are attempting to view or act on to perform this action.",
                code="missing_membership",
            )
        }

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_retrieve_200(self):
        i11 = self.invitation_maker(account=self.account, invited_by=self.inviter)  # noqa: F841
        i12 = self.invitation_maker(account=self.account, invited_by=self.inviter)
        i13 = self.invitation_maker(account=self.account, invited_by=self.inviter)  # noqa: F841
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u2 = self.user_maker(account=a2)
        i21 = self.invitation_maker(  # noqa: F841
            account=a2, invited_by=u2, email="email2@example.com"
        )

        r = self.retrieve(i12.pk)

        assert r.status_code == 200
        assert r.data == InvitationReadOnlySerializer(i12).data

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_update_404(self):
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u2 = self.user_maker(account=a2)
        i2 = self.invitation_maker(
            account=a2, invited_by=u2, email="email2@example.com", role=Role.OWNER
        )

        r = self.partial_update(i2.pk + 10_000, role=Role.MEMBER)

        assert r.status_code == 404, r.data

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_update_403(self):
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u2 = self.user_maker(account=a2)
        i2 = self.invitation_maker(
            account=a2, invited_by=u2, email="email2@example.com", role=Role.OWNER
        )
        a3 = self.account_maker(account_type=AccountType.TEAM)
        u3 = self.user_maker(account=a3)
        i3 = self.invitation_maker(
            account=a3, invited_by=u3, email="email3@example.com", role=Role.OWNER
        )
        self.membership_maker(account=a3, user=self.inviter, role=Role.MEMBER)

        r_missing_membership = self.partial_update(i2.pk, role=Role.MEMBER)
        r_not_owner = self.partial_update(i3.pk, name="Frank Doe")

        assert r_missing_membership.status_code == 403
        assert r_missing_membership.data == {
            "detail": ErrorDetail(
                "You must have a membership in the account you are attempting to view or act on to perform this action.",
                code="missing_membership",
            )
        }

        assert r_not_owner.status_code == 403
        assert r_not_owner.data == {
            "detail": ErrorDetail(
                (
                    "You must be an owner role in the account associated with the "
                    "invitation you are trying to view or act on to perform this action."
                ),
                code="owner_required",
            )
        }

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_update_400(self):
        def im(**kwargs: Any) -> Invitation:
            kwargs.setdefault("account", self.account)
            kwargs.setdefault("invited_by", self.inviter)
            kwargs.setdefault("user", None)
            kwargs.setdefault("role", Role.MEMBER)

            return self.invitation_maker(**kwargs)

        i1 = im(email="email1@example.com")
        i2 = im(email="email2@example.com", user=None, accepted_at=self.times.now)
        i3 = im(
            email="email2@example.com",
            user=self.user_maker(),
            accepted_at=self.times.now,
        )
        i4 = im(email="email2@example.com", declined_at=self.times.now)
        i5 = im(email="email2@example.com", expired=True)

        r_invalid_role = self.partial_update(i1.pk, role="duck")
        r_invalid_name = self.partial_update(i1.pk, name="A" * 256)
        r_accepted1 = self.partial_update(i2.pk, name="New Name")
        r_accepted2 = self.partial_update(i3.pk, name="New Name")
        r_declined = self.partial_update(i4.pk, name="New Name")
        r_expired = self.partial_update(i5.pk, name="New Name")

        for r in [
            r_invalid_role,
            r_invalid_name,
            r_accepted1,
            r_accepted2,
            r_declined,
            r_expired,
        ]:
            assert r.status_code == 400

        assert r_invalid_role.data == {
            "role": [
                ErrorDetail('"duck" is not a valid choice.', code="invalid_choice")
            ]
        }
        assert r_invalid_name.data == {
            "name": ["Ensure this field has no more than 255 characters."]
        }
        assert r_accepted1.data == {
            "non_field_errors": [
                ErrorDetail(
                    "You cannot update an invitation that has been accepted.",
                    code="already_accepted",
                )
            ]
        }
        assert r_accepted2.data == {
            "non_field_errors": [
                ErrorDetail(
                    "You cannot update an invitation that has been accepted.",
                    code="already_accepted",
                )
            ]
        }
        assert r_declined.data == {
            "non_field_errors": [
                ErrorDetail(
                    "You cannot update an invitation that has been declined.",
                    code="already_declined",
                )
            ]
        }
        assert r_expired.data == {
            "non_field_errors": [
                ErrorDetail(
                    "You cannot update an invitation that has expired.",
                    code="expired",
                )
            ]
        }

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_update_200(self):
        i1 = self.invitation_maker(
            account=self.account,
            invited_by=self.inviter,
            email="email2@example.com",
            role=Role.OWNER,
            name="John Doe",
            created=self.times.now - timedelta(hours=2),
            modified=self.times.now - timedelta(hours=2),
        )

        r = self.partial_update(
            i1.pk,
            role=Role.MEMBER,
            email="email22@example.com",
            name="Frank Doe",
        )
        i1.refresh_from_db()

        assert r.status_code == 200
        assert r.data == InvitationReadOnlySerializer(i1).data

        assert i1.role == Role.MEMBER
        # The `email` shouldn't change since we don't allow changing email on the
        # `Invitation`.
        assert i1.email == "email2@example.com"
        assert i1.name == "Frank Doe"
        assert i1.role == Role.MEMBER
        assert i1.modified == self.times.close_to_now

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_resend_404(self):
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u2 = self.user_maker(account=a2)
        i2 = self.invitation_maker(
            account=a2, invited_by=u2, email="email2@example.com"
        )

        r = self.resend(i2.pk + 10_000)

        assert r.status_code == 404

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_resend_403(self):
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u2 = self.user_maker(account=a2)
        i2 = self.invitation_maker(
            account=a2, invited_by=u2, email="email2@example.com", role=Role.OWNER
        )
        a3 = self.account_maker(account_type=AccountType.TEAM)
        u3 = self.user_maker(account=a3)
        i3 = self.invitation_maker(
            account=a3, invited_by=u3, email="email3@example.com", role=Role.OWNER
        )
        self.membership_maker(account=a3, user=self.inviter, role=Role.MEMBER)

        r_missing_membership = self.resend(i2.pk)
        r_not_owner = self.resend(i3.pk)

        assert r_missing_membership.status_code == 403
        assert r_missing_membership.data == {
            "detail": ErrorDetail(
                "You must have a membership in the account you are attempting to view or act on to perform this action.",
                code="missing_membership",
            )
        }

        assert r_not_owner.status_code == 403
        assert r_not_owner.data == {
            "detail": ErrorDetail(
                (
                    "You must be an owner role in the account associated with the "
                    "invitation you are trying to view or act on to perform this action."
                ),
                code="owner_required",
            )
        }

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_resend_400(self):
        def im(**kwargs: Any) -> Invitation:
            kwargs.setdefault("account", self.account)
            kwargs.setdefault("invited_by", self.inviter)
            kwargs.setdefault("user", None)
            kwargs.setdefault("role", Role.MEMBER)

            return self.invitation_maker(**kwargs)

        i1 = im(email="email1@example.com")  # noqa: F841
        i2 = im(email="email2@example.com", user=None, accepted_at=self.times.now)
        i3 = im(
            email="email2@example.com",
            user=self.user_maker(),
            accepted_at=self.times.now,
        )
        i4 = im(email="email2@example.com", declined_at=self.times.now)
        i5 = im(email="email2@example.com", expired=True)

        r_accepted1 = self.resend(i2.pk)
        r_accepted2 = self.resend(i3.pk)
        r_declined = self.resend(i4.pk)
        r_expired = self.resend(i5.pk)

        for r in [r_accepted1, r_accepted2, r_declined, r_expired]:
            assert r.status_code == 400

        assert r_accepted1.data == {
            "non_field_errors": [
                ErrorDetail(
                    "You cannot resend an invitation that has been accepted.",
                    code="already_accepted",
                )
            ]
        }
        assert r_accepted2.data == {
            "non_field_errors": [
                ErrorDetail(
                    "You cannot resend an invitation that has been accepted.",
                    code="already_accepted",
                )
            ]
        }
        assert r_declined.data == {
            "non_field_errors": [
                ErrorDetail(
                    "You cannot resend an invitation that has been declined.",
                    code="already_declined",
                )
            ]
        }
        assert r_expired.data == {
            "non_field_errors": [
                ErrorDetail(
                    "You cannot resend an invitation that has expired.",
                    code="expired",
                )
            ]
        }

    def test_resend_200_succeeds_for_user_needing_creation(
        self, time_machine: TimeMachineFixture
    ):
        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        inviter = self.user_maker(account=a1)
        self.membership_maker(account=a2, user=inviter, role=Role.OWNER)

        self.api_client.force_authenticate(inviter)
        initial_r = self.create(account=a1.pk, invited_by=inviter.pk)
        assert initial_r.status_code == 201

        i = Invitation.objects.get()

        time_diff = timedelta(minutes=10)
        original_now = self.times.now
        new_now = original_now + time_diff
        time_machine.move_to(new_now)
        r = self.resend(i.pk)
        i.refresh_from_db()

        assert r.status_code == 200
        assert r.data == InvitationReadOnlySerializer(i).data

        self._assert_invitation_email_properly_sent(
            i,
            account=a1,
            inviter=inviter,
            user=None,
            num_times_sent=2,
            now=new_now,
            first_sent_near=original_now,
        )

    @pytest.mark.parametrize(
        "existing_email", ["email2@example.com", "eMail2@example.com"]
    )
    @pytest.mark.parametrize(
        "existing_role_in_other_account", [Role.OWNER, Role.MEMBER]
    )
    def test_resend_200_succeeds_for_user_already_present(
        self,
        existing_email: str,
        existing_role_in_other_account: Role,
        time_machine: TimeMachineFixture,
    ):
        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        inviter = self.user_maker(account=a1)

        u2 = self.user_maker(
            account=a2,
            email=existing_email,
            membership__role=existing_role_in_other_account,
        )

        self.api_client.force_authenticate(inviter)
        initial_r = self.create(account=a1.pk, invited_by=inviter.pk)
        assert initial_r.status_code == 201

        i = Invitation.objects.get()

        time_diff = timedelta(minutes=10)
        original_now = self.times.now
        new_now = original_now + time_diff
        time_machine.move_to(new_now)
        r = self.resend(i.pk)
        i.refresh_from_db()

        assert r.status_code == 200
        assert r.data == InvitationReadOnlySerializer(i).data

        self._assert_invitation_email_properly_sent(
            i,
            account=a1,
            inviter=inviter,
            user=u2,
            num_times_sent=2,
            now=new_now,
            first_sent_near=original_now,
        )

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_delete_404(self):
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u2 = self.user_maker(account=a2)
        i2 = self.invitation_maker(
            account=a2, invited_by=u2, email="email2@example.com"
        )

        r = self.destroy(i2.pk + 10_000)

        assert r.status_code == 404

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_delete_403(self):
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u2 = self.user_maker(account=a2)
        i2 = self.invitation_maker(
            account=a2, invited_by=u2, email="email2@example.com", role=Role.OWNER
        )
        a3 = self.account_maker(account_type=AccountType.TEAM)
        u3 = self.user_maker(account=a3)
        i3 = self.invitation_maker(
            account=a3, invited_by=u3, email="email3@example.com", role=Role.OWNER
        )
        self.membership_maker(account=a3, user=self.inviter, role=Role.MEMBER)

        r_missing_membership = self.destroy(i2.pk)
        r_not_owner = self.destroy(i3.pk)

        assert r_missing_membership.status_code == 403
        assert r_missing_membership.data == {
            "detail": ErrorDetail(
                "You must have a membership in the account you are attempting to view or act on to perform this action.",
                code="missing_membership",
            )
        }

        assert r_not_owner.status_code == 403
        assert r_not_owner.data == {
            "detail": ErrorDetail(
                (
                    "You must be an owner role in the account associated with the "
                    "invitation you are trying to view or act on to perform this action."
                ),
                code="owner_required",
            )
        }

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_delete_400(self):
        i1 = self.invitation_maker(
            account=self.account,
            invited_by=self.inviter,
            email="email1@example.com",
            user=self.user_maker(email="email1@example.com"),
            accepted_at=self.times.now,
        )
        i2 = self.invitation_maker(
            account=self.account,
            invited_by=self.inviter,
            email="email2@example.com",
            accepted_at=self.times.now,
        )

        r_accepted1 = self.destroy(i1.pk)
        r_accepted2 = self.destroy(i2.pk)

        assert r_accepted1.status_code == 400
        assert r_accepted1.data == {
            "non_field_errors": [
                ErrorDetail(
                    "You cannot delete an invitation that has been accepted.",
                    code="already_accepted",
                )
            ]
        }
        assert r_accepted2.status_code == 400
        assert r_accepted2.data == {
            "non_field_errors": [
                ErrorDetail(
                    "You cannot delete an invitation that has been accepted.",
                    code="already_accepted",
                )
            ]
        }

    @pytest.mark.usefixtures("setup_default_inviter")
    def test_delete_204(
        self, django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks
    ):
        i1 = self.invitation_maker(
            account=self.account,
            invited_by=self.inviter,
            email="email2@example.com",
            role=Role.OWNER,
            name="John Doe",
            created=self.times.now - timedelta(hours=2),
            modified=self.times.now - timedelta(hours=2),
        )
        i2 = self.invitation_maker(
            account=self.account,
            invited_by=self.inviter,
            email="email2@example.com",
            role=Role.OWNER,
            name="John Doe",
            created=self.times.now - timedelta(hours=2),
            modified=self.times.now - timedelta(hours=2),
        )

        with django_capture_on_commit_callbacks(execute=True):
            r = self.destroy(i1.pk)

        with pytest.raises(Invitation.DoesNotExist):
            i1.refresh_from_db()
        i2.refresh_from_db()
        assert i2.pk is not None
        assert r.status_code == 204

    def _assert_invitation_properly_created(
        self,
        i: Invitation,
        *,
        account: Account,
        inviter: User,
        email: str = "email2@example.com",
        name: str = "John Doe",
        user: User | None,
        role: Role | str = Role.MEMBER,
        now_reference_point: datetime | Literal["default"] = "default",
    ):
        now: datetime
        if now_reference_point == "default":
            now = self.times.now
        else:
            assert isinstance(now_reference_point, datetime), "Pre-condition"
            now = now_reference_point

        assert i.account == account
        assert i.invited_by == inviter
        assert i.email == email
        assert i.name == name
        assert i.role == role

        assert i.user == user
        assert i.accepted_at is None
        assert i.declined_at is None

        # Just sanity check some values. The operation(s) that create `Invitation`(s)
        # are already tested in detail, so we just want to sanity check a few things.
        assert i.expires_at == self.times.CloseTo(
            now + Invitation.default_expires_after
        )
        assert i.secret_token and len(i.secret_token) >= 30
        assert i.created == self.times.CloseTo(now)
        assert i.modified == self.times.CloseTo(now)

        assert i.first_followed_at is None
        assert i.last_followed_at is None
        assert i.num_times_followed == 0

    def _assert_invitation_email_properly_sent(
        self,
        i: Invitation,
        *,
        account: Account,
        inviter: User,
        user: User | None,
        email: str = "email2@example.com",
        num_times_sent: int = 1,
        now: datetime | Literal["default"] = "default",
        first_sent_near: datetime | Literal["default"] = "default",
    ):
        if now == "default":
            now = self.times.now
        if first_sent_near == "default":
            first_sent_near = now

        assert i.account == account
        assert i.invited_by == inviter

        assert i.delivery_method == DeliveryMethod.EMAIL
        assert i.first_sent_at == self.times.CloseTo(first_sent_near)
        assert i.last_sent_at == self.times.CloseTo(now)
        assert i.num_times_sent == num_times_sent
        assert i.delivery_data == {
            "invited_user_email": (None if user is None else user.email),
            "invited_user_id": (None if user is None else user.pk),
            "sent_at": self.times.CloseTo(now, string=True),
            "to_email": "email2@example.com",
            "was_sent": True,
        }
        assert i.modified == self.times.CloseTo(now)

        assert len(self.mailoutbox) == num_times_sent
        ea = EmailAssertions(self.mailoutbox[-1])
        ea.assert_is_invitation_email(
            i, to_email=email, subject=i.headline, user_exists=user is not None
        )


@pytest.mark.django_db
class TestInviteeInvitationsFlows:
    account_maker = staticmethod(gf(Account))
    invitation_maker = staticmethod(gf(Invitation))
    membership_maker = staticmethod(gf(Membership))
    user_maker = staticmethod(gf(User))

    endpoint_accept = "/api/invitations/{pk}/accept"
    endpoint_create = "/api/invitations"
    endpoint_decline = "/api/invitations/{pk}/decline"
    endpoint_list = "/api/invitations"
    endpoint_resend = "/api/invitations/{pk}/resend"

    endpoint_login = "/api/auth/login/from-invitation"
    endpoint_signup = "/api/auth/signup/from-invitation"

    # Some password that will pass validation.
    strong_password = "Burn!IngSt@r541"

    @pytest.fixture(autouse=True)
    def setup(
        self,
        settings,
        times: Times,
        client: Client,
        api_client: APIClient,
        mailoutbox,
        django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    ) -> None:
        self.settings = settings
        self.times = times
        self.client = client
        self.api_client = api_client
        self.mailoutbox = mailoutbox
        self.django_capture_on_commit_callbacks = django_capture_on_commit_callbacks

    def create(self, **kwargs: Any):
        kwargs.setdefault("email", "email2@example.com")
        kwargs.setdefault("name", "John Doe")
        kwargs.setdefault("role", Role.MEMBER.value)

        api_client: APIClient = kwargs.pop("api_client", self.api_client)

        return api_client.post(self.endpoint_create, data=kwargs)

    def list(self, **kwargs: Any):
        return self.api_client.get(self.endpoint_list, data=kwargs)

    def resend(self, pk: int, **kwargs: Any):
        return self.api_client.post(self.endpoint_resend.format(pk=pk), data=kwargs)

    @dataclass
    class FollowResult:
        first_response: HttpResponse
        first_response_status_code: int
        redirect_link: str
        second_response: HttpResponse
        second_response_status_code: int
        second_response_initial_data: dict[str, Any]
        invitation: Invitation | None

    def follow(
        self,
        *,
        api_client: APIClient,
        email_assertions: EmailAssertions,
        check_invitation_exists: bool = True,
        check_invitation_followed: bool = True,
        check_invitation_followed_by_email: bool = True,
        strip_signature: bool = False,
        log_in_as_user_before_following: User | None = None,
        use_passed_invitation: Invitation | None = None,
    ) -> FollowResult:
        if log_in_as_user_before_following:
            api_client.force_authenticate(log_in_as_user_before_following)
            api_client.force_login(log_in_as_user_before_following)

        link = email_assertions.extract_invitation_email_link()
        assert link, "Pre-condition"
        _, token_part = link.rsplit("/", 1)
        assert token_part, "Pre-condition"
        signature_part: str | None = None
        signature: str | None = None
        try:
            token, signature_part = token_part.split("?")
        except ValueError:
            token = token_part
        else:
            assert len(signature_part.split("=")) == 2
            signature = signature_part.split("=")[1]
            assert signature, "Pre-condition"
        if strip_signature and signature:
            link_strip_split = link.split("?es=")
            assert (
                len(link_strip_split) == 2
                and link_strip_split[0]
                and link_strip_split[1]
            )
            link = link_strip_split[0]

        invitation: Invitation | None = None
        invitation_info: dict[str, Any] = {}
        if check_invitation_exists:
            invitation = Invitation.objects.select_related(
                "account", "invited_by", "user"
            ).get(secret_token=token)
            assert invitation is not None
        elif use_passed_invitation is not None:
            invitation = use_passed_invitation
        else:
            try:
                invitation = Invitation.objects.select_related(
                    "account", "invited_by", "user"
                ).get(secret_token=token)
            except Invitation.DoesNotExist:
                pass
        if invitation is not None:
            invitation_info["first_followed_at"] = invitation.first_followed_at
            invitation_info["last_followed_at"] = invitation.last_followed_at
            invitation_info["num_times_followed"] = invitation.num_times_followed

        first_response = Client.get(api_client, link, follow=False)
        next_link = first_response.headers["Location"]

        assert first_response.status_code == 302
        assert next_link, "Pre-condition"
        assert next_link == "/follow-invitation"

        second_response = Client.get(api_client, next_link, follow=False)
        second_response_initial_data = extract_initial_data(second_response)

        assert second_response.status_code == 200
        assert second_response_initial_data["extra"]

        if check_invitation_followed:
            assert invitation is not None, "Pre-condition"
            invitation.refresh_from_db()
            assert invitation.first_followed_at is not None
            assert invitation.first_followed_at == (
                invitation_info["first_followed_at"] or invitation.first_followed_at
            )
            assert invitation.last_followed_at is not None
            if invitation_info["num_times_followed"]:
                assert invitation.last_followed_at >= invitation.first_followed_at
            else:
                assert invitation.last_followed_at == invitation.first_followed_at
            assert (
                invitation.num_times_followed
                == invitation_info["num_times_followed"] + 1
            )

        if check_invitation_followed_by_email:
            assert invitation is not None, "Pre-condition"
            assert signature == get_invitation_email_delivery_signature(invitation)
            assert check_invitation_email_delivery_signature(invitation, signature)

        return self.FollowResult(
            first_response=first_response,  # type: ignore[arg-type]
            first_response_status_code=first_response.status_code,
            redirect_link=next_link,
            second_response=second_response,  # type: ignore[arg-type]
            second_response_status_code=second_response.status_code,
            second_response_initial_data=second_response_initial_data,
            invitation=invitation,
        )

    def signup(self, *, api_client: APIClient | None = None, **kwargs: Any):
        api_client = self.api_client if api_client is None else api_client
        with self.django_capture_on_commit_callbacks(execute=True):
            return api_client.post(self.endpoint_signup, data=kwargs)

    def login(self, *, api_client: APIClient | None = None, **kwargs: Any):
        api_client = self.api_client if api_client is None else api_client
        with self.django_capture_on_commit_callbacks(execute=True):
            return api_client.post(self.endpoint_login, data=kwargs)

    def decline(self, *, api_client: APIClient | None = None, **kwargs: Any):
        if not (invitation_id := kwargs.pop("invitation_id", None)):
            raise RuntimeError(
                "Currently you must provide `invitation_id` through the kwargs."
            )
        api_client = self.api_client if api_client is None else api_client
        with self.django_capture_on_commit_callbacks(execute=True):
            return api_client.post(
                self.endpoint_decline.format(pk=invitation_id), data=kwargs
            )

    def accept(self, *, api_client: APIClient | None = None, **kwargs: Any):
        if not (invitation_id := kwargs.pop("invitation_id", None)):
            raise RuntimeError(
                "Currently you must provide `invitation_id` through the kwargs."
            )
        api_client = self.api_client if api_client is None else api_client
        with self.django_capture_on_commit_callbacks(execute=True):
            return api_client.post(
                self.endpoint_accept.format(pk=invitation_id), data=kwargs
            )

    def test_list_200_from_invitee_perspective(self):
        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        a3 = self.account_maker(account_type=AccountType.TEAM)
        a4 = self.account_maker(account_type=AccountType.TEAM)
        a5 = self.account_maker(account_type=AccountType.TEAM)
        u1 = self.user_maker(account=a1, email="email1@example.com")
        self.membership_maker(account=a3, user=u1, role=Role.OWNER)
        self.membership_maker(account=a5, user=u1, role=Role.MEMBER)

        other_user1 = self.user_maker(account=a2, email="email70@example.com")
        self.membership_maker(account=a1, user=other_user1, role=Role.OWNER)
        invited_user1 = self.user_maker(account=a2, email="email100@example.com")
        invited_user2 = self.user_maker(
            account=a4, email="email101@example.com", membership__role=Role.MEMBER
        )

        def im(**kwargs: Any) -> Invitation:
            kwargs.setdefault("account", a1)
            kwargs.setdefault("invited_by", u1)
            kwargs.setdefault("user", None)
            kwargs.setdefault("role", Role.MEMBER)

            return self.invitation_maker(**kwargs)

        # fmt: off
        i11 = im(email="email11@example.com")  # noqa: F841
        i12 = im(email=invited_user1.email, user=invited_user1)
        i13 = im(invited_by=other_user1, email="emaiL101@example.com")  # noqa: F841
        i14 = im(email="email14@example.com", role=Role.OWNER)  # noqa: F841
        i15 = im(invited_by=other_user1, email="email15@example.com", user=invited_user1, declined_at=self.times.now)
        i16 = im(email="email16@example.com", accepted_at=self.times.now - timedelta(seconds=1))  # noqa: F841
        i17 = im(email="email17@example.com", accepted_at=self.times.now + timedelta(minutes=3))  # noqa: F841
        i18 = im(email=invited_user1.email, user=invited_user1, expires_at=self.times.now - timedelta(seconds=1))
        i19 = im(email="email19@example.com", expires_at=self.times.now - timedelta(days=50))  # noqa: F841

        i21 = im(account=a2, invited_by=other_user1, email="email21@example.com")  # noqa: F841
        i22 = im(account=a2, email=invited_user2.email, user=invited_user2, accepted_at=self.times.now)  # noqa: F841
        i23 = im(account=a2, invited_by=other_user1, email="email23@example.com")  # noqa: F841

        i31 = im(account=a3, invited_by=other_user1, email="email31@example.com")  # noqa: F841
        i32 = im(account=a3, email=invited_user1.email, user=invited_user1, accepted_at=self.times.now)
        i33 = im(account=a3, email=invited_user2.email, user=invited_user2, accepted_at=self.times.now)  # noqa: F841
        i34 = im(account=a3, invited_by=other_user1, email="email34@example.com")  # noqa: F841
        i35 = im(account=a3, email=invited_user2.email)  # noqa: F841

        i41 = im(account=a4, invited_by=invited_user2, email=invited_user1.email, user=invited_user1)
        i42 = im(account=a4, invited_by=invited_user1, email="email41@example.com")  # noqa: F841
        # fmt: on

        self.api_client.force_authenticate(invited_user1)
        r_no_user_specified = self.list()
        r_other_user_specified = self.list(user_id=invited_user2.pk)
        r1_default = self.list(user_id=invited_user1.pk)
        r1_only_accepted = self.list(user_id=invited_user1.pk, is_accepted=True)
        r1_only_not_accepted = self.list(user_id=invited_user1.pk, is_accepted=False)
        r1_only_declined = self.list(user_id=invited_user1.pk, is_declined=True)
        r1_only_not_declined = self.list(user_id=invited_user1.pk, is_declined=False)
        r1_only_expired = self.list(user_id=invited_user1.pk, is_expired=True)
        r1_only_not_expired = self.list(user_id=invited_user1.pk, is_expired=False)

        self.membership_maker(account=a1, user=invited_user1, role=Role.MEMBER)
        invited_user1.refresh_from_db()
        with suppress(AttributeError):
            del invited_user1.account_id_to_membership_local_cache
        with suppress(AttributeError):
            del invited_user1.active_memberships

        r1_a1_default = self.list(user_id=invited_user1.pk, account_id=a1.pk)
        r1_a2_default = self.list(user_id=invited_user1.pk, account_id=a2.pk)
        r1_a3_default = self.list(user_id=invited_user1.pk, account_id=a3.pk)
        r1_a4_default = self.list(user_id=invited_user1.pk, account_id=a4.pk)

        assert r_no_user_specified.status_code == 400
        assert r_no_user_specified.data == {
            "non_field_errors": [
                ErrorDetail(
                    string="You must provide at least one of `user_id` or `account_id` as a query parameter.",
                    code="missing_query_param",
                ),
            ]
        }

        assert r_other_user_specified.status_code == 403
        assert r_other_user_specified.data == {
            "detail": (
                ErrorDetail(
                    string=(
                        "You cannot filter down to a specific user (`user_id`) without "
                        "that user being you or without filtering down to a specific "
                        "account (`account_id`) that you belong to as well."
                    ),
                    code="cannot_filter_down_to_user_without_account_unless_you",
                )
            )
        }

        S = InvitationListUserExcludedReadOnlySerializer

        def assert_response_correct(
            r,
            *invitations,
            S: type[InvitationListReadOnlySerializer] = S,
        ):
            serializer_data = S(invitations, many=True).data
            # Start with the easier assertions to see pytest error output for and then
            # progress to the ones that would have the most red/green output, etc.
            assert len(r.data) == len(invitations)
            assert len(serializer_data) == len(invitations)
            if invitations:
                assert r.data[0] == serializer_data[0]
                assert r.data[-1] == serializer_data[-1]
            assert r.data == serializer_data

        # fmt: off
        assert_response_correct(r1_default, i41, i32, i18, i15, i12)
        assert_response_correct(r1_only_accepted, i32)
        assert_response_correct(r1_only_not_accepted, i41, i18, i15, i12)
        assert_response_correct(r1_only_declined, i15)
        assert_response_correct(r1_only_not_declined, i41, i32, i18, i12)
        assert_response_correct(r1_only_expired, i18)
        assert_response_correct(r1_only_not_expired, i41, i32, i15, i12)

        AS = InvitationListAccountExcludedReadOnlySerializer
        assert_response_correct(r1_a1_default, i18, i15, i12, S=AS)
        assert_response_correct(r1_a2_default, S=AS)

        assert r1_a3_default.status_code == 403
        assert r1_a3_default.data == {
            "detail": (
                ErrorDetail(
                    "You do not have a membership in the account you are attempting to view or act on.",
                    code="missing_membership",
                )
            )
        }

        assert r1_a4_default.status_code == 403
        assert r1_a4_default.data == {
            "detail": (
                ErrorDetail(
                    "You do not have a membership in the account you are attempting to view or act on.",
                    code="missing_membership",
                )
            )
        }
        # fmt: on

    # --- Invitee - New User ---

    @dataclass(kw_only=True)
    class InvitedNewUserSetup:
        a1: Account
        a2: Account
        u1: User
        other_user1: User
        other_membership1: Membership
        create_response: Response
        i1: Invitation
        ea1: EmailAssertions
        follow_result: TestInviteeInvitationsFlows.FollowResult
        initial_follow_extra: dict[str, Any]

    @dataclass(kw_only=True)
    class InvitedExistingUserSetup:
        a1: Account
        a2: Account
        u1: User
        eu1: User
        other_user1: User
        other_membership1: Membership
        create_response: Response
        i1: Invitation
        ea1: EmailAssertions
        follow_result: TestInviteeInvitationsFlows.FollowResult
        initial_follow_extra: dict[str, Any]

    def make_invited_new_user_setup(
        self,
        *,
        email: str = "email2@example.com",
        name: str = "John Doe",
        invitee_role: Role = Role.MEMBER,
        has_email_signature: bool = True,
        logged_in_as_other_user_when_following_link: bool = False,
    ) -> InvitedNewUserSetup:
        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u1 = self.user_maker(account=a1, email="email1@example.com")
        other_user1 = self.user_maker(account=a2, email="email70@example.com")
        other_membership1 = self.membership_maker(
            account=a1, user=other_user1, role=Role.MEMBER
        )

        # Create the invitation.
        self.api_client.force_authenticate(u1)
        create_response = self.create(
            account=a1.pk,
            email=email,
            name=name,
            role=invitee_role,
        )
        assert create_response.status_code == 201, create_response.data
        # Then check that it's present.
        i1 = Invitation.objects.select_related("account", "invited_by", "user").get()
        assert i1.account == a1
        assert i1.invited_by == u1
        assert i1.email == email
        assert i1.name == name
        assert i1.role == invitee_role
        assert i1.user is None
        assert i1.accepted_at is None
        assert i1.declined_at is None
        assert i1.expires_at == self.times.CloseTo(
            self.times.now + Invitation.default_expires_after
        )
        assert i1.secret_token
        assert i1.status == InvitationStatus.OPEN
        # And that the email was sent properly.
        assert len(self.mailoutbox) == 1
        ea1 = EmailAssertions(self.mailoutbox[-1])
        ea1.assert_is_invitation_email(
            i1, to_email="email2@example.com", subject=i1.headline, user_exists=False
        )

        # Follow the invitation.
        self.api_client.force_authenticate()
        follow_result = self.follow(
            api_client=self.api_client,
            email_assertions=ea1,
            strip_signature=(not has_email_signature),
            log_in_as_user_before_following=(
                other_user1 if logged_in_as_other_user_when_following_link else None
            ),
        )
        assert follow_result.invitation == i1
        assert follow_result.first_response_status_code == 302
        assert follow_result.redirect_link == "/follow-invitation"
        assert follow_result.second_response_status_code == 200
        assert follow_result.second_response_initial_data["extra"] == {
            "followInvitation": {
                "authenticatedUser": None,
                "canFollow": True,
                "existingUser": None,
                "followedThroughEmail": (
                    "email2@example.com" if has_email_signature else None
                ),
                "hasError": False,
                "invitation": dict(
                    camelize(
                        InvitationReadOnlySerializer(follow_result.invitation).data
                    )
                ),
                "inviteeIsAuthenticated": False,
                "requiresSignup": True,
                "shouldAutoAccept": False,
            },
            "signaling": {"immediatelyRedirectTo": "followInvitation"},
        }

        return self.InvitedNewUserSetup(
            a1=a1,
            a2=a2,
            u1=u1,
            other_user1=other_user1,
            other_membership1=other_membership1,
            create_response=create_response,
            i1=i1,
            ea1=ea1,
            follow_result=follow_result,
            initial_follow_extra=follow_result.second_response_initial_data["extra"],
        )

    def make_invited_existing_user_setup(
        self,
        *,
        initial_user_email: str = "email2@example.com",
        email: str = "email2@example.com",
        name: str = "John Doe",
        invitee_role: Role = Role.MEMBER,
        has_email_signature: bool = True,
        logged_in_as_other_user_when_following_link: bool = False,
        is_attached_to_user: bool = True,
        is_existing_user_authenticated: bool = False,
        existing_user_email_is_verified: bool = False,
    ) -> InvitedExistingUserSetup:
        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u1 = self.user_maker(account=a1, email="email1@example.com")
        other_user1 = self.user_maker(account=a2, email="email70@example.com")
        other_membership1 = self.membership_maker(
            account=a1, user=other_user1, role=Role.MEMBER
        )

        eu1 = self.user_maker(
            email=initial_user_email,
            password=self.strong_password + "#",
            email_is_verified=existing_user_email_is_verified,
            email_verified_as_of=(
                timezone.now() if existing_user_email_is_verified else None
            ),
            account__account_type=AccountType.PERSONAL,
        )

        # Create the invitation.
        self.api_client.force_authenticate(u1)
        create_response = self.create(
            account=a1.pk,
            email=email,
            name=name,
            role=invitee_role,
        )
        assert create_response.status_code == 201, create_response.data
        # Then check that it's present.
        i1 = Invitation.objects.select_related("account", "invited_by", "user").get()
        assert i1.account == a1
        assert i1.invited_by == u1
        assert i1.email == email
        assert i1.name == name
        assert i1.role == invitee_role
        if is_attached_to_user:
            assert i1.user == eu1
        else:
            assert i1.user is None
        assert i1.accepted_at is None
        assert i1.declined_at is None
        assert i1.expires_at == self.times.CloseTo(
            self.times.now + Invitation.default_expires_after
        )
        assert i1.secret_token
        assert i1.status == InvitationStatus.OPEN
        # And that the email was sent properly.
        assert len(self.mailoutbox) == 1
        ea1 = EmailAssertions(self.mailoutbox[-1])
        ea1.assert_is_invitation_email(
            i1,
            to_email="email2@example.com",
            subject=i1.headline,
            user_exists=True,
        )

        # Follow the invitation.
        if is_existing_user_authenticated:
            self.api_client.force_authenticate(eu1)
            self.api_client.force_login(eu1)
        else:
            self.api_client.force_authenticate()
        follow_result = self.follow(
            api_client=self.api_client,
            email_assertions=ea1,
            strip_signature=(not has_email_signature),
            log_in_as_user_before_following=(
                other_user1 if logged_in_as_other_user_when_following_link else None
            ),
        )
        assert follow_result.invitation == i1
        assert follow_result.first_response_status_code == 302
        assert follow_result.redirect_link == "/follow-invitation"
        assert follow_result.second_response_status_code == 200

        if (
            is_existing_user_authenticated
            and not logged_in_as_other_user_when_following_link
        ):
            follow_result.invitation.refresh_from_db()
            assert follow_result.second_response_initial_data["extra"] == {
                "followInvitation": {
                    "authenticatedUser": camelize(UserReadOnlySerializer(eu1).data),
                    "canFollow": True,
                    "existingUser": camelize(UserReadOnlySerializer(eu1).data),
                    "followedThroughEmail": (
                        "email2@example.com" if has_email_signature else None
                    ),
                    "hasError": False,
                    "invitation": dict(
                        camelize(
                            InvitationReadOnlySerializer(follow_result.invitation).data
                        )
                    ),
                    "inviteeIsAuthenticated": True,
                    "requiresSignup": False,
                    "shouldAutoAccept": existing_user_email_is_verified,
                },
                "signaling": {"immediatelyRedirectTo": "followInvitation"},
            }
        elif (
            is_existing_user_authenticated
            and logged_in_as_other_user_when_following_link
        ):
            follow_result.invitation.refresh_from_db()
            assert follow_result.second_response_initial_data["extra"] == {
                "followInvitation": {
                    "authenticatedUser": None,
                    "canFollow": True,
                    "existingUser": camelize(UserReadOnlySerializer(eu1).data),
                    "followedThroughEmail": (
                        "email2@example.com" if has_email_signature else None
                    ),
                    "hasError": False,
                    "invitation": dict(
                        camelize(
                            InvitationReadOnlySerializer(follow_result.invitation).data
                        )
                    ),
                    "inviteeIsAuthenticated": False,
                    "requiresSignup": False,
                    "shouldAutoAccept": False,
                },
                "signaling": {"immediatelyRedirectTo": "followInvitation"},
            }
        else:
            assert follow_result.second_response_initial_data["extra"] == {
                "followInvitation": {
                    "authenticatedUser": None,
                    "canFollow": True,
                    "existingUser": camelize(UserReadOnlySerializer(eu1).data),
                    "followedThroughEmail": (
                        "email2@example.com" if has_email_signature else None
                    ),
                    "hasError": False,
                    "invitation": dict(
                        camelize(
                            InvitationReadOnlySerializer(follow_result.invitation).data
                        )
                    ),
                    "inviteeIsAuthenticated": False,
                    "requiresSignup": False,
                    "shouldAutoAccept": False,
                },
                "signaling": {"immediatelyRedirectTo": "followInvitation"},
            }

        return self.InvitedExistingUserSetup(
            a1=a1,
            a2=a2,
            u1=u1,
            eu1=eu1,
            other_user1=other_user1,
            other_membership1=other_membership1,
            create_response=create_response,
            i1=i1,
            ea1=ea1,
            follow_result=follow_result,
            initial_follow_extra=follow_result.second_response_initial_data["extra"],
        )

    @pytest.mark.parametrize(
        "case",
        [
            "invitee_role_owner",
            "no_email_signature",
            "case_insensitive_email_follow",
            "logged_in_as_other_user_when_following_link",
            "logged_in_as_other_user_when_signing_up",
        ],
    )
    def test_successful_straightforward_flow_inviting_new_user(
        self,
        case: Literal[
            "invitee_role_owner",
            "no_email_signature",
            "case_insensitive_email_follow",
            "logged_in_as_other_user_when_following_link",
            "logged_in_as_other_user_when_signing_up",
        ],
    ):
        invited_email = "email2@example.com"
        email = (
            "EmaiL2@example.com"
            if case == "case_insensitive_email_follow"
            else invited_email
        )
        invited_role = Role.OWNER if case == "invitee_role_owner" else Role.MEMBER
        has_email_signature: bool = case != "no_email_signature"
        s = self.make_invited_new_user_setup(
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=(
                case == "logged_in_as_other_user_when_following_link"
            ),
        )

        if case == "logged_in_as_other_user_when_signing_up":
            self.api_client.force_authenticate(s.other_user1)
        ts_before_signup = timezone.now()
        r1 = self.signup(
            invitation_id=s.i1.pk,
            email=email,
            first_name="John",
            last_name="Doe",
            password=self.strong_password,
            password_confirm=self.strong_password,
        )
        s.i1.refresh_from_db()

        assert r1.status_code == 201
        asserted_against = self._assert_newly_created_invitee_details_correct(
            email=email,
            email_is_verified=(
                has_email_signature and case != "case_insensitive_email_follow"
            ),
            name="John Doe",
            invitation=s.i1,
            invitation_account=s.a1,
            role=invited_role,
            provided_ts_close_to_user_creation_time=ts_before_signup,
        )
        # NOTE: `ur1` stands for "underlying request", currently referring to the Django
        # `HttpRequest` object.
        ur1 = r1.wsgi_request
        expected_r1_data = get_all_data(
            context=RequestContext(ur1), request=ur1, camel_case=False
        ) | {
            # The CSRF token extracted from `ur1` will be different (likely) from the
            # actual correct one in these tests. That's fine, this (the `"csrf_token"`
            # exact comparison checking for correct logic) should be tested elsewhere.
            "csrf_token": IsStr(min_length=20),
            "new_membership": dict(
                MembershipReadOnlySerializer(asserted_against.m).data
            ),
        }
        assert r1.data == expected_r1_data

    def test_invited_new_user_can_sign_up_but_runs_into_validation_errors(self):
        invited_email = "email2@example.com"
        email = invited_email
        invited_role = Role.OWNER
        has_email_signature: bool = True
        s = self.make_invited_new_user_setup(
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
        )

        r1 = self.signup(
            invitation_id=s.i1.pk,
            email=email,
            first_name="John",
            last_name="Doe",
            password=self.strong_password,
            password_confirm=self.strong_password + "@",
        )
        assert r1.status_code == 400
        assert r1.data == {"password_confirm": ["Passwords do not match."]}

        r2 = self.signup(
            invitation_id=s.i1.pk,
            email="email3@example.com",
            first_name="John",
            last_name="Doe",
            password=self.strong_password,
            password_confirm=self.strong_password,
        )
        assert r2.status_code == 400
        assert r2.data == {
            "non_field_errors": [
                "The email address you are signing up with here does match the email "
                "address you were invited with. Either use that email address to "
                "signup here or signup from the regular signup page."
            ]
        }

        r3 = self.signup(
            invitation_id=s.i1.pk,
            email="email2@example.com",
            first_name="John",
            last_name="Doe",
            password="123456789",
            password_confirm="123456789",
        )
        assert r3.status_code == 400
        assert r3.data == {
            "password": [
                "This password is too common.",
                "This password is entirely numeric.",
                "Please include at least one special character (!@#$&*%?) in your password",
            ]
        }

        r41 = self.signup(
            invitation_id=s.i1.pk,
            email="email1@example.com",
            first_name="John",
            last_name="Doe",
            password=self.strong_password,
            password_confirm=self.strong_password,
        )

        assert r41.status_code == 400
        assert r41.data == {
            "non_field_errors": [
                "An account with that email address already exists. Either log in or "
                "double check the provided info and try again."
            ],
            "_main_code_": "existing_user",
        }

        r42 = self.signup(
            invitation_id=s.i1.pk,
            email="emaiL1@example.com",
            first_name="John",
            last_name="Doe",
            password=self.strong_password,
            password_confirm=self.strong_password,
        )

        assert r42.status_code == 400
        assert r42.data == {
            "non_field_errors": [
                "An account with that email address already exists. Either log in or "
                "double check the provided info and try again."
            ],
            "_main_code_": "existing_user",
        }

        r5 = self.signup(
            invitation_id=s.i1.pk,
            email="email2@example.com",
            first_name="John",
            last_name="Doe",
            password=self.strong_password,
            password_confirm=self.strong_password,
        )

        assert r5.status_code == 201

    def test_invited_new_user_cannot_sign_up_due_to_not_allowed_invitation_state(
        self, time_machine: TimeMachineFixture
    ):
        invited_email = "email2@example.com"
        email = invited_email
        invited_role = Role.OWNER
        has_email_signature: bool = True
        s = self.make_invited_new_user_setup(
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
        )
        i1 = s.i1
        default_signup_kwargs: dict[str, Any] = {
            "invitation_id": i1.pk,
            "email": email,
            "first_name": "John",
            "last_name": "Doe",
            "password": self.strong_password,
            "password_confirm": self.strong_password,
        }

        initial_now = self.times.now
        initial_expires_at = i1.expires_at
        # Make sure this is actually somewhat in the future.
        assert initial_expires_at > (initial_now + timedelta(minutes=8, seconds=45)), (
            "Current pre-condition"
        )

        updated_expires_at = initial_now + timedelta(minutes=25)
        i1.expires_at = updated_expires_at
        i1.__class__.objects.filter(pk=i1.pk).update(expires_at=updated_expires_at)

        with auto_rolling_back_transaction():
            time_machine.move_to(updated_expires_at + timedelta(seconds=3))
            r1 = self.signup(**default_signup_kwargs)
        self.mailoutbox.clear()
        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "The invitation has expired and cannot be accepted. Please ask the "
                "individual who invited you (email1@example.com) to send a new "
                "invitation."
            ]
        }

        with auto_rolling_back_transaction():
            # Make sure that it will work if just before the expiration time, etc.
            time_machine.move_to(updated_expires_at - timedelta(seconds=45))
            r2_api_client = deepcopy(self.api_client)
            r2 = self.signup(api_client=r2_api_client, **default_signup_kwargs)
        self.mailoutbox.clear()
        assert r2.status_code == 201

        time_machine.move_to(initial_now, tick=True)

        with auto_rolling_back_transaction():
            i1.declined_at = timezone.now()
            i1.save(update_fields=["declined_at"])
            assert i1.status == InvitationStatus.DECLINED
            r3 = self.signup(**default_signup_kwargs)
        self.mailoutbox.clear()
        assert r3.status_code == 400
        assert r3.data == {
            "non_field_errors": [
                "This invitation has already been declined and cannot be used now. If "
                "you'd like a new invitation, please ask the person who invited you to "
                "send another invitation."
            ]
        }

        with auto_rolling_back_transaction():
            i1.declined_at = None
            i1.accepted_at = timezone.now()
            i1.user = None
            i1.save(update_fields=["declined_at", "accepted_at", "user"])
            r41 = self.signup(**default_signup_kwargs)
        self.mailoutbox.clear()
        assert r41.status_code == 400
        assert r41.data == {
            "non_field_errors": ["This invitation has already been accepted."]
        }

        with auto_rolling_back_transaction():
            i1.accepted_at = timezone.now()
            i1.user = User.objects.get(email="email1@example.com")
            i1.save(update_fields=["accepted_at", "user"])
            r42 = self.signup(**default_signup_kwargs)
        self.mailoutbox.clear()
        assert r42.status_code == 400
        assert r42.data == {
            "non_field_errors": ["This invitation has already been accepted."]
        }

        r5 = self.signup(**default_signup_kwargs)

        assert r5.status_code == 201

    def test_invited_new_user_cannot_sign_up_due_to_email_not_found_in_session(self):
        invited_email = "email2@example.com"
        email = invited_email
        invited_role = Role.OWNER
        has_email_signature: bool = True
        s = self.make_invited_new_user_setup(
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
        )
        i1 = s.i1
        default_signup_kwargs: dict[str, Any] = {
            "invitation_id": i1.pk,
            "email": email,
            "first_name": "John",
            "last_name": "Doe",
            "password": self.strong_password,
            "password_confirm": self.strong_password,
        }

        api_client2 = APIClient()
        # Use a new `APIClient`, which means the session will be empty.
        r1 = self.signup(api_client=api_client2, **default_signup_kwargs)

        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "We couldn't find record of you following the invitation link for the "
                "invitation you're signing up with. Please follow the link again and "
                "try again. If there's still an issue, it could be that a previous "
                "browser session expired, or that something else went wrong. Also, "
                "browser cookies may be required for this portion of site "
                "functionality to work."
            ]
        }

        post_r1_ts = timezone.now()
        session_for_api_client2 = api_client2.session
        mark_invitation_as_followed_in_session(
            i1,
            session=session_for_api_client2,
            followed_through="email_link",
            followed_through_email="email3@example.com",
            followed_at=post_r1_ts,
        )
        session_for_api_client2.save()

        r2 = self.signup(
            api_client=api_client2,
            **(default_signup_kwargs | {"email": "email3@example.com"}),
        )
        assert r2.status_code == 400
        assert r2.data == {
            "non_field_errors": [
                "The email address you are signing up with here does match the email "
                "address you were invited with. Either use that email address to "
                "signup here or signup from the regular signup page."
            ]
        }

        post_r2_ts = timezone.now()
        mark_invitation_as_followed_in_session(
            i1,
            session=session_for_api_client2,
            followed_through="email_link",
            followed_through_email="email2@example.com",
            followed_at=post_r2_ts,
        )
        session_for_api_client2.save()

        r3 = self.signup(api_client=api_client2, **default_signup_kwargs)
        assert r3.status_code == 201, r3.data

    @pytest.mark.parametrize(
        "email_case_insensitive",
        [
            pytest.param(True, id="case_insensitive"),
            pytest.param(False, id="case_sensitive"),
        ],
    )
    def test_invited_new_user_cannot_sign_up_due_to_different_email_than_invitation_email(
        self,
        email_case_insensitive: bool,
    ):
        invited_email = "email2@example.com"
        email = invited_email
        invited_role = Role.OWNER
        has_email_signature: bool = True
        s = self.make_invited_new_user_setup(
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
        )
        i1 = s.i1
        default_signup_kwargs: dict[str, Any] = {
            "invitation_id": i1.pk,
            "email": email,
            "first_name": "John",
            "last_name": "Doe",
            "password": self.strong_password,
            "password_confirm": self.strong_password,
        }

        r1 = self.signup(**(default_signup_kwargs | {"email": "email3@example.com"}))

        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "The email address you are signing up with here does match the email "
                "address you were invited with. Either use that email address to "
                "signup here or signup from the regular signup page."
            ]
        }

        r2_email = (
            "emaiL2@example.com" if email_case_insensitive else "email2@example.com"
        )
        r2 = self.signup(**(default_signup_kwargs | {"email": r2_email}))
        assert r2.status_code == 201

    def test_another_user_cannot_hijack_new_user_invitation_in_session_after_logout(
        self,
    ):
        invited_email = "email2@example.com"
        email = invited_email
        invited_role = Role.OWNER
        has_email_signature: bool = True
        s = self.make_invited_new_user_setup(
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
        )
        i1 = s.i1
        default_signup_kwargs: dict[str, Any] = {
            "invitation_id": i1.pk,
            "email": email,
            "first_name": "John",
            "last_name": "Doe",
            "password": self.strong_password,
            "password_confirm": self.strong_password,
        }

        logout_response = self.api_client.post(drf_reverse("api:auth-logout"))
        assert logout_response.status_code == 200, "Pre-condition"

        r2 = self.signup(**default_signup_kwargs)
        assert r2.status_code == 400
        assert r2.data == {
            "non_field_errors": [
                "We couldn't find record of you following the invitation link for the "
                "invitation you're signing up with. Please follow the link again and "
                "try again. If there's still an issue, it could be that a previous "
                "browser session expired, or that something else went wrong. Also, "
                "browser cookies may be required for this portion of site "
                "functionality to work."
            ]
        }

    @pytest.mark.parametrize(
        "case",
        ["no_email_signature", "case_insensitive_email_follow"],
    )
    def test_no_second_signup_possible_even_if_account_deleted(
        self,
        case: Literal["no_email_signature", "case_insensitive_email_follow"],
    ):
        invited_email = "email2@example.com"
        email = (
            "EmaiL2@example.com"
            if case == "case_insensitive_email_follow"
            else invited_email
        )
        invited_role = Role.OWNER
        has_email_signature: bool = case != "no_email_signature"
        s = self.make_invited_new_user_setup(
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
        )

        ts_before_signup = timezone.now()
        r1 = self.signup(
            invitation_id=s.i1.pk,
            email=email,
            first_name="John",
            last_name="Doe",
            password=self.strong_password,
            password_confirm=self.strong_password,
        )
        s.i1.refresh_from_db()

        assert r1.status_code == 201
        asserted_against = self._assert_newly_created_invitee_details_correct(
            email=email,
            email_is_verified=(
                has_email_signature and case != "case_insensitive_email_follow"
            ),
            name="John Doe",
            invitation=s.i1,
            invitation_account=s.a1,
            role=invited_role,
            provided_ts_close_to_user_creation_time=ts_before_signup,
        )
        # NOTE: `ur1` stands for "underlying request", currently referring to the Django
        # `HttpRequest` object.
        ur1 = r1.wsgi_request
        expected_r1_data = get_all_data(
            context=RequestContext(ur1), request=ur1, camel_case=False
        ) | {
            # The CSRF token extracted from `ur1` will be different (likely) from the
            # actual correct one in these tests. That's fine, this (the `"csrf_token"`
            # exact comparison checking for correct logic) should be tested elsewhere.
            "csrf_token": IsStr(min_length=20),
            "new_membership": dict(
                MembershipReadOnlySerializer(asserted_against.m).data
            ),
        }
        assert r1.data == expected_r1_data

        m = asserted_against.m
        u = asserted_against.u
        pm = asserted_against.pm

        i1_pk = s.i1.pk
        pm.account.delete()
        pm.delete()
        m.delete()
        u.delete()

        r2 = self.signup(
            invitation_id=i1_pk,
            email=email,
            first_name="John",
            last_name="Doe",
            password=self.strong_password,
            password_confirm=self.strong_password,
        )
        assert r2.status_code == 400
        assert r2.data == {
            "invitation": [
                ErrorDetail(
                    string=f'Invalid pk "{i1_pk}" - object does not exist.',
                    code="does_not_exist",
                )
            ]
        }

    @pytest.mark.parametrize(
        "case",
        [
            "invitee_role_owner",
            "no_email_signature",
            "case_insensitive_email_follow",
            "logged_in_as_other_user_when_following_link",
            "logged_in_as_other_user_when_signing_up",
        ],
    )
    def test_link_follow_does_not_succeed(
        self,
        case: Literal[
            "invitee_role_owner",
            "no_email_signature",
            "case_insensitive_email_follow",
            "logged_in_as_other_user_when_following_link",
            "logged_in_as_other_user_when_signing_up",
        ],
        time_machine: TimeMachineFixture,
    ):
        email = "email2@example.com"
        name = "John Doe"
        invitee_role = Role.OWNER if case == "invitee_role_owner" else Role.MEMBER
        has_email_signature: bool = case != "no_email_signature"
        logged_in_as_other_user_when_following_link: bool = (
            case == "logged_in_as_other_user_when_following_link"
        )

        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u1 = self.user_maker(account=a1, email="email1@example.com")
        other_user1 = self.user_maker(account=a2, email="email70@example.com")
        other_membership1 = self.membership_maker(  # noqa: F841
            account=a1, user=other_user1, role=Role.MEMBER
        )

        # Create the invitation.
        self.api_client.force_authenticate(u1)
        create_response = self.create(
            account=a1.pk,
            email=email,
            name=name,
            role=invitee_role,
        )
        assert create_response.status_code == 201, create_response.data
        # Then check that it's present.
        i1 = Invitation.objects.select_related("account", "invited_by", "user").get()
        assert i1.account == a1
        assert i1.invited_by == u1
        assert i1.email == email
        assert i1.name == name
        assert i1.role == invitee_role
        assert i1.user is None
        assert i1.accepted_at is None
        assert i1.declined_at is None
        assert i1.expires_at == self.times.CloseTo(
            self.times.now + Invitation.default_expires_after
        )
        assert i1.secret_token
        assert i1.status == InvitationStatus.OPEN
        # And that the email was sent properly.
        assert len(self.mailoutbox) == 1
        ea1 = EmailAssertions(self.mailoutbox[-1])
        ea1.assert_is_invitation_email(
            i1, to_email="email2@example.com", subject=i1.headline, user_exists=False
        )

        def follow_and_check(
            *,
            check_invitation_followed: bool,
            check_invitation_followed_by_email: bool,
            first_response_status_code: int,
            redirect_link: str,
            second_response_status_code: int,
            authenticated_user: dict[str, Any] | None = None,
            can_follow: bool,
            existing_user: dict[str, Any] | None = None,
            followed_through_email: str | None = None,
            has_error: bool,
            invitation: dict[str, Any] | None,
            invitee_is_authenticated: bool | None,
            requires_signup: bool | Literal["unknown"],
            should_auto_accept: bool,
            error_message: str | None = None,
            error_code: str | None = None,
            follow_check_invitation_exists: bool = True,
            follow_use_passed_invitation: Invitation | None = None,
            signaling: dict[str, Any],
        ):
            # Follow the invitation.
            self.api_client.force_authenticate()
            follow_result = self.follow(
                api_client=self.api_client,
                email_assertions=ea1,
                check_invitation_followed=check_invitation_followed,
                check_invitation_followed_by_email=check_invitation_followed_by_email,
                strip_signature=(not has_email_signature),
                log_in_as_user_before_following=(
                    other_user1 if logged_in_as_other_user_when_following_link else None
                ),
                check_invitation_exists=follow_check_invitation_exists,
                use_passed_invitation=follow_use_passed_invitation,
            )
            assert follow_result.invitation == i1
            assert (
                follow_result.first_response_status_code == first_response_status_code
            )
            assert follow_result.redirect_link == redirect_link
            assert (
                follow_result.second_response_status_code == second_response_status_code
            )
            if can_follow and not has_error:
                assert follow_result.second_response_initial_data["extra"] == {
                    "followInvitation": {
                        "authenticatedUser": authenticated_user,
                        "canFollow": can_follow,
                        "existingUser": existing_user,
                        "followedThroughEmail": followed_through_email,
                        "hasError": has_error,
                        "invitation": invitation,
                        "inviteeIsAuthenticated": invitee_is_authenticated,
                        "requiresSignup": requires_signup,
                        "shouldAutoAccept": should_auto_accept,
                    },
                    "signaling": signaling,
                }
            else:
                assert follow_result.second_response_initial_data["extra"] == {
                    "followInvitation": {
                        "authenticatedUser": authenticated_user,
                        "canFollow": can_follow,
                        "existingUser": existing_user,
                        "followedThroughEmail": followed_through_email,
                        "hasError": has_error,
                        "invitation": invitation,
                        "inviteeIsAuthenticated": invitee_is_authenticated,
                        "requiresSignup": requires_signup,
                        "shouldAutoAccept": should_auto_accept,
                    },
                    "followInvitationError": {
                        "errorMessage": error_message,
                        "errorCode": error_code,
                    },
                    "signaling": signaling,
                }

        initial_now = self.times.now
        initial_expires_at = i1.expires_at
        # Make sure this is actually somewhat in the future, taking
        # `cannot_follow_within` into accoun.t
        assert initial_expires_at > (
            initial_now
            + timedelta(minutes=8, seconds=45)
            + Invitation.cannot_follow_within
        ), "Current pre-condition"

        updated_expires_at = initial_now + timedelta(minutes=25)
        i1.expires_at = updated_expires_at
        i1.__class__.objects.filter(pk=i1.pk).update(expires_at=updated_expires_at)

        with auto_rolling_back_transaction():
            time_machine.move_to(updated_expires_at + timedelta(seconds=3))
            follow_and_check(
                check_invitation_followed=False,
                check_invitation_followed_by_email=False,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=None,
                can_follow=False,
                existing_user=None,
                followed_through_email=None,
                has_error=True,
                invitation=None,
                invitee_is_authenticated=None,
                requires_signup="unknown",
                should_auto_accept=False,
                error_code="invalid",
                error_message=(
                    "Looks like that link has expired! Please request another "
                    "invitation from the person who invited you."
                ),
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )
        self.mailoutbox.clear()

        with auto_rolling_back_transaction():
            time_machine.move_to(
                updated_expires_at
                + timedelta(seconds=3)
                - Invitation.cannot_follow_within
            )
            follow_and_check(
                check_invitation_followed=False,
                check_invitation_followed_by_email=False,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=None,
                can_follow=False,
                existing_user=None,
                followed_through_email=None,
                has_error=True,
                invitation=None,
                invitee_is_authenticated=None,
                requires_signup="unknown",
                should_auto_accept=False,
                error_code="invalid",
                error_message=(
                    "Looks like that link has expired! Please request another "
                    "invitation from the person who invited you."
                ),
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )
        self.mailoutbox.clear()

        with auto_rolling_back_transaction():
            time_machine.move_to(
                updated_expires_at
                - timedelta(seconds=45)
                - Invitation.cannot_follow_within
            )
            i1.refresh_from_db()
            follow_and_check(
                check_invitation_followed=True,
                check_invitation_followed_by_email=True,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=None,
                can_follow=True,
                existing_user=None,
                followed_through_email=(
                    "email2@example.com" if has_email_signature else None
                ),
                has_error=False,
                invitation=dict(camelize(InvitationReadOnlySerializer(i1).data)),
                invitee_is_authenticated=False,
                requires_signup=True,
                should_auto_accept=False,
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )
        self.mailoutbox.clear()
        time_machine.move_to(initial_now, tick=True)

        with auto_rolling_back_transaction():
            i1.declined_at = timezone.now()
            i1.save(update_fields=["declined_at"])
            assert i1.status == InvitationStatus.DECLINED
            follow_and_check(  # type: ignore[unreachable]
                check_invitation_followed=False,
                check_invitation_followed_by_email=False,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=None,
                can_follow=False,
                existing_user=None,
                followed_through_email=None,
                has_error=True,
                invitation=None,
                invitee_is_authenticated=None,
                requires_signup="unknown",
                should_auto_accept=False,
                error_code="invalid",
                error_message=(
                    "Looks like that link has expired! Please request another "
                    "invitation from the person who invited you."
                ),
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )
        self.mailoutbox.clear()  # type: ignore[unreachable]

        with auto_rolling_back_transaction():
            i1.declined_at = None
            i1.accepted_at = timezone.now()
            i1.user = None
            i1.save(update_fields=["declined_at", "accepted_at", "user"])
            follow_and_check(
                check_invitation_followed=False,
                check_invitation_followed_by_email=False,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=None,
                can_follow=False,
                existing_user=None,
                followed_through_email=None,
                has_error=True,
                invitation=None,
                invitee_is_authenticated=None,
                requires_signup="unknown",
                should_auto_accept=False,
                error_code="invalid",
                error_message=(
                    "Looks like that link has expired! Please request another "
                    "invitation from the person who invited you."
                ),
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )

        with auto_rolling_back_transaction():
            i1.declined_at = None
            i1.accepted_at = None
            i1.user = None
            i1.secret_token = "token12345"
            i1.save(
                update_fields=["declined_at", "accepted_at", "user", "secret_token"]
            )
            follow_and_check(
                check_invitation_followed=False,
                check_invitation_followed_by_email=False,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=None,
                can_follow=False,
                existing_user=None,
                followed_through_email=None,
                has_error=True,
                invitation=None,
                invitee_is_authenticated=None,
                requires_signup="unknown",
                should_auto_accept=False,
                error_code="invalid",
                error_message=(
                    "Looks like that link has expired! Please request another "
                    "invitation from the person who invited you."
                ),
                follow_check_invitation_exists=False,
                follow_use_passed_invitation=i1,
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )

    # ---                    ---

    # --- Invitee - New User - May or May Not Be Not Already Authenticated ---

    @pytest.mark.parametrize(
        "case",
        [
            "invitee_role_owner",
            "no_email_signature",
            "case_insensitive_email_follow",
            "logged_in_as_other_user_when_following_link",
            "logged_in_as_other_user_when_logging_in",
            "logged_in_as_self_before_following_link",
        ],
    )
    def test_successful_straightforward_flow_inviting_existing_user(
        self,
        case: Literal[
            "invitee_role_owner",
            "no_email_signature",
            "case_insensitive_email_follow",
            "logged_in_as_other_user_when_following_link",
            "logged_in_as_other_user_when_logging_in",
            "logged_in_as_self_before_following_link",
        ],
    ):
        invited_email = "email2@example.com"
        email = (
            "EmaiL2@example.com"
            if case == "case_insensitive_email_follow"
            else invited_email
        )
        invited_role = Role.OWNER if case == "invitee_role_owner" else Role.MEMBER
        has_email_signature: bool = case != "no_email_signature"
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=(
                case == "logged_in_as_other_user_when_following_link"
            ),
            is_attached_to_user=(case != "case_insensitive_email_follow"),
            is_existing_user_authenticated=(
                case == "logged_in_as_self_before_following_link"
            ),
        )

        if case == "logged_in_as_other_user_when_logging_in":
            self.api_client.force_authenticate(s.other_user1)
        ts_before_login = timezone.now()
        r1 = self.login(
            invitation_id=s.i1.pk,
            email=email,
            password=(self.strong_password + "#"),
        )
        s.i1.refresh_from_db()

        assert r1.status_code == 200
        asserted_against = self._assert_existing_invitee_details_correct(
            email=email,
            email_is_verified=(
                has_email_signature and case != "case_insensitive_email_follow"
            ),
            name=s.eu1.name,
            invitation=s.i1,
            invitation_account=s.a1,
            role=invited_role,
            provided_ts_close_to_invitation_login_time=ts_before_login,
        )
        # NOTE: `ur1` stands for "underlying request", currently referring to the Django
        # `HttpRequest` object.
        ur1 = r1.wsgi_request
        expected_r1_data = get_all_data(
            context=RequestContext(ur1), request=ur1, camel_case=False
        ) | {
            # The CSRF token extracted from `ur1` will be different (likely) from the
            # actual correct one in these tests. That's fine, this (the `"csrf_token"`
            # exact comparison checking for correct logic) should be tested elsewhere.
            "csrf_token": IsStr(min_length=20),
            "new_membership": dict(
                MembershipReadOnlySerializer(asserted_against.m).data
            ),
        }
        assert r1.data == expected_r1_data

    @pytest.mark.parametrize(
        "email_case_insensitive",
        [
            pytest.param(True, id="email_case_insensitive"),
            pytest.param(False, id="email_case_sensitive"),
        ],
    )
    def test_invited_existing_user_can_login_but_runs_into_validation_errors(
        self,
        email_case_insensitive: bool,
    ):
        invited_email = "email2@example.com"
        email = "EmaiL2@example.com" if email_case_insensitive else invited_email
        invited_role = Role.OWNER
        has_email_signature: bool = True
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
            is_attached_to_user=(not email_case_insensitive),
        )

        r1 = self.login(
            invitation_id=s.i1.pk,
            email=email,
            password="wrong_password",
        )
        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": ["Incorrect password."],
            "_main_code_": "incorrect_password",
        }

        r2 = self.login(
            invitation_id=s.i1.pk,
            email="email3@example.com",
            password=self.strong_password,
        )
        assert r2.status_code == 400
        assert r2.data == {
            "non_field_errors": [
                "We don't have an account on file for that email address. Either sign "
                "up or double check the provided info and try again."
            ],
            "_main_code_": "no_user",
        }

        s.eu1.is_active = False
        s.eu1.set_password("new_password123@8fsd")
        s.eu1.save(update_fields=["is_active", "password", "modified"])

        r3 = self.login(
            invitation_id=s.i1.pk,
            email=email,
            password="new_password123@8fsd",
        )
        assert r3.status_code == 400
        assert r3.data == {
            "non_field_errors": [
                "This account is inactive. Please contact support to reactivate it."
            ],
            "_main_code_": "inactive",
        }

        s.eu1.is_active = True
        s.eu1.save(update_fields=["is_active", "modified"])

        r4 = self.login(
            invitation_id=s.i1.pk,
            email=email,
            password="new_password123@8fsd",
        )
        self.mailoutbox.clear()
        assert r4.status_code == 200

    @pytest.mark.parametrize(
        "email_case_insensitive",
        [
            pytest.param(True, id="email_case_insensitive"),
            pytest.param(False, id="email_case_sensitive"),
        ],
    )
    def test_invited_existing_user_cannot_login_due_to_not_allowed_invitation_state(
        self,
        time_machine: TimeMachineFixture,
        email_case_insensitive: bool,
    ):
        invited_email = "email2@example.com"
        email = "EmaiL2@example.com" if email_case_insensitive else invited_email
        invited_role = Role.OWNER
        has_email_signature: bool = True
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
            is_attached_to_user=(not email_case_insensitive),
        )
        i1 = s.i1
        default_login_kwargs: dict[str, Any] = {
            "invitation_id": i1.pk,
            "email": email,
            "password": self.strong_password + "#",
        }

        initial_now = self.times.now
        initial_expires_at = i1.expires_at
        # Make sure this is actually somewhat in the future.
        assert initial_expires_at > (initial_now + timedelta(minutes=8, seconds=45)), (
            "Current pre-condition"
        )

        updated_expires_at = initial_now + timedelta(minutes=25)
        i1.expires_at = updated_expires_at
        i1.__class__.objects.filter(pk=i1.pk).update(expires_at=updated_expires_at)

        with auto_rolling_back_transaction():
            time_machine.move_to(updated_expires_at + timedelta(seconds=3))
            r1 = self.login(**default_login_kwargs)
        self.mailoutbox.clear()
        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "The invitation has expired and cannot be accepted. Please ask the "
                "individual who invited you (email1@example.com) to send a new "
                "invitation."
            ]
        }

        with auto_rolling_back_transaction():
            # Make sure that it will work if just before the expiration time, etc.
            time_machine.move_to(updated_expires_at - timedelta(seconds=45))
            r2_api_client = deepcopy(self.api_client)
            r2 = self.login(api_client=r2_api_client, **default_login_kwargs)
        self.mailoutbox.clear()
        assert r2.status_code == 200

        time_machine.move_to(initial_now, tick=True)

        with auto_rolling_back_transaction():
            i1.declined_at = timezone.now()
            i1.save(update_fields=["declined_at"])
            assert i1.status == InvitationStatus.DECLINED
            r3 = self.login(**default_login_kwargs)
        self.mailoutbox.clear()
        assert r3.status_code == 400
        assert r3.data == {
            "non_field_errors": [
                "This invitation has already been declined and cannot be used now. If "
                "you'd like a new invitation, please ask the person who invited you to "
                "send another invitation."
            ]
        }

        with auto_rolling_back_transaction():
            i1.declined_at = None
            i1.accepted_at = timezone.now()
            i1.user = None
            i1.save(update_fields=["declined_at", "accepted_at", "user"])
            r41 = self.login(**default_login_kwargs)
        self.mailoutbox.clear()
        assert r41.status_code == 400
        assert r41.data == {
            "non_field_errors": ["This invitation has already been accepted."]
        }

        with auto_rolling_back_transaction():
            i1.accepted_at = timezone.now()
            i1.user = User.objects.get(email="email1@example.com")
            i1.save(update_fields=["accepted_at", "user"])
            r42 = self.login(**default_login_kwargs)
        self.mailoutbox.clear()
        assert r42.status_code == 400
        assert r42.data == {
            "non_field_errors": ["This invitation has already been accepted."]
        }

        r5 = self.login(**default_login_kwargs)

        assert r5.status_code == 200

    @pytest.mark.parametrize(
        "email_case_insensitive",
        [
            pytest.param(True, id="email_case_insensitive"),
            pytest.param(False, id="email_case_sensitive"),
        ],
    )
    def test_invited_existing_user_cannot_login_due_to_email_not_found_in_session(
        self,
        email_case_insensitive: bool,
    ):
        invited_email = "email2@example.com"
        email = "EmaiL2@example.com" if email_case_insensitive else invited_email
        invited_role = Role.OWNER
        has_email_signature: bool = True
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
            is_attached_to_user=(not email_case_insensitive),
        )
        i1 = s.i1
        default_login_kwargs: dict[str, Any] = {
            "invitation_id": i1.pk,
            "email": email,
            "password": self.strong_password + "#",
        }

        api_client2 = APIClient()
        # Use a new `APIClient`, which means the session will be empty.
        r1 = self.login(api_client=api_client2, **default_login_kwargs)

        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "We couldn't find record of you following the invitation link for the "
                "invitation you're logging in for. Please follow the link again and "
                "try again. If there's still an issue, it could be that a previous "
                "browser session expired, or that something else went wrong. Also, "
                "browser cookies may be required for this portion of site "
                "functionality to work."
            ]
        }

        post_r1_ts = timezone.now()
        session_for_api_client2 = api_client2.session
        mark_invitation_as_followed_in_session(
            i1,
            session=session_for_api_client2,
            followed_through="email_link",
            followed_through_email="email3@example.com",
            followed_at=post_r1_ts,
        )
        session_for_api_client2.save()

        r2 = self.login(
            api_client=api_client2,
            **(default_login_kwargs | {"email": "email3@example.com"}),
        )
        assert r2.status_code == 400
        assert r2.data == {
            "non_field_errors": [
                "We don't have an account on file for that email address. Either sign "
                "up or double check the provided info and try again."
            ],
            "_main_code_": "no_user",
        }

        post_r2_ts = timezone.now()
        mark_invitation_as_followed_in_session(
            i1,
            session=session_for_api_client2,
            followed_through="email_link",
            followed_through_email="email2@example.com",
            followed_at=post_r2_ts,
        )
        session_for_api_client2.save()

        r3 = self.login(api_client=api_client2, **default_login_kwargs)
        assert r3.status_code == 200, r3.data

    @pytest.mark.parametrize(
        "email_case_insensitive",
        [
            pytest.param(True, id="email_case_insensitive"),
            pytest.param(False, id="email_case_sensitive"),
        ],
    )
    def test_invited_existing_user_cannot_login_due_to_different_email_than_invitation_email(
        self,
        email_case_insensitive: bool,
    ):
        eu2 = self.user_maker(
            email="email3@example.com",
            password=self.strong_password + "*",
            email_is_verified=True,
            email_verified_as_of=timezone.now(),
            account__account_type=AccountType.PERSONAL,
        )
        assert Membership.objects.filter(user=eu2).count() == 1, "Pre-condition"

        invited_email = "email2@example.com"
        email = "EmaiL2@example.com" if email_case_insensitive else invited_email
        invited_role = Role.OWNER
        has_email_signature: bool = True
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
            is_attached_to_user=(not email_case_insensitive),
        )
        i1 = s.i1
        default_login_kwargs: dict[str, Any] = {
            "invitation_id": i1.pk,
            "email": eu2.email,
            "password": (self.strong_password + "*"),
        }

        r1 = self.login(**default_login_kwargs)
        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "This invitation cannot be accepted likely because your logged in email "
                "address does not exactly match the invited email address. To fix, "
                "please click on the invitation link sent to your email address and "
                "log in with that email address."
            ],
        }

        assert Membership.objects.filter(user=eu2).count() == 1

    def test_another_user_cannot_hijack_existing_user_invitation_in_session_after_logout(
        self,
    ):
        invited_email = "email2@example.com"
        email = invited_email
        invited_role = Role.OWNER
        has_email_signature: bool = True
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
        )
        i1 = s.i1
        default_login_kwargs: dict[str, Any] = {
            "invitation_id": i1.pk,
            "email": email,
            "password": (self.strong_password + "#"),
        }

        logout_response = self.api_client.post(drf_reverse("api:auth-logout"))
        assert logout_response.status_code == 200, "Pre-condition"

        r2 = self.login(**default_login_kwargs)
        assert r2.status_code == 400
        assert r2.data == {
            "non_field_errors": [
                "We couldn't find record of you following the invitation link for the "
                "invitation you're logging in for. Please follow the link again and "
                "try again. If there's still an issue, it could be that a previous "
                "browser session expired, or that something else went wrong. Also, "
                "browser cookies may be required for this portion of site "
                "functionality to work."
            ]
        }

    @pytest.mark.parametrize(
        "email_is_verified",
        [
            pytest.param(True, id="email_is_verified"),
            pytest.param(False, id="email_is_not_verified"),
        ],
    )
    @pytest.mark.parametrize(
        "case",
        [
            "invitee_role_owner",
            "no_email_signature",
            "case_insensitive_email_follow",
            "existing_user_is_authenticated",
        ],
    )
    def test_link_follow_does_not_succeed_for_existing_user(
        self,
        case: Literal[
            "invitee_role_owner",
            "no_email_signature",
            "case_insensitive_email_follow",
            "existing_user_is_authenticated",
        ],
        time_machine: TimeMachineFixture,
        email_is_verified: bool,
    ):
        invited_email = "email2@example.com"
        email = (
            "EmaiL2@example.com"
            if case == "case_insensitive_email_follow"
            else invited_email
        )
        name = "John Doe"
        invitee_role = Role.OWNER if case == "invitee_role_owner" else Role.MEMBER
        has_email_signature: bool = case != "no_email_signature"
        existing_user_is_authenticated: bool = case == "existing_user_is_authenticated"
        a1 = self.account_maker(account_type=AccountType.TEAM)
        a2 = self.account_maker(account_type=AccountType.TEAM)
        u1 = self.user_maker(account=a1, email="email1@example.com")
        other_user1 = self.user_maker(account=a2, email="email70@example.com")
        other_membership1 = self.membership_maker(  # noqa: F841
            account=a1, user=other_user1, role=Role.MEMBER
        )

        eu1 = self.user_maker(
            email=email,
            email_is_verified=email_is_verified,
            email_verified_as_of=(timezone.now() if email_is_verified else None),
            account__account_type=AccountType.PERSONAL,
        )

        # Create the invitation.
        self.api_client.force_authenticate(u1)
        create_response = self.create(
            account=a1.pk,
            email=invited_email,
            name=name,
            role=invitee_role,
        )
        assert create_response.status_code == 201, create_response.data
        # Then check that it's present.
        i1 = Invitation.objects.select_related("account", "invited_by", "user").get()
        assert i1.account == a1
        assert i1.invited_by == u1
        assert i1.email == invited_email
        assert i1.name == name
        assert i1.role == invitee_role
        if case == "case_insensitive_email_follow":
            assert i1.user is None
        else:
            assert i1.user == eu1
        assert i1.accepted_at is None
        assert i1.declined_at is None
        assert i1.expires_at == self.times.CloseTo(
            self.times.now + Invitation.default_expires_after
        )
        assert i1.secret_token
        assert i1.status == InvitationStatus.OPEN
        # And that the email was sent properly.
        assert len(self.mailoutbox) == 1
        ea1 = EmailAssertions(self.mailoutbox[-1])
        ea1.assert_is_invitation_email(
            i1,
            to_email=invited_email,
            subject=i1.headline,
            user_exists=True,
        )

        def follow_and_check(
            *,
            check_invitation_followed: bool,
            check_invitation_followed_by_email: bool,
            first_response_status_code: int,
            redirect_link: str,
            second_response_status_code: int,
            authenticated_user: dict[str, Any] | None = None,
            can_follow: bool,
            existing_user: dict[str, Any] | None = None,
            followed_through_email: str | None = None,
            has_error: bool,
            invitation: dict[str, Any] | None,
            invitee_is_authenticated: bool | None,
            requires_signup: bool | Literal["unknown"],
            should_auto_accept: bool,
            error_message: str | None = None,
            error_code: str | None = None,
            follow_check_invitation_exists: bool = True,
            follow_use_passed_invitation: Invitation | None = None,
            signaling: dict[str, Any],
        ):
            # Follow the invitation.
            self.api_client.force_authenticate()
            follow_result = self.follow(
                api_client=self.api_client,
                email_assertions=ea1,
                check_invitation_followed=check_invitation_followed,
                check_invitation_followed_by_email=check_invitation_followed_by_email,
                strip_signature=(not has_email_signature),
                log_in_as_user_before_following=(
                    eu1 if existing_user_is_authenticated else None
                ),
                check_invitation_exists=follow_check_invitation_exists,
                use_passed_invitation=follow_use_passed_invitation,
            )
            assert follow_result.invitation == i1
            assert (
                follow_result.first_response_status_code == first_response_status_code
            )
            assert follow_result.redirect_link == redirect_link
            assert (
                follow_result.second_response_status_code == second_response_status_code
            )

            if existing_user_is_authenticated and authenticated_user:
                authenticated_user = camelize(
                    UserReadOnlySerializer(
                        User.objects.get(pk=authenticated_user["id"])
                    ).data
                )
            if (
                existing_user_is_authenticated
                and authenticated_user
                and existing_user
                and authenticated_user["id"] == existing_user["id"]
            ):
                existing_user = authenticated_user
            if invitation and invitation["user"] and invitation["user"]["id"]:
                invitation["user"] = camelize(
                    UserReadOnlySerializer(
                        User.objects.get(pk=invitation["user"]["id"])
                    ).data
                )

            if can_follow and not has_error:
                assert follow_result.second_response_initial_data["extra"] == {
                    "followInvitation": {
                        "authenticatedUser": authenticated_user,
                        "canFollow": can_follow,
                        "existingUser": existing_user,
                        "followedThroughEmail": followed_through_email,
                        "hasError": has_error,
                        "invitation": invitation,
                        "inviteeIsAuthenticated": invitee_is_authenticated,
                        "requiresSignup": requires_signup,
                        "shouldAutoAccept": should_auto_accept,
                    },
                    "signaling": signaling,
                }
            else:
                assert follow_result.second_response_initial_data["extra"] == {
                    "followInvitation": {
                        "authenticatedUser": authenticated_user,
                        "canFollow": can_follow,
                        "existingUser": existing_user,
                        "followedThroughEmail": followed_through_email,
                        "hasError": has_error,
                        "invitation": invitation,
                        "inviteeIsAuthenticated": invitee_is_authenticated,
                        "requiresSignup": requires_signup,
                        "shouldAutoAccept": should_auto_accept,
                    },
                    "followInvitationError": {
                        "errorMessage": error_message,
                        "errorCode": error_code,
                    },
                    "signaling": signaling,
                }

        initial_now = self.times.now
        initial_expires_at = i1.expires_at
        # Make sure this is actually somewhat in the future, taking
        # `cannot_follow_within` into accoun.t
        assert initial_expires_at > (
            initial_now
            + timedelta(minutes=8, seconds=45)
            + Invitation.cannot_follow_within
        ), "Current pre-condition"

        updated_expires_at = initial_now + timedelta(minutes=25)
        i1.expires_at = updated_expires_at
        i1.__class__.objects.filter(pk=i1.pk).update(expires_at=updated_expires_at)

        with auto_rolling_back_transaction():
            time_machine.move_to(updated_expires_at + timedelta(seconds=3))
            follow_and_check(
                check_invitation_followed=False,
                check_invitation_followed_by_email=False,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=(
                    camelize(UserReadOnlySerializer(eu1).data)
                    if existing_user_is_authenticated
                    else None
                ),
                can_follow=False,
                existing_user=None,
                followed_through_email=None,
                has_error=True,
                invitation=None,
                invitee_is_authenticated=None,
                requires_signup="unknown",
                should_auto_accept=False,
                error_code="invalid",
                error_message=(
                    "Looks like that link has expired! Please request another "
                    "invitation from the person who invited you."
                ),
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )
        self.mailoutbox.clear()

        with auto_rolling_back_transaction():
            time_machine.move_to(
                updated_expires_at
                + timedelta(seconds=3)
                - Invitation.cannot_follow_within
            )
            follow_and_check(
                check_invitation_followed=False,
                check_invitation_followed_by_email=False,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=(
                    camelize(UserReadOnlySerializer(eu1).data)
                    if existing_user_is_authenticated
                    else None
                ),
                can_follow=False,
                existing_user=None,
                followed_through_email=None,
                has_error=True,
                invitation=None,
                invitee_is_authenticated=None,
                requires_signup="unknown",
                should_auto_accept=False,
                error_code="invalid",
                error_message=(
                    "Looks like that link has expired! Please request another "
                    "invitation from the person who invited you."
                ),
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )
        self.mailoutbox.clear()

        with auto_rolling_back_transaction():
            time_machine.move_to(
                updated_expires_at
                - timedelta(seconds=45)
                - Invitation.cannot_follow_within
            )
            if existing_user_is_authenticated:
                eu1.refresh_from_db()
                if i1.user is not None:
                    i1.user.refresh_from_db()
            i1.refresh_from_db()
            follow_and_check(
                check_invitation_followed=True,
                check_invitation_followed_by_email=True,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=(
                    camelize(UserReadOnlySerializer(eu1).data)
                    if existing_user_is_authenticated
                    else None
                ),
                can_follow=True,
                existing_user=camelize(UserReadOnlySerializer(eu1).data),
                followed_through_email=(
                    "email2@example.com" if has_email_signature else None
                ),
                has_error=False,
                invitation=dict(camelize(InvitationReadOnlySerializer(i1).data)),
                invitee_is_authenticated=existing_user_is_authenticated,
                requires_signup=False,
                should_auto_accept=(
                    existing_user_is_authenticated and email_is_verified
                ),
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )
        self.mailoutbox.clear()
        time_machine.move_to(initial_now, tick=True)

        with auto_rolling_back_transaction():
            i1.declined_at = timezone.now()
            i1.save(update_fields=["declined_at"])
            assert i1.status == InvitationStatus.DECLINED
            follow_and_check(  # type: ignore[unreachable]
                check_invitation_followed=False,
                check_invitation_followed_by_email=False,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=(
                    camelize(UserReadOnlySerializer(eu1).data)
                    if existing_user_is_authenticated
                    else None
                ),
                can_follow=False,
                existing_user=None,
                followed_through_email=None,
                has_error=True,
                invitation=None,
                invitee_is_authenticated=None,
                requires_signup="unknown",
                should_auto_accept=False,
                error_code="invalid",
                error_message=(
                    "Looks like that link has expired! Please request another "
                    "invitation from the person who invited you."
                ),
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )
        self.mailoutbox.clear()  # type: ignore[unreachable]

        with auto_rolling_back_transaction():
            i1.declined_at = None
            i1.accepted_at = timezone.now()
            i1.user = None
            i1.save(update_fields=["declined_at", "accepted_at", "user"])
            follow_and_check(
                check_invitation_followed=False,
                check_invitation_followed_by_email=False,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=(
                    camelize(UserReadOnlySerializer(eu1).data)
                    if existing_user_is_authenticated
                    else None
                ),
                can_follow=False,
                existing_user=None,
                followed_through_email=None,
                has_error=True,
                invitation=None,
                invitee_is_authenticated=None,
                requires_signup="unknown",
                should_auto_accept=False,
                error_code="invalid",
                error_message=(
                    "Looks like that link has expired! Please request another "
                    "invitation from the person who invited you."
                ),
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )

        with auto_rolling_back_transaction():
            i1.declined_at = None
            i1.accepted_at = None
            i1.user = None
            i1.secret_token = "token12345"
            i1.save(
                update_fields=["declined_at", "accepted_at", "user", "secret_token"]
            )
            follow_and_check(
                check_invitation_followed=False,
                check_invitation_followed_by_email=False,
                first_response_status_code=302,
                redirect_link="/follow-invitation",
                second_response_status_code=200,
                authenticated_user=None,
                can_follow=False,
                existing_user=None,
                followed_through_email=None,
                has_error=True,
                invitation=None,
                invitee_is_authenticated=None,
                requires_signup="unknown",
                should_auto_accept=False,
                error_code="invalid",
                error_message=(
                    "Looks like that link has expired! Please request another "
                    "invitation from the person who invited you."
                ),
                follow_check_invitation_exists=False,
                follow_use_passed_invitation=i1,
                signaling={"immediatelyRedirectTo": "followInvitation"},
            )

    # ---                                                                  ---

    # --- Invitee - Existing User - Already Authenticated ---

    @pytest.mark.parametrize(
        "case",
        [
            "invitee_role_owner",
            "no_email_signature",
            "case_insensitive_email_follow",
            "logged_in_as_other_user_when_following_link",
        ],
    )
    @pytest.mark.parametrize(
        "existing_user_email_is_verified",
        [
            pytest.param(True, id="existing_user_email_is_verified"),
            pytest.param(False, id="existing_user_email_is_not_verified"),
        ],
    )
    def test_successful_straightforward_flow_inviting_existing_and_authenticated_user(
        self,
        case: Literal[
            "invitee_role_owner",
            "no_email_signature",
            "case_insensitive_email_follow",
            "logged_in_as_other_user_when_following_link",
        ],
        existing_user_email_is_verified: bool,
    ):
        invited_email = "email2@example.com"
        email = (
            "EmaiL2@example.com"
            if case == "case_insensitive_email_follow"
            else invited_email
        )
        invited_role = Role.OWNER if case == "invitee_role_owner" else Role.MEMBER
        has_email_signature: bool = case != "no_email_signature"
        ts_before_follow = timezone.now()
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=(
                case == "logged_in_as_other_user_when_following_link"
            ),
            is_attached_to_user=(case != "case_insensitive_email_follow"),
            is_existing_user_authenticated=True,
            existing_user_email_is_verified=existing_user_email_is_verified,
        )
        assert Membership.objects.filter(user=s.eu1).count() == 1

        s.i1.refresh_from_db()
        fr1 = s.follow_result
        eu1 = s.eu1
        eu1.refresh_from_db()
        eu1_pre_login_snapshot = deepcopy(eu1)
        i1_pre_login_snapshot = deepcopy(s.i1)
        if i1_pre_login_snapshot.user is not None:
            i1_pre_login_snapshot.user.refresh_from_db()

        should_auto_accept = fr1.second_response_initial_data["extra"][
            "followInvitation"
        ]["shouldAutoAccept"]
        assert should_auto_accept in (True, False), "Pre-condition"
        if (
            not existing_user_email_is_verified
            and case != "logged_in_as_other_user_when_following_link"
        ):
            assert should_auto_accept is False
        elif case == "logged_in_as_other_user_when_following_link":
            assert should_auto_accept is False
        else:
            assert should_auto_accept is existing_user_email_is_verified
        if should_auto_accept is True:
            r2 = self.accept(invitation_id=s.i1.pk, email=email)
            assert r2.status_code == 201, r2.data
        else:
            r2 = None

        s.i1.refresh_from_db()
        eu1.refresh_from_db()

        if (
            not existing_user_email_is_verified
            and case != "logged_in_as_other_user_when_following_link"
        ):
            assert fr1.second_response_status_code == 200
            assert fr1.second_response_initial_data["extra"] == {
                "followInvitation": {
                    "authenticatedUser": camelize(
                        UserReadOnlySerializer(eu1_pre_login_snapshot).data
                    ),
                    "canFollow": True,
                    "existingUser": camelize(
                        UserReadOnlySerializer(eu1_pre_login_snapshot).data
                    ),
                    "followedThroughEmail": (
                        "email2@example.com" if has_email_signature else None
                    ),
                    "hasError": False,
                    "invitation": dict(
                        camelize(
                            InvitationReadOnlySerializer(i1_pre_login_snapshot).data
                        )
                    ),
                    "inviteeIsAuthenticated": True,
                    "requiresSignup": False,
                    "shouldAutoAccept": False,
                },
                "signaling": {"immediatelyRedirectTo": "followInvitation"},
            }
            asserted_against = None
            assert r2 is None
            assert Membership.objects.filter(user=eu1).count() == 1
        elif case == "logged_in_as_other_user_when_following_link":
            assert fr1.second_response_status_code == 200
            assert fr1.second_response_initial_data["extra"] == {
                "followInvitation": {
                    "authenticatedUser": None,
                    "canFollow": True,
                    "existingUser": camelize(
                        UserReadOnlySerializer(eu1_pre_login_snapshot).data
                    ),
                    "followedThroughEmail": (
                        "email2@example.com" if has_email_signature else None
                    ),
                    "hasError": False,
                    "invitation": dict(
                        camelize(
                            InvitationReadOnlySerializer(i1_pre_login_snapshot).data
                        )
                    ),
                    "inviteeIsAuthenticated": False,
                    "requiresSignup": False,
                    "shouldAutoAccept": False,
                },
                "signaling": {"immediatelyRedirectTo": "followInvitation"},
            }
            asserted_against = None
            assert r2 is None
            assert Membership.objects.filter(user=eu1).count() == 1
        else:
            assert fr1.second_response_status_code == 200
            assert fr1.second_response_initial_data["extra"] == {
                "followInvitation": {
                    "authenticatedUser": camelize(
                        UserReadOnlySerializer(eu1_pre_login_snapshot).data
                    ),
                    "canFollow": True,
                    "existingUser": camelize(
                        UserReadOnlySerializer(eu1_pre_login_snapshot).data
                    ),
                    "followedThroughEmail": (
                        "email2@example.com" if has_email_signature else None
                    ),
                    "hasError": False,
                    "invitation": dict(
                        camelize(
                            InvitationReadOnlySerializer(i1_pre_login_snapshot).data
                        )
                    ),
                    "inviteeIsAuthenticated": True,
                    "requiresSignup": False,
                    "shouldAutoAccept": bool(existing_user_email_is_verified),
                },
                "signaling": {"immediatelyRedirectTo": "followInvitation"},
            }
            asserted_against = self._assert_existing_invitee_details_correct(
                email=email,
                email_is_verified=existing_user_email_is_verified,
                name=s.eu1.name,
                invitation=s.i1,
                invitation_account=s.a1,
                role=invited_role,
                provided_ts_close_to_invitation_login_time=ts_before_follow,
            )
            assert Membership.objects.filter(user=eu1).count() == 2

        if r2 is not None:
            assert asserted_against is not None, "Pre-condition"
            s.i1.refresh_from_db()
            assert r2.data == InvitationReadOnlySerializer(s.i1).data | {
                "new_membership": dict(
                    MembershipReadOnlySerializer(asserted_against.m).data
                )
            }

    # ---                                                 ---

    # --- Test Accepting Invitations Without Following Link ---

    @pytest.mark.parametrize(
        "email_case_insensitive",
        [
            pytest.param(True, id="email_case_insensitive"),
            pytest.param(False, id="email_case_sensitive"),
        ],
    )
    @pytest.mark.parametrize(
        "initial_email_is_verified",
        [
            pytest.param(True, id="initial_email_is_verified"),
            pytest.param(False, id="initial_email_is_not_verified"),
        ],
    )
    def test_successful_straightforward_flow_accepting_invitation_without_following_link(
        self,
        email_case_insensitive: bool,
        initial_email_is_verified: bool,
    ):
        invited_email = "email2@example.com"
        email = "EmaiL2@example.com" if email_case_insensitive else invited_email
        invited_role = Role.MEMBER
        has_email_signature: bool = True
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
            is_attached_to_user=(not email_case_insensitive),
            is_existing_user_authenticated=False,
            existing_user_email_is_verified=initial_email_is_verified,
        )

        i1 = s.i1
        eu1 = s.eu1
        assert Membership.objects.filter(user=eu1).count() == 1
        api_client2 = APIClient()
        api_client2.force_authenticate(user=eu1)
        api_client2.force_login(eu1)

        pre_accept_ts = timezone.now()
        r1 = self.accept(api_client=api_client2, invitation_id=i1.pk)
        i1.refresh_from_db()

        if not email_case_insensitive and initial_email_is_verified:
            assert r1.status_code == 201, r1.data
            assert i1.status == InvitationStatus.ACCEPTED
            assert i1.accepted_at is not None
            assert i1.accepted_at == self.times.CloseTo(timezone.now())
            assert i1.user == eu1
            assert Membership.objects.filter(user=eu1).count() == 2
        else:
            assert r1.status_code == 403, r1.data
            if initial_email_is_verified:
                assert r1.data == {
                    "detail": (
                        "For security reasons, In order to accept this particular "
                        "invitation, you need to follow the link for it sent to your email."
                    )
                }
            else:
                assert r1.data == {
                    "detail": (
                        "You must verify your email before you can perform this action."
                    )
                }
            assert i1.status == InvitationStatus.OPEN
            assert i1.accepted_at is None
            if email_case_insensitive:
                assert i1.user is None
            else:
                assert i1.user == eu1
            assert Membership.objects.filter(user=eu1).count() == 1

        if r1.status_code >= 200 and r1.status_code < 400:
            asserted_against = self._assert_existing_invitee_details_correct(
                email=email,
                email_is_verified=initial_email_is_verified,
                name=eu1.name,
                invitation=i1,
                invitation_account=s.a1,
                role=invited_role,
                provided_ts_close_to_invitation_login_time=pre_accept_ts,
            )
            assert r1.data == InvitationReadOnlySerializer(i1).data | {
                "new_membership": dict(
                    MembershipReadOnlySerializer(asserted_against.m).data
                )
            }

    def test_cannot_accept_without_following_link_due_to_invitation_state(
        self, time_machine: TimeMachineFixture
    ):
        email_case_insensitive = False
        invited_email = "email2@example.com"
        email = "EmaiL2@example.com" if email_case_insensitive else invited_email
        invited_role = Role.MEMBER
        has_email_signature: bool = True
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
            is_attached_to_user=(not email_case_insensitive),
            is_existing_user_authenticated=False,
            existing_user_email_is_verified=True,
        )

        i1 = s.i1
        eu1 = s.eu1
        assert Membership.objects.filter(user=eu1).count() == 1
        api_client2 = APIClient()
        api_client2.force_authenticate(user=eu1)
        api_client2.force_login(eu1)

        initial_now = self.times.now
        initial_expires_at = i1.expires_at
        # Make sure this is actually somewhat in the future.
        assert initial_expires_at > (initial_now + timedelta(minutes=8, seconds=45)), (
            "Current pre-condition"
        )

        updated_expires_at = initial_now + timedelta(minutes=25)
        i1.expires_at = updated_expires_at
        i1.__class__.objects.filter(pk=i1.pk).update(expires_at=updated_expires_at)

        with auto_rolling_back_transaction():
            time_machine.move_to(updated_expires_at + timedelta(seconds=3))
            r1 = self.accept(api_client=api_client2, invitation_id=i1.pk)
        self.mailoutbox.clear()
        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "The invitation has expired and cannot be accepted. Please ask the "
                "individual who invited you (email1@example.com) to send a new invitation."
            ]
        }

        with auto_rolling_back_transaction():
            # Make sure that it will work if just before the expiration time
            time_machine.move_to(updated_expires_at - timedelta(seconds=45))
            r2_api_client = deepcopy(api_client2)
            r2 = self.accept(api_client=r2_api_client, invitation_id=i1.pk)
        self.mailoutbox.clear()
        assert r2.status_code == 201

        time_machine.move_to(initial_now, tick=True)

        with auto_rolling_back_transaction():
            i1.declined_at = timezone.now()
            i1.save(update_fields=["declined_at"])
            assert i1.status == InvitationStatus.DECLINED
            r3 = self.accept(api_client=api_client2, invitation_id=i1.pk)
        self.mailoutbox.clear()
        assert r3.status_code == 400
        assert r3.data == {
            "non_field_errors": [
                "This invitation has already been declined and cannot be used now. If "
                "you'd like a new invitation, please ask the person who invited you to "
                "send another invitation."
            ]
        }

        with auto_rolling_back_transaction():
            i1.declined_at = None
            i1.accepted_at = timezone.now()
            i1.user = None
            i1.save(update_fields=["declined_at", "accepted_at", "user"])
            r41 = self.accept(api_client=api_client2, invitation_id=i1.pk)
        self.mailoutbox.clear()
        assert r41.status_code == 400
        assert r41.data == {
            "non_field_errors": ["This invitation has already been accepted."]
        }

        with auto_rolling_back_transaction():
            i1.accepted_at = timezone.now()
            i1.user = User.objects.get(email="email1@example.com")
            i1.save(update_fields=["accepted_at", "user"])
            r42 = self.accept(api_client=api_client2, invitation_id=i1.pk)
        self.mailoutbox.clear()
        assert r42.status_code == 400
        assert r42.data == {
            "non_field_errors": ["This invitation has already been accepted."]
        }

        r5 = self.accept(api_client=api_client2, invitation_id=i1.pk)
        assert r5.status_code == 201

    @pytest.mark.parametrize(
        "email_case_insensitive",
        [
            pytest.param(True, id="email_case_insensitive"),
            pytest.param(False, id="email_case_sensitive"),
        ],
    )
    def test_cannot_accept_without_following_link_due_to_non_matching_email(
        self,
        email_case_insensitive: bool,
    ):
        invited_email = "email2@example.com"
        email = "EmaiL2@example.com" if email_case_insensitive else invited_email
        invited_role = Role.MEMBER
        has_email_signature: bool = True
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
            is_attached_to_user=(not email_case_insensitive),
            is_existing_user_authenticated=False,
            existing_user_email_is_verified=True,
        )

        eu2 = deepcopy(s.eu1)
        eu2.pk = None
        eu2.email = "email3@example.com"
        eu2.email_is_verified = True
        eu2.email_verified_as_of = timezone.now()
        eu2.save()

        i1 = s.i1
        api_client2 = APIClient()
        api_client2.force_authenticate(user=eu2)
        api_client2.force_login(eu2)

        r1 = self.accept(api_client=api_client2, invitation_id=i1.pk)
        i1.refresh_from_db()

        assert r1.status_code == 403, r1.data
        assert r1.data == {
            "detail": (
                "You cannot perform this action on an invitation you are not the invitee of."
            )
        }
        assert i1.status == InvitationStatus.OPEN
        assert i1.declined_at is None

    # ---                                                   ---

    # --- Test Declining Invitations ---

    @pytest.mark.parametrize(
        "email_case_insensitive",
        [
            pytest.param(True, id="email_case_insensitive"),
            pytest.param(False, id="email_case_sensitive"),
        ],
    )
    @pytest.mark.parametrize(
        "initial_email_is_verified",
        [
            pytest.param(True, id="initial_email_is_verified"),
            pytest.param(False, id="initial_email_is_not_verified"),
        ],
    )
    def test_successful_straightforward_flow_declining_invitation(
        self,
        email_case_insensitive: bool,
        initial_email_is_verified: bool,
    ):
        invited_email = "email2@example.com"
        email = "EmaiL2@example.com" if email_case_insensitive else invited_email
        invited_role = Role.MEMBER
        has_email_signature: bool = True
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
            is_attached_to_user=(not email_case_insensitive),
            is_existing_user_authenticated=False,
            existing_user_email_is_verified=initial_email_is_verified,
        )

        i1 = s.i1
        eu1 = s.eu1
        assert Membership.objects.filter(user=eu1).count() == 1
        api_client2 = APIClient()
        api_client2.force_authenticate(user=eu1)
        api_client2.force_login(eu1)

        r1 = self.decline(api_client=api_client2, invitation_id=i1.pk)
        i1.refresh_from_db()

        if initial_email_is_verified:
            assert r1.status_code == 200, r1.data
            assert i1.status == InvitationStatus.DECLINED
            assert i1.declined_at is not None
            assert i1.declined_at == self.times.CloseTo(timezone.now())
        else:
            assert r1.status_code == 403, r1.data
            assert r1.data == {
                "detail": (
                    "You must verify your email before you can perform this action."
                )
            }
            assert i1.status == InvitationStatus.OPEN
            assert i1.declined_at is None
        assert Membership.objects.filter(user=eu1).count() == 1

    @pytest.mark.parametrize(
        "email_case_insensitive",
        [
            pytest.param(True, id="email_case_insensitive"),
            pytest.param(False, id="email_case_sensitive"),
        ],
    )
    def test_cannot_decline_due_to_invitation_state(
        self,
        time_machine: TimeMachineFixture,
        email_case_insensitive: bool,
    ):
        invited_email = "email2@example.com"
        email = "EmaiL2@example.com" if email_case_insensitive else invited_email
        invited_role = Role.MEMBER
        has_email_signature: bool = True
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
            is_attached_to_user=(not email_case_insensitive),
            is_existing_user_authenticated=False,
            existing_user_email_is_verified=True,
        )

        i1 = s.i1
        eu1 = s.eu1
        assert Membership.objects.filter(user=eu1).count() == 1
        api_client2 = APIClient()
        api_client2.force_authenticate(user=eu1)
        api_client2.force_login(eu1)

        initial_now = self.times.now
        initial_expires_at = i1.expires_at
        # Make sure this is actually somewhat in the future.
        assert initial_expires_at > (initial_now + timedelta(minutes=8, seconds=45)), (
            "Current pre-condition"
        )

        updated_expires_at = initial_now + timedelta(minutes=25)
        i1.expires_at = updated_expires_at
        i1.__class__.objects.filter(pk=i1.pk).update(expires_at=updated_expires_at)

        with auto_rolling_back_transaction():
            time_machine.move_to(updated_expires_at + timedelta(seconds=3))
            r1 = self.decline(api_client=api_client2, invitation_id=i1.pk)
        self.mailoutbox.clear()
        assert r1.status_code == 400
        assert r1.data == {
            "non_field_errors": [
                "The invitation has expired and cannot be declined. If you wish to "
                "formally decline, feel free to notify the individual who invited you "
                "(email1@example.com) or ask for a a new invitation to be sent. Also, "
                "you may ignore this invitation and just log in or sign up with your "
                "current email address."
            ]
        }

        with auto_rolling_back_transaction():
            # Make sure that it will work if just before the expiration time
            time_machine.move_to(updated_expires_at - timedelta(seconds=45))
            r2_api_client = deepcopy(api_client2)
            r2 = self.decline(api_client=r2_api_client, invitation_id=i1.pk)
        self.mailoutbox.clear()
        assert r2.status_code == 200

        time_machine.move_to(initial_now, tick=True)

        with auto_rolling_back_transaction():
            i1.declined_at = timezone.now()
            i1.save(update_fields=["declined_at"])
            assert i1.status == InvitationStatus.DECLINED
            r3 = self.decline(api_client=api_client2, invitation_id=i1.pk)
        self.mailoutbox.clear()
        assert r3.status_code == 400
        assert r3.data == {
            "non_field_errors": ["The invitation has already been declined."]
        }

        with auto_rolling_back_transaction():
            i1.declined_at = None
            i1.accepted_at = timezone.now()
            i1.user = None
            i1.save(update_fields=["declined_at", "accepted_at", "user"])
            r41 = self.decline(api_client=api_client2, invitation_id=i1.pk)
        self.mailoutbox.clear()
        assert r41.status_code == 400
        assert r41.data == {
            "non_field_errors": [
                "This invitation has already been accepted and hence cannot be declined."
            ]
        }

        with auto_rolling_back_transaction():
            i1.accepted_at = timezone.now()
            i1.user = User.objects.get(email="email1@example.com")
            i1.save(update_fields=["accepted_at", "user"])
            r42 = self.decline(api_client=api_client2, invitation_id=i1.pk)
        self.mailoutbox.clear()
        assert r42.status_code == 400
        assert r42.data == {
            "non_field_errors": [
                "This invitation has already been accepted and hence cannot be declined."
            ]
        }

        r5 = self.decline(api_client=api_client2, invitation_id=i1.pk)
        assert r5.status_code == 200

    @pytest.mark.parametrize(
        "email_case_insensitive",
        [
            pytest.param(True, id="email_case_insensitive"),
            pytest.param(False, id="email_case_sensitive"),
        ],
    )
    def test_cannot_decline_due_to_non_matching_email(
        self,
        email_case_insensitive: bool,
    ):
        invited_email = "email2@example.com"
        email = "EmaiL2@example.com" if email_case_insensitive else invited_email
        invited_role = Role.MEMBER
        has_email_signature: bool = True
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=invited_email,
            invitee_role=invited_role,
            has_email_signature=has_email_signature,
            logged_in_as_other_user_when_following_link=False,
            is_attached_to_user=(not email_case_insensitive),
            is_existing_user_authenticated=False,
            existing_user_email_is_verified=True,
        )

        eu2 = deepcopy(s.eu1)
        eu2.pk = None
        eu2.email = "email3@example.com"
        eu2.email_is_verified = True
        eu2.email_verified_as_of = timezone.now()
        eu2.save()

        i1 = s.i1
        api_client2 = APIClient()
        api_client2.force_authenticate(user=eu2)
        api_client2.force_login(eu2)

        r1 = self.decline(api_client=api_client2, invitation_id=i1.pk)
        i1.refresh_from_db()

        assert r1.status_code == 403, r1.data
        assert r1.data == {
            "detail": (
                "You cannot perform this action on an invitation you are not the invitee of."
            )
        }
        assert i1.status == InvitationStatus.OPEN
        assert i1.declined_at is None

    # ---                            ---

    # --- Test Various Edge Case(s) ---

    def test_can_follow_and_accept_multiple_invitations_in_the_same_session(
        self,
        time_machine: TimeMachineFixture,
    ):
        initial_ts = timezone.now()

        email = "email2@example.com"
        s = self.make_invited_existing_user_setup(
            initial_user_email=email,
            email=email,
            invitee_role=Role.MEMBER,
            has_email_signature=True,
            logged_in_as_other_user_when_following_link=False,
            is_attached_to_user=True,
            is_existing_user_authenticated=True,
            existing_user_email_is_verified=True,
        )
        assert Membership.objects.filter(user=s.eu1).count() == 1

        ea1 = s.ea1
        eu1 = s.eu1
        eu1_api_client = APIClient()
        eu1_api_client.force_authenticate(user=eu1)
        eu1_api_client.force_login(eu1)
        eu1.refresh_from_db()

        a2 = self.account_maker(
            account_type=AccountType.TEAM,
            name="Account 2",
        )
        u2 = self.user_maker(
            account=a2,
            email="other-email2@example.com",
            email_is_verified=True,
            email_verified_as_of=timezone.now(),
        )
        api_client2 = APIClient()
        api_client2.force_authenticate(user=u2)
        api_client2.force_login(u2)
        c2 = self.create(
            api_client=api_client2,
            account=a2.pk,
            email=email,
            name="Name 2",
            role=Role.MEMBER,
        )
        i2 = Invitation.objects.select_related("account", "user").get(pk=c2.data["id"])

        assert c2.status_code == 201
        ea2 = EmailAssertions(self.mailoutbox[-1])
        ea2.assert_is_invitation_email(
            i2,
            to_email=email,
            subject=i2.headline,
            user_exists=True,
        )

        a3 = self.account_maker(
            account_type=AccountType.TEAM,
            name="Account 3",
        )
        u3 = self.user_maker(
            account=a3,
            email="other-email3@example.com",
            email_is_verified=True,
            email_verified_as_of=timezone.now(),
        )
        api_client3 = APIClient()
        api_client3.force_authenticate(user=u3)
        api_client3.force_login(u3)
        c3 = self.create(
            api_client=api_client3,
            account=a3.pk,
            email=email,
            name="Name 3",
            role=Role.MEMBER,
        )
        i3 = Invitation.objects.select_related("account", "user").get(pk=c3.data["id"])

        assert c3.status_code == 201
        ea3 = EmailAssertions(self.mailoutbox[-1])
        ea3.assert_is_invitation_email(
            i3,
            to_email=email,
            subject=i3.headline,
            user_exists=True,
        )

        a4 = self.account_maker(
            account_type=AccountType.TEAM,
            name="Account 4",
        )
        u4 = self.user_maker(
            account=a4,
            email="other-email4@example.com",
            email_is_verified=True,
            email_verified_as_of=timezone.now(),
        )
        api_client4 = APIClient()
        api_client4.force_authenticate(user=u4)
        api_client4.force_login(u4)
        c4 = self.create(
            api_client=api_client4,
            account=a4.pk,
            email=email,
            name="Name 4",
            role=Role.MEMBER,
        )
        i4 = Invitation.objects.select_related("account", "user").get(pk=c4.data["id"])
        assert c4.status_code == 201
        ea4 = EmailAssertions(self.mailoutbox[-1])
        ea4.assert_is_invitation_email(
            i4,
            to_email=email,
            subject=i4.headline,
            user_exists=True,
        )

        # Ensure current time moved at least a little bit forward.
        time_machine.move_to(timezone.now() + timedelta(seconds=1), tick=True)

        f1 = self.follow(api_client=eu1_api_client, email_assertions=ea1)
        assert f1.first_response_status_code == 302
        assert f1.second_response_status_code == 200
        f2 = self.follow(api_client=eu1_api_client, email_assertions=ea2)
        assert f2.first_response_status_code == 302
        assert f2.second_response_status_code == 200
        f3 = self.follow(api_client=eu1_api_client, email_assertions=ea3)
        assert f3.first_response_status_code == 302
        assert f3.second_response_status_code == 200
        f4 = self.follow(api_client=eu1_api_client, email_assertions=ea4)
        assert f4.first_response_status_code == 302
        assert f4.second_response_status_code == 200

        session = Session.objects.latest("expire_date")
        decoded = session.get_decoded()
        assert int(decoded["_auth_user_id"]) == eu1.pk
        initial_invitation_last_followed = decoded["invitation_last_followed"]
        initial_invitations_followed = decoded["invitations_followed"]
        assert initial_invitation_last_followed == i4.pk
        assert sorted(initial_invitations_followed, key=lambda x: int(x["pk"])) == [
            {
                "last_followed_at": self.times.CloseTo(
                    initial_ts,
                    delta=timedelta(seconds=90),
                    string=True,
                ),
                "last_followed_through": "email_link",
                "last_followed_through_email": email,
                "pk": i.pk,
            }
            for i in (s.i1, i2, i3, i4)
        ]

        # Ensure current time moved at least a little bit forward.
        time_machine.move_to(timezone.now() + timedelta(seconds=1), tick=True)

        f21 = self.follow(api_client=eu1_api_client, email_assertions=ea1)
        f22 = self.follow(api_client=eu1_api_client, email_assertions=ea2)
        f23 = self.follow(api_client=eu1_api_client, email_assertions=ea3)
        f24 = self.follow(api_client=eu1_api_client, email_assertions=ea4)
        assert (
            f21.first_response_status_code,
            f22.first_response_status_code,
            f23.first_response_status_code,
            f24.first_response_status_code,
        ) == (302, 302, 302, 302)
        assert (
            f21.second_response_status_code,
            f22.second_response_status_code,
            f23.second_response_status_code,
            f24.second_response_status_code,
        ) == (200, 200, 200, 200)

        session = Session.objects.latest("expire_date")
        decoded = session.get_decoded()
        assert int(decoded["_auth_user_id"]) == eu1.pk
        next_invitation_last_followed = decoded["invitation_last_followed"]
        next_invitations_followed = decoded["invitations_followed"]
        assert next_invitation_last_followed == i4.pk
        assert sorted(next_invitations_followed, key=lambda x: int(x["pk"])) == [
            {
                "last_followed_at": self.times.CloseTo(
                    initial_ts,
                    delta=timedelta(seconds=90),
                    string=True,
                ),
                "last_followed_through": "email_link",
                "last_followed_through_email": email,
                "pk": i.pk,
            }
            for i in (s.i1, i2, i3, i4)
        ]
        # This ensures that `last_followed_at` is getting properly updated.
        assert sorted(next_invitations_followed, key=lambda x: int(x["pk"])) != (
            sorted(initial_invitations_followed, key=lambda x: int(x["pk"]))
        )
        # But checks that everything else should stay the same.
        assert {
            r1["pk"]: {k1: v1 for k1, v1 in r1.items() if k1 != "last_followed_at"}
            for r1 in initial_invitations_followed
        } == {
            r2["pk"]: {k2: v2 for k2, v2 in r2.items() if k2 != "last_followed_at"}
            for r2 in next_invitations_followed
        }
        assert Membership.objects.filter(user=s.eu1).count() == 1

        ar3 = self.accept(api_client=eu1_api_client, invitation_id=i3.pk)
        ar2 = self.login(
            api_client=eu1_api_client,
            invitation_id=i2.pk,
            email=email,
            password=(self.strong_password + "#"),
        )
        assert ar3.status_code == 201
        assert ar2.status_code == 200
        assert Membership.objects.filter(user=s.eu1).count() == 3

        session = Session.objects.latest("expire_date")
        decoded = session.get_decoded()
        assert int(decoded["_auth_user_id"]) == eu1.pk
        post_acceptanceinvitation_last_followed = decoded["invitation_last_followed"]
        post_acceptanceinvitations_followed = decoded["invitations_followed"]
        assert post_acceptanceinvitation_last_followed == i4.pk
        assert sorted(
            post_acceptanceinvitations_followed, key=lambda x: int(x["pk"])
        ) == [
            {
                "last_followed_at": self.times.CloseTo(
                    initial_ts,
                    delta=timedelta(seconds=90),
                    string=True,
                ),
                "last_followed_through": "email_link",
                "last_followed_through_email": email,
                "pk": i.pk,
            }
            for i in (s.i1, i4)
        ]

        dr1 = self.decline(api_client=eu1_api_client, invitation_id=s.i1.pk)
        assert dr1.status_code == 200
        assert Membership.objects.filter(user=s.eu1).count() == 3

        session = Session.objects.latest("expire_date")
        decoded = session.get_decoded()
        assert int(decoded["_auth_user_id"]) == eu1.pk
        final_invitation_last_followed = decoded["invitation_last_followed"]
        final_invitations_followed = decoded["invitations_followed"]
        assert final_invitation_last_followed == i4.pk
        assert sorted(final_invitations_followed, key=lambda x: int(x["pk"])) == [
            {
                "last_followed_at": self.times.CloseTo(
                    initial_ts,
                    delta=timedelta(seconds=90),
                    string=True,
                ),
                "last_followed_through": "email_link",
                "last_followed_through_email": email,
                "pk": i.pk,
            }
            for i in (i4,)
        ]

    # ---                           ---

    @dataclass(kw_only=True)
    class _AssertedNewlyCreatedInviteeDetails:
        u: User
        i: Invitation
        m: Membership
        pm: Membership

    def _assert_newly_created_invitee_details_correct(
        self,
        *,
        # `User` details
        email: str,
        email_is_verified: bool,
        name: str,
        # `Invitation` details
        invitation: Invitation,
        invitation_account: Account,
        # `Membership` details
        role: Role,
        # Other details
        provided_ts_close_to_user_creation_time: datetime | None = None,
    ) -> _AssertedNewlyCreatedInviteeDetails:
        latest_ts = (
            timezone.now()
            if provided_ts_close_to_user_creation_time is None
            else provided_ts_close_to_user_creation_time
        )

        # Check the `User` first.
        u = User.objects.all().first_existing_with_email_case_insensitive(email)
        assert u is not None and isinstance(u, User)
        assert u.email == email
        assert u.email_is_verified is email_is_verified
        if email_is_verified:
            assert u.email_verified_as_of == self.times.CloseTo(latest_ts)
            assert u.email_verified_as_of >= u.created
            assert u.email_verified_as_of >= u.date_joined
        else:
            assert u.email_verified_as_of is None
        assert u.name == name
        assert u.is_staff is False
        assert u.is_superuser is False
        assert u.is_active is True
        assert u.date_joined
        assert u.date_joined == self.times.CloseTo(latest_ts)
        assert u.created
        assert u.created == self.times.CloseTo(latest_ts)
        assert u.modified
        assert u.modified == self.times.CloseTo(latest_ts)
        assert u.modified >= u.created
        assert u.date_joined == u.created
        assert u.created_from == UserCreatedFrom.ACCOUNT_INVITATION
        assert not u.uploaded_profile_image

        # Next, check the `Invitation`.
        assert invitation.account == invitation_account
        assert invitation.email.casefold() == u.email.casefold()
        assert invitation.user == u
        assert invitation.accepted_at
        assert invitation.accepted_at == self.times.CloseTo(latest_ts)
        assert invitation.accepted_at >= u.created
        assert invitation.accepted_at >= u.date_joined
        assert invitation.status == InvitationStatus.ACCEPTED
        assert invitation.modified == self.times.CloseTo(latest_ts)

        # And next, the team `Membership`.
        m = Membership.objects.select_related("account", "user").get(
            account=invitation_account, user=u
        )
        assert m.account == invitation_account
        assert invitation_account.account_type == AccountType.TEAM, (
            "Current pre-condition"
        )
        assert m.user == u
        assert m.role == role
        assert m.last_selected_at is not None
        assert m.last_selected_at == self.times.CloseTo(latest_ts)
        assert m.created == self.times.CloseTo(latest_ts)
        assert m.modified == self.times.CloseTo(latest_ts)
        assert m.modified >= m.created

        # Now, check the personal `Membership`, which should properly get auto-created
        # here.
        pm = (
            Membership.objects.select_related("account", "user")
            .exclude(pk=m.pk)
            .get(user=u)
        )
        assert pm.account is not None
        assert pm.account.account_type == AccountType.PERSONAL
        assert pm.user == u
        assert pm.role == Role.OWNER
        assert pm.last_selected_at <= m.last_selected_at
        assert pm.created == self.times.CloseTo(latest_ts)
        assert pm.modified == self.times.CloseTo(latest_ts)
        assert pm.modified >= pm.created

        if not u.email_is_verified:
            ea = EmailAssertions(self.mailoutbox[-1])
            ea.assert_is_verification_email(to_email=u.email)

        return self._AssertedNewlyCreatedInviteeDetails(u=u, i=invitation, m=m, pm=pm)

    def _assert_existing_invitee_details_correct(
        self,
        *,
        # `User` details
        email: str,
        email_is_verified: bool,
        name: str,
        # `Invitation` details
        invitation: Invitation,
        invitation_account: Account,
        # `Membership` details
        role: Role,
        # Other details
        provided_ts_close_to_invitation_login_time: datetime | None = None,
    ) -> _AssertedNewlyCreatedInviteeDetails:
        latest_ts = (
            timezone.now()
            if provided_ts_close_to_invitation_login_time is None
            else provided_ts_close_to_invitation_login_time
        )

        # Check the `User` first.
        u = User.objects.all().first_existing_with_email_case_insensitive(email)
        assert u is not None and isinstance(u, User)
        assert u.email == email
        assert u.email_is_verified is email_is_verified
        if email_is_verified:
            assert u.email_verified_as_of is not None
        else:
            assert u.email_verified_as_of is None
        assert u.name == name
        assert u.is_staff is False
        assert u.is_superuser is False
        assert u.is_active is True
        assert u.date_joined
        assert u.created
        assert u.modified

        # Next, check the `Invitation`.
        assert invitation.account == invitation_account
        assert invitation.email.casefold() == u.email.casefold()
        assert invitation.user == u
        assert invitation.accepted_at
        assert invitation.accepted_at == self.times.CloseTo(latest_ts)
        assert invitation.accepted_at >= u.created
        assert invitation.accepted_at >= u.date_joined
        assert invitation.status == InvitationStatus.ACCEPTED
        assert invitation.modified == self.times.CloseTo(latest_ts)

        # And next, the team `Membership`.
        m = Membership.objects.select_related("account", "user").get(
            account=invitation_account, user=u
        )
        assert m.account == invitation_account
        assert invitation_account.account_type == AccountType.TEAM, (
            "Current pre-condition"
        )
        assert m.user == u
        assert m.role == role
        assert m.last_selected_at is not None
        assert m.last_selected_at == self.times.CloseTo(latest_ts)
        assert m.created == self.times.CloseTo(latest_ts)
        assert m.modified == self.times.CloseTo(latest_ts)
        assert m.modified >= m.created

        # Now, check the personal `Membership`, which should already be here.
        pm = (
            Membership.objects.select_related("account", "user")
            .exclude(pk=m.pk)
            .get(user=u)
        )
        assert pm.account is not None
        assert pm.account.account_type == AccountType.PERSONAL
        assert pm.user == u
        assert pm.role == Role.OWNER
        assert pm.last_selected_at <= m.last_selected_at
        assert pm.created
        assert pm.modified
        assert pm.modified

        return self._AssertedNewlyCreatedInviteeDetails(u=u, i=invitation, m=m, pm=pm)
