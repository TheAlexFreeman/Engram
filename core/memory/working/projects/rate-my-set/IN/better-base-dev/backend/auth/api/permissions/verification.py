from __future__ import annotations

from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from backend.accounts.models.users import User


class HasVerifiedEmail(BasePermission):
    """
    Permission that checks if the requesting `User`'s email has been verified.
    """

    code = "email_not_verified"
    message = _("You must verify your email before you can perform this action.")

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        assert user.is_authenticated and isinstance(user, User), "Pre-condition"

        return bool(user.email and user.email_is_verified)
