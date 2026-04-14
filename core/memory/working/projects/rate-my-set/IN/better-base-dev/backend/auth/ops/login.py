from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeAlias, overload

from django.contrib.auth import authenticate, login
from django.http import HttpRequest
from django.views.decorators.debug import sensitive_variables

from backend.accounts.models import User


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulLoginBaseResult:
    email: str
    user: User


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulLoginDidPerformLoginResult(SuccessfulLoginBaseResult):
    # We logged in.
    did_perform_login: Literal[True]


@dataclass(frozen=True, slots=True, kw_only=True)
class SuccessfulLoginDidNotPerformLoginResult(SuccessfulLoginBaseResult):
    # We didn't actually log in.
    did_perform_login: Literal[False]
    # But we'll provide a callable that the outside caller can use to finalize the login
    # (I.E. this will call `perform_login` and potentially other things down the line).
    finalize_login: Callable[[], None]


SuccessfulLoginResult: TypeAlias = (
    SuccessfulLoginDidPerformLoginResult | SuccessfulLoginDidNotPerformLoginResult
)


@dataclass(frozen=True, slots=True, kw_only=True)
class FailedLoginResult:
    email: str
    user: User | None
    message: str
    code: str


@overload
def attempt_login(
    *,
    request: HttpRequest,
    email: str,
    password: str,
    just_validate: Literal[False] = False,
) -> SuccessfulLoginDidPerformLoginResult | FailedLoginResult: ...


@overload
def attempt_login(
    *,
    request: HttpRequest,
    email: str,
    password: str,
    just_validate: Literal[True],
) -> SuccessfulLoginDidNotPerformLoginResult | FailedLoginResult: ...


@sensitive_variables("password")
def attempt_login(
    *,
    request: HttpRequest,
    email: str,
    password: str,
    just_validate: bool = False,
) -> SuccessfulLoginResult | FailedLoginResult:
    assert email, "Pre-condition"
    assert password, "Pre-condition"

    user: User | None = (
        User.objects.all()
        .exclude(email="")
        .filter(email__isnull=False)
        .first_existing_with_email_case_insensitive(email=email)
    )

    def construct_failed_login_result(message: str, code: str) -> FailedLoginResult:
        return FailedLoginResult(
            email=email,
            user=user,
            message=message,
            code=code,
        )

    if user is None:
        return construct_failed_login_result(
            (
                "We don't have an account on file for that email address. Either sign "
                "up or double check the provided info and try again."
            ),
            "no_user",
        )

    if not password:
        return construct_failed_login_result(
            "Please provide a password.",
            "missing_password",
        )

    # Use the actual found `User`'s `email` so that we have the case-sensitive correct email.
    authenticated_user: User | None = authenticate(
        username=user.email, password=password
    )
    if authenticated_user is None:
        if (
            not user.is_active
            and user.has_usable_password()
            and user.check_password(password)
        ):
            return construct_failed_login_result(
                "This account is inactive. Please contact support to reactivate it.",
                "inactive",
            )
        return construct_failed_login_result(
            "Incorrect password.",
            "incorrect_password",
        )
    user = authenticated_user

    if not user.is_active:
        return construct_failed_login_result(
            "This account is inactive. Please contact support to reactivate it.",
            "inactive",
        )

    def finalize_login() -> None:
        perform_login(request=request, user=user)

    if just_validate:
        return SuccessfulLoginDidNotPerformLoginResult(
            email=email,
            user=user,
            did_perform_login=False,
            finalize_login=finalize_login,
        )

    finalize_login()

    return SuccessfulLoginDidPerformLoginResult(
        email=email,
        user=user,
        did_perform_login=True,
    )


def perform_login(*, request: HttpRequest, user: User) -> None:
    assert user is not None and user.is_authenticated, "Pre-condition"

    login(request, user)
