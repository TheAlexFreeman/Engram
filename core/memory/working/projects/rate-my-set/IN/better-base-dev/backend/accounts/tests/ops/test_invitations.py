from __future__ import annotations

import base64
from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

import pytest
from django.utils import timezone
from pytest_mock import MockerFixture
from pytest_subtests import SubTests
from time_machine import TimeMachineFixture

from backend.accounts.models.invitations import Invitation
from backend.accounts.models.memberships import Membership
from backend.accounts.models.users import User
from backend.accounts.ops import invitations as invitations_ops
from backend.accounts.ops.invitations import (
    MembershipAlreadyExistsValidationError,
    create_invitation,
    delete_invitation,
    mark_invitation_as_followed,
    mark_invitation_as_sent,
    update_invitation,
    validate_can_create_invitation,
    validate_can_delete_invitation,
    validate_can_follow_invitation,
    validate_can_resend_invitation,
    validate_can_update_invitation,
)
from backend.accounts.tests.factories import UserFactory
from backend.accounts.tests.factories.accounts import AccountFactory
from backend.accounts.tests.factories.invitations import InvitationFactory
from backend.accounts.tests.factories.memberships import MembershipFactory
from backend.accounts.types.invitations import DeliveryMethod, InvitationStatus
from backend.accounts.types.roles import Role
from backend.base.tests.helpers.validation_errors import raises_validation_error

# mypy: disable-error-code="operator"


@contextmanager
def raises_membership_already_exists_error(
    message: str,
    existing_email: str,
    existing_user: User,
    existing_membership: Membership,
    *,
    partial_match: bool = False,
    code: str | None = None,
    params: Mapping[str, Any] | None = None,
):
    with pytest.raises(MembershipAlreadyExistsValidationError) as exc_info:
        try:
            yield exc_info
        except MembershipAlreadyExistsValidationError as e:
            if partial_match:
                assert message in e.message
            else:
                assert e.message == message
            if code is not None:
                assert e.code == code
            if params is not None:
                assert e.params == params

            assert e.existing_email == existing_email
            assert e.existing_user == existing_user
            assert e.existing_membership == existing_membership

            raise


@pytest.mark.django_db
def test_validate_can_create_invitation(subtests: SubTests):
    a1 = AccountFactory.create()
    u1 = UserFactory.create(account=a1, membership__role=Role.OWNER)
    u2 = UserFactory.create(account=a1, membership__role=Role.MEMBER)
    m1 = u1._membership_factory_created_
    m2 = u2._membership_factory_created_

    with subtests.test(msg="Invalid: Not Owner"):
        with raises_validation_error(
            "You must be an account owner to invite new users."
        ):
            validate_can_create_invitation(initiator=m2, email="duck@duckduckgoose.com")

    u3 = UserFactory.create(email="DucK@duckduckgoose.com")
    m3 = MembershipFactory.create(account=a1, user=u3, role=Role.MEMBER)

    with subtests.test(msg="Invalid: Membership Already Exists"):
        with raises_membership_already_exists_error(
            "A user with that email address is already a part of your team.",
            "DucK@duckduckgoose.com",
            u3,
            m3,
        ):
            validate_can_create_invitation(initiator=m1, email="duck@duckduckgoose.com")

    with subtests.test(msg="Valid"):
        validate_can_create_invitation(initiator=m1, email="goose@duckduckgoose.com")


@pytest.mark.django_db
def test_validate_can_update_invitation(subtests: SubTests):
    a1 = AccountFactory.create()
    u1 = UserFactory.create(account=a1, membership__role=Role.OWNER)
    u2 = UserFactory.create(account=a1, membership__role=Role.MEMBER)
    u3 = UserFactory.create(membership__role=Role.OWNER)
    u4 = UserFactory.create(
        account=u3._account_factory_created_, membership__role=Role.OWNER
    )
    assert u1._account_ == u2._account_, "Pre-condition"
    assert u1._account_ != u3._account_, "Pre-condition"
    assert u3._account_ == u4._account_, "Pre-condition"
    m1 = u1._membership_factory_created_
    m2 = u2._membership_factory_created_
    m3 = u3._membership_factory_created_

    email1 = "ie1@tests.betterbase.com"
    email2 = "ie2@tests.betterbase.com"
    email3 = "ie3@tests.betterbase.com"
    email4 = "ie4@tests.betterbase.com"
    i1 = InvitationFactory.create(account=u1._account_, email=email1)
    i2 = InvitationFactory.create(account=u3._account_, email=email2)
    i3 = InvitationFactory.create(account=u1._account_, email=email3, accepted=True)
    i4 = InvitationFactory.create(account=u1._account_, email=email4, expired=True)

    for n, (m, i) in enumerate([(m1, i2), (m3, i1)]):
        with subtests.test(msg=f"Invalid: Accounts mismatch (case={n + 1})"):
            with raises_validation_error(
                "You are not a member of the account associated with the invitation "
                "you are trying to update."
            ):
                validate_can_update_invitation(i, initiator=m)

    for n, (m, i) in enumerate([(m2, i1)]):
        with subtests.test(msg=f"Invalid: Not Owner (case={n + 1})"):
            with raises_validation_error(
                "You must be an account owner to update invitations."
            ):
                validate_can_update_invitation(i, initiator=m)

    with subtests.test(msg="Invalid: Already Accepted"):
        with raises_validation_error(
            "You cannot update an invitation that has been accepted."
        ):
            validate_can_update_invitation(i3, initiator=m1)

    with subtests.test(msg="Invalid: Already Expired"):
        with raises_validation_error(
            "You cannot update an invitation that has expired."
        ):
            validate_can_update_invitation(i4, initiator=m1)

    for n, (m, i) in enumerate([(m1, i1), (m3, i2)]):
        with subtests.test(msg=f"Valid (case={n + 1})"):
            validate_can_update_invitation(i, initiator=m)


@pytest.mark.django_db
def test_validate_can_resend_invitation(subtests: SubTests):
    a1 = AccountFactory.create()
    u1 = UserFactory.create(account=a1, membership__role=Role.OWNER)
    u2 = UserFactory.create(account=a1, membership__role=Role.MEMBER)
    u3 = UserFactory.create(membership__role=Role.OWNER)
    u4 = UserFactory.create(account=u3._account_, membership__role=Role.OWNER)
    assert u1._account_ == u2._account_, "Pre-condition"
    assert u1._account_ != u3._account_, "Pre-condition"
    assert u3._account_ == u4._account_, "Pre-condition"
    m1 = u1._membership_factory_created_
    m2 = u2._membership_factory_created_
    m3 = u3._membership_factory_created_

    email1 = "ie1@tests.betterbase.com"
    email2 = "ie2@tests.betterbase.com"
    email3 = "ie3@tests.betterbase.com"
    email4 = "ie4@tests.betterbase.com"
    i1 = InvitationFactory.create(account=u1._account_, email=email1)
    i2 = InvitationFactory.create(account=u3._account_, email=email2)
    i3 = InvitationFactory.create(account=u1._account_, email=email3, accepted=True)
    i4 = InvitationFactory.create(account=u1._account_, email=email4, expired=True)

    for n, (m, i) in enumerate([(m1, i2), (m3, i1)]):
        with subtests.test(msg=f"Invalid: Accounts mismatch (case={n + 1})"):
            with raises_validation_error(
                "You are not a member of the account associated with the invitation "
                "you are trying to resend."
            ):
                validate_can_resend_invitation(i, initiator=m)

    for n, (m, i) in enumerate([(m2, i1)]):
        with subtests.test(msg=f"Invalid: Not Owner (case={n + 1})"):
            with raises_validation_error(
                "You must be an account owner to resend invitations."
            ):
                validate_can_resend_invitation(i, initiator=m)

    with subtests.test(msg="Invalid: Already Accepted"):
        with raises_validation_error(
            "You cannot resend an invitation that has been accepted."
        ):
            validate_can_resend_invitation(i3, initiator=m1)

    with subtests.test(msg="Invalid: Expired"):
        with raises_validation_error(
            "You cannot resend an invitation that has expired."
        ):
            validate_can_resend_invitation(i4, initiator=m1)

    for n, (m, i) in enumerate([(m1, i1), (m3, i2)]):
        with subtests.test(msg=f"Valid: Not Expired (case={n + 1})"):
            validate_can_resend_invitation(i, initiator=m)


@pytest.mark.django_db
def test_validate_can_follow_invitation(subtests: SubTests):
    account = AccountFactory.create()
    invitee_email = "invitee@tests.betterbase.com"
    invitee = UserFactory.create(account=account, email=invitee_email)
    email1 = "ie1@tests.betterbase.com"
    email2 = "ie2@tests.betterbase.com"
    email3 = "ie3@tests.betterbase.com"
    email4 = "ie4@tests.betterbase.com"
    different_cased_email4 = email4[0].upper() + email4[1].upper() + email4[2:]
    email5 = "ie5@tests.betterbase.com"
    email6 = "ie6@tests.betterbase.com"
    i1 = InvitationFactory.create(
        account=account,
        email=email1,
        accepted=True,
    )
    i2 = InvitationFactory.create(
        account=account,
        email=email2,
        expired=True,
        set_invited_by=invitee,
    )
    i3 = InvitationFactory.create(
        account=account,
        email=email3,
        expiring_soon_and_cannot_follow=True,
        set_invited_by=invitee,
    )
    i4 = InvitationFactory.create(
        account=account,
        email=email4,
    )
    u4 = UserFactory.create(
        account=account,
        email=different_cased_email4,
    )
    i5 = InvitationFactory.create(
        account=account,
        email=email5,
        expiring_soon_and_can_follow=True,
    )
    i6 = InvitationFactory.create(
        account=account,
        email=email6,
    )

    with subtests.test(msg="Invalid: Already Accepted"):
        with raises_validation_error("This invitation has already been accepted."):
            validate_can_follow_invitation(i1)

    with subtests.test(msg="Invalid: Expired"):
        with raises_validation_error(
            "The invitation has expired. Please ask the individual who invited you "
            f"({invitee_email}) to send a new invitation."
        ):
            validate_can_follow_invitation(i2)

        i2.invited_by = None
        with raises_validation_error(
            "The invitation has expired. Please ask the individual who invited you "
            "to send a new invitation."
        ):
            validate_can_follow_invitation(i2)

        i2.invited_by = invitee

    with subtests.test(msg="Invalid: Past Follow Window"):
        with raises_validation_error(
            "The invitation has expired. Please ask the individual who invited you "
            f"({invitee_email}) to send a new invitation."
        ):
            validate_can_follow_invitation(i3)

        i3.invited_by = None
        with raises_validation_error(
            "The invitation has expired. Please ask the individual who invited you "
            "to send a new invitation."
        ):
            validate_can_follow_invitation(i3)

        i3.invited_by = invitee

    with subtests.test(msg="Invalid: User Already Exists"):
        assert i4.email == email4, "Pre-condition"
        assert u4.email == different_cased_email4, "Pre-condition"
        assert email4 != different_cased_email4, "Pre-condition"
        assert email4.lower() == different_cased_email4.lower(), "Pre-condition"
        with raises_validation_error(
            f"We found an already existing membership on file for {i4.team_display_name} "
            f"with the email address {different_cased_email4}. Please log in to your "
            "existing account."
        ):
            validate_can_follow_invitation(i4)

    with subtests.test(msg="Valid (case=expiring_soon_and_can_follow)"):
        validate_can_follow_invitation(i5)

    with subtests.test(msg="Valid (case=not_expiring_soon)"):
        validate_can_follow_invitation(i6)


@pytest.mark.django_db
def test_validate_can_delete_invitation(subtests: SubTests):
    a1 = AccountFactory.create()
    u1 = UserFactory.create(account=a1, membership__role=Role.OWNER)
    u2 = UserFactory.create(account=a1, membership__role=Role.MEMBER)
    u3 = UserFactory.create(membership__role=Role.OWNER)
    u4 = UserFactory.create(account=u3._account_, membership__role=Role.OWNER)
    assert u1._account_ == u2._account_, "Pre-condition"
    assert u1._account_ != u3._account_, "Pre-condition"
    assert u3._account_ == u4._account_, "Pre-condition"
    m1 = u1._membership_factory_created_
    m2 = u2._membership_factory_created_
    m3 = u3._membership_factory_created_

    email1 = "ie1@tests.betterbase.com"
    email2 = "ie2@tests.betterbase.com"
    email3 = "ie3@tests.betterbase.com"
    i1 = InvitationFactory.create(account=u1._account_, email=email1)
    i2 = InvitationFactory.create(account=u3._account_, email=email2)
    i3 = InvitationFactory.create(account=u1._account_, email=email3, accepted=True)

    for n, (m, i) in enumerate([(m1, i2), (m3, i1)]):
        with subtests.test(msg=f"Invalid: Accounts mismatch (case={n + 1})"):
            with raises_validation_error(
                "You are not a member of the account associated with the invitation "
                "you are trying to delete."
            ):
                validate_can_delete_invitation(i, initiator=m)

    for n, (m, i) in enumerate([(m2, i1)]):
        with subtests.test(msg=f"Invalid: Not Owner (case={n + 1})"):
            with raises_validation_error(
                "You must be an account owner to delete invitations."
            ):
                validate_can_delete_invitation(i, initiator=m)

    with subtests.test(msg="Invalid: Accepted"):
        with raises_validation_error(
            "You cannot delete an invitation that has been accepted."
        ):
            validate_can_delete_invitation(i3, initiator=m1)

    for n, (m, i) in enumerate([(m1, i1), (m3, i2)]):
        with subtests.test(msg=f"Valid (case={n + 1})"):
            validate_can_delete_invitation(i, initiator=m)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "should_override_expires_at",
    [
        pytest.param(True, id="should_override_expires_at"),
        pytest.param(False, id="should_not_override_expires_at"),
    ],
)
def test_create_invitation(
    mocker: MockerFixture,
    now: datetime,
    should_override_expires_at: bool,
):
    import secrets

    # NOTE: We spy on `token_bytes` because, as of the current Python version,
    # `token_urlsafe` calls `token_bytes` under the hood. This allows us to patch
    # "deeper" so to speak, with the consequence of, if `secrets.token_urlsafe` changes
    # its implementation this test might fail and need to be updated.
    spy = mocker.spy(secrets, "token_bytes")

    def get_token_urlsafe_expected_value(token_bytes_return: bytes) -> str:
        # Similar NOTE to the above: This directly copy pastes `secrets.token_urlsafe`'s
        # implementation. If that changes, this will probably need to be updated (but
        # the tests will very likely fail if it does change in a significant way that
        # impacts these tests and the implementation in the first place, etc.).
        return (
            base64.urlsafe_b64encode(token_bytes_return).rstrip(b"=").decode("ascii")
        )[:32]

    a1 = AccountFactory.create()
    u1 = UserFactory.create(account=a1)
    email1 = "ie1@tests.betterbase.com"
    email2 = "ie2@tests.betterbase.com"

    override_expires_at = (
        now + timedelta(days=5, minutes=30) if should_override_expires_at else None
    )
    i1 = create_invitation(
        account=a1,
        invited_by=u1,
        email=email1,
        name="Your Name 1",
        role=Role.MEMBER,
        delivery_method=DeliveryMethod.EMAIL,
        override_expires_at=override_expires_at,
    )

    assert i1.pk is not None
    assert i1.account == a1
    assert i1.invited_by == u1
    assert i1.email == email1
    assert i1.name == "Your Name 1"
    assert i1.role == Role.MEMBER
    assert i1.user is None
    assert i1.accepted_at is None
    if should_override_expires_at:
        assert i1.expires_at == override_expires_at
    else:
        assert (
            (now + Invitation.default_expires_after - timedelta(minutes=3))
            < i1.expires_at
            < (now + Invitation.default_expires_after + timedelta(minutes=3))
        )
    assert i1.secret_token
    assert len(i1.secret_token) == 40
    assert i1.secret_token[:8] == i1.expires_at.strftime("%Y%m%d")
    spy.assert_called_once()
    spy.assert_called_once_with(64)
    i1_last_part_of_secret_token = i1.secret_token[8:]
    assert i1_last_part_of_secret_token == get_token_urlsafe_expected_value(
        spy.spy_return
    )
    spy.reset_mock()
    assert i1.delivery_method == DeliveryMethod.EMAIL
    assert i1.first_sent_at is None
    assert i1.last_sent_at is None
    assert i1.num_times_sent == 0
    assert i1.delivery_data is None
    assert i1.first_followed_at is None
    assert i1.last_followed_at is None
    assert i1.num_times_followed == 0
    assert i1.is_accepted is False
    assert i1.is_expired is False
    assert i1.is_past_follow_window is False
    assert i1.status == InvitationStatus.OPEN
    assert i1.created >= now
    assert i1.modified >= i1.created

    i2 = create_invitation(
        account=a1,
        invited_by=u1,
        email=email2,
        name=None,
        role=Role.OWNER,
        delivery_method=DeliveryMethod.EMAIL,
        override_expires_at=override_expires_at,
    )

    assert i2.pk is not None
    assert i2.account == a1
    assert i2.invited_by == u1
    assert i2.email == email2
    assert i2.name == ""
    assert i2.role == Role.OWNER
    assert i2.user is None
    assert i2.accepted_at is None
    if should_override_expires_at:
        assert i2.expires_at == override_expires_at
    else:
        assert (
            (now + Invitation.default_expires_after - timedelta(minutes=3))
            < i2.expires_at
            < (now + Invitation.default_expires_after + timedelta(minutes=3))
        )
    assert i2.secret_token
    assert len(i2.secret_token) == 40
    assert i2.secret_token[:8] == i2.expires_at.strftime("%Y%m%d")
    spy.assert_called_once()
    spy.assert_called_once_with(64)
    i2_last_part_of_secret_token = i2.secret_token[8:]
    assert i2_last_part_of_secret_token == get_token_urlsafe_expected_value(
        spy.spy_return
    )
    spy.reset_mock()
    assert i2.delivery_method == DeliveryMethod.EMAIL
    assert i2.first_sent_at is None
    assert i2.last_sent_at is None
    assert i2.num_times_sent == 0
    assert i2.delivery_data is None
    assert i2.first_followed_at is None
    assert i2.last_followed_at is None
    assert i2.num_times_followed == 0
    assert i2.is_accepted is False
    assert i2.is_expired is False
    assert i2.is_past_follow_window is False
    assert i2.status == InvitationStatus.OPEN
    assert i2.created >= now
    assert i2.modified >= i2.created

    # Do some sanity checks in making sure that the `secret_token`s are definitely
    # unique. Yes, we have a `unique=True` constraint in the database as well, but we
    # call `invitations_ops._generate_invitation_secret_token` a few more times as an
    # extra check of uniqueness, etc.
    assert i1.secret_token != i2.secret_token
    additional_secret_token1 = invitations_ops._generate_invitation_secret_token(
        expires_at=i1.expires_at
    )
    additional_secret_token2 = invitations_ops._generate_invitation_secret_token(
        expires_at=i2.expires_at
    )
    assert i1.secret_token != additional_secret_token1
    assert i1.secret_token != additional_secret_token2
    assert i2.secret_token != additional_secret_token1
    assert i2.secret_token != additional_secret_token2


@pytest.mark.django_db
def test_mark_invitation_as_sent(now: datetime, time_machine: TimeMachineFixture):
    ts1 = now - timedelta(seconds=1)
    ts2 = now
    ts3 = now + timedelta(seconds=1)

    time_machine.move_to(ts1, tick=False)
    a = AccountFactory.create()
    i = InvitationFactory.create(account=a)

    assert i.first_sent_at is None, "Pre-condition"
    assert i.last_sent_at is None, "Pre-condition"
    assert i.num_times_sent == 0, "Pre-condition"
    assert i.delivery_data is None, "Pre-condition"

    time_machine.move_to(ts2, tick=False)
    mark_invitation_as_sent(i, delivery_data={"duck": "duck goose"})

    for n in range(2):
        if n == 1:
            i.refresh_from_db()
        assert i.first_sent_at == ts2
        assert i.last_sent_at == ts2
        assert i.num_times_sent == 1
        assert i.delivery_data == {"duck": "duck goose"}
        assert i.modified == ts2

    time_machine.move_to(ts3, tick=True)
    mark_invitation_as_sent(i, delivery_data=None)

    for n in range(2):
        if n == 1:
            i.refresh_from_db()
        assert i.first_sent_at == ts2
        assert i.last_sent_at >= ts3
        assert i.num_times_sent == 2
        assert i.delivery_data is None
        assert i.modified >= ts3


@pytest.mark.django_db
def test_update_invitation():
    a = AccountFactory.create()
    i = InvitationFactory.create(account=a, name="", role=Role.MEMBER)

    assert i.name == "", "Pre-condition"
    assert i.role == Role.MEMBER, "Pre-condition"

    for n in range(2):
        if n == 0:
            name = "Name 1"
            role = Role.OWNER
        else:
            name = ""
            role = Role.MEMBER
        start_datetime = timezone.now()
        update_invitation(i, name=name, role=role, db_save_only_update_fields=(n == 0))

        for m in range(2):
            if m == 1:
                i.refresh_from_db()
            assert i.name == name
            assert i.role == role
            assert i.modified >= start_datetime


@pytest.mark.django_db
def test_mark_invitation_as_followed(now: datetime, time_machine: TimeMachineFixture):
    ts1 = now - timedelta(seconds=1)
    ts2 = now
    ts3 = now + timedelta(seconds=1)

    time_machine.move_to(ts1, tick=False)
    a = AccountFactory.create()
    i = InvitationFactory.create(account=a)

    assert i.first_followed_at is None, "Pre-condition"
    assert i.last_followed_at is None, "Pre-condition"
    assert i.num_times_followed == 0, "Pre-condition"

    time_machine.move_to(ts2, tick=False)
    mark_invitation_as_followed(i)

    for n in range(2):
        if n == 1:
            i.refresh_from_db()
        assert i.first_followed_at == ts2
        assert i.last_followed_at == ts2
        assert i.num_times_followed == 1
        assert i.modified == ts2

    time_machine.move_to(ts3, tick=True)
    mark_invitation_as_followed(i)

    for n in range(2):
        if n == 1:
            i.refresh_from_db()
        assert i.first_followed_at == ts2
        assert i.last_followed_at >= ts3
        assert i.num_times_followed == 2
        assert i.modified >= ts3


@pytest.mark.django_db
def test_delete_invitation():
    a = AccountFactory.create()
    UserFactory.create(account=a, membership__role=Role.OWNER)
    i1 = InvitationFactory.create(account=a, name="Name 1", role=Role.OWNER)
    i2 = InvitationFactory.create(account=a, name="Name 2", role=Role.MEMBER)

    assert i1.pk is not None, "Pre-condition"

    assert delete_invitation(i1, request=None) == (1, {"accounts.Invitation": 1})
    with pytest.raises(Invitation.DoesNotExist):
        i1.refresh_from_db()
    i2.refresh_from_db()
