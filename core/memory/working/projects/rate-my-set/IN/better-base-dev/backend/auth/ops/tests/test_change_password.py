from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from backend.accounts.tests.factories.users import UserFactory
from backend.auth.ops.change_password import (
    FailedChangePasswordResult,
    SuccessfulChangePasswordResult,
    attempt_change_password,
)


@pytest.mark.django_db
class TestAttemptChangePassword:
    # Some password that will pass validation.
    strong_password = "Burn!IngSt@r541"

    def test_error_missing_new_password(self):
        user = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        previous_password = self.strong_password
        new_password = ""

        # NOTE: The assertion at the top of `attempt_change_password` will raise an error
        # instead of returning a `FailedChangePasswordResult` instance.
        with pytest.raises(AssertionError):
            attempt_change_password(
                user,
                previous_password=previous_password,
                new_password=new_password,
                request=None,
            )

    def test_error_invalid_new_password(self):
        user = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        previous_password = self.strong_password
        new_password = "12345"

        with pytest.raises(ValidationError) as exc_info:
            attempt_change_password(
                user,
                previous_password=previous_password,
                new_password=new_password,
                request=None,
            )

        exception = exc_info.value
        assert exception.messages == [
            "This password is too short. It must contain at least 9 characters.",
            "This password is too common.",
            "This password is entirely numeric.",
            "Please include at least one special character (!@#$&*%?) in your password",
        ]

    def test_error_incorrect_password(self):
        user = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        previous_password = self.strong_password + "0"
        new_password = self.strong_password + "1"

        result = attempt_change_password(
            user,
            previous_password=previous_password,
            new_password=new_password,
            request=None,
        )

        assert isinstance(result, FailedChangePasswordResult)
        assert result.user == user
        assert result.message == "Incorrect password."
        assert result.code == "incorrect_password"

    def test_error_inactive_user(self):
        user = UserFactory.create(
            email="email1@example.com", password=self.strong_password, is_active=False
        )
        previous_password = self.strong_password
        new_password = self.strong_password + "1"

        result = attempt_change_password(
            user,
            previous_password=previous_password,
            new_password=new_password,
            request=None,
        )

        assert isinstance(result, FailedChangePasswordResult)
        assert result.user == user
        assert result.message == (
            "This account is inactive. Please contact support to reactivate it."
        )
        assert result.code == "inactive"

    def test_successful_change_password(self):
        user = UserFactory.create(
            email="email1@example.com", password=self.strong_password
        )
        last_modified = user.modified
        old_password_hash = user.password
        previous_password = self.strong_password
        new_password = self.strong_password + "1"

        result = attempt_change_password(
            user,
            previous_password=previous_password,
            new_password=new_password,
            request=None,
        )

        assert isinstance(result, SuccessfulChangePasswordResult)
        assert result.user == user
        assert result.user.password != old_password_hash
        assert result.user.modified > last_modified
        assert result.user.check_password(new_password) is True
        assert result.user.check_password(previous_password) is False
