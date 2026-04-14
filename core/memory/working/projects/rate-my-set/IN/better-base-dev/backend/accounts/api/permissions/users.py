from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from backend.accounts.models.users import User


class UserIsRequestUser(BasePermission):
    """
    Detail permission where `obj` is an instance of `User`.

    Checks that `obj` is exactly the `User` of the `request.user`.

    *Practically*: Only allows access to the User if you are exactly that User.
    """

    message = _("You cannot perform this action on a User that is not you.")

    def has_object_permission(self, request: Request, view: APIView, obj: User) -> bool:
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        return user == obj
