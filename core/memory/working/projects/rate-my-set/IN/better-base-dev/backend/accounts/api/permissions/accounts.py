from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from backend.accounts.models.accounts import Account, AccountType
from backend.accounts.models.users import User
from backend.accounts.types.roles import Role


class AccountMembershipOfRequestingUserIsOwner(BasePermission):
    """
    Detail permission where `obj` is an instance of `Account`.

    Checks that the `request`'s `User` (authenticated pre-condition) has a `Membership`
    belonging to `obj`, and that that `Membership` (the one belonging to the
    `request`'s `User`) is an owner.

    *Practically*: Disallows a User from acting on an Account if they are not an owner
    of that Account.
    """

    message = _("You must be an owner role in the account to perform this action.")
    code = "account_membership_of_requesting_user_is_not_owner"

    def has_object_permission(
        self, request: Request, view: APIView, obj: Account
    ) -> bool:
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        if (request_membership := user.get_membership_for_account_id(obj.pk)) is None:
            return False

        return request_membership.role == Role.OWNER


class RequestingUserHasMembershipInAccount(BasePermission):
    """
    Detail permission where `obj` is an instance of `Account`.

    Checks that the `request`'s `User` (authenticated pre-condition) has a `Membership`
    belonging to `obj`.

    *Practically*: Disallows a User from acting on an Account if they do not have a
    Membership in that Account.
    """

    message = _("You must have a membership in the account to perform this action.")
    code = "requesting_user_does_not_have_membership_in_account"

    def has_object_permission(
        self, request: Request, view: APIView, obj: Account
    ) -> bool:
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        return user.get_membership_for_account_id(obj.pk) is not None


class AccountTypeMustBePersonal(BasePermission):
    """
    Detail permission where `obj` is an instance of `Account`.

    Checks that the `Account`'s `account_type` is equal to `AccountType.PERSONAL`.

    *Practically*: Disallows an action (or retrieval, etc.) from happening on an account
    that is not a personal account.
    """

    message = _(
        "You can only perform this action if the account you're performing it on is a "
        "personal account."
    )
    code = "account_type_is_not_personal"

    def has_object_permission(
        self, request: Request, view: APIView, obj: Account
    ) -> bool:
        return obj.account_type == AccountType.PERSONAL
