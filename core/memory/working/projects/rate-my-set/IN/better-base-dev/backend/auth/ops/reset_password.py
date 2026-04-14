from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Final, Literal, TypeAlias, TypedDict, cast

import structlog
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.views import (
    INTERNAL_RESET_SESSION_TOKEN,
    PasswordResetConfirmView,
)
from django.contrib.sessions.backends.base import SessionBase
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.debug import sensitive_variables

from backend.accounts.models import User
from backend.auth.ops.login import perform_login
from backend.base.ops.emails import EmailSendResult, TransactionalEmail
from backend.base.ops.emails import Key as EmailKey
from backend.utils.repr import NiceReprMixin

logger = structlog.stdlib.get_logger()


class ResetPasswordEmail(TransactionalEmail, key=EmailKey.EMAIL_RESET_PASSWORD):
    @dataclass(kw_only=True)
    class CoreSpec(TransactionalEmail.CoreSpec):
        template_path: str = "emails/reset-password"

    @dataclass(kw_only=True)
    class RenderSpec(TransactionalEmail.RenderSpec):
        secret_link: str = field(repr=False)

    @dataclass(kw_only=True)
    class DeliverySpec(TransactionalEmail.DeliverySpec):  # type: ignore[override,unused-ignore]
        subject: str = "Password Reset for Better Base"

    @classmethod
    def prepare(cls, *, to_email: str, secret_link: str):
        return cls(
            core=cls.CoreSpec(),
            render=cls.RenderSpec(secret_link=secret_link),
            delivery=cls.DeliverySpec(to_email=to_email),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulResetPasswordBeginResult:
    email: str
    sent_email_to: str
    user: User
    email_send_result: EmailSendResult


@dataclass(frozen=True, slots=True, kw_only=True)
class FailedResetPasswordBeginResult:
    email: str
    user: User | None
    message: str
    code: str


@sensitive_variables("link_details", "email", "email_result", "result")
def attempt_reset_password_begin(
    *, email: str
) -> SuccessfulResetPasswordBeginResult | FailedResetPasswordBeginResult:
    assert email, "Pre-condition"

    user: User | None = (
        User.objects.all()
        .exclude(email="")
        .filter(email__isnull=False)
        .first_existing_with_email_case_insensitive(email=email)
    )

    def construct_failed_result(
        message: str, code: str
    ) -> FailedResetPasswordBeginResult:
        return FailedResetPasswordBeginResult(
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

    if not user.has_usable_password():
        return construct_failed_result(
            (
                "This type of user account doesn't currently support passwords. Please "
                "log in with your existing method or reach out to support if you need "
                "any additional assistance."
            ),
            "no_usable_password",
        )

    link_details = generate_reset_password_link(user)
    email_delivery_result = deliver_reset_password_email(
        user=user,
        secret_link=link_details.secret_link,
    )
    result = SuccessfulResetPasswordBeginResult(
        email=email,
        sent_email_to=link_details.send_email_to,
        user=user,
        email_send_result=email_delivery_result.email_send_result,
    )

    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateResetPasswordLinkResult:
    user: User
    send_email_to: str
    secret_link: str = field(repr=False)


@sensitive_variables("secret_token", "path", "secret_link", "result")
def generate_reset_password_link(user: User) -> GenerateResetPasswordLinkResult:
    assert user is not None and user.email, "Pre-condition"

    token_generator = PasswordResetTokenGenerator()
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    secret_token = token_generator.make_token(user)
    path = reverse(
        "auth:reset-password-redirect",
        kwargs={"uidb64": uidb64, "secret_token": secret_token},
    )
    secret_link = f"{settings.BASE_WEB_APP_URL}/{path.removeprefix('/')}"
    result = GenerateResetPasswordLinkResult(
        user=user,
        send_email_to=user.email,
        secret_link=secret_link,
    )

    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliverResetPasswordEmailResult:
    user: User
    sent_email_to: str
    email_send_result: EmailSendResult


def deliver_reset_password_email(
    *, user: User, secret_link: str
) -> DeliverResetPasswordEmailResult:
    assert user is not None and user.email and secret_link, "Pre-condition"

    sent_email_to = user.email
    email = ResetPasswordEmail.prepare(to_email=sent_email_to, secret_link=secret_link)
    email_send_result = email.send()

    return DeliverResetPasswordEmailResult(
        user=user,
        sent_email_to=sent_email_to,
        email_send_result=email_send_result,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ResetPasswordRedirectRunPreparationLogicResult:
    uidb64: str
    secret_token_to_use: str = field(repr=False)
    did_set_secret_token_in_session: bool


@sensitive_variables("request", "uidb64", "secret_token", "result")
def reset_password_redirect_run_preparation_logic(
    *,
    request: HttpRequest,
    uidb64: str,
    secret_token: str,
) -> ResetPasswordRedirectRunPreparationLogicResult:
    assert uidb64 and secret_token, "Pre-condition"

    reset_url_token = PasswordResetConfirmView.reset_url_token
    assert isinstance(reset_url_token, str), "Current pre-condition"
    did_set_secret_token_in_session: bool = False
    secret_token_to_use: str = secret_token

    if secret_token != reset_url_token:
        did_set_secret_token_in_session = True
        request.session[INTERNAL_RESET_SESSION_TOKEN] = secret_token
        secret_token_to_use = reset_url_token

    result = ResetPasswordRedirectRunPreparationLogicResult(
        uidb64=uidb64,
        secret_token_to_use=secret_token_to_use,
        did_set_secret_token_in_session=did_set_secret_token_in_session,
    )

    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulAttemptResetPasswordConfirmResult:
    uidb64: str
    secret_token: str = field(repr=False)
    only_check_uidb64_and_secret_token: bool
    uidb64_and_secret_token_valid: bool
    secret_token_was_reset_url_token: bool
    could_request_another_link: bool
    user: User
    did_set_new_password: bool
    did_login: bool
    did_add_verifiable_email_to_session: bool
    did_verify_email: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class FailedAttemptResetPasswordConfirmResult:
    uidb64: str
    secret_token: str = field(repr=False)
    only_check_uidb64_and_secret_token: bool
    uidb64_and_secret_token_valid: bool
    secret_token_was_reset_url_token: bool
    could_request_another_link: bool
    user: User | None
    did_set_new_password: bool
    did_login: bool
    did_add_verifiable_email_to_session: bool
    did_verify_email: bool
    message: str
    code: str


@sensitive_variables(
    "request",
    "uidb64",
    "secret_token",
    "password",
    "secret_token_from_session",
    "result",
)
def attempt_reset_password_confirm(
    *,
    request: HttpRequest,
    uidb64: str,
    secret_token: str,
    only_check_uidb64_and_secret_token: bool,
    password: str,
    login_if_successful: bool,
    already_retrieved_uidb64_user: User | None = None,
) -> (
    SuccessfulAttemptResetPasswordConfirmResult
    | FailedAttemptResetPasswordConfirmResult
):
    """
    If `only_check_uidb64_and_secret_token` is `True`, only check the `uidb64` and
    `secret_token` values and then return. Otherwise, also check the `password` value,
    save the `User`, and do anything else, etc., and return.
    """
    assert uidb64 and secret_token, "Pre-condition"
    if not only_check_uidb64_and_secret_token:
        assert password, "Pre-condition"

    reset_url_token = PasswordResetConfirmView.reset_url_token
    assert isinstance(reset_url_token, str), "Current pre-condition"

    uidb64_and_secret_token_valid: bool = False
    could_request_another_link: bool = True
    secret_token_was_reset_url_token: bool = secret_token == reset_url_token
    did_set_new_password: bool = False
    did_login: bool = False
    did_add_verifiable_email_to_session: bool = False
    did_verify_email: bool = False

    user: User | None
    if already_retrieved_uidb64_user is None:
        user = get_user_from_uidb64(uidb64)
    else:
        user = already_retrieved_uidb64_user

    def construct_success_result() -> SuccessfulAttemptResetPasswordConfirmResult:
        return SuccessfulAttemptResetPasswordConfirmResult(
            uidb64=uidb64,
            secret_token=secret_token,
            only_check_uidb64_and_secret_token=only_check_uidb64_and_secret_token,
            uidb64_and_secret_token_valid=uidb64_and_secret_token_valid,
            secret_token_was_reset_url_token=secret_token_was_reset_url_token,
            could_request_another_link=could_request_another_link,
            user=cast(User, user),
            did_set_new_password=did_set_new_password,
            did_login=did_login,
            did_add_verifiable_email_to_session=did_add_verifiable_email_to_session,
            did_verify_email=did_verify_email,
        )

    def construct_failed_result(
        message: str, code: str
    ) -> FailedAttemptResetPasswordConfirmResult:
        return FailedAttemptResetPasswordConfirmResult(
            uidb64=uidb64,
            secret_token=secret_token,
            only_check_uidb64_and_secret_token=only_check_uidb64_and_secret_token,
            uidb64_and_secret_token_valid=uidb64_and_secret_token_valid,
            secret_token_was_reset_url_token=secret_token_was_reset_url_token,
            could_request_another_link=could_request_another_link,
            user=user,
            did_set_new_password=did_set_new_password,
            did_login=did_login,
            did_add_verifiable_email_to_session=did_add_verifiable_email_to_session,
            did_verify_email=did_verify_email,
            message=message,
            code=code,
        )

    default_error_message = (
        "The reset password link you followed either has expired or is invalid. Please "
        "request another link to reset your password."
    )
    invalid_key: Literal["invalid"] = "invalid"

    def construct_default_error() -> FailedAttemptResetPasswordConfirmResult:
        return construct_failed_result(default_error_message, invalid_key)

    if user is None:
        return construct_default_error()

    secret_token_to_use: str
    if secret_token == reset_url_token:
        secret_token_from_session = request.session.get(INTERNAL_RESET_SESSION_TOKEN)
        if not secret_token_from_session:
            return construct_default_error()
        secret_token_to_use = secret_token_from_session
    else:
        secret_token_to_use = secret_token

    email_before_token_check = user.email
    email_is_verified_before_token_check = user.email_is_verified
    token_generator = PasswordResetTokenGenerator()
    if not token_generator.check_token(user, secret_token_to_use):
        return construct_default_error()

    if not user.is_active:
        could_request_another_link = False
        return construct_failed_result(
            "This account is inactive. Please contact support to reactivate it.",
            "inactive",
        )

    if not user.has_usable_password():
        could_request_another_link = False
        return construct_failed_result(
            (
                "This type of user account doesn't currently support passwords. Please "
                "log in with your existing method or reach out to support if you need "
                "any additional assistance."
            ),
            "no_usable_password",
        )

    uidb64_and_secret_token_valid = True

    if only_check_uidb64_and_secret_token:
        # ! Important NOTE: At the time of writing, *we assume* that the `secret_token`
        # from `uidb64` and `secret_token` would only ever be sent or retrieved from an
        # email link. If that ever changes in the future and there are other surfaces
        # that could send or retrieve password reset links with `uidb64` and
        # `secret_token` then we'll need to add additional security and/or validation
        # measures to check that the link could have, for all intensive purposes, only
        # been sent and retrieved through an email link and not elsewhere, etc. like we
        # do in the invitations links (adding a cryptographic signature-like thing to
        # the query string in the URL, etc.) at the time of writing.
        if email_before_token_check and not email_is_verified_before_token_check:
            did_add_verifiable_email_to_session = (
                _check_and_add_verifiable_email_to_session(
                    request=request, user=user, email=email_before_token_check
                )
            )

        return construct_success_result()

    validate_password(password, user)

    assert password, "Pre-condition"
    user.set_password(password)
    did_set_new_password = True
    user.save(update_fields=["password", "modified"])

    # ! Important NOTE: See the Important NOTE above that talks about the assumption(s)
    # we're making about the `secret_token` and `uidb64` values above and how we're
    # assuming that they're only ever sent and retrieved from email links at the time of
    # writing.
    if email_before_token_check and not email_is_verified_before_token_check:
        email_verification_result = (
            _check_and_potentially_verify_email_from_session_verifiable_emails(
                request=request, user=user, email=email_before_token_check
            )
        )
        did_verify_email = email_verification_result.did_verify

    if login_if_successful:
        perform_login(request=request, user=user)
        did_login = True

    result = construct_success_result()

    return result


def get_user_from_uidb64(uidb64: str) -> User | None:
    assert uidb64, "Pre-condition"

    user: User | None
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (
        TypeError,
        ValueError,
        OverflowError,
        User.DoesNotExist,
        ValidationError,
    ):
        user = None

    return user


class _ResetPasswordSessionVerifiableEmailsHandler(NiceReprMixin):
    REPR_FIELDS = ("session", "request")

    SESSION_KEY_FOR_LIST: Final[str] = "reset_password_verifiable_emails"

    class VerifiableEmailDict(TypedDict):
        user_pk: int
        email: str
        followed_at: str  # ISO 8601 datetime string

    @dataclass(frozen=True, kw_only=True, slots=True)
    class VerifiableEmailRecord:
        user_pk: int
        email: str
        followed_at: datetime

    Raw: TypeAlias = VerifiableEmailDict
    Record: TypeAlias = VerifiableEmailRecord
    RawList: TypeAlias = list[Raw]
    RecordList: TypeAlias = list[Record]

    @classmethod
    def get_record_timeout(cls) -> timedelta:
        settings_min: timedelta = (
            settings.PASSWORD_RESET_TIMEOUT
            if isinstance(settings.PASSWORD_RESET_TIMEOUT, timedelta)  # type: ignore[unreachable]
            else timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT)
        )
        here_min = timedelta(hours=3)
        return min(settings_min, here_min)

    def __init__(self, *, request: HttpRequest):
        self.request = request

    @property
    def session(self) -> SessionBase:
        return self.request.session

    def add_verifiable_email_to_session(
        self,
        email: str,
        *,
        user: User,
        assert_matches: bool = True,
    ) -> None:
        assert email and (user is not None), "Pre-condition"
        user_pk = user.pk
        assert user_pk is not None, "Pre-condition"
        if assert_matches:
            assert email == user.email, "Pre-condition"

        new_record = self.VerifiableEmailRecord(
            user_pk=user_pk,
            email=email,
            followed_at=timezone.now(),
        )
        self._update_list(add_record=new_record, remove_record=None)

    def remove_verifiable_email_from_session(self, record: Record) -> None:
        self._update_list(add_record=None, remove_record=record)

    def prune_verifiable_emails_from_session(self) -> None:
        self._update_list(add_record=None, remove_record=None)

    def can_verify_email(
        self, *, email: str, user: User, assert_matches: bool = True
    ) -> tuple[Literal[True], Record] | tuple[Literal[False], None]:
        assert email and (user is not None), "Pre-condition"
        user_pk = user.pk
        assert user_pk is not None, "Pre-condition"
        if assert_matches:
            assert email == user.email, "Pre-condition"

        # Prune expired emails before getting the list.
        self.prune_verifiable_emails_from_session()

        records = self._get_list()
        for record in records:
            if record.email == email and record.user_pk == user.pk:
                return (True, record)

        return (False, None)

    def _get_list(self) -> RecordList:
        raw_list: _ResetPasswordSessionVerifiableEmailsHandler.RawList = (
            self.session.get(self.SESSION_KEY_FOR_LIST, []) or []
        )
        if not isinstance(raw_list, list):
            logger.error(  # type: ignore[unreachable]
                "Expected `raw_list` to be a `list`.",
                raw_list_type=type(raw_list),
                stack_info=True,
            )
            raw_list = []

        records: _ResetPasswordSessionVerifiableEmailsHandler.RecordList = []
        for raw_dict in raw_list:
            next_record = self.VerifiableEmailRecord(
                user_pk=raw_dict["user_pk"],
                email=raw_dict["email"],
                followed_at=datetime.fromisoformat(raw_dict["followed_at"]),
            )
            records.append(next_record)

        return records

    def _update_list(
        self,
        *,
        add_record: VerifiableEmailRecord | None,
        remove_record: VerifiableEmailRecord | None,
    ) -> None:
        existing = self._get_list()

        max_length: int = 30
        default_timeout = self.get_record_timeout()
        now = timezone.now()
        seen: set[tuple[int, str]] = set()

        def can_keep(r: _ResetPasswordSessionVerifiableEmailsHandler.Record):
            if (
                add_record is not None
                and r.user_pk == add_record.user_pk
                and r.email == add_record.email
            ):
                return False

            if (
                remove_record is not None
                and r.user_pk == remove_record.user_pk
                and r.email == remove_record.email
            ):
                return False

            if (r.user_pk, r.email) in seen:
                return False

            if r.followed_at + default_timeout <= now:
                return False

            return True

        can_keep_added: bool = add_record is not None and (
            add_record.followed_at + default_timeout > now
        )

        raw_records: _ResetPasswordSessionVerifiableEmailsHandler.RawList = []
        # Go through the existing records and add them to the list.
        for record in existing:
            if can_keep(record):
                raw_records.append(
                    {
                        "user_pk": record.user_pk,
                        "email": record.email,
                        "followed_at": record.followed_at.isoformat(),
                    }
                )
                seen.add((record.user_pk, record.email))
        # Put the `add_record` at the front of the list.
        if can_keep_added and add_record is not None:
            raw_records = [
                {
                    "user_pk": add_record.user_pk,
                    "email": add_record.email,
                    "followed_at": add_record.followed_at.isoformat(),
                },
                *raw_records,
            ]
            seen.add((add_record.user_pk, add_record.email))

        # Limit to `max_length` entries max.
        self.session[self.SESSION_KEY_FOR_LIST] = raw_records[:max_length]


def _check_and_add_verifiable_email_to_session(
    *, request: HttpRequest, user: User, email: str
) -> bool:
    assert email and (user is not None), "Pre-condition"
    assert user.pk is not None, "Pre-condition"
    assert email == user.email, "Current pre-condition"

    handler = _ResetPasswordSessionVerifiableEmailsHandler(request=request)

    handler.add_verifiable_email_to_session(email=email, user=user)

    return True


@dataclass(frozen=True, slots=True, kw_only=True)
class _CheckAndPotentiallyVerifyEmailFromSessionVerifiableEmailsResult:
    can_verify: bool
    did_verify: bool
    user: User
    user_db_saved: bool
    email: str
    email_is_verified: bool
    email_verified_as_of: datetime | None
    record_from_session: _ResetPasswordSessionVerifiableEmailsHandler.Record | None


def _check_and_potentially_verify_email_from_session_verifiable_emails(
    request: HttpRequest, user: User, email: str
) -> _CheckAndPotentiallyVerifyEmailFromSessionVerifiableEmailsResult:
    assert email and (user is not None), "Pre-condition"
    assert user.pk is not None, "Pre-condition"
    assert email == user.email, "Current pre-condition"

    handler = _ResetPasswordSessionVerifiableEmailsHandler(request=request)
    did_verify: bool = False
    user_db_saved: bool = False

    can_verify, record = handler.can_verify_email(email=email, user=user)

    if can_verify and user.email == email and not user.email_is_verified:
        now = timezone.now()
        user.email = email
        user.email_is_verified = True
        user.email_verified_as_of = now
        user.modified = now
        user.save(
            update_fields=(
                "email",
                "email_is_verified",
                "email_verified_as_of",
                "modified",
            )
        )
        did_verify = True
        user_db_saved = True

    if did_verify and record is not None:
        handler.remove_verifiable_email_from_session(record)
    else:
        handler.prune_verifiable_emails_from_session()

    return _CheckAndPotentiallyVerifyEmailFromSessionVerifiableEmailsResult(
        can_verify=can_verify,
        did_verify=did_verify,
        user=user,
        user_db_saved=user_db_saved,
        email=user.email,
        email_is_verified=user.email_is_verified,
        email_verified_as_of=user.email_verified_as_of,
        record_from_session=record,
    )
