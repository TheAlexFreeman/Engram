from __future__ import annotations

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpRequest
from django.test import RequestFactory

from backend.accounts.models.users import User
from backend.accounts.tests.factories.users import UserFactory
from backend.auth.ops.login import (
    FailedLoginResult,
    SuccessfulLoginDidNotPerformLoginResult,
    SuccessfulLoginDidPerformLoginResult,
    attempt_login,
)
from backend.base.tests.helpers.auth import AuthWatcher


@pytest.mark.django_db
class TestLogin:
    @pytest.fixture(autouse=True)
    def setup(self, settings, request_factory: RequestFactory, times) -> None:
        self.settings = settings
        self.request_factory = request_factory

        self.request = self.request_factory.post("/some-endpoint")
        self.request.session = SessionStore()
        self.session = self.request.session

        self.times = times

    def test_login_fail(self):
        email = "test@example.com"
        password = "TestPassword1!"
        wrong_password = "WRONGTestPassword1!"

        result = attempt_login(request=HttpRequest(), email=email, password=password)

        assert type(result) is FailedLoginResult

        assert result.email == email
        assert result.user is None
        assert result.message == (
            "We don't have an account on file for that email address. Either sign "
            "up or double check the provided info and try again."
        )
        assert result.code == "no_user"

        user = UserFactory.create(name=email, email=email)
        user.set_password(password)
        user.save()

        with pytest.raises(AssertionError, match="Pre-condition"):
            attempt_login(request=HttpRequest(), email=email, password="")

        with pytest.raises(AssertionError, match="Pre-condition"):
            attempt_login(request=HttpRequest(), email="", password=password)

        result_wrong_password = attempt_login(
            request=HttpRequest(), email=email, password=wrong_password
        )

        assert type(result_wrong_password) is FailedLoginResult
        assert result_wrong_password.email == email
        assert result_wrong_password.user == user
        assert result_wrong_password.message == "Incorrect password."
        assert result_wrong_password.code == "incorrect_password"

        user.is_active = False
        user.email_is_verified = True
        user.save()

        result_inactive_user = attempt_login(
            request=self.request, email=email, password=password
        )
        assert type(result_inactive_user) is FailedLoginResult
        assert result_inactive_user.email == email
        assert result_inactive_user.user == user
        assert (
            result_inactive_user.message
            == "This account is inactive. Please contact support to reactivate it."
        )
        assert result_inactive_user.code == "inactive"

    def test_login_success(self, request_factory):
        email = "test@example.com"
        password = "TestPassword1!"

        user = UserFactory.create(
            email=email, name=email, is_active=True, email_is_verified=True
        )
        user.set_password(password)
        user.save()

        result = attempt_login(request=self.request, email=email, password=password)
        u = User.objects.get()
        assert u.is_authenticated
        assert self.times.is_close_to_now(u.last_login)

        assert type(result) is SuccessfulLoginDidPerformLoginResult
        assert result.did_perform_login
        assert result.email == email
        assert result.user == user

    def test_login_just_validate(self, request_factory):
        email = "test@example.com"
        password = "TestPassword1!"

        user = UserFactory.create(
            email=email, name=email, is_active=True, email_is_verified=True
        )
        user.set_password(password)
        user.save()

        result = attempt_login(
            request=self.request, email=email, password=password, just_validate=True
        )
        u = User.objects.get()
        assert u.is_authenticated

        assert type(result) is SuccessfulLoginDidNotPerformLoginResult
        assert result.did_perform_login is False
        assert result.email == email
        assert result.user == user

        # Make sure that the finalize_login method returned in the result successfully
        # logs in user
        finalize_login = result.finalize_login

        auth_watcher = AuthWatcher()
        with auth_watcher.expect_user_login(user=user, assert_counter_equals=1):
            finalize_login()
