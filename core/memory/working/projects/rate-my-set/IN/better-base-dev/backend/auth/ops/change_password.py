from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.http import HttpRequest
from django.views.decorators.debug import sensitive_variables

from backend.accounts.models import User


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulChangePasswordResult:
    user: User


@dataclass(frozen=True, slots=True, kw_only=True)
class FailedChangePasswordResult:
    user: User
    message: str
    code: str


@sensitive_variables("previous_password", "new_password")
def attempt_change_password(
    user: User,
    *,
    previous_password: str,
    new_password: str,
    request: HttpRequest | None,
) -> SuccessfulChangePasswordResult | FailedChangePasswordResult:
    assert previous_password, "Current pre-condition"
    assert new_password, "Pre-condition"

    def construct_failed_result(message: str, code: str) -> FailedChangePasswordResult:
        return FailedChangePasswordResult(
            user=user,
            message=message,
            code=code,
        )

    if not new_password:
        return construct_failed_result(
            "Please provide a new password.",
            "missing_new_password",
        )

    validate_password(new_password, user)

    if not user.check_password(previous_password):
        return construct_failed_result(
            "Incorrect password.",
            "incorrect_password",
        )

    if not user.is_active:
        return construct_failed_result(
            "This account is inactive. Please contact support to reactivate it.",
            "inactive",
        )

    user.set_password(new_password)
    user.save(update_fields=["password", "modified"])

    if request is not None:
        update_session_auth_hash(request, user)

    return SuccessfulChangePasswordResult(user=user)
