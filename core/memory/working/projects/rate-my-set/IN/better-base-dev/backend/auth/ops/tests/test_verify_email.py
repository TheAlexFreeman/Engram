from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Literal

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sessions.backends.db import SessionStore
from django.test.client import RequestFactory
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from time_machine import TimeMachineFixture

from backend.accounts.models.users import User
from backend.accounts.tests.factories.users import UserFactory
from backend.auth.ops.change_email import ChangeEmailTokenGenerator
from backend.auth.ops.verify_email import (
    FailedAttemptVerifyEmailConfirmResult,
    FailedSendVerificationEmailResult,
    SuccessfulAttemptVerifyEmailConfirmResult,
    SuccessfulSendVerificationEmailResult,
    VerifyEmailTokenGenerator,
    attempt_verify_email_confirm,
    deliver_verification_email,
    generate_verify_email_link,
    send_verification_email,
    verify_email_redirect_run_preparation_logic,
)
from backend.base.tests.helpers.auth import AuthWatcher
from backend.base.tests.helpers.datetimes import Times
from backend.base.tests.helpers.emails import EmailAssertions


@pytest.mark.django_db
class TestVerifyEmailTokenGenerator:
    @pytest.fixture(autouse=True)
    def setup(
        self,
        times: Times,
        settings,
    ) -> None:
        self.times = times
        self.settings = settings

    def test_check_token(self, time_machine: TimeMachineFixture):
        ts1 = self.times.now_incremented
        time_machine.move_to(ts1, tick=False)

        u = UserFactory.create(email="email1@example.com")

        secret_key1 = "secret-key-abcdefg-1234567-1"
        secret_key_fallback1 = "secret-key-fallback-abcdefg-1234567-1"
        secret_key_fallback2 = "secret-key-fallback-abcdefg-1234567-2"
        secret_key_fallback3_not_set = "secret-key-fallback-abcdefg-1234567-3-not-set"
        self.settings.SECRET_KEY = secret_key1
        self.settings.SECRET_KEY_FALLBACKS = [
            secret_key_fallback1,
            secret_key_fallback2,
        ]

        self.settings.VERIFY_EMAIL_TIMEOUT = int(timedelta(hours=1).total_seconds())

        ts2 = self.times.now_incremented
        time_machine.move_to(ts2, tick=True)

        g = VerifyEmailTokenGenerator()

        assert g.check_token(None, None) is False
        assert g.check_token(None, "") is False
        assert g.check_token(None, "abc") is False
        assert g.check_token(None, "@@@-###") is False
        assert g.check_token(u, None) is False
        assert g.check_token(u, "") is False
        assert g.check_token(u, "") is False
        assert g.check_token(u, "@@@-###") is False

        def num_seconds(dt: datetime) -> int:
            return int((dt - datetime(2001, 1, 1)).total_seconds())

        for k in (secret_key1, secret_key_fallback1, secret_key_fallback2):
            now = datetime.now()
            assert (
                g.check_token(u, g._make_token_with_timestamp(u, num_seconds(now), k))
                is True
            )

        invalid_token = g._make_token_with_timestamp(
            u, num_seconds(datetime.now()), secret_key_fallback3_not_set
        )
        assert g.check_token(u, invalid_token) is False

        invalid_time_limit_token = g._make_token_with_timestamp(
            u, num_seconds(datetime.now() - timedelta(seconds=4001)), secret_key1
        )
        valid_time_limit_token = g._make_token_with_timestamp(
            u, num_seconds(datetime.now() - timedelta(seconds=3199)), secret_key1
        )

        assert g.check_token(u, invalid_time_limit_token) is False
        assert g.check_token(u, valid_time_limit_token) is True

    def test_make_hash_value(self, time_machine: TimeMachineFixture):
        ts1 = self.times.now_incremented
        time_machine.move_to(ts1, tick=False)

        u = UserFactory.create(
            email="email1@example.com", email_is_verified=True, last_login=None
        )

        secret_key1 = "secret-key-abcdefg-1234567-1"
        secret_key_fallback1 = "secret-key-fallback-abcdefg-1234567-1"
        secret_key_fallback2 = "secret-key-fallback-abcdefg-1234567-2"
        self.settings.SECRET_KEY = secret_key1
        self.settings.SECRET_KEY_FALLBACKS = [
            secret_key_fallback1,
            secret_key_fallback2,
        ]

        self.settings.VERIFY_EMAIL_TIMEOUT = int(timedelta(hours=1).total_seconds())

        ts2 = self.times.now_incremented
        time_machine.move_to(ts2, tick=True)

        def num_seconds(dt: datetime) -> int:
            return int((dt - datetime(2001, 1, 1)).total_seconds())

        next_int_ts1 = num_seconds(datetime.now())
        g = VerifyEmailTokenGenerator()

        hv1 = g._make_hash_value(u, next_int_ts1)
        hv2 = g._make_hash_value(u, next_int_ts1)
        hv3 = g._make_hash_value(u, next_int_ts1)
        t1 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)
        t2 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)
        t3 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)

        assert hv1 == hv2 == hv3
        assert t1 == t2 == t3

        u = User.objects.get(pk=u.pk)

        reference_tok = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)

        def apply_mutation_and_check(
            attr: str, value: Any, should_change: bool
        ) -> None:
            original_hv1 = g._make_hash_value(u, next_int_ts1)
            original_t1 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)
            original_hv2 = g._make_hash_value(u, next_int_ts1)
            original_t2 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)
            original_hv3 = g._make_hash_value(u, next_int_ts1)
            original_t3 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)

            # Check original stability
            assert original_hv1 == original_hv2 == original_hv3
            assert original_t1 == original_t2 == original_t3

            original_value = getattr(u, attr)
            setattr(u, attr, value)

            next_hv1 = g._make_hash_value(u, next_int_ts1)
            next_t1 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)
            next_hv2 = g._make_hash_value(u, next_int_ts1)
            next_t2 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)
            next_hv3 = g._make_hash_value(u, next_int_ts1)
            next_t3 = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)

            # Check next stability
            assert next_hv1 == next_hv2 == next_hv3
            assert next_t1 == next_t2 == next_t3

            if should_change:
                assert original_hv1 != next_hv1
                assert original_t1 != next_t1
                assert g.check_token(u, reference_tok) is False
            else:
                assert original_hv1 == next_hv1
                assert original_t1 == next_t1
                assert g.check_token(u, reference_tok) is True

            setattr(u, attr, original_value)

        apply_mutation_and_check("pk", u.pk + 1, True)

        original_pw = u.password
        u.set_password("Some-Duck!@!-14#")
        next_pw = u.password
        u.set_password("Some-Duck!@!-15#")
        apply_mutation_and_check("password", next_pw, True)
        u.password = original_pw

        u.last_login = ts1 - timedelta(microseconds=5)
        reference_tok = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)
        apply_mutation_and_check("last_login", None, True)
        apply_mutation_and_check(
            "last_login", timezone.now() + timedelta(seconds=1), True
        )
        apply_mutation_and_check("email", "Email1@example.com", True)
        apply_mutation_and_check("email", "email2@example.com", True)
        apply_mutation_and_check("email", "EmaiL2@example.com", True)
        apply_mutation_and_check("email", "EmaiL2@example.com", True)
        apply_mutation_and_check("email", "email_is_verified", True)

        u = User.objects.get(pk=u.pk)
        reference_tok = g._make_token_with_timestamp(u, next_int_ts1, secret_key1)

        apply_mutation_and_check("email", "email1@example.com", False)

        apply_mutation_and_check(
            "modified", timezone.now() + timedelta(seconds=1), False
        )


@pytest.mark.django_db
class TestVerificationEmailOps:
    @pytest.fixture(autouse=True)
    def setup(
        self,
        times: Times,
        settings,
    ) -> None:
        self.times = times
        self.settings = settings

    def test_generate_verify_email_link(self) -> None:
        email1 = "email1@example.com"
        user1 = UserFactory.create(id=10001, email=email1)
        g1 = generate_verify_email_link(user1)

        expected_token = VerifyEmailTokenGenerator().make_token(user1)
        assert expected_token, "Pre-condition"
        base_url = (self.settings.BASE_WEB_APP_URL or "").removesuffix("/")
        assert base_url, "Pre-condition"
        uidb64 = urlsafe_base64_encode(b"10001")
        assert uidb64 and isinstance(uidb64, str), "Pre-condition"
        assert uidb64 == urlsafe_base64_encode(force_bytes(user1.pk)), "Pre-condition"
        expected_link = (
            f"{base_url}/auth/verify-email/redirect/{uidb64}/{expected_token}"
        )

        assert g1.user == user1
        assert g1.send_email_to == email1
        assert g1.secret_link == expected_link

    def test_deliver_verification_email(self, mailoutbox) -> None:
        email1 = "email1@example.com"
        user1 = UserFactory.create(id=10001, email=email1)
        g1 = generate_verify_email_link(user1)

        expected_token = VerifyEmailTokenGenerator().make_token(user1)
        assert expected_token, "Pre-condition"
        base_url = (self.settings.BASE_WEB_APP_URL or "").removesuffix("/")
        assert base_url, "Pre-condition"
        uidb64 = urlsafe_base64_encode(b"10001")
        assert uidb64 and isinstance(uidb64, str), "Pre-condition"
        assert uidb64 == urlsafe_base64_encode(force_bytes(user1.pk)), "Pre-condition"
        expected_link = (
            f"{base_url}/auth/verify-email/redirect/{uidb64}/{expected_token}"
        )

        assert g1.secret_link == expected_link

        assert len(mailoutbox) == 0, "Pre-condition"

        d1 = deliver_verification_email(user=user1, secret_link=g1.secret_link)

        assert d1.user == user1
        assert d1.sent_email_to == email1
        assert d1.email_send_result.num_sent == 1
        assert self.times.is_close_to_now(d1.email_send_result.sent_at)

        assert len(mailoutbox) == 1
        ea = EmailAssertions(mailoutbox[0])
        ea.assert_is_verification_email(to_email=email1)
        link = ea.extract_verification_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert VerifyEmailTokenGenerator().check_token(user1, token)


@pytest.mark.django_db
class TestSendVerificationEmail:
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
            email=self.email1, is_active=True, email_is_verified=False
        )

    def test_with_nonexistent_user(self, mailoutbox) -> None:
        email = self.email1 + "_"
        result = send_verification_email(email=email)

        assert result
        assert isinstance(result, FailedSendVerificationEmailResult)
        assert result.email == email
        assert result.user is None
        assert result.message == (
            "We don't have an account on file for that email address. Either sign "
            "up or double check the provided info and try again."
        )
        assert result.code == "no_user"

        assert len(mailoutbox) == 0

    def test_with_inactive_user(self, mailoutbox) -> None:
        user = self.user1
        user.is_active = False
        user.save()

        result = send_verification_email(email=user.email)

        assert result
        assert isinstance(result, FailedSendVerificationEmailResult)
        assert result.email == user.email
        assert result.user == user
        assert result.message == (
            "This account is inactive. Please contact support to reactivate it."
        )
        assert result.code == "inactive"

        assert len(mailoutbox) == 0

    @pytest.mark.parametrize("case", ["exact", "case_insensitive"])
    def test_with_already_verified_user(
        self, mailoutbox, case: Literal["exact", "case_insensitive"]
    ) -> None:
        if case == "exact":
            u1 = UserFactory.create(email="email2@example.com")
            email = "email2@example.com"

            assert u1.email == email, "Pre-condition"

        else:
            u1 = UserFactory.create(email="EmaiL2@example.com")
            email = "eMaIl2@example.com"

            assert u1.email != email, "Pre-condition"
            assert u1.email.lower() == email.lower(), "Pre-condition"

        result = send_verification_email(email=email)

        assert result
        assert isinstance(result, FailedSendVerificationEmailResult)
        assert result.email == email
        assert result.user == u1
        assert result.message == "This email is already verified."
        assert result.code == "already_verified"

        assert len(mailoutbox) == 0

    def test_with_successful_send(self, mailoutbox) -> None:
        user = self.user1

        result = send_verification_email(email=user.email)

        assert result
        assert isinstance(result, SuccessfulSendVerificationEmailResult)
        assert result.email == user.email
        assert result.user == user
        assert result.sent_email_to == user.email
        assert result.email_send_result.num_sent == 1
        assert self.times.is_close_to_now(result.email_send_result.sent_at)

        assert len(mailoutbox) == 1
        ea = EmailAssertions(mailoutbox[0])
        ea.assert_is_verification_email(to_email=user.email)
        link = ea.extract_verification_email_link()

        assert link
        token = link.rsplit("/", 1)[1]
        assert VerifyEmailTokenGenerator().check_token(user, token)


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

    secret_token = "verify-email" if use_reset_url_token else "t123"

    r = verify_email_redirect_run_preparation_logic(
        request=request,  # type: ignore[arg-type]
        uidb64=uidb64,
        secret_token=secret_token,
    )

    assert r.uidb64 == uidb64
    assert r.secret_token_to_use == "verify-email"

    if secret_token == "verify-email":
        assert r.did_set_secret_token_in_session is False
        assert session == {}
    else:
        assert r.did_set_secret_token_in_session is True
        assert session == {"verify_email_token": secret_token}


@pytest.mark.django_db
class TestAttemptVerifyEmailConfirm:
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

    def test_error_no_user(self) -> None:
        user1 = UserFactory.create(id=10001, email="email1@example.com")
        uidb64 = urlsafe_base64_encode(b"10001")

        assert uidb64 and isinstance(uidb64, str), "Pre-condition"
        assert uidb64 == urlsafe_base64_encode(force_bytes(user1.pk)), "Pre-condition"

        user1.delete()

        r1 = attempt_verify_email_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token="t123",
            only_check_uidb64_and_secret_token=False,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptVerifyEmailConfirmResult)
        assert r1.uidb64 == uidb64
        assert r1.secret_token == "t123"
        assert r1.only_check_uidb64_and_secret_token is False
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is False
        assert r1.could_request_another_link is True
        assert r1.user is None
        assert r1.email is None
        assert r1.email_is_verified is None
        assert r1.email_verified_as_of is None
        assert r1.did_login is False
        assert r1.message == (
            "The email verification link you followed either has expired or is invalid. "
            "Please request another link to verify your email."
        )
        assert r1.code == "invalid"

    def test_error_reset_url_token_no_secret_token_from_session(self):
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        uidb64 = urlsafe_base64_encode(force_bytes(user1.pk))

        r1 = attempt_verify_email_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token="verify-email",
            only_check_uidb64_and_secret_token=False,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptVerifyEmailConfirmResult)
        assert r1.uidb64 == urlsafe_base64_encode(force_bytes(user1.pk))
        assert r1.secret_token == "verify-email"
        assert r1.only_check_uidb64_and_secret_token is False
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is True
        assert r1.could_request_another_link is True
        assert r1.user == user1
        assert r1.email == user1.email
        assert r1.email_is_verified is False
        assert r1.email_verified_as_of is None
        assert r1.did_login is False
        assert r1.message == (
            "The email verification link you followed either has expired or is invalid. "
            "Please request another link to verify your email."
        )
        assert r1.code == "invalid"

    @pytest.mark.parametrize(
        "set_in_session, secret_token",
        [
            (True, "t123"),
            (False, "t123"),
            (True, "chg"),
            (False, "chg"),
            (True, "rpg"),
            (False, "rpg"),
        ],
    )
    def test_error_invalid_token(self, set_in_session: bool, secret_token: str) -> None:
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        uidb64 = urlsafe_base64_encode(force_bytes(user1.pk))

        if secret_token == "chg":
            secret_token = ChangeEmailTokenGenerator().make_token(user1)
        elif secret_token == "rpg":
            secret_token = PasswordResetTokenGenerator().make_token(user1)

        use_secret_token = "verify-email" if set_in_session else secret_token
        if set_in_session:
            self.session["verify_email_token"] = secret_token

        r1 = attempt_verify_email_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token=use_secret_token,
            only_check_uidb64_and_secret_token=False,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptVerifyEmailConfirmResult)
        assert r1.uidb64 == uidb64
        assert r1.secret_token == use_secret_token
        assert r1.only_check_uidb64_and_secret_token is False
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.could_request_another_link is True
        assert r1.user == user1
        assert r1.email == user1.email
        assert r1.email_is_verified is False
        assert r1.email_verified_as_of is None
        assert r1.did_login is False
        assert r1.message == (
            "The email verification link you followed either has expired or is invalid. "
            "Please request another link to verify your email."
        )
        assert r1.code == "invalid"

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_error_user_inactive(self, set_in_session: bool) -> None:
        user1 = UserFactory.create(
            email="email1@example.com",
            is_active=False,
            email_is_verified=False,
            email_verified_as_of=None,
        )
        uidb64 = urlsafe_base64_encode(force_bytes(user1.pk))
        secret_token = VerifyEmailTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"
        use_secret_token = "verify-email" if set_in_session else secret_token
        if set_in_session:
            self.session["verify_email_token"] = secret_token

        r1 = attempt_verify_email_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token=use_secret_token,
            only_check_uidb64_and_secret_token=False,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptVerifyEmailConfirmResult)
        assert r1.uidb64 == uidb64
        assert r1.secret_token == use_secret_token
        assert r1.only_check_uidb64_and_secret_token is False
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.could_request_another_link is False
        assert r1.user == user1
        assert r1.email == user1.email
        assert r1.email_is_verified is False
        assert r1.email_verified_as_of is None
        assert r1.did_login is False
        assert r1.message == (
            "This account is inactive. Please contact support to reactivate it."
        )
        assert r1.code == "inactive"

    def test_error_with_already_retrieved_uidb64_user(self) -> None:
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        user2 = UserFactory.create(
            email="email2@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )

        user1_idb64 = urlsafe_base64_encode(force_bytes(user1.pk))
        secret_token = VerifyEmailTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"

        r1 = attempt_verify_email_confirm(
            request=self.request,
            uidb64=user1_idb64,
            secret_token=secret_token,
            only_check_uidb64_and_secret_token=False,
            login_if_successful=True,
            already_retrieved_uidb64_user=user2,
        )

        assert isinstance(r1, FailedAttemptVerifyEmailConfirmResult)
        assert r1.uidb64 == user1_idb64
        assert r1.secret_token == secret_token
        assert r1.only_check_uidb64_and_secret_token is False
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is False
        assert r1.could_request_another_link is True
        assert r1.user == user2
        assert r1.email == user2.email
        assert r1.email_is_verified is False
        assert r1.email_verified_as_of is None
        assert r1.did_login is False
        assert r1.message == (
            "The email verification link you followed either has expired or is invalid. "
            "Please request another link to verify your email."
        )
        assert r1.code == "invalid"

    def test_error_without_already_retrieved_uidb64_user(self) -> None:
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )

        uidb64 = urlsafe_base64_encode(force_bytes(user1.pk))
        secret_token = VerifyEmailTokenGenerator().make_token(user1) + "_1"
        assert secret_token, "Pre-condition"

        r1 = attempt_verify_email_confirm(
            request=self.request,
            uidb64=uidb64,
            secret_token=secret_token,
            only_check_uidb64_and_secret_token=False,
            login_if_successful=True,
            already_retrieved_uidb64_user=None,
        )

        assert isinstance(r1, FailedAttemptVerifyEmailConfirmResult)
        assert r1.uidb64 == uidb64
        assert r1.secret_token == secret_token
        assert r1.only_check_uidb64_and_secret_token is False
        assert r1.uidb64_and_secret_token_valid is False
        assert r1.secret_token_was_reset_url_token is False
        assert r1.could_request_another_link is True
        assert r1.user == user1
        assert r1.email == user1.email
        assert r1.email_is_verified is False
        assert r1.email_verified_as_of is None
        assert r1.did_login is False
        assert r1.message == (
            "The email verification link you followed either has expired or is invalid. "
            "Please request another link to verify your email."
        )
        assert r1.code == "invalid"

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_success_only_check_uidb64_and_secret_token(
        self, set_in_session: bool
    ) -> None:
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        uidb64 = urlsafe_base64_encode(force_bytes(user1.pk))
        secret_token = VerifyEmailTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"
        use_secret_token = "verify-email" if set_in_session else secret_token
        if set_in_session:
            self.session["verify_email_token"] = secret_token
        auth_watcher = AuthWatcher()

        with auth_watcher.expect_no_user_login(user1):
            r1 = attempt_verify_email_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=True,
                login_if_successful=True,
                already_retrieved_uidb64_user=None,
            )

        assert isinstance(r1, SuccessfulAttemptVerifyEmailConfirmResult)
        assert r1.uidb64 == uidb64
        assert r1.secret_token == use_secret_token
        assert r1.only_check_uidb64_and_secret_token is True
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.could_request_another_link is True
        assert r1.user == user1
        assert r1.email == user1.email
        # The `email_is_verified` and `email_verified_as_of` fields should not have changed
        assert r1.email_is_verified is False
        assert r1.email_verified_as_of is None
        assert r1.did_login is False

        user1.refresh_from_db()
        assert user1.email_is_verified is False
        assert user1.email_verified_as_of is None

    @pytest.mark.parametrize(
        "set_in_session",
        [
            pytest.param(True, id="set_in_session"),
            pytest.param(False, id="not_set_in_session"),
        ],
    )
    def test_success_with_already_retrieved_uidb64_user_only_uidb64_and_secret_token(
        self, set_in_session: bool
    ):
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        user2 = UserFactory.create(
            email="email2@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )

        user1_idb64 = urlsafe_base64_encode(force_bytes(user1.pk))
        secret_token = VerifyEmailTokenGenerator().make_token(user2)
        assert secret_token, "Pre-condition"
        use_secret_token = "verify-email" if set_in_session else secret_token
        if set_in_session:
            self.session["verify_email_token"] = secret_token
        auth_watcher = AuthWatcher()

        with (
            auth_watcher.expect_no_user_login(user1),
            auth_watcher.expect_no_user_login(user2),
        ):
            r1 = attempt_verify_email_confirm(
                request=self.request,
                uidb64=user1_idb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=True,
                login_if_successful=True,
                already_retrieved_uidb64_user=user2,
            )

        assert isinstance(r1, SuccessfulAttemptVerifyEmailConfirmResult)
        assert r1.uidb64 == user1_idb64
        assert r1.secret_token == use_secret_token
        assert r1.only_check_uidb64_and_secret_token is True
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.could_request_another_link is True
        assert r1.user == user2
        assert r1.email == user2.email
        # The `email_is_verified` and `email_verified_as_of` fields should not have changed
        assert r1.email_is_verified is False
        assert r1.email_verified_as_of is None
        assert r1.did_login is False

        user1.refresh_from_db()
        assert user1.email_is_verified is False
        assert user1.email_verified_as_of is None

        user2.refresh_from_db()
        assert user2.email_is_verified is False
        assert user2.email_verified_as_of is None

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
    ) -> None:
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )

        uidb64 = urlsafe_base64_encode(force_bytes(user1.pk))
        secret_token = VerifyEmailTokenGenerator().make_token(user1)
        assert secret_token, "Pre-condition"
        use_secret_token = "verify-email" if set_in_session else secret_token
        if set_in_session:
            self.session["verify_email_token"] = secret_token

        a = AuthWatcher()
        auth_context_manager = (
            a.expect_user_login if should_login else a.expect_no_user_login
        )
        with auth_context_manager(user1):
            r1 = attempt_verify_email_confirm(
                request=self.request,
                uidb64=uidb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=False,
                login_if_successful=should_login,
                already_retrieved_uidb64_user=None,
            )

        assert isinstance(r1, SuccessfulAttemptVerifyEmailConfirmResult)
        assert r1.uidb64 == uidb64
        assert r1.secret_token == use_secret_token
        assert r1.only_check_uidb64_and_secret_token is False
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.could_request_another_link is True
        assert r1.user == user1
        assert r1.email == user1.email
        assert r1.email_is_verified is True
        assert self.times.is_close_to_now(r1.email_verified_as_of)
        assert r1.did_login is should_login

        user1.refresh_from_db()
        assert user1.email_is_verified is True
        assert self.times.is_close_to_now(user1.email_verified_as_of)

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
    ) -> None:
        user1 = UserFactory.create(
            email="email1@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )
        user2 = UserFactory.create(
            email="email2@example.com",
            email_is_verified=False,
            email_verified_as_of=None,
        )

        user1_idb64 = urlsafe_base64_encode(force_bytes(user1.pk))
        secret_token = VerifyEmailTokenGenerator().make_token(user2)
        assert secret_token, "Pre-condition"
        use_secret_token = "verify-email" if set_in_session else secret_token
        if set_in_session:
            self.session["verify_email_token"] = secret_token

        a = AuthWatcher()
        auth_context_manager = (
            a.expect_user_login if should_login else a.expect_no_user_login
        )
        with auth_context_manager(user2):
            r1 = attempt_verify_email_confirm(
                request=self.request,
                uidb64=user1_idb64,
                secret_token=use_secret_token,
                only_check_uidb64_and_secret_token=False,
                login_if_successful=should_login,
                already_retrieved_uidb64_user=user2,
            )

        assert isinstance(r1, SuccessfulAttemptVerifyEmailConfirmResult)
        assert r1.uidb64 == user1_idb64
        assert r1.secret_token == use_secret_token
        assert r1.only_check_uidb64_and_secret_token is False
        assert r1.uidb64_and_secret_token_valid is True
        assert r1.secret_token_was_reset_url_token is set_in_session
        assert r1.could_request_another_link is True
        assert r1.user == user2
        assert r1.email == user2.email
        assert r1.email_is_verified is True
        assert self.times.is_close_to_now(r1.email_verified_as_of)
        assert r1.did_login is should_login

        user1.refresh_from_db()
        assert user1.email_is_verified is False
        assert user1.email_verified_as_of is None

        user2.refresh_from_db()
        assert user2.email_is_verified is True
        assert self.times.is_close_to_now(user2.email_verified_as_of)
