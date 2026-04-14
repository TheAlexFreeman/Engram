from __future__ import annotations

from datetime import datetime
from typing import Literal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from backend.accounts.models.accounts import Account, AccountType
from backend.accounts.models.memberships import Membership
from backend.accounts.models.users import User
from backend.accounts.tests.factories.users import UserFactory
from backend.accounts.types.roles import Role
from backend.accounts.types.users import UserCreatedFrom, UserCreationResult
from backend.auth.ops.signup import (
    FailedSignupResendVerificationEmailResult,
    FailedSignupResult,
    SignupBlockedException,
    SuccessfulSignupResendVerificationEmailResult,
    SuccessfulSignupResult,
    attempt_signup,
    attempt_signup_resend_verification_email,
)
from backend.auth.ops.verify_email import (
    SuccessfulSendVerificationEmailResult,
    VerifyEmailTokenGenerator,
)
from backend.base.ops.emails import EmailSendResult
from backend.base.tests.helpers.datetimes import Times
from backend.base.tests.helpers.emails import EmailAssertions


@pytest.mark.django_db
class TestAttemptSignup:
    # Some password that will pass validation.
    strong_password = "Burn!IngSt@r541"

    @pytest.mark.parametrize("case", ["exact", "case_insensitive"])
    def test_existing_user(self, case: Literal["exact", "case_insensitive"]):
        if case == "exact":
            u1 = UserFactory.create(email="email1@example.com")
            email = "email1@example.com"
        else:
            u1 = UserFactory.create(email="EmaiL1@example.com")
            email = "eMaIl1@example.com"

        result = attempt_signup(
            email=email,
            name="Some Name",
            password=self.strong_password,
            create_user_from=UserCreatedFrom.DIRECT_SIGNUP,
        )
        assert isinstance(result, FailedSignupResult)
        assert result.email == email
        assert result.name == "Some Name"
        assert result.existing_user == u1
        assert result.message == (
            "An account with that email address already exists. Either log in or "
            "double check the provided info and try again."
        )
        assert result.code == "existing_user"

    def test_password_does_not_pass_validation(self):
        with pytest.raises(ValidationError) as exc_info:
            attempt_signup(
                email="email1@example.com",
                name="Some Name",
                password="12345",
                create_user_from=UserCreatedFrom.DIRECT_SIGNUP,
            )

        exception = exc_info.value
        assert exception.messages == [
            "This password is too short. It must contain at least 9 characters.",
            "This password is too common.",
            "This password is entirely numeric.",
            "Please include at least one special character (!@#$&*%?) in your password",
        ]

    @pytest.mark.parametrize(
        "create_user_from",
        [UserCreatedFrom.DIRECT_SIGNUP, UserCreatedFrom.ACCOUNT_INVITATION],
    )
    def test_signup_not_allowed_from_email_domain(
        self,
        settings,
        create_user_from: Literal[
            UserCreatedFrom.DIRECT_SIGNUP, UserCreatedFrom.ACCOUNT_INVITATION
        ],
    ):
        settings.SIGNUP_ENABLE_ONLY_ALLOWING_SPECIFIC_EMAIL_DOMAINS = True
        settings.SIGNUP_ONLY_ALLOW_SPECIFIC_EMAIL_DOMAINS = ["duck.com", "goose.com"]
        settings.SIGNUP_ENABLE_ALLOWING_ANY_EMAIL_DOMAIN_IF_CREATING_FROM_INVITATION = (
            False
        )
        if create_user_from != UserCreatedFrom.ACCOUNT_INVITATION:
            settings.SIGNUP_ENABLE_ALLOWING_ANY_EMAIL_DOMAIN_IF_CREATING_FROM_INVITATION = True

        with pytest.raises(SignupBlockedException) as exc_info:
            attempt_signup(
                email="email1@example.com",
                name="Some Name",
                password=self.strong_password,
                create_user_from=create_user_from,
            )
        exception = exc_info.value
        assert exception.message == (
            'The email "email1@example.com" is not allowed to sign up at this time.'
        )
        assert exception.code == "email_not_allowed_for_signup"

    def test_signup_allowed_no_blockers(self, times: Times):
        assert User.objects.count() == 0, "Current pre-condition"
        assert Account.objects.count() == 0, "Current pre-condition"
        assert Membership.objects.count() == 0, "Current pre-condition"

        result = attempt_signup(
            email="Email1@example.com",
            name="Some Name",
            password=self.strong_password,
            create_user_from=UserCreatedFrom.DIRECT_SIGNUP,
        )
        assert isinstance(result, SuccessfulSignupResult)
        creation_result = result.user_creation_result
        user = User.objects.get()
        account = Account.objects.get()
        membership = Membership.objects.get()

        self._assert_creation_result_and_user_and_account_and_membership_correct(
            user,
            account,
            membership,
            creation_result=creation_result,
            times=times,
            user_created_from=UserCreatedFrom.DIRECT_SIGNUP,
        )

    @pytest.mark.parametrize(
        "create_user_from",
        [UserCreatedFrom.DIRECT_SIGNUP, UserCreatedFrom.ACCOUNT_INVITATION],
    )
    def test_signup_allowed_passes_blockers(
        self,
        settings,
        create_user_from: Literal[
            UserCreatedFrom.DIRECT_SIGNUP, UserCreatedFrom.ACCOUNT_INVITATION
        ],
        times: Times,
    ):
        settings.SIGNUP_ENABLE_ONLY_ALLOWING_SPECIFIC_EMAIL_DOMAINS = True
        settings.SIGNUP_ONLY_ALLOW_SPECIFIC_EMAIL_DOMAINS = [
            "duck.com",
            "example.com",
            "goose.com",
        ]
        settings.SIGNUP_ENABLE_ALLOWING_ANY_EMAIL_DOMAIN_IF_CREATING_FROM_INVITATION = (
            False
        )

        assert User.objects.count() == 0, "Current pre-condition"
        assert Account.objects.count() == 0, "Current pre-condition"
        assert Membership.objects.count() == 0, "Current pre-condition"

        result = attempt_signup(
            email="Email1@example.com",
            name="Some Name",
            password=self.strong_password,
            create_user_from=create_user_from,
        )
        assert isinstance(result, SuccessfulSignupResult)
        creation_result = result.user_creation_result
        user = User.objects.get()
        account = Account.objects.get()
        membership = Membership.objects.get()

        self._assert_creation_result_and_user_and_account_and_membership_correct(
            user,
            account,
            membership,
            creation_result=creation_result,
            times=times,
            user_created_from=create_user_from,
        )

    def test_signup_allowed_from_invitation_special_case(self, settings, times: Times):
        settings.SIGNUP_ENABLE_ONLY_ALLOWING_SPECIFIC_EMAIL_DOMAINS = True
        settings.SIGNUP_ONLY_ALLOW_SPECIFIC_EMAIL_DOMAINS = ["duck.com", "goose.com"]
        settings.SIGNUP_ENABLE_ALLOWING_ANY_EMAIL_DOMAIN_IF_CREATING_FROM_INVITATION = (
            True
        )

        assert User.objects.count() == 0, "Current pre-condition"
        assert Account.objects.count() == 0, "Current pre-condition"
        assert Membership.objects.count() == 0, "Current pre-condition"

        result = attempt_signup(
            email="Email1@example.com",
            name="Some Name",
            password=self.strong_password,
            create_user_from=UserCreatedFrom.ACCOUNT_INVITATION,
        )
        assert isinstance(result, SuccessfulSignupResult)
        creation_result = result.user_creation_result
        user = User.objects.get()
        account = Account.objects.get()
        membership = Membership.objects.get()

        self._assert_creation_result_and_user_and_account_and_membership_correct(
            user,
            account,
            membership,
            creation_result=creation_result,
            times=times,
            user_created_from=UserCreatedFrom.ACCOUNT_INVITATION,
        )

    def _assert_creation_result_and_user_and_account_and_membership_correct(
        self,
        user: User,
        account: Account,
        membership: Membership,
        *,
        creation_result: UserCreationResult,
        times: Times,
        user_created_from: UserCreatedFrom,
    ):
        assert creation_result.user == user
        assert creation_result.account == account
        assert creation_result.account_automatically_created is True
        assert creation_result.membership == membership
        assert creation_result.is_active is True
        assert creation_result.is_staff is False
        assert creation_result.is_superuser is False
        assert creation_result.created_from == user_created_from

        assert user.email == "Email1@example.com"
        assert user.email_is_verified is False
        assert user.email_verified_as_of is None
        assert user.name == "Some Name"
        assert user.is_staff is False
        assert user.is_superuser is False
        assert times.is_close_to_now(user.date_joined)
        assert user.created_from == user_created_from
        assert not user.uploaded_profile_image
        assert user.created == user.date_joined
        assert user.modified == user.created

        assert account.account_type == AccountType.PERSONAL
        assert account.name == "Personal Account"
        assert not account.uploaded_profile_image
        assert times.is_close_to_now(account.created)
        assert times.is_close_to_now(account.modified)

        assert membership.account == account
        assert membership.user == user
        assert membership.role == Role.OWNER
        assert times.is_close_to_now(membership.last_selected_at)
        assert times.is_close_to_now(membership.created)
        assert times.is_close_to_now(membership.modified)


@pytest.mark.django_db
class TestAttemptSignupResendVerificationEmail:
    def test_not_sent_user_inactive(self, mailoutbox):
        user = UserFactory.create(email="email1@example.com", is_active=False)
        result = attempt_signup_resend_verification_email(
            user=user, email="email1@example.com"
        )

        assert isinstance(result, FailedSignupResendVerificationEmailResult)
        assert result.user == user
        assert result.email == "email1@example.com"
        assert result.email_changed is False
        assert result.send_verification_email_result is None
        assert result.message == (
            "This account is inactive. Please contact support to reactivate it."
        )
        assert result.code == "inactive"

        assert len(mailoutbox) == 0

    def test_not_sent_email_already_verified(self, mailoutbox):
        user = UserFactory.create(email="email1@example.com", email_is_verified=True)
        result = attempt_signup_resend_verification_email(
            user=user, email="email1@example.com"
        )

        assert isinstance(result, FailedSignupResendVerificationEmailResult)
        assert result.user == user
        assert result.email == "email1@example.com"
        assert result.email_changed is False
        assert result.send_verification_email_result is None
        assert result.message == (
            "You have already verified your current email address on file. Please "
            "refresh the page, re-login, or navigate to the home page to continue."
        )
        assert result.code == "already_verified"

        assert len(mailoutbox) == 0

    def test_not_sent_email_verified_before(self, now: datetime, mailoutbox):
        user = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=now,
        )
        result = attempt_signup_resend_verification_email(
            user=user, email="email1@example.com"
        )

        assert isinstance(result, FailedSignupResendVerificationEmailResult)
        assert result.user == user
        assert result.email == "email1@example.com"
        assert result.email_changed is False
        assert result.send_verification_email_result is None
        assert result.message == (
            "You have verified your email address in the signup flow before and "
            "may have accidentally landed on this page; please refresh the page, "
            "re-login, or navigate to the home page to continue."
        )
        assert result.code == "verified_before"

        assert len(mailoutbox) == 0

    @pytest.mark.parametrize("case", ["exact", "case_insensitive"])
    def test_not_sent_to_new_email_existing_user(
        self,
        case: Literal["exact", "case_insensitive"],
        mailoutbox,
    ):
        if case == "exact":
            u1 = UserFactory.create(email="email1@example.com")
            email = "email1@example.com"
        else:
            u1 = UserFactory.create(email="EmaiL1@example.com")
            email = "eMaIl1@example.com"
        user = UserFactory.create(
            email="email0@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        assert user != u1 and user.email != u1.email, "Pre-condition"
        result = attempt_signup_resend_verification_email(user=user, email=email)

        assert isinstance(result, FailedSignupResendVerificationEmailResult)
        assert result.user == user
        assert result.email == email
        assert result.email_changed is True
        assert result.send_verification_email_result is None
        assert result.message == (
            "That email address is already regisered to another account. "
            "Either choose a different email address or log in to the "
            "existing account."
        )
        assert result.code == "email_taken"

        assert len(mailoutbox) == 0

    @pytest.mark.parametrize("case", ["exact", "case_insensitive"])
    def test_sent_to_new_email(
        self,
        case: Literal["exact", "case_insensitive"],
        mailoutbox,
        times: Times,
    ):
        if case == "exact":
            email = "email1@example.com"
        else:
            email = "eMaIl1@example.com"
        user = UserFactory.create(
            email="email0@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        t1 = timezone.now()
        result = attempt_signup_resend_verification_email(user=user, email=email)
        t2 = timezone.now()
        user.refresh_from_db()

        assert isinstance(result, SuccessfulSignupResendVerificationEmailResult)
        assert result.user == user
        assert result.email == email
        assert result.email_changed is True
        assert result.previous_email == "email0@example.com"
        assert result.new_email == email
        assert (
            result.send_verification_email_result
            == SuccessfulSendVerificationEmailResult(
                email=user.email,
                sent_email_to=email,
                user=user,
                email_send_result=EmailSendResult(
                    num_sent=1,
                    sent_at=times.close_to_now,  # type: ignore[arg-type]
                ),
            )
        )

        assert user.email == email
        assert user.email_is_verified is False
        assert user.email_verified_as_of is None
        assert user.modified >= t1 and user.modified <= t2

        assert len(mailoutbox) == 1
        ea = EmailAssertions(mailoutbox[0])
        ea.assert_is_verification_email(to_email=email)
        link = ea.extract_verification_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert VerifyEmailTokenGenerator().check_token(user, token)

    def test_sent_to_existing_email(self, mailoutbox, times: Times):
        user = UserFactory.create(
            email="email0@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        t1 = timezone.now()
        result = attempt_signup_resend_verification_email(
            user=user, email="email0@example.com"
        )
        user.refresh_from_db()

        assert isinstance(result, SuccessfulSignupResendVerificationEmailResult)
        assert result.user == user
        assert result.email == "email0@example.com"
        assert result.email_changed is False
        assert result.previous_email == "email0@example.com"
        assert result.new_email == "email0@example.com"
        assert (
            result.send_verification_email_result
            == SuccessfulSendVerificationEmailResult(
                email="email0@example.com",
                sent_email_to="email0@example.com",
                user=user,
                email_send_result=EmailSendResult(
                    num_sent=1,
                    sent_at=times.close_to_now,  # type: ignore[arg-type]
                ),
            )
        )

        assert user.email == "email0@example.com"
        assert user.modified <= t1

        assert len(mailoutbox) == 1
        ea = EmailAssertions(mailoutbox[0])
        ea.assert_is_verification_email(to_email="email0@example.com")
        link = ea.extract_verification_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert VerifyEmailTokenGenerator().check_token(user, token)
