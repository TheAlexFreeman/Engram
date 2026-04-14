from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from time_machine import TimeMachineFixture

from backend.accounts.tests.factories.users import UserFactory
from backend.auth.ops.change_email import ChangeEmailTokenGenerator
from backend.auth.ops.reset_password import (
    FailedAttemptResetPasswordConfirmResult,
    FailedResetPasswordBeginResult,
    SuccessfulAttemptResetPasswordConfirmResult,
    SuccessfulResetPasswordBeginResult,
    attempt_reset_password_begin,
    attempt_reset_password_confirm,
    deliver_reset_password_email,
    generate_reset_password_link,
    reset_password_redirect_run_preparation_logic,
)
from backend.auth.ops.verify_email import VerifyEmailTokenGenerator
from backend.base.tests.helpers.auth import AuthWatcher
from backend.base.tests.helpers.datetimes import Times
from backend.base.tests.helpers.emails import EmailAssertions


@pytest.mark.django_db
class TestResetPasswordEmailOps:
    @pytest.fixture(autouse=True)
    def setup(
        self,
        times: Times,
        settings,
    ) -> None:
        self.times = times
        self.settings = settings

        self.email1 = "email1@example.com"
        self.user1 = UserFactory.create(id=10001, email=self.email1)

    def test_generate_reset_password_link(self):
        user = self.user1
        g1 = generate_reset_password_link(user)

        expected_token = PasswordResetTokenGenerator().make_token(user)
        assert expected_token, "Pre-condition"
        base_url = (self.settings.BASE_WEB_APP_URL or "").removesuffix("/")
        assert base_url, "Pre-condition"
        uidb64 = urlsafe_base64_encode(b"10001")
        assert uidb64 and isinstance(uidb64, str), "Pre-condition"
        assert uidb64 == urlsafe_base64_encode(force_bytes(user.pk)), "Pre-condition"
        expected_link = (
            f"{base_url}/auth/reset-password/redirect/{uidb64}/{expected_token}"
        )

        assert g1.user == user
        assert g1.send_email_to == user.email
        assert g1.secret_link == expected_link

    def test_deliver_reset_password_email(self, mailoutbox):
        user = self.user1
        g1 = generate_reset_password_link(user)

        expected_token = PasswordResetTokenGenerator().make_token(user)
        assert expected_token, "Pre-condition"
        base_url = (self.settings.BASE_WEB_APP_URL or "").removesuffix("/")
        assert base_url, "Pre-condition"
        uidb64 = urlsafe_base64_encode(b"10001")
        assert uidb64 and isinstance(uidb64, str), "Pre-condition"
        assert uidb64 == urlsafe_base64_encode(force_bytes(user.pk)), "Pre-condition"
        expected_link = (
            f"{base_url}/auth/reset-password/redirect/{uidb64}/{expected_token}"
        )

        assert g1.secret_link == expected_link

        d1 = deliver_reset_password_email(user=user, secret_link=g1.secret_link)

        assert d1.user == user
        assert d1.sent_email_to == user.email
        assert d1.email_send_result.num_sent == 1
        assert self.times.is_close_to_now(d1.email_send_result.sent_at)

        assert len(mailoutbox) == 1
        ea = EmailAssertions(mailoutbox[0])
        ea.assert_is_reset_password_email(to_email=user.email)
        link = ea.extract_reset_password_email_link()

        assert link == expected_link
        token = link.rsplit("/", 1)[1]
        assert PasswordResetTokenGenerator().check_token(user, token)


@pytest.mark.django_db
class TestAttemptResetPasswordBegin:
    # Some password that will pass validation.
    strong_password = "Burn!IngSt@r541"

    @pytest.fixture(autouse=True)
    def setup(
        self,
        times: Times,
        settings,
    ) -> None:
        self.times = times
        self.settings = settings

        self.email1 = "email1@example.com"
        self.user1 = UserFactory.create(
            email=self.email1, password=self.strong_password
        )

    def test_error_no_user(self):
        r = attempt_reset_password_begin(email="email2@example.com")

        assert isinstance(r, FailedResetPasswordBeginResult)
        assert r.email == "email2@example.com"
        assert r.user is None
        assert r.message == (
            "We don't have an account on file for that email address. Either sign "
            "up or double check the provided info and try again."
        )
        assert r.code == "no_user"

    def test_error_inactive_user(self):
        user = self.user1
        user.is_active = False
        user.save()

        r = attempt_reset_password_begin(email=self.email1)

        assert isinstance(r, FailedResetPasswordBeginResult)
        assert r.email == self.email1
        assert r.user == user
        assert r.message == (
            "This account is inactive. Please contact support to reactivate it."
        )
        assert r.code == "inactive"

    def test_error_no_usable_password(self):
        user = self.user1
        user.set_unusable_password()
        user.save()

        r = attempt_reset_password_begin(email=self.email1)

        assert isinstance(r, FailedResetPasswordBeginResult)
        assert r.email == self.email1
        assert r.user == user
        assert r.message == (
            "This type of user account doesn't currently support passwords. Please "
            "log in with your existing method or reach out to support if you need "
            "any additional assistance."
        )
        assert r.code == "no_usable_password"

    def test_success(self, mailoutbox):
        r = attempt_reset_password_begin(email=self.email1)

        assert isinstance(r, SuccessfulResetPasswordBeginResult)
        assert r.email == self.email1
        assert r.sent_email_to == self.email1
        assert r.user == self.user1

        esr = r.email_send_result
        assert esr.num_sent == 1
        assert self.times.is_close_to_now(esr.sent_at)

        assert len(mailoutbox) == 1
        ea = EmailAssertions(mailoutbox[0])
        ea.assert_is_reset_password_email(to_email=self.email1)
        link = ea.extract_reset_password_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert PasswordResetTokenGenerator().check_token(self.user1, token)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "use_reset_url_token",
    [
        pytest.param(True, id="using_reset_url_token"),
        pytest.param(False, id="not_using_reset_url_token"),
    ],
)
def test_redirect_preparation_logic(use_reset_url_token: bool) -> None:
    user1 = UserFactory.create(id=10001, email="email1@example.com")
    uidb64 = urlsafe_base64_encode(b"10001")

    assert uidb64 and isinstance(uidb64, str), "Pre-condition"
    assert uidb64 == urlsafe_base64_encode(force_bytes(user1.pk)), "Pre-condition"

    session: dict[str, Any] = {}
    request = SimpleNamespace(session=session)

    secret_token = "set-password" if use_reset_url_token else "t123"

    r = reset_password_redirect_run_preparation_logic(
        request=request,  # type: ignore[arg-type]
        uidb64=uidb64,
        secret_token=secret_token,
    )

    assert r.uidb64 == uidb64
    assert r.secret_token_to_use == "set-password"

    if secret_token == "set-password":
        assert r.did_set_secret_token_in_session is False
        assert session == {}
    else:
        assert r.did_set_secret_token_in_session is True
        assert session == {"_password_reset_token": secret_token}


@pytest.mark.django_db
class TestAttemptResetPasswordConfirm:
    # Some password that will pass validation.
    strong_password = "Burn!IngSt@r541"

    @pytest.fixture(autouse=True)
    def setup(
        self,
        times: Times,
        settings,
        request_factory: RequestFactory,
    ) -> None:
        self.times = times
        self.settings = settings
        self.request_factory = request_factory

        self.request = self.request_factory.post("/some-endpoint")
        self.request.session = SessionStore()
        self.session = self.request.session

        self.email1 = "email1@example.com"
        self.user1 = UserFactory.create(
            email=self.email1, password=self.strong_password
        )

    def test_error_no_user(self):
        user = UserFactory.create(
            id=10001, email="email0@example.com", password=self.strong_password
        )
        uidb64 = urlsafe_base64_encode(b"10001")

        assert uidb64 and isinstance(uidb64, str), "Pre-condition"
        assert uidb64 == urlsafe_base64_encode(force_bytes(user.pk)), "Pre-condition"

        user.delete()

        r = attempt_reset_password_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token="t123",
            only_check_uidb64_and_secret_token=False,
            password="NewP@ssword123!",
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r, FailedAttemptResetPasswordConfirmResult)
        assert r.user is None
        assert r.uidb64 == uidb64
        assert r.secret_token == "t123"
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is False
        assert r.secret_token_was_reset_url_token is False
        assert r.could_request_another_link is True
        assert r.message == (
            "The reset password link you followed either has expired or is invalid. "
            "Please request another link to reset your password."
        )
        assert r.code == "invalid"

    def test_error_reset_url_token_no_secret_token_from_session(self):
        user = self.user1
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

        r = attempt_reset_password_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token="set-password",
            only_check_uidb64_and_secret_token=False,
            password="NewP@ssword123!",
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r, FailedAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == "set-password"
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is False
        assert r.secret_token_was_reset_url_token is True
        assert r.could_request_another_link is True
        assert r.message == (
            "The reset password link you followed either has expired or is invalid. "
            "Please request another link to reset your password."
        )
        assert r.code == "invalid"

    @pytest.mark.parametrize(
        "set_in_session, secret_token",
        [
            (True, "t123"),
            (False, "t123"),
            (True, "chg"),
            (False, "chg"),
            (True, "vfg"),
            (False, "vfg"),
        ],
    )
    def test_error_invalid_token(self, set_in_session: bool, secret_token: str):
        user = self.user1
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

        if secret_token == "chg":
            secret_token = ChangeEmailTokenGenerator().make_token(user)
        elif secret_token == "vfg":
            secret_token = VerifyEmailTokenGenerator().make_token(user)

        use_secret_token = "set-password" if set_in_session else secret_token
        if set_in_session:
            self.session["_password_reset_token"] = "chg"

        r = attempt_reset_password_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token=use_secret_token,
            only_check_uidb64_and_secret_token=False,
            password="NewP@ssword123!",
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r, FailedAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is False
        assert r.secret_token_was_reset_url_token is set_in_session
        assert r.could_request_another_link is True
        assert r.message == (
            "The reset password link you followed either has expired or is invalid. "
            "Please request another link to reset your password."
        )
        assert r.code == "invalid"

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_error_user_inactive(self, set_in_session: bool):
        user = self.user1
        user.is_active = False
        user.save()

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if set_in_session else secret_token
        if set_in_session:
            self.session["_password_reset_token"] = secret_token

        r = attempt_reset_password_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token=use_secret_token,
            only_check_uidb64_and_secret_token=False,
            password="NewP@ssword123!",
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r, FailedAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is False
        assert r.secret_token_was_reset_url_token is set_in_session
        assert r.could_request_another_link is False
        assert r.message == (
            "This account is inactive. Please contact support to reactivate it."
        )
        assert r.code == "inactive"

    def test_error_with_already_retrieved_uidb64_user(self):
        user1 = self.user1
        user2 = UserFactory.create(
            email="email2@example.com", password=self.strong_password
        )

        user1_idb64 = urlsafe_base64_encode(force_bytes(user1.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"

        r = attempt_reset_password_confirm(
            request=self.request,
            uidb64=user1_idb64,
            secret_token=secret_token,
            only_check_uidb64_and_secret_token=False,
            password="NewP@ssword123!",
            login_if_successful=True,
            already_retrieved_uidb64_user=user2,
        )

        assert isinstance(r, FailedAttemptResetPasswordConfirmResult)
        assert r.user == user2
        assert r.uidb64 == user1_idb64
        assert r.secret_token == secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is False
        assert r.secret_token_was_reset_url_token is False
        assert r.could_request_another_link is True
        assert r.message == (
            "The reset password link you followed either has expired or is invalid. "
            "Please request another link to reset your password."
        )
        assert r.code == "invalid"

    def test_error_without_already_retrieved_uidb64_user(self):
        user = self.user1
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user) + "x"
        assert secret_token, "Pre-condition"

        r = attempt_reset_password_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token=secret_token,
            only_check_uidb64_and_secret_token=False,
            password="NewP@ssword123!",
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r, FailedAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is False
        assert r.secret_token_was_reset_url_token is False
        assert r.could_request_another_link is True
        assert r.message == (
            "The reset password link you followed either has expired or is invalid. "
            "Please request another link to reset your password."
        )
        assert r.code == "invalid"

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_success_only_check_uidb64_and_secret_token(self, set_in_session: bool):
        user = self.user1
        old_password_hash = user.password
        last_modified = user.modified

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if set_in_session else secret_token
        if set_in_session:
            self.session["_password_reset_token"] = secret_token
        auth_watcher = AuthWatcher()

        with auth_watcher.expect_no_user_login(user):
            r = attempt_reset_password_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=True,
                password="NewP@ssword123!",
                login_if_successful=True,
                already_retrieved_uidb64_user=None,
            )

        assert isinstance(r, SuccessfulAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is True
        assert r.uidb64_and_secret_token_valid is True
        assert r.secret_token_was_reset_url_token is set_in_session
        assert r.could_request_another_link is True
        assert r.did_login is False
        assert r.did_set_new_password is False
        assert r.did_add_verifiable_email_to_session is False
        assert r.did_verify_email is False

        # The password should not have changed.
        user.refresh_from_db()
        assert user.password == old_password_hash
        assert user.modified == last_modified

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_success_with_already_retrieved_uidb64_user_only_check_uidb64_and_secret_token(
        self, set_in_session: bool
    ):
        user1 = self.user1
        old_password_hash1 = user1.password
        last_modified1 = user1.modified

        user2 = UserFactory.create(
            email="email2@example.com", password=self.strong_password
        )
        old_password_hash2 = user2.password
        last_modified2 = user2.modified

        user1_idb64 = urlsafe_base64_encode(force_bytes(user1.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user2)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if set_in_session else secret_token
        if set_in_session:
            self.session["_password_reset_token"] = secret_token
        auth_watcher = AuthWatcher()

        with (
            auth_watcher.expect_no_user_login(user1),
            auth_watcher.expect_no_user_login(user2),
        ):
            r = attempt_reset_password_confirm(
                request=self.request,
                uidb64=user1_idb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=True,
                password="NewP@ssword123!",
                login_if_successful=True,
                already_retrieved_uidb64_user=user2,
            )

        assert isinstance(r, SuccessfulAttemptResetPasswordConfirmResult)
        assert r.user == user2
        assert r.uidb64 == user1_idb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is True
        assert r.uidb64_and_secret_token_valid is True
        assert r.secret_token_was_reset_url_token is set_in_session
        assert r.could_request_another_link is True
        assert r.did_login is False
        assert r.did_set_new_password is False
        assert r.did_add_verifiable_email_to_session is False
        assert r.did_verify_email is False

        user1.refresh_from_db()
        assert user1.password == old_password_hash1
        assert user1.modified == last_modified1

        user2.refresh_from_db()
        assert user2.password == old_password_hash2
        assert user2.modified == last_modified2

    def test_error_invalid_password(self):
        user = self.user1
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user)
        assert secret_token, "Pre-condition"

        with pytest.raises(ValidationError) as exc_info:
            attempt_reset_password_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=secret_token,
                only_check_uidb64_and_secret_token=False,
                password="password",
                login_if_successful=True,
                already_retrieved_uidb64_user=None,
            )

        exception = exc_info.value
        assert exception.messages == [
            "This password is too short. It must contain at least 9 characters.",
            "This password is too common.",
            "Please include at least one number in your password",
            "Please include at least one special character (!@#$&*%?) in your password",
        ]

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    @pytest.mark.parametrize(
        "should_login",
        [
            pytest.param(True, id="should_login"),
            pytest.param(False, id="should_not_login"),
        ],
    )
    def test_success_without_already_retrieved_uidb64_user(
        self, set_in_session: bool, should_login: bool
    ):
        user = self.user1
        old_password_hash = user.password
        last_modified = user.modified

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if set_in_session else secret_token
        if set_in_session:
            self.session["_password_reset_token"] = secret_token

        a = AuthWatcher()
        auth_context_manager = (
            a.expect_user_login if should_login else a.expect_no_user_login
        )

        with auth_context_manager(user):
            r = attempt_reset_password_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=False,
                password="NewP@ssword123!",
                login_if_successful=should_login,
                already_retrieved_uidb64_user=None,
            )

        assert isinstance(r, SuccessfulAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is True
        assert r.secret_token_was_reset_url_token is set_in_session
        assert r.could_request_another_link is True
        assert r.did_login is should_login
        assert r.did_set_new_password is True
        assert r.did_add_verifiable_email_to_session is False
        assert r.did_verify_email is False

        user.refresh_from_db()
        assert user.password != old_password_hash
        assert user.modified != last_modified
        assert user.check_password("NewP@ssword123!")
        assert self.times.is_close_to_now(user.modified)

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    @pytest.mark.parametrize(
        "should_login",
        [
            pytest.param(True, id="should_login"),
            pytest.param(False, id="should_not_login"),
        ],
    )
    def test_success_with_already_retrieved_uidb64_user(
        self, set_in_session: bool, should_login: bool
    ):
        user1 = self.user1
        old_password_hash1 = user1.password
        last_modified1 = user1.modified

        user2 = UserFactory.create(
            email="email2@example.com", password=self.strong_password + "2"
        )
        old_password_hash2 = user2.password
        last_modified2 = user2.modified

        user1_idb64 = urlsafe_base64_encode(force_bytes(user1.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user2)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if set_in_session else secret_token
        if set_in_session:
            self.session["_password_reset_token"] = secret_token

        a = AuthWatcher()
        auth_context_manager = (
            a.expect_user_login if should_login else a.expect_no_user_login
        )

        with a.expect_no_user_login(user1), auth_context_manager(user2):
            r = attempt_reset_password_confirm(
                request=self.request,
                uidb64=user1_idb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=False,
                password="NewP@ssword123!",
                login_if_successful=should_login,
                already_retrieved_uidb64_user=user2,
            )

        assert isinstance(r, SuccessfulAttemptResetPasswordConfirmResult)
        assert r.user == user2
        assert r.uidb64 == user1_idb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is True
        assert r.secret_token_was_reset_url_token is set_in_session
        assert r.could_request_another_link is True
        assert r.did_login is should_login
        assert r.did_set_new_password is True
        assert r.did_add_verifiable_email_to_session is False
        assert r.did_verify_email is False

        user1.refresh_from_db()
        assert user1.password == old_password_hash1
        assert user1.modified == last_modified1

        user2.refresh_from_db()
        assert user2.password != old_password_hash2
        assert user2.modified > last_modified2
        assert self.times.is_close_to_now(user2.modified)
        assert user2.check_password("NewP@ssword123!")


@pytest.mark.django_db
class TestPasswordResetEmailVerification:
    # Some password that will pass validation.
    strong_password = "Burn!IngSt@r541"

    @pytest.fixture(autouse=True)
    def setup(
        self,
        times: Times,
        settings,
        request_factory: RequestFactory,
    ) -> None:
        self.times = times
        self.settings = settings
        self.request_factory = request_factory

        self.request = self.request_factory.post("/some-endpoint")
        self.request.session = SessionStore()
        self.session = self.request.session

        self.email1 = "email1@example.com"
        self.user1 = UserFactory.create(
            email=self.email1,
            password=self.strong_password,
            email_is_verified=False,
            email_verified_as_of=None,
        )

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_no_verification_only_check_uidb64_and_secret_token(
        self, set_in_session: bool
    ):
        user = self.user1
        old_password_hash = user.password
        last_modified = user.modified

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if set_in_session else secret_token
        if set_in_session:
            self.session["_password_reset_token"] = secret_token
        auth_watcher = AuthWatcher()

        with auth_watcher.expect_no_user_login(user):
            r = attempt_reset_password_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=True,
                password="NewP@ssword123!",
                login_if_successful=True,
                already_retrieved_uidb64_user=None,
            )

        assert isinstance(r, SuccessfulAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is True
        assert r.uidb64_and_secret_token_valid is True
        assert r.secret_token_was_reset_url_token is set_in_session
        assert r.could_request_another_link is True
        assert r.did_login is False
        assert r.did_set_new_password is False
        assert r.did_add_verifiable_email_to_session is True
        assert r.did_verify_email is False

        # Check email record in session.
        verifiable_email_records = self.session.get("reset_password_verifiable_emails")
        assert verifiable_email_records and isinstance(verifiable_email_records, list)
        assert len(verifiable_email_records) == 1
        record = verifiable_email_records[0]
        assert record["email"] == user.email
        assert record["user_pk"] == user.pk
        assert self.times.is_close_to_now(datetime.fromisoformat(record["followed_at"]))

        # Should not have changed password or verified email.
        user.refresh_from_db()
        assert user.email_is_verified is False
        assert user.email_verified_as_of is None
        assert user.password == old_password_hash
        assert user.modified == last_modified

    @pytest.mark.parametrize(
        "token_set_in_session",
        [
            pytest.param(True, id="token_set_in_session"),
            pytest.param(False, id="token_not_set_in_session"),
        ],
    )
    @pytest.mark.parametrize(
        "should_login",
        [
            pytest.param(True, id="should_login"),
            pytest.param(False, id="should_not_login"),
        ],
    )
    def test_no_verification_no_email_record_in_session(
        self, token_set_in_session: bool, should_login: bool
    ):
        user = self.user1
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if token_set_in_session else secret_token
        if token_set_in_session:
            self.session["_password_reset_token"] = secret_token
        auth_watcher = AuthWatcher()
        auth_context_manager = (
            auth_watcher.expect_user_login
            if should_login
            else auth_watcher.expect_no_user_login
        )

        assert self.session.get("reset_password_verifiable_emails") is None, (
            "Pre-condition"
        )

        with auth_context_manager(user):
            r = attempt_reset_password_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=False,
                password="NewP@ssword123!",
                login_if_successful=should_login,
                already_retrieved_uidb64_user=None,
            )

        # No email added to session when `only_check_uidb64_and_secret_token` is False.
        assert self.session.get("reset_password_verifiable_emails") == []

        assert isinstance(r, SuccessfulAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is True
        assert r.secret_token_was_reset_url_token is token_set_in_session
        assert r.could_request_another_link is True
        assert r.did_login is should_login
        assert r.did_set_new_password is True
        assert r.did_add_verifiable_email_to_session is False
        assert r.did_verify_email is False

        user.refresh_from_db()
        assert user.email_is_verified is False
        assert user.email_verified_as_of is None

    @pytest.mark.parametrize(
        "token_set_in_session",
        [
            pytest.param(True, id="token_set_in_session"),
            pytest.param(False, id="token_not_set_in_session"),
        ],
    )
    @pytest.mark.parametrize(
        "should_login",
        [
            pytest.param(True, id="should_login"),
            pytest.param(False, id="should_not_login"),
        ],
    )
    def test_no_verification_case_sensitive_email_match(
        self, token_set_in_session: bool, should_login: bool
    ):
        user = self.user1
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if token_set_in_session else secret_token
        if token_set_in_session:
            self.session["_password_reset_token"] = secret_token
        now = self.times.now.isoformat()

        # Add case-insensitve email matches to the session.
        self.session["reset_password_verifiable_emails"] = [
            {"email": "Email1@example.com", "user_pk": user.pk, "followed_at": now},
            {"email": "EmAiL1@example.com", "user_pk": user.pk, "followed_at": now},
            {"email": "EMAIL1@example.com", "user_pk": user.pk, "followed_at": now},
        ]

        auth_watcher = AuthWatcher()
        auth_context_manager = (
            auth_watcher.expect_user_login
            if should_login
            else auth_watcher.expect_no_user_login
        )

        with auth_context_manager(user):
            r = attempt_reset_password_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=False,
                password="NewP@ssword123!",
                login_if_successful=should_login,
                already_retrieved_uidb64_user=None,
            )

        assert isinstance(r, SuccessfulAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is True
        assert r.secret_token_was_reset_url_token is token_set_in_session
        assert r.could_request_another_link is True
        assert r.did_login is should_login
        assert r.did_set_new_password is True
        assert r.did_add_verifiable_email_to_session is False
        assert r.did_verify_email is False

        user.refresh_from_db()
        assert user.email_is_verified is False
        assert user.email_verified_as_of is None

    @pytest.mark.parametrize(
        "token_set_in_session",
        [
            pytest.param(True, id="token_set_in_session"),
            pytest.param(False, id="token_not_set_in_session"),
        ],
    )
    @pytest.mark.parametrize(
        "should_login",
        [
            pytest.param(True, id="should_login"),
            pytest.param(False, id="should_not_login"),
        ],
    )
    def test_no_verification_expired_email_record(
        self,
        token_set_in_session: bool,
        should_login: bool,
        time_machine: TimeMachineFixture,
    ):
        user = self.user1
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if token_set_in_session else secret_token
        if token_set_in_session:
            self.session["_password_reset_token"] = secret_token

        time_machine.move_to(self.times.now, tick=False)

        # Add email record to session.
        self.session["reset_password_verifiable_emails"] = [
            {
                "email": user.email,
                "user_pk": user.pk,
                "followed_at": self.times.now.isoformat(),
            }
        ]

        # Move time forward to expire the token.
        time_machine.move_to(
            self.times.now + timedelta(seconds=self.settings.PASSWORD_RESET_TIMEOUT),
        )

        r = attempt_reset_password_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token=use_secret_token,
            only_check_uidb64_and_secret_token=False,
            password="NewP@ssword123!",
            login_if_successful=should_login,
            already_retrieved_uidb64_user=None,
        )

        # Expired email should have been pruned.
        assert self.session.get("reset_password_verifiable_emails") == []

        assert isinstance(r, SuccessfulAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is True
        assert r.secret_token_was_reset_url_token is token_set_in_session
        assert r.could_request_another_link is True
        assert r.did_login is should_login
        assert r.did_set_new_password is True
        assert r.did_add_verifiable_email_to_session is False
        assert r.did_verify_email is False

        user.refresh_from_db()
        assert user.email_is_verified is False
        assert user.email_verified_as_of is None

    @pytest.mark.parametrize(
        "token_set_in_session",
        [
            pytest.param(True, id="token_set_in_session"),
            pytest.param(False, id="token_not_set_in_session"),
        ],
    )
    @pytest.mark.parametrize(
        "should_login",
        [
            pytest.param(True, id="should_login"),
            pytest.param(False, id="should_not_login"),
        ],
    )
    def test_verification_email_already_in_session(
        self,
        token_set_in_session: bool,
        should_login: bool,
        time_machine: TimeMachineFixture,
    ):
        user = self.user1
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if token_set_in_session else secret_token
        if token_set_in_session:
            self.session["_password_reset_token"] = secret_token

        time_machine.move_to(self.times.now, tick=False)
        now = self.times.now.isoformat()

        # Add email record to session.
        self.session["reset_password_verifiable_emails"] = [
            {"email": user.email, "user_pk": user.pk, "followed_at": now}
        ]

        auth_watcher = AuthWatcher()
        auth_context_manager = (
            auth_watcher.expect_user_login
            if should_login
            else auth_watcher.expect_no_user_login
        )

        # Three minutes before the session email record would expire.
        later = self.times.now + timedelta(
            seconds=self.settings.PASSWORD_RESET_TIMEOUT - 180
        )
        time_machine.move_to(later)

        with auth_context_manager(user):
            r = attempt_reset_password_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=False,
                password="NewP@ssword123!",
                login_if_successful=should_login,
                already_retrieved_uidb64_user=None,
            )

        assert isinstance(r, SuccessfulAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is True
        assert r.secret_token_was_reset_url_token is token_set_in_session
        assert r.could_request_another_link is True
        assert r.did_login is should_login
        assert r.did_set_new_password is True
        assert r.did_add_verifiable_email_to_session is False
        assert r.did_verify_email is True

        user.refresh_from_db()
        assert user.email_is_verified is True
        assert user.email_verified_as_of == self.times.CloseTo(later)

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    @pytest.mark.parametrize(
        "should_login",
        [
            pytest.param(True, id="should_login"),
            pytest.param(False, id="should_not_login"),
        ],
    )
    def test_verification_full_flow_without_already_retrieved_uidb64_user(
        self, set_in_session: bool, should_login: bool
    ):
        user = self.user1
        user.email_is_verified = False
        user.email_verified_as_of = None
        user.save()

        old_password_hash = user.password
        last_modified = user.modified

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if set_in_session else secret_token
        if set_in_session:
            self.session["_password_reset_token"] = secret_token

        auth_watcher = AuthWatcher()

        # Simulate the pre-redirect logic to store verifiable email in session.
        with auth_watcher.expect_no_user_login(user):
            r1 = attempt_reset_password_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=True,
                password="NewP@ssword123!",
                login_if_successful=should_login,
                already_retrieved_uidb64_user=None,
            )

        assert isinstance(r1, SuccessfulAttemptResetPasswordConfirmResult)
        assert r1.user == user
        assert r1.uidb64 == uidb64
        assert r1.secret_token == use_secret_token
        assert r1.only_check_uidb64_and_secret_token is True
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.could_request_another_link is True
        assert r1.did_login is False
        assert r1.did_set_new_password is False
        assert r1.did_add_verifiable_email_to_session is True
        assert r1.did_verify_email is False

        verifiable_email_records = self.session.get("reset_password_verifiable_emails")
        assert verifiable_email_records and isinstance(verifiable_email_records, list)
        assert len(verifiable_email_records) == 1
        record = verifiable_email_records[0]
        assert record["email"] == user.email
        assert record["user_pk"] == user.pk
        assert self.times.is_close_to_now(datetime.fromisoformat(record["followed_at"]))

        auth_context_manager = (
            auth_watcher.expect_user_login
            if should_login
            else auth_watcher.expect_no_user_login
        )

        with auth_context_manager(user):
            r = attempt_reset_password_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=False,
                password="NewP@ssword123!",
                login_if_successful=should_login,
                already_retrieved_uidb64_user=None,
            )

        assert isinstance(r, SuccessfulAttemptResetPasswordConfirmResult)
        assert r.user == user
        assert r.uidb64 == uidb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is True
        assert r.secret_token_was_reset_url_token is set_in_session
        assert r.could_request_another_link is True
        assert r.did_login is should_login
        assert r.did_set_new_password is True
        assert r.did_add_verifiable_email_to_session is False
        assert r.did_verify_email is True

        user.refresh_from_db()
        assert user.password != old_password_hash
        assert user.modified != last_modified
        assert user.check_password("NewP@ssword123!")
        assert self.times.is_close_to_now(user.modified)

        assert user.email_is_verified is True
        assert self.times.is_close_to_now(user.email_verified_as_of)

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    @pytest.mark.parametrize(
        "should_login",
        [
            pytest.param(True, id="should_login"),
            pytest.param(False, id="should_not_login"),
        ],
    )
    def test_verification_full_flow_with_already_retrieved_uidb64_user(
        self, set_in_session: bool, should_login: bool
    ):
        user1 = self.user1
        old_password_hash1 = user1.password
        last_modified1 = user1.modified

        user2 = UserFactory.create(
            email="email2@example.com", password=self.strong_password
        )
        user2.email_is_verified = False
        user2.email_verified_as_of = None
        user2.save()

        old_password_hash2 = user2.password
        last_modified2 = user2.modified

        uidb64 = urlsafe_base64_encode(force_bytes(user1.pk))
        secret_token = PasswordResetTokenGenerator().make_token(user2)
        assert secret_token, "Pre-condition"
        use_secret_token = "set-password" if set_in_session else secret_token
        if set_in_session:
            self.session["_password_reset_token"] = secret_token

        auth_watcher = AuthWatcher()

        # Simulate the pre-redirect logic to store verifiable email in session.
        with auth_watcher.expect_no_user_login(user2):
            r1 = attempt_reset_password_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=True,
                password="NewP@ssword123!",
                login_if_successful=should_login,
                already_retrieved_uidb64_user=user2,
            )

        assert isinstance(r1, SuccessfulAttemptResetPasswordConfirmResult)
        assert r1.user == user2
        assert r1.uidb64 == uidb64
        assert r1.secret_token == use_secret_token
        assert r1.only_check_uidb64_and_secret_token is True
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.could_request_another_link is True
        assert r1.did_login is False
        assert r1.did_set_new_password is False
        assert r1.did_add_verifiable_email_to_session is True
        assert r1.did_verify_email is False

        verifiable_email_records = self.session.get("reset_password_verifiable_emails")
        assert verifiable_email_records
        assert len(verifiable_email_records) == 1
        record = verifiable_email_records[0]
        assert record["email"] == user2.email
        assert record["user_pk"] == user2.pk
        assert self.times.is_close_to_now(datetime.fromisoformat(record["followed_at"]))

        auth_context_manager = (
            auth_watcher.expect_user_login
            if should_login
            else auth_watcher.expect_no_user_login
        )

        with auth_context_manager(user2):
            r = attempt_reset_password_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=False,
                password="NewP@ssword123!",
                login_if_successful=should_login,
                already_retrieved_uidb64_user=user2,
            )

        assert isinstance(r, SuccessfulAttemptResetPasswordConfirmResult)
        assert r.user == user2
        assert r.uidb64 == uidb64
        assert r.secret_token == use_secret_token
        assert r.only_check_uidb64_and_secret_token is False
        assert r.uidb64_and_secret_token_valid is True
        assert r.secret_token_was_reset_url_token is set_in_session
        assert r.could_request_another_link is True
        assert r.did_login is should_login
        assert r.did_set_new_password is True
        assert r.did_add_verifiable_email_to_session is False
        assert r.did_verify_email is True

        user1.refresh_from_db()
        assert user1.password == old_password_hash1
        assert user1.modified == last_modified1

        user2.refresh_from_db()
        assert user2.password != old_password_hash2
        assert user2.modified != last_modified2
        assert user2.check_password("NewP@ssword123!")
        assert self.times.is_close_to_now(user2.modified)

        assert user2.email_is_verified is True
        assert self.times.is_close_to_now(user2.email_verified_as_of)
