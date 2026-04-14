from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn, Protocol

import structlog
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_variables
from django_stubs_ext import StrOrPromise

from backend.accounts.models import User
from backend.accounts.ops.users import create_user
from backend.accounts.types.roles import Role
from backend.accounts.types.users import UserCreatedFrom, UserCreationResult
from backend.auth.ops.verify_email import (
    FailedSendVerificationEmailResult,
    SuccessfulSendVerificationEmailResult,
    send_verification_email,
)
from backend.utils.transactions import is_in_transaction

logger = structlog.stdlib.get_logger()


class PreSignupCreateUserHook(Protocol):
    def __call__(
        self,
        *,
        email: str,
        name: str,
        created_from: UserCreatedFrom,
        membership_role: Role,
    ) -> None: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulSignupResult:
    user_creation_result: UserCreationResult


@dataclass(frozen=True, slots=True, kw_only=True)
class FailedSignupResult:
    email: str
    name: str
    existing_user: User | None
    message: StrOrPromise
    code: str


@sensitive_variables("password")
def attempt_signup(
    *,
    email: str,
    name: str,
    password: str,
    create_user_from: UserCreatedFrom,
    pre_create_user_hooks: list[PreSignupCreateUserHook] | None = None,
) -> SuccessfulSignupResult | FailedSignupResult:
    assert email, "Pre-condition"
    assert password, "Pre-condition"
    assert is_in_transaction(), "Current pre-condition"
    pre_create_user_hooks = pre_create_user_hooks or []

    pre_create_user_hooks = [_block_not_allowed_signup_emails, *pre_create_user_hooks]

    existing_user: User | None = (
        User.objects.all()
        .exclude(email="")
        .filter(email__isnull=False)
        .first_existing_with_email_case_insensitive(email=email)
    )

    def construct_failed_result(message: StrOrPromise, code: str) -> FailedSignupResult:
        return FailedSignupResult(
            email=email,
            name=name,
            existing_user=existing_user,
            message=message,
            code=code,
        )

    if existing_user is not None:
        return construct_failed_result(
            _(
                "An account with that email address already exists. Either log in or "
                "double check the provided info and try again."
            ),
            "existing_user",
        )

    validate_password(password)

    membership_role: Role = Role.OWNER

    for hook in pre_create_user_hooks:
        hook(
            email=email,
            name=name,
            created_from=create_user_from,
            membership_role=membership_role,
        )

    user_creation_result = create_user(
        account=None,
        email=email,
        password=password,
        name=name,
        created_from=create_user_from,
        membership_role=membership_role,
    )

    return SuccessfulSignupResult(user_creation_result=user_creation_result)


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulSignupResendVerificationEmailResult:
    user: User
    email: str
    email_changed: bool
    previous_email: str
    new_email: str
    send_verification_email_result: SuccessfulSendVerificationEmailResult


@dataclass(frozen=True, slots=True, kw_only=True)
class FailedSignupResendVerificationEmailResult:
    user: User
    email: str
    email_changed: bool
    send_verification_email_result: FailedSendVerificationEmailResult | None
    message: StrOrPromise
    code: str


@sensitive_variables("send_verification_email_result")
def attempt_signup_resend_verification_email(
    *,
    user: User,
    email: str | None,
) -> (
    SuccessfulSignupResendVerificationEmailResult
    | FailedSignupResendVerificationEmailResult
):
    assert user is not None and user.is_authenticated, "Pre-condition"
    assert user.pk is not None, "Pre-condition"
    assert email, "Pre-condition"
    assert is_in_transaction(), "Current pre-condition"

    _original_email = user.email
    _original_email_is_verified = user.email_is_verified
    _original_email_verified_as_of = user.email_verified_as_of
    _original_modified = user.modified

    original_email: str = user.email
    email_to_use: str = original_email
    if email:
        email_to_use = email
    email_changed: bool = email_to_use != user.email
    send_verification_email_result: (
        SuccessfulSendVerificationEmailResult | FailedSendVerificationEmailResult | None
    ) = None

    assert email_to_use, "Post-condition"

    def construct_successful_result() -> SuccessfulSignupResendVerificationEmailResult:
        assert isinstance(
            send_verification_email_result, SuccessfulSendVerificationEmailResult
        ), "Post-condition"

        return SuccessfulSignupResendVerificationEmailResult(
            user=user,
            email=email_to_use,
            email_changed=email_changed,
            previous_email=original_email,
            new_email=email_to_use,
            send_verification_email_result=send_verification_email_result,
        )

    def construct_failed_result(
        message: StrOrPromise, code: str
    ) -> FailedSignupResendVerificationEmailResult:
        if user.email != _original_email:
            user.email = _original_email
        if user.email_is_verified != _original_email_is_verified:
            user.email_is_verified = _original_email_is_verified
        if user.email_verified_as_of != _original_email_verified_as_of:
            user.email_verified_as_of = _original_email_verified_as_of
        if user.modified != _original_modified:
            user.modified = _original_modified

        assert not isinstance(
            send_verification_email_result, SuccessfulSendVerificationEmailResult
        ), "Post-condition"

        return FailedSignupResendVerificationEmailResult(
            user=user,
            email=email_to_use,
            email_changed=email_changed,
            send_verification_email_result=send_verification_email_result,
            message=message,
            code=code,
        )

    if not user.is_active:
        return construct_failed_result(
            _("This account is inactive. Please contact support to reactivate it."),
            "inactive",
        )

    if user.email_is_verified:
        return construct_failed_result(
            _(
                "You have already verified your current email address on file. Please "
                "refresh the page, re-login, or navigate to the home page to continue."
            ),
            "already_verified",
        )

    if user.email_verified_as_of is not None:
        return construct_failed_result(
            _(
                "You have verified your email address in the signup flow before and "
                "may have accidentally landed on this page; please refresh the page, "
                "re-login, or navigate to the home page to continue."
            ),
            "verified_before",
        )

    if email_changed:
        existing_user_with_new_email: User | None = (
            User.objects.all()
            .exclude(pk=user.pk)
            .exclude(email="")
            .filter(email__isnull=False)
            .first_existing_with_email_case_insensitive(email=email)
        )

        if existing_user_with_new_email is not None:
            return construct_failed_result(
                _(
                    "That email address is already regisered to another account. "
                    "Either choose a different email address or log in to the "
                    "existing account."
                ),
                "email_taken",
            )

    if email_changed:
        now = timezone.now()
        user.email = email_to_use
        user.email_is_verified = False
        user.email_verified_as_of = None
        user.modified = now
        user.save(
            update_fields=[
                "email",
                "email_is_verified",
                "email_verified_as_of",
                "modified",
            ]
        )

    send_verification_email_result = send_verification_email(email=email_to_use)
    if isinstance(send_verification_email_result, FailedSendVerificationEmailResult):
        return construct_failed_result(
            send_verification_email_result.message, send_verification_email_result.code
        )
    assert isinstance(
        send_verification_email_result, SuccessfulSendVerificationEmailResult
    ), "Post-condition"

    return construct_successful_result()


class SignupBlockedException(Exception):
    def __init__(self, message: StrOrPromise, code: str):
        self.message = message
        self.code = code

        super().__init__(message, code)


def _block_not_allowed_signup_emails(
    *,
    email: str,
    name: str,
    created_from: UserCreatedFrom,
    membership_role: Role,
) -> None:
    if not settings.SIGNUP_ENABLE_ONLY_ALLOWING_SPECIFIC_EMAIL_DOMAINS:
        return

    default_error_message = _(
        'The email "%(email)s" is not allowed to sign up at this time.'
    ) % {"email": email}
    default_error_code = "email_not_allowed_for_signup"

    def raise_error(
        message: StrOrPromise = default_error_message,
        code: str = default_error_code,
    ) -> NoReturn:
        logger.info(
            "Email blocked from signing up due to email signup domain rules.",
            email=email,
            name=name,
            created_from=created_from,
            membership_role=membership_role,
            error_message=message,
            error_code=code,
        )

        raise SignupBlockedException(message, code)

    if not email or email.count("@") != 1:
        raise_error(
            _("At this time, you must provide an email for signup."),
            "email_required_for_signup",
        )

    allow_from_invitation = (
        settings.SIGNUP_ENABLE_ALLOWING_ANY_EMAIL_DOMAIN_IF_CREATING_FROM_INVITATION
    )
    if allow_from_invitation and created_from == UserCreatedFrom.ACCOUNT_INVITATION:
        return

    allowed_domains = settings.SIGNUP_ONLY_ALLOW_SPECIFIC_EMAIL_DOMAINS
    email_domain_part = email.split("@")[1]
    for d in allowed_domains:
        if email_domain_part == d:
            return

    raise_error()
