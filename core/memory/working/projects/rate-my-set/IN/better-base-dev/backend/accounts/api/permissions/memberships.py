from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from backend.accounts.models.memberships import Membership
from backend.accounts.models.users import User
from backend.accounts.types.roles import Role


class MembershipSharesAccountWithRequestingUser(BasePermission):
    """
    Detail permission where `obj` is an instance of `Membership`.

    Checks that the `request`'s `User` (authenticated pre-condition) has a `Membership`
    belonging to `obj.account`.

    *Practically*: Disallows a User from accessing or acting on a Membership that
    doesn't belong to an Account the User is a part of.
    """

    message = _(
        "You must have a membership in the account you are attempting to view or act "
        "on to perform this action."
    )

    def has_object_permission(
        self, request: Request, view: APIView, obj: Membership
    ) -> bool:
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        request_membership = user.get_membership_for_account_id(obj.account_id)
        return request_membership is not None


class MembershipBelongsToRequestingUser(BasePermission):
    """
    Detail permission where `obj` is an instance of `Membership`.

    Checks that `obj` is exactly the `Membership` belonging to the `request`'s `User`
    for `obj.account`.

    *Practically*: Disallows a User from accessing or acting on a Membership that is
    not, literally, its own membership.
    """

    message = _("You cannot perform this action on a membership that is not yours.")

    def has_object_permission(
        self, request: Request, view: APIView, obj: Membership
    ) -> bool:
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        if (
            request_membership := user.get_membership_for_account_id(obj.account_id)
        ) is None:
            return False

        return request_membership == obj


class MembershipOfRequestingUserIsOwner(BasePermission):
    """
    Detail permission where `obj` is an instance of `Membership`.

    Checks that the `request`'s `User` (authenticated pre-condition) has a `Membership`
    belonging to `obj.account`, and that that `Membership` (the one belonging to the
    `request`'s `User`) is an owner.

    *Practically*: Disallows a User from accessing or acting on a Membership if its
    own Membership for the same Account is not an owner.
    """

    message = _(
        "You must be an owner role in the account associated with the membership you "
        "are trying to view or act on to perform this action."
    )

    def has_object_permission(
        self, request: Request, view: APIView, obj: Membership
    ) -> bool:
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        if (
            request_membership := user.get_membership_for_account_id(obj.account_id)
        ) is None:
            return False

        return request_membership.role == Role.OWNER
