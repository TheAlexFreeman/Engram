from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Literal, TypeAlias, cast, overload

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db.models import F
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.encoding import force_bytes
from django.utils.http import base36_to_int, urlsafe_base64_encode
from django.views.decorators.debug import sensitive_variables

from backend.accounts.models import User
from backend.auth.models.email_changes import (
    EmailChangeRequest,
    SuccessfulEmailChange,
)
from backend.auth.ops.login import perform_login
from backend.auth.ops.reset_password import get_user_from_uidb64
from backend.base.ops.emails import EmailSendResult, TransactionalEmail
from backend.base.ops.emails import Key as EmailKey
from backend.utils.repr import NiceReprMixin
from backend.utils.transactions import is_in_transaction

INTERNAL_CHANGE_EMAIL_URL_TOKEN: Final[str] = "change-email"
INTERNAL_CHANGE_EMAIL_SESSION_TOKEN: Final[str] = "change_email_token"


class EmailChangeRequestOps(NiceReprMixin):
    REPR_FIELDS = ("instance",)

    def __init__(self, instance: EmailChangeRequest):
        self.instance = instance

    @classmethod
    def get_from_user_or_create(cls, user: User) -> tuple[EmailChangeRequest, bool]:
        assert user is not None and user.pk is not None, "Pre-condition"

        # Try and use the reverse 1-1 accessor first since it caches
        # `EmailChangeRequest` instances (and may not make a DB query if already cached,
        # etc.).
        try:
            return (user.email_change_request, False)
        except EmailChangeRequest.DoesNotExist:
            pass

        # Otherwise, go with the regular `get_or_create` call.
        return EmailChangeRequest.objects.get_or_create(user=user)

    def mark_requested(self, user: User, to_email: str) -> None:
        instance = self.instance

        if user != instance.user:
            raise ValueError(
                "The `user` must match the `EmailChangeRequest` instance's `user`."
            )

        assert user is not None and user.pk is not None, "Pre-condition"
        assert user.pk == instance.user_id, "Pre-condition"
        assert to_email, "Pre-condition"
        assert instance.pk is not None, "Pre-condition"

        now = timezone.now()

        previous_from_email = instance.from_email
        previous_to_email = instance.to_email

        instance.from_email = user.email
        instance.to_email = to_email
        instance.requested_at = now
        instance.successfully_changed_at = None
        instance.modified = now

        update_fields: set[str] = {
            "from_email",
            "to_email",
            "requested_at",
            "successfully_changed_at",
            "modified",
        }

        set_post_f_expression_values: dict[
            Literal["num_times_requested_a_new_from_or_to_email"],
            int,
        ] = {}

        if (
            previous_from_email != instance.from_email
            or previous_to_email != instance.to_email
        ):
            instance.last_requested_a_new_from_or_to_email_at = now
            set_post_f_expression_values[
                "num_times_requested_a_new_from_or_to_email"
            ] = instance.num_times_requested_a_new_from_or_to_email + 1
            instance.num_times_requested_a_new_from_or_to_email = (
                F("num_times_requested_a_new_from_or_to_email") + 1
            )
            update_fields |= {
                "last_requested_a_new_from_or_to_email_at",
                "num_times_requested_a_new_from_or_to_email",
            }

        instance.save(update_fields=update_fields)
        for k, v in set_post_f_expression_values.items():
            setattr(instance, k, v)

    def mark_sent(self) -> None:
        instance = self.instance
        set_post_f_expression_values: dict[
            Literal["num_times_sent_a_change_email"], int
        ] = {}
        now = timezone.now()

        instance.requested_at = now
        instance.last_sent_a_change_email_at = now
        set_post_f_expression_values["num_times_sent_a_change_email"] = (
            instance.num_times_sent_a_change_email + 1
        )
        instance.num_times_sent_a_change_email = F("num_times_sent_a_change_email") + 1
        instance.modified = now

        update_fields: set[str] = {
            "requested_at",
            "last_sent_a_change_email_at",
            "num_times_sent_a_change_email",
            "modified",
        }

        instance.save(update_fields=update_fields)
        for k, v in set_post_f_expression_values.items():
            setattr(instance, k, v)

    def mark_successfully_changed(
        self,
        *,
        from_email: str,
        to_email: str,
    ) -> SuccessfulEmailChange:
        assert is_in_transaction(), "Pre-condition"

        instance = self.instance
        user = instance.user
        set_post_f_expression_values: dict[
            Literal["num_times_email_successfully_changed"], int
        ] = {}
        now = timezone.now()

        assert from_email, "Current pre-condition"
        assert to_email, "Pre-condition"
        assert user is not None and user.pk is not None, "Pre-condition"

        if from_email != instance.from_email or to_email != instance.to_email:
            raise ValueError(
                "The `from_email` and `to_email` must match the `EmailChangeRequest` "
                "instance's `from_email` and `to_email`."
            )

        instance.successfully_changed_at = now
        instance.last_successfully_changed_at = now
        set_post_f_expression_values["num_times_email_successfully_changed"] = (
            instance.num_times_email_successfully_changed + 1
        )
        instance.num_times_email_successfully_changed = (
            F("num_times_email_successfully_changed") + 1
        )
        instance.modified = now

        update_fields: set[str] = {
            "successfully_changed_at",
            "last_successfully_changed_at",
            "num_times_email_successfully_changed",
            "modified",
        }

        instance.save(update_fields=update_fields)
        for k, v in set_post_f_expression_values.items():
            setattr(instance, k, v)

        return SuccessfulEmailChange.objects.create(
            user=instance.user,
            from_email=instance.from_email,
            to_email=instance.to_email,
            requested_at=(instance.requested_at or now),
            successfully_changed_at=now,
            created=now,
            modified=now,
        )


class ChangeEmailTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "backend|auth|ChangeEmailTokenGenerator"

    def check_token(self, user: User | None, token: str | None) -> bool:
        """
        NOTE: Implementation almost entirely copy/pasted from
        `PasswordResetTokenGenerator.check_token`, except that we changed
        `settings.PASSWORD_RESET_TIMEOUT` to `settings.CHANGE_EMAIL_TIMEOUT`.
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
        if (self._num_seconds(self._now()) - ts) > settings.CHANGE_EMAIL_TIMEOUT:
            return False

        return True

    def _make_hash_value(
        self, user: User, timestamp: int, *args: Any, **kwargs: Any
    ) -> str:
        parent_hash_value = super()._make_hash_value(user, timestamp, *args, **kwargs)

        u: User = user
        email_change_request = EmailChangeRequestOps.get_from_user_or_create(user=u)[0]

        user_extra_hash_value = f"{u.email}-{u.email_is_verified}"

        successfully_changed_at_str = (
            None
            if email_change_request.successfully_changed_at is None
            else email_change_request.successfully_changed_at.isoformat()
        )
        email_change_request_hash_value = (
            f"{email_change_request.pk}-{email_change_request.from_email}"
            f"-{email_change_request.to_email}-{successfully_changed_at_str}"
        )

        return (
            f"{parent_hash_value}"
            f"--u-{user_extra_hash_value}"
            f"--ecr-{email_change_request_hash_value}"
        )


class EmailChangeEmail(TransactionalEmail, key=EmailKey.EMAIL_CHANGE_EMAIL):
    @dataclass(kw_only=True)
    class CoreSpec(TransactionalEmail.CoreSpec):
        template_path: str = "emails/change-email"

    @dataclass(kw_only=True)
    class RenderSpec(TransactionalEmail.RenderSpec):
        from_email: str
        to_email: str
        secret_link: str = field(repr=False)

    @dataclass(kw_only=True)
    class DeliverySpec(TransactionalEmail.DeliverySpec):  # type: ignore[override,unused-ignore]
        subject: str = "Change Your Email on Better Base"

    @classmethod
    def prepare(cls, *, from_email: str, to_email: str, secret_link: str):
        return cls(
            core=cls.CoreSpec(),
            render=cls.RenderSpec(
                from_email=from_email,
                to_email=to_email,
                secret_link=secret_link,
            ),
            delivery=cls.DeliverySpec(to_email=to_email),
        )


class EmailNotifyOriginalEmailOfEmailChangeRequest(
    TransactionalEmail, key=EmailKey.EMAIL_NOTIFY_ORIGINAL_EMAIL_OF_EMAIL_CHANGE_REQUEST
):
    @dataclass(kw_only=True)
    class CoreSpec(TransactionalEmail.CoreSpec):
        template_path: str = "emails/notify-original-email-of-email-change-request"

    @dataclass(kw_only=True)
    class RenderSpec(TransactionalEmail.RenderSpec):
        from_email: str
        to_email: str

    @dataclass(kw_only=True)
    class DeliverySpec(TransactionalEmail.DeliverySpec):  # type: ignore[override,unused-ignore]
        subject: str = "Email Change Request Made on Better Base"

    @classmethod
    def prepare(cls, *, from_email: str, to_email: str):
        return cls(
            core=cls.CoreSpec(),
            render=cls.RenderSpec(from_email=from_email, to_email=to_email),
            delivery=cls.DeliverySpec(to_email=from_email),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulInitiateEmailChangeProcessResultBase:
    user: User
    from_email: str
    to_email: str
    email_change_request: EmailChangeRequest
    to_email_send_result: EmailSendResult


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulInitiateEmailChangeProcessResultNotOnlyResend(
    SuccessfulInitiateEmailChangeProcessResultBase
):
    from_email_send_result: EmailSendResult


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulInitiateEmailChangeProcessResultOnlyResend(
    SuccessfulInitiateEmailChangeProcessResultBase
):
    from_email_send_result: None


SuccessfulInitiateEmailChangeProcessResult: TypeAlias = (
    SuccessfulInitiateEmailChangeProcessResultNotOnlyResend
    | SuccessfulInitiateEmailChangeProcessResultOnlyResend
)


@dataclass(frozen=True, slots=True, kw_only=True)
class FailedInitiateEmailChangeProcessResult:
    user: User
    from_email: str
    to_email: str
    email_change_request: EmailChangeRequest | None
    message: str
    code: str


@overload
def initiate_email_change_process(
    *,
    user: User,
    to_email: str | Literal["use_email_change_request"],
    only_resend: Literal[True],
) -> (
    SuccessfulInitiateEmailChangeProcessResultOnlyResend
    | FailedInitiateEmailChangeProcessResult
): ...


@overload
def initiate_email_change_process(
    *,
    user: User,
    to_email: str,
    only_resend: Literal[False],
) -> (
    SuccessfulInitiateEmailChangeProcessResultNotOnlyResend
    | FailedInitiateEmailChangeProcessResult
): ...


@sensitive_variables(
    "from_email",
    "to_email",
    "to_email_link_details",
    "to_email_delivery_result",
    "from_email_instance",
    "from_email_send_result",
)
def initiate_email_change_process(
    *,
    user: User,
    to_email: str | Literal["use_email_change_request"],
    only_resend: bool,
) -> (
    SuccessfulInitiateEmailChangeProcessResult | FailedInitiateEmailChangeProcessResult
):
    initial_to_email: str | Literal["use_email_change_request"] = to_email
    from_email = user.email
    email_change_request: EmailChangeRequest | None = None

    assert user is not None and user.pk is not None and isinstance(user, User), (
        "Pre-condition"
    )
    assert from_email, "Current pre-condition"

    def construct_failed_result(
        message: str, code: str
    ) -> FailedInitiateEmailChangeProcessResult:
        return FailedInitiateEmailChangeProcessResult(
            user=user,
            from_email=from_email,
            to_email=to_email,
            email_change_request=email_change_request,
            message=message,
            code=code,
        )

    no_existing_email_change_request_message = (
        "There is no existing email change request to resend."
    )
    no_existing_email_change_request_code = "no_existing_email_change_request"
    if initial_to_email == "use_email_change_request":
        try:
            email_change_request = user.email_change_request
        except EmailChangeRequest.DoesNotExist:
            return construct_failed_result(
                no_existing_email_change_request_message,
                no_existing_email_change_request_code,
            )
        assert email_change_request is not None, "Post-condition"
        to_email = email_change_request.to_email
        if not to_email:
            return construct_failed_result(
                no_existing_email_change_request_message,
                no_existing_email_change_request_code,
            )

    if not to_email and only_resend:
        return construct_failed_result(
            no_existing_email_change_request_message,
            no_existing_email_change_request_code,
        )

    if not to_email:
        return construct_failed_result(
            "The new email cannot be blank.",
            "blank",
        )

    assert to_email and to_email != "use_email_change_request", "Post-condition"

    if not user.is_active:
        return construct_failed_result(
            "This account is inactive. Please contact support to reactivate it.",
            "inactive",
        )

    if to_email == user.email:
        return construct_failed_result(
            "The new email is the same as the current email.",
            "same_email",
        )

    if not user.email_is_verified:
        return construct_failed_result(
            (
                "The current email address must be verified before you can change to a "
                "new email."
            ),
            "current_email_requires_verification",
        )

    conflicting_user: User | None = (
        User.objects.all()
        .exclude(email="")
        .filter(email__isnull=False)
        .first_existing_with_email_case_insensitive(email=to_email)
    )

    if conflicting_user is not None and conflicting_user != user:
        return construct_failed_result(
            "A different user already has this email.",
            "email_taken",
        )

    email_change_request = EmailChangeRequestOps.get_from_user_or_create(user=user)[0]
    assert email_change_request is not None, "Post-condition"
    if only_resend and email_change_request.to_email:
        email_change_request.ops.mark_sent()
    else:
        email_change_request.ops.mark_requested(user, to_email)

    from_email_send_result: EmailSendResult | None = None
    if not only_resend:
        from_email_instance = EmailNotifyOriginalEmailOfEmailChangeRequest.prepare(
            from_email=from_email,
            to_email=to_email,
        )
        from_email_send_result = from_email_instance.send()

    to_email_link_details = generate_change_email_link(
        user,
        from_email=from_email,
        to_email=to_email,
    )
    to_email_delivery_result = deliver_email_change_email(
        user=user,
        from_email=from_email,
        to_email=to_email,
        secret_link=to_email_link_details.secret_link,
    )

    if only_resend:
        assert from_email_send_result is None, "Post-condition"
        return SuccessfulInitiateEmailChangeProcessResultOnlyResend(
            user=user,
            from_email=from_email,
            to_email=to_email,
            email_change_request=email_change_request,
            to_email_send_result=to_email_delivery_result.email_send_result,
            from_email_send_result=from_email_send_result,
        )

    assert from_email_send_result is not None, "Post-condition"
    return SuccessfulInitiateEmailChangeProcessResultNotOnlyResend(
        user=user,
        from_email=from_email,
        to_email=to_email,
        email_change_request=email_change_request,
        to_email_send_result=to_email_delivery_result.email_send_result,
        from_email_send_result=from_email_send_result,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class GenerateChangeEmailLinkResult:
    user: User
    from_email: str
    to_email: str
    send_email_to: str
    secret_link: str = field(repr=False)


@sensitive_variables("secret_token", "path", "secret_link", "result")
def generate_change_email_link(
    user: User,
    *,
    from_email: str,
    to_email: str,
) -> GenerateChangeEmailLinkResult:
    assert user is not None and user.email, "Pre-condition"
    assert user.email == from_email and from_email, "Current pre-condition"
    assert to_email, "Pre-condition"

    token_generator = ChangeEmailTokenGenerator()
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    secret_token = token_generator.make_token(user)
    path = reverse(
        "auth:change-email-redirect",
        kwargs={"uidb64": uidb64, "secret_token": secret_token},
    )
    secret_link = f"{settings.BASE_WEB_APP_URL}/{path.removeprefix('/')}"
    result = GenerateChangeEmailLinkResult(
        user=user,
        from_email=from_email,
        to_email=to_email,
        send_email_to=to_email,
        secret_link=secret_link,
    )

    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliverEmailChangeEmailResult:
    user: User
    from_email: str
    to_email: str
    sent_email_to: str
    email_send_result: EmailSendResult


def deliver_email_change_email(
    *,
    user: User,
    from_email: str,
    to_email: str,
    secret_link: str,
) -> DeliverEmailChangeEmailResult:
    assert user is not None and user.email and secret_link, "Pre-condition"
    assert user.email == from_email and from_email, "Current pre-condition"
    assert to_email, "Pre-condition"

    email = EmailChangeEmail.prepare(
        from_email=from_email,
        to_email=to_email,
        secret_link=secret_link,
    )
    email_send_result = email.send()
    sent_email_to = to_email

    return DeliverEmailChangeEmailResult(
        user=user,
        from_email=from_email,
        to_email=to_email,
        sent_email_to=sent_email_to,
        email_send_result=email_send_result,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeEmailRedirectRunPreparationLogicResult:
    uidb64: str
    secret_token_to_use: str = field(repr=False)
    did_set_secret_token_in_session: bool


@sensitive_variables("request", "uidb64", "secret_token", "result")
def change_email_redirect_run_preparation_logic(
    *,
    request: HttpRequest,
    uidb64: str,
    secret_token: str,
) -> ChangeEmailRedirectRunPreparationLogicResult:
    assert uidb64 and secret_token, "Pre-condition"

    reset_url_token = INTERNAL_CHANGE_EMAIL_URL_TOKEN
    assert isinstance(reset_url_token, str), "Current pre-condition"
    did_set_secret_token_in_session: bool = False
    secret_token_to_use: str = secret_token

    if secret_token != reset_url_token:
        did_set_secret_token_in_session = True
        request.session[INTERNAL_CHANGE_EMAIL_SESSION_TOKEN] = secret_token
        secret_token_to_use = reset_url_token

    result = ChangeEmailRedirectRunPreparationLogicResult(
        uidb64=uidb64,
        secret_token_to_use=secret_token_to_use,
        did_set_secret_token_in_session=did_set_secret_token_in_session,
    )

    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulAttemptChangeEmailConfirmResult:
    uidb64: str
    secret_token: str = field(repr=False)
    only_check_validation_conditions: bool
    checked_password: bool
    uidb64_and_secret_token_valid: bool
    secret_token_was_reset_url_token: bool
    user: User
    from_email: str
    to_email: str
    did_login: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class FailedAttemptChangeEmailConfirmResult:
    uidb64: str
    secret_token: str = field(repr=False)
    only_check_validation_conditions: bool
    checked_password: bool | None
    uidb64_and_secret_token_valid: bool
    secret_token_was_reset_url_token: bool
    user: User | None
    from_email: str | None
    to_email: str | None
    did_login: bool
    message: str
    code: str


@sensitive_variables(
    "request",
    "uidb64",
    "secret_token",
    "password",
    "secret_token_from_session",
    "from_email",
    "to_email",
    "result",
)
def attempt_change_email_confirm(
    *,
    request: HttpRequest,
    uidb64: str,
    secret_token: str,
    password: str,
    only_check_validation_conditions: bool,
    check_password: bool,
    login_if_successful: bool = False,
    already_retrieved_uidb64_user: User | None = None,
) -> SuccessfulAttemptChangeEmailConfirmResult | FailedAttemptChangeEmailConfirmResult:
    """
    If `only_check_validation_conditions` is `True`, only check the `uidb64` and
    `secret_token` values along with running any other validation/check logic and then
    return. Otherwise, change the email and save the `User` and mark the
    `EmailChangeRequest` as successful, do anything else, else, etc., and return.
    """
    assert is_in_transaction(), "Pre-condition"
    assert uidb64 and secret_token, "Pre-condition"

    reset_url_token = INTERNAL_CHANGE_EMAIL_URL_TOKEN
    assert isinstance(reset_url_token, str), "Current pre-condition"

    checked_password: bool | None = None
    uidb64_and_secret_token_valid: bool = False
    secret_token_was_reset_url_token: bool = secret_token == reset_url_token
    did_login: bool = False

    user: User | None
    if already_retrieved_uidb64_user is None:
        user = get_user_from_uidb64(uidb64)
    else:
        user = already_retrieved_uidb64_user
    from_email: str | None = None
    to_email: str | None = None

    def construct_success_result() -> SuccessfulAttemptChangeEmailConfirmResult:
        assert from_email and to_email, "Post-condition"
        assert checked_password is not None, "Post-condition"

        return SuccessfulAttemptChangeEmailConfirmResult(
            uidb64=uidb64,
            secret_token=secret_token,
            only_check_validation_conditions=only_check_validation_conditions,
            checked_password=checked_password,
            uidb64_and_secret_token_valid=uidb64_and_secret_token_valid,
            secret_token_was_reset_url_token=secret_token_was_reset_url_token,
            user=cast(User, user),
            from_email=from_email,
            to_email=to_email,
            did_login=did_login,
        )

    def construct_failed_result(
        message: str, code: str
    ) -> FailedAttemptChangeEmailConfirmResult:
        return FailedAttemptChangeEmailConfirmResult(
            uidb64=uidb64,
            secret_token=secret_token,
            only_check_validation_conditions=only_check_validation_conditions,
            checked_password=checked_password,
            uidb64_and_secret_token_valid=uidb64_and_secret_token_valid,
            secret_token_was_reset_url_token=secret_token_was_reset_url_token,
            user=user,
            from_email=from_email,
            to_email=to_email,
            did_login=did_login,
            message=message,
            code=code,
        )

    default_error_message = (
        "The email change link you followed either has expired or is invalid. Please "
        "request another link to change your email."
    )
    invalid_key: Literal["invalid"] = "invalid"

    def construct_default_error() -> FailedAttemptChangeEmailConfirmResult:
        return construct_failed_result(default_error_message, invalid_key)

    if user is None:
        return construct_default_error()

    try:
        email_change_request: EmailChangeRequest = user.email_change_request
    except EmailChangeRequest.DoesNotExist:
        return construct_default_error()
    else:
        from_email = email_change_request.from_email
        to_email = email_change_request.to_email
        if not from_email or not to_email:
            return construct_default_error()
    assert from_email and to_email, "Post-condition"

    secret_token_to_use: str
    if secret_token == reset_url_token:
        secret_token_from_session = request.session.get(
            INTERNAL_CHANGE_EMAIL_SESSION_TOKEN
        )
        if not secret_token_from_session:
            return construct_default_error()
        secret_token_to_use = secret_token_from_session
    else:
        secret_token_to_use = secret_token

    token_generator = ChangeEmailTokenGenerator()
    if not token_generator.check_token(user, secret_token_to_use):
        return construct_default_error()

    uidb64_and_secret_token_valid = True

    if not user.is_active:
        return construct_failed_result(
            "This account is inactive. Please contact support to reactivate it.",
            "inactive",
        )

    checked_password = check_password
    if check_password:
        if not password:
            return construct_failed_result(
                "Please enter the password.",
                "missing_password",
            )
        if not user.check_password(password):
            return construct_failed_result(
                "Incorrect password.",
                "incorrect_password",
            )

    conflicting_user: User | None = (
        User.objects.all()
        .exclude(email="")
        .filter(email__isnull=False)
        .first_existing_with_email_case_insensitive(email=to_email)
    )

    if conflicting_user is not None and conflicting_user != user:
        return construct_failed_result(
            "A different user already has this email.",
            "email_taken",
        )

    if only_check_validation_conditions:
        return construct_success_result()

    user.email = to_email
    user.email_is_verified = True
    user.email_verified_as_of = timezone.now()
    user.save(
        update_fields=["email", "email_is_verified", "email_verified_as_of", "modified"]
    )

    email_change_request.ops.mark_successfully_changed(
        from_email=from_email,
        to_email=to_email,
    )

    if login_if_successful:
        perform_login(request=request, user=user)
        did_login = True

    result = construct_success_result()

    return result
