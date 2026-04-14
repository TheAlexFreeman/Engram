from __future__ import annotations

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from backend.accounts.tests.factories.users import UserFactory
from backend.auth.ops.logout import attempt_logout
from backend.base.tests.helpers.auth import AuthWatcher


@pytest.mark.django_db
class TestLogout:
    @pytest.fixture(autouse=True)
    def setup(self, request_factory: RequestFactory, api_client) -> None:
        self.email = "test@example.com"

        self.user = UserFactory.create(
            email=self.email, name=self.email, is_active=True, email_is_verified=True
        )
        self.request_factory = request_factory

        self.request = self.request_factory.post("/some-endpoint")
        self.request.session = SessionStore()
        self.request.user = self.user

        self.api_client = api_client

    def test_logout_logged_in_user(self):
        user = self.user
        self.api_client.force_login(user)

        auth_watcher = AuthWatcher()

        with auth_watcher.expect_user_logout(user=user):
            attempt_logout(request=self.request)

    def test_logout_already_logged_out_user(self):
        user = self.user

        auth_watcher = AuthWatcher()
        with auth_watcher.expect_user_logout(user=user, assert_counter_equals=1):
            attempt_logout(request=self.request)

        with auth_watcher.expect_no_user_logout(user=user, assert_counter_equals=2):
            attempt_logout(request=self.request)
