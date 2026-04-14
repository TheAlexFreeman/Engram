from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from backend.accounts.models.invitations import Invitation
from backend.accounts.models.users import User
from backend.accounts.types.roles import Role
from backend.utils.case_insensitive_emails import (
    are_emails_equal_case_insensitive_in_db,
)


class InvitationSharesAccountWithRequestingUser(BasePermission):
    """
    Detail permission where `obj` is an instance of `Invitation`.

    Checks that the `request`'s `User` (authenticated pre-condition) has a `Membership`
    belonging to `obj.account`.

    *Practically*: Disallows a User from accessing or acting on an Invitation that
    doesn't belong to an Account the User is a part of.
    """

    message = _(
        "You must have a membership in the account you are attempting to view or act "
        "on to perform this action."
    )
    code = "missing_membership"

    def has_object_permission(
        self, request: Request, view: APIView, obj: Invitation
    ) -> bool:
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        request_membership = user.get_membership_for_account_id(obj.account_id)
        return request_membership is not None


class InvitationAccountHasRequestingUserAsOwner(BasePermission):
    """
    Detail permission where `obj` is an instance of `Invitation`.

    Checks that the `request`'s `User` (authenticated pre-condition) has a `Membership`
    belonging to `obj.account`, and that that `Membership` (the one belonging to the
    `request`'s `User`) is an owner.

    *Practically*: Disallows a User from acting on a Invitation if its Membership for
    the Invitation's Account is not an owner.
    """

    message = _(
        "You must be an owner role in the account associated with the invitation you "
        "are trying to view or act on to perform this action."
    )
    code = "owner_required"

    def has_object_permission(
        self, request: Request, view: APIView, obj: Invitation
    ) -> bool:
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        if (
            request_membership := user.get_membership_for_account_id(obj.account_id)
        ) is None:
            return False

        return request_membership.role == Role.OWNER


class InvitationEmailCaseInsensitiveEqualsUserEmail(BasePermission):
    """
    Detail permission where `obj` is an instance of `Invitation`.

    Checks that the `request`'s `User`'s `email` (authenticated pre-condition) is equal
    to `obj.email` with a case-insensitive comparison.

    *Practically*: Disallows a User from accessing or acting on an Invitation if the
    User's email doesn't match the Invitation's email (in a case-insensitive way).
    """

    message = _(
        "You cannot perform this action on an invitation you are not the invitee of."
    )

    def has_object_permission(
        self, request: Request, view: APIView, obj: Invitation
    ) -> bool:
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        return bool(obj.email and user.email) and (
            obj.email == user.email
            or are_emails_equal_case_insensitive_in_db(obj.email, user.email)
        )
