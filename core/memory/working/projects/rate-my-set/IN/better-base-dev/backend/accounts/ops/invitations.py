from __future__ import annotations

import secrets
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    Literal,
    NotRequired,
    Self,
    TypeAlias,
    TypedDict,
    TypeVar,
)

import structlog
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sessions.backends.base import SessionBase
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, UUIDField
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _
from django.views.decorators.debug import sensitive_variables
from django_stubs_ext import StrOrPromise

from backend.accounts.models import Account, Invitation, Membership, User
from backend.accounts.types.invitations import DeliveryMethod, InvitationStatus
from backend.accounts.types.roles import Role
from backend.base.ops.emails import EmailSendResult, TransactionalEmail
from backend.base.ops.emails import Key as EmailKey
from backend.base.ops.frontend_extra_signaling import (
    set_frontend_extra_data_to_bring_in,
    set_frontend_extra_signaling_data,
)
from backend.utils.case_insensitive_emails import (
    are_emails_equal_case_insensitive_in_db,
)
from backend.utils.model_fields import get_primary_key_field
from backend.utils.transactions import transaction_if_not_in_one_already
from backend.utils.urls import add_query_param_to_url

if TYPE_CHECKING:
    from backend.accounts.api.serializers.invitations import (
        InvitationReadOnlySerializer,
    )
    from backend.accounts.api.serializers.users import UserReadOnlySerializer

logger = structlog.stdlib.get_logger()


class MembershipAlreadyExistsValidationError(ValidationError):
    existing_email: str
    existing_user: User
    existing_membership: Membership

    @classmethod
    def construct_from(
        cls,
        error_message: StrOrPromise,
        *,
        existing_email: str,
        existing_user: User,
        existing_membership: Membership,
        error_code: str = "membership_already_exists",
    ) -> Self:
        instance = cls(error_message, code=error_code)

        instance.existing_email = existing_email
        instance.existing_user = existing_user
        instance.existing_membership = existing_membership

        return instance


def validate_can_create_invitation(
    *,
    initiator: Membership,
    email: str | None,
) -> None:
    if initiator.role != Role.OWNER:
        raise ValidationError(
            _("You must be an account owner to invite new users."),
            code="owner_required",
        )

    if (
        email
        and (
            existing_user := User.objects.first_existing_with_email_case_insensitive(
                email
            )
        )
        is not None
        and (
            existing_membership := existing_user.get_membership_for_account_id(
                initiator.account_id
            )
        )
        is not None
    ):
        raise MembershipAlreadyExistsValidationError.construct_from(
            _("A user with that email address is already a part of your team."),
            existing_email=existing_user.email,
            existing_user=existing_user,
            existing_membership=existing_membership,
        )


def validate_can_update_invitation(
    invitation: Invitation,
    *,
    initiator: Membership,
) -> None:
    if initiator.account != invitation.account:
        raise ValidationError(
            _(
                "You are not a member of the account associated with the invitation "
                "you are trying to update."
            ),
            code="no_membership_in_account",
        )

    # NOTE: If it's ever changed so that non-`OWNER`s can update invitations, then
    # you'll probably want to have a second validator and/or check for changing the
    # `role`, since you probably don't want non-`OWNER`s to be able to change the `role`
    # of an invitation (otherwise they could ultimately give themselves an `OWNER` role
    # by inviting a second account and then promoting their original account to owner).
    if initiator.role != Role.OWNER:
        raise ValidationError(
            _("You must be an account owner to update invitations."),
            code="owner_required",
        )

    try:
        _validate_invitation_is_not_already_accepted(invitation)
    except ValidationError as e:
        raise ValidationError(
            _("You cannot update an invitation that has been accepted."),
            e.code,
        ) from e

    try:
        _validate_invitation_is_not_already_declined(invitation)
    except ValidationError as e:
        raise ValidationError(
            _("You cannot update an invitation that has been declined."),
            e.code,
        ) from e

    try:
        _validate_invitation_is_not_expired(invitation)
    except ValidationError as e:
        raise ValidationError(
            _("You cannot update an invitation that has expired."),
            e.code,
        ) from e


def validate_can_resend_invitation(
    invitation: Invitation,
    *,
    initiator: Membership,
) -> None:
    if initiator.account != invitation.account:
        raise ValidationError(
            _(
                "You are not a member of the account associated with the invitation "
                "you are trying to resend."
            ),
            code="no_membership_in_account",
        )

    if initiator.role != Role.OWNER:
        raise ValidationError(
            _("You must be an account owner to resend invitations."),
            code="owner_required",
        )

    try:
        _validate_invitation_is_not_already_accepted(invitation)
    except ValidationError as e:
        raise ValidationError(
            _("You cannot resend an invitation that has been accepted."),
            e.code,
        ) from e

    try:
        _validate_invitation_is_not_already_declined(invitation)
    except ValidationError as e:
        raise ValidationError(
            _("You cannot resend an invitation that has been declined."),
            e.code,
        ) from e

    try:
        _validate_invitation_is_not_expired(invitation)
    except ValidationError as e:
        raise ValidationError(
            _("You cannot resend an invitation that has expired."),
            e.code,
        ) from e


def validate_can_follow_invitation(invitation: Invitation) -> None:
    try:
        _validate_invitation_is_not_already_accepted(invitation)
    except ValidationError as e:
        raise ValidationError(
            _("This invitation has already been accepted."),
            e.code,
        ) from e

    try:
        _validate_invitation_is_not_expired(invitation)
        _validate_invitation_is_not_past_follow_window(invitation)
    except ValidationError as e:
        error_message = _get_invitation_expired_error_message(
            invitation, action_name="follow"
        )
        raise ValidationError(error_message, e.code) from e

    if (
        found_user := User.objects.first_existing_with_email_case_insensitive(
            invitation.email
        )
    ) is not None and (
        found_membership := found_user.get_membership_for_account_id(
            invitation.account_id
        )
    ) is not None:
        found_email = found_user.email
        error_message = (
            _get_existing_membership_for_followed_or_accepted_invitation_error_message(
                invitation,
                found_email=found_email,
            )
        )
        raise MembershipAlreadyExistsValidationError.construct_from(
            error_message,
            existing_email=found_email,
            existing_user=found_user,
            existing_membership=found_membership,
        )


@dataclass(frozen=True, kw_only=True, slots=True)
class CanAcceptOrDeclineResult:
    invitation: Invitation
    user: User
    request: HttpRequest

    can_attach_result: CanInvitationBeAttachedToUserResult

    can_mark_user_email_as_is_verified: str | None


class EmailMismatchValidationError(ValidationError):
    case: Literal["pre_user_creation", "user_logged_in"]
    user_email: str
    invitation_email: str

    @classmethod
    def construct_from(
        cls,
        error_message: StrOrPromise,
        *,
        case: Literal["pre_user_creation", "user_logged_in"],
        user_email: str,
        invitation_email: str,
        error_code: str = "email_mismatch",
    ) -> Self:
        instance = cls(error_message, code=error_code)

        instance.case = case
        instance.user_email = user_email
        instance.invitation_email = invitation_email

        return instance


@dataclass(frozen=True, kw_only=True, slots=True)
class CanAcceptResult(CanAcceptOrDeclineResult):
    pass


def validate_can_accept_invitation(
    invitation: Invitation,
    *,
    initiator: User,
    request: HttpRequest,
    is_special_pre_user_creation_case: bool,
    existing_invitations_followed_from_session: list[ExpandedSessionFollowedInvitation]
    | None = None,
) -> CanAcceptResult:
    assert initiator.is_authenticated and isinstance(initiator, User), (
        "Current pre-condition"
    )

    try:
        _validate_invitation_is_not_already_accepted(invitation)
    except ValidationError as e:
        raise ValidationError(
            _("This invitation has already been accepted."),
            e.code,
        ) from e

    try:
        _validate_invitation_is_not_already_declined(invitation)
    except ValidationError as e:
        raise ValidationError(
            _(
                "This invitation has already been declined and cannot be used now. If "
                "you'd like a new invitation, please ask the person who invited you to "
                "send another invitation."
            ),
            e.code,
        ) from e

    return _validate_can_accept_or_decline_invitation(
        invitation=invitation,
        initiator=initiator,
        request=request,
        is_special_pre_user_creation_case=is_special_pre_user_creation_case,
        action_name="accept",
        result_type=CanAcceptResult,
        existing_invitations_followed_from_session=existing_invitations_followed_from_session,
    )


@dataclass(frozen=True, kw_only=True, slots=True)
class CanDeclineResult(CanAcceptOrDeclineResult):
    pass


def validate_can_decline_invitation(
    invitation: Invitation,
    *,
    initiator: User,
    request: HttpRequest,
    is_special_pre_user_creation_case: bool,
    existing_invitations_followed_from_session: list[SessionFollowedInvitation]
    | None = None,
) -> CanDeclineResult:
    assert initiator.is_authenticated and isinstance(initiator, User), (
        "Current pre-condition"
    )

    if (
        invitation.user is not None
        and invitation.user != initiator
        and invitation.accepted_at is not None
    ):
        raise ValidationError(
            _(
                "This invitation has already been accepted and hence cannot be "
                "declined."
            ),
            "already_accepted",
        )

    if invitation.accepted_at is not None:
        raise ValidationError(
            _(
                "This invitation has already been accepted and hence cannot be "
                "declined."
            ),
            "already_accepted",
        )

    _validate_invitation_is_not_already_declined(invitation)

    return _validate_can_accept_or_decline_invitation(
        invitation=invitation,
        initiator=initiator,
        request=request,
        is_special_pre_user_creation_case=is_special_pre_user_creation_case,
        action_name="decline",
        result_type=CanDeclineResult,
    )


def validate_can_delete_invitation(
    invitation: Invitation,
    *,
    initiator: Membership,
) -> None:
    if initiator.account != invitation.account:
        raise ValidationError(
            _(
                "You are not a member of the account associated with the invitation "
                "you are trying to delete."
            )
        )

    if initiator.role != Role.OWNER:
        raise ValidationError(_("You must be an account owner to delete invitations."))

    try:
        _validate_invitation_is_not_already_accepted(invitation)
    except ValidationError as e:
        raise ValidationError(
            _("You cannot delete an invitation that has been accepted."),
            e.code,
        ) from e


@sensitive_variables("secret_token")
def create_invitation(
    *,
    account: Account,
    invited_by: User,
    email: str,
    name: str | None,
    role: Role,
    delivery_method: DeliveryMethod,
    override_expires_at: datetime | None = None,
) -> Invitation:
    expires_at: datetime
    if override_expires_at is None:
        expires_after: timedelta = Invitation.default_expires_after
        expires_at = timezone.now() + expires_after
    else:
        expires_at = override_expires_at

    secret_token = _generate_invitation_secret_token(expires_at=expires_at)

    existing_user: User | None
    try:
        existing_user = User.objects.get(email=email)
    except User.DoesNotExist:
        existing_user = None

    return Invitation.objects.create(
        account=account,
        invited_by=invited_by,
        email=email,
        name=(name or ""),
        role=role,
        user=existing_user,
        expires_at=expires_at,
        secret_token=secret_token,
        delivery_method=delivery_method,
    )


class TeamInvitationEmail(TransactionalEmail, key=EmailKey.EMAIL_TEAM_INVITATION):
    @dataclass(kw_only=True)
    class CoreSpec(TransactionalEmail.CoreSpec):
        template_path: str = "emails/team-invitation"

    @dataclass(kw_only=True)
    class RenderSpec(TransactionalEmail.RenderSpec):
        team_display_name: StrOrPromise
        action_text: StrOrPromise
        secret_link: str = field(repr=False)

    @dataclass(kw_only=True)
    class DeliverySpec(TransactionalEmail.DeliverySpec):
        pass

    @classmethod
    @sensitive_variables(
        "invitation",
        "secret_link",
        "email_signature",
        "email_secret_link",
    )
    def prepare(cls, *, invitation: Invitation, existing_user: User | None):
        team_display_name = invitation.team_display_name
        subject = invitation.headline
        # Don't let the email subject get too long.
        if len(force_str(subject or "")) > 100:  # pragma: no cover
            subject = _("Better Base Team Invitation")

        if existing_user is None:
            action_text = _("Create Account")
        else:
            action_text = _("Accept Invitation")

        secret_link = _get_invitation_follow_url(invitation)
        email_signature = get_invitation_email_delivery_signature(invitation)
        email_secret_link = add_query_param_to_url(secret_link, "es", email_signature)

        return cls(
            core=cls.CoreSpec(),
            render=cls.RenderSpec(
                team_display_name=team_display_name,
                action_text=action_text,
                secret_link=email_secret_link,
            ),
            delivery=cls.DeliverySpec(to_email=invitation.email, subject=subject),
        )


def send_invitation(invitation: Invitation) -> EmailSendResult:
    with transaction_if_not_in_one_already():
        assert invitation.email, "Pre-condition"
        user = User.objects.first_existing_with_email_case_insensitive(invitation.email)
        email = TeamInvitationEmail.prepare(invitation=invitation, existing_user=user)
        send_result = email.send()
        mark_invitation_as_sent(
            invitation,
            delivery_data={
                "was_sent": bool(send_result.num_sent),
                "to_email": email.delivery.to_email,
                "sent_at": send_result.sent_at.isoformat(),
                # These are the values at the time of sending.
                "invited_user_id": (None if user is None else user.pk),
                "invited_user_email": (None if user is None else user.email),
            },
        )
        return send_result


def mark_invitation_as_sent(
    invitation: Invitation,
    *,
    delivery_data: dict[str, Any] | None,
) -> None:
    update_fields: list[
        Literal[
            "first_sent_at",
            "last_sent_at",
            "num_times_sent",
            "delivery_data",
            "modified",
        ]
    ] = [
        "last_sent_at",
        "num_times_sent",
        "delivery_data",
        "modified",
    ]

    now = timezone.now()
    later_set_num_times_sent_to_avoid_f_instance_without_refreshing = (
        invitation.num_times_sent or 0
    ) + 1

    if invitation.first_sent_at is None:
        invitation.first_sent_at = now
        update_fields.append("first_sent_at")
    invitation.last_sent_at = now
    invitation.num_times_sent = F("num_times_sent") + 1
    invitation.delivery_data = delivery_data

    invitation.save(update_fields=update_fields)
    invitation.num_times_sent = (
        later_set_num_times_sent_to_avoid_f_instance_without_refreshing
    )


@sensitive_variables(
    "invitation",
    "provided_secret",
    "settings",
    "secret",
    "created_str",
    "status_str",
    "accepted_at_str",
    "user",
    "user_id",
    "user_email",
    "to_hash",
    "initial_hashed_string",
    "finalized_hashed_string",
)
def get_invitation_email_delivery_signature(
    invitation: Invitation, *, provided_secret: str | None = None
) -> str:
    key_salt: Final[str] = (
        "backend.accounts.ops.invitations.get_invitation_email_delivery_signature"
    )
    secret: str = provided_secret or settings.SECRET_KEY
    created_str = invitation.created.isoformat()
    status_str: str = invitation.status or "_"
    accepted_at_str: str = (
        "_" if invitation.accepted_at is None else invitation.accepted_at.isoformat()
    )
    user: User | None = invitation.user
    user_id: int | None = None if user is None else user.pk
    user_email: str | None = None if user is None else user.email
    to_hash: str = (
        f"{invitation.pk}-{invitation.secret_token}-{invitation.email}-{created_str}-"
        f"{status_str}-{accepted_at_str}-{user_id}-{user_email}"
    )

    token_generator = PasswordResetTokenGenerator()
    token_algorithm = token_generator.algorithm or "sha256"

    initial_hashed_string: str = salted_hmac(
        key_salt,
        to_hash,
        secret=secret,
        algorithm=token_algorithm,
    ).hexdigest()
    # Very similar to what Django does in
    # `PasswordResetTokenGenerator._make_token_with_timestamp` (as of Django 4.2 around
    # ~10-24-2023 at least), truncate the hash because it'll be used in URLs and it
    # should be more than fine security wise to do this, etc., while keeping URLs
    # shorter. Django does this with `::2` to get every other character, we'll do the
    # same thing but in reverse order.
    finalized_hashed_string = initial_hashed_string[::-2]

    return finalized_hashed_string


@sensitive_variables(
    "invitation",
    "email_delivery_signature",
    "settings",
    "all_signatures",
    "current_signature",
    "matches",
)
def check_invitation_email_delivery_signature(
    invitation: Invitation,
    email_delivery_signature: str,
) -> bool:
    all_signatures = _get_all_possible_invitation_email_delivery_signatures(invitation)

    matches: list[bool] = []
    for current_signature in all_signatures:
        if current_signature and email_delivery_signature:
            comparison_result = constant_time_compare(
                current_signature, email_delivery_signature
            )
            matches.append(bool(comparison_result))

    return sum([int(v) for v in matches]) >= 1


def update_invitation(
    invitation: Invitation,
    *,
    name: str | None = None,
    role: Role | None = None,
    db_save_only_update_fields: bool = True,
) -> None:
    update_fields: list[Literal["name", "role", "modified"]] = []

    if name is not None:
        invitation.name = name
        update_fields.append("name")

    if role is not None:
        invitation.role = role
        update_fields.append("role")

    if update_fields:
        update_fields.append("modified")

    if db_save_only_update_fields:
        if update_fields:
            invitation.save(update_fields=update_fields)
    else:
        invitation.save()


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowWithBase:
    should_mark_followed: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowWithSecretToken(FollowWithBase):
    secret_token: str = field(repr=False)
    email_signature: str | None = field(repr=False)

    logical_branch: Literal["secret_token"] = "secret_token"


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowWithExistingInvitation(FollowWithBase):
    expanded: ExpandedSessionFollowedInvitation

    logical_branch: Literal["existing_invitation"] = "existing_invitation"


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowWithForceDefaultError(FollowWithBase):
    logical_branch: Literal["force_default_error"] = "force_default_error"


FollowWith: TypeAlias = (
    FollowWithSecretToken | FollowWithExistingInvitation | FollowWithForceDefaultError
)


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowInvitationSuccessfulResult:
    can_follow: Literal[True]

    logical_branch: Literal["secret_token", "existing_invitation"]

    found_invitation: Invitation
    found_user: User | None

    followed_through: Literal["email_link", "direct_link"]
    followed_through_email: str | None


@dataclass(frozen=True, kw_only=True, slots=True)
class FollowInvitationFailedResult:
    can_follow: Literal[False]

    logical_branch: Literal[
        "secret_token", "existing_invitation", "force_default_error"
    ]

    found_invitation: Invitation | None
    found_user: User | None

    followed_through: Literal["email_link", "direct_link"] | None
    followed_through_email: str | None

    error_message: StrOrPromise
    error_code: str


FollowInvitationResult: TypeAlias = (
    FollowInvitationSuccessfulResult | FollowInvitationFailedResult
)


@sensitive_variables(
    "follow_with",
    "secret_token",
    "email_signature",
    "expanded",
    "q",
)
def follow_invitation(
    *,
    request: HttpRequest,
    follow_with: FollowWith,
) -> FollowInvitationResult:
    now = timezone.now()
    found: Invitation | None = None
    user: User | None = None
    followed_through: Literal["email_link", "direct_link"] | None = None
    followed_through_email: str | None = None

    default_error_message = _(
        "Looks like that link has expired! Please request another invitation "
        "from the person who invited you."
    )
    default_error_code = "invalid"

    def successful() -> FollowInvitationSuccessfulResult:
        assert found is not None, "Post-condition"
        assert followed_through is not None, "Post-condition"
        assert follow_with.logical_branch != "force_default_error", "Post-condition"

        return FollowInvitationSuccessfulResult(
            can_follow=True,
            logical_branch=follow_with.logical_branch,
            found_invitation=found,
            found_user=user,
            followed_through=followed_through,
            followed_through_email=followed_through_email,
        )

    def failed(
        error_message: StrOrPromise = default_error_message,
        error_code: str = default_error_code,
    ) -> FollowInvitationFailedResult:
        return FollowInvitationFailedResult(
            can_follow=False,
            logical_branch=follow_with.logical_branch,
            found_invitation=found,
            found_user=user,
            followed_through=followed_through,
            followed_through_email=followed_through_email,
            error_message=error_message,
            error_code=error_code,
        )

    # Allow the default error to be forced right away without proceeding further. This
    # can be useful if outside/calling code runs into a clear error condition and wants
    # to redirect to/render a default error page right away.
    if follow_with.logical_branch == "force_default_error":
        return failed()

    # Prepare the lookup logic for the `Invitation` and/or directly retrieve it,
    # validating along the way (in the case of `"existing_invitation"`).
    if follow_with.logical_branch == "secret_token":
        secret_token = follow_with.secret_token
        email_signature = follow_with.email_signature

        q: Q = (
            Q(secret_token=secret_token)
            & Q(secret_token__isnull=False)
            & (~Q(secret_token=""))
        )
    else:
        assert follow_with.logical_branch == "existing_invitation", "Pre-condition"

        expanded = follow_with.expanded
        found = expanded.invitation

    # Resolve the `Invitation` (and return a failure if it can't be found, etc.)
    # depending on the `logical_branch`.
    try:
        if follow_with.logical_branch == "secret_token":
            found = (
                Invitation.objects.all()
                .with_significant_relations_select_related()
                .filter(q)
                .get()
            )
        else:
            assert follow_with.logical_branch == "existing_invitation", "Pre-condition"
    except (
        TypeError,
        ValueError,
        OverflowError,
        ValidationError,
        Invitation.DoesNotExist,
    ):
        return failed()
    if found is None:  # pragma: no cover
        return failed()
    assert found is not None, "Post-condition"

    # Try to find an existing `User` with the `found` `Invitation`'s `email`
    # (case-insensitive).
    user = (
        User.objects.all()
        .filter(email__isnull=False)
        .exclude(email="")
        .first_existing_with_email_case_insensitive(found.email)
    )

    if found.status != InvitationStatus.OPEN:
        return failed()

    if found.is_past_follow_window:
        return failed()

    # If `should_mark_followed` is specified, then mark the invitation as followed.
    if follow_with.should_mark_followed:
        mark_invitation_as_followed(found)

    # Handle setting the `followed_through` and `followed_through_email` and marking the
    # invitation as followed in the session for the `"secret_token"` logical branch.
    if follow_with.logical_branch == "secret_token":
        followed_through = "direct_link"

        if email_signature and check_invitation_email_delivery_signature(
            found, email_signature
        ):
            followed_through = "email_link"
            followed_through_email = found.email

        if follow_with.should_mark_followed:
            mark_invitation_as_followed_in_session(
                found,
                session=request.session,
                followed_through=followed_through,
                followed_through_email=followed_through_email,
                followed_at=now,
            )

    # Handle setting the `followed_through` and `followed_through_email` for the
    # `"existing_invitation"` logical branch.
    if follow_with.logical_branch == "existing_invitation":
        followed_through = expanded.last_followed_through
        followed_through_email = expanded.last_followed_through_email

    return successful()


def mark_invitation_as_followed(invitation: Invitation) -> None:
    update_fields: list[
        Literal[
            "first_followed_at",
            "last_followed_at",
            "num_times_followed",
            "modified",
        ]
    ] = ["last_followed_at", "num_times_followed", "modified"]

    now = timezone.now()
    later_set_num_times_followed_to_avoid_f_instance_without_refreshing = (
        invitation.num_times_followed or 0
    ) + 1

    if invitation.first_followed_at is None:
        invitation.first_followed_at = now
        update_fields.append("first_followed_at")
    invitation.last_followed_at = now
    invitation.num_times_followed = F("num_times_followed") + 1

    invitation.save(update_fields=update_fields)
    invitation.num_times_followed = (
        later_set_num_times_followed_to_avoid_f_instance_without_refreshing
    )


invitations_followed_session_key: Final[Literal["invitations_followed"]] = (
    "invitations_followed"
)
invitation_last_followed_session_key: Final[Literal["invitation_last_followed"]] = (
    "invitation_last_followed"
)


def mark_invitation_as_followed_in_session(
    invitation: Invitation,
    *,
    session: SessionBase,
    followed_through: Literal["email_link", "direct_link"],
    followed_through_email: str | None = None,
    followed_at: datetime | None = None,
) -> None:
    assert invitation.pk is not None, "Pre-condition"

    if followed_through == "direct_link":
        assert followed_through_email is None, "Pre-condition"

    pk = invitation.pk
    key = invitations_followed_session_key
    existing: list[SessionFollowedInvitation] = session.get(key) or []
    if not isinstance(existing, list):  # pragma: no cover
        logger.error(  # type: ignore[unreachable]
            "Expected `existing` to be a `list`.",
            existing_type=type(existing),
            stack_info=True,
        )
        existing = []

    def should_keep(v: SessionFollowedInvitation) -> bool:
        here_pk = invitation.pk
        here_pk_str = str(here_pk)
        v_pk = v["pk"]
        v_pk_str = str(v_pk)
        # If there's no primary key match definitely keep.
        if here_pk != v_pk and here_pk_str != v_pk_str:
            return True
        # Keep if any of these values differ, otherwise discard.
        return v["last_followed_through"] != followed_through or (
            followed_through_email != v.get("last_followed_through_email")
        )

    new_value: list[SessionFollowedInvitation] = [
        # Put the most recently followed at the start of the list.
        SessionFollowedInvitation(
            pk=pk,
            last_followed_at=(followed_at or timezone.now()).isoformat(),
            last_followed_through=followed_through,
            last_followed_through_email=followed_through_email,
        ),
        # Remove any existing entries for this `pk` that have the same
        # `followed_through` and `followed_through_email` since we're putting a fresh
        # entry at the head of the list.
        *(v for v in existing if should_keep(v)),
    ]
    # Limit to `30` entries max.
    new_value = new_value[:30]

    session[key] = new_value
    session[invitation_last_followed_session_key] = new_value[0]["pk"]

    assert session[key], "Post-condition"
    assert session[invitation_last_followed_session_key] is not None, "Post-condition"


@dataclass(frozen=True, kw_only=True, slots=True)
class RetrieveAndCheckJustFollowedInvitationInSessionSuccessfulResult:
    unsanitized_pk: str | int
    expanded: ExpandedSessionFollowedInvitation


@dataclass(frozen=True, kw_only=True, slots=True)
class RetrieveAndCheckJustFollowedInvitationInSessionFailedResult:
    unsanitized_pk: str | int | None
    expanded: ExpandedSessionFollowedInvitation | None

    error_code: Literal["session_data_missing", "unsanitized_pk_and_expanded_mismatch"]


RetrieveAndCheckJustFollowedInvitationInSessionResult: TypeAlias = (
    RetrieveAndCheckJustFollowedInvitationInSessionSuccessfulResult
    | RetrieveAndCheckJustFollowedInvitationInSessionFailedResult
)


def retrieve_and_check_just_followed_invitation_in_session(
    *, session: SessionBase
) -> RetrieveAndCheckJustFollowedInvitationInSessionResult:
    unsanitized_pk: str | int | None = None
    expanded: ExpandedSessionFollowedInvitation | None = None

    def successful() -> RetrieveAndCheckJustFollowedInvitationInSessionSuccessfulResult:
        assert unsanitized_pk is not None, "Post-condition"
        assert expanded is not None, "Post-condition"

        return RetrieveAndCheckJustFollowedInvitationInSessionSuccessfulResult(
            unsanitized_pk=unsanitized_pk,
            expanded=expanded,
        )

    def failed(
        error_code: Literal[
            "session_data_missing", "unsanitized_pk_and_expanded_mismatch"
        ],
    ) -> RetrieveAndCheckJustFollowedInvitationInSessionFailedResult:
        return RetrieveAndCheckJustFollowedInvitationInSessionFailedResult(
            unsanitized_pk=unsanitized_pk,
            expanded=expanded,
            error_code=error_code,
        )

    unsanitized_pk = session.get(invitation_last_followed_session_key)
    all_expanded = get_invitations_followed_from_session(session)
    expanded = all_expanded[0] if all_expanded else None

    if unsanitized_pk is None or unsanitized_pk == "" or expanded is None:
        return failed(error_code="session_data_missing")

    if unsanitized_pk != expanded.pk and str(unsanitized_pk) != str(expanded.pk):
        return failed(error_code="unsanitized_pk_and_expanded_mismatch")

    if unsanitized_pk != expanded.invitation.pk and str(unsanitized_pk) != str(
        expanded.invitation.pk
    ):
        return failed(error_code="unsanitized_pk_and_expanded_mismatch")

    return successful()


_FOLLOWED_INVITATION_DATA_ALREADY_LOADED_REQUEST_ATTRIBUTE: Final[
    Literal["_followed_invitation_data_already_loaded_"]
] = "_followed_invitation_data_already_loaded_"


def check_and_load_followed_invitation_data(
    *,
    request: HttpRequest,
    set_immediately_redirect_to: bool,
) -> None:
    request_attr = _FOLLOWED_INVITATION_DATA_ALREADY_LOADED_REQUEST_ATTRIBUTE
    if hasattr(request, request_attr) and getattr(request, request_attr):
        return

    session = request.session

    associated_serializer_classes = _get_associated_serializer_classes()
    UserReadOnlySerializer = associated_serializer_classes.UserReadOnlySerializer
    InvitationReadOnlySerializer = (
        associated_serializer_classes.InvitationReadOnlySerializer
    )

    check_result = retrieve_and_check_just_followed_invitation_in_session(
        session=session
    )
    if isinstance(
        check_result, RetrieveAndCheckJustFollowedInvitationInSessionSuccessfulResult
    ):
        result = follow_invitation(
            request=request,
            follow_with=FollowWithExistingInvitation(
                expanded=check_result.expanded, should_mark_followed=False
            ),
        )
    else:
        assert isinstance(
            check_result, RetrieveAndCheckJustFollowedInvitationInSessionFailedResult
        ), "Post-condition"

        result = follow_invitation(
            request=request,
            follow_with=FollowWithForceDefaultError(should_mark_followed=False),
        )

    follow_invitation_dict: dict[str, Any]
    if isinstance(result, FollowInvitationSuccessfulResult):
        existing_user: User | None = result.found_user
        authenticated_user: User | None = (
            request.user if request.user.is_authenticated else None
        )
        invitee_is_authenticated: bool = (
            bool(request.user.is_authenticated)
            and existing_user is not None
            and existing_user == request.user
        )
        invitee_has_email_verified: bool = (
            invitee_is_authenticated
            and existing_user is not None
            and bool(existing_user.email)
            and existing_user.email_is_verified
        )
        follow_invitation_dict = {
            "has_error": False,
            "can_follow": result.can_follow,
            "invitation": InvitationReadOnlySerializer(result.found_invitation).data,
            "existing_user": (
                None
                if existing_user is None
                else UserReadOnlySerializer(existing_user).data
            ),
            "requires_signup": existing_user is None,
            "followed_through_email": (result.followed_through_email or None),
            "authenticated_user": (
                None
                if authenticated_user is None
                else (
                    UserReadOnlySerializer(existing_user).data
                    if (
                        existing_user is not None
                        and existing_user == authenticated_user
                    )
                    else UserReadOnlySerializer(authenticated_user).data
                )
            ),
            "invitee_is_authenticated": invitee_is_authenticated,
            "should_auto_accept": (
                invitee_is_authenticated and invitee_has_email_verified
            ),
        }
        if set_immediately_redirect_to:
            set_frontend_extra_signaling_data(
                request,
                immediately_redirect_to="followInvitation",
            )
        set_frontend_extra_data_to_bring_in(
            request,
            follow_invitation=follow_invitation_dict,
        )
    else:
        assert isinstance(result, FollowInvitationFailedResult), "Post-condition"
        follow_invitation_dict = {
            "has_error": True,
            "can_follow": result.can_follow,
            # NOTE: Hide `invitation` and `existing_user` from the frontend if we can't
            # follow the invitation so that no sensitive information/data is leaked in
            # potentially invalid cases or malicious requests, etc.
            "invitation": None,
            "existing_user": None,
            "requires_signup": "unknown",
            "followed_through_email": None,
            "authenticated_user": (
                UserReadOnlySerializer(request.user).data
                if request.user.is_authenticated
                else None
            ),
            "invitee_is_authenticated": None,
            "should_auto_accept": False,
        }
        follow_invitation_error_dict: dict[str, Any] = {
            "error_message": result.error_message,
            "error_code": result.error_code,
        }
        if set_immediately_redirect_to:
            set_frontend_extra_signaling_data(
                request,
                immediately_redirect_to="followInvitation",
            )
        set_frontend_extra_data_to_bring_in(
            request,
            follow_invitation=follow_invitation_dict,
            follow_invitation_error=follow_invitation_error_dict,
        )

    setattr(request, request_attr, True)


def accept_invitation(
    invitation: Invitation, user: User, *, can_accept_result: CanAcceptResult | None
) -> None:
    def clear_relevant_session_data() -> None:
        assert can_accept_result is not None, "Pre-condition"

        clear_invitation_from_session(
            invitation,
            session=can_accept_result.request.session,
            save_session=True,
        )

    with transaction_if_not_in_one_already():
        # Mark the `Invitation` as accepted.
        _mark_invitation_as_accepted(invitation, user=user)

        if (
            can_accept_result is not None
            and user.email
            and can_accept_result.can_mark_user_email_as_is_verified
            and user.email == can_accept_result.can_mark_user_email_as_is_verified
            and not user.email_is_verified
        ):
            user.email = (
                can_accept_result.can_mark_user_email_as_is_verified or user.email
            )
            user.email_is_verified = True
            email_verified_at_ts = timezone.now()
            user.email_verified_as_of = email_verified_at_ts
            user.modified = email_verified_at_ts
            user.save(
                update_fields=[
                    "email",
                    "email_is_verified",
                    "email_verified_as_of",
                    "modified",
                ]
            )

        if can_accept_result is not None:
            transaction.on_commit(clear_relevant_session_data)


def decline_invitation(
    invitation: Invitation, *, can_decline_result: CanDeclineResult | None
) -> None:
    def clear_relevant_session_data() -> None:
        assert can_decline_result is not None, "Pre-condition"

        clear_invitation_from_session(
            invitation,
            session=can_decline_result.request.session,
            save_session=True,
        )

    with transaction_if_not_in_one_already():
        # Mark the `Invitation` as declined.
        _mark_invitation_as_declined(invitation)

        if can_decline_result is not None:
            transaction.on_commit(clear_relevant_session_data)


def delete_invitation(
    invitation: Invitation, *, request: HttpRequest | None
) -> tuple[int, dict[str, int]]:
    pk_before_deleted = invitation.pk

    def clear_relevant_session_data() -> None:
        assert request is not None, "Pre-condition"

        clear_invitation_from_session(
            invitation,
            session=request.session,
            save_session=True,
            pk_before_deleted=pk_before_deleted,
        )

    with transaction_if_not_in_one_already():
        # Delete the `Invitation`.
        deletion_result = invitation.delete()

        if request is not None:
            transaction.on_commit(clear_relevant_session_data)

        return deletion_result


class SessionFollowedInvitation(TypedDict):
    pk: int
    last_followed_at: str  # ISO 8601 datetime string
    last_followed_through: Literal["email_link", "direct_link"]
    last_followed_through_email: NotRequired[str | None]


@dataclass(kw_only=True, frozen=True, slots=True)
class ExpandedSessionFollowedInvitation:
    pk: int
    invitation: Invitation
    last_followed_at: datetime
    last_followed_through: Literal["email_link", "direct_link"]
    last_followed_through_email: str | None


def get_invitations_followed_from_session(
    session: SessionBase,
) -> list[ExpandedSessionFollowedInvitation]:
    key = invitations_followed_session_key
    value: list[SessionFollowedInvitation] = session.get(key) or []
    if not isinstance(value, list):  # pragma: no cover
        logger.error(  # type: ignore[unreachable]
            "Expected `value` to be a `list`.",
            existing_type=type(value),
            stack_info=True,
        )
        value = []

    pk_field = _get_invitation_model_primary_key_field()
    allowed_types_list = [int, str]
    if isinstance(pk_field, UUIDField):  # pragma: no cover
        allowed_types_list.append(uuid.UUID)
        allowed_types_list.remove(int)
    allowed_types = tuple(allowed_types_list)
    possible_pks: list[int | str | uuid.UUID] = []
    for v in value:
        if isinstance(v["pk"], allowed_types):
            possible_pks.append(v["pk"])

    mapping: dict[int, Invitation] = {}
    if possible_pks:
        mapping = {
            i.pk: i
            for i in Invitation.objects.filter(
                pk__in=possible_pks
            ).with_significant_relations_select_related()
        }

    finalized: list[ExpandedSessionFollowedInvitation] = []
    for v in value:
        if (pk := v["pk"]) in mapping:
            invitation = mapping[pk]
            last_followed_at = datetime.fromisoformat(v["last_followed_at"])
            finalized.append(
                ExpandedSessionFollowedInvitation(
                    pk=pk,
                    invitation=invitation,
                    last_followed_at=last_followed_at,
                    last_followed_through=v["last_followed_through"],
                    last_followed_through_email=v["last_followed_through_email"],
                )
            )

    return finalized


@dataclass(frozen=True, kw_only=True, slots=True)
class CanInvitationBeAttachedToUserResult:
    invitation: Invitation
    user: User

    can_attach: bool

    case_insensitive_email_match: bool

    already_attached: bool
    already_attached_to: User | None
    already_attached_and_matched: bool

    cannot_attach_for_non_user_reasons: bool

    primary_case_satisfied: (
        Literal[
            "already_attached_and_matched",
            "email_link",
            "direct_link",
            "emails_matched_and_verified_accordingly",
            "decline_case_with_verified_and_sufficiently_matching_email",
        ]
        | None
    )
    all_cases_satisfied: list[
        Literal[
            "already_attached_and_matched",
            "email_link",
            "direct_link",
            "emails_matched_and_verified_accordingly",
            "decline_case_with_verified_and_sufficiently_matching_email",
        ]
    ]

    can_verify_user_email: str | None


def can_invitation_be_attached_to_user(
    invitation: Invitation,
    user: User,
    *,
    is_initiator_authenticated: bool,
    is_initiator_email_verified: bool,
    contextual_action_name: Literal["accept", "decline"],
    existing_expanded_session_mappings_result: (
        _GenerateExpandedSessionFollowedInvitationsMappingsResult | None
    ),
    case_insensitive_email_match_already_checked: bool | None = None,
) -> CanInvitationBeAttachedToUserResult:
    assert user.is_authenticated and isinstance(user, User), "Pre-condition"

    if is_initiator_authenticated:
        assert user.is_authenticated, "Current pre-condition"
    if is_initiator_email_verified:
        assert bool(user.email and user.email_is_verified), "Current pre-condition"

    direct_links_mapping: dict[int, ExpandedSessionFollowedInvitation] = {}
    email_links_mapping: dict[int, ExpandedSessionFollowedInvitation] = {}
    if existing_expanded_session_mappings_result is not None:
        direct_links_mapping = (
            existing_expanded_session_mappings_result.direct_links_mapping
        )
        email_links_mapping = (
            existing_expanded_session_mappings_result.email_links_mapping
        )

    can_attach: bool = False

    case_insensitive_email_match: bool
    if case_insensitive_email_match_already_checked is not None:
        case_insensitive_email_match = case_insensitive_email_match_already_checked
    else:
        case_insensitive_email_match = bool(
            user.email and invitation.email
        ) and are_emails_equal_case_insensitive_in_db(user.email, invitation.email)

    already_attached: bool = False
    already_attached_to: User | None = None
    already_attached_and_matched: bool = False

    cannot_attach_for_non_user_reasons: bool = False

    primary_case_satisfied: (
        Literal[
            "already_attached_and_matched",
            "email_link",
            "direct_link",
            "emails_matched_and_verified_accordingly",
            "decline_case_with_verified_and_sufficiently_matching_email",
        ]
        | None
    ) = None
    all_cases_satisfied: list[
        Literal[
            "already_attached_and_matched",
            "email_link",
            "direct_link",
            "emails_matched_and_verified_accordingly",
            "decline_case_with_verified_and_sufficiently_matching_email",
        ]
    ] = []

    can_verify_user_email: str | None = None

    if invitation.user is not None:
        already_attached = True
        already_attached_to = invitation.user
        if already_attached_and_matched := (already_attached_to == user):
            can_attach = True
            all_cases_satisfied.append("already_attached_and_matched")

            # In this case, only set `can_verify_user_email` if all of the necessary
            # open/non-expiration and other conditions are in place and
            # `ele.last_followed_through_email` is there and _exactly matches_
            # `user.email`.
            if (
                invitation.pk in email_links_mapping
                # Shorthand for "Email Link Expanded".
                and (ele := email_links_mapping[invitation.pk])
                and (case_insensitive_email_match)
                and (ele.invitation.pk == invitation.pk)
                and (ele.last_followed_at < invitation.expires_at)
                and (ele.last_followed_through_email)
                and (user.email)
                and (ele.last_followed_through_email == user.email)
            ):
                can_verify_user_email = ele.last_followed_through_email
                assert can_verify_user_email, "Post-condition"
    elif invitation.status != InvitationStatus.OPEN:
        cannot_attach_for_non_user_reasons = True
    else:
        # If we get to here, at the time of writing, we have an open invitation with no
        # `user` attached yet, so we're good to proceed through this branch of the code
        # for checking if `can_attach` can be set to `True`.

        # Case 1: Email link
        if invitation.pk in email_links_mapping:
            # Shorthand for "Email Link Expanded".
            ele = email_links_mapping[invitation.pk]
            if (
                (case_insensitive_email_match)
                and (ele.invitation.pk == invitation.pk)
                and (ele.last_followed_at < invitation.expires_at)
            ):
                all_cases_satisfied.append("email_link")
                can_attach = True

                # Only set `can_verify_user_email` if all of the necessary
                # open/non-expiration and other conditions are in place and
                # `ele.last_followed_through_email` is there and _exactly matches_
                # `user.email`.
                if (
                    (ele.last_followed_through_email)
                    and (user.email)
                    and (ele.last_followed_through_email == user.email)
                ):
                    can_verify_user_email = ele.last_followed_through_email
                    assert can_verify_user_email, "Post-condition"

        # Case 2: Direct link
        if invitation.pk in direct_links_mapping:
            # Shorthand for "Direct Link Expanded".
            dle = direct_links_mapping[invitation.pk]
            if (
                (case_insensitive_email_match)
                and (dle.invitation.pk == invitation.pk)
                and (dle.last_followed_at < invitation.expires_at)
            ):
                all_cases_satisfied.append("direct_link")
                can_attach = True

        # Case 3: Exact match on the email
        if (
            (case_insensitive_email_match)
            and (user.email)
            and (invitation.email)
            and (user.email == invitation.email)
        ):
            all_cases_satisfied.append("emails_matched_and_verified_accordingly")
            can_attach = True

        # Case 4: We're contextually asking about the decline case and the user is
        # authenticated with a verified email.
        if (
            contextual_action_name == "decline"
            and is_initiator_authenticated
            and is_initiator_email_verified
            and (user.email)
            and (user.email_is_verified)
            and (invitation.email)
            and (case_insensitive_email_match)
        ):
            all_cases_satisfied.append(
                "decline_case_with_verified_and_sufficiently_matching_email"
            )
            can_attach = True

    if all_cases_satisfied:
        primary_case_satisfied = all_cases_satisfied[0]

    if can_attach:
        assert primary_case_satisfied, "Current post-condition"
        assert all_cases_satisfied, "Current post-condition"
        assert invitation.user is None or invitation.user == user, (
            "Current post-condition"
        )

    return CanInvitationBeAttachedToUserResult(
        invitation=invitation,
        user=user,
        can_attach=can_attach,
        case_insensitive_email_match=case_insensitive_email_match,
        already_attached=already_attached,
        already_attached_to=already_attached_to,
        already_attached_and_matched=already_attached_and_matched,
        cannot_attach_for_non_user_reasons=cannot_attach_for_non_user_reasons,
        primary_case_satisfied=primary_case_satisfied,
        all_cases_satisfied=all_cases_satisfied,
        can_verify_user_email=can_verify_user_email,
    )


def clear_invitation_from_session(
    invitation: Invitation,
    *,
    session: SessionBase,
    save_session: bool,
    pk_before_deleted: int | None = None,
) -> None:
    pk = pk_before_deleted if invitation.pk is None else invitation.pk
    assert pk is not None, "Pre-condition"
    key = invitations_followed_session_key
    existing: list[SessionFollowedInvitation] = session.get(key) or []
    if not isinstance(existing, list):  # pragma: no cover
        logger.error(  # type: ignore[unreachable]
            "Expected `existing` to be a `list`.",
            existing_type=type(existing),
            stack_info=True,
        )
        existing = []

    def should_keep(v: SessionFollowedInvitation) -> bool:
        here_pk = pk
        here_pk_str = str(here_pk)
        v_pk = v["pk"]
        v_pk_str = str(v_pk)
        # If there's a primary key match, then discard.
        return here_pk != v_pk and here_pk_str != v_pk_str

    new_value: list[SessionFollowedInvitation] = [v for v in existing if should_keep(v)]
    # Limit to `30` entries max.
    new_value = new_value[:30]

    # Delete the last pk (the value associated with the
    # `invitation_last_followed_session_key` in the session) if it matches the pk we're
    # clearing.
    if invitation_last_followed_session_key in session:
        last_pk = session[invitation_last_followed_session_key]
        if last_pk == pk or str(last_pk) == str(pk):
            session.delete(invitation_last_followed_session_key)

    # Set `invitation_last_followed_session_key` consistently the same as logic in
    # `def mark_invitation_as_followed_in_session`.
    session[key] = new_value
    if new_value:
        session[invitation_last_followed_session_key] = new_value[0]["pk"]
    else:
        session.delete(invitation_last_followed_session_key)

    if save_session:
        session.save()


@contextmanager
def restore_session_invitation_data(*, request: HttpRequest):
    list_key = invitations_followed_session_key
    latest_key = invitation_last_followed_session_key
    list_value = request.session.get(list_key, ...)
    latest_value = request.session.get(latest_key, ...)

    try:
        yield
    finally:
        if list_value is not ...:
            request.session[list_key] = list_value
        if latest_value is not ...:
            request.session[latest_key] = latest_value


def construct_temporary_pre_persisted_user_for_acceptance_validation(
    *, email: str
) -> User:
    # -- Fake Id --
    # Comes from: `-1 * (2 ** 129 + 15)`
    #
    # Any database system storing `id`s with 128 bit max size or less should throw an
    # error on this value. We want that because we never want this `User` to be
    # accidentally persisted to the database.
    #
    # We use `+ 15` in the above calculation just to make it a little more unique and
    # more of a "magic" number that could be easily searched for in the codebase or
    # found if there was an error.
    fake_id: Final[int] = -680564733841876926926749214863536422927
    # --         --

    return User(id=fake_id, email=email)


def _validate_invitation_is_not_past_follow_window(invitation: Invitation) -> None:
    if invitation.is_past_follow_window:
        raise ValidationError(
            _("The invitation is expired."), code="past_follow_window"
        )


def _validate_invitation_is_not_expired(invitation: Invitation) -> None:
    if invitation.is_expired:
        raise ValidationError(_("The invitation is expired."), code="expired")


def _validate_invitation_is_not_already_accepted(invitation: Invitation) -> None:
    if invitation.accepted_at is not None:
        raise ValidationError(
            _("The invitation has already been accepted."), code="already_accepted"
        )


def _validate_invitation_is_not_already_declined(invitation: Invitation) -> None:
    if invitation.declined_at is not None:
        raise ValidationError(
            _("The invitation has already been declined."), code="already_declined"
        )


_CanAcceptOrDeclineResultType = TypeVar(
    "_CanAcceptOrDeclineResultType", CanAcceptResult, CanDeclineResult
)


def _validate_can_accept_or_decline_invitation(
    invitation: Invitation,
    *,
    initiator: User,
    request: HttpRequest,
    is_special_pre_user_creation_case: bool,
    action_name: Literal["accept", "decline"],
    result_type: type[_CanAcceptOrDeclineResultType],
    existing_invitations_followed_from_session: list[ExpandedSessionFollowedInvitation]
    | None = None,
) -> _CanAcceptOrDeclineResultType:
    assert action_name in ("accept", "decline"), "Pre-condition"
    if action_name == "accept":
        assert issubclass(result_type, CanAcceptResult), "Pre-condition"
    else:
        assert issubclass(result_type, CanDeclineResult), "Pre-condition"

    is_initiator_authenticated: bool = (
        isinstance(initiator, User)
        and initiator.is_authenticated
        and request.user.is_authenticated
        and initiator == request.user
    )
    is_initiator_email_verified: bool = is_initiator_authenticated and bool(
        initiator.email and initiator.email_is_verified
    )

    do_case_insensitive_emails_match: bool = bool(
        initiator.email and invitation.email
    ) and are_emails_equal_case_insensitive_in_db(initiator.email, invitation.email)
    expanded_list: list[ExpandedSessionFollowedInvitation]
    if existing_invitations_followed_from_session is None:
        expanded_list = get_invitations_followed_from_session(request.session)
    else:
        expanded_list = existing_invitations_followed_from_session
    existing_expanded_session_mappings_result = (
        _generate_expanded_session_followed_invitations_mappings(expanded_list)
    )
    can_attach_result = can_invitation_be_attached_to_user(
        invitation,
        initiator,
        is_initiator_authenticated=is_initiator_authenticated,
        is_initiator_email_verified=is_initiator_email_verified,
        contextual_action_name=action_name,
        existing_expanded_session_mappings_result=existing_expanded_session_mappings_result,
        case_insensitive_email_match_already_checked=do_case_insensitive_emails_match,
    )
    can_attach = can_attach_result.can_attach
    verifiable_email: str | None = can_attach_result.can_verify_user_email
    can_mark_user_email_as_is_verified: str | None = None

    # Do the check for expiration after the above block of code since the above
    # `can_invitation_be_attached_to_user(...)` call also checks for expiration but
    # doesn't have as nice of an error message or as easy as a way to tell that
    # expiration was the reason `can_accept` was not `True`, etc.
    try:
        _validate_invitation_is_not_expired(invitation)
    except ValidationError as e:
        error_message = _get_invitation_expired_error_message(
            invitation, action_name=action_name
        )
        raise ValidationError(error_message, e.code) from e

    if can_attach and verifiable_email and initiator.email == verifiable_email:
        can_mark_user_email_as_is_verified = verifiable_email

    if not can_attach and is_special_pre_user_creation_case:
        raise EmailMismatchValidationError.construct_from(
            _(
                "The email address you are signing up with here does match the email "
                "address you were invited with. Either use that email address to "
                "signup here or signup from the regular signup page."
            ),
            case=(
                "pre_user_creation"
                if is_special_pre_user_creation_case
                else "user_logged_in"
            ),
            user_email=initiator.email,
            invitation_email=invitation.email,
        )

    if not can_attach:
        if action_name == "accept":
            raise ValidationError(
                _(
                    "This invitation cannot be accepted likely because your logged in "
                    "email address does not exactly match the invited email address. "
                    "To fix, please click on the invitation link sent to your email "
                    "address and log in with that email address."
                ),
                "email_mismatch_or_invalid_invitation",
            )
        raise ValidationError(
            _(
                "This invitation cannot be declined likely because your logged in "
                "email address does not exactly match the invited email address. To "
                "fix, please click on the link sent to your email address and log in "
                "with that email address. Alternatively, you may ignore this invitation "
                "and just log in or sign up with your current email address."
            ),
            "email_mismatch_or_invalid_invitation",
        )

    return result_type(
        invitation=invitation,
        user=initiator,
        request=request,
        can_attach_result=can_attach_result,
        can_mark_user_email_as_is_verified=can_mark_user_email_as_is_verified,
    )


def _get_invitation_expired_error_message(
    invitation: Invitation, *, action_name: Literal["follow", "accept", "decline"]
):
    assert action_name in ("follow", "accept", "decline"), "Pre-condition"

    known_invited_by_text = _("the individual who invited you (%(email)s)")
    unknown_invited_by_text = _("the individual who invited you")
    invited_by_text: StrOrPromise
    if invitation.invited_by is None:
        invited_by_text = unknown_invited_by_text
    else:
        invited_by_text = known_invited_by_text % {"email": invitation.invited_by}

    if action_name == "accept":
        expiration_instructions = _(
            "The invitation has expired and cannot be accepted. Please ask "
            "%(invited_by_text)s to send a new invitation."
        )
        return expiration_instructions % {"invited_by_text": invited_by_text}

    if action_name == "decline":
        expiration_instructions = _(
            "The invitation has expired and cannot be declined. If you wish to "
            "formally decline, feel free to notify %(invited_by_text)s or ask for a "
            "a new invitation to be sent. Also, you may ignore this invitation and "
            "just log in or sign up with your current email address."
        )
        return expiration_instructions % {"invited_by_text": invited_by_text}

    expiration_instructions = _(
        "The invitation has expired. Please ask %(invited_by_text)s to send a new "
        "invitation."
    )
    return expiration_instructions % {"invited_by_text": invited_by_text}


def _get_existing_membership_for_followed_or_accepted_invitation_error_message(
    invitation: Invitation,
    *,
    found_email: str,
) -> StrOrPromise:
    team_display_name_to_use = invitation.team_display_name
    if invitation.is_using_fallback_team_display_name:
        team_display_name_to_use = _("This invitation's team")

    instructions = _(
        "We found an already existing membership on file for %(team_display_name)s "
        "with the email address %(email)s. Please log in to your existing account."
    )

    return instructions % {
        "team_display_name": team_display_name_to_use,
        "email": found_email,
    }


@sensitive_variables("underlying_secret", "secret_token")
def _generate_invitation_secret_token(*, expires_at: datetime) -> str:
    prefix: str = expires_at.strftime("%Y%m%d")
    assert prefix and len(prefix) == 8, "Current pre-condition"

    underlying_secret = secrets.token_urlsafe(64)[:32]
    assert underlying_secret and len(underlying_secret) == 32, "Current pre-condition"

    secret_token = f"{prefix}{underlying_secret}"
    assert secret_token and len(secret_token) == 40, "Current pre-condition"

    return secret_token


@sensitive_variables("secret_token", "follow_path", "full_url")
def _get_invitation_follow_url(invitation: Invitation) -> str:
    secret_token = invitation.secret_token
    assert secret_token and len(secret_token) >= 15, "Pre-condition + Sanity check"

    base_url = settings.BASE_WEB_APP_URL
    follow_path = reverse(
        "accounts:invitations-redirect-to-follow", args=(secret_token,)
    )
    full_url = f"{base_url}/{follow_path.removeprefix('/')}"

    return full_url


@sensitive_variables(
    "invitation",
    "settings",
    "secret",
    "fallbacks",
    "all_secrets",
    "current_secret",
    "signatures",
    "signature",
)
def _get_all_possible_invitation_email_delivery_signatures(
    invitation: Invitation,
) -> list[str]:
    secret = settings.SECRET_KEY
    fallbacks = settings.SECRET_KEY_FALLBACKS or []
    all_secrets = [secret, *fallbacks]

    signatures: list[str] = []
    for current_secret in all_secrets:
        if current_secret and (
            signature := get_invitation_email_delivery_signature(
                invitation, provided_secret=current_secret
            )
        ):
            signatures.append(signature)

    return signatures


@dataclass(frozen=True, kw_only=True, slots=True)
class _GenerateExpandedSessionFollowedInvitationsMappingsResult:
    direct_links_mapping: dict[int, ExpandedSessionFollowedInvitation]
    email_links_mapping: dict[int, ExpandedSessionFollowedInvitation]
    invitations_mapping: dict[int, Invitation]


def _generate_expanded_session_followed_invitations_mappings(
    expanded_list: list[ExpandedSessionFollowedInvitation],
) -> _GenerateExpandedSessionFollowedInvitationsMappingsResult:
    direct_links_mapping: dict[int, ExpandedSessionFollowedInvitation] = {}
    email_links_mapping: dict[int, ExpandedSessionFollowedInvitation] = {}
    invitations_mapping: dict[int, Invitation] = {}

    for expanded in expanded_list:
        if expanded.pk is None:  # pragma: no cover
            continue  # type: ignore[unreachable]
        if expanded.pk != expanded.invitation.pk:
            logger.error(
                "Expected `expanded.pk` to match `expanded.invitation.pk`.",
                expanded_pk=expanded.pk,
                expanded_invitation_pk=expanded.invitation.pk,
                stack_info=True,
            )
            continue

        invitation = expanded.invitation

        if expanded.last_followed_through == "direct_link":
            if invitation.pk not in direct_links_mapping:
                direct_links_mapping[invitation.pk] = expanded

        if expanded.last_followed_through == "email_link":
            if invitation.pk not in email_links_mapping:
                email_links_mapping[invitation.pk] = expanded

        invitations_mapping[invitation.pk] = invitation

    return _GenerateExpandedSessionFollowedInvitationsMappingsResult(
        direct_links_mapping=direct_links_mapping,
        email_links_mapping=email_links_mapping,
        invitations_mapping=invitations_mapping,
    )


def _mark_invitation_as_accepted(invitation: Invitation, *, user: User) -> None:
    update_fields: list[Literal["user", "accepted_at", "declined_at", "modified"]] = [
        "user",
        "accepted_at",
        "modified",
    ]
    now = timezone.now()

    invitation.user = user
    invitation.accepted_at = now

    if invitation.declined_at is not None:  # pragma: no cover
        invitation.declined_at = None
        update_fields.append("declined_at")

    invitation.save(update_fields=update_fields)


def _mark_invitation_as_declined(invitation: Invitation) -> None:
    update_fields: list[Literal["declined_at", "modified"]] = [
        "declined_at",
        "modified",
    ]
    now = timezone.now()

    invitation.declined_at = now

    invitation.save(update_fields=update_fields)


@lru_cache(1)
def _get_invitation_model_primary_key_field():
    return get_primary_key_field(Invitation)


@dataclass(frozen=True, kw_only=True, slots=True)
class _GetAssociatedSerializerClassesResult:
    InvitationReadOnlySerializer: type[InvitationReadOnlySerializer]
    UserReadOnlySerializer: type[UserReadOnlySerializer]


# NOTE: This, among other things, resolves circular import issues.
@lru_cache(1)
def _get_associated_serializer_classes() -> _GetAssociatedSerializerClassesResult:
    from backend.accounts.api.serializers.invitations import (
        InvitationReadOnlySerializer,
    )
    from backend.accounts.api.serializers.users import UserReadOnlySerializer

    return _GetAssociatedSerializerClassesResult(
        InvitationReadOnlySerializer=InvitationReadOnlySerializer,
        UserReadOnlySerializer=UserReadOnlySerializer,
    )
