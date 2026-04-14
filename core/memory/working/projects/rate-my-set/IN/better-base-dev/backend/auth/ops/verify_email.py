from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Literal, cast

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_bytes
from django.utils.http import base36_to_int, urlsafe_base64_encode
from django.views.decorators.debug import sensitive_variables

from backend.accounts.models import User
from backend.auth.ops.login import perform_login
from backend.auth.ops.reset_password import get_user_from_uidb64
from backend.base.ops.emails import EmailSendResult, TransactionalEmail
from backend.base.ops.emails import Key as EmailKey

INTERNAL_VERIFY_EMAIL_URL_TOKEN: Final[str] = "verify-email"
INTERNAL_VERIFY_EMAIL_SESSION_TOKEN: Final[str] = "verify_email_token"


class VerifyEmailTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "backend|auth|VerifyEmailTokenGenerator"

    def check_token(self, user: User | None, token: str | None) -> bool:
        """
        NOTE: Implementation almost entirely copy/pasted from
        `PasswordResetTokenGenerator.check_token`, except that we changed
        `settings.PASSWORD_RESET_TIMEOUT` to `settings.VERIFY_EMAIL_TIMEOUT`.
        """
        if not (user and token):
            return False
        # Parse the token
        try:
            ts_b36, _ = token.split("-")
        except ValueError:
            return False

        try:
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        # Check that the timestamp/uid has not been tampered with
        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(
                self._make_token_with_timestamp(user, ts, secret),
                token,
            ):
                break
        else:
            return False

        # Check the timestamp is within limit.
        if (self._num_seconds(self._now()) - ts) > settings.VERIFY_EMAIL_TIMEOUT:
            return False

        return True

    def _make_hash_value(
        self, user: User, timestamp: int, *args: Any, **kwargs: Any
    ) -> str:
        parent_hash_value = super()._make_hash_value(user, timestamp, *args, **kwargs)
        u: User = user
        return f"{parent_hash_value}--ev-{u.email}-{u.email_is_verified}-{u.email_verified_as_of}"


class VerificationEmail(TransactionalEmail, key=EmailKey.EMAIL_VERIFICATION_EMAIL):
    @dataclass(kw_only=True)
    class CoreSpec(TransactionalEmail.CoreSpec):
        template_path: str = "emails/verify-email"

    @dataclass(kw_only=True)
    class RenderSpec(TransactionalEmail.RenderSpec):
        secret_link: str = field(repr=False)

    @dataclass(kw_only=True)
    class DeliverySpec(TransactionalEmail.DeliverySpec):  # type: ignore[override,unused-ignore]
        subject: str = "Verify Your Email for Better Base"

    @classmethod
    def prepare(cls, *, to_email: str, secret_link: str):
        return cls(
            core=cls.CoreSpec(),
            render=cls.RenderSpec(secret_link=secret_link),
            delivery=cls.DeliverySpec(to_email=to_email),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulSendVerificationEmailResult:
    email: str
    sent_email_to: str
    user: User
    email_send_result: EmailSendResult


@dataclass(frozen=True, slots=True, kw_only=True)
class FailedSendVerificationEmailResult:
    email: str
    user: User | None
    message: str
    code: str


@sensitive_variables("email", "link_details", "email_delivery_result", "result")
def send_verification_email(
    *, email: str
) -> SuccessfulSendVerificationEmailResult | FailedSendVerificationEmailResult:
    assert email, "Pre-condition"

    user: User | None = (
        User.objects.all()
        .exclude(email="")
        .filter(email__isnull=False)
        .first_existing_with_email_case_insensitive(email=email)
    )

    def construct_failed_result(
        message: str, code: str
    ) -> FailedSendVerificationEmailResult:
        return FailedSendVerificationEmailResult(
            email=email,
            user=user,
            message=message,
            code=code,
        )

    if user is None:
        return construct_failed_result(
            (
                "We don't have an account on file for that email address. Either sign "
                "up or double check the provided info and try again."
            ),
            "no_user",
        )

    if not user.is_active:
        return construct_failed_result(
            "This account is inactive. Please contact support to reactivate it.",
            "inactive",
        )

    if user.email_is_verified:
        return construct_failed_result(
            "This email is already verified.",
            "already_verified",
        )

    link_details = generate_verify_email_link(user)
    email_delivery_result = deliver_verification_email(
        user=user,
        secret_link=link_details.secret_link,
    )
    result = SuccessfulSendVerificationEmailResult(
        email=email,
        sent_email_to=link_details.send_email_to,
        user=user,
        email_send_result=email_delivery_result.email_send_result,
    )

    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateVerifyEmailLinkResult:
    user: User
    send_email_to: str
    secret_link: str = field(repr=False)


@sensitive_variables("secret_token", "path", "secret_link", "result")
def generate_verify_email_link(user: User) -> GenerateVerifyEmailLinkResult:
    assert user is not None and user.email, "Pre-condition"

    token_generator = VerifyEmailTokenGenerator()
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    secret_token = token_generator.make_token(user)
    path = reverse(
        "auth:verify-email-redirect",
        kwargs={"uidb64": uidb64, "secret_token": secret_token},
    )
    secret_link = f"{settings.BASE_WEB_APP_URL}/{path.removeprefix('/')}"
    result = GenerateVerifyEmailLinkResult(
        user=user,
        send_email_to=user.email,
        secret_link=secret_link,
    )

    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliverVerificationEmailResult:
    user: User
    sent_email_to: str
    email_send_result: EmailSendResult


def deliver_verification_email(
    *, user: User, secret_link: str
) -> DeliverVerificationEmailResult:
    assert user is not None and user.email and secret_link, "Pre-condition"

    sent_email_to = user.email
    email = VerificationEmail.prepare(to_email=sent_email_to, secret_link=secret_link)
    email_send_result = email.send()

    return DeliverVerificationEmailResult(
        user=user,
        sent_email_to=sent_email_to,
        email_send_result=email_send_result,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class VerifyEmailRedirectRunPreparationLogicResult:
    uidb64: str
    secret_token_to_use: str = field(repr=False)
    did_set_secret_token_in_session: bool


@sensitive_variables("request", "uidb64", "secret_token", "result")
def verify_email_redirect_run_preparation_logic(
    *,
    request: HttpRequest,
    uidb64: str,
    secret_token: str,
) -> VerifyEmailRedirectRunPreparationLogicResult:
    assert uidb64 and secret_token, "Pre-condition"

    reset_url_token = INTERNAL_VERIFY_EMAIL_URL_TOKEN
    assert isinstance(reset_url_token, str), "Current pre-condition"
    did_set_secret_token_in_session: bool = False
    secret_token_to_use: str = secret_token

    if secret_token != reset_url_token:
        did_set_secret_token_in_session = True
        request.session[INTERNAL_VERIFY_EMAIL_SESSION_TOKEN] = secret_token
        secret_token_to_use = reset_url_token

    result = VerifyEmailRedirectRunPreparationLogicResult(
        uidb64=uidb64,
        secret_token_to_use=secret_token_to_use,
        did_set_secret_token_in_session=did_set_secret_token_in_session,
    )

    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulAttemptVerifyEmailConfirmResult:
    uidb64: str
    secret_token: str = field(repr=False)
    only_check_uidb64_and_secret_token: bool
    uidb64_and_secret_token_valid: bool
    secret_token_was_reset_url_token: bool
    could_request_another_link: bool
    user: User
    email: str | None
    email_is_verified: bool | None
    email_verified_as_of: datetime | None
    did_login: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class FailedAttemptVerifyEmailConfirmResult:
    uidb64: str
    secret_token: str = field(repr=False)
    only_check_uidb64_and_secret_token: bool
    uidb64_and_secret_token_valid: bool
    secret_token_was_reset_url_token: bool
    could_request_another_link: bool
    user: User | None
    email: str | None
    email_is_verified: bool | None
    email_verified_as_of: datetime | None
    did_login: bool
    message: str
    code: str


@sensitive_variables(
    "request",
    "uidb64",
    "secret_token",
    "secret_token_from_session",
    "email",
    "result",
)
def attempt_verify_email_confirm(
    *,
    request: HttpRequest,
    uidb64: str,
    secret_token: str,
    only_check_uidb64_and_secret_token: bool,
    login_if_successful: bool = False,
    already_retrieved_uidb64_user: User | None = None,
) -> SuccessfulAttemptVerifyEmailConfirmResult | FailedAttemptVerifyEmailConfirmResult:
    """
    If `only_check_uidb64_and_secret_token` is `True`, only check the `uidb64` and
    `secret_token` values and then return. Otherwise, mark the email as verified, save
    the `User`, and do anything else, etc., and return.
    """
    assert uidb64 and secret_token, "Pre-condition"

    reset_url_token = INTERNAL_VERIFY_EMAIL_URL_TOKEN
    assert isinstance(reset_url_token, str), "Current pre-condition"

    uidb64_and_secret_token_valid: bool = False
    could_request_another_link: bool = True
    secret_token_was_reset_url_token: bool = secret_token == reset_url_token
    did_login: bool = False

    user: User | None
    if already_retrieved_uidb64_user is None:
        user = get_user_from_uidb64(uidb64)
    else:
        user = already_retrieved_uidb64_user
    email: str | None = None
    email_is_verified: bool | None = None
    email_verified_as_of: datetime | None = None
    if user is not None:
        email = user.email
        email_is_verified = user.email_is_verified
        email_verified_as_of = user.email_verified_as_of

    def construct_success_result() -> SuccessfulAttemptVerifyEmailConfirmResult:
        return SuccessfulAttemptVerifyEmailConfirmResult(
            uidb64=uidb64,
            secret_token=secret_token,
            only_check_uidb64_and_secret_token=only_check_uidb64_and_secret_token,
            uidb64_and_secret_token_valid=uidb64_and_secret_token_valid,
            secret_token_was_reset_url_token=secret_token_was_reset_url_token,
            could_request_another_link=could_request_another_link,
            user=cast(User, user),
            email=email,
            email_is_verified=email_is_verified,
            email_verified_as_of=email_verified_as_of,
            did_login=did_login,
        )

    def construct_failed_result(
        message: str, code: str
    ) -> FailedAttemptVerifyEmailConfirmResult:
        return FailedAttemptVerifyEmailConfirmResult(
            uidb64=uidb64,
            secret_token=secret_token,
            only_check_uidb64_and_secret_token=only_check_uidb64_and_secret_token,
            uidb64_and_secret_token_valid=uidb64_and_secret_token_valid,
            secret_token_was_reset_url_token=secret_token_was_reset_url_token,
            could_request_another_link=could_request_another_link,
            user=user,
            email=email,
            email_is_verified=email_is_verified,
            email_verified_as_of=email_verified_as_of,
            did_login=did_login,
            message=message,
            code=code,
        )

    default_error_message = (
        "The email verification link you followed either has expired or is invalid. "
        "Please request another link to verify your email."
    )
    invalid_key: Literal["invalid"] = "invalid"

    def construct_default_error() -> FailedAttemptVerifyEmailConfirmResult:
        return construct_failed_result(default_error_message, invalid_key)

    if user is None:
        return construct_default_error()

    secret_token_to_use: str
    if secret_token == reset_url_token:
        secret_token_from_session = request.session.get(
            INTERNAL_VERIFY_EMAIL_SESSION_TOKEN
        )
        if not secret_token_from_session:
            return construct_default_error()
        secret_token_to_use = secret_token_from_session
    else:
        secret_token_to_use = secret_token

    token_generator = VerifyEmailTokenGenerator()
    if not token_generator.check_token(user, secret_token_to_use):
        return construct_default_error()

    if not user.is_active:
        could_request_another_link = False
        return construct_failed_result(
            "This account is inactive. Please contact support to reactivate it.",
            "inactive",
        )

    uidb64_and_secret_token_valid = True

    if only_check_uidb64_and_secret_token:
        return construct_success_result()

    user.email = email or user.email
    user.email_is_verified = True
    user.email_verified_as_of = timezone.now()
    user.save(
        update_fields=["email", "email_is_verified", "email_verified_as_of", "modified"]
    )

    email = user.email
    email_is_verified = user.email_is_verified
    email_verified_as_of = user.email_verified_as_of

    if login_if_successful:
        perform_login(request=request, user=user)
        did_login = True

    result = construct_success_result()

    return result
